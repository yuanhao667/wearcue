"""Rewrite legacy preset plans into a validated Prompt V3-compatible contract."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "app" / "defaults"
SEASON = {
    "hot": "summer", "warm": "summer", "mild": "spring-autumn",
    "cool": "spring-autumn", "cold": "winter", "freezing": "winter", "severe": "winter",
}
RANGE = {
    "hot": (28, 40), "warm": (24, 34), "mild": (20, 29), "cool": (15, 24),
    "cold": (10, 19), "freezing": (5, 14), "severe": (-20, 8),
}
VALID_ASSETS = {
    "top_tshirt_short", "top_tshirt_long", "top_tank", "top_camisole", "top_shirt",
    "top_sweatshirt", "top_knit", "top_knit_vest", "outer_light_jacket",
    "outer_wool_coat", "outer_down_short", "outer_shell", "bottom_shorts",
    "bottom_casual_pants", "bottom_sweatpants", "bottom_skirt_short",
    "bottom_skirt_long", "onepiece_dress", "shoe_sneaker", "shoe_canvas",
    "shoe_leather", "shoe_pump", "shoe_sneaker_high_top", "acc_baseball_cap", "acc_bucket_hat", "acc_beanie",
    "acc_gloves", "acc_tote_bag", "acc_crossbody_bag", "acc_backpack", "acc_glasses", "acc_scarf",
}
FUNCTIONAL = {
    "top_tshirt_short": "short_sleeve", "top_tank": "short_sleeve",
    "top_camisole": "short_sleeve", "top_tshirt_long": "long_sleeve",
    "top_shirt": "long_sleeve", "top_sweatshirt": "long_sleeve",
    "top_knit": "warm_top", "top_knit_vest": "warm_top",
    "outer_light_jacket": "light_outerwear", "outer_wool_coat": "warm_outerwear",
    "outer_down_short": "warm_outerwear", "outer_shell": "protective_outerwear",
    "bottom_shorts": "short_bottom", "bottom_skirt_short": "short_bottom",
    "bottom_skirt_long": "long_bottom", "bottom_casual_pants": "long_bottom",
    "bottom_sweatpants": "warm_bottom", "onepiece_dress": "onepiece",
    "shoe_sneaker": "daily_shoes", "shoe_canvas": "daily_shoes",
    "shoe_leather": "daily_shoes", "shoe_pump": "daily_shoes",
    "shoe_sneaker_high_top": "daily_shoes", "acc_gloves": "gloves",
    "acc_backpack": "backpack",
    "acc_glasses": "glasses",
}
STYLE_NAME = {"minimal": "简约", "sport": "运动", "outdoor": "户外"}
SCENE_NAME = {"commute": "通勤", "date": "约会", "travel": "出行"}


def corrected_asset(item: dict) -> str:
    text = str(item.get("variant_type") or "")
    slot = item.get("slot")
    if slot == "shoes":
        if "凉鞋" in text:
            return "shoe_sneaker"
        if "靴" in text:
            return "shoe_sneaker_high_top"
        if any(word in text for word in ("乐福", "德比", "皮鞋")):
            return "shoe_leather"
        if "帆布" in text:
            return "shoe_canvas"
    if slot == "bottom":
        if "短裙" in text:
            return "bottom_skirt_short"
        if any(word in text for word in ("长裙", "半身裙")):
            return "bottom_skirt_long"
        if "短裤" in text:
            return "bottom_shorts"
    if slot == "outerwear":
        if "大衣" in text:
            return "outer_wool_coat"
        if "冲锋" in text:
            return "outer_shell"
        if "羽绒" in text:
            return "outer_down_short"
    if slot == "equipment":
        if any(word in text for word in ("双肩包", "登山包", "背包")):
            return "acc_backpack"
        if any(word in text for word in ("眼镜", "墨镜", "太阳镜")):
            return "acc_glasses"
    return str(item.get("asset_key") or "")


def structure(item: dict) -> dict:
    text = str(item.get("variant_type") or "具体单品")
    asset = corrected_asset(item)
    fit = "修身" if any(word in text for word in ("修身", "贴身")) else (
        "宽松" if any(word in text for word in ("宽松", "阔腿", "A字")) else "常规合身"
    )
    shoulder = "不适用" if item.get("slot") in {"bottom", "shoes", "equipment"} else (
        "落肩" if "落肩" in text else "自然肩线"
    )
    if "九分" in text:
        length = "九分至脚踝"
    elif any(word in text for word in ("短裤", "短裙")):
        length = "膝上"
    elif "过膝" in text:
        length = "过膝"
    elif item.get("slot") == "shoes":
        length = "完整包覆脚部"
    elif item.get("slot") == "outerwear":
        length = "臀部以下" if "大衣" in text else "臀部附近"
    else:
        length = "常规长度"
    waistline = "高腰" if "高腰" in text else (
        "自然腰" if item.get("slot") == "bottom" else "不适用"
    )
    bottom_shape = "不适用"
    if item.get("slot") == "bottom":
        bottom_shape = next(
            (shape for shape in ("A字", "阔腿", "直筒", "束脚", "修身") if shape in text),
            "自然直筒",
        )
    material = next(
        (value for keyword, value in (
            ("羊毛", "羊毛质感"), ("针织", "针织"), ("灯芯绒", "灯芯绒"),
            ("法兰绒", "法兰绒"), ("速干", "轻量速干面料"), ("牛仔", "牛仔布"),
            ("棉麻", "棉麻混纺"), ("呢", "毛呢质感"), ("皮", "皮革质感"),
        ) if keyword in text),
        "日常哑光面料",
    )
    details = [value for keyword, value in (
        ("落肩", "落肩线"), ("高领", "高领"), ("连帽", "连帽"),
        ("双排扣", "双排扣"), ("工装", "功能口袋"), ("束脚", "收口裤脚"),
    ) if keyword in text] or ["简洁剪裁"]
    wearing = "作为外层自然叠穿" if item.get("slot") == "outerwear" else (
        "完整露出腰线" if waistline == "高腰" else "按自然线条穿着"
    )
    return item | {
        "asset_key": asset,
        "functional_icon_key": FUNCTIONAL.get(asset, asset),
        "fit": fit,
        "shoulder": shoulder,
        "length": length,
        "waistline": waistline,
        "bottom_shape": bottom_shape,
        "structure_details": details,
        "material": material,
        "pattern_description": "拼色" if "拼色" in text else "纯色",
        "wearing_method": wearing,
    }


def style_for(items: list[dict]) -> str:
    text = json.dumps(items, ensure_ascii=False)
    if any(word in text for word in ("冲锋", "防水", "防风", "工装", "机能", "徒步")):
        return "outdoor"
    if any(word in text for word in ("卫衣", "运动裤", "跑鞋", "速干", "束脚", "运动套装")):
        return "sport"
    return "minimal"


def validate(outfit: dict) -> None:
    items = outfit["items"]
    slots = {item["slot"] for item in items}
    if not ({"top", "onepiece"} & slots and {"bottom", "onepiece"} & slots and "shoes" in slots):
        raise ValueError(f"{outfit['id']}: incomplete visible outfit")
    for item in items:
        if item["asset_key"] not in VALID_ASSETS:
            raise ValueError(f"{outfit['id']}: invalid asset {item['asset_key']}")
        for field in (
            "fit", "shoulder", "length", "waistline", "bottom_shape",
            "structure_details", "material", "wearing_method",
        ):
            if not item.get(field):
                raise ValueError(f"{outfit['id']}: missing {field}")
    serialized = json.dumps(outfit["items"], ensure_ascii=False)
    if any(word in serialized for word in ("防晒霜", "雨伞")):
        raise ValueError(f"{outfit['id']}: reminder leaked into visible items")


def main() -> None:
    path = ROOT / "system_ai_outfits.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    for outfit in payload["outfits"]:
        items = [structure(item) for item in outfit.get("items") or []]
        band = outfit["thermal_band"]
        style = style_for(items)
        signatures = [
            f"{item['variant_type']}（{item['fit']}，{item['length']}）" for item in items
        ][:8]
        locked = signatures[:3]
        layers = "含可脱外层" if any(item["slot"] == "outerwear" for item in items) else "单层组合"
        proportion = "高腰线" if any(item["waistline"] == "高腰" for item in items) else "自然腰线"
        outfit.update({
            "items": items,
            "prompt_version": "wearcue-outfit-plan-v3-migrated",
            "mode": "original_generation",
            "season": SEASON[band],
            "style_tags": [style],
            "temperature_range_c": {"min": RANGE[band][0], "max": RANGE[band][1]},
            "outfit_dna": {
                "silhouette_route": "＋".join(item["fit"] for item in items[:2]),
                "proportion": proportion,
                "layering": layers,
                "material_contrast": "＋".join(dict.fromkeys(item["material"] for item in items[:3])),
                "color_structure": "＋".join(item["color_name"] for item in items),
                "accessory_role": "仅保留 items 中已有配饰",
                "footwear_shape": next(item["variant_type"] for item in items if item["slot"] == "shoes"),
            },
            "signature_features": signatures,
            "locked_features": locked,
            "image_direction": {
                "composition": "2:3竖版全身，头部与鞋履完整，自然光日常环境",
                "must_show": locked,
                "must_avoid": ["普通化替换", "只换颜色", "无故添加配饰", "品牌与水印"],
            },
            "replication_guide": {
                "formula": "＋".join(item["variant_type"] for item in items),
                "steps": [
                    f"穿好{item['variant_type']}，保持{item['fit']}与{item['wearing_method']}"
                    for item in items
                ],
                "styling_points": [f"保持{proportion}", f"保持{layers}", "鞋履完整可见"],
                "weather_note": f"适穿温度为 {RANGE[band][0]}～{RANGE[band][1]}℃。",
                "substitute": "仅可换同品类、同厚度且版型比例一致的单品。",
            },
            "outfit_analysis": {
                "summary": f"以{STYLE_NAME[style]}结构适配{SCENE_NAME[outfit['scene']]}，单品与图标逐项一致。",
                "structure_points": [f"廓形：{items[0]['fit']}＋{items[1]['fit']}", f"比例：{proportion}", f"层次：{layers}"],
                "completion_advice": [],
            },
            "quality_status": "approved",
        })
        validate(outfit)
    payload.update({
        "version": 6,
        "prompt_version": "wearcue-outfit-plan-v3-migrated",
        "quality_status": "approved",
    })
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
