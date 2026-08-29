import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.auth import CurrentUser
from app.domain.weather_rules import WeatherInput, evaluate_weather_rules
from app.schemas import GarmentAssetResponse, RecommendationRequest, WeatherRuleRequest
from app.services.recommendation_service import recommend_official_outfit, recommend_personal_outfit
from app.services.store import store
from app.services.vision_service import VisionService

router = APIRouter()
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
    return {"status": "healthy", "service": "outfit-signal-backend", "version": "0.1.0"}


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
    personal = recommend_personal_outfit(
        weather=_weather_input(payload),
        scene=payload.scene,
        audience=audience,
        outfits=store.list_outfits(in_pool=True, user_id=user["id"]),
        excluded_ids=payload.excluded_template_ids,
    )
    if personal:
        return personal
    return recommend_official_outfit(
        weather=_weather_input(payload),
        scene=payload.scene,
        audience=audience,
        city_id=payload.city_id,
        local_date=payload.local_date,
        excluded_template_ids=payload.excluded_template_ids,
    )


@router.post("/recommendations/swap", tags=["recommendations"])
async def swap_recommendation(payload: RecommendationRequest, user: CurrentUser) -> dict:
    return await preview_recommendation(payload, user)


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
