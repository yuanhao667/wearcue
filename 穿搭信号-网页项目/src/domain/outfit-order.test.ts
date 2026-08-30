import { describe, expect, it } from "vitest";
import { outfitItemSortKey } from "./outfit-order";

describe("outfitItemSortKey", () => {
  it("puts hats first and non-hat equipment last", () => {
    const items = [
      { slot: "shoes", functional_icon_key: "daily_shoes", asset_key: "shoe_sneaker" },
      { slot: "equipment", functional_icon_key: "sun_protection", asset_key: "acc_beanie" },
      { slot: "top", functional_icon_key: "long_sleeve", asset_key: "top_shirt" },
      { slot: "equipment", functional_icon_key: "umbrella", asset_key: "acc_umbrella" },
    ].sort((a, b) => outfitItemSortKey(a) - outfitItemSortKey(b));

    expect(items.map((item) => item.asset_key)).toEqual(["acc_beanie", "top_shirt", "shoe_sneaker", "acc_umbrella"]);
  });
});
