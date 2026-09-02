const WEATHER_GEAR_ORDER: Record<string, number> = { acc_sunscreen: 0, acc_umbrella: 1, outer_shell: 2, protective_outerwear: 2, acc_baseball_cap: 3, acc_sun_hat: 3, acc_beanie: 4 };
const SLOT_ORDER: Record<string, number> = { top: 10, outerwear: 11, onepiece: 12, bottom: 13, shoes: 14, equipment: 15 };
type SortableOutfitItem = { slot: string; functional_icon_key?: string | null; asset_key?: string | null };

function itemKeys(item: SortableOutfitItem) {
  return [item.functional_icon_key || "", item.asset_key || ""];
}

export function outfitItemSortKey(item: SortableOutfitItem) {
  return Math.min(...itemKeys(item).map((key) => WEATHER_GEAR_ORDER[key] ?? 99), SLOT_ORDER[item.slot] ?? 99);
}
