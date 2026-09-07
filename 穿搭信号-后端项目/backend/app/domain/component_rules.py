from typing import Any, Dict


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


def normalize_component_list(components: Any) -> list[Any]:
    return [
        normalize_component_thickness(component) if isinstance(component, dict) else component
        for component in components or []
    ]
