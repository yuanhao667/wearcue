import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

import httpx

# functional_icon_key -> 基础图标 key（与前端 functionalFallbacks 保持一致）
FUNCTIONAL_TO_ASSET: Dict[str, str] = {
    "short_sleeve": "top_tshirt_short",
    "short_or_long_sleeve": "top_tshirt_long",
    "long_sleeve": "top_tshirt_long",
    "warm_top": "top_knit",
    "light_outerwear": "outer_light_jacket",
    "warm_outerwear": "outer_down_short",
    "protective_outerwear": "outer_shell",
    "short_bottom": "bottom_shorts",
    "long_bottom": "bottom_casual_pants",
    "warm_bottom": "bottom_sweatpants",
    "daily_shoes": "shoe_sneaker",
    "protective_shoes": "shoe_canvas",
    "acc_umbrella": "acc_umbrella",
    "acc_gloves": "acc_gloves",
    "acc_baseball_cap": "acc_baseball_cap",
}

VALID_SLOTS = {"top", "bottom", "outerwear", "onepiece", "shoes", "equipment"}
VALID_THICKNESS = {"thin", "regular", "thick"}
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class OutfitAIServiceError(RuntimeError):
    pass


def _first_str(value: Any, fallback: str = "") -> str:
    return str(value).strip() if value is not None else fallback


def _normalize_guide(raw: Any) -> Dict[str, Any]:
    raw = raw or {}
    steps = raw.get("steps") or []
    return {
        "formula": _first_str(raw.get("formula"), "今日推荐"),
        "steps": [_first_str(step) for step in steps if _first_str(step)][:5] or ["按推荐单品逐件穿着"],
        "styling_points": [_first_str(point) for point in (raw.get("styling_points") or []) if _first_str(point)][:3],
        "weather_note": _first_str(raw.get("weather_note"), "按当天体感增减外层。"),
        "substitute": _first_str(raw.get("substitute"), "同厚度、相近版型的基础款即可替换。"),
    }


def _normalize_analysis(raw: Any) -> Dict[str, Any]:
    raw = raw or {}
    return {
        "summary": _first_str(raw.get("summary"), "基础款组合，按现有层次直接复刻即可。"),
        "structure_points": [_first_str(point) for point in (raw.get("structure_points") or []) if _first_str(point)][:3],
        "completion_advice": [_first_str(advice) for advice in (raw.get("completion_advice") or []) if _first_str(advice)][:3],
    }


class OutfitAIService:
    def __init__(self) -> None:
        self.url = (os.getenv("AI_API_URL") or os.getenv("VISION_API_URL") or "").rstrip("/")
        self.key = os.getenv("AI_API_KEY") or os.getenv("VISION_API_KEY") or ""
        self.model = os.getenv("AI_MODEL") or os.getenv("VISION_MODEL") or ""
        base = Path(__file__).resolve().parents[1] / "prompts"
        self.prompt = (base / "outfit_generation.txt").read_text()
        self.items_prompt = (base / "outfit_items.txt").read_text()
        self.advice_prompt = (base / "outfit_advice.txt").read_text()

    @property
    def configured(self) -> bool:
        return bool(self.url and self.key and self.model)

    async def _call(self, prompt: str, user_content: Any, max_tokens: int) -> Dict[str, Any]:
        if not self.configured:
            raise OutfitAIServiceError("AI 推荐模型尚未配置")
        payload = {
            "model": self.model,
            "temperature": 0.7,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    self.url + "/chat/completions",
                    headers={"Authorization": "Bearer " + self.key},
                    json=payload,
                )
                response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            raw = str(content).strip().removeprefix("```json").removesuffix("```").strip()
            return json.loads(raw)
        except (httpx.HTTPError, KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise OutfitAIServiceError("AI 生成失败") from exc

    def _normalize_items(self, raw_items: Any) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for item in raw_items or []:
            functional_key = _first_str(item.get("functional_icon_key"))
            if functional_key not in FUNCTIONAL_TO_ASSET:
                continue
            slot = _first_str(item.get("slot"))
            if slot not in VALID_SLOTS:
                continue
            thickness = _first_str(item.get("thickness"), "regular")
            if thickness not in VALID_THICKNESS:
                thickness = "regular"
            color_value = _first_str(item.get("color_value"))
            if color_value and not HEX_RE.match(color_value):
                color_value = ""
            items.append(
                {
                    "slot": slot,
                    "functional_icon_key": functional_key,
                    "asset_key": FUNCTIONAL_TO_ASSET[functional_key],
                    "variant_type": _first_str(item.get("variant_type"), functional_key),
                    "color_name": _first_str(item.get("color_name"), "基础色"),
                    "color_value": color_value or None,
                    "color_type": "solid",
                    "thickness": thickness,
                }
            )
        return items

    def _normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        items = self._normalize_items(raw.get("items"))
        if not items:
            raise OutfitAIServiceError("AI 推荐未返回可映射到图标的单品")
        return {
            "label": _first_str(raw.get("label"), "AI 穿搭方案"),
            "items": items,
            "replication_guide": _normalize_guide(raw.get("replication_guide")),
            "outfit_analysis": _normalize_analysis(raw.get("outfit_analysis")),
        }

    async def generate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """完整生成（含建议），用于离线预生成系统推荐。"""
        raw = await self._call(self.prompt, context, max_tokens=1200)
        return self._normalize(raw)

    async def generate_items(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """只生成首页展示需要的单品（快）。"""
        raw = await self._call(self.items_prompt, context, max_tokens=600)
        items = self._normalize_items(raw.get("items"))
        if not items:
            raise OutfitAIServiceError("AI 未返回可映射到图标的单品")
        return {
            "label": _first_str(raw.get("label"), "AI 穿搭方案"),
            "items": items,
        }

    async def generate_advice(
        self, items: List[Dict[str, Any]], weather_summary: str, scene: str, audience: str
    ) -> Dict[str, Any]:
        """按需生成建议文案（点进详情时调用）。"""
        raw = await self._call(
            self.advice_prompt,
            {"scene": scene, "audience": audience, "weather": weather_summary, "items": items},
            max_tokens=800,
        )
        return {
            "replication_guide": _normalize_guide(raw.get("replication_guide")),
            "outfit_analysis": _normalize_analysis(raw.get("outfit_analysis")),
        }
