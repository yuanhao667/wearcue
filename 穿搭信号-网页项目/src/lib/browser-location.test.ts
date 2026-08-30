import { beforeEach, describe, expect, it } from "vitest";
import { districtName, saveLoginLocation, takeLoginLocation } from "./browser-location";

beforeEach(() => sessionStorage.clear());

describe("districtName", () => {
  it("prefers the district inside a Beijing administrative hierarchy", () => {
    expect(districtName({ city: "北京市", locality: "三里屯街道", localityInfo: { administrative: [{ name: "北京市" }, { name: "市辖区" }, { name: "朝阳区" }] } })).toBe("朝阳区");
  });

  it("normalizes a traditional Chinese district name", () => {
    expect(districtName({ localityInfo: { administrative: [{ name: "北京市" }, { name: "朝陽區" }] } })).toBe("朝阳区");
  });

  it("hands the login location to the home page exactly once", () => {
    const location = { id: "geo-39.9-116.4", name: "朝阳区", admin1: "北京市", country: "中国", latitude: 39.9, longitude: 116.4, timezone: "Asia/Shanghai" };
    saveLoginLocation(location);
    expect(takeLoginLocation()).toEqual(location);
    expect(takeLoginLocation()).toBeNull();
  });
});
