import asyncio
import json

from fastapi.testclient import TestClient

from app import auth as auth_dependency
from app.api import mvp, system
from app.domain.weather_rules import WeatherInput
from app.main import app
from app.services.jev_service import build_request
from app.services.outfit_ai_service import OutfitAIService, REALTIME_CONTEXT_KEYS
from app.services.recommendation_service import recommend_ai_outfit, recommend_system_outfit
from app.services.store import Store


def test_preferences_are_validated_persistent_and_user_scoped(tmp_path, monkeypatch):
    storage = Store(tmp_path)
    for module in (auth_dependency, mvp, system):
        monkeypatch.setattr(module, "store", storage)
    first, _ = storage.register("styles-a@example.test", "test-password", "style-a")
    second, _ = storage.register("styles-b@example.test", "test-password", "style-b")
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {first['token']}"}
    assert client.get("/api/v1/settings", headers=headers).json()["style_preferences_set"] is False
    response = client.post("/api/v1/settings", headers=headers, json={"preferred_styles": ["minimal", "casual", "minimal"]})
    assert response.status_code == 200
    assert response.json()["preferred_styles"] == ["minimal", "casual"]
    assert response.json()["style_preferences_set"] is True
    assert storage.get_settings(second["user"]["id"])["preferred_styles"] == []
    assert Store(tmp_path).get_settings(first["user"]["id"])["preferred_styles"] == ["minimal", "casual"]
    client.post("/api/v1/settings", headers=headers, json={"cold_offset": 2})
    assert storage.get_settings(first["user"]["id"])["preferred_styles"] == ["minimal", "casual"]
    for invalid in (["elegant"], ["sport"] * 6, "sport"):
        assert client.post("/api/v1/settings", headers=headers, json={"preferred_styles": invalid}).status_code == 422
    response = client.post("/api/v1/settings", headers=headers, json={"preferred_styles": []})
    assert response.json()["preferred_styles"] == []
    assert response.json()["style_preferences_set"] is True
    assert client.post("/api/v1/settings", json={"preferred_styles": ["sport"]}).status_code == 401


def test_style_priority_never_bypasses_temperature_or_scene():
    base = {"id": "fallback", "label": "休闲", "source": "system", "system_ready": True,
            "audience": "mens", "scene_ids": ["travel"], "suitable_min": 10, "suitable_max": 25,
            "style_tags": ["casual"], "components": [{"slot": "top", "functional_icon_key": "long_sleeve", "variant_type": "长袖上衣"}]}
    preferred = base | {"id": "preferred", "style_tags": ["outdoor"]}
    unsuitable = preferred | {"id": "cold", "suitable_max": 5}
    weather = WeatherInput(apparent_min=16, apparent_max=20)
    assert recommend_system_outfit(weather, "travel", "mens", [base, unsuitable, preferred], preferred_styles=["outdoor"])["template_id"] == "preferred"
    assert recommend_system_outfit(weather, "travel", "mens", [base, unsuitable], preferred_styles=["outdoor"])["template_id"] == "fallback"
    assert recommend_system_outfit(weather, "date", "mens", [base, preferred], preferred_styles=["outdoor"]) is None


def test_preferences_reach_ai_and_jev_without_losing_weather(monkeypatch):
    captured = {}
    async def fake_generate(_self, context):
        captured.update(context)
        return {"label": "运动穿搭", "items": [{"slot": "top", "functional_icon_key": "long_sleeve", "variant_type": "长袖上衣"}]}
    monkeypatch.setattr(OutfitAIService, "generate_items", fake_generate)
    asyncio.run(recommend_ai_outfit(WeatherInput(apparent_min=12, apparent_max=18), "travel", "mens", weather_context={"preferred_style_tags": ["sport", "outdoor"]}))
    assert captured["preferred_style_tags"] == ["sport", "outdoor"]
    assert "preferred_style_tags" in REALTIME_CONTEXT_KEYS
    state, _, _ = build_request({key: value for key, value in captured.items() if key in REALTIME_CONTEXT_KEYS})
    assert json.loads(state)["用户喜欢的风格"] == ["sport", "outdoor"]
    assert json.loads(state)["体感温度"] == "12~18℃"
