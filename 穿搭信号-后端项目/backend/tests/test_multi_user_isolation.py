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
        "slot": "top", "functional_icon_key": "short_sleeve",
        "variant_type": "短袖 T 恤", "color_name": "黑色", "thickness": "thin",
    }


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_two_users_cannot_read_or_change_each_others_data(tmp_path, monkeypatch) -> None:
    test_store = Store(tmp_path)
    for module in (auth_dependency, auth_api, mvp, system):
        monkeypatch.setattr(module, "store", test_store)
    monkeypatch.setenv("INVITE_CODES", "INVITE-A,INVITE-B")
    client = TestClient(app)

    login_a = client.post(
        "/api/v1/auth/login",
        json={"nickname": "小明", "audience": "mens", "invite_code": "INVITE-A"},
    )
    login_b = client.post(
        "/api/v1/auth/login",
        json={"nickname": "小红", "audience": "womens", "invite_code": "INVITE-B"},
    )
    assert login_a.status_code == login_b.status_code == 200
    token_a = login_a.json()["token"]
    token_b = login_b.json()["token"]
    assert login_a.json()["user"]["id"] != login_b.json()["user"]["id"]

    assert client.get("/api/v1/outfits").status_code == 401
    client.post("/api/v1/settings", json={"cold_offset": -4}, headers=_headers(token_a))
    assert client.get("/api/v1/settings", headers=_headers(token_a)).json()["cold_offset"] == -4
    assert client.get("/api/v1/settings", headers=_headers(token_b)).json()["cold_offset"] == 0

    outfit = client.post(
        "/api/v1/outfits",
        headers=_headers(token_a),
        json={
            "label": "A 的私人穿搭", "audience": "mens", "components": [_component()],
            "scene_ids": ["commute"], "in_pool": True,
        },
    ).json()
    assert client.get(f"/api/v1/outfits/{outfit['id']}", headers=_headers(token_a)).status_code == 200
    assert client.get(f"/api/v1/outfits/{outfit['id']}", headers=_headers(token_b)).status_code == 404
    assert outfit["id"] not in {
        item["id"] for item in client.get("/api/v1/outfits", headers=_headers(token_b)).json()
    }

    mens_system = next(
        item for item in client.get("/api/v1/outfits", headers=_headers(token_a)).json()
        if item["source"] == "system"
    )
    client.post(
        f"/api/v1/outfits/{mens_system['id']}/status",
        headers=_headers(token_a), json={"in_pool": False},
    )
    assert client.get(
        f"/api/v1/outfits/{mens_system['id']}", headers=_headers(token_a)
    ).json()["in_pool"] is False
    assert client.get(
        f"/api/v1/outfits/{mens_system['id']}", headers=_headers(token_b)
    ).json()["in_pool"] is True

    image = Image.new("RGB", (32, 48), "white")
    buffer = BytesIO()
    image.save(buffer, "PNG")
    uploaded = client.post(
        "/api/v1/inspirations/upload",
        headers=_headers(token_a),
        files={"image": ("private.png", buffer.getvalue(), "image/png")},
    ).json()
    assert client.get(
        f"/api/v1/inspirations/{uploaded['id']}/image", headers=_headers(token_a)
    ).status_code == 200
    assert client.get(
        f"/api/v1/inspirations/{uploaded['id']}/image", headers=_headers(token_b)
    ).status_code == 404

    relogin_a = client.post(
        "/api/v1/auth/login",
        json={"nickname": "错误昵称", "audience": "womens", "invite_code": "INVITE-A"},
    ).json()
    assert relogin_a["user"] == login_a.json()["user"]
