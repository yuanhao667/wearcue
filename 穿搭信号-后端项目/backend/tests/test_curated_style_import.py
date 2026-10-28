import json
from collections import Counter
from pathlib import Path

from app.services.store import Store
from app.services.vision_service import coerce_vision_result


def test_five_styles_survive_store_reload_and_new_assets_are_complete(tmp_path, monkeypatch):
    monkeypatch.delenv("PERSISTENT_DATA_DIR", raising=False)
    manifest = json.loads((Path(__file__).parents[1] / "app/defaults/system_assets.json").read_text())
    first = Store(tmp_path)
    second = Store(tmp_path)
    counts = Counter()
    for entry in manifest["assets"]:
        outfit = second.get_outfit(entry["asset_id"])
        assert outfit["style_tags"] == entry["style_tags"]
        assert outfit["components"] == first.get_outfit(entry["asset_id"])["components"]
        counts.update(outfit["style_tags"])
        if int(entry["asset_id"].split("-")[1]) > 46:
            assert any(c["slot"] == "bottom" for c in outfit["components"])
            assert all(c["asset_key"] and c["color_name"] for c in outfit["components"])
            assert outfit["system_ready"]
    assert counts == {"minimal": 9, "casual": 23, "street": 11, "sport": 12, "outdoor": 8}


def test_vision_keeps_casual_and_street_styles():
    result = coerce_vision_result({"suggested_style_tags": ["casual", "street"]})
    assert result["suggested_style_tags"] == ["casual", "street"]
