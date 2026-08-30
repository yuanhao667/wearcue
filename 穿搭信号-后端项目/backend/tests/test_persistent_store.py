import shutil

from app.services.store import Store


def test_store_restores_database_and_keeps_assets_on_persistent_volume(tmp_path, monkeypatch) -> None:
    local = tmp_path / "local"
    persistent = tmp_path / "persistent"
    monkeypatch.setenv("PERSISTENT_DATA_DIR", str(persistent))

    first = Store(local)
    session = first.login("persistent-invite", "测试", "mens")
    assert (persistent / "database" / "outfit-signal.sqlite3").is_file()
    assert first.upload_dir == persistent / "uploads"

    shutil.rmtree(local)
    restored = Store(local)
    assert restored.user_for_token(session["token"])["id"] == session["user"]["id"]
    assert restored.upload_dir == persistent / "uploads"
