import type { GarmentCollection } from "@/domain/types";
import type { Audience, OutfitComponent, OutfitSlot } from "@/domain/backend";

export type GarmentIconCategory = "top" | "outerwear" | "bottom" | "onepiece" | "shoes" | "accessory";
export type GarmentIconPriority = "P0" | "P1";

export interface GarmentIconDefinition {
  category: GarmentIconCategory;
  iconKey: string;
  baseIconKey: string;
  label: string;
  aliases: readonly string[];
  collection: GarmentCollection;
  svgFile: string;
  priority: GarmentIconPriority;
}

type WearableCollection = Exclude<GarmentCollection, "accessory">;
type BaseAvailability = "both" | WearableCollection;

interface BaseGarmentIconDefinition {
  category: GarmentIconCategory;
  iconKey: string;
  label: string;
  aliases: readonly string[];
  priority: GarmentIconPriority;
  availability: BaseAvailability;
}

function icon(
  category: GarmentIconCategory,
  iconKey: string,
  label: string,
  aliases: readonly string[],
  priority: GarmentIconPriority = "P0",
  availability: BaseAvailability = "both",
): BaseGarmentIconDefinition {
  return { category, iconKey, label, aliases, priority, availability };
}

/**
 * Stable vocabulary shared by AI extraction, user correction and UI rendering.
 * Do not rename an iconKey after release; add aliases or a migration instead.
 */
const BASE_GARMENT_ICON_MAP: readonly BaseGarmentIconDefinition[] = [
  icon("top", "top_tshirt_short", "短袖 T 恤", ["短T", "T恤", "短袖", "短袖上衣"]),
  icon("top", "top_tshirt_long", "长袖 T 恤", ["长T", "长袖T恤", "长袖打底"]),
  icon("top", "top_tank", "基础背心", ["背心", "无袖背心", "无袖上衣"], "P1", "mens"),
  icon("top", "top_camisole", "基础吊带", ["吊带", "吊带背心", "细肩带上衣"], "P1", "womens"),
  icon("top", "top_shirt", "长袖衬衫", ["衬衫", "衬衣", "长袖衬衫"]),
  icon("top", "top_sweatshirt", "卫衣", ["圆领卫衣", "套头卫衣", "无帽卫衣"]),
  icon("top", "top_knit", "厚针织衫", ["毛衣", "针织衫", "套头毛衣"]),
  icon("top", "top_knit_vest", "针织背心", ["马甲毛衣", "毛背心", "针织马甲"], "P1"),

  icon("outerwear", "outer_light_jacket", "薄款外套", ["夹克", "薄外套", "短外套"]),
  icon("outerwear", "outer_wool_coat", "厚大衣", ["大衣", "毛呢外套", "羊毛大衣"]),
  icon("outerwear", "outer_down_short", "厚羽绒服", ["短款羽绒服", "短羽绒", "羽绒夹克"]),
  icon("outerwear", "outer_shell", "冲锋衣", ["硬壳", "防水外壳", "防水夹克", "防风外套"]),

  icon("bottom", "bottom_shorts", "短裤", ["休闲短裤", "运动短裤", "五分裤"]),
  icon("bottom", "bottom_casual_pants", "常规长裤", ["长裤", "直筒裤", "阔腿裤", "休闲裤"]),
  icon("bottom", "bottom_sweatpants", "保暖长裤", ["运动裤", "卫裤", "束脚裤", "慢跑裤"]),
  icon("bottom", "bottom_skirt_short", "短裙", ["半身短裙", "A字短裙"], "P0", "womens"),
  icon("bottom", "bottom_skirt_long", "长裙", ["半身长裙", "中长裙"], "P0", "womens"),

  icon("onepiece", "onepiece_dress", "连衣裙", ["裙装", "长裙连衣裙", "短裙连衣裙"], "P0", "womens"),

  icon("shoes", "shoe_sneaker", "低帮鞋", ["运动鞋", "球鞋", "休闲鞋", "板鞋"]),
  icon("shoes", "shoe_canvas", "高帮鞋", ["高帮帆布鞋", "高帮运动鞋"]),
  icon("shoes", "shoe_leather", "正装皮鞋", ["皮鞋", "德比鞋", "牛津鞋"], "P1", "mens"),
  icon("shoes", "shoe_pump", "高跟鞋", ["浅口单鞋", "猫跟鞋"], "P1", "womens"),

  icon("accessory", "acc_baseball_cap", "棒球帽", ["鸭舌帽", "运动帽"]),
  icon("accessory", "acc_beanie", "针织帽", ["毛线帽", "冷帽"]),
  icon("accessory", "acc_gloves", "手套", ["保暖手套", "防风手套"], "P1"),
  icon("accessory", "acc_umbrella", "雨伞", ["折叠伞", "长柄伞"]),
  icon("accessory", "acc_sunscreen", "防晒霜", ["防晒乳", "防晒露"]),
] as const;

const wearableCollections: readonly WearableCollection[] = ["mens", "womens"];

export const GARMENT_ICON_MAP: readonly GarmentIconDefinition[] = BASE_GARMENT_ICON_MAP.flatMap<GarmentIconDefinition>((item) => {
  if (item.category === "accessory") {
    return [{
      category: item.category,
      iconKey: item.iconKey,
      baseIconKey: item.iconKey,
      label: item.label,
      aliases: item.aliases,
      collection: "accessory" as const,
      svgFile: `/icons/garments/accessories/${item.iconKey}.svg`,
      priority: item.priority,
    }];
  }

  const collections = item.availability === "both" ? wearableCollections : [item.availability];
  return collections.map((collection) => ({
    category: item.category,
    iconKey: `${collection}_${item.iconKey}`,
    baseIconKey: item.iconKey,
    label: item.label,
    aliases: item.aliases,
    collection,
    svgFile: `/icons/garments/${collection}/${item.iconKey}.svg`,
    priority: item.priority,
  }));
});

const GARMENT_ICON_BY_KEY = new Map(GARMENT_ICON_MAP.map((item) => [item.iconKey, item]));

const slotCategory: Record<OutfitSlot, GarmentIconCategory> = {
  top: "top", bottom: "bottom", outerwear: "outerwear", onepiece: "onepiece", shoes: "shoes", equipment: "accessory",
};

const functionalFallbacks: Record<string, string> = {
  short_sleeve: "top_tshirt_short", short_or_long_sleeve: "top_tshirt_long", long_sleeve: "top_tshirt_long", warm_top: "top_knit",
  light_outerwear: "outer_light_jacket", warm_outerwear: "outer_down_short", protective_outerwear: "outer_shell",
  short_bottom: "bottom_shorts", long_bottom: "bottom_casual_pants", warm_bottom: "bottom_sweatpants",
  daily_shoes: "shoe_sneaker", protective_shoes: "shoe_canvas", umbrella: "acc_umbrella", gloves: "acc_gloves", sunscreen: "acc_sunscreen", sun_protection: "acc_baseball_cap",
};

export function garmentIconsFor(slot: OutfitSlot, audience: Audience) {
  const collection: GarmentCollection = slot === "equipment" ? "accessory" : audience;
  const options = GARMENT_ICON_MAP.filter((item) => item.category === slotCategory[slot] && item.collection === collection);
  return options.length ? options : GARMENT_ICON_MAP.filter((item) => item.category === slotCategory[slot]);
}

export function resolveGarmentIcon(item: OutfitComponent, audience: Audience) {
  const options = garmentIconsFor(item.slot, audience);
  const variant = item.variant_type.trim().toLocaleLowerCase();
  return GARMENT_ICON_BY_KEY.get(item.asset_key ?? "")
    ?? options.find((option) => [option.label, ...option.aliases].some((term) => term.toLocaleLowerCase() === variant))
    ?? options.find((option) => option.baseIconKey === item.asset_key || option.iconKey === item.asset_key)
    ?? GARMENT_ICON_MAP.find((option) => option.category === slotCategory[item.slot] && option.baseIconKey === item.asset_key)
    ?? options.find((option) => option.baseIconKey === functionalFallbacks[item.functional_icon_key])
    ?? options[0];
}

export function crossAudienceGarmentLabels(items: OutfitComponent[], audience: Audience) {
  return [...new Set(items.flatMap((item) => {
    const definition = resolveGarmentIcon(item, audience);
    return definition && definition.collection !== "accessory" && definition.collection !== audience ? [item.variant_type] : [];
  }))];
}
