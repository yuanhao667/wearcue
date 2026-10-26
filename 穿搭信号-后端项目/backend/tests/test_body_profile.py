import pytest
from fastapi.testclient import TestClient
from app import auth as auth_dependency
from app.api import mvp, system
from app.main import app
from app.services.store import Store
from app.services.outfit_ai_service import _profile_styling_points


def test_five_body_choices_persist_and_keep_other_preferences(tmp_path, monkeypatch):
    storage = Store(tmp_path)
    for module in (auth_dependency, mvp, system):
        monkeypatch.setattr(module, "store", storage)
    first, _ = storage.register("body-a@example.test", "test-password", "body-a")
    second, _ = storage.register("body-b@example.test", "test-password", "body-b")
    headers = {"Authorization": f"Bearer {first['token']}"}
    client = TestClient(app)
    client.post("/api/v1/settings", headers=headers, json={"preferred_styles": ["sport"]})
    for choice in ("偏瘦", "稍瘦", "中等", "稍重", "偏重", "偏轻"):
        response = client.post("/api/v1/settings", headers=headers, json={"height_group": "偏高", "weight_group": choice})
        assert response.status_code == 200
        assert response.json()["weight_group"] == choice
        saved = Store(tmp_path).get_settings(first["user"]["id"])
        assert saved["weight_group"] == choice
        assert saved["height_group"] == "偏高"
        assert saved["preferred_styles"] == ["sport"]
    assert storage.get_settings(second["user"]["id"])["weight_group"] == "中等"
    for invalid in ("未知", 4, "偏胖"):
        assert client.post("/api/v1/settings", headers=headers, json={"weight_group": invalid}).status_code == 422


@pytest.mark.parametrize("choice", ["偏瘦", "稍瘦", "稍重", "偏重"])
def test_five_body_choices_have_specific_styling_guidance(choice):
    guidance = _profile_styling_points({"height_group": "中等", "weight_group": choice})
    assert "采用合身但不紧绷的常规松量" not in guidance[0]
