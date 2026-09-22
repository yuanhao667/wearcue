"""TypeSafe JEV（System One）客户端，以及首页“换一套”的图标方案规划器。

JEV 不是对话模型：它只回答被限定的类型化问题（choice / noul / score），
返回取值和校准概率。因此它只接管 Prompt A 里本来就是一个分类问题的部分——
在天气规则已经确定的每个必备槽位里，从既有图标库中挑选具体单品图标——
其余字段由稳定词表推导。文字模型（AI_FAST_MODEL）保留为兜底路径。

JEV 无法生成自由文本（label / variant_type / outfit_dna 等），也无法读图；
这也是它只做“选择”而不做“识别”和“方案生成”的原因。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import httpx

from app.domain.component_rules import FUNCTIONAL_ASSET_KEYS, SUPPORTED_COMPONENT_ASSET_KEYS

logger = logging.getLogger(__name__)

DEFAULT_JEV_API_URL = "https://api.typesafe.ai/v1"
DEFAULT_JEV_MODEL = "jev-latest"
DEFAULT_JEV_TIMEOUT_SECONDS = 8.0

# 稳定图标词表的中文名，与前端 garment-icon-map.ts 的 label 保持一致。
ASSET_LABELS: Dict[str, str] = {
    "top_tshirt_short": "短袖 T 恤",
    "top_tshirt_long": "长袖 T 恤",
    "top_tank": "基础背心",
    "top_camisole": "基础吊带",
    "top_shirt": "长袖衬衫",
    "top_sweatshirt": "卫衣",
    "top_knit": "厚针织衫",
    "top_knit_vest": "针织背心",
    "outer_light_jacket": "薄款外套",
    "outer_wool_coat": "厚大衣",
    "outer_down_short": "厚羽绒服",
    "outer_shell": "冲锋衣",
    "bottom_shorts": "短裤",
    "bottom_casual_pants": "常规长裤",
    "bottom_sweatpants": "保暖长裤",
    "bottom_skirt_short": "短裙",
    "bottom_skirt_long": "长裙",
    "onepiece_dress": "连衣裙",
    "shoe_sneaker": "低帮鞋",
    "shoe_canvas": "高帮鞋",
    "shoe_leather": "正装皮鞋",
    "shoe_pump": "高跟鞋",
    "shoe_sneaker_high_top": "高帮运动鞋",
    "acc_baseball_cap": "棒球帽",
    "acc_bucket_hat": "渔夫帽",
    "acc_beanie": "针织帽",
    "acc_gloves": "手套",
    "acc_tote_bag": "托特包",
    "acc_crossbody_bag": "斜挎包",
    "acc_backpack": "双肩包",
    "acc_glasses": "眼镜 / 墨镜",
    "acc_scarf": "围巾",
}

# 仅这两个性别专属的图标不能跨性别推荐；未列出的图标男女通用。
GENDER_LOCKED: Dict[str, str] = {
    "top_tank": "mens",
    "shoe_leather": "mens",
    "top_camisole": "womens",
    "bottom_skirt_short": "womens",
    "bottom_skirt_long": "womens",
    "onepiece_dress": "womens",
    "shoe_pump": "womens",
}

# 天气规则给出的必备功能族 -> 该族内可选的实体图标。
SLOT_CANDIDATES: Dict[str, Dict[str, List[str]]] = {
    "top": {
        "short_sleeve": ["top_tshirt_short", "top_tank", "top_camisole"],
        "short_or_long_sleeve": ["top_tshirt_short", "top_tshirt_long", "top_shirt"],
        "long_sleeve": ["top_tshirt_long", "top_shirt", "top_sweatshirt", "top_knit"],
        "warm_top": ["top_knit", "top_sweatshirt", "top_knit_vest", "top_shirt"],
    },
    "bottom": {
        "short_bottom": ["bottom_shorts", "bottom_skirt_short"],
        "long_bottom": ["bottom_casual_pants", "bottom_skirt_long"],
        "warm_bottom": ["bottom_sweatpants", "bottom_casual_pants"],
    },
    "outerwear": {
        "light_outerwear": ["outer_light_jacket"],
        "warm_outerwear": ["outer_down_short", "outer_wool_coat"],
        "protective_outerwear": ["outer_shell"],
    },
    "shoes": {
        "daily_shoes": [
            "shoe_sneaker", "shoe_canvas", "shoe_sneaker_high_top",
            "shoe_leather", "shoe_pump",
        ],
        "protective_shoes": ["shoe_canvas", "shoe_sneaker_high_top"],
    },
}

ACCESSORY_CANDIDATES: List[str] = [
    "acc_baseball_cap", "acc_beanie", "acc_bucket_hat", "acc_tote_bag",
    "acc_crossbody_bag", "acc_backpack", "acc_glasses", "acc_scarf",
]

ACCESSORY_NONE = "none"

THICKNESS_OPTIONS: List[str] = ["thin", "regular", "thick"]
THICKNESS_LABELS: Dict[str, str] = {
    "thin": "薄款，适合偏热体感",
    "regular": "常规厚度，适合温和体感",
    "thick": "加厚，适合偏冷体感",
}

STYLE_OPTIONS: List[str] = ["minimal", "sport", "outdoor"]
STYLE_LABELS: Dict[str, str] = {
    "minimal": "简约干净，基础款为主",
    "sport": "运动感，休闲且有活力",
    "outdoor": "户外感，功能性面料和轮廓",
}

# 与 Prompt A/前端校验一致的稳定标签词表，不含任何会被性别或场景规则拒绝的词。
LABEL_OPTIONS: Dict[str, List[str]] = {
    "commute": ["利落通勤", "简约通勤", "轻快通勤", "日常通勤", "轻松通勤", "简洁通勤"],
    "date": ["精致约会", "松弛约会", "简约约会", "轻快约会", "自然约会", "利落约会"],
    "travel": ["活力出行", "轻旅出行", "自在出行", "轻便出行", "松弛出行", "简洁出行"],
}

DNA_OPTIONS: Dict[str, List[str]] = {
    "silhouette_route": ["利落直线", "上松下收", "上收下松", "箱型宽松", "自然垂坠"],
    "proportion": ["高腰线", "自然腰线", "上短下长", "长外套盖胯"],
    "color_structure": ["同色系", "基础色为主", "深浅对比", "基础色加一点亮色"],
    "footwear_shape": ["鞋裤顺色", "轻量鞋型收尾", "厚底增加分量", "鞋与上装呼应"],
}

SCENE_NAMES: Dict[str, str] = {"commute": "通勤", "date": "约会", "travel": "出行"}
AUDIENCE_NAMES: Dict[str, str] = {"mens": "男装", "womens": "女装"}
SEASON_NAMES: Dict[str, str] = {
    "spring-autumn": "春秋",
    "summer": "夏季",
    "winter": "冬季",
}

# 通勤场景禁止商务正装元素；正装皮鞋的图标名会被场景校验拒绝。
COMMUTE_BLOCKED_ASSETS = {"shoe_leather"}


class JevServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class JevAnswer:
    type: str
    choice: Optional[str] = None
    noul: Optional[float] = None
    score: Optional[int] = None
    confidence: Optional[float] = None
    probabilities: Dict[str, float] = field(default_factory=dict)


@dataclass
class _SlotPlan:
    slot: str
    functional_icon_key: str
    asset_question_id: str
    thickness_question_id: str
    candidates: List[str]


@dataclass
class _PlanSpec:
    slots: List[_SlotPlan]
    accessory_question_id: Optional[str]
    accessory_candidates: List[str]
    style_question_id: str
    label_question_id: str
    dna_question_ids: Dict[str, str]


class JevClient:
    """最小 TypeSafe System One 客户端：一个 endpoint，一次并行提问。"""

    def __init__(self) -> None:
        self.url = (os.getenv("JEV_API_URL") or DEFAULT_JEV_API_URL).rstrip("/")
        self.key = os.getenv("JEV_API_KEY") or ""
        self.model = os.getenv("JEV_MODEL") or DEFAULT_JEV_MODEL
        try:
            configured_timeout = float(
                os.getenv("JEV_TIMEOUT_SECONDS", str(DEFAULT_JEV_TIMEOUT_SECONDS))
            )
        except ValueError:
            configured_timeout = DEFAULT_JEV_TIMEOUT_SECONDS
        self.timeout_seconds = min(30.0, max(0.5, configured_timeout))

    @property
    def configured(self) -> bool:
        return bool(self.url and self.key and self.model)

    async def ask(
        self, state: Any, questions: Dict[str, Any]
    ) -> Dict[str, JevAnswer]:
        if not self.configured:
            raise JevServiceError("JEV 尚未配置")
        if not questions:
            raise JevServiceError("JEV 没有问题可问")
        payload = {
            "model": self.model,
            "state": state if isinstance(state, str) else json.dumps(state, ensure_ascii=False),
            "questions": questions,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds + 5) as client:
                response = await client.post(
                    self.url + "/systemone",
                    headers={
                        "Authorization": "Bearer " + self.key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPStatusError as caught:
            raise JevServiceError(f"JEV 返回 HTTP {caught.response.status_code}") from caught
        except (httpx.RequestError, ValueError, TypeError) as caught:
            raise JevServiceError("JEV 请求失败") from caught
        if not isinstance(body, dict):
            raise JevServiceError("JEV 返回体不是对象")
        raw_answers = body.get("answers")
        if not isinstance(raw_answers, dict):
            raise JevServiceError("JEV 未返回 answers")
        return {
            str(key): _parse_answer(value)
            for key, value in raw_answers.items()
            if isinstance(value, dict)
        }


def _parse_answer(value: Dict[str, Any]) -> JevAnswer:
    def _number(source: Any) -> Optional[float]:
        return float(source) if isinstance(source, (int, float)) and not isinstance(source, bool) else None

    return JevAnswer(
        type=str(value.get("type") or ""),
        choice=value.get("choice") if isinstance(value.get("choice"), str) else None,
        noul=_number(value.get("noul")),
        score=int(value["score"]) if isinstance(value.get("score"), (int, float)) else None,
        confidence=_number(value.get("confidence")),
        probabilities={
            str(option): float(probability)
            for option, probability in (value.get("probabilities") or {}).items()
            if isinstance(probability, (int, float))
        },
    )


def _choice_question(
    instructions: str,
    options: Sequence[str],
    descriptions: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    descriptions = descriptions or {}
    return {
        "type": "choice",
        "instructions": instructions,
        "criteria": {
            str(option): descriptions.get(str(option)) or ASSET_LABELS.get(str(option))
            for option in options
        },
    }


def _slot_label(slot: str) -> str:
    return {
        "top": "上装",
        "bottom": "下装",
        "outerwear": "外层",
        "shoes": "鞋",
    }.get(slot, slot)


def _audience_candidates(candidates: Sequence[str], audience: str) -> List[str]:
    return [
        key for key in candidates
        if GENDER_LOCKED.get(key) in (None, audience)
    ]


def _required_slots(context: Dict[str, Any]) -> List[Tuple[str, str]]:
    slots: List[Tuple[str, str]] = []
    for slot, key in (
        ("top", "required_top"),
        ("bottom", "required_bottom"),
        ("outerwear", "required_outerwear"),
        ("shoes", "required_shoes"),
    ):
        functional_key = str(context.get(key) or "").strip()
        if functional_key:
            slots.append((slot, functional_key))
    return slots


def _state_text(context: Dict[str, Any], blocks: Sequence[str]) -> str:
    """把当次输入整理成 JEV 的 state：只放与判断相关的证据。"""
    apparent_min = context.get("apparent_min")
    apparent_max = context.get("apparent_max")
    temperature = (
        f"{apparent_min}~{apparent_max}℃"
        if isinstance(apparent_min, (int, float)) and isinstance(apparent_max, (int, float))
        else "未知"
    )
    weather_requirements = [
        name for flag, name in (
            ("needs_waterproof", "需要防水"),
            ("needs_windproof", "需要防风"),
        ) if context.get(flag)
    ]
    return json.dumps(
        {
            "场景": SCENE_NAMES.get(str(context.get("scene") or ""), str(context.get("scene") or "")),
            "人群": AUDIENCE_NAMES.get(str(context.get("audience") or ""), ""),
            "季节": SEASON_NAMES.get(str(context.get("season") or ""), ""),
            "体感温度": temperature,
            "天气要求": weather_requirements or ["无特殊要求"],
            "天气规则已确定": list(blocks),
        },
        ensure_ascii=False,
    )


def build_request(
    context: Dict[str, Any]
) -> Tuple[str, Dict[str, Any], _PlanSpec]:
    """把首页换一套的上下文转成一次 JEV 并行提问。"""
    audience = str(context.get("audience") or "")
    scene = str(context.get("scene") or "")
    available = {str(key) for key in (context.get("available_assets") or [])}
    scene_name = SCENE_NAMES.get(scene, scene)

    questions: Dict[str, Any] = {}
    slots: List[_SlotPlan] = []
    blocks: List[str] = []

    for slot, functional_key in _required_slots(context):
        candidates = _audience_candidates(
            SLOT_CANDIDATES.get(slot, {}).get(functional_key, []), audience
        )
        candidates = [key for key in candidates if not available or key in available]
        if scene == "commute":
            candidates = [key for key in candidates if key not in COMMUTE_BLOCKED_ASSETS]
        if not candidates:
            continue
        asset_question_id = f"{slot}_asset"
        thickness_question_id = f"{slot}_thickness"
        questions[asset_question_id] = _choice_question(
            (
                f"为「{scene_name}」场景的日常穿搭选择一件{_slot_label(slot)}。"
                "按场景得体和整体协调来选，不要选过于正式或与天气不符的那一件。"
            ),
            candidates,
        )
        questions[thickness_question_id] = _choice_question(
            f"这件{_slot_label(slot)}的厚薄应该是？", THICKNESS_OPTIONS, THICKNESS_LABELS
        )
        slots.append(
            _SlotPlan(
                slot=slot,
                functional_icon_key=functional_key,
                asset_question_id=asset_question_id,
                thickness_question_id=thickness_question_id,
                candidates=candidates,
            )
        )
        blocks.append(f"{_slot_label(slot)}：{ASSET_LABELS.get(candidates[0], candidates[0])}类")

    accessory_candidates = [
        key for key in ACCESSORY_CANDIDATES if not available or key in available
    ]
    accessory_question_id: Optional[str] = None
    accessory_options = accessory_candidates + [ACCESSORY_NONE]
    if accessory_candidates:
        accessory_question_id = "accessory"
        questions[accessory_question_id] = _choice_question(
            (
                f"这套「{scene_name}」穿搭需要额外加一件配饰吗？"
                "只有在场景和天气确实需要时才选，否则选 none。"
            ),
            accessory_options,
            {ACCESSORY_NONE: "不需要额外配饰"},
        )

    style_question_id = "style"
    questions[style_question_id] = _choice_question(
        f"这套「{scene_name}」穿搭的主风格是？", STYLE_OPTIONS, STYLE_LABELS
    )

    label_question_id = "label"
    label_options = LABEL_OPTIONS.get(scene) or ["今日穿搭"]
    questions[label_question_id] = _choice_question(
        "这套穿搭最合适的标题是？", label_options
    )

    dna_question_ids: Dict[str, str] = {}
    for field_name, options in DNA_OPTIONS.items():
        question_id = f"dna_{field_name}"
        dna_question_ids[field_name] = question_id
        questions[question_id] = _choice_question(
            f"这套穿搭的「{field_name}」应该是？", options
        )

    spec = _PlanSpec(
        slots=slots,
        accessory_question_id=accessory_question_id,
        accessory_candidates=accessory_candidates,
        style_question_id=style_question_id,
        label_question_id=label_question_id,
        dna_question_ids=dna_question_ids,
    )
    return _state_text(context, blocks), questions, spec


def assemble_plan(
    context: Dict[str, Any],
    spec: _PlanSpec,
    answers: Dict[str, JevAnswer],
) -> Dict[str, Any]:
    """把 JEV 的选择装配成 Prompt A 的输出结构（仅选择类字段，文本用稳定词表）。"""
    items: List[Dict[str, Any]] = []
    for slot_plan in spec.slots:
        answer = answers.get(slot_plan.asset_question_id)
        asset_key = answer.choice if answer else None
        if asset_key not in slot_plan.candidates:
            raise JevServiceError(f"JEV 未为 {slot_plan.slot} 返回可用图标")
        thickness_answer = answers.get(slot_plan.thickness_question_id)
        thickness = (
            thickness_answer.choice
            if thickness_answer and thickness_answer.choice in THICKNESS_OPTIONS
            else "regular"
        )
        items.append(
            {
                "slot": slot_plan.slot,
                "functional_icon_key": slot_plan.functional_icon_key,
                "asset_key": asset_key,
                "variant_type": ASSET_LABELS.get(asset_key, asset_key),
                "color_name": "基础色",
                "color_value": None,
                "color_type": "solid",
                "thickness": thickness,
            }
        )

    if spec.accessory_question_id:
        accessory_answer = answers.get(spec.accessory_question_id)
        accessory_key = accessory_answer.choice if accessory_answer else None
        if accessory_key in spec.accessory_candidates:
            items.append(
                {
                    "slot": "equipment",
                    "functional_icon_key": FUNCTIONAL_ASSET_KEYS.get(
                        accessory_key, accessory_key
                    ),
                    "asset_key": accessory_key,
                    "variant_type": ASSET_LABELS.get(accessory_key, accessory_key),
                    "color_name": "基础色",
                    "color_value": None,
                    "color_type": "solid",
                    "thickness": "regular",
                }
            )

    style_answer = answers.get(spec.style_question_id)
    style_tags = (
        [style_answer.choice]
        if style_answer and style_answer.choice in STYLE_OPTIONS
        else ["minimal"]
    )

    label_answer = answers.get(spec.label_question_id)
    label = label_answer.choice if label_answer else None

    outfit_dna: Dict[str, Any] = {}
    for field_name, question_id in spec.dna_question_ids.items():
        answer = answers.get(question_id)
        if answer and answer.choice in (DNA_OPTIONS.get(field_name) or []):
            outfit_dna[field_name] = answer.choice

    apparent_min = context.get("apparent_min")
    apparent_max = context.get("apparent_max")

    return {
        "status": "ok",
        "label": label,
        "season": context.get("season"),
        "scene": context.get("scene"),
        "temperature_range_c": {
            "min": apparent_min if isinstance(apparent_min, (int, float)) else 15,
            "max": apparent_max if isinstance(apparent_max, (int, float)) else 28,
        },
        "style_tags": style_tags,
        "outfit_dna": outfit_dna,
        "locked_features": [
            ASSET_LABELS.get(str(item.get("asset_key")), str(item.get("asset_key")))
            for item in items
        ],
        "items": items,
    }


async def plan_with_jev(
    client: JevClient, context: Dict[str, Any]
) -> Dict[str, Any]:
    """JEV 首选路径；任何失败都抛出 JevServiceError 交给文字模型兜底。"""
    state, questions, spec = build_request(context)
    if not spec.slots:
        raise JevServiceError("天气规则未给出可判断的必备槽位")
    try:
        answers = await asyncio.wait_for(
            client.ask(state, questions), timeout=client.timeout_seconds
        )
        plan = assemble_plan(context, spec, answers)
    except JevServiceError:
        raise
    except TimeoutError as caught:
        raise JevServiceError("JEV 响应超时") from caught
    except Exception as caught:  # 兜底路径必须能接住任何装配异常
        raise JevServiceError(f"JEV 方案装配失败：{type(caught).__name__}") from caught
    logger.info(
        "JEV homepage icon plan ok: items=%d style=%s",
        len(plan["items"]),
        plan["style_tags"],
    )
    return plan


def supported_asset_keys() -> List[str]:
    """暴露给测试与调试：确认候选图标都落在正式图标词表内。"""
    return sorted(SUPPORTED_COMPONENT_ASSET_KEYS)
