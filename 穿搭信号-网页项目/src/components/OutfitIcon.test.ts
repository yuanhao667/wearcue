import { describe, expect, it } from "vitest";
import { assetPath } from "./OutfitIcon";

describe("OutfitIcon", () => {
  it("loads the existing women dress SVG when the selected audience is mens", () => {
    expect(assetPath({ slot: "onepiece", functional_icon_key: "", variant_type: "连衣裙", color_name: "白色", thickness: "thin", asset_key: "onepiece_dress" }, "mens")).toBe("/icons/garments/womens/onepiece_dress.svg");
  });

  it("preserves an explicitly recognised women shared garment for a mens account", () => {
    expect(assetPath({ slot: "top", functional_icon_key: "long_sleeve", variant_type: "长袖衬衫", color_name: "白色", thickness: "thin", asset_key: "womens_top_shirt" }, "mens")).toBe("/icons/garments/womens/top_shirt.svg");
  });
});
