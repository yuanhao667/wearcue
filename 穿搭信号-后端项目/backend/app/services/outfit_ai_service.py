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
SCENE_CONTEXT: Dict[str, Dict[str, str]] = {
    "commute": {
        "scene_name": "通勤",
        "scene_requirements": "优先轻松自然、日常得体、轮廓简洁、易打理，方便工作或上学及日常走动；采用休闲通勤和轻松层次，避免默认生成成套西装、衬衫领带、商务皮鞋等传统商务正装，除非输入衣物明确包含这些款式；方案名突出松弛、简约、轻便或日常得体，不能只写天气感。",
    },
    "date": {
        "scene_name": "约会",
        "scene_requirements": "优先精致协调、有视觉重点和约会氛围，颜色或层次应温柔、有质感，避免纯通勤或纯机能感；方案名突出温柔、优雅、浪漫、精致或松弛中的真实特点，禁止使用“清爽约会”这类天气词加场景的机械命名。",
    },
    "travel": {
        "scene_name": "出行",
        "scene_requirements": "优先舒适、方便活动、耐走、易打理，适合较长时间在外；整体采用轻旅、户外休闲或轻机能风格，在口袋、层次、材质和鞋履上体现便携、耐走与活动感，避免正统商务或过度精致束缚；方案名突出舒适、轻旅、活力、机能、便携或松弛中的真实特点，禁止使用“清爽出行”这类天气词加场景的机械命名。",
    },
}
SCENE_LABEL_FALLBACKS = {"commute": "利落通勤", "date": "精致约会", "travel": "舒适出行"}
NAMING_SCENES = {"commute": "通勤", "date": "约会", "travel": "出行"}


class OutfitAIServiceError(RuntimeError):
    pass


def _first_str(value: Any, fallback: str = "") -> str:
    return str(value).strip() if value is not None else fallback


def _normalize_guide(raw: Any) -> Dict[str, Any]:
    raw = raw or {}
    steps = raw.get("steps") or []
    return {
        "formula": _first_str(raw.get("formula"), "今日推荐"),
        "steps": [_first_str(step) for step in steps if _first_str(step)][:8] or ["按推荐单品逐件穿着"],
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


def _profile_styling_points(profile: Dict[str, str]) -> List[str]:
    height = {
        "偏矮": "上装避免过长，腰线保持清晰，裤脚利落不堆叠",
        "中等": "衣长与裤长保持自然比例，腰线清楚即可",
        "偏高": "保留完整纵向线条，衣袖和裤长避免偏短",
    }.get(profile.get("height_group"), "衣长与裤长保持自然比例")
    weight = {
        "偏轻": "用适度层次和有结构感的面料完善轮廓，避免过度紧贴",
        "中等": "采用合身但不紧绷的常规松量",
        "偏重": "选择有垂感且不过度贴身的松量，给肩腰和活动留出空间",
    }.get(profile.get("weight_group"), "采用合身但不紧绷的常规松量")
    return [
        f"{height}；{weight}。",
        "细节可保持简洁轻快，同时兼顾当前场景的得体度。",
    ]


def _with_scene_context(payload: Dict[str, Any]) -> Dict[str, Any]:
    context = dict(payload)
    context.update(SCENE_CONTEXT.get(_first_str(context.get("scene")), {}))
    return context


def _normalize_label(raw: Any, context: Dict[str, Any]) -> str:
    scene = _first_str(context.get("scene"))
    label = _first_str(raw, SCENE_LABEL_FALLBACKS.get(scene, "AI 穿搭方案"))
    if scene in {"date", "travel"} and "清爽" in label:
        label = SCENE_LABEL_FALLBACKS[scene]
    return label[:8]


def _normalize_outfit_name(raw: Any, recognition_result: Dict[str, Any]) -> str:
    name = _first_str(raw).strip("“”\"' \n\r\t")
    suggested_scenes = [
        NAMING_SCENES[scene_id]
        for scene_id in recognition_result.get("suggested_scenes") or []
        if scene_id in NAMING_SCENES
    ]
    if suggested_scenes:
        scene = next((scene_name for scene_name in suggested_scenes if scene_name in name), suggested_scenes[0])
        style = name
        for scene_name in NAMING_SCENES.values():
            style = style.replace(scene_name, "")
        style = style.strip(" ·＋+-，,。")
        if style:
            name = style[: 30 - len(scene)] + scene
    else:
        for scene_name in NAMING_SCENES.values():
            name = name.replace(scene_name, "")
    return name[:30].strip()


def name_follows_style_scene(name: str, recognition_result: Dict[str, Any]) -> bool:
    suggested_scenes = [
        NAMING_SCENES[scene_id]
        for scene_id in recognition_result.get("suggested_scenes") or []
        if scene_id in NAMING_SCENES
    ]
    return not suggested_scenes or any(
        name.endswith(scene) and len(name) > len(scene) for scene in suggested_scenes
    )


class OutfitAIService:
    def __init__(self) -> None:
        self.url = (os.getenv("AI_API_URL") or os.getenv("VISION_API_URL") or "").rstrip("/")
        self.key = os.getenv("AI_API_KEY") or os.getenv("VISION_API_KEY") or ""
        self.model = os.getenv("AI_MODEL") or os.getenv("VISION_MODEL") or ""
        self.fast_model = os.getenv("AI_FAST_MODEL") or self.model
        self.quality_model = os.getenv("AI_QUALITY_MODEL") or self.model
        base = Path(__file__).resolve().parents[1] / "prompts"
        self.prompt = (base / "outfit_generation.txt").read_text()
        self.items_prompt = (base / "outfit_items.txt").read_text()
        self.advice_prompt = (base / "outfit_advice.txt").read_text()
        self.naming_prompt = (base / "outfit_naming.txt").read_text()

    @property
    def configured(self) -> bool:
        return bool(self.url and self.key and self.fast_model and self.quality_model)

    async def _call(
        self,
        prompt: str,
        user_content: Any,
        max_tokens: int,
        model: str,
        fallback_model: str,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        if not self.configured:
            raise OutfitAIServiceError("AI 模型尚未配置")
        models = list(dict.fromkeys([model, fallback_model]))
        async with httpx.AsyncClient(timeout=45) as client:
            for index, selected_model in enumerate(models):
                payload = {
                    "model": selected_model,
                    "enable_thinking": False,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": prompt},
                        {
                            "role": "user",
                            "content": json.dumps(user_content, ensure_ascii=False),
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
                    raw = str(content).strip().removeprefix("```json").removesuffix("```").strip()
                    return json.loads(raw)
                except httpx.HTTPStatusError as caught:
                    error = caught
                    retryable = caught.response.status_code == 429 or caught.response.status_code >= 500
                except (httpx.RequestError, KeyError, TypeError, ValueError) as caught:
                    error = caught
                    retryable = True
                if not retryable or index == len(models) - 1:
                    raise OutfitAIServiceError("AI 生成失败") from error
        raise OutfitAIServiceError("AI 生成失败")

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

    def _normalize(self, raw: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        items = self._normalize_items(raw.get("items"))
        if not items:
            raise OutfitAIServiceError("AI 推荐未返回可映射到图标的单品")
        return {
            "label": _normalize_label(raw.get("label"), context),
            "items": items,
            "replication_guide": _normalize_guide(raw.get("replication_guide")),
            "outfit_analysis": _normalize_analysis(raw.get("outfit_analysis")),
        }

    async def generate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """完整生成（含建议），用于服务端预生成系统推荐。"""
        enriched_context = _with_scene_context(context)
        raw = await self._call(
            self.prompt, enriched_context, 1200, self.quality_model, self.fast_model
        )
        return self._normalize(raw, enriched_context)

    async def generate_items(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """只生成首页展示需要的单品（快）。"""
        enriched_context = _with_scene_context(context)
        raw = await self._call(
            self.items_prompt,
            enriched_context,
            500,
            self.fast_model,
            self.quality_model,
            temperature=0.2,
        )
        items = self._normalize_items(raw.get("items"))
        if not items:
            raise OutfitAIServiceError("AI 未返回可映射到图标的单品")
        return {
            "label": _normalize_label(raw.get("label"), enriched_context),
            "items": items,
        }

    async def generate_advice(
        self,
        items: List[Dict[str, Any]],
        weather_summary: Any,
        scene: str,
        audience: str,
        person_profile: Dict[str, str],
    ) -> Dict[str, Any]:
        """按需生成建议文案（点进详情时调用）。"""
        raw = await self._call(
            self.advice_prompt,
            _with_scene_context(
                {
                    "scene": scene,
                    "audience": audience,
                    "weather": weather_summary,
                    "items": items,
                    "person_profile": person_profile,
                }
            ),
            800,
            self.fast_model,
            self.quality_model,
        )
        guide = _normalize_guide(raw.get("replication_guide"))
        guide["styling_points"] = (
            _profile_styling_points(person_profile) + guide["styling_points"]
        )[:3]
        return {
            "replication_guide": guide,
            "outfit_analysis": _normalize_analysis(raw.get("outfit_analysis")),
        }

    async def generate_name(self, recognition_result: Dict[str, Any]) -> str:
        """根据图片识别结果生成一次可编辑的穿搭名称。"""
        raw = await self._call(
            self.naming_prompt, recognition_result, 100, self.fast_model, self.quality_model
        )
        name = _normalize_outfit_name(raw.get("name"), recognition_result)
        if not name:
            raise OutfitAIServiceError("AI 未返回有效的穿搭名称")
        return name
