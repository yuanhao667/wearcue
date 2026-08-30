import base64
import json
import os
from pathlib import Path

import httpx

from app.schemas import VisionResult


VALID_ASSET_KEYS = {
    "top_tshirt_short", "top_tshirt_long", "top_tank", "top_camisole", "top_shirt",
    "top_sweatshirt", "top_knit", "top_knit_vest", "outer_light_jacket",
    "outer_wool_coat", "outer_down_short", "outer_shell", "bottom_shorts",
    "bottom_casual_pants", "bottom_sweatpants", "bottom_skirt_short",
    "bottom_skirt_long", "onepiece_dress", "shoe_sneaker", "shoe_canvas",
    "shoe_leather", "shoe_pump", "acc_baseball_cap", "acc_beanie", "acc_gloves",
    "acc_umbrella",
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
    "高跟鞋": "shoe_pump", "棒球帽": "acc_baseball_cap", "针织帽": "acc_beanie",
    "手套": "acc_gloves", "雨伞": "acc_umbrella",
}

FUNCTIONAL_ASSET_KEYS = {
    "short_sleeve": "top_tshirt_short", "short_or_long_sleeve": "top_tshirt_long",
    "long_sleeve": "top_tshirt_long", "warm_top": "top_knit",
    "light_outerwear": "outer_light_jacket", "warm_outerwear": "outer_down_short",
    "protective_outerwear": "outer_shell", "short_bottom": "bottom_shorts",
    "long_bottom": "bottom_casual_pants", "warm_bottom": "bottom_sweatpants",
    "daily_shoes": "shoe_sneaker", "protective_shoes": "shoe_canvas",
    "umbrella": "acc_umbrella", "gloves": "acc_gloves",
    "sun_protection": "acc_baseball_cap",
}

SLOT_ASSET_KEYS = {
    "top": "top_tshirt_long", "bottom": "bottom_casual_pants",
    "outerwear": "outer_light_jacket", "onepiece": "onepiece_dress",
    "shoes": "shoe_sneaker", "equipment": "acc_baseball_cap",
}


def canonical_asset_key(component: dict) -> str:
    """Convert provider vocabulary into the stable icon vocabulary used by the UI."""
    raw_key = str(component.get("asset_key") or "").strip().lower()
    for prefix in ("mens_", "womens_", "accessories_"):
        if raw_key.startswith(prefix):
            raw_key = raw_key[len(prefix):]
            break
    key = ASSET_KEY_ALIASES.get(raw_key, raw_key)
    if key in VALID_ASSET_KEYS:
        return key
    variant = "".join(str(component.get("variant_type") or "").lower().split())
    return VARIANT_ASSET_KEYS.get(variant) or FUNCTIONAL_ASSET_KEYS.get(
        str(component.get("functional_icon_key") or "").strip().lower()
    ) or SLOT_ASSET_KEYS.get(str(component.get("slot") or "").strip().lower(), "top_tshirt_long")


def normalize_vision_result(result: dict) -> dict:
    for component in result.get("components", []):
        component["asset_key"] = canonical_asset_key(component)
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
                    "max_tokens": 1000,
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
                    result = VisionResult.model_validate(json.loads(raw))
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
