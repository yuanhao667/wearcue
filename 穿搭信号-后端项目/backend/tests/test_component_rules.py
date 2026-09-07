from app.domain.component_rules import normalize_component_list, normalize_component_thickness


def test_non_thickness_accessories_are_always_regular() -> None:
    for item in (
        {"asset_key": "acc_glasses", "variant_type": "窄框墨镜", "thickness": "thin"},
        {"functional_icon_key": "sunscreen", "variant_type": "防晒霜", "thickness": "thick"},
        {"functional_icon_key": "umbrella", "variant_type": "折叠雨伞", "thickness": "thin"},
    ):
        assert normalize_component_thickness(item)["thickness"] == "regular"


def test_clothing_keeps_real_thickness() -> None:
    item = {"asset_key": "outer_down_short", "variant_type": "羽绒服", "thickness": "thick"}
    assert normalize_component_thickness(item)["thickness"] == "thick"


def test_only_components_with_real_product_icons_are_kept() -> None:
    components = normalize_component_list([
        {"slot": "top", "asset_key": "top_tshirt_short", "functional_icon_key": "short_sleeve"},
        {"slot": "equipment", "asset_key": None, "functional_icon_key": "long_socks"},
        {"slot": "equipment", "asset_key": "unknown", "functional_icon_key": "leg_warmers"},
        {"slot": "equipment", "asset_key": "acc_scarf", "functional_icon_key": "leg_warmers", "variant_type": "粗针织堆堆腿套"},
        {"slot": "equipment", "asset_key": None, "functional_icon_key": "sunglasses"},
        {"slot": "equipment", "asset_key": "acc_umbrella", "functional_icon_key": "umbrella"},
    ])

    assert [item["asset_key"] for item in components] == ["top_tshirt_short", "acc_glasses"]
