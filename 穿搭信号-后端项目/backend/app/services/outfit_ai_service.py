import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List

import httpx

from app.domain.component_rules import normalize_component_thickness

logger = logging.getLogger(__name__)
REALTIME_PLAN_PROMPT_VERSION = "wearcue-realtime-plan-v3.2"
REALTIME_CONTEXT_KEYS = {
    "scene", "audience", "season", "current_apparent_temperature",
    "apparent_min", "apparent_max", "thermal_band", "needs_waterproof",
    "needs_windproof", "required_top", "required_bottom",
    "required_outerwear", "required_shoes", "available_assets",
}

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
    "acc_sunscreen": "acc_sunscreen",
    "acc_baseball_cap": "acc_baseball_cap",
    "acc_beanie": "acc_beanie",
    "acc_bucket_hat": "acc_bucket_hat",
    "acc_tote_bag": "acc_tote_bag",
    "acc_crossbody_bag": "acc_crossbody_bag",
    "acc_backpack": "acc_backpack",
    "backpack": "acc_backpack",
    "acc_glasses": "acc_glasses",
    "glasses": "acc_glasses",
    "sunglasses": "acc_glasses",
    "acc_scarf": "acc_scarf",
    "shoe_sandal": "shoe_sneaker",
    "shoe_boot_short": "shoe_sneaker_high_top",
    "shoe_sneaker_high_top": "shoe_sneaker_high_top",
}

VALID_ASSET_KEYS = {
    "top_tshirt_short", "top_tshirt_long", "top_tank", "top_camisole", "top_shirt",
    "top_sweatshirt", "top_knit", "top_knit_vest", "outer_light_jacket",
    "outer_wool_coat", "outer_down_short", "outer_shell", "bottom_shorts",
    "bottom_casual_pants", "bottom_sweatpants", "bottom_skirt_short",
    "bottom_skirt_long", "onepiece_dress", "shoe_sneaker", "shoe_canvas",
    "shoe_leather", "shoe_pump", "shoe_sneaker_high_top", "acc_baseball_cap", "acc_beanie", "acc_bucket_hat",
    "acc_gloves", "acc_tote_bag", "acc_crossbody_bag", "acc_backpack", "acc_glasses", "acc_scarf",
}

VALID_SLOTS = {"top", "bottom", "outerwear", "onepiece", "shoes", "equipment"}
VALID_THICKNESS = {"thin", "regular", "thick"}
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
COMMUTE_BUSINESS_TERMS = ("西装", "西服", "西裤", "领带", "正装", "商务", "正式", "德比鞋")
AUDIENCE_STYLE_TERMS = {
    "mens": ("温柔", "柔美", "甜美", "娇俏", "妩媚", "少女", "淑女"),
    "womens": ("硬汉", "硬朗", "粗犷", "阳刚", "猛男", "绅士"),
}
SCENE_CONTEXT: Dict[tuple[str, str], Dict[str, str]] = {
    ("commute", "mens"): {
        "scene_name": "通勤",
        "scene_requirements": "中国语境下的男士通勤仅指日常上班或上学，不是商务、会议、面试或正式活动。优先轻松自然、帅气利落、轮廓简洁、易打理和方便走动；严禁主动生成、推荐或作为替代项加入西装或西服、领带、西裤、德比皮鞋、正装皮鞋或商务皮鞋，不得使用轻商务、正式感等措辞。优先选择 T 恤、卫衣、针织衫、休闲衬衫、夹克、风衣、牛仔裤、休闲裤、运动裤、运动鞋或板鞋等日常单品；方案名突出帅气、利落、松弛、简约、轻便或质感，不得使用温柔、柔美、甜美、娇俏、妩媚、少女或淑女等女性化词语，也不能只写天气感。",
    },
    ("commute", "womens"): {
        "scene_name": "通勤",
        "scene_requirements": "中国语境下的女士通勤仅指日常上班或上学，不是商务、会议、面试或正式活动。优先轻松自然、简洁清爽、日常得体、易打理和方便走动；严禁主动生成、推荐或作为替代项加入西装或西服、领带、西裤、德比皮鞋、正装皮鞋或商务皮鞋，不得使用轻商务、正式感等措辞。优先选择 T 恤、卫衣、针织衫、休闲衬衫、夹克、风衣、牛仔裤、休闲裤、运动裤、半身裙、运动鞋或板鞋等日常单品；方案名突出简约、知性、清新、松弛、轻便或日常得体，不得使用硬汉、硬朗、粗犷、阳刚、猛男或绅士等男性化词语，也不能只写天气感。",
    },
    ("date", "mens"): {
        "scene_name": "约会",
        "scene_requirements": "男士约会优先帅气得体、层次清楚、有质感和视觉重点，在配色、材质、轮廓或细节中体现约会氛围，避免纯通勤、纯机能或过度商务；方案名突出帅气、利落、层次、质感、松弛、复古或精致中的真实特点，不得使用温柔、柔美、甜美、娇俏、妩媚、少女或淑女等女性化词语，也禁止使用“清爽约会”这类天气词加场景的机械命名。",
    },
    ("date", "womens"): {
        "scene_name": "约会",
        "scene_requirements": "女士约会优先精致协调、有视觉重点和约会氛围，在配色、材质、轮廓或细节中体现优雅与质感，避免纯通勤或纯机能感；方案名突出优雅、浪漫、温柔、知性、清新、松弛或精致中的真实特点，不得使用硬汉、硬朗、粗犷、阳刚、猛男或绅士等男性化词语，也禁止使用“清爽约会”这类天气词加场景的机械命名。",
    },
    ("travel", "mens"): {
        "scene_name": "出行",
        "scene_requirements": "男士出行优先舒适、方便活动、耐走、易打理，适合较长时间在外；整体采用帅气轻旅、户外休闲或轻机能风格，在口袋、层次、材质和鞋履上体现便携、耐走与活动感，避免正统商务或过度精致束缚；方案名突出帅气、活力、轻旅、机能、便携、层次或松弛中的真实特点，不得使用温柔、柔美、甜美、娇俏、妩媚、少女或淑女等女性化词语，也禁止使用“清爽出行”这类天气词加场景的机械命名。",
    },
    ("travel", "womens"): {
        "scene_name": "出行",
        "scene_requirements": "女士出行优先舒适、轻盈、方便活动、耐走、易打理，适合较长时间在外；整体采用轻旅、户外休闲或轻机能风格，在层次、材质、口袋和鞋履上体现便携、耐走与活动感，避免正统商务、粗犷硬朗或过度精致束缚；方案名突出舒适、轻盈、清新、活力、轻旅、便携或松弛中的真实特点，不得使用硬汉、硬朗、粗犷、阳刚、猛男或绅士等男性化词语，也禁止使用“清爽出行”这类天气词加场景的机械命名。",
    },
}
SCENE_LABEL_FALLBACKS = {
    ("commute", "mens"): "利落通勤",
    ("commute", "womens"): "简约通勤",
    ("date", "mens"): "帅气约会",
    ("date", "womens"): "精致约会",
    ("travel", "mens"): "活力出行",
    ("travel", "womens"): "轻旅出行",
}
NAMING_SCENES = {"commute": "通勤", "date": "约会", "travel": "出行"}
TRAILING_NAME_SEQUENCE_RE = re.compile(r"\s+(?:0?\d{1,3}|[０-９]{1,3})$")


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


def scene_context_for(scene: str, audience: str) -> Dict[str, str]:
    return SCENE_CONTEXT.get(
        (scene, audience), {"scene_name": scene, "scene_requirements": ""}
    )


def _with_scene_context(payload: Dict[str, Any]) -> Dict[str, Any]:
    context = dict(payload)
    context.update(
        scene_context_for(
            _first_str(context.get("scene")), _first_str(context.get("audience"))
        )
    )
    return context


def _reject_business_commute(raw: Dict[str, Any], context: Dict[str, Any]) -> None:
    if _first_str(context.get("scene")) != "commute":
        return
    text = json.dumps(raw, ensure_ascii=False)
    if any(term in text for term in COMMUTE_BUSINESS_TERMS):
        raise OutfitAIServiceError("通勤方案误用了商务正装元素")


def _reject_audience_style(raw: Dict[str, Any], context: Dict[str, Any]) -> None:
    audience = _first_str(context.get("audience"))
    text = json.dumps(raw, ensure_ascii=False)
    if any(term in text for term in AUDIENCE_STYLE_TERMS.get(audience, ())):
        raise OutfitAIServiceError("穿搭风格与用户选择的性别不一致")


def _normalize_label(raw: Any, context: Dict[str, Any]) -> str:
    scene = _first_str(context.get("scene"))
    audience = _first_str(context.get("audience"))
    fallback = SCENE_LABEL_FALLBACKS.get((scene, audience), "AI 穿搭方案")
    label = TRAILING_NAME_SEQUENCE_RE.sub("", _first_str(raw, fallback)).strip()
    if scene in {"date", "travel"} and "清爽" in label:
        label = fallback
    if any(term in label for term in AUDIENCE_STYLE_TERMS.get(audience, ())):
        label = fallback
    return label[:8]


def _normalize_outfit_name(raw: Any, recognition_result: Dict[str, Any]) -> str:
    name = TRAILING_NAME_SEQUENCE_RE.sub(
        "", _first_str(raw).strip("“”\"' \n\r\t")
    ).strip()
    suggested_scenes = [
        NAMING_SCENES[scene_id]
        for scene_id in recognition_result.get("suggested_scenes") or []
        if scene_id in NAMING_SCENES
    ]
    audience = _first_str(recognition_result.get("garment_audience"))
    if any(term in name for term in AUDIENCE_STYLE_TERMS.get(audience, ())):
        scene = suggested_scenes[0] if suggested_scenes else ""
        return {
            ("通勤", "mens"): "利落通勤",
            ("通勤", "womens"): "简约通勤",
            ("约会", "mens"): "帅气约会",
            ("约会", "womens"): "精致约会",
            ("出行", "mens"): "活力出行",
            ("出行", "womens"): "轻旅出行",
        }.get((scene, audience), "协调穿搭")
    if suggested_scenes:
        if "通勤" in name and any(term in name for term in COMMUTE_BUSINESS_TERMS):
            return "日常通勤"
    else:
        for scene_name in NAMING_SCENES.values():
            name = name.replace(scene_name, "")
    return name[:30].strip()


def name_follows_style_scene(name: str, recognition_result: Dict[str, Any]) -> bool:
    audience = _first_str(recognition_result.get("garment_audience"))
    if any(term in name for term in AUDIENCE_STYLE_TERMS.get(audience, ())):
        return False
    return bool(name.strip()) and not (
        "通勤" in name and any(term in name for term in COMMUTE_BUSINESS_TERMS)
    )


class OutfitAIService:
    def __init__(self) -> None:
        self.url = (os.getenv("AI_API_URL") or os.getenv("VISION_API_URL") or "").rstrip("/")
        self.key = os.getenv("AI_API_KEY") or os.getenv("VISION_API_KEY") or ""
        self.model = os.getenv("AI_MODEL") or os.getenv("VISION_MODEL") or ""
        self.fast_model = os.getenv("AI_FAST_MODEL") or self.model
        self.quality_model = os.getenv("AI_QUALITY_MODEL") or self.model
        try:
            configured_timeout = float(os.getenv("AI_REALTIME_TIMEOUT_SECONDS", "30"))
        except ValueError:
            configured_timeout = 30
        self.realtime_timeout_seconds = min(60, max(0.01, configured_timeout))
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
            raw_asset_key = _first_str(item.get("asset_key"))
            if functional_key not in FUNCTIONAL_TO_ASSET and raw_asset_key in VALID_ASSET_KEYS:
                functional_key = raw_asset_key
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
            asset_key = raw_asset_key if raw_asset_key in VALID_ASSET_KEYS else FUNCTIONAL_TO_ASSET[functional_key]
            if asset_key in {"acc_umbrella", "acc_sunscreen"}:
                continue
            items.append(normalize_component_thickness(
                {
                    "slot": slot,
                    "functional_icon_key": functional_key,
                    "asset_key": asset_key,
                    "variant_type": _first_str(item.get("variant_type"), functional_key),
                    "color_name": _first_str(item.get("color_name"), "基础色"),
                    "color_value": color_value or None,
                    "color_type": "solid",
                    "thickness": thickness,
                    "fit": _first_str(item.get("fit")) or None,
                    "shoulder": _first_str(item.get("shoulder")) or None,
                    "length": _first_str(item.get("length")) or None,
                    "waistline": _first_str(item.get("waistline")) or None,
                    "bottom_shape": _first_str(item.get("bottom_shape")) or None,
                    "structure_details": [
                        _first_str(detail) for detail in item.get("structure_details") or []
                        if _first_str(detail)
                    ][:6] or ([_first_str(item.get("design"))] if _first_str(item.get("design")) else []),
                    "material": _first_str(item.get("material")) or None,
                    "pattern_description": _first_str(item.get("pattern_description")) or None,
                    "wearing_method": _first_str(item.get("wearing_method")) or None,
                }
            ))
        return items

    def _normalize(
        self,
        raw: Dict[str, Any],
        context: Dict[str, Any],
        *,
        include_detail: bool = True,
    ) -> Dict[str, Any]:
        items = self._normalize_items(raw.get("items"))
        if not items:
            raise OutfitAIServiceError("AI 推荐未返回可映射到图标的单品")
        status = _first_str(raw.get("status"), "ok")
        if status != "ok":
            raise OutfitAIServiceError(_first_str(raw.get("regeneration_instruction"), "AI 方案未通过 V3 质量检查"))
        styles = [
            style for style in raw.get("style_tags") or []
            if style in {"minimal", "sport", "outdoor"}
        ][:2]
        return {
            "status": "ok",
            "prompt_version": (
                "wearcue-outfit-plan-v3"
                if include_detail
                else REALTIME_PLAN_PROMPT_VERSION
            ),
            "label": _normalize_label(raw.get("label"), context),
            "season": raw.get("season") if raw.get("season") in {"spring-autumn", "summer", "winter"} else context.get("season", "spring-autumn"),
            "temperature_range_c": raw.get("temperature_range_c") or {
                "min": context.get("current_apparent_temperature", context.get("apparent_min", 15)),
                "max": context.get("apparent_max", 28),
            },
            "scene": raw.get("scene") if raw.get("scene") in {"commute", "date", "travel"} else context.get("scene", "commute"),
            "style_tags": styles or ["minimal"],
            "items": items,
            "outfit_dna": raw.get("outfit_dna") or {},
            "signature_features": (raw.get("signature_features") or [])[:8],
            "locked_features": (raw.get("locked_features") or [])[:8],
            "outing_reminders": raw.get("outing_reminders") or [],
            "replication_guide": (
                _normalize_guide(raw.get("replication_guide")) if include_detail else None
            ),
            "outfit_analysis": (
                _normalize_analysis(raw.get("outfit_analysis")) if include_detail else None
            ),
            "image_direction": raw.get("image_direction") or {},
            "quality_check": raw.get("quality_check") or {},
        }

    async def generate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """完整生成（含建议），用于服务端预生成系统推荐。"""
        enriched_context = _with_scene_context(context)
        raw = await self._call(
            self.prompt, enriched_context, 1200, self.quality_model, self.fast_model
        )
        _reject_business_commute(raw, enriched_context)
        _reject_audience_style(raw, enriched_context)
        return self._normalize(raw, enriched_context)

    async def generate_items(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """只用小模型生成首页图标方案；整条调用强制秒级结束。"""
        enriched_context = _with_scene_context(context)
        realtime_context = {
            key: value for key, value in enriched_context.items()
            if key in REALTIME_CONTEXT_KEYS and value is not None
        }
        started_at = time.perf_counter()
        logger.info(
            "AI realtime outfit plan %s started with small model=%s thinking=false timeout=%.1fs",
            REALTIME_PLAN_PROMPT_VERSION,
            self.fast_model,
            self.realtime_timeout_seconds,
        )
        try:
            raw = await asyncio.wait_for(
                self._call(
                    self.items_prompt,
                    realtime_context,
                    480,
                    self.fast_model,
                    self.fast_model,
                    temperature=0.25,
                ),
                timeout=self.realtime_timeout_seconds,
            )
        except TimeoutError as error:
            logger.warning(
                "AI realtime outfit plan %s timed out after %.1fs",
                REALTIME_PLAN_PROMPT_VERSION,
                self.realtime_timeout_seconds,
            )
            raise OutfitAIServiceError("AI 实时穿搭方案响应超时") from error
        logger.info(
            "AI realtime outfit plan %s completed in %dms",
            REALTIME_PLAN_PROMPT_VERSION,
            round((time.perf_counter() - started_at) * 1000),
        )
        _reject_business_commute(raw, enriched_context)
        _reject_audience_style(raw, enriched_context)
        return self._normalize(raw, enriched_context, include_detail=False)

    async def generate_advice(
        self,
        items: List[Dict[str, Any]],
        weather_summary: Any,
        scene: str,
        audience: str,
        person_profile: Dict[str, str],
        outfit_dna: Dict[str, Any] | None = None,
        locked_features: List[str] | None = None,
    ) -> Dict[str, Any]:
        """按需生成建议文案（点进详情时调用）。"""
        enriched_context = _with_scene_context(
            {
                "scene": scene,
                "audience": audience,
                "weather": weather_summary,
                "items": items,
                "person_profile": person_profile,
                "outfit_dna": outfit_dna or {},
                "locked_features": locked_features or [],
            }
        )
        started_at = time.perf_counter()
        raw = await self._call(
            self.advice_prompt,
            enriched_context,
            800,
            self.fast_model,
            self.quality_model,
        )
        logger.info(
            "AI outfit advice completed in %dms",
            round((time.perf_counter() - started_at) * 1000),
        )
        _reject_business_commute(raw, enriched_context)
        _reject_audience_style(raw, enriched_context)
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
