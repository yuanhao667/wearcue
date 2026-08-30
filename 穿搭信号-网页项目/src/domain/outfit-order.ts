const HAT_KEYS = new Set(["acc_baseball_cap", "acc_beanie", "acc_sun_hat"]);
const SLOT_ORDER: Record<string, number> = { top: 1, outerwear: 2, onepiece: 3, bottom: 4, shoes: 5, equipment: 6 };

export function outfitItemSortKey(item: { slot: string; functional_icon_key?: string | null; asset_key?: string | null }) {
  if (HAT_KEYS.has(item.functional_icon_key || "") || HAT_KEYS.has(item.asset_key || "")) return 0;
  return SLOT_ORDER[item.slot] ?? 99;
}
