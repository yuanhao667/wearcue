import asyncio
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import auth as auth_dependency
from app.api import auth as auth_api
from app.api import mvp, system
from app.main import app
from app.services import recommendation_service
from app.services.outfit_ai_service import OutfitAIService, OutfitAIServiceError
from app.services.outfit_image_service import OutfitImageService, safe_image_url
from app.services.store import Store, user_local_date
from app.services.vision_service import VisionService, VisionServiceError


def _component() -> dict:
    return {
        "slot": "top", "functional_icon_key": "long_sleeve",
        "variant_type": "长袖 T 恤", "color_name": "黑色", "thickness": "regular",
    }


async def _fake_vision_analyze(self, path):
    return {
        "model_version": "test",
        "garment_audience": "mens",
        "requires_user_confirmation": True,
        "components": [
            {
                "slot": "top", "functional_icon_key": "long_sleeve",
                "variant_type": "长袖 T 恤", "color_name": "基础色",
                "color_value": None, "thickness": "regular",
                "confidence": 0.9, "approximate": False, "suggested": False,
            }
        ],
    }


async def _fake_ai_items(self, context):
    return {
        "label": "AI 测试穿搭",
        "items": [_component() | {"asset_key": "top_tshirt_long"}],
    }


async def _fake_ai_advice(self, items, weather_summary, scene, audience, person_profile, *metadata):
    return {
        "replication_guide": {
            "formula": "长袖 T 恤＋长裤",
            "steps": ["先穿长袖 T 恤", "再搭长裤"],
            "styling_points": [],
            "weather_note": "按体感增减外层。",
            "substitute": "同厚度基础款即可。",
        },
        "outfit_analysis": {
            "summary": "适合今日体感的基础搭配。",
            "structure_points": [],
            "completion_advice": [],
        },
    }


async def _fake_ai_name(self, recognition_result):
    return "黑灰层次通勤"


async def _fake_outfit_image(self, label, audience, scene, items, constraints, person_profile, *metadata):
    image = Image.new("RGB", (32, 48), "#dce7e2")
    buffer = BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def _recommendation_payload() -> dict:
    return {
        "apparent_min": 20,
        "apparent_max": 24,
        "scene": "commute",
        "audience": "mens",
        "city_id": "test-city",
        "local_date": "2026-08-30",
    }


def _client(test_store: Store, monkeypatch, audience: str = "mens") -> TestClient:
    monkeypatch.setattr(mvp, "store", test_store)
    monkeypatch.setattr(system, "store", test_store)
    monkeypatch.setattr(auth_dependency, "store", test_store)
    monkeypatch.setattr(auth_api, "store", test_store)
    session = test_store.register("TEST-INVITE", "测试", audience)
    assert session is not None
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {session['token']}"
    return client


def test_backend_root_redirects_to_authenticated_frontend() -> None:
    response = TestClient(app).get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "http://localhost:3456"


def test_single_user_mvp_workflow(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path)
    client = _client(test_store, monkeypatch)
    monkeypatch.setattr(VisionService, "analyze", _fake_vision_analyze)

    settings = client.post(
        "/api/v1/settings",
        json={
            "audience": "mens", "cold_offset": -2,
            "height_group": "偏高", "weight_group": "中等",
        },
    )
    assert settings.status_code == 200
    assert settings.json()["cold_offset"] == -2
    assert {
        key: settings.json()[key]
        for key in ("height_group", "weight_group", "age_group")
    } == {
        "height_group": "偏高", "weight_group": "中等", "age_group": "青年",
    }

    outfit_payload = {
        "label": "测试穿搭", "audience": "mens", "components": [_component()],
        "scene_ids": ["commute"], "suitable_min": 0, "suitable_max": 40,
        "in_pool": True,
        "outfit_analysis": {
            "summary": "基础长袖保持简洁利落。",
            "structure_points": ["衣摆自然垂落"],
            "completion_advice": ["搭配直筒长裤补全下装"],
        },
    }
    outfit = client.post("/api/v1/outfits", json=outfit_payload).json()
    recommendation = client.post(
        "/api/v1/recommendations/preview",
        json={"apparent_min": 20, "apparent_max": 24, "scene": "commute", "audience": "mens"},
    )
    assert recommendation.status_code == 200
    assert recommendation.json()["source"] == "personal"
    assert recommendation.json()["template_id"] == outfit["id"]
    assert recommendation.json()["outfit_analysis"]["summary"] == "基础长袖保持简洁利落。"

    image = Image.new("RGB", (32, 48), "white")
    buffer = BytesIO()
    image.save(buffer, "PNG")
    upload = client.post(
        "/api/v1/inspirations/upload",
        data={"upload_key": "test-upload"},
        files={"image": ("look.png", buffer.getvalue(), "image/png")},
    )
    assert upload.status_code == 200
    inspiration_id = upload.json()["id"]
    analysis = client.post(f"/api/v1/inspirations/{inspiration_id}/analyze")
    assert analysis.json()["status"] == "needs_review"
    assert analysis.json()["result"]["components"][0]["color_name"] == "基础色"
    assert analysis.json()["result"]["components"][0].get("color_value") is None
    monkeypatch.setattr(OutfitAIService, "generate_name", _fake_ai_name)
    generated_name = client.post(f"/api/v1/inspirations/{inspiration_id}/generate-name")
    assert generated_name.json() == {"name": "黑灰层次通勤", "cached": False}
    cached_name = client.post(f"/api/v1/inspirations/{inspiration_id}/generate-name")
    assert cached_name.json() == {"name": "黑灰层次通勤", "cached": True}
    assert test_store.get_inspiration(inspiration_id, session_user_id(client))["result"]["ai_generated_name"] == "黑灰层次通勤"
    confirmed = client.post(
        f"/api/v1/inspirations/{inspiration_id}/confirm",
        json=outfit_payload | {"in_pool": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["source"] == "inspiration"
    assert confirmed.json()["outfit_analysis"]["completion_advice"] == ["搭配直筒长裤补全下装"]
    confirmed_again = client.post(
        f"/api/v1/inspirations/{inspiration_id}/confirm",
        json=outfit_payload | {"in_pool": False},
    )
    assert confirmed_again.status_code == 200
    assert confirmed_again.json()["id"] == confirmed.json()["id"]
    assert confirmed_again.json()["in_pool"] is True
    removed_from_personal_recommendations = client.post(
        f"/api/v1/outfits/{confirmed.json()['id']}/status", json={"in_pool": False}
    ).json()
    assert removed_from_personal_recommendations["in_pool"] is False
    assert confirmed.json()["id"] in {item["id"] for item in client.get("/api/v1/outfits").json()}
    assert confirmed.json()["id"] not in {item["id"] for item in client.get("/api/v1/outfits?in_pool=true").json()}
    client.post(
        f"/api/v1/outfits/{confirmed.json()['id']}/status", json={"in_pool": True}
    )
    personal_recommendation = client.post(
        "/api/v1/recommendations/preview",
        json={"apparent_min": 20, "apparent_max": 24, "scene": "commute", "audience": "mens"},
    )
    assert personal_recommendation.status_code == 200
    assert personal_recommendation.json()["source"] == "personal"
    assert personal_recommendation.json()["template_id"] == confirmed.json()["id"]
    assert personal_recommendation.json()["items"] == confirmed.json()["components"]

    notification = {"local_date": "2026-08-27", "message": "测试提醒"}
    first = client.post("/api/v1/notifications/test", json=notification).json()
    second = client.post("/api/v1/notifications/test", json=notification).json()
    assert not first["deduplicated"]
    assert second["deduplicated"]

    feedback = client.post(
        "/api/v1/feedback/comfort", json={"week_key": "2026-W35", "choice": "cold"}
    )
    assert feedback.json()["new_offset"] == -4

    skip = client.post(
        "/api/v1/feedback/skips", json={"outfit_id": outfit["id"], "local_date": "2026-08-27"}
    )
    assert skip.json()["skip_count"] == 1

    deleted = client.delete(f"/api/v1/outfits/{outfit['id']}")
    assert deleted.status_code == 200
    assert client.get(f"/api/v1/outfits/{outfit['id']}").status_code == 404


def session_user_id(client: TestClient) -> str:
    return client.get("/api/v1/auth/me").json()["user"]["id"]


def test_ai_name_is_trimmed_to_thirty_characters(monkeypatch) -> None:
    service = OutfitAIService()

    async def fake_call(prompt, recognition_result, max_tokens, model, fallback_model):
        return {"name": "“" + "春" * 35 + "”"}

    monkeypatch.setattr(service, "_call", fake_call)
    assert asyncio.run(service.generate_name({"components": [_component()]})) == "春" * 30


def test_ai_name_removes_legacy_sequence_suffix(monkeypatch) -> None:
    service = OutfitAIService()

    async def fake_call(prompt, recognition_result, max_tokens, model, fallback_model):
        return {"name": "蓝调层次通勤 03"}

    monkeypatch.setattr(service, "_call", fake_call)
    assert asyncio.run(service.generate_name({
        "components": [_component()], "suggested_scenes": ["commute"]
    })) == "蓝调层次通勤"


def test_ai_name_uses_style_plus_suggested_scene(monkeypatch) -> None:
    service = OutfitAIService()

    async def fake_call(prompt, recognition_result, max_tokens, model, fallback_model):
        return {"name": "黑灰通勤层次感"}

    monkeypatch.setattr(service, "_call", fake_call)
    assert asyncio.run(
        service.generate_name(
            {"components": [_component()], "suggested_scenes": ["commute", "travel"]}
        )
    ) == "黑灰通勤层次感"


def test_ai_name_keeps_the_models_valid_scene_choice(monkeypatch) -> None:
    service = OutfitAIService()

    async def fake_call(prompt, recognition_result, max_tokens, model, fallback_model):
        return {"name": "轻旅出行"}

    monkeypatch.setattr(service, "_call", fake_call)
    assert asyncio.run(
        service.generate_name(
            {"components": [_component()], "suggested_scenes": ["commute", "travel"]}
        )
    ) == "轻旅出行"


def test_ai_name_does_not_frame_commute_as_business(monkeypatch) -> None:
    service = OutfitAIService()

    async def fake_call(prompt, recognition_result, max_tokens, model, fallback_model):
        return {"name": "商务正装通勤"}

    monkeypatch.setattr(service, "_call", fake_call)
    assert asyncio.run(
        service.generate_name(
            {"components": [_component()], "suggested_scenes": ["commute"]}
        )
    ) == "日常通勤"


@pytest.mark.parametrize(
    ("audience", "raw_name", "expected"),
    [("mens", "温柔约会", "帅气约会"), ("womens", "硬汉约会", "精致约会")],
)
def test_ai_name_corrects_gender_incompatible_style(
    monkeypatch, audience: str, raw_name: str, expected: str
) -> None:
    service = OutfitAIService()

    async def fake_call(prompt, recognition_result, max_tokens, model, fallback_model):
        return {"name": raw_name}

    monkeypatch.setattr(service, "_call", fake_call)
    assert asyncio.run(
        service.generate_name(
            {
                "components": [_component()],
                "garment_audience": audience,
                "suggested_scenes": ["date"],
            }
        )
    ) == expected


def test_text_ai_retries_once_with_the_task_fallback_model(monkeypatch) -> None:
    monkeypatch.setenv("AI_API_URL", "https://example.test/v1")
    monkeypatch.setenv("AI_API_KEY", "test-key")
    monkeypatch.setenv("AI_FAST_MODEL", "qwen-turbo")
    monkeypatch.setenv("AI_QUALITY_MODEL", "qwen3.8-flash")
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    responses = [
        httpx.Response(429, request=request),
        httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": '{"name":"备用模型成功"}'}}]},
        ),
    ]
    called_models = []

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            called_models.append(kwargs["json"]["model"])
            return responses.pop(0)

    monkeypatch.setattr("app.services.outfit_ai_service.httpx.AsyncClient", FakeClient)
    service = OutfitAIService()
    result = asyncio.run(service.generate_name({"components": [_component()]}))

    assert result == "备用模型成功"
    assert called_models == ["qwen-turbo", "qwen3.8-flash"]


def test_realtime_text_tasks_use_fast_model_and_low_variance_items(monkeypatch) -> None:
    monkeypatch.setenv("AI_FAST_MODEL", "qwen-turbo")
    monkeypatch.setenv("AI_QUALITY_MODEL", "qwen3.8-flash")
    service = OutfitAIService()
    calls = []

    async def fake_call(prompt, content, max_tokens, model, fallback_model, temperature=0.7):
        calls.append((prompt, content, max_tokens, model, fallback_model, temperature))
        if prompt == service.items_prompt:
            return {
                "label": "适合通勤场景的清爽休闲穿搭",
                "items": [
                    {
                        "slot": "top",
                        "functional_icon_key": "short_sleeve",
                        "variant_type": "短袖 T 恤",
                        "color_name": "白色",
                        "thickness": "thin",
                    }
                ],
            }
        return {
            "replication_guide": {"formula": "短袖 T 恤", "steps": ["穿短袖 T 恤"]},
            "outfit_analysis": {"summary": "清爽基础搭配" * 20},
        }

    monkeypatch.setattr(service, "_call", fake_call)
    items_result = asyncio.run(service.generate_items({"scene": "commute", "audience": "mens"}))
    advice_result = asyncio.run(
        service.generate_advice(
            [],
            "晴，30°C",
            "commute",
            "mens",
            {"height_group": "偏高", "weight_group": "中等"},
        )
    )

    assert calls[0][0] == service.items_prompt
    assert calls[0][2:] == (650, "qwen-turbo", "qwen-turbo", 0.25)
    assert calls[0][1] == {"scene": "commute", "audience": "mens"}
    assert calls[1][1]["scene_name"] == "通勤"
    assert calls[1][1]["person_profile"] == {
        "height_group": "偏高", "weight_group": "中等",
    }
    assert calls[1][3:5] == ("qwen-turbo", "qwen3.8-flash")
    assert items_result["label"] == "适合通勤场景的清"
    assert items_result["replication_guide"] is None
    assert items_result["outfit_analysis"] is None
    assert items_result["prompt_version"] == "wearcue-realtime-plan-v3.2"
    assert advice_result["replication_guide"]["styling_points"][:2] == [
        "保留完整纵向线条，衣袖和裤长避免偏短；采用合身但不紧绷的常规松量。",
        "细节可保持简洁轻快，同时兼顾当前场景的得体度。",
    ]
    assert advice_result["outfit_analysis"]["summary"] == "清爽基础搭配" * 20
    assert "replication_guide.steps 必须逐件覆盖 items" in service.advice_prompt
    assert "outfit_dna" in service.advice_prompt
    assert "思考过程、详情文案和图片" in service.items_prompt
    assert "中年商务男装目录" in service.items_prompt
    assert "必须消费同一份 outfit_dna" in service.prompt
    assert "locked_features" in service.prompt


def test_realtime_items_have_a_hard_total_timeout(monkeypatch) -> None:
    monkeypatch.setenv("AI_REALTIME_TIMEOUT_SECONDS", "0.01")
    service = OutfitAIService()

    async def slow_call(*args, **kwargs):
        await asyncio.sleep(0.1)
        return {"items": []}

    monkeypatch.setattr(service, "_call", slow_call)

    with pytest.raises(OutfitAIServiceError, match="响应超时"):
        asyncio.run(service.generate_items({"scene": "commute", "audience": "mens"}))


@pytest.mark.parametrize(
    ("scene", "audience"),
    [
        ("commute", "mens"),
        ("commute", "womens"),
        ("date", "mens"),
        ("date", "womens"),
        ("travel", "mens"),
        ("travel", "womens"),
    ],
)
def test_realtime_prompt_keeps_scene_and_audience_without_long_context(
    monkeypatch, scene: str, audience: str
) -> None:
    service = OutfitAIService()
    captured = {}

    async def fake_call(prompt, content, max_tokens, model, fallback_model, temperature=0.7):
        captured.update(content)
        return {
            "label": "场景穿搭",
            "items": [{"slot": "top", "functional_icon_key": "short_sleeve"}],
        }

    monkeypatch.setattr(service, "_call", fake_call)
    asyncio.run(service.generate_items({"scene": scene, "audience": audience}))

    assert captured["scene"] == scene
    assert captured["audience"] == audience
    assert "scene_requirements" not in captured


def test_all_scenes_have_distinct_mens_and_womens_requirements() -> None:
    from app.services.outfit_ai_service import scene_context_for

    requirements = {
        (scene, audience): scene_context_for(scene, audience)["scene_requirements"]
        for scene in ("commute", "date", "travel")
        for audience in ("mens", "womens")
    }

    assert len(set(requirements.values())) == 6
    assert all("男士" in requirements[(scene, "mens")] for scene in ("commute", "date", "travel"))
    assert all("女士" in requirements[(scene, "womens")] for scene in ("commute", "date", "travel"))


def test_generated_commute_rejects_business_clothing(monkeypatch) -> None:
    service = OutfitAIService()

    async def fake_call(prompt, content, max_tokens, model, fallback_model, temperature=0.7):
        return {
            "label": "商务通勤",
            "items": [
                {
                    "slot": "bottom",
                    "functional_icon_key": "long_bottom",
                    "variant_type": "直筒西裤",
                }
            ],
        }

    monkeypatch.setattr(service, "_call", fake_call)
    with pytest.raises(OutfitAIServiceError, match="商务正装元素"):
        asyncio.run(service.generate_items({"scene": "commute", "audience": "mens"}))


@pytest.mark.parametrize(
    ("audience", "label"),
    [("mens", "温柔约会"), ("womens", "硬汉约会")],
)
def test_generated_style_rejects_wrong_gender_words(monkeypatch, audience: str, label: str) -> None:
    service = OutfitAIService()

    async def fake_call(prompt, content, max_tokens, model, fallback_model, temperature=0.7):
        return {
            "label": label,
            "items": [{"slot": "top", "functional_icon_key": "short_sleeve"}],
        }

    monkeypatch.setattr(service, "_call", fake_call)
    with pytest.raises(OutfitAIServiceError, match="性别不一致"):
        asyncio.run(service.generate_items({"scene": "date", "audience": audience}))


@pytest.mark.parametrize(
    ("scene", "requirement_start", "keyword"),
    [
        ("commute", "中国语境下的男士通勤", "严禁主动生成"),
        ("travel", "男士出行", "轻机能"),
    ],
)
def test_outfit_image_receives_scene_context(
    monkeypatch, scene: str, requirement_start: str, keyword: str
) -> None:
    monkeypatch.setenv("AI_IMAGE_API_URL", "https://example.com/v1")
    monkeypatch.setenv("AI_API_KEY", "test-key")
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [{"b64_json": "aW1hZ2U="}]}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            captured.update(kwargs["json"])
            return FakeResponse()

    monkeypatch.setattr("app.services.outfit_image_service.httpx.AsyncClient", FakeClient)
    service = OutfitImageService()
    asyncio.run(
        service.generate(
            "场景穿搭",
            "mens",
            scene,
            [_component()],
            {},
            {"height_group": "中等", "weight_group": "中等"},
            style_tags=["sport"],
        )
    )

    assert f"场景约束：{requirement_start}" in captured["prompt"]
    assert keyword in captured["prompt"]
    assert "主风格：sport" in captured["prompt"]
    assert "中年商务男装目录" in captured["prompt"]
    assert "完整结构化输入" not in captured["prompt"]


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://cdn.example.com/outfit.png", True),
        ("https://8.8.8.8/outfit.png", True),
        ("http://cdn.example.com/outfit.png", False),
        ("https://localhost/outfit.png", False),
        ("https://127.0.0.1/outfit.png", False),
        ("https://10.0.0.1/outfit.png", False),
        ("file:///tmp/outfit.png", False),
    ],
)
def test_generated_image_url_requires_public_https(url: str, expected: bool) -> None:
    assert safe_image_url(url) is expected


@pytest.mark.parametrize(
    ("scene", "raw_label", "expected"),
    [("commute", "清爽通勤风", "清爽通勤风"), ("date", "清爽约会风", "精致约会"), ("travel", "清爽出行装", "舒适出行")],
)
def test_generic_weather_labels_are_not_reused_across_scenes(
    monkeypatch, scene: str, raw_label: str, expected: str
) -> None:
    service = OutfitAIService()

    async def fake_call(prompt, content, max_tokens, model, fallback_model, temperature=0.7):
        return {
            "label": raw_label,
            "items": [{"slot": "top", "functional_icon_key": "short_sleeve"}],
        }

    monkeypatch.setattr(service, "_call", fake_call)
    expected_for_audience = "帅气约会" if scene == "date" else "活力出行" if scene == "travel" else expected
    assert asyncio.run(service.generate_items({"scene": scene, "audience": "mens"}))["label"] == expected_for_audience


def test_realtime_outfit_label_removes_sequence_suffix(monkeypatch) -> None:
    service = OutfitAIService()

    async def fake_call(prompt, content, max_tokens, model, fallback_model, temperature=0.7):
        return {
            "label": "蓝调运动通勤 02",
            "items": [{"slot": "top", "functional_icon_key": "short_sleeve"}],
        }

    monkeypatch.setattr(service, "_call", fake_call)
    result = asyncio.run(service.generate_items({"scene": "commute", "audience": "mens"}))
    assert result["label"] == "蓝调运动通勤"


def test_text_ai_does_not_change_models_for_auth_errors(monkeypatch) -> None:
    monkeypatch.setenv("AI_API_URL", "https://example.test/v1")
    monkeypatch.setenv("AI_API_KEY", "bad-key")
    monkeypatch.setenv("AI_FAST_MODEL", "qwen-turbo")
    monkeypatch.setenv("AI_QUALITY_MODEL", "qwen3.8-flash")
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    called_models = []

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            called_models.append(kwargs["json"]["model"])
            return httpx.Response(401, request=request)

    monkeypatch.setattr("app.services.outfit_ai_service.httpx.AsyncClient", FakeClient)

    with pytest.raises(OutfitAIServiceError):
        asyncio.run(OutfitAIService().generate_name({"components": [_component()]}))

    assert called_models == ["qwen-turbo"]


def test_vision_ai_does_not_call_an_unconfigured_fallback(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("VISION_API_URL", "https://example.test/v1")
    monkeypatch.setenv("VISION_API_KEY", "test-key")
    monkeypatch.setenv("VISION_MODEL", "qwen3.8-flash")
    monkeypatch.setenv("VISION_FALLBACK_MODEL", "")
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    responses = [httpx.Response(503, request=request)]
    called_models = []

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            called_models.append(kwargs["json"]["model"])
            return responses.pop(0)

    monkeypatch.setattr("app.services.vision_service.httpx.AsyncClient", FakeClient)
    image_path = tmp_path / "outfit.jpg"
    image_path.write_bytes(b"test-image")

    with pytest.raises(VisionServiceError):
        asyncio.run(VisionService().analyze(image_path))

    assert called_models == ["qwen3.8-flash"]


def test_upload_rejects_fake_image(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path)
    client = _client(test_store, monkeypatch)
    response = client.post(
        "/api/v1/inspirations/upload",
        files={"image": ("fake.png", b"not an image", "image/png")},
    )
    assert response.status_code == 415


def test_upload_rejects_image_over_five_megabytes(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path)
    client = _client(test_store, monkeypatch)
    oversized = b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024)

    response = client.post(
        "/api/v1/inspirations/upload",
        files={"image": ("large.png", oversized, "image/png")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["message"] == "图片不能超过 5 MB"


def test_image_recognition_is_limited_to_thirty_successes_per_day(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path)
    client = _client(test_store, monkeypatch)
    monkeypatch.setattr(VisionService, "analyze", _fake_vision_analyze)
    image = Image.new("RGB", (24, 36), "white")
    buffer = BytesIO()
    image.save(buffer, "PNG")
    upload = client.post(
        "/api/v1/inspirations/upload",
        files={"image": ("quota.png", buffer.getvalue(), "image/png")},
    )
    inspiration_id = upload.json()["id"]

    for expected_remaining in range(29, -1, -1):
        response = client.post(f"/api/v1/inspirations/{inspiration_id}/analyze")
        assert response.status_code == 200
        assert response.json()["remaining_analyses"] == expected_remaining

    exhausted = client.post(f"/api/v1/inspirations/{inspiration_id}/analyze")
    assert exhausted.status_code == 429
    assert client.get("/api/v1/inspirations/analysis-quota").json() == {
        "limit": 30,
        "used": 30,
        "remaining": 0,
    }


def test_ai_usage_quotas_are_independent_and_non_ai_swaps_remain_available(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path)
    client = _client(test_store, monkeypatch)
    monkeypatch.setattr(OutfitAIService, "generate_items", _fake_ai_items)
    monkeypatch.setattr(OutfitAIService, "generate_advice", _fake_ai_advice)
    monkeypatch.setattr(OutfitImageService, "generate", _fake_outfit_image)
    monkeypatch.setattr(recommendation_service, "system_ai_templates", lambda: [])
    monkeypatch.setattr(system, "recommend_system_outfit", lambda **kwargs: None)

    initial_quota = client.get("/api/v1/ai-usage-quota").json()
    assert initial_quota["vision"]["remaining"] == 30
    assert initial_quota["swap"]["remaining"] == 4
    assert initial_quota["advice"]["remaining"] == 4

    for expected_remaining in (3, 2, 1, 0):
        response = client.post("/api/v1/recommendations/swap", json=_recommendation_payload())
        assert response.status_code == 200
        assert response.json()["source"] == "ai"
        assert response.json()["ai_quota"]["remaining"] == expected_remaining

    response = client.post("/api/v1/recommendations/swap", json=_recommendation_payload())
    assert response.status_code == 429

    after_swaps = client.get("/api/v1/ai-usage-quota").json()
    assert after_swaps["vision"]["remaining"] == 30
    assert after_swaps["advice"]["remaining"] == 4

    advice_payload = {
        "recommendation_id": "ai-advice-0",
        "scene": "commute",
        "audience": "mens",
        "items": [_component()],
        "constraints": {"calibrated_apparent_min": 20},
    }
    for expected_remaining in (3, 2, 1, 0):
        response = client.post(
            "/api/v1/recommendations/advice",
            json=advice_payload | {"recommendation_id": f"ai-advice-{expected_remaining}"},
        )
        assert response.status_code == 200
        assert response.json()["ai_quota"]["remaining"] == expected_remaining

    exhausted = client.post(
        "/api/v1/recommendations/advice",
        json=advice_payload | {"recommendation_id": "ai-advice-exhausted"},
    )
    assert exhausted.status_code == 429
    assert client.get("/api/v1/ai-usage-quota").json()["vision"]["remaining"] == 30


def test_live_swap_only_generates_icon_mapped_plan_not_detail_image(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path)
    client = _client(test_store, monkeypatch)
    image_calls = 0

    async def unexpected_image(*args, **kwargs):
        nonlocal image_calls
        image_calls += 1
        return await _fake_outfit_image(*args, **kwargs)

    monkeypatch.setattr(OutfitAIService, "generate_items", _fake_ai_items)
    monkeypatch.setattr(OutfitImageService, "generate", unexpected_image)
    monkeypatch.setattr(recommendation_service, "system_ai_templates", lambda: [])
    monkeypatch.setattr(system, "recommend_system_outfit", lambda **kwargs: None)

    response = client.post("/api/v1/recommendations/swap", json=_recommendation_payload())

    assert response.status_code == 200
    assert response.json()["source"] == "ai"
    assert response.json()["items"]
    assert image_calls == 0


def test_reopening_same_ai_detail_reuses_advice_without_charging_again(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path)
    client = _client(test_store, monkeypatch)
    client.post(
        "/api/v1/settings",
        json={"height_group": "偏高", "weight_group": "偏重"},
    )
    calls = 0

    captured_advice_profile = {}

    async def count_advice(self, items, weather_summary, scene, audience, person_profile, *metadata):
        nonlocal calls
        calls += 1
        captured_advice_profile.update(person_profile)
        return await _fake_ai_advice(
            self, items, weather_summary, scene, audience, person_profile
        )

    monkeypatch.setattr(OutfitAIService, "generate_advice", count_advice)
    image_calls = 0

    captured_profile = {}

    async def count_image(self, label, audience, scene, items, constraints, person_profile, *metadata):
        nonlocal image_calls
        image_calls += 1
        captured_profile.update(person_profile)
        return await _fake_outfit_image(
            self, label, audience, scene, items, constraints, person_profile
        )

    monkeypatch.setattr(OutfitImageService, "generate", count_image)
    payload = {
        "recommendation_id": "ai-reopen-detail",
        "scene": "commute",
        "audience": "mens",
        "items": [_component()],
        "constraints": {"calibrated_apparent_min": 20},
    }

    first = client.post("/api/v1/recommendations/advice", json=payload)
    reopened = client.post("/api/v1/recommendations/advice", json=payload)

    assert first.json()["cached"] is False
    assert reopened.json()["cached"] is True
    assert reopened.json()["replication_guide"] == first.json()["replication_guide"]
    assert reopened.json()["outfit_analysis"] == first.json()["outfit_analysis"]
    assert reopened.json()["image_url"] == first.json()["image_url"]
    assert client.get(reopened.json()["image_url"].replace("/recommendations", "/api/v1/recommendations")).status_code == 200
    assert reopened.json()["ai_quota"]["remaining"] == 3
    assert calls == 1
    assert image_calls == 1
    assert captured_profile == {
        "height_group": "偏高", "weight_group": "偏重",
    }
    assert captured_advice_profile == captured_profile


def test_detail_cache_changes_with_current_profile(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path)
    client = _client(test_store, monkeypatch)
    advice_calls = 0
    image_calls = 0

    async def count_advice(self, items, weather_summary, scene, audience, person_profile, *metadata):
        nonlocal advice_calls
        advice_calls += 1
        return await _fake_ai_advice(
            self, items, weather_summary, scene, audience, person_profile
        )

    async def count_image(self, label, audience, scene, items, constraints, person_profile, *metadata):
        nonlocal image_calls
        image_calls += 1
        return await _fake_outfit_image(
            self, label, audience, scene, items, constraints, person_profile
        )

    monkeypatch.setattr(OutfitAIService, "generate_advice", count_advice)
    monkeypatch.setattr(OutfitImageService, "generate", count_image)
    payload = {
        "recommendation_id": "profile-sensitive-detail",
        "scene": "commute",
        "items": [_component()],
        "constraints": {"calibrated_apparent_min": 20},
    }

    first = client.post("/api/v1/recommendations/advice", json=payload)
    client.post("/api/v1/settings", json={"height_group": "偏高"})
    changed = client.post("/api/v1/recommendations/advice", json=payload)

    assert first.status_code == changed.status_code == 200
    assert first.json()["image_url"] != changed.json()["image_url"]
    assert changed.json()["cached"] is False
    assert changed.json()["ai_quota"]["remaining"] == 2
    assert advice_calls == image_calls == 2


def test_detail_ai_reads_current_account_gender_scene_and_profile(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path)
    client = _client(test_store, monkeypatch, audience="womens")
    client.post(
        "/api/v1/settings",
        json={"height_group": "偏矮", "weight_group": "偏轻"},
    )
    captured = {}

    async def capture_advice(self, items, weather_summary, scene, audience, person_profile, *metadata):
        captured["advice"] = (scene, audience, person_profile)
        return await _fake_ai_advice(
            self, items, weather_summary, scene, audience, person_profile
        )

    async def capture_image(self, label, audience, scene, items, constraints, person_profile, *metadata):
        captured["image"] = (scene, audience, person_profile)
        return await _fake_outfit_image(
            self, label, audience, scene, items, constraints, person_profile
        )

    monkeypatch.setattr(OutfitAIService, "generate_advice", capture_advice)
    monkeypatch.setattr(OutfitImageService, "generate", capture_image)
    response = client.post(
        "/api/v1/recommendations/advice",
        json={
            "recommendation_id": "current-settings-detail",
            "scene": "date",
            "items": [_component()],
            "constraints": {"calibrated_apparent_min": 20},
        },
    )

    assert response.status_code == 200
    expected = ("date", "womens", {"height_group": "偏矮", "weight_group": "偏轻"})
    assert captured == {"advice": expected, "image": expected}


def test_weather_and_removed_diagnostic_routes_are_not_public() -> None:
    client = TestClient(app)

    assert client.get("/api/v1/cities?q=北京").status_code == 401
    assert client.get(
        "/api/v1/weather/today?latitude=39.9&longitude=116.4&city=北京"
    ).status_code == 401
    assert client.get("/api/v1/capabilities").status_code == 404
    assert client.get("/api/v1/runtime-status").status_code == 404
    assert client.post("/api/v1/rules/evaluate", json={}).status_code == 404


def test_failed_live_ai_swap_releases_quota(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path)
    client = _client(test_store, monkeypatch)

    async def fail_items(self, context):
        raise OutfitAIServiceError("模型暂时不可用")

    monkeypatch.setattr(OutfitAIService, "generate_items", fail_items)
    monkeypatch.setattr(recommendation_service, "system_ai_templates", lambda: [])
    monkeypatch.setattr(system, "recommend_system_outfit", lambda **kwargs: None)
    response = client.post("/api/v1/recommendations/swap", json=_recommendation_payload())

    assert response.status_code == 503
    assert client.get("/api/v1/ai-usage-quota").json()["swap"]["remaining"] == 4


def test_failed_live_ai_swap_returns_immediate_template_when_available(
    tmp_path, monkeypatch
) -> None:
    test_store = Store(tmp_path)
    client = _client(test_store, monkeypatch)

    async def fail_items(self, context):
        raise OutfitAIServiceError("模型暂时不可用")

    monkeypatch.setattr(OutfitAIService, "generate_items", fail_items)
    monkeypatch.setattr(recommendation_service, "system_ai_templates", lambda: [])
    monkeypatch.setattr(system, "recommend_system_outfit", lambda **kwargs: None)
    monkeypatch.setattr(
        system,
        "_provider_failure_fallback",
        lambda payload, weather, audience: {
            "source": "system",
            "template_id": "fast-local-fallback",
            "label": "即时备用穿搭",
            "scene": payload.scene,
            "audience": audience,
            "items": [_component()],
            "ai_fallback_reason": "provider_failed",
        },
    )

    response = client.post("/api/v1/recommendations/swap", json=_recommendation_payload())

    assert response.status_code == 200
    assert response.json()["template_id"] == "fast-local-fallback"
    assert response.json()["ai_fallback_reason"] == "provider_failed"
    assert response.json()["ai_quota"]["remaining"] == 4


def test_ai_quota_reservation_is_atomic(tmp_path) -> None:
    test_store = Store(tmp_path)
    local_date = user_local_date("Asia/Shanghai")

    with ThreadPoolExecutor(max_workers=12) as executor:
        reservations = list(
            executor.map(
                lambda _: test_store.reserve_ai_usage("concurrent-user", local_date, "swap"),
                range(24),
            )
        )

    assert sum(reservation is not None for reservation in reservations) == 4
    assert test_store.get_ai_quota("concurrent-user", local_date, "swap")["remaining"] == 0


def test_new_account_library_starts_with_matching_ai_example(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path)
    client = _client(test_store, monkeypatch)

    mens = client.get("/api/v1/outfits").json()
    assert len(mens) == 25
    sample = next(item for item in mens if item["label"] == "都市层次出行")
    assert sample["source"] == "system"
    assert sample["audience"] == "mens"
    assert sample["season"] == "winter"
    assert sample["style_tags"] == ["outdoor", "minimal"]
    assert sample["in_pool"] is False
    assert len(client.get("/api/v1/inspirations").json()) == 1
    assert client.get(f"/api/v1/inspirations/{sample['inspiration_id']}/image").status_code == 200
    padded = next(item for item in mens if item["id"] == "system-042-6c4d312c")
    assert padded["label"] == "灰调飞行夹克通勤"
    assert padded["season"] == "winter"
    assert (padded["suitable_min"], padded["suitable_max"]) == (0, 10)

    old_mens = client.post(
        "/api/v1/outfits",
        json={
            "label": "切换角色前的男装", "audience": "mens",
            "components": [_component()], "scene_ids": ["commute"],
            "season": "spring-autumn", "style_tags": ["minimal"],
            "suitable_min": 15, "suitable_max": 28,
        },
    ).json()
    assert old_mens["id"] in {item["id"] for item in client.get("/api/v1/outfits").json()}

    client.post("/api/v1/settings", json={"audience": "womens"})
    womens = client.get("/api/v1/outfits").json()
    assert len(womens) == 23
    assert old_mens["id"] not in {item["id"] for item in womens}
    assert all(item["audience"] == "womens" for item in womens)
    sample = next(item for item in womens if item["label"] == "条纹休闲出行")
    assert sample["source"] == "system"
    assert sample["audience"] == "womens"
    assert sample["season"] == "summer"
    assert sample["style_tags"] == ["sport"]
    light_date = next(item for item in womens if item["id"] == "system-017-f6b839c6")
    assert light_date["label"] == "白衬衫松弛约会"
    assert light_date["season"] == "summer"
    assert (light_date["suitable_min"], light_date["suitable_max"]) == (22, 30)
    active_travel = next(item for item in womens if item["id"] == "system-018-bc107caa")
    assert active_travel["label"] == "蓝调运动出行"
    assert active_travel["season"] == "summer"
    assert (active_travel["suitable_min"], active_travel["suitable_max"]) == (20, 28)


def test_outfit_without_upload_reuses_existing_audience_example_image(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path)
    client = _client(test_store, monkeypatch)

    created = client.post(
        "/api/v1/outfits",
        json={"label": "夏日通勤清爽", "audience": "mens", "components": [_component()]},
    )

    assert created.status_code == 200
    merged = created.json()
    image_url = merged["image_url"]
    assert image_url.startswith("/inspirations/")
    assert merged["label"] == "都市层次出行"
    assert merged["season"] == "winter"
    assert merged["style_tags"] == ["outdoor", "minimal"]
    assert client.get(f"/api/v1{image_url}").status_code == 200

    all_outfits = client.get("/api/v1/outfits").json()
    assert len(all_outfits) == 25
    assert any(item["id"] == merged["id"] for item in all_outfits)
    assert not any(item["id"].startswith("example_mens_") for item in all_outfits)
    assert not any(
        item["id"] == merged["id"]
        for item in client.get("/api/v1/outfits?season=summer").json()
    )
    assert any(
        item["id"] == merged["id"]
        for item in client.get("/api/v1/outfits?season=winter").json()
    )


def test_system_asset_metadata_is_refreshed_from_manifest(tmp_path) -> None:
    test_store = Store(tmp_path)
    outfit_id = "system-042-6c4d312c"
    with test_store.connect() as db:
        db.execute(
            "UPDATE outfits SET label=?,season=?,suitable_min=?,suitable_max=? WHERE id=?",
            ("春秋简约通勤 06", "spring-autumn", 8, 18, outfit_id),
        )

    refreshed = Store(tmp_path).get_outfit(outfit_id)
    assert refreshed is not None
    assert refreshed["label"] == "灰调飞行夹克通勤"
    assert refreshed["season"] == "winter"
    assert (refreshed["suitable_min"], refreshed["suitable_max"]) == (0, 10)


def test_discovery_filters_mine_favorite_and_user_scoped_system_delete(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path)
    client = _client(test_store, monkeypatch)
    system_outfit = next(
        item for item in client.get("/api/v1/outfits").json()
        if item["id"].startswith("system-")
    )

    filtered = client.get(
        "/api/v1/outfits",
        params={
            "season": system_outfit["season"],
            "scene": system_outfit["scene_ids"][0],
            "style": system_outfit["style_tags"][0],
        },
    ).json()
    assert system_outfit["id"] in {item["id"] for item in filtered}
    assert all(item["season"] == system_outfit["season"] for item in filtered)
    assert all(system_outfit["scene_ids"][0] in item["scene_ids"] for item in filtered)
    assert all(system_outfit["style_tags"][0] in item["style_tags"] for item in filtered)

    favorite = client.post(
        f"/api/v1/outfits/{system_outfit['id']}/status", json={"favorite": True}
    )
    assert favorite.status_code == 200
    assert favorite.json()["favorite"] is True
    assert favorite.json()["in_pool"] is True
    mine = client.get("/api/v1/outfits", params={"tab": "mine"}).json()
    assert system_outfit["id"] in {item["id"] for item in mine}

    unfavorite = client.post(
        f"/api/v1/outfits/{system_outfit['id']}/status", json={"favorite": False}
    )
    assert unfavorite.json()["in_pool"] is False
    mine = client.get("/api/v1/outfits", params={"tab": "mine"}).json()
    assert system_outfit["id"] not in {item["id"] for item in mine}
    deleted = client.delete(f"/api/v1/outfits/{system_outfit['id']}")
    assert deleted.status_code == 200
    assert system_outfit["id"] not in {
        item["id"] for item in client.get("/api/v1/outfits").json()
    }
    assert test_store.get_outfit(system_outfit["id"], "another-user") is not None

    manual = client.post(
        "/api/v1/outfits",
        json={
            "label": "夏季运动约会",
            "audience": "mens",
            "components": [_component()],
            "scene_ids": ["date"],
            "season": "summer",
            "style_tags": ["sport", "minimal"],
            "suitable_min": 24,
            "suitable_max": 35,
        },
    ).json()
    result = client.get(
        "/api/v1/outfits",
        params={"tab": "mine", "season": "summer", "scene": "date", "style": "sport"},
    ).json()
    assert [item["id"] for item in result] == [manual["id"]]


def test_confirmed_upload_enters_personal_home_pool(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path)
    client = _client(test_store, monkeypatch)
    monkeypatch.setattr(VisionService, "analyze", _fake_vision_analyze)
    image = Image.new("RGB", (32, 48), "white")
    buffer = BytesIO()
    image.save(buffer, "PNG")
    uploaded = client.post(
        "/api/v1/inspirations/upload",
        files={"image": ("look.png", buffer.getvalue(), "image/png")},
    ).json()
    assert client.post(f"/api/v1/inspirations/{uploaded['id']}/analyze").status_code == 200
    confirmed = client.post(
        f"/api/v1/inspirations/{uploaded['id']}/confirm",
        json={
            "label": "识别穿搭",
            "audience": "mens",
            "components": [_component()],
            "scene_ids": ["travel"],
            "season": "spring-autumn",
            "style_tags": ["minimal"],
            "suitable_min": 15,
            "suitable_max": 28,
            "in_pool": False,
        },
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["in_pool"] is True


def test_home_recommendation_uses_personal_system_ai_layers(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path)
    client = _client(test_store, monkeypatch)
    monkeypatch.setattr(OutfitAIService, "generate_items", _fake_ai_items)
    personal = client.post(
        "/api/v1/outfits",
        json={
            "label": "我的通勤",
            "audience": "mens",
            "components": [_component()],
            "scene_ids": ["commute"],
            "season": "spring-autumn",
            "style_tags": ["minimal"],
            "suitable_min": 15,
            "suitable_max": 28,
            "in_pool": True,
        },
    ).json()
    first = client.post("/api/v1/recommendations/swap", json=_recommendation_payload()).json()
    assert first["source"] == "personal"
    assert first["template_id"] == personal["id"]

    client.post(f"/api/v1/outfits/{personal['id']}/status", json={"in_pool": False})
    second = client.post("/api/v1/recommendations/swap", json=_recommendation_payload()).json()
    assert second["source"] == "system"
    assert second["outfit_analysis"]["summary"]
    assert second["replication_guide"]["steps"]
    assert second["season"]
    assert second["style_tags"]

    monkeypatch.setattr(recommendation_service, "system_ai_templates", lambda: [])
    monkeypatch.setattr(system, "recommend_system_outfit", lambda **kwargs: None)
    third = client.post(
        "/api/v1/recommendations/swap",
        json=_recommendation_payload() | {"excluded_template_ids": [second["template_id"]]},
    ).json()
    assert third["source"] == "ai"
