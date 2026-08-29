import { describe, expect, it } from "vitest";
import { districtName } from "./browser-location";

describe("districtName", () => {
  it("prefers the district inside a Beijing administrative hierarchy", () => {
    expect(districtName({ city: "北京市", locality: "三里屯街道", localityInfo: { administrative: [{ name: "北京市" }, { name: "市辖区" }, { name: "朝阳区" }] } })).toBe("朝阳区");
  });

  it("normalizes a traditional Chinese district name", () => {
    expect(districtName({ localityInfo: { administrative: [{ name: "北京市" }, { name: "朝陽區" }] } })).toBe("朝阳区");
  });
});
