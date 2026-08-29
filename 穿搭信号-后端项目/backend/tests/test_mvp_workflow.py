from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app import auth as auth_dependency
from app.api import auth as auth_api
from app.api import mvp, system
from app.main import app
from app.services.store import Store


def _component() -> dict:
    return {
        "slot": "top", "functional_icon_key": "long_sleeve",
        "variant_type": "长袖 T 恤", "color_name": "黑色", "thickness": "regular",
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


def test_single_user_mvp_workflow(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path, seed_defaults=False)
    client = _client(test_store, monkeypatch)

    settings = client.post("/api/v1/settings", json={"audience": "mens", "cold_offset": -2})
    assert settings.status_code == 200
    assert settings.json()["cold_offset"] == -2

    outfit_payload = {
        "label": "测试穿搭", "audience": "mens", "components": [_component()],
        "scene_ids": ["commute"], "suitable_min": 0, "suitable_max": 40,
        "favorite": True, "in_pool": True,
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
    confirmed = client.post(
        f"/api/v1/inspirations/{inspiration_id}/confirm",
        json=outfit_payload | {"favorite": False, "in_pool": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["source"] == "inspiration"
    assert confirmed.json()["outfit_analysis"]["completion_advice"] == ["搭配直筒长裤补全下装"]
    added_to_favorites = client.post(
        f"/api/v1/inspirations/{inspiration_id}/confirm",
        json=outfit_payload | {"favorite": True, "in_pool": False},
    )
    assert added_to_favorites.status_code == 200
    assert added_to_favorites.json()["id"] == confirmed.json()["id"]
    assert added_to_favorites.json()["favorite"] is True
    assert added_to_favorites.json()["in_pool"] is True
    removed_from_favorites = client.post(
        f"/api/v1/outfits/{confirmed.json()['id']}/status", json={"favorite": False}
    ).json()
    assert removed_from_favorites["favorite"] is False
    assert removed_from_favorites["in_pool"] is True
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


def test_system_default_outfits_are_seeded_once(tmp_path, monkeypatch) -> None:
    first_store = Store(tmp_path)
    defaults = [outfit for outfit in first_store.list_outfits() if outfit["source"] == "system"]

    assert len(defaults) == 6
    assert sum(outfit["audience"] == "mens" for outfit in defaults) == 3
    assert sum(outfit["audience"] == "womens" for outfit in defaults) == 3
    assert all(outfit["favorite"] and outfit["in_pool"] for outfit in defaults)
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
            "favorite": True, "in_pool": False,
        },
    ).json()
    assert confirmed["id"] != system_outfit["id"]
    assert confirmed["favorite"] is True and confirmed["in_pool"] is False
    assert second_store.get_outfit(system_outfit["id"])["source"] == "system"


def test_default_upgrade_restores_overwritten_system_outfit_without_losing_user_copy(tmp_path) -> None:
    store = Store(tmp_path)
    system_outfit = next(outfit for outfit in store.list_outfits() if outfit["source"] == "system" and outfit["audience"] == "mens")
    store.save_outfit(system_outfit | {"source": "inspiration", "audience": "womens", "favorite": True, "in_pool": False}, system_outfit["id"])
    with store.connect() as db:
        db.execute("UPDATE app_meta SET value='1' WHERE key='default_outfits_version'")

    upgraded = Store(tmp_path)
    restored = upgraded.get_outfit(system_outfit["id"])
    user_copy = upgraded.get_outfit_by_inspiration(system_outfit["inspiration_id"])

    assert restored["source"] == "system" and restored["audience"] == "mens"
    assert user_copy["id"] != restored["id"]
    assert user_copy["source"] == "inspiration" and user_copy["audience"] == "womens"
    assert user_copy["favorite"] is True and user_copy["in_pool"] is False
