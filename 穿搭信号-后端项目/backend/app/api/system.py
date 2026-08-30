import asyncio
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.auth import CurrentUser
from app.domain.weather_rules import WeatherInput, evaluate_weather_rules
from app.schemas import GarmentAssetResponse, RecommendationAdviceRequest, RecommendationRequest, WeatherRuleRequest
from app.services.outfit_ai_service import OutfitAIService
from app.services.outfit_image_service import OutfitImageService
from app.services.recommendation_service import (
    NoRecommendationError,
    recommend_ai_outfit,
    recommend_official_outfit,
    recommend_personal_outfit,
    recommend_system_ai_outfit,
)
from app.services.store import AI_USAGE_LIMITS, store, user_local_date
from app.services.vision_service import VisionService

router = APIRouter()
logger = logging.getLogger(__name__)
STATIC_ROOT = Path(__file__).resolve().parents[1] / "static"
GARMENT_ROOT = STATIC_ROOT / "garments"
GARMENT_LABELS = {
    "top_tank": "基础背心", "top_camisole": "基础吊带",
    "top_tshirt_short": "短袖 T 恤", "top_tshirt_long": "长袖 T 恤",
    "top_shirt": "长袖衬衫", "top_sweatshirt": "卫衣", "top_knit": "厚针织衫",
    "top_knit_vest": "针织背心", "outer_light_jacket": "薄款外套",
    "outer_wool_coat": "厚大衣", "outer_down_short": "厚羽绒服", "outer_shell": "冲锋衣",
    "bottom_shorts": "短裤", "bottom_casual_pants": "常规长裤",
    "bottom_sweatpants": "保暖长裤", "bottom_skirt_short": "短裙",
    "bottom_skirt_long": "长裙", "onepiece_dress": "连衣裙", "shoe_sneaker": "低帮鞋",
    "shoe_canvas": "高帮鞋", "shoe_leather": "正装皮鞋", "shoe_pump": "高跟鞋",
    "acc_umbrella": "雨伞", "acc_baseball_cap": "棒球帽", "acc_gloves": "手套",
    "acc_beanie": "针织帽",
}
# ponytail: 进程内锁足够覆盖当前单 worker；扩到多 worker 时改为数据库任务锁。
DETAIL_LOCKS: defaultdict[tuple[str, str], asyncio.Lock] = defaultdict(asyncio.Lock)


def _quota_date(user_id: str) -> str:
    return user_local_date(store.get_settings(user_id).get("timezone"))


def _non_ai_recommendation(
    payload: RecommendationRequest,
    weather: WeatherInput,
    audience: str,
) -> dict:
    try:
        return recommend_system_ai_outfit(
            weather=weather,
            scene=payload.scene,
            audience=audience,
            city_id=payload.city_id,
            local_date=payload.local_date,
            excluded_template_ids=payload.excluded_template_ids,
        )
    except NoRecommendationError:
        pass
    except Exception:
        logger.exception("system recommendation failed, falling back to official templates")
    return recommend_official_outfit(
        weather=weather,
        scene=payload.scene,
        audience=audience,
        city_id=payload.city_id,
        local_date=payload.local_date,
        excluded_template_ids=payload.excluded_template_ids,
    )


def _weather_input(payload: WeatherRuleRequest) -> WeatherInput:
    return WeatherInput(
        apparent_min=payload.apparent_min,
        apparent_max=payload.apparent_max,
        max_precipitation_probability=payload.max_precipitation_probability,
        total_precipitation=payload.total_precipitation,
        total_snowfall=payload.total_snowfall,
        max_wind_speed=payload.max_wind_speed,
        max_wind_gust=payload.max_wind_gust,
        uv_index_max=payload.uv_index_max,
        cold_offset=payload.cold_offset,
    )


@router.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "healthy", "service": "wearcue-backend", "version": "0.1.0"}


@router.get("/capabilities", tags=["system"])
async def capabilities() -> dict:
    return {
        "weather_provider": True,
        "deterministic_rules": True,
        "official_recommendations": True,
        "garment_assets": True,
        "production_entry": True,
        "multi_user_auth": True,
        "per_user_data_isolation": True,
        "user_settings": True,
        "personal_outfits": True,
        "garment_details": True,
        "image_upload": True,
        "vision_workflow": True,
        "notification_workflow": True,
        "comfort_feedback": True,
        "persistence": True,
        "vision_provider_configured": VisionService().configured,
        "image_provider_configured": OutfitImageService().configured,
        "web_push_provider_configured": bool(
            os.getenv("VAPID_PRIVATE_KEY") and os.getenv("VAPID_PUBLIC_KEY") and os.getenv("VAPID_SUBJECT")
        ),
        "cloud_database_configured": False,
        "object_storage_configured": False,
    }


@router.post("/rules/evaluate", tags=["recommendations"])
async def evaluate(payload: WeatherRuleRequest) -> dict:
    return evaluate_weather_rules(_weather_input(payload)).to_dict()


@router.post("/recommendations/preview", tags=["recommendations"])
async def preview_recommendation(payload: RecommendationRequest, user: CurrentUser) -> dict:
    audience = store.get_settings(user["id"])["audience"]
    weather = _weather_input(payload)
    personal = recommend_personal_outfit(
        weather=weather,
        scene=payload.scene,
        audience=audience,
        outfits=store.list_outfits(in_pool=True, user_id=user["id"]),
        excluded_ids=payload.excluded_template_ids,
    )
    if personal:
        return personal
    return _non_ai_recommendation(payload, weather, audience)


@router.get("/ai-usage-quota", tags=["system"])
async def ai_usage_quota(user: CurrentUser) -> dict:
    local_date = _quota_date(user["id"])
    return {
        usage_type: store.get_ai_quota(user["id"], local_date, usage_type)
        for usage_type in AI_USAGE_LIMITS
    }


@router.post("/recommendations/swap", tags=["recommendations"])
async def swap_recommendation(payload: RecommendationRequest, user: CurrentUser) -> dict:
    audience = store.get_settings(user["id"])["audience"]
    weather = _weather_input(payload)
    personal = recommend_personal_outfit(
        weather=weather,
        scene=payload.scene,
        audience=audience,
        outfits=store.list_outfits(in_pool=True, user_id=user["id"]),
        excluded_ids=payload.excluded_template_ids,
    )
    if personal:
        return personal
    local_date = _quota_date(user["id"])
    reservation_id = store.reserve_ai_usage(user["id"], local_date, "swap")
    if not reservation_id:
        recommendation = _non_ai_recommendation(payload, weather, audience)
        return recommendation | {
            "ai_quota": store.get_ai_quota(user["id"], local_date, "swap"),
            "ai_fallback_reason": "quota_exhausted",
        }
    try:
        recommendation = await recommend_ai_outfit(
            weather=weather,
            scene=payload.scene,
            audience=audience,
            city_id=payload.city_id,
            local_date=payload.local_date,
            weather_context={
                "city_name": payload.city_name,
                "latitude": payload.latitude,
                "longitude": payload.longitude,
                "timezone": payload.timezone,
                "current_temperature": payload.current_temperature,
                "current_apparent_temperature": payload.current_apparent_temperature,
                "temperature_min": payload.temperature_min,
                "temperature_max": payload.temperature_max,
                "weather_code": payload.weather_code,
            },
        )
    except Exception:
        store.release_ai_usage(reservation_id)
        logger.exception("AI recommendation failed, falling back to non-AI recommendations")
        recommendation = _non_ai_recommendation(payload, weather, audience)
        return recommendation | {
            "ai_quota": store.get_ai_quota(user["id"], local_date, "swap"),
            "ai_fallback_reason": "provider_failed",
        }
    return recommendation | {"ai_quota": store.get_ai_quota(user["id"], local_date, "swap")}


@router.post("/recommendations/advice", tags=["recommendations"])
async def recommendation_advice(payload: RecommendationAdviceRequest, user: CurrentUser) -> dict:
    async with DETAIL_LOCKS[(user["id"], payload.recommendation_id)]:
        local_date = _quota_date(user["id"])
        cached_advice = store.get_ai_advice(user["id"], payload.recommendation_id)
        cached_image = store.get_ai_outfit_image(user["id"], payload.recommendation_id)
        needs_advice = payload.generate_advice and not cached_advice
        needs_image = not cached_image
        if not needs_advice and not needs_image:
            return (cached_advice or {}) | {
                "image_url": f"/recommendations/{payload.recommendation_id}/image",
                "ai_quota": store.get_ai_quota(user["id"], local_date, "advice"),
                "cached": True,
            }
        reservation_id = store.reserve_ai_usage(user["id"], local_date, "advice")
        if not reservation_id:
            raise HTTPException(429, "今日 AI 穿搭建议次数已用完，可先参考下方基础搭配，明天再来生成")
        items = [item.model_dump() for item in payload.items]
        settings = store.get_settings(user["id"])
        generation_audience = settings["audience"]
        person_profile = {
            key: settings[key] for key in ("height_group", "weight_group")
        }
        try:
            advice_task = (
                OutfitAIService().generate_advice(
                    items,
                    payload.constraints,
                    payload.scene,
                    generation_audience,
                    person_profile,
                )
                if needs_advice
                else None
            )
            image_task = (
                OutfitImageService().generate(
                    payload.label,
                    generation_audience,
                    payload.scene,
                    items,
                    payload.constraints,
                    person_profile,
                )
                if needs_image
                else None
            )
            pending = [task for task in (advice_task, image_task) if task is not None]
            generated = await asyncio.gather(*pending)
            index = 0
            result = cached_advice or {}
            if needs_advice:
                result = generated[index]
                index += 1
                store.set_ai_advice(user["id"], payload.recommendation_id, result)
            if needs_image:
                store.set_ai_outfit_image(user["id"], payload.recommendation_id, generated[index])
        except Exception:
            store.release_ai_usage(reservation_id)
            raise
        return result | {
            "image_url": f"/recommendations/{payload.recommendation_id}/image",
            "ai_quota": store.get_ai_quota(user["id"], local_date, "advice"),
            "cached": False,
        }


@router.get("/recommendations/{recommendation_id}/image", tags=["recommendations"], include_in_schema=False)
async def recommendation_image(recommendation_id: str, user: CurrentUser) -> FileResponse:
    cached = store.get_ai_outfit_image(user["id"], recommendation_id)
    if not cached:
        raise HTTPException(404, "穿搭参考图不存在")
    return FileResponse(
        cached["file_path"], media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"}
    )


@router.get(
    "/garment-assets",
    response_model=List[GarmentAssetResponse],
    tags=["garment-assets"],
)
async def garment_assets(
    collection: Optional[str] = Query(default=None, pattern="^(mens|womens|accessories)$"),
) -> List[GarmentAssetResponse]:
    assets: List[GarmentAssetResponse] = []
    for path in sorted(GARMENT_ROOT.rglob("*.svg")):
        relative = path.relative_to(GARMENT_ROOT)
        asset_collection = relative.parts[0]
        if collection and asset_collection != collection:
            continue
        assets.append(
            GarmentAssetResponse(
                key=relative.stem,
                collection=asset_collection,
                category=relative.stem.split("_")[0],
                url="/assets/garments/%s" % relative.as_posix(),
                label=GARMENT_LABELS.get(relative.stem, relative.stem),
            )
        )
    return assets


@router.get("/garment-assets/{collection}/{key}", response_model=GarmentAssetResponse, tags=["garment-assets"])
async def garment_asset_detail(collection: str, key: str) -> GarmentAssetResponse:
    if collection not in {"mens", "womens", "accessories"}:
        raise HTTPException(404, "素材不存在")
    path = GARMENT_ROOT / collection / (key + ".svg")
    if not path.is_file():
        raise HTTPException(404, "素材不存在")
    return GarmentAssetResponse(
        key=key, collection=collection, category=key.split("_")[0],
        url="/assets/garments/%s/%s.svg" % (collection, key),
        label=GARMENT_LABELS.get(key, key),
    )
