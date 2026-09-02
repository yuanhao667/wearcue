import { describe, expect, it } from "vitest";
import { outfitItemSortKey } from "./outfit-order";

describe("outfitItemSortKey", () => {
  it("puts weather protection gear before the regular outfit", () => {
    const items = [
      { slot: "shoes", functional_icon_key: "daily_shoes", asset_key: "shoe_sneaker" },
      { slot: "equipment", functional_icon_key: "acc_baseball_cap", asset_key: "acc_baseball_cap" },
      { slot: "top", functional_icon_key: "long_sleeve", asset_key: "top_shirt" },
      { slot: "outerwear", functional_icon_key: "protective_outerwear", asset_key: "outer_shell" },
      { slot: "equipment", functional_icon_key: "umbrella", asset_key: "acc_umbrella" },
      { slot: "equipment", functional_icon_key: "acc_sunscreen", asset_key: "acc_sunscreen" },
    ].sort((a, b) => outfitItemSortKey(a) - outfitItemSortKey(b));

    expect(items.map((item) => item.asset_key)).toEqual(["acc_sunscreen", "acc_umbrella", "outer_shell", "acc_baseball_cap", "top_shirt", "shoe_sneaker"]);
  });
});
