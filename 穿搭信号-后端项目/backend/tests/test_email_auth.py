import hashlib
import sqlite3
import ssl

import pytest

from fastapi.testclient import TestClient

from app import auth as auth_dependency
from app.api import auth as auth_api
from app.main import app
from app.services import email_service
from app.services.store import Store


def test_production_rejects_console_delivery(monkeypatch, caplog):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("EMAIL_DELIVERY_MODE", "console")
    with pytest.raises(email_service.EmailDeliveryError):
        email_service.send_verification_email("recipient@example.com", "123456", "register")
    assert "123456" not in caplog.text


def test_smtp_verifies_certificate_and_sends_expected_message(monkeypatch):
    monkeypatch.setenv("EMAIL_DELIVERY_MODE", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.resend.com")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USERNAME", "resend")
    monkeypatch.setenv("SMTP_PASSWORD", "test-only-key")
    monkeypatch.setenv("SMTP_FROM", "WearCue <noreply@mail.wearcue.cn>")
    monkeypatch.setenv("SMTP_USE_SSL", "true")
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout, context):
            assert (host, port, timeout) == ("smtp.resend.com", 465, 10)
            assert context.verify_mode == ssl.CERT_REQUIRED
            assert context.check_hostname

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def login(self, username, password):
            assert (username, password) == ("resend", "test-only-key")

        def send_message(self, message):
            sent.append(message)

    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", FakeSMTP)
    email_service.send_verification_email("recipient@example.com", "123456", "register")
    assert sent[0]["To"] == "recipient@example.com"
    assert sent[0]["From"] == "WearCue <noreply@mail.wearcue.cn>"
    assert "123456" in sent[0].get_content()


def test_smtp_rejects_plaintext_connection(monkeypatch):
    monkeypatch.setenv("EMAIL_DELIVERY_MODE", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.resend.com")
    monkeypatch.setenv("SMTP_FROM", "noreply@mail.wearcue.cn")
    monkeypatch.setenv("SMTP_USE_SSL", "false")
    monkeypatch.setenv("SMTP_USE_STARTTLS", "false")
    with pytest.raises(email_service.EmailDeliveryError, match="TLS"):
        email_service.send_verification_email("recipient@example.com", "123456", "register")


def _client(tmp_path, monkeypatch):
    test_store = Store(tmp_path)
    monkeypatch.setattr(auth_dependency, "store", test_store)
    monkeypatch.setattr(auth_api, "store", test_store)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("EMAIL_DELIVERY_MODE", "console")
    monkeypatch.setenv("EMAIL_CODE_SECRET", "test-secret-with-more-than-thirty-two-characters")
    monkeypatch.setenv("INVITE_CODES", "VALID-INVITE")
    return TestClient(app), test_store


def _code(client: TestClient, email: str, purpose: str, invite_code: str | None = None) -> str:
    response = client.post(
        "/api/v1/auth/email-code",
        json={"email": email, "purpose": purpose, "invite_code": invite_code},
    )
    assert response.status_code == 200
    return response.json()["dev_code"]


def test_registration_verifies_email_hashes_password_and_binds_invite(tmp_path, monkeypatch) -> None:
    client, test_store = _client(tmp_path, monkeypatch)
    code = _code(client, "New@Example.com", "register", "VALID-INVITE")
    registered = client.post(
        "/api/v1/auth/login",
        json={
            "mode": "register", "email": "New@Example.com", "password": "safe-password",
            "invite_code": "VALID-INVITE", "verification_code": code,
        },
    )
    assert registered.status_code == 200
    assert registered.json()["user"]["profile_completed"] is False

    with sqlite3.connect(test_store.db_path) as db:
        password_hash = db.execute(
            "SELECT password_hash FROM users WHERE email_normalized='new@example.com'"
        ).fetchone()[0]
    assert password_hash.startswith("scrypt$")
    assert "safe-password" not in password_hash

    assert client.post(
        "/api/v1/auth/login",
        json={"mode": "login", "email": "NEW@example.com", "password": "safe-password"},
    ).status_code == 200
    assert client.post(
        "/api/v1/auth/login",
        json={"mode": "login", "email": "new@example.com", "password": "wrong-password"},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={
            "mode": "register", "email": "other@example.com", "password": "safe-password",
            "invite_code": "VALID-INVITE", "verification_code": code,
        },
    ).status_code == 409


def test_onboarding_and_password_reset_flow(tmp_path, monkeypatch) -> None:
    client, _ = _client(tmp_path, monkeypatch)
    register_code = _code(client, "me@example.com", "register", "VALID-INVITE")
    registered = client.post(
        "/api/v1/auth/login",
        json={
            "mode": "register", "email": "me@example.com", "password": "old-password",
            "invite_code": "VALID-INVITE", "verification_code": register_code,
        },
    ).json()
    headers = {"Authorization": f"Bearer {registered['token']}"}
    onboarded = client.post(
        "/api/v1/auth/onboarding",
        headers=headers,
        json={"nickname": "小明", "audience": "womens"},
    )
    assert onboarded.json()["user"]["profile_completed"] is True
    assert onboarded.json()["user"]["nickname"] == "小明"
    assert onboarded.json()["user"]["audience"] == "womens"

    reset_code = _code(client, "me@example.com", "reset")
    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"email": "me@example.com", "verification_code": reset_code, "password": "new-password"},
    )
    assert reset.status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"mode": "login", "email": "me@example.com", "password": "old-password"},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"mode": "login", "email": "me@example.com", "password": "new-password"},
    ).status_code == 200


def test_email_code_is_rate_limited_and_one_time(tmp_path, monkeypatch) -> None:
    client, _ = _client(tmp_path, monkeypatch)
    code = _code(client, "once@example.com", "register", "VALID-INVITE")
    repeated = client.post(
        "/api/v1/auth/email-code",
        json={"email": "once@example.com", "purpose": "register", "invite_code": "VALID-INVITE"},
    )
    assert repeated.status_code == 429
    payload = {
        "mode": "register", "email": "once@example.com", "password": "safe-password",
        "invite_code": "VALID-INVITE", "verification_code": code,
    }
    assert client.post("/api/v1/auth/login", json=payload).status_code == 200
    assert client.post("/api/v1/auth/login", json=payload).status_code == 409


def test_existing_invite_only_account_can_claim_email_without_losing_identity(tmp_path) -> None:
    db_path = tmp_path / "outfit-signal.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.execute(
            """CREATE TABLE users (
            id TEXT PRIMARY KEY, invite_code_hash TEXT NOT NULL UNIQUE,
            nickname TEXT NOT NULL, audience TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
        )
        db.execute(
            "INSERT INTO users VALUES (?,?,?,?,?,?)",
            (
                "legacy-user",
                hashlib.sha256(b"LEGACY-INVITE").hexdigest(),
                "老用户",
                "womens",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )
    migrated = Store(tmp_path)
    session, conflict = migrated.register(
        "legacy@example.com", "safe-password", "LEGACY-INVITE",
    )
    assert conflict is None
    assert session["user"]["id"] == "legacy-user"
    assert session["user"]["nickname"] == "老用户"
    assert session["user"]["audience"] == "womens"
    assert session["user"]["profile_completed"] is True
