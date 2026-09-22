"""首页图标方案：JEV 选图标、文字模型补文案、文字模型整体兜底。"""

import asyncio
import json

import httpx

from app.domain.component_rules import SUPPORTED_COMPONENT_ASSET_KEYS
from app.services.jev_service import (
    ACCESSORY_NONE,
    GENDER_LOCKED,
    build_request,
)
from app.services.outfit_ai_service import OutfitAIService

REALTIME_CONTEXT = {
    "scene": "commute",
    "audience": "mens",
    "season": "spring-autumn",
    "apparent_min": 12,
    "apparent_max": 20,
    "thermal_band": "cool",
    "needs_waterproof": False,
    "needs_windproof": False,
    "required_top": "long_sleeve",
    "required_bottom": "long_bottom",
    "required_shoes": "daily_shoes",
    "available_assets": sorted(SUPPORTED_COMPONENT_ASSET_KEYS),
}

# 整体兜底路径：文字模型一次性给出完整 Prompt A 方案。
TEXT_MODEL_PLAN = {
    "status": "ok",
    "label": "兜底方案",
    "items": [
        {
            "slot": "top",
            "functional_icon_key": "long_sleeve",
            "asset_key": "top_shirt",
            "variant_type": "长袖衬衫",
            "color_name": "白色",
            "thickness": "regular",
        }
    ],
}

# 文案补充路径：只给自由文本，不改 items。
TEXT_SUPPLEMENT = {
    "status": "ok",
    "label": "清晨通勤",
    "outfit_dna": {
        "silhouette_route": "自然垂坠",
        "proportion": "上短下长",
        "color_structure": "深浅对比",
        "footwear_shape": "鞋与上装呼应",
    },
    "locked_features": ["长袖上衣的落肩结构", "常规长裤的直筒裤型"],
    "signature_features": ["通勤感利落轮廓"],
}

PLAN_TEXT_MARKER = "文案补充"


def _answers_for(questions):
    answers = {}
    for question_id, question in questions.items():
        options = list(question.get("criteria") or {})
        if question_id == "accessory" and ACCESSORY_NONE in options:
            chosen = ACCESSORY_NONE
        else:
            chosen = options[0]
        answers[question_id] = {
            "type": "choice",
            "choice": chosen,
            "confidence": 1.0,
            "probabilities": {option: float(option == chosen) for option in options},
        }
    return answers


class _FakeRuntime:
    """jev_service 与 outfit_ai_service 共享同一个 httpx 模块，按 URL 分发。"""

    def __init__(self, jev_status=200, text_status=200, answers_builder=_answers_for):
        self.jev_status = jev_status
        self.text_status = text_status
        self.answers_builder = answers_builder
        self.jev_calls = []
        self.text_calls = []

    def install(self, monkeypatch):
        runtime = self

        class FakeAsyncClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, headers=None, **kwargs):
                body = kwargs.get("json") or {}
                request = httpx.Request("POST", url)
                if url.endswith("/systemone"):
                    runtime.jev_calls.append(body)
                    if runtime.jev_status >= 400:
                        return httpx.Response(runtime.jev_status, request=request)
                    return httpx.Response(
                        200,
                        request=request,
                        json={
                            "model": "jev-1.13.0",
                            "answers": runtime.answers_builder(body["questions"]),
                            "usage": {"input_tokens": 420, "output_tokens": 60},
                        },
                    )
                system_prompt = ((body.get("messages") or [{}])[0].get("content") or "")
                kind = "plan_text" if PLAN_TEXT_MARKER in system_prompt else "items"
                runtime.text_calls.append({"kind": kind, "model": body["model"]})
                if kind == "plan_text" and runtime.text_status >= 400:
                    return httpx.Response(runtime.text_status, request=request)
                content = TEXT_SUPPLEMENT if kind == "plan_text" else TEXT_MODEL_PLAN
                return httpx.Response(
                    200,
                    request=request,
                    json={
                        "choices": [
                            {"message": {"content": json.dumps(content, ensure_ascii=False)}}
                        ]
                    },
                )

        monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)


def _configure_text_models(monkeypatch):
    monkeypatch.setenv("AI_API_URL", "https://example.test/v1")
    monkeypatch.setenv("AI_API_KEY", "test-ai-key")
    monkeypatch.setenv("AI_FAST_MODEL", "qwen-turbo")
    monkeypatch.setenv("AI_QUALITY_MODEL", "qwen3.8-flash")


def _asset_keys(result):
    return [item["asset_key"] for item in result["items"]]


JEV_ASSET_KEYS = ["top_tshirt_long", "bottom_casual_pants", "shoe_sneaker"]


def test_homepage_plan_takes_icons_from_jev_and_copy_from_text_model(monkeypatch):
    _configure_text_models(monkeypatch)
    monkeypatch.setenv("JEV_API_KEY", "test-jev-key")
    monkeypatch.setenv("JEV_MODEL", "jev-latest")
    runtime = _FakeRuntime()
    runtime.install(monkeypatch)

    result = asyncio.run(OutfitAIService().generate_items(REALTIME_CONTEXT))

    assert len(runtime.jev_calls) == 1
    assert runtime.jev_calls[0]["model"] == "jev-latest"
    # 图标来自 JEV，文案只调用了一次补充接口，没有走整体兜底。
    assert _asset_keys(result) == JEV_ASSET_KEYS
    assert runtime.text_calls == [{"kind": "plan_text", "model": "qwen-turbo"}]
    # 文案字段来自文字模型，可枚举字段仍以 JEV 为准。
    assert result["label"] == "清晨通勤"
    assert result["outfit_dna"]["proportion"] == "上短下长"
    assert result["locked_features"] == ["长袖上衣的落肩结构", "常规长裤的直筒裤型"]
    assert result["style_tags"] == ["minimal"]
    assert result["prompt_version"] == "wearcue-realtime-plan-v3.2"
    assert result["replication_guide"] is None


def test_homepage_plan_keeps_jev_icons_when_copy_supplement_fails(monkeypatch):
    _configure_text_models(monkeypatch)
    monkeypatch.setenv("JEV_API_KEY", "test-jev-key")
    runtime = _FakeRuntime(text_status=500)
    runtime.install(monkeypatch)

    result = asyncio.run(OutfitAIService().generate_items(REALTIME_CONTEXT))

    assert _asset_keys(result) == JEV_ASSET_KEYS
    # 文案补不成时沿用 JEV 路径的稳定词表，不丢弃图标方案。
    assert result["label"] == "利落通勤"
    assert result["outfit_dna"]["silhouette_route"] == "利落直线"


def test_homepage_plan_falls_back_to_the_full_text_model_when_jev_errors(monkeypatch):
    _configure_text_models(monkeypatch)
    monkeypatch.setenv("JEV_API_KEY", "test-jev-key")
    runtime = _FakeRuntime(jev_status=503)
    runtime.install(monkeypatch)

    result = asyncio.run(OutfitAIService().generate_items(REALTIME_CONTEXT))

    assert len(runtime.jev_calls) == 1
    assert runtime.text_calls == [{"kind": "items", "model": "qwen-turbo"}]
    assert result["label"] == "兜底方案"


def test_homepage_plan_falls_back_when_jev_omits_required_answers(monkeypatch):
    _configure_text_models(monkeypatch)
    monkeypatch.setenv("JEV_API_KEY", "test-jev-key")
    runtime = _FakeRuntime(answers_builder=lambda questions: {})
    runtime.install(monkeypatch)

    result = asyncio.run(OutfitAIService().generate_items(REALTIME_CONTEXT))

    assert runtime.text_calls == [{"kind": "items", "model": "qwen-turbo"}]
    assert result["label"] == "兜底方案"


def test_homepage_plan_uses_the_full_text_model_when_jev_is_not_configured(monkeypatch):
    _configure_text_models(monkeypatch)
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    runtime = _FakeRuntime()
    runtime.install(monkeypatch)

    service = OutfitAIService()
    assert service.jev.configured is False
    result = asyncio.run(service.generate_items(REALTIME_CONTEXT))

    assert runtime.jev_calls == []
    assert runtime.text_calls == [{"kind": "items", "model": "qwen-turbo"}]
    assert result["label"] == "兜底方案"


def test_jev_icon_options_stay_inside_the_released_vocabulary():
    _, questions, spec = build_request(REALTIME_CONTEXT)
    option_sets = {
        question_id: set(question.get("criteria") or {})
        for question_id, question in questions.items()
    }

    asset_options = {
        option
        for question_id, options in option_sets.items()
        if question_id.endswith("_asset")
        for option in options
    }
    assert asset_options <= SUPPORTED_COMPONENT_ASSET_KEYS
    # 男装上下文不得出现女装专属图标。
    assert not any(GENDER_LOCKED.get(key) == "womens" for key in asset_options)
    # 通勤禁止商务正装，正装皮鞋不能进入候选。
    assert "shoe_leather" not in option_sets["shoes_asset"]
    # 每件必备单品都同时问了厚薄，且三个槽位都进了方案。
    assert {slot.slot for slot in spec.slots} == {"top", "bottom", "shoes"}
    assert all(f"{slot.slot}_thickness" in questions for slot in spec.slots)
