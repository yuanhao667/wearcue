from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from app.domain.weather_rules import ThermalBand


@dataclass(frozen=True)
class TemplateItem:
    slot: str
    functional_icon_key: str
    variant_type: str
    color_name: str
    thickness: str


@dataclass(frozen=True)
class OfficialTemplate:
    id: str
    thermal_band: ThermalBand
    scenes: Tuple[str, ...]
    audiences: Tuple[str, ...]
    label: str
    items: Tuple[TemplateItem, ...]


def _item(slot: str, icon: str, variant: str, color: str, thickness: str = "regular") -> TemplateItem:
    return TemplateItem(slot, icon, variant, color, thickness)


_BASE: Dict[ThermalBand, Sequence[Tuple[str, Tuple[TemplateItem, ...]]]] = {
    ThermalBand.hot: (
        ("清爽机能", (_item("top", "short_sleeve", "短袖 T 恤", "奶白", "thin"), _item("bottom", "short_bottom", "速干短裤", "黑色", "thin"), _item("shoes", "daily_shoes", "透气运动鞋", "浅灰"))),
        ("高温留白", (_item("top", "short_sleeve", "宽松短袖", "冰灰", "thin"), _item("bottom", "short_bottom", "宽松短裤", "藏蓝", "thin"), _item("shoes", "daily_shoes", "网面跑鞋", "白色"))),
    ),
    ThermalBand.warm: (
        ("城市轻装", (_item("top", "short_sleeve", "轻薄短袖", "炭灰", "thin"), _item("bottom", "long_bottom", "轻薄长裤", "卡其", "thin"), _item("shoes", "daily_shoes", "运动鞋", "黑色"))),
        ("松弛日常", (_item("top", "short_sleeve", "轻薄 Polo", "米白", "thin"), _item("bottom", "long_bottom", "垂感长裤", "石墨灰", "thin"), _item("shoes", "daily_shoes", "休闲鞋", "灰绿"))),
    ),
    ThermalBand.mild: (
        ("薄层日常", (_item("top", "long_sleeve", "长袖 T 恤", "奶油白", "thin"), _item("bottom", "long_bottom", "直筒休闲裤", "黑色"), _item("shoes", "daily_shoes", "运动鞋", "银灰"))),
        ("长袖节奏", (_item("top", "long_sleeve", "宽松长袖 T 恤", "浅蓝", "thin"), _item("bottom", "long_bottom", "直筒裤", "藏蓝"), _item("shoes", "daily_shoes", "板鞋", "灰白"))),
    ),
    ThermalBand.cool: (
        ("轻机能叠穿", (_item("top", "long_sleeve", "长袖打底", "浅灰"), _item("outerwear", "light_outerwear", "轻量夹克", "黑色"), _item("bottom", "long_bottom", "工装裤", "橄榄绿"), _item("shoes", "daily_shoes", "运动鞋", "黑色"))),
        ("复古运动层", (_item("top", "long_sleeve", "薄卫衣", "麻灰"), _item("outerwear", "light_outerwear", "教练夹克", "藏蓝"), _item("bottom", "long_bottom", "休闲长裤", "奶油白"), _item("shoes", "daily_shoes", "复古跑鞋", "银灰"))),
    ),
    ThermalBand.cold: (
        ("暖感街头", (_item("top", "long_sleeve", "中厚针织", "黑色", "thick"), _item("outerwear", "warm_outerwear", "短呢外套", "深灰"), _item("bottom", "long_bottom", "厚长裤", "黑色"), _item("shoes", "daily_shoes", "短靴", "灰色"))),
        ("暖感层次", (_item("top", "long_sleeve", "高领针织", "米白", "thick"), _item("outerwear", "warm_outerwear", "工装外套", "橄榄绿"), _item("bottom", "long_bottom", "厚直筒裤", "黑色"), _item("shoes", "daily_shoes", "短靴", "棕色"))),
    ),
    ThermalBand.freezing: (
        ("轻量御寒", (_item("top", "warm_top", "保暖打底", "黑色", "thick"), _item("outerwear", "warm_outerwear", "轻羽绒", "银灰", "thick"), _item("bottom", "warm_bottom", "加绒长裤", "深灰", "thick"), _item("shoes", "daily_shoes", "保暖短靴", "黑色"))),
        ("冬日撞色", (_item("top", "warm_top", "保暖内层", "藏蓝", "thick"), _item("outerwear", "warm_outerwear", "短羽绒", "灰绿", "thick"), _item("bottom", "warm_bottom", "保暖裤", "深灰", "thick"), _item("shoes", "daily_shoes", "厚底鞋", "黑色"))),
    ),
    ThermalBand.severe: (
        ("完整冬季防护", (_item("top", "warm_top", "厚保暖层", "深灰", "thick"), _item("outerwear", "warm_outerwear", "长款羽绒", "黑色", "thick"), _item("bottom", "warm_bottom", "防风厚裤", "黑色", "thick"), _item("shoes", "protective_shoes", "防滑保暖靴", "黑色", "thick"))),
        ("极寒机能层", (_item("top", "warm_top", "厚保暖打底", "黑色", "thick"), _item("outerwear", "warm_outerwear", "长款羽绒", "深灰", "thick"), _item("bottom", "warm_bottom", "加厚防风长裤", "黑色", "thick"), _item("shoes", "protective_shoes", "防水防滑高帮鞋", "灰黑", "thick"))),
    ),
}


def official_templates() -> List[OfficialTemplate]:
    templates: List[OfficialTemplate] = []
    for band, rows in _BASE.items():
        for index, (label, items) in enumerate(rows, 1):
            templates.append(
                OfficialTemplate(
                    id="official-%s-%02d" % (band.value, index),
                    thermal_band=band,
                    scenes=("commute", "date", "travel"),
                    audiences=("mens", "womens"),
                    label=label,
                    items=items,
                )
            )
    return templates
