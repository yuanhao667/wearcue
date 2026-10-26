import type { Outfit } from "./backend";

export const outfitColors = [
  { id: "black", label: "黑色", swatch: "#303238", pattern: /黑|black/i },
  { id: "white", label: "白色", swatch: "#ffffff", pattern: /白|white/i },
  { id: "gray", label: "灰色", swatch: "#aeb2b8", pattern: /灰|gr[ae]y|银/i },
  { id: "beige", label: "米色", swatch: "#f3e3bc", pattern: /米|卡其|燕麦|beige|ivory|cream|khaki/i },
  { id: "brown", label: "棕色", swatch: "#b57c4b", pattern: /棕|褐|咖|驼|焦糖|巧克力|brown|camel|chocolate/i },
  { id: "pink", label: "粉色", swatch: "#f28fb7", pattern: /粉|pink/i },
  { id: "red", label: "红色", swatch: "#f35d5b", pattern: /红|red|burgundy|maroon/i },
  { id: "orange", label: "橙色", swatch: "#ffad47", pattern: /橙|橘|orange/i },
  { id: "yellow", label: "黄色", swatch: "#f5d94c", pattern: /黄|yellow|gold/i },
  { id: "green", label: "绿色", swatch: "#70ba78", pattern: /绿|青|green|olive|teal/i },
  { id: "blue", label: "蓝色", swatch: "#5da3ec", pattern: /蓝|blue|navy|denim/i },
  { id: "purple", label: "紫色", swatch: "#b38be4", pattern: /紫|purple|violet|lavender/i },
] as const;

export type OutfitColorId = typeof outfitColors[number]["id"];

export function outfitMatchesColor(outfit: Pick<Outfit, "components">, color: OutfitColorId | null): boolean {
  if (!color) return true;
  const pattern = outfitColors.find((option) => option.id === color)!.pattern;
  return outfit.components.some((item) => {
    if (!["top", "outerwear", "bottom", "onepiece"].includes(item.slot) || item.suggested) return false;
    // shortcut: 使用已记录的单品颜色，缺失或误标时需补齐识别结果，不能用照片背景色兜底。
    const colors = `${item.color_name} ${item.pattern_description ?? ""}`
      .replace(/米白|奶白|象牙白|奶油白|米黄/g, "米色")
      .replace(/藏青|深青|靛青/g, "蓝色")
      .replace(/粉红/g, "粉色")
      .replace(/黄棕|黄褐|棕黄/g, "棕色");
    return pattern.test(colors);
  });
}
