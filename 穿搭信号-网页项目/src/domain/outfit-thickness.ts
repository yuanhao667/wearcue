import type { OutfitComponent, Thickness } from "@/domain/backend";

type ThicknessItem = {
  functional_icon_key?: string;
  variant_type: string;
  thickness: string;
  asset_key?: string | null;
};

const REGULAR_ONLY_KEYS = new Set([
  "acc_glasses", "acc_sunglasses", "acc_eyeglasses", "glasses", "sunglasses",
  "acc_sunscreen", "sunscreen", "acc_umbrella", "umbrella",
]);
const REGULAR_ONLY_TERMS = ["眼镜", "墨镜", "太阳镜", "防晒霜", "防晒乳", "防晒露", "雨伞", "折叠伞", "长柄伞"];

export function usesRegularAccessoryThickness(item: ThicknessItem) {
  return REGULAR_ONLY_KEYS.has(item.asset_key || "")
    || REGULAR_ONLY_KEYS.has(item.functional_icon_key || "")
    || REGULAR_ONLY_TERMS.some((term) => item.variant_type.includes(term));
}

export function normalizedOutfitThickness(item: ThicknessItem): Thickness {
  if (usesRegularAccessoryThickness(item)) return "regular";
  return (["thin", "regular", "thick"] as string[]).includes(item.thickness)
    ? item.thickness as Thickness
    : "regular";
}

export function outfitThicknessLabel(item: ThicknessItem) {
  const value = normalizedOutfitThickness(item);
  return ({ thin: "薄款", regular: "常规", thick: "厚款" } as const)[value];
}

export function normalizeOutfitComponent(item: OutfitComponent): OutfitComponent {
  return { ...item, thickness: normalizedOutfitThickness(item) };
}
