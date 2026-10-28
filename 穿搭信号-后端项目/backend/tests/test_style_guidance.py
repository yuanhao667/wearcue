import asyncio
import json

import pytest

from app.services.jev_service import build_request
from app.services.outfit_ai_service import OutfitAIService
from app.services.outfit_image_service import OutfitImageService
from app.services.style_guidance import STYLE_GUIDES, style_guidance


@pytest.mark.parametrize("audience", ["mens", "womens"])
@pytest.mark.parametrize("tag", list(STYLE_GUIDES))
@pytest.mark.parametrize("api_style", ["openai", "dashscope"])
def test_style_guide_reaches_image_provider(monkeypatch, audience, tag, api_style):
    monkeypatch.setenv("AI_IMAGE_API_URL", "https://example.test/v1")
    monkeypatch.setenv("AI_IMAGE_API_KEY", "test-key")
    monkeypatch.setenv("AI_IMAGE_API_STYLE", api_style)
    captured = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            if api_style == "dashscope":
                return {"output": {"choices": [{"message": {"content": [
                    {"image": "https://example.test/image.png", "b64_json": "aW1hZ2U="}
                ]}}]}}
            return {"data": [{"b64_json": "aW1hZ2U="}]}

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            captured.update(kwargs["json"])
            return Response()

    monkeypatch.setattr("app.services.outfit_image_service.httpx.AsyncClient", Client)
    items = [{"slot": "top", "variant_type": "卫衣", "color_name": "灰色",
              "pattern_description": "几何图案", "thickness": "thick"}]
    result = asyncio.run(OutfitImageService().generate(
        "穿搭", audience, "travel", items, {},
        {"height_group": "中等", "weight_group": "中等"}, style_tags=[tag],
    ))
    assert result == b"image"
    prompt = (captured["input"]["messages"][0]["content"][0]["text"]
              if api_style == "dashscope" else captured["prompt"])
    assert style_guidance(audience, [tag]) in prompt
    assert "不是生成参考图或固定穿搭模板" in prompt
    assert "本期 46 张" not in prompt
    other_audience = "womens" if audience == "mens" else "mens"
    assert STYLE_GUIDES[tag][other_audience] not in prompt
    for other_tag, guide in STYLE_GUIDES.items():
        if other_tag != tag:
            assert guide["focus"] not in prompt
    assert "几何图案" in prompt
    assert "已确认的单品、颜色、版型、厚度与锁定特征优先" in prompt
    assert "输入没有 equipment：禁止帽子、包" in prompt
    assert len(items) == 1


@pytest.mark.parametrize("method", ["generate", "generate_items"])
def test_full_and_fallback_plans_receive_shared_guides(monkeypatch, method):
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    service = OutfitAIService()
    captured = {}

    async def call(prompt, content, *args, **kwargs):
        captured.update(content)
        return {"style_tags": ["sport"], "items": [
            {"slot": "top", "functional_icon_key": "long_sleeve"}
        ]}

    monkeypatch.setattr(service, "_call", call)
    asyncio.run(getattr(service, method)({
        "audience": "womens", "scene": "travel", "season": "winter",
        "preferred_style_tags": ["sport", "casual"], "required_bottom": "warm_bottom",
    }))
    assert captured["preferred_style_tags"] == ["sport", "casual"]
    assert captured["required_bottom"] == "warm_bottom"
    assert style_guidance("womens") in captured["style_guidance"]
    assert "多选不代表把所有风格混穿" in captured["style_guidance"]
    assert "原创生成先根据当次条件选择表达方向，再确定单品" in captured["style_guidance"]
    assert "不是生成参考图或固定穿搭模板" in captured["style_guidance"]


def test_jev_state_and_text_supplement_use_same_style_definition(monkeypatch):
    context = {"audience": "mens", "scene": "travel", "preferred_style_tags": ["sport"]}
    state, _, _ = build_request(context)
    assert style_guidance("mens") in json.loads(state)["风格穿搭指引"]
    service = OutfitAIService()
    captured = {}

    async def call(prompt, content, *args, **kwargs):
        captured.update(content)
        return {"label": "运动长裤"}

    monkeypatch.setattr(service, "_call", call)
    plan = {"style_tags": ["sport"], "items": [{"slot": "bottom", "variant_type": "运动长裤"}]}
    result = asyncio.run(service._attach_plan_text(plan, context))
    assert captured["style_tags"] == ["sport"]
    assert STYLE_GUIDES["sport"]["season"] in captured["style_guidance"]
    assert STYLE_GUIDES["casual"]["focus"] not in captured["style_guidance"]
    assert result["items"] == plan["items"]
    assert result["style_tags"] == plan["style_tags"]


def test_unknown_or_missing_image_styles_do_not_force_a_style():
    assert style_guidance("mens", []) == ""
    assert style_guidance("mens", ["unknown"]) == ""
    assert style_guidance("mens", ["sport", "sport"]) == style_guidance("mens", ["sport"])


def test_street_style_supports_multiple_routes_without_a_fixed_outfit():
    for audience in ("mens", "womens"):
        guide = style_guidance(audience, ["street"])
        assert "层次、比例、配色、材质对比、图案" in guide
        assert "纯色单品也能构成潮流" in guide
        assert "不要求短夹克、宽腿牛仔裤、贴布或星星图案" in guide
    for tag in STYLE_GUIDES:
        for audience in ("mens", "womens"):
            assert "可参考" not in STYLE_GUIDES[tag][audience]
