from app.domain.component_rules import normalize_component_thickness


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
