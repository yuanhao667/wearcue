import json
from pathlib import Path

from app.schemas import VisionResult
from app.services.vision_service import (
    canonical_asset_key,
    coerce_vision_result,
    normalize_vision_result,
)


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


def test_new_accessories_resolve_to_supplied_icons() -> None:
    assert canonical_asset_key({
        "slot": "equipment", "variant_type": "登山双肩包",
        "functional_icon_key": "backpack", "asset_key": "unknown",
    }) == "acc_backpack"
    assert canonical_asset_key({
        "slot": "equipment", "variant_type": "黑框墨镜",
        "functional_icon_key": "sunglasses", "asset_key": "unknown",
    }) == "acc_glasses"
    assert canonical_asset_key({
        "slot": "equipment", "variant_type": "白色窄框猫眼墨镜",
        "functional_icon_key": "unknown", "asset_key": "unknown",
    }) == "acc_glasses"
    normalized = normalize_vision_result({
        "components": [{
            "slot": "equipment", "variant_type": "黑色窄框墨镜",
            "functional_icon_key": "sunglasses", "asset_key": "acc_glasses",
            "thickness": "thin",
        }],
    })
    assert normalized["components"][0]["thickness"] == "regular"


def test_unknown_model_vocabulary_always_uses_a_library_icon() -> None:
    assert canonical_asset_key({
        "slot": "shoes", "variant_type": "未来感鞋款",
        "functional_icon_key": "unknown", "asset_key": "custom_icon",
    }) == "shoe_sneaker"


def test_unknown_accessory_does_not_force_an_unrelated_icon() -> None:
    assert canonical_asset_key({
        "slot": "equipment", "variant_type": "粗针织堆堆腿套",
        "functional_icon_key": "leg_warmers", "asset_key": "unknown",
    }) is None


def test_asset_key_repairs_legacy_slot_so_a_top_never_falls_back_to_a_hat() -> None:
    result = normalize_vision_result({
        "components": [{
            "slot": "equipment", "variant_type": "基础款短袖T恤",
            "functional_icon_key": "short_sleeve", "asset_key": "top_tshirt_short",
        }],
    })

    assert result["components"][0]["slot"] == "top"


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


def test_vision_copy_uses_gender_appropriate_style_words() -> None:
    mens = normalize_vision_result({
        "garment_audience": "mens",
        "outfit_analysis": {"summary": "温柔甜美约会风"},
        "replication_guide": {"styling_points": ["营造柔美感"]},
    })
    womens = normalize_vision_result({
        "garment_audience": "womens",
        "outfit_analysis": {"summary": "硬汉粗犷出行风"},
        "replication_guide": {"styling_points": ["强化阳刚感"]},
    })

    assert mens["outfit_analysis"]["summary"] == "协调清新约会风"
    assert mens["replication_guide"]["styling_points"] == ["营造柔和感"]
    assert womens["outfit_analysis"]["summary"] == "利落有层次出行风"
    assert womens["replication_guide"]["styling_points"] == ["强化有力量感"]


def test_prompt_example_is_valid_and_self_consistent() -> None:
    prompt = (Path(__file__).resolve().parents[1] / "app" / "prompts" / "vision_outfit.txt").read_text()
    example = VisionResult.model_validate(json.loads(next(line for line in prompt.splitlines() if line.startswith("{"))))
    formula = example.replication_guide.formula

    assert example.image_coverage == "full_body"
    assert all(not component.suggested for component in example.components)
    assert all(component.variant_type in formula for component in example.components)
    assert example.outfit_analysis.completion_advice == []
    assert example.suggested_season == "summer"


def test_provider_vocabulary_is_coerced_before_strict_validation() -> None:
    result = coerce_vision_result({
        "model_version": "provider-test",
        "garment_audience": "female",
        "image_coverage": "full",
        "components": [
            {
                "slot": "outer", "functional_icon_key": "warm_outerwear",
                "variant_type": "拼色棉服", "color_type": "color_block",
                "color_name": "黑棕拼色", "color_value": "#1A1A1A & #7B5E43",
                "thickness": "medium",
            },
            {
                "slot": "shoe", "functional_icon_key": "daily_shoes",
                "variant_type": "运动鞋", "color_type": "solid",
                "color_name": "白色", "color_value": "#FFFFFF",
                "thickness": "light",
            },
        ],
        "replication_guide": {"formula": "拼色棉服＋运动鞋", "steps": ["穿棉服", "穿运动鞋"]},
        "outfit_analysis": {"summary": "厚外套与轻量鞋形成冬季层次。"},
    })

    parsed = VisionResult.model_validate(result)
    assert parsed.garment_audience == "womens"
    assert parsed.image_coverage == "full_body"
    assert parsed.components[0].slot == "outerwear"
    assert parsed.components[0].thickness == "regular"
    assert parsed.components[0].color_type == "pattern"
    assert parsed.components[0].color_value == "#1A1A1A"
    assert parsed.components[1].slot == "shoes"
    assert parsed.components[1].thickness == "thin"
