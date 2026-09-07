import base64
import json
import os
import re
from pathlib import Path

import httpx

from app.domain.component_rules import (
    UNSUPPORTED_COMPONENT_TERMS,
    normalize_component_list,
    normalize_component_thickness,
)
from app.schemas import VisionResult


VALID_ASSET_KEYS = {
    "top_tshirt_short", "top_tshirt_long", "top_tank", "top_camisole", "top_shirt",
    "top_sweatshirt", "top_knit", "top_knit_vest", "outer_light_jacket",
    "outer_wool_coat", "outer_down_short", "outer_shell", "bottom_shorts",
    "bottom_casual_pants", "bottom_sweatpants", "bottom_skirt_short",
    "bottom_skirt_long", "onepiece_dress", "shoe_sneaker", "shoe_canvas",
    "shoe_leather", "shoe_pump", "acc_baseball_cap", "acc_beanie", "acc_gloves",
    "acc_umbrella", "acc_sunscreen",
    "acc_bucket_hat", "acc_tote_bag", "acc_crossbody_bag", "acc_backpack", "acc_glasses", "acc_scarf",
    "shoe_sneaker_high_top",
}

ASSET_KEY_ALIASES = {
    "top_shirt_long": "top_shirt",
    "top_long_sleeve_shirt": "top_shirt",
    "outerwear_jacket": "outer_light_jacket",
    "outer_jacket": "outer_light_jacket",
    "bottom_pants_long": "bottom_casual_pants",
    "bottom_long_pants": "bottom_casual_pants",
    "shoes_sneakers": "shoe_sneaker",
    "shoe_sneakers": "shoe_sneaker",
    "shoes_casual": "shoe_sneaker",
    "shoe_casual": "shoe_sneaker",
    "shoe_pump_summer": "shoe_pump",
    "shoe_snow_boot": "shoe_canvas",
    "acc_sun_hat": "acc_baseball_cap",
    "shoe_high_top_sneaker": "shoe_sneaker_high_top",
    "shoe_boot_short": "shoe_sneaker_high_top",
    "shoe_sandal": "shoe_sneaker",
    "acc_shoulder_bag": "acc_tote_bag",
    "backpack": "acc_backpack",
    "acc_backpack_bag": "acc_backpack",
    "acc_sunglasses": "acc_glasses",
    "acc_eyeglasses": "acc_glasses",
}

VARIANT_ASSET_KEYS = {
    "短袖t恤": "top_tshirt_short", "短袖上衣": "top_tshirt_short", "t恤": "top_tshirt_short",
    "长袖t恤": "top_tshirt_long", "长袖衬衫": "top_shirt", "衬衫": "top_shirt",
    "卫衣": "top_sweatshirt", "针织衫": "top_knit", "毛衣": "top_knit",
    "基础背心": "top_tank", "基础吊带": "top_camisole", "针织背心": "top_knit_vest",
    "薄款外套": "outer_light_jacket", "夹克": "outer_light_jacket",
    "厚大衣": "outer_wool_coat", "大衣": "outer_wool_coat",
    "厚羽绒服": "outer_down_short", "羽绒服": "outer_down_short", "冲锋衣": "outer_shell",
    "短裤": "bottom_shorts", "长裤": "bottom_casual_pants", "常规长裤": "bottom_casual_pants",
    "直筒裤": "bottom_casual_pants", "休闲裤": "bottom_casual_pants",
    "运动裤": "bottom_sweatpants", "卫裤": "bottom_sweatpants",
    "短裙": "bottom_skirt_short", "长裙": "bottom_skirt_long", "连衣裙": "onepiece_dress",
    "运动鞋": "shoe_sneaker", "休闲鞋": "shoe_sneaker", "低帮鞋": "shoe_sneaker",
    "高帮鞋": "shoe_canvas", "皮鞋": "shoe_leather", "正装皮鞋": "shoe_leather",
    "高帮运动鞋": "shoe_sneaker_high_top", "凉鞋": "shoe_sneaker", "短靴": "shoe_sneaker_high_top",
    "高跟鞋": "shoe_pump", "棒球帽": "acc_baseball_cap", "渔夫帽": "acc_bucket_hat", "针织帽": "acc_beanie",
    "托特包": "acc_tote_bag", "单肩包": "acc_tote_bag", "斜挎包": "acc_crossbody_bag",
    "双肩包": "acc_backpack", "双肩背包": "acc_backpack", "登山双肩包": "acc_backpack", "登山包": "acc_backpack", "背包": "acc_backpack",
    "眼镜": "acc_glasses", "墨镜": "acc_glasses", "太阳镜": "acc_glasses", "太阳眼镜": "acc_glasses", "黑框眼镜": "acc_glasses", "围巾": "acc_scarf",
    "手套": "acc_gloves", "雨伞": "acc_umbrella", "防晒霜": "acc_sunscreen",
}

FUNCTIONAL_ASSET_KEYS = {
    "short_sleeve": "top_tshirt_short", "short_or_long_sleeve": "top_tshirt_long",
    "long_sleeve": "top_tshirt_long", "warm_top": "top_knit",
    "light_outerwear": "outer_light_jacket", "warm_outerwear": "outer_down_short",
    "protective_outerwear": "outer_shell", "short_bottom": "bottom_shorts",
    "long_bottom": "bottom_casual_pants", "warm_bottom": "bottom_sweatpants",
    "daily_shoes": "shoe_sneaker", "protective_shoes": "shoe_canvas",
    "umbrella": "acc_umbrella", "gloves": "acc_gloves",
    "sun_protection": "acc_baseball_cap", "sunscreen": "acc_sunscreen",
    "backpack": "acc_backpack", "acc_backpack": "acc_backpack",
    "glasses": "acc_glasses", "sunglasses": "acc_glasses", "acc_glasses": "acc_glasses",
}

SLOT_ASSET_KEYS = {
    "top": "top_tshirt_long", "bottom": "bottom_casual_pants",
    "outerwear": "outer_light_jacket", "onepiece": "onepiece_dress",
    "shoes": "shoe_sneaker", "equipment": "acc_baseball_cap",
}

AUDIENCE_STYLE_REPLACEMENTS = {
    "mens": {"温柔": "协调", "柔美": "柔和", "甜美": "清新", "娇俏": "灵动", "妩媚": "有魅力", "少女": "青春", "淑女": "得体"},
    "womens": {"硬汉": "利落", "硬朗": "利落", "粗犷": "有层次", "阳刚": "有力量", "猛男": "活力", "绅士": "精致"},
}

SLOT_ALIASES = {
    "acc": "equipment", "accessory": "equipment", "accessories": "equipment", "hat": "equipment",
    "bag": "equipment", "outer": "outerwear", "jacket": "outerwear",
    "shoe": "shoes", "footwear": "shoes", "pants": "bottom",
    "skirt": "bottom", "dress": "onepiece",
}
THICKNESS_ALIASES = {
    "light": "thin", "lightweight": "thin", "medium": "regular",
    "normal": "regular", "mid": "regular", "heavy": "thick",
    "warm": "thick",
}


def coerce_vision_result(result: dict) -> dict:
    """Repair common provider vocabulary drift before strict schema validation."""
    result = dict(result)
    audience = str(result.get("garment_audience") or "unisex").lower()
    result["garment_audience"] = {
        "male": "mens", "man": "mens", "men": "mens",
        "female": "womens", "woman": "womens", "women": "womens",
    }.get(audience, audience if audience in {"mens", "womens", "unisex"} else "unisex")
    coverage = str(result.get("image_coverage") or "unknown").lower()
    result["image_coverage"] = {
        "full": "full_body", "fullbody": "full_body", "half_body": "partial",
    }.get(coverage, coverage if coverage in {"full_body", "partial", "unknown"} else "unknown")
    result["suggested_scenes"] = [
        value for value in result.get("suggested_scenes", [])
        if value in {"commute", "date", "travel"}
    ][:3]
    season = result.get("suggested_season")
    result["suggested_season"] = {
        "spring": "spring-autumn", "autumn": "spring-autumn", "fall": "spring-autumn",
    }.get(season, season if season in {"spring-autumn", "summer", "winter"} else "spring-autumn")
    result["suggested_style_tags"] = [
        value for value in result.get("suggested_style_tags", [])
        if value in {"minimal", "sport", "outdoor"}
    ][:2]

    components = []
    for raw_component in result.get("components", [])[:8]:
        component = dict(raw_component)
        slot = str(component.get("slot") or "").lower()
        component["slot"] = SLOT_ALIASES.get(slot, slot if slot in SLOT_ASSET_KEYS else "equipment")
        thickness = str(component.get("thickness") or "regular").lower()
        component["thickness"] = THICKNESS_ALIASES.get(
            thickness, thickness if thickness in {"thin", "regular", "thick"} else "regular"
        )
        color_type = str(component.get("color_type") or "solid").lower()
        component["color_type"] = "solid" if color_type == "solid" else "pattern"
        color_value = str(component.get("color_value") or "")
        match = re.search(r"#[0-9A-Fa-f]{6}", color_value)
        component["color_value"] = match.group(0) if match else None
        component["confidence"] = min(1.0, max(0.0, float(component.get("confidence", 1))))
        for field, limit in (
            ("functional_icon_key", 60), ("variant_type", 60), ("color_name", 30),
            ("pattern_description", 80), ("fit", 30), ("shoulder", 40),
            ("length", 40), ("waistline", 30), ("bottom_shape", 30),
            ("material", 80), ("wearing_method", 80),
        ):
            if component.get(field) is not None:
                component[field] = str(component[field])[:limit]
        component["structure_details"] = [
            str(value)[:80] for value in component.get("structure_details", [])
        ][:6]
        components.append(normalize_component_thickness(component))
    result["components"] = components

    guide = dict(result.get("replication_guide") or {})
    formula = str(guide.get("formula") or "＋".join(
        str(component.get("variant_type") or "单品") for component in components
    ))[:60]
    steps = [str(value)[:120] for value in guide.get("steps", [])][:6]
    if len(steps) < 2:
        steps = [f"穿好{component.get('variant_type') or '单品'}" for component in components[:6]]
    if len(steps) < 2:
        steps.append("按照片中的层次完成搭配")
    result["replication_guide"] = {
        "formula": formula or "按照片复刻完整穿搭",
        "steps": steps,
        "styling_points": [str(value)[:120] for value in guide.get("styling_points", [])][:3],
        "weather_note": str(guide.get("weather_note") or "按当天体感增减外层。")[:80],
        "substitute": str(guide.get("substitute") or "选择同版型和薄厚的单品替换。")[:80],
    }
    analysis = dict(result.get("outfit_analysis") or {})
    result["outfit_analysis"] = {
        "summary": str(analysis.get("summary") or "按参考图的版型和层次直接复刻。")[:60],
        "structure_points": [str(value)[:120] for value in analysis.get("structure_points", [])][:3],
        "completion_advice": [str(value)[:120] for value in analysis.get("completion_advice", [])][:3],
    }
    result["signature_features"] = [str(value)[:120] for value in result.get("signature_features", [])][:8]
    result["locked_features"] = [str(value)[:120] for value in result.get("locked_features", [])][:8]
    return result


def canonical_asset_key(component: dict) -> str | None:
    """Convert provider vocabulary into the stable icon vocabulary used by the UI."""
    variant = "".join(str(component.get("variant_type") or "").lower().split())
    if any(term in variant for term in UNSUPPORTED_COMPONENT_TERMS):
        return None
    raw_key = str(component.get("asset_key") or "").strip().lower()
    for prefix in ("mens_", "womens_", "accessories_"):
        if raw_key.startswith(prefix):
            raw_key = raw_key[len(prefix):]
            break
    key = ASSET_KEY_ALIASES.get(raw_key, raw_key)
    if key in VALID_ASSET_KEYS:
        return key
    # Providers often return a descriptive variant (for example
    # “黑色大框墨镜”) instead of one of the exact vocabulary entries above.
    # Keep visible eyewear on the supplied glasses icon instead of falling
    # through to the generic equipment/hat fallback.
    if any(token in variant for token in ("眼镜", "墨镜", "太阳镜", "太阳眼镜")):
        return "acc_glasses"
    matched = VARIANT_ASSET_KEYS.get(variant) or FUNCTIONAL_ASSET_KEYS.get(
        str(component.get("functional_icon_key") or "").strip().lower()
    )
    if matched:
        return matched
    return None


def _normalize_audience_style_text(value, audience: str):
    if isinstance(value, dict):
        return {key: _normalize_audience_style_text(item, audience) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_audience_style_text(item, audience) for item in value]
    if isinstance(value, str):
        for source, target in AUDIENCE_STYLE_REPLACEMENTS.get(audience, {}).items():
            value = value.replace(source, target)
    return value


def normalize_vision_result(result: dict) -> dict:
    result["components"] = [
        component for component in result.get("components", [])
        if component.get("asset_key") not in {"acc_umbrella", "acc_sunscreen"}
        and component.get("functional_icon_key") not in {
            "acc_umbrella", "umbrella", "acc_sunscreen", "sunscreen", "sun_protection"
        }
    ]
    mapped_components = []
    for component in result.get("components", []):
        component["asset_key"] = canonical_asset_key(component)
        if component["asset_key"] is None:
            continue
        component.update(normalize_component_thickness(component))
        asset_key = component["asset_key"]
        component["slot"] = (
            "equipment" if asset_key.startswith("acc_")
            else "shoes" if asset_key.startswith("shoe_")
            else "bottom" if asset_key.startswith("bottom_")
            else "outerwear" if asset_key.startswith("outer_")
            else "onepiece" if asset_key.startswith("onepiece_")
            else "top"
        )
        mapped_components.append(component)
    result["components"] = normalize_component_list(mapped_components)
    asset_keys = {component.get("asset_key") for component in result.get("components", [])}
    if asset_keys & {"top_tshirt_short", "top_tank", "top_camisole"} and asset_keys & {
        "bottom_shorts", "bottom_skirt_short"
    } and not asset_keys & {
        "outer_light_jacket", "outer_wool_coat", "outer_down_short", "outer_shell",
        "top_knit", "top_sweatshirt", "bottom_sweatpants",
    }:
        result["suggested_season"] = "summer"
    formula = str(result.get("replication_guide", {}).get("formula") or "")
    if "短裙" in formula and "短裤" not in formula:
        for component in result.get("components", []):
            if component.get("slot") == "bottom" and component.get("asset_key") == "bottom_shorts":
                component.update({
                    "variant_type": "短裙",
                    "functional_icon_key": "short_bottom",
                    "asset_key": "bottom_skirt_short",
                })
    visible_shoes = result.get("image_coverage") == "full_body" and any(
        component.get("slot") == "shoes" and component.get("suggested")
        for component in result.get("components", [])
    )
    if visible_shoes:
        for component in result.get("components", []):
            if component.get("slot") == "shoes":
                component["suggested"] = False
        analysis = result.get("outfit_analysis", {})
        analysis["completion_advice"] = [
            advice for advice in analysis.get("completion_advice", [])
            if not any(word in advice for word in ("鞋", "靴"))
        ]
    audience = str(result.get("garment_audience") or "")
    for key in ("outfit_analysis", "replication_guide"):
        result[key] = _normalize_audience_style_text(result.get(key, {}), audience)
    return result


class VisionServiceError(RuntimeError):
    pass


class VisionService:
    def __init__(self) -> None:
        self.url = os.getenv("VISION_API_URL", "").rstrip("/")
        self.key = os.getenv("VISION_API_KEY", "")
        self.model = os.getenv("VISION_MODEL", "")
        self.fallback_model = os.getenv("VISION_FALLBACK_MODEL", "")
        self.prompt = (Path(__file__).resolve().parents[1] / "prompts" / "vision_outfit.txt").read_text()

    @property
    def configured(self) -> bool:
        return bool(self.url and self.key and self.model)

    async def analyze(self, image_path: Path) -> dict:
        if not self.configured:
            raise VisionServiceError("生产视觉模型尚未配置")
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        models = list(dict.fromkeys(filter(None, [self.model, self.fallback_model])))
        async with httpx.AsyncClient(timeout=45) as client:
            for index, selected_model in enumerate(models):
                payload = {
                    "model": selected_model,
                    "enable_thinking": False,
                    "temperature": 0,
                    "max_tokens": 2200,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": self.prompt},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "识别并分析这张穿搭照片，只返回系统要求的 JSON。",
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": "data:image/jpeg;base64," + encoded},
                                },
                            ],
                        },
                    ],
                }
                try:
                    response = await client.post(
                        self.url + "/chat/completions",
                        headers={"Authorization": "Bearer " + self.key},
                        json=payload,
                    )
                    response.raise_for_status()
                    content = response.json()["choices"][0]["message"]["content"]
                    if isinstance(content, list):
                        content = "".join(part.get("text", "") for part in content)
                    raw = str(content).strip().removeprefix("```json").removesuffix("```").strip()
                    result = VisionResult.model_validate(coerce_vision_result(json.loads(raw)))
                    return normalize_vision_result(result.model_dump())
                except httpx.HTTPStatusError as caught:
                    error = caught
                    retryable = caught.response.status_code == 429 or caught.response.status_code >= 500
                except (httpx.RequestError, KeyError, TypeError, ValueError) as caught:
                    error = caught
                    retryable = True
                if not retryable or index == len(models) - 1:
                    if isinstance(error, httpx.TimeoutException):
                        raise VisionServiceError("视觉模型响应超时，请重新识别") from error
                    raise VisionServiceError("视觉模型返回失败，请重试或手动确认") from error
        raise VisionServiceError("视觉模型返回失败，请重试或手动确认")
