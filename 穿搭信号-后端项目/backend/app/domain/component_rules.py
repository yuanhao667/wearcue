from typing import Any, Dict


# Only these keys have real SVG assets in the product icon library. Weather
# reminders are intentionally excluded because they do not belong in an outfit
# component grid.
SUPPORTED_COMPONENT_ASSET_KEYS = {
    "top_tshirt_short", "top_tshirt_long", "top_tank", "top_camisole", "top_shirt",
    "top_sweatshirt", "top_knit", "top_knit_vest", "outer_light_jacket",
    "outer_wool_coat", "outer_down_short", "outer_shell", "bottom_shorts",
    "bottom_casual_pants", "bottom_sweatpants", "bottom_skirt_short",
    "bottom_skirt_long", "onepiece_dress", "shoe_sneaker", "shoe_canvas",
    "shoe_leather", "shoe_pump", "shoe_sneaker_high_top", "acc_baseball_cap",
    "acc_bucket_hat", "acc_beanie", "acc_gloves", "acc_tote_bag",
    "acc_crossbody_bag", "acc_backpack", "acc_glasses", "acc_scarf",
}

ASSET_KEY_ALIASES = {
    "shoe_sandal": "shoe_sneaker",
    "shoe_boot_short": "shoe_sneaker_high_top",
    "acc_sunglasses": "acc_glasses",
    "acc_eyeglasses": "acc_glasses",
}

FUNCTIONAL_ASSET_KEYS = {
    "short_sleeve": "top_tshirt_short",
    "short_or_long_sleeve": "top_tshirt_long",
    "long_sleeve": "top_tshirt_long",
    "warm_top": "top_knit",
    "light_outerwear": "outer_light_jacket",
    "warm_outerwear": "outer_down_short",
    "protective_outerwear": "outer_shell",
    "short_bottom": "bottom_shorts",
    "long_bottom": "bottom_casual_pants",
    "warm_bottom": "bottom_sweatpants",
    "daily_shoes": "shoe_sneaker",
    "protective_shoes": "shoe_canvas",
    "gloves": "acc_gloves",
    "acc_gloves": "acc_gloves",
    "acc_baseball_cap": "acc_baseball_cap",
    "acc_beanie": "acc_beanie",
    "acc_bucket_hat": "acc_bucket_hat",
    "acc_tote_bag": "acc_tote_bag",
    "acc_crossbody_bag": "acc_crossbody_bag",
    "backpack": "acc_backpack",
    "acc_backpack": "acc_backpack",
    "glasses": "acc_glasses",
    "sunglasses": "acc_glasses",
    "acc_glasses": "acc_glasses",
    "acc_scarf": "acc_scarf",
}

UNSUPPORTED_COMPONENT_TERMS = (
    "袜", "腿套", "护腿", "腰带", "皮带", "耳环", "耳饰", "项链", "手链", "戒指",
)


REGULAR_ONLY_ACCESSORY_KEYS = {
    "acc_glasses", "acc_sunglasses", "acc_eyeglasses", "glasses", "sunglasses",
    "acc_sunscreen", "sunscreen", "acc_umbrella", "umbrella",
}
REGULAR_ONLY_ACCESSORY_TERMS = (
    "眼镜", "墨镜", "太阳镜", "防晒霜", "防晒乳", "防晒露", "雨伞", "折叠伞", "长柄伞",
)


def uses_regular_accessory_thickness(component: Dict[str, Any]) -> bool:
    return (
        str(component.get("asset_key") or "") in REGULAR_ONLY_ACCESSORY_KEYS
        or str(component.get("functional_icon_key") or "") in REGULAR_ONLY_ACCESSORY_KEYS
        or any(
            term in str(component.get("variant_type") or "")
            for term in REGULAR_ONLY_ACCESSORY_TERMS
        )
    )


def normalize_component_thickness(component: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(component)
    if uses_regular_accessory_thickness(result):
        result["thickness"] = "regular"
    return result


def normalize_component(component: Dict[str, Any]) -> Dict[str, Any] | None:
    result = normalize_component_thickness(component)
    variant = str(result.get("variant_type") or "")
    if any(term in variant for term in UNSUPPORTED_COMPONENT_TERMS):
        return None
    raw_asset_key = str(result.get("asset_key") or "").strip().lower()
    asset_key = ASSET_KEY_ALIASES.get(raw_asset_key, raw_asset_key)
    if asset_key not in SUPPORTED_COMPONENT_ASSET_KEYS:
        functional_key = str(result.get("functional_icon_key") or "").strip().lower()
        asset_key = FUNCTIONAL_ASSET_KEYS.get(functional_key, "")
    if asset_key not in SUPPORTED_COMPONENT_ASSET_KEYS:
        return None
    result["asset_key"] = asset_key
    return result


def normalize_component_list(components: Any) -> list[Any]:
    normalized = (
        normalize_component(component)
        for component in components or []
        if isinstance(component, dict)
    )
    return [component for component in normalized if component is not None]
