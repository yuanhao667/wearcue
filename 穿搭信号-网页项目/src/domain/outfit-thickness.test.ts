import { describe, expect, it } from "vitest";
import { normalizedOutfitThickness, outfitThicknessLabel } from "./outfit-thickness";

describe("accessory thickness", () => {
  it.each([
    ["acc_glasses", "sunglasses", "黑色窄框墨镜"],
    ["acc_sunscreen", "sunscreen", "防晒霜"],
    ["acc_umbrella", "umbrella", "折叠雨伞"],
  ])("forces %s to regular", (asset_key, functional_icon_key, variant_type) => {
    const item = { asset_key, functional_icon_key, variant_type, thickness: "thin" as const };
    expect(normalizedOutfitThickness(item)).toBe("regular");
    expect(outfitThicknessLabel(item)).toBe("常规");
  });

  it("keeps real garment thickness", () => {
    expect(outfitThicknessLabel({
      asset_key: "top_tshirt_short", functional_icon_key: "short_sleeve",
      variant_type: "短袖 T 恤", thickness: "thin",
    })).toBe("薄款");
  });
});
