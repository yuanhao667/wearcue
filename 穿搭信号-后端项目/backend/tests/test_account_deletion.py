import sqlite3
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import auth as auth_dependency
from app.api import auth as auth_api
from app.main import app
from app.services.image_service import ImageService
from app.services.store import Store, USER_DATA_COLUMNS


@pytest.fixture
def account(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSISTENT_DATA_DIR", str(tmp_path / "persistent"))
    store = Store(tmp_path / "local")
    monkeypatch.setattr(auth_dependency, "store", store)
    monkeypatch.setattr(auth_api, "store", store)
    first, _ = store.register("first@example.com", "first-password", "first-invite")
    second, _ = store.register("second@example.com", "second-password", "second-invite")
    return TestClient(app), store, first, second


def close(client, session, **body):
    return client.post("/api/v1/auth/delete-account", headers={
        "Authorization": f"Bearer {session['token']}",
    }, json={"password": "first-password", "confirmed": True, **body})


def picture(store, owner, digest):
    data = BytesIO()
    Image.new("RGB", (8, 8), "white").save(data, "PNG")
    paths = ImageService(store.upload_dir).process_and_store(data.getvalue(), digest)
    store.create_inspiration({
        "upload_key": digest, "content_hash": digest, "original_name": "test.png",
        "media_type": "image/png", "file_path": paths["original"],
    }, owner)
    return paths


def test_requires_session_password_and_explicit_confirmation(account):
    client, store, first, second = account
    assert client.post("/api/v1/auth/delete-account", json={
        "password": "first-password", "confirmed": True,
    }).status_code == 401
    assert close(client, first, confirmed=False).status_code == 422
    assert close(client, first, password="second-password").status_code == 422
    assert close(client, first, user_id=second["user"]["id"]).status_code == 422
    assert store.user_for_token(first["token"])
    assert store.user_for_token(second["token"])


def test_closes_only_current_account_revokes_sessions_and_cleans_private_files(account):
    client, store, first, second = account
    uid = first["user"]["id"]
    other_id = second["user"]["id"]
    extra_session = store.login("first@example.com", "first-password")
    private = picture(store, uid, "private-test")
    shared = picture(store, uid, "shared-test")
    picture(store, other_id, "shared-test")
    store.set_ai_advice(uid, "test-rec", {"text": "private"})
    store.save_outfit({"label": "private outfit"}, user_id=uid)
    store.issue_email_code("first@example.com", "reset", "test-hash", "2999-01-01T00:00:00+00:00")
    with store.connect() as db:
        system_count = db.execute("SELECT COUNT(*) FROM outfits WHERE owner_user_id IS NULL").fetchone()[0]
    assert close(client, first).status_code == 200
    assert not store.user_for_token(first["token"])
    assert not store.user_for_token(extra_session["token"])
    assert store.login("first@example.com", "first-password") is None
    assert store.user_for_token(second["token"])
    assert close(client, first).status_code == 401
    with store.connect() as db:
        for table, column in USER_DATA_COLUMNS.items():
            assert db.execute(f"SELECT COUNT(*) FROM {table} WHERE {column}=?", (uid,)).fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM email_verification_codes WHERE email_normalized='first@example.com'").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM outfits WHERE owner_user_id IS NULL").fetchone()[0] == system_count
    from pathlib import Path
    assert all(not Path(path).exists() for path in private.values())
    assert all(Path(path).exists() for path in shared.values())
    # A pending AI response may finish after deletion, but cannot restore private records.
    with pytest.raises(sqlite3.IntegrityError, match="account deleted"):
        store.set_ai_advice(uid, "late-result", {"text": "late"})
    with pytest.raises(ValueError, match="account deleted"):
        store.set_ai_outfit_image(uid, "late-image", b"not processed")
    restored = Store(store.data_dir.parent / "restored")
    assert not restored.user_for_token(first["token"])
    assert restored.user_for_token(second["token"])


def test_wrong_password_is_throttled_without_deleting_data(account):
    client, store, first, _ = account
    for _ in range(5):
        assert close(client, first, password="wrong-password").status_code == 422
    assert close(client, first).status_code == 429
    assert store.user_for_token(first["token"])
    with store.connect() as db:
        db.execute("UPDATE users SET deletion_retry_at='2000-01-01' WHERE id=?", (first["user"]["id"],))
    assert close(client, first).status_code == 200


def test_database_failure_rolls_back_deletion(account):
    _, store, first, _ = account
    uid = first["user"]["id"]
    with store.connect() as db:
        db.execute("CREATE TRIGGER fail_delete BEFORE DELETE ON users BEGIN SELECT RAISE(ABORT, 'test failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match="test failure"):
        store.delete_account(uid, "first-password")
    assert store.user_for_token(first["token"])
    assert store.get_settings(uid)
    with store.connect() as db:
        assert not db.execute("SELECT 1 FROM deleted_users WHERE user_id=?", (uid,)).fetchone()
