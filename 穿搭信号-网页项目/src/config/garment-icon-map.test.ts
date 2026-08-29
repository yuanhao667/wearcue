import { describe, expect, it } from "vitest";
import { GARMENT_ICON_MAP, resolveGarmentIcon } from "./garment-icon-map";

describe("garment icon vocabulary", () => {
  it("contains fully separated mens, womens and accessory collections", () => {
    expect(GARMENT_ICON_MAP).toHaveLength(41);
    expect(GARMENT_ICON_MAP.some((item) => item.collection === "mens")).toBe(true);
    expect(GARMENT_ICON_MAP.some((item) => item.collection === "womens")).toBe(true);
    expect(GARMENT_ICON_MAP.some((item) => item.collection === "accessory")).toBe(true);
  });

  it("has unique keys and one SVG path per item", () => {
    const keys = GARMENT_ICON_MAP.map((item) => item.iconKey);
    const files = GARMENT_ICON_MAP.map((item) => item.svgFile);
    expect(new Set(keys).size).toBe(keys.length);
    expect(new Set(files).size).toBe(files.length);
  });

  it("duplicates common garments into both complete lists and keeps targeted items in one list", () => {
    expect(GARMENT_ICON_MAP.find((item) => item.iconKey === "mens_top_tshirt_short")?.collection).toBe("mens");
    expect(GARMENT_ICON_MAP.find((item) => item.iconKey === "womens_top_tshirt_short")?.collection).toBe("womens");
    expect(GARMENT_ICON_MAP.find((item) => item.iconKey === "mens_onepiece_dress")).toBeUndefined();
    expect(GARMENT_ICON_MAP.find((item) => item.iconKey === "womens_onepiece_dress")?.collection).toBe("womens");
    expect(GARMENT_ICON_MAP.find((item) => item.iconKey === "mens_shoe_leather")?.collection).toBe("mens");
    expect(GARMENT_ICON_MAP.find((item) => item.iconKey === "womens_shoe_pump")?.collection).toBe("womens");
  });

  it("keeps final user-facing terms as distinct mappings", () => {
    const byTerm = (term: string) => GARMENT_ICON_MAP.find((item) => item.label === term || item.aliases.includes(term));
    expect(byTerm("卫衣")?.baseIconKey).toBe("top_sweatshirt");
    expect(byTerm("薄款外套")?.baseIconKey).toBe("outer_light_jacket");
    expect(byTerm("冲锋衣")?.baseIconKey).toBe("outer_shell");
    expect(byTerm("休闲短裤")?.baseIconKey).toBe("bottom_shorts");
  });

  it("maps a recognised sneaker name to the available sneaker SVG", () => {
    expect(resolveGarmentIcon({ slot: "shoes", functional_icon_key: "unknown", variant_type: "运动鞋", color_name: "", thickness: "regular", asset_key: "missing" }, "mens")?.baseIconKey).toBe("shoe_sneaker");
  });

  it("maps a recognised pants name to the available pants SVG", () => {
    expect(resolveGarmentIcon({ slot: "bottom", functional_icon_key: "long_bottom", variant_type: "长裤", color_name: "", thickness: "regular", asset_key: "bottom_pants_long" }, "mens")?.baseIconKey).toBe("bottom_casual_pants");
  });

  it("uses the real women collection for a dress even when mens is selected", () => {
    expect(resolveGarmentIcon({ slot: "onepiece", functional_icon_key: "", variant_type: "连衣裙", color_name: "白色", thickness: "thin", asset_key: "onepiece_dress" }, "mens")?.collection).toBe("womens");
  });

  it("keeps a recognised women skirt instead of replacing it with mens shorts", () => {
    expect(resolveGarmentIcon({ slot: "bottom", functional_icon_key: "short_bottom", variant_type: "短裙", color_name: "黑色", thickness: "thin", asset_key: "bottom_skirt_short" }, "mens")?.iconKey).toBe("womens_bottom_skirt_short");
  });
});
