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


async def _fake_ai_advice(self, items, weather_summary, scene, audience):
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
    test_store = Store(tmp_path, seed_defaults=False)
    client = _client(test_store, monkeypatch)
    monkeypatch.setattr(VisionService, "analyze", _fake_vision_analyze)

    settings = client.post("/api/v1/settings", json={"audience": "mens", "cold_offset": -2})
    assert settings.status_code == 200
    assert settings.json()["cold_offset"] == -2

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
    advice_result = asyncio.run(service.generate_advice([], "晴，30°C", "commute", "mens"))

    assert calls[0][2:] == (500, "qwen-turbo", "qwen3.8-flash", 0.2)
    assert calls[0][1]["scene_name"] == "通勤"
    assert calls[0][1]["scene_requirements"].startswith("优先得体利落")
    assert calls[1][1]["scene_name"] == "通勤"
    assert calls[1][3:5] == ("qwen-turbo", "qwen3.8-flash")
    assert items_result["label"] == "适合通勤场景的清"
    assert advice_result["outfit_analysis"]["summary"] == "清爽基础搭配" * 20


@pytest.mark.parametrize(
    ("scene", "scene_name", "keyword"),
    [("commute", "通勤", "得体利落"), ("date", "约会", "清爽约会"), ("travel", "出行", "清爽出行")],
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
    test_store = Store(tmp_path, seed_defaults=False)
    client = _client(test_store, monkeypatch)
    response = client.post(
        "/api/v1/inspirations/upload",
        files={"image": ("fake.png", b"not an image", "image/png")},
    )
    assert response.status_code == 415


def test_upload_rejects_image_over_five_megabytes(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path, seed_defaults=False)
    client = _client(test_store, monkeypatch)
    oversized = b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024)

    response = client.post(
        "/api/v1/inspirations/upload",
        files={"image": ("large.png", oversized, "image/png")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["message"] == "图片不能超过 5 MB"


def test_image_recognition_is_limited_to_thirty_successes_per_day(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path, seed_defaults=False)
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
    test_store = Store(tmp_path, seed_defaults=False)
    client = _client(test_store, monkeypatch)
    monkeypatch.setattr(OutfitAIService, "generate_items", _fake_ai_items)
    monkeypatch.setattr(OutfitAIService, "generate_advice", _fake_ai_advice)

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
    test_store = Store(tmp_path, seed_defaults=False)
    client = _client(test_store, monkeypatch)
    calls = 0

    async def count_advice(self, items, weather_summary, scene, audience):
        nonlocal calls
        calls += 1
        return await _fake_ai_advice(self, items, weather_summary, scene, audience)

    monkeypatch.setattr(OutfitAIService, "generate_advice", count_advice)
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
    assert reopened.json()["ai_quota"]["remaining"] == 3
    assert calls == 1


def test_failed_live_ai_swap_releases_quota(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path, seed_defaults=False)
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
    test_store = Store(tmp_path, seed_defaults=False)
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


def test_system_default_outfits_are_seeded_once(tmp_path, monkeypatch) -> None:
    first_store = Store(tmp_path)
    defaults = [outfit for outfit in first_store.list_outfits() if outfit["source"] == "system"]

    assert len(defaults) == 6
    assert sum(outfit["audience"] == "mens" for outfit in defaults) == 3
    assert sum(outfit["audience"] == "womens" for outfit in defaults) == 3
    assert all(outfit["in_pool"] and "favorite" not in outfit for outfit in defaults)
    assert {outfit["label"] for outfit in defaults} == {
        "休闲出行", "复古出行", "层次通勤", "利落通勤", "极简通勤", "甜酷出行",
    }
    assert all(
        any(outfit["label"].endswith(scene) for scene in ("通勤", "约会", "出行"))
        for outfit in defaults
    )
    assert all(component.get("asset_key") for outfit in defaults for component in outfit["components"])
    summer_example = next(outfit for outfit in defaults if outfit["id"] == "outfit_8cec81248dc8")
    summer_result = first_store.get_inspiration(summer_example["inspiration_id"])["result"]
    assert summer_result["suggested_season"] == "summer"
    assert (summer_example["suitable_min"], summer_example["suitable_max"]) == (24.0, 34.0)
    for outfit in defaults:
        original = first_store.inspiration_path(outfit["inspiration_id"])
        assert original and original.is_file()
        assert original.with_name(f"{original.stem}_medium{original.suffix}").is_file()
        assert original.with_name(f"{original.stem}_thumb{original.suffix}").is_file()

    second_store = Store(tmp_path)
    assert len(second_store.list_outfits()) == 6
    assert len(second_store.list_inspirations()) == 6

    client = _client(second_store, monkeypatch)
    assert len(client.get("/api/v1/outfits").json()) == 3
    client.post("/api/v1/settings", json={"audience": "womens"})
    womens_defaults = client.get("/api/v1/outfits").json()
    assert len(womens_defaults) == 3
    assert all(outfit["audience"] == "womens" for outfit in womens_defaults)
    client.post("/api/v1/settings", json={"audience": "mens"})
    assert len(client.get("/api/v1/outfits").json()) == 3

    system_outfit = next(outfit for outfit in second_store.list_outfits() if outfit["source"] == "system" and outfit["audience"] == "mens")
    confirmed = client.post(
        f"/api/v1/inspirations/{system_outfit['inspiration_id']}/confirm",
        json={
            "label": system_outfit["label"], "audience": "womens",
            "components": system_outfit["components"], "scene_ids": system_outfit["scene_ids"],
            "suitable_min": system_outfit["suitable_min"], "suitable_max": system_outfit["suitable_max"],
            "in_pool": False,
        },
    ).json()
    assert confirmed["id"] != system_outfit["id"]
    assert "favorite" not in confirmed and confirmed["in_pool"] is False
    assert second_store.get_outfit(system_outfit["id"])["source"] == "system"


def test_default_upgrade_restores_overwritten_system_outfit_without_losing_user_copy(tmp_path) -> None:
    store = Store(tmp_path)
    system_outfit = next(outfit for outfit in store.list_outfits() if outfit["source"] == "system" and outfit["audience"] == "mens")
    store.save_outfit(system_outfit | {"source": "inspiration", "audience": "womens", "in_pool": False}, system_outfit["id"])
    with store.connect() as db:
        db.execute("UPDATE app_meta SET value='1' WHERE key='default_outfits_version'")

    upgraded = Store(tmp_path)
    restored = upgraded.get_outfit(system_outfit["id"])
    user_copy = upgraded.get_outfit_by_inspiration(system_outfit["inspiration_id"])

    assert restored["source"] == "system" and restored["audience"] == "mens"
    assert user_copy["id"] != restored["id"]
    assert user_copy["source"] == "inspiration" and user_copy["audience"] == "womens"
    assert "favorite" not in user_copy and user_copy["in_pool"] is False
