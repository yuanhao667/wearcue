import json
from pathlib import Path

from app.schemas import VisionResult
from app.services.vision_service import canonical_asset_key, normalize_vision_result


def test_provider_asset_keys_are_normalized_to_existing_icon_keys() -> None:
    result = normalize_vision_result({
        "components": [
            {"variant_type": "运动鞋", "functional_icon_key": "daily_shoes", "asset_key": "shoes_sneakers"},
            {"variant_type": "长裤", "functional_icon_key": "long_bottom", "asset_key": "bottom_pants_long"},
            {"variant_type": "夹克", "functional_icon_key": "light_outerwear", "asset_key": "outerwear_jacket"},
        ]
    })

    assert [item["asset_key"] for item in result["components"]] == [
        "shoe_sneaker", "bottom_casual_pants", "outer_light_jacket"
    ]


def test_unknown_asset_key_falls_back_to_variant_then_function() -> None:
    assert canonical_asset_key({
        "variant_type": "高帮鞋", "functional_icon_key": "daily_shoes", "asset_key": "unknown"
    }) == "shoe_canvas"
    assert canonical_asset_key({
        "variant_type": "未知裤装", "functional_icon_key": "long_bottom", "asset_key": "unknown"
    }) == "bottom_casual_pants"


def test_unknown_model_vocabulary_always_uses_a_library_icon() -> None:
    assert canonical_asset_key({
        "slot": "shoes", "variant_type": "未来感鞋款",
        "functional_icon_key": "unknown", "asset_key": "custom_icon",
    }) == "shoe_sneaker"


def test_formula_short_skirt_repairs_inconsistent_shorts_component() -> None:
    result = normalize_vision_result({
        "components": [{
            "slot": "bottom", "variant_type": "短裤",
            "functional_icon_key": "short_bottom", "asset_key": "bottom_shorts",
        }],
        "replication_guide": {"formula": "印花短袖＋格纹短裙＋低帮鞋"},
    })

    assert result["components"][0]["variant_type"] == "短裙"
    assert result["components"][0]["asset_key"] == "bottom_skirt_short"


def test_visible_shoes_in_full_body_photo_are_not_ai_suggestions() -> None:
    result = normalize_vision_result({
        "image_coverage": "full_body",
        "components": [{
            "slot": "shoes", "variant_type": "低帮鞋",
            "functional_icon_key": "daily_shoes", "asset_key": "shoe_sneaker",
            "suggested": True,
        }],
        "outfit_analysis": {"completion_advice": ["搭配卡其色工装靴呼应裙装色调", "卷起袖口"]},
    })

    assert result["components"][0]["suggested"] is False
    assert result["outfit_analysis"]["completion_advice"] == ["卷起袖口"]


def test_short_sleeve_with_short_bottom_is_always_summer() -> None:
    result = normalize_vision_result({
        "suggested_season": "spring-autumn",
        "components": [
            {"slot": "top", "variant_type": "短袖 T 恤", "asset_key": "top_tshirt_short"},
            {"slot": "bottom", "variant_type": "短裤", "asset_key": "bottom_shorts"},
        ],
    })

    assert result["suggested_season"] == "summer"


def test_prompt_example_is_valid_and_self_consistent() -> None:
    prompt = (Path(__file__).resolve().parents[1] / "app" / "prompts" / "vision_outfit.txt").read_text()
    example = VisionResult.model_validate(json.loads(next(line for line in prompt.splitlines() if line.startswith("{"))))
    formula = example.replication_guide.formula

    assert example.image_coverage == "full_body"
    assert all(not component.suggested for component in example.components)
    assert all(component.variant_type in formula for component in example.components)
    assert example.outfit_analysis.completion_advice == []
    assert example.suggested_season == "summer"
