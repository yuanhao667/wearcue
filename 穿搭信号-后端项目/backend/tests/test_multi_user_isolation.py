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

    unregistered = client.post(
        "/api/v1/auth/login",
        json={"mode": "login", "email": "a@example.com", "password": "password-a"},
    )
    assert unregistered.status_code == 401
    assert unregistered.json()["error"]["message"] == "邮箱或密码错误"

    code_a = client.post(
        "/api/v1/auth/email-code",
        json={"email": "a@example.com", "purpose": "register", "invite_code": "INVITE-A"},
    ).json()["dev_code"]
    code_b = client.post(
        "/api/v1/auth/email-code",
        json={"email": "b@example.com", "purpose": "register", "invite_code": "INVITE-B"},
    ).json()["dev_code"]

    login_a = client.post(
        "/api/v1/auth/login",
        json={"mode": "register", "email": "a@example.com", "password": "password-a", "invite_code": "INVITE-A", "verification_code": code_a},
    )
    login_b = client.post(
        "/api/v1/auth/login",
        json={"mode": "register", "email": "b@example.com", "password": "password-b", "invite_code": "INVITE-B", "verification_code": code_b},
    )
    assert login_a.status_code == login_b.status_code == 200
    token_a = login_a.json()["token"]
    token_b = login_b.json()["token"]
    assert login_a.json()["user"]["id"] != login_b.json()["user"]["id"]
    client.post("/api/v1/auth/onboarding", headers=_headers(token_a), json={"nickname": "小明", "audience": "mens"})
    client.post("/api/v1/auth/onboarding", headers=_headers(token_b), json={"nickname": "小红", "audience": "womens"})

    assert client.get("/api/v1/outfits").status_code == 401
    outfits_a = client.get("/api/v1/outfits", headers=_headers(token_a)).json()
    outfits_b = client.get("/api/v1/outfits", headers=_headers(token_b)).json()
    assert len(outfits_a) == 24
    assert len(outfits_b) == 22
    assert all(item["source"] == "system" for item in outfits_a + outfits_b)
    assert all(item["audience"] == "mens" for item in outfits_a)
    assert all(item["audience"] == "womens" for item in outfits_b)
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
        json={"mode": "login", "email": "a@example.com", "password": "password-a"},
    ).json()
    assert relogin_a["user"]["id"] == login_a.json()["user"]["id"]
    assert relogin_a["user"]["nickname"] == "小明"
    assert relogin_a["user"]["profile_completed"] is True
    original_user_id = login_a.json()["user"]["id"]
    updated_user = client.post(
        "/api/v1/auth/profile",
        headers=_headers(token_a),
        json={"nickname": "新昵称"},
    ).json()["user"]
    assert updated_user["id"] == original_user_id
    assert client.get("/api/v1/auth/me", headers=_headers(token_a)).json()["user"]["id"] == original_user_id

    duplicate = client.post(
        "/api/v1/auth/login",
        json={"mode": "register", "email": "other@example.com", "password": "password-c", "invite_code": "INVITE-A", "verification_code": "123456"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message"] == "该邀请码已注册，请更换邀请码"
