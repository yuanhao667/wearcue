import asyncio
import json
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
from app.services.outfit_ai_service import OutfitAIService, OutfitAIServiceError
from app.services.outfit_image_service import OutfitImageService
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


async def _fake_ai_advice(self, items, weather_summary, scene, audience, person_profile):
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


async def _fake_outfit_image(self, label, audience, scene, items, constraints, person_profile):
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
    session = test_store.login("TEST-INVITE", "测试", audience)
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


def test_ai_name_uses_style_plus_suggested_scene(monkeypatch) -> None:
    service = OutfitAIService()

    async def fake_call(prompt, recognition_result, max_tokens, model, fallback_model):
        return {"name": "黑灰通勤层次感"}

    monkeypatch.setattr(service, "_call", fake_call)
    assert asyncio.run(
        service.generate_name(
            {"components": [_component()], "suggested_scenes": ["commute", "travel"]}
        )
    ) == "黑灰层次感通勤"


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
    items_result = asyncio.run(service.generate_items({"scene": "commute"}))
    advice_result = asyncio.run(
        service.generate_advice(
            [],
            "晴，30°C",
            "commute",
            "mens",
            {"height_group": "偏高", "weight_group": "中等"},
        )
    )

    assert calls[0][2:] == (500, "qwen-turbo", "qwen3.8-flash", 0.2)
    assert calls[0][1]["scene_name"] == "通勤"
    assert calls[0][1]["scene_requirements"].startswith("优先轻松自然")
    assert "传统商务正装" in calls[0][1]["scene_requirements"]
    assert calls[1][1]["scene_name"] == "通勤"
    assert calls[1][1]["person_profile"] == {
        "height_group": "偏高", "weight_group": "中等",
    }
    assert calls[1][3:5] == ("qwen-turbo", "qwen3.8-flash")
    assert items_result["label"] == "适合通勤场景的清"
    assert advice_result["replication_guide"]["styling_points"][:2] == [
        "保留完整纵向线条，衣袖和裤长避免偏短；采用合身但不紧绷的常规松量。",
        "细节可保持简洁轻快，同时兼顾当前场景的得体度。",
    ]
    assert advice_result["outfit_analysis"]["summary"] == "清爽基础搭配" * 20


@pytest.mark.parametrize(
    ("scene", "scene_name", "keyword"),
    [("commute", "通勤", "轻松自然"), ("date", "约会", "清爽约会"), ("travel", "出行", "轻机能")],
)
def test_all_user_selected_scenes_are_expanded_for_ai(
    monkeypatch, scene: str, scene_name: str, keyword: str
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
    asyncio.run(service.generate_items({"scene": scene}))

    assert captured["scene"] == scene
    assert captured["scene_name"] == scene_name
    assert keyword in captured["scene_requirements"]


@pytest.mark.parametrize(
    ("scene", "requirement_start", "keyword"),
    [
        ("commute", "优先轻松自然", "传统商务正装"),
        ("travel", "优先舒适", "轻机能"),
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
        )
    )

    assert f"场景风格要求：{requirement_start}" in captured["prompt"]
    assert keyword in captured["prompt"]
    assert f'"风格侧重点": "{requirement_start}' in captured["prompt"]


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
    assert asyncio.run(service.generate_items({"scene": scene}))["label"] == expected


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

    initial_quota = client.get("/api/v1/ai-usage-quota").json()
    assert initial_quota["vision"]["remaining"] == 30
    assert initial_quota["swap"]["remaining"] == 4
    assert initial_quota["advice"]["remaining"] == 4

    for expected_remaining in (3, 2, 1, 0):
        response = client.post("/api/v1/recommendations/swap", json=_recommendation_payload())
        assert response.status_code == 200
        assert response.json()["source"] == "ai"
        assert response.json()["ai_quota"]["remaining"] == expected_remaining

    for _ in range(3):
        response = client.post("/api/v1/recommendations/swap", json=_recommendation_payload())
        assert response.status_code == 200
        assert response.json()["source"] != "ai"
        assert response.json()["ai_fallback_reason"] == "quota_exhausted"
        assert response.json()["ai_quota"]["remaining"] == 0

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


def test_reopening_same_ai_detail_reuses_advice_without_charging_again(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path)
    client = _client(test_store, monkeypatch)
    client.post(
        "/api/v1/settings",
        json={"height_group": "偏高", "weight_group": "偏重"},
    )
    calls = 0

    captured_advice_profile = {}

    async def count_advice(self, items, weather_summary, scene, audience, person_profile):
        nonlocal calls
        calls += 1
        captured_advice_profile.update(person_profile)
        return await _fake_ai_advice(
            self, items, weather_summary, scene, audience, person_profile
        )

    monkeypatch.setattr(OutfitAIService, "generate_advice", count_advice)
    image_calls = 0

    captured_profile = {}

    async def count_image(self, label, audience, scene, items, constraints, person_profile):
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


def test_failed_live_ai_swap_releases_quota(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path)
    client = _client(test_store, monkeypatch)

    async def fail_items(self, context):
        raise OutfitAIServiceError("模型暂时不可用")

    monkeypatch.setattr(OutfitAIService, "generate_items", fail_items)
    response = client.post("/api/v1/recommendations/swap", json=_recommendation_payload())

    assert response.status_code == 200
    assert response.json()["source"] != "ai"
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
    assert len(mens) == 1
    assert mens[0]["source"] == "system"
    assert mens[0]["audience"] == "mens"
    assert mens[0]["label"] == "都市层次出行"
    assert mens[0]["in_pool"] is False
    assert len(client.get("/api/v1/inspirations").json()) == 1
    assert client.get(f"/api/v1/inspirations/{mens[0]['inspiration_id']}/image").status_code == 200

    client.post("/api/v1/settings", json={"audience": "womens"})
    womens = client.get("/api/v1/outfits").json()
    assert len(womens) == 1
    assert womens[0]["source"] == "system"
    assert womens[0]["audience"] == "womens"
    assert womens[0]["label"] == "条纹休闲出行"
