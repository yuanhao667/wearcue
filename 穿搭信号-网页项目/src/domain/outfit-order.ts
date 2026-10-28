const BODY_POSITION_ORDER: Record<string, number> = {
  acc_baseball_cap: 0,
  acc_sun_hat: 0,
  acc_bucket_hat: 0,
  acc_beanie: 0,
  acc_glasses: 2,
  acc_scarf: 5,
  acc_tote_bag: 18,
  acc_crossbody_bag: 18,
  acc_backpack: 18,
  acc_gloves: 19,
  acc_sunscreen: 40,
  acc_umbrella: 40,
};
const SLOT_ORDER: Record<string, number> = { top: 10, outerwear: 11, onepiece: 12, bottom: 20, shoes: 30, equipment: 40 };
type SortableOutfitItem = { slot: string; functional_icon_key?: string | null; asset_key?: string | null };

function itemKeys(item: SortableOutfitItem) {
  return [item.functional_icon_key || "", item.asset_key || ""];
}

export function outfitItemSortKey(item: SortableOutfitItem) {
  return Math.min(...itemKeys(item).map((key) => BODY_POSITION_ORDER[key] ?? 99), SLOT_ORDER[item.slot] ?? 99);
}
