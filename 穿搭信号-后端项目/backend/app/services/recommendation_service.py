import hashlib
from dataclasses import asdict
from typing import Dict, List, Optional, Sequence

from app.domain.official_templates import OfficialTemplate, TemplateItem, official_templates
from app.domain.weather_rules import WeatherConstraints, WeatherInput, evaluate_weather_rules


class NoRecommendationError(ValueError):
    pass


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

    for equipment in constraints.equipment:
        labels = {
            "umbrella": ("雨伞", "acc_umbrella"),
            "gloves": ("保暖手套", "acc_gloves"),
            "sun_protection": ("棒球帽", "acc_baseball_cap"),
        }
        label, icon = labels[equipment]
        result.append(
            {
                "slot": "equipment",
                "functional_icon_key": icon,
                "variant_type": label,
                "color_name": "基础色",
                "thickness": "regular",
            }
        )
    return result


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
        "items": outfit["components"],
        "outfit_analysis": outfit.get("outfit_analysis") or None,
        "replication_guide": outfit.get("replication_guide") or _official_guide(outfit["components"], constraints),
    }
