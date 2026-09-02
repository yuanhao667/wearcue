import hashlib
import json
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from uuid import uuid4

from app.domain.official_templates import OfficialTemplate, TemplateItem, official_templates
from app.domain.weather_rules import WeatherConstraints, WeatherInput, evaluate_weather_rules
from app.services.outfit_ai_service import FUNCTIONAL_TO_ASSET, OutfitAIService


class NoRecommendationError(ValueError):
    pass


def _ensure_weather_equipment(
    items: Sequence[Dict[str, object]], constraints: WeatherConstraints
) -> List[Dict[str, object]]:
    result = [dict(item) for item in items]
    keys = {
        str(value)
        for item in result
        for value in (item.get("functional_icon_key"), item.get("asset_key"))
        if value
    }
    labels = {
        "umbrella": ("雨伞", "acc_umbrella"),
        "gloves": ("保暖手套", "acc_gloves"),
        "sunscreen": ("防晒霜", "acc_sunscreen"),
        "sun_protection": ("棒球帽", "acc_baseball_cap"),
    }
    for equipment in constraints.equipment:
        label, icon = labels[equipment]
        if icon in keys:
            continue
        result.append({
            "slot": "equipment",
            "functional_icon_key": icon,
            "asset_key": icon,
            "variant_type": label,
            "color_name": "基础色",
            "color_value": None,
            "thickness": "regular",
        })
        keys.add(icon)
    return result


def _official_guide(items: Sequence[Dict[str, object]], constraints: WeatherConstraints) -> Dict[str, object]:
    names = [str(item["variant_type"]) for item in items]
    weather_note = "早晚温差明显，外层要方便穿脱。" if constraints.apparent_delta >= 8 else "按当前体感穿，外层无需反复增减。"
    if constraints.needs_waterproof:
        weather_note = "有降水，鞋面注意防水并随身带伞。"
    return {
        "formula": " + ".join(names[:4]),
        "steps": ["穿好%s" % name for name in names[:5]],
        "styling_points": ["上装保持自然垂落", "裤脚避免明显堆叠"],
        "weather_note": weather_note,
        "substitute": "同厚度、相近版型的基础款即可替换。",
    }


def _stable_index(seed: str, size: int) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % size


def _protect_items(
    items: Sequence[TemplateItem], constraints: WeatherConstraints
) -> List[Dict[str, object]]:
    result = [asdict(item) for item in items]

    if constraints.outerwear and not any(item["slot"] == "outerwear" for item in result):
        result.append(
            {
                "slot": "outerwear",
                "functional_icon_key": constraints.outerwear.functional_icon_key,
                "variant_type": "可脱穿薄外层",
                "color_name": "基础色",
                "thickness": constraints.outerwear.thickness or "thin",
                "removable": constraints.outerwear.removable,
            }
        )

    if constraints.outerwear and constraints.outerwear.functional_icon_key == "protective_outerwear":
        protected = {
            "slot": "outerwear",
            "functional_icon_key": "protective_outerwear",
            "variant_type": "防水防风外套" if constraints.needs_waterproof else "防风外套",
            "color_name": "深色",
            "thickness": constraints.outerwear.thickness or "regular",
            "waterproof": constraints.outerwear.waterproof,
            "windproof": constraints.outerwear.windproof,
        }
        result = [item for item in result if item["slot"] != "outerwear"]
        result.append(protected)

    if constraints.shoes.functional_icon_key == "protective_shoes":
        result = [item for item in result if item["slot"] != "shoes"]
        result.append(
            {
                "slot": "shoes",
                "functional_icon_key": "protective_shoes",
                "variant_type": "防滑防水靴" if constraints.needs_snow_protection else "防水鞋",
                "color_name": "深色",
                "thickness": "regular",
                "waterproof": True,
                "slip_resistant": constraints.needs_snow_protection,
            }
        )

    return _ensure_weather_equipment(result, constraints)


def recommend_official_outfit(
    weather: WeatherInput,
    scene: str,
    audience: str,
    city_id: str = "unknown",
    local_date: str = "today",
    excluded_template_ids: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    if scene not in ("commute", "date", "travel"):
        raise ValueError("scene must be commute, date or travel")
    if audience not in ("mens", "womens"):
        raise ValueError("audience must be mens or womens")

    constraints = evaluate_weather_rules(weather)
    excluded = set(excluded_template_ids or ())
    candidates = [
        template
        for template in official_templates()
        if template.thermal_band == constraints.thermal_band
        and scene in template.scenes
        and audience in template.audiences
        and template.id not in excluded
    ]
    if not candidates:
        raise NoRecommendationError("暂无更多满足天气硬条件的官方穿搭")

    seed = "%s:%s:%s:%s:%s" % (
        city_id,
        local_date,
        scene,
        audience,
        ",".join(sorted(excluded)),
    )
    template: OfficialTemplate = candidates[_stable_index(seed, len(candidates))]
    items = _protect_items(template.items, constraints)
    return {
        "source": "official",
        "template_id": template.id,
        "label": template.label,
        "scene": scene,
        "audience": audience,
        "constraints": constraints.to_dict(),
        "items": items,
        "replication_guide": _official_guide(items, constraints),
    }


def recommend_personal_outfit(
    weather: WeatherInput,
    scene: str,
    audience: str,
    outfits: Sequence[Dict[str, object]],
    excluded_ids: Optional[Sequence[str]] = None,
) -> Optional[Dict[str, object]]:
    constraints = evaluate_weather_rules(weather)
    excluded = set(excluded_ids or ())

    def suitable(outfit: Dict[str, object]) -> bool:
        components = outfit.get("components", [])
        keys = {item.get("functional_icon_key") for item in components}
        protected = not constraints.needs_waterproof or bool(
            keys & {"protective_outerwear", "acc_umbrella", "umbrella"}
        )
        protected = protected and (
            not constraints.needs_snow_protection or "protective_shoes" in keys
        )
        protected = protected and (
            not constraints.needs_sun_protection or bool(keys & {"acc_baseball_cap", "sun_protection"})
        )
        return bool(
            outfit.get("in_pool")
            and outfit.get("audience") == audience
            and scene in outfit.get("scene_ids", [])
            and float(outfit.get("suitable_min", 100)) <= constraints.calibrated_apparent_min
            and float(outfit.get("suitable_max", -100)) >= weather.apparent_max
            and outfit.get("id") not in excluded
            and protected
        )

    candidates = [outfit for outfit in outfits if suitable(outfit)]
    if not candidates:
        return None
    outfit = candidates[0]
    return {
        "source": "personal",
        "template_id": outfit["id"],
        "label": outfit["label"],
        "scene": scene,
        "audience": audience,
        "constraints": constraints.to_dict(),
        "items": _ensure_weather_equipment(outfit["components"], constraints),
        "outfit_analysis": outfit.get("outfit_analysis") or None,
        "replication_guide": outfit.get("replication_guide") or _official_guide(outfit["components"], constraints),
    }


async def recommend_ai_outfit(
    weather: WeatherInput,
    scene: str,
    audience: str,
    city_id: str = "unknown",
    local_date: str = "today",
    weather_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, object]:
    """生成一套 AI 推荐穿搭（个人推荐池无命中时的首选兑底）。"""
    constraints = evaluate_weather_rules(weather)
    context = {
        "scene": scene,
        "audience": audience,
        "city_id": city_id,
        "local_date": local_date,
        "apparent_min": weather.apparent_min,
        "apparent_max": weather.apparent_max,
        "max_precipitation_probability": weather.max_precipitation_probability,
        "total_precipitation": weather.total_precipitation,
        "total_snowfall": weather.total_snowfall,
        "max_wind_speed": weather.max_wind_speed,
        "max_wind_gust": weather.max_wind_gust,
        "uv_index_max": weather.uv_index_max,
        "cold_offset": weather.cold_offset,
        "thermal_band": constraints.thermal_band.value,
        "calibrated_apparent_min": constraints.calibrated_apparent_min,
        "apparent_delta": constraints.apparent_delta,
        "needs_waterproof": constraints.needs_waterproof,
        "needs_heavy_rain_protection": constraints.needs_heavy_rain_protection,
        "needs_snow_protection": constraints.needs_snow_protection,
        "needs_windproof": constraints.needs_windproof,
        "needs_sun_protection": constraints.needs_sun_protection,
        "needs_strong_sun_protection": constraints.needs_strong_sun_protection,
        "avoid_umbrella": constraints.avoid_umbrella,
        "equipment": constraints.equipment,
        "warnings": constraints.warnings,
        "required_top": constraints.top.functional_icon_key,
        "required_bottom": constraints.bottom.functional_icon_key,
        "required_outerwear": (
            constraints.outerwear.functional_icon_key if constraints.outerwear else None
        ),
        "required_shoes": constraints.shoes.functional_icon_key,
    }
    context.update({
        key: value for key, value in (weather_context or {}).items() if value is not None
    })
    result = await OutfitAIService().generate_items(context)
    items = _protect_dict_items(result["items"], constraints)
    return {
        "source": "ai",
        "template_id": "ai-%s" % uuid4().hex[:8],
        "label": result["label"],
        "scene": scene,
        "audience": audience,
        "constraints": constraints.to_dict() | {
            key: context[key]
            for key in (
                "city_id", "city_name", "latitude", "longitude", "timezone", "local_date",
                "current_temperature", "current_apparent_temperature", "temperature_min",
                "temperature_max", "apparent_min", "apparent_max",
                "max_precipitation_probability", "total_precipitation", "total_snowfall",
                "max_wind_speed", "max_wind_gust", "uv_index_max", "weather_code", "cold_offset",
            )
            if key in context
        },
        "items": items,
        "outfit_analysis": None,
        "replication_guide": None,
    }


@lru_cache(maxsize=1)
def system_ai_templates() -> List[Dict[str, Any]]:
    """预生成的系统推荐（AI 生成、离线存储，首页加载不调 AI）。"""
    path = Path(__file__).resolve().parents[1] / "defaults" / "system_ai_outfits.json"
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("outfits", [])
    except (json.JSONDecodeError, OSError):
        return []


def _protect_dict_items(
    items: List[Dict[str, Any]], constraints: WeatherConstraints
) -> List[Dict[str, Any]]:
    """按当前天气确定性校正 AI 或预生成推荐中的必要单品。"""
    result: List[Dict[str, Any]] = [
        dict(item)
        for item in items
        if not (
            constraints.avoid_umbrella
            and item.get("functional_icon_key") == "acc_umbrella"
        )
    ]
    slots = {item.get("slot") for item in result}
    keys = {item.get("functional_icon_key") for item in result}

    required_basics = (
        ("top", constraints.top, "天气适配上装"),
        ("bottom", constraints.bottom, "天气适配下装"),
    )
    for slot, required, label in required_basics:
        if required.functional_icon_key not in keys:
            result = [item for item in result if item.get("slot") != slot]
            result.append({
                "slot": slot,
                "functional_icon_key": required.functional_icon_key,
                "asset_key": FUNCTIONAL_TO_ASSET.get(required.functional_icon_key),
                "variant_type": label,
                "color_name": "基础色",
                "color_value": None,
                "thickness": required.thickness or "regular",
            })
    slots = {item.get("slot") for item in result}
    keys = {item.get("functional_icon_key") for item in result}

    if constraints.outerwear and "outerwear" not in slots:
        result.append({
            "slot": "outerwear",
            "functional_icon_key": constraints.outerwear.functional_icon_key,
            "asset_key": FUNCTIONAL_TO_ASSET.get(constraints.outerwear.functional_icon_key),
            "variant_type": "可脱穿薄外层",
            "color_name": "基础色",
            "color_value": None,
            "thickness": constraints.outerwear.thickness or "thin",
        })
    if constraints.outerwear and constraints.outerwear.functional_icon_key == "protective_outerwear":
        protective = {
            "slot": "outerwear",
            "functional_icon_key": "protective_outerwear",
            "asset_key": "outer_shell",
            "variant_type": "防水防风外套" if constraints.needs_waterproof else "防风外套",
            "color_name": "深色",
            "color_value": None,
            "thickness": constraints.outerwear.thickness or "regular",
        }
        result = [item for item in result if item.get("slot") != "outerwear"]
        result.append(protective)
    if constraints.shoes.functional_icon_key == "protective_shoes" and "protective_shoes" not in keys:
        result = [item for item in result if item.get("slot") != "shoes"]
        result.append({
            "slot": "shoes",
            "functional_icon_key": "protective_shoes",
            "asset_key": "shoe_canvas",
            "variant_type": "防滑防水靴" if constraints.needs_snow_protection else "防水鞋",
            "color_name": "深色",
            "color_value": None,
            "thickness": "regular",
        })
    return _ensure_weather_equipment(result, constraints)


def recommend_system_ai_outfit(
    weather: WeatherInput,
    scene: str,
    audience: str,
    city_id: str = "unknown",
    local_date: str = "today",
    excluded_template_ids: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    """从预生成批中选择一套系统推荐（快，不调 AI）。"""
    constraints = evaluate_weather_rules(weather)
    excluded = set(excluded_template_ids or ())
    candidates = [
        template
        for template in system_ai_templates()
        if template.get("thermal_band") == constraints.thermal_band.value
        and template.get("audience") == audience
        and template.get("scene", "commute") == scene
        and template.get("id") not in excluded
    ]
    if not candidates:
        raise NoRecommendationError("暂无系统推荐")
    template = candidates[0]
    items = _protect_dict_items(template.get("items") or [], constraints)
    return {
        "source": "system_ai",
        "template_id": template["id"],
        "label": template.get("label") or "系统推荐",
        "scene": scene,
        "audience": audience,
        "constraints": constraints.to_dict(),
        "items": items,
        "outfit_analysis": template.get("outfit_analysis"),
        "replication_guide": template.get("replication_guide") or _official_guide(items, constraints),
    }
