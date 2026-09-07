import json
import re
from collections import Counter
from pathlib import Path

from PIL import Image

from app.services.outfit_ai_service import VALID_ASSET_KEYS


ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "app" / "prompts"


def test_prompt_v3_shared_contract_and_accessory_policy() -> None:
    plan = (PROMPTS / "outfit_generation.txt").read_text(encoding="utf-8")
    vision = (PROMPTS / "vision_outfit.txt").read_text(encoding="utf-8")
    advice = (PROMPTS / "outfit_advice.txt").read_text(encoding="utf-8")
    items = (PROMPTS / "outfit_items.txt").read_text(encoding="utf-8")
    image = (PROMPTS / "outfit_image.txt").read_text(encoding="utf-8")

    for document in (plan, vision, advice, image):
        assert "outfit_dna" in document
        assert "locked_features" in document
    assert "70%" in image and "30%" in image
    assert "中年商务男装目录" in items and "中年商务男装目录" in image
    assert "蓝灰衬衫配黑壳与修身灰裤" in image
    assert "replication_guide" not in items
    assert "outfit_analysis" not in items
    assert "不得擅自新增" in image
    assert "不自动重做" in plan
    assert "禁止在名称末尾添加 01、02、1、2 等编号" in plan
    assert "acc_umbrella" not in VALID_ASSET_KEYS
    assert "acc_sunscreen" not in VALID_ASSET_KEYS
    assert {
        "acc_bucket_hat", "acc_tote_bag", "acc_crossbody_bag", "acc_backpack", "acc_glasses", "acc_scarf",
        "shoe_sneaker_high_top",
    }.issubset(VALID_ASSET_KEYS)


def test_fixed_thirty_case_human_review_matrix_has_required_coverage() -> None:
    cases = json.loads((Path(__file__).parent / "fixtures" / "prompt_v3_samples.json").read_text())
    assert len(cases) == 30
    assert {case["audience"] for case in cases} == {"mens", "womens"}
    assert {case["season"] for case in cases} == {"spring-autumn", "summer", "winter"}
    assert {case["scene"] for case in cases} == {"commute", "date", "travel"}
    assert {style for case in cases for style in case["style_tags"]} == {
        "minimal", "sport", "outdoor",
    }
    assert {case["weather"]["weather"] for case in cases} == {
        "clear", "high_uv", "light_rain", "windy", "snow",
    }
    assert all(case["review"]["status"] == "pending_human_image_review" for case in cases)


def test_cleaned_system_presets_are_structurally_complete_and_approved() -> None:
    payload = json.loads((ROOT / "app" / "defaults" / "system_ai_outfits.json").read_text())
    outfits = payload["outfits"]
    assert payload["quality_status"] == "approved"
    assert len(outfits) == 42
    assert Counter((item["scene"], item["audience"]) for item in outfits) == {
        (scene, audience): 7
        for scene in ("commute", "date", "travel")
        for audience in ("mens", "womens")
    }
    for outfit in outfits:
        assert outfit["quality_status"] == "approved"
        assert outfit["replication_guide"]["formula"] == "＋".join(
            item["variant_type"] for item in outfit["items"]
        )
        assert len(outfit["replication_guide"]["steps"]) == len(outfit["items"])
        assert len(outfit["locked_features"]) >= 3
        for item in outfit["items"]:
            assert item["asset_key"] in VALID_ASSET_KEYS
            assert all(item[field] for field in (
                "fit", "shoulder", "length", "waistline", "bottom_shape",
                "structure_details", "material", "wearing_method",
            ))
            assert item["asset_key"] not in {"acc_umbrella", "acc_sunscreen"}


def test_packaged_system_images_match_the_reviewed_metadata() -> None:
    defaults = ROOT / "app" / "defaults"
    manifest = json.loads((defaults / "system_assets.json").read_text())
    assets = manifest["assets"]
    assert manifest["count"] == len(assets) == 46
    assert Counter(item["audience"] for item in assets) == {"mens": 24, "womens": 22}
    assert Counter(item["season"] for item in assets) == {
        "spring-autumn": 18, "summer": 17, "winter": 11,
    }
    assert len({item["sha256"] for item in assets}) == 46
    for item in assets:
        assert item["content_ready"] is True
        assert item["content_version"]
        assert item["components"]
        assert item["outfit_analysis"]["summary"]
        assert item["replication_guide"]["formula"]
        assert len(item["replication_guide"]["steps"]) >= 2
        assert item["outfit_dna"]
        assert item["signature_features"]
        assert item["locked_features"]
        for component in item["components"]:
            assert component["variant_type"]
            assert component["asset_key"] is not None
            assert component["asset_key"] in VALID_ASSET_KEYS
            expected_slot = (
                "equipment" if component["asset_key"].startswith("acc_")
                else "shoes" if component["asset_key"].startswith("shoe_")
                else "bottom" if component["asset_key"].startswith("bottom_")
                else "outerwear" if component["asset_key"].startswith("outer_")
                else "onepiece" if component["asset_key"].startswith("onepiece_")
                else "top"
            )
            assert component["slot"] == expected_slot
        original = defaults / item["image"]
        assert original.is_file()
        assert original.with_name(original.stem + "_medium.jpg").is_file()
        assert original.with_name(original.stem + "_thumb.jpg").is_file()
        with Image.open(original) as image:
            assert image.width <= 1024 and image.height <= 1536


def test_visible_glasses_are_backfilled_as_detail_components() -> None:
    payload = json.loads((ROOT / "app" / "defaults" / "system_assets.json").read_text())
    expected_ids = {
        "system-001-1da18315", "system-004-1aabf4b6", "system-010-0f9e8da3",
        "system-011-fd4283b0", "system-012-8832354e", "system-013-b600cb09",
        "system-014-b7bd7c80", "system-016-a6fc7785", "system-019-efbc66e7",
        "system-023-3b5336e0", "system-024-24eb810f", "system-025-69b0fbe5",
        "system-026-1779ec36", "system-029-91d2824b", "system-030-fa413b01",
        "system-031-1e9a733b", "system-034-8b82c1ad", "system-035-8bf1acfd",
        "system-039-b47d126a", "system-043-20407ba5", "system-045-e09aca15",
    }
    actual_ids = {
        item["asset_id"]
        for item in payload["assets"]
        if any(component["asset_key"] == "acc_glasses" for component in item["components"])
    }
    assert actual_ids == expected_ids


def test_vision_prompt_requires_visible_glasses_as_components() -> None:
    prompt = (ROOT / "app" / "prompts" / "vision_outfit.txt").read_text()

    assert "眼部、帽檐或头顶" in prompt
    assert "asset_key=acc_glasses" in prompt
    assert "不得只写进 analysis" in prompt


def test_vision_prompt_and_presets_exclude_components_without_icons() -> None:
    prompt = (ROOT / "app" / "prompts" / "vision_outfit.txt").read_text()
    payload = json.loads((ROOT / "app" / "defaults" / "system_assets.json").read_text())

    assert "只有能明确映射到上述现有图标的元素才能进入 components" in prompt
    assert "禁止为了保留元素而强行匹配" in prompt
    assert all(
        component.get("asset_key")
        for item in payload["assets"]
        for component in item["components"]
    )


def test_system_asset_names_are_semantic_unique_and_have_no_sequence_suffix() -> None:
    payload = json.loads((ROOT / "app" / "defaults" / "system_assets.json").read_text())
    labels = [asset["label"] for asset in payload["assets"]]

    assert len(labels) == len(set(labels))
    assert all(
        not re.search(r"\s+(?:0?\d{1,3}|[０-９]{1,3})$", label)
        for label in labels
    )


def test_scarf_icon_is_never_reused_for_legwear() -> None:
    payload = json.loads((ROOT / "app" / "defaults" / "system_assets.json").read_text())
    scarf_components = [
        component
        for item in payload["assets"]
        for component in item["components"]
        if component.get("asset_key") == "acc_scarf"
    ]

    assert scarf_components
    assert all(component["functional_icon_key"] in {"scarf", "scarf_shoulder"} for component in scarf_components)
    legwear = [
        component
        for item in payload["assets"]
        for component in item["components"]
        if component["functional_icon_key"] in {"socks", "long_socks", "leg_warmers"}
    ]
    assert legwear == []
