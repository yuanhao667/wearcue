import asyncio

import pytest

from app.services.outfit_image_service import OutfitImageService


@pytest.mark.parametrize("style", ["dashscope", "openai"])
@pytest.mark.parametrize("height", ["偏矮", "中等", "偏高"])
@pytest.mark.parametrize("build", ["偏轻", "偏瘦", "稍瘦", "中等", "稍重", "偏重"])
def test_text_only_body_constraints_reach_provider(monkeypatch, style, height, build):
    monkeypatch.setenv("AI_IMAGE_API_URL", "https://example.test/v1")
    monkeypatch.setenv("AI_IMAGE_API_KEY", "test-key")
    monkeypatch.setenv("AI_IMAGE_API_STYLE", style)
    captured = {}

    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, **kwargs):
            captured.update(kwargs["json"])
            class Response:
                def raise_for_status(self):
                    pass
                def json(self):
                    if style == "dashscope":
                        return {"output": {"choices": [{"message": {"content": [
                            {"image": "https://example.test/image.png", "b64_json": "aW1hZ2U="}
                        ]}}]}}
                    return {"data": [{"b64_json": "aW1hZ2U="}]}
            return Response()

    monkeypatch.setattr("app.services.outfit_image_service.httpx.AsyncClient", Client)
    profile = {"height_group": height, "weight_group": build}
    result = asyncio.run(OutfitImageService().generate(
        "浅灰工装日常", "mens", "travel",
        [{"slot": "top", "variant_type": "浅灰工装夹克", "color_name": "浅灰", "thickness": "regular"}],
        {}, profile,
    ))
    assert result == b"image"
    if style == "dashscope":
        content = captured["input"]["messages"][0]["content"]
        assert len(content) == 1
        assert set(content[0]) == {"text"}
        prompt = content[0]["text"]
    else:
        prompt = captured["prompt"]
        assert "image" not in captured and "images" not in captured
    assert f"{height}身高、{build}体型" in prompt
    if build == "偏重":
        assert "不自动瘦身" in prompt
    if height == "偏矮":
        assert "不拉成长腿高个模特" in prompt
    assert "体型示意图" not in prompt
    assert "背景必须呈现与本次场景相符的真实生活环境" in prompt
    assert "每张图至少呈现一处自然动作" in prompt
    assert "不新增道具或不存在的口袋" in prompt
    assert "浅灰工装夹克" in prompt
    assert "唯一允许出现的 1 件服装与配饰" in prompt
