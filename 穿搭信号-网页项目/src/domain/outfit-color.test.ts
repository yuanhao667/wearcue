import { describe, expect, it } from "vitest";
import type { OutfitComponent, OutfitSlot } from "./backend";
import { outfitMatchesColor } from "./outfit-color";

const item = (slot: OutfitSlot, color_name: string, extra: Partial<OutfitComponent> = {}): OutfitComponent => ({
  slot, color_name, functional_icon_key: "test", variant_type: "测试单品", thickness: "regular", ...extra,
});

describe("outfit color filtering", () => {
  it("matches any actual garment, including an inner layer, skirt or dress", () => {
    for (const slot of ["top", "outerwear", "bottom", "onepiece"] as const) {
      expect(outfitMatchesColor({ components: [item(slot, "浅灰色")] }, "gray")).toBe(true);
    }
    expect(outfitMatchesColor({ components: [item("top", "白色"), item("bottom", "深棕色")] }, "brown")).toBe(true);
  });

  it("never matches shoes, accessories or suggested additions", () => {
    const outfit = { components: [item("top", "白色"), item("shoes", "黑色"), item("equipment", "黑色"), item("outerwear", "黑色", { suggested: true })] };
    expect(outfitMatchesColor(outfit, "black")).toBe(false);
    expect(outfitMatchesColor(outfit, null)).toBe(true);
  });

  it("matches secondary pattern colors and common named shades", () => {
    const pattern = { components: [item("top", "米白色", { pattern_description: "藏青红细条纹" })] };
    expect(outfitMatchesColor(pattern, "beige")).toBe(true);
    expect(outfitMatchesColor(pattern, "blue")).toBe(true);
    expect(outfitMatchesColor(pattern, "red")).toBe(true);
    expect(outfitMatchesColor(pattern, "green")).toBe(false);
    expect(outfitMatchesColor({ components: [item("top", "棕色与黑色拼接")] }, "black")).toBe(true);
    expect(outfitMatchesColor({ components: [item("top", "米白色")] }, "white")).toBe(false);
    expect(outfitMatchesColor({ components: [item("top", "粉红色")] }, "red")).toBe(false);
    expect(outfitMatchesColor({ components: [item("top", "navy")] }, "blue")).toBe(true);
  });

  it("does not guess colors from a title or an unlabelled hex value", () => {
    expect(outfitMatchesColor({ components: [item("top", "基础色", { color_value: "#000000", variant_type: "墨镜印花上衣" })] }, "black")).toBe(false);
    expect(outfitMatchesColor({ components: [] }, "black")).toBe(false);
  });
});
