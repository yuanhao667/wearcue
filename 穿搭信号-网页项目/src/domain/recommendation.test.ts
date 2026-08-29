import { describe, expect, it } from "vitest";
import { getGarmentThickness, getThermalBand, getWeatherAdjustments, recommendOutfit } from "./recommendation";
import type { InspirationLook } from "./inspiration";
import type { WeatherSnapshot } from "./types";

const weather: WeatherSnapshot = {
  city: {
    id: "test",
    name: "测试城市",
    country: "中国",
    latitude: 0,
    longitude: 0,
    timezone: "Asia/Shanghai",
  },
  date: "2026-08-23",
  timezone: "Asia/Shanghai",
  currentTemperature: 21,
  currentApparentTemperature: 20,
  apparentMin: 16,
  apparentMax: 25,
  temperatureMin: 17,
  temperatureMax: 26,
  maxPrecipitationProbability: 60,
  totalPrecipitation: 1,
  totalSnowfall: 0,
  maxWindSpeed: 20,
  maxWindGust: 35,
  uvIndexMax: 7,
  weatherCode: 3,
  hourly: [],
  fetchedAt: "2026-08-23T00:00:00.000Z",
};

const personalLook: InspirationLook = {
  id: "grey-commute",
  title: "我常穿的灰色通勤",
  note: "自己的衣服优先",
  imageDataUrl: "data:image/jpeg;base64,test",
  collection: "mens",
  createdAt: "2026-08-24T00:00:00.000Z",
  updatedAt: "2026-08-24T00:00:00.000Z",
  recommendationEnabled: true,
  items: [
    { id: "top", iconKey: "mens_top_shirt", label: "衬衫", category: "top", colorName: "灰色", colorHex: "#777777", thickness: "regular", confidence: 1 },
    { id: "pants", iconKey: "mens_bottom_jeans", label: "牛仔裤", category: "bottom", colorName: "蓝色", colorHex: "#405b79", thickness: "regular", confidence: 1 },
  ],
};

describe("temperature bands", () => {
  it.each([
    [28, "hot"],
    [24, "warm"],
    [20, "mild"],
    [15, "cool"],
    [10, "cold"],
    [5, "freezing"],
    [4.9, "severe"],
  ])("maps %s°C to %s", (temperature, expected) => {
    expect(getThermalBand(temperature)).toBe(expected);
  });

  it("applies personal cold/heat offset", () => {
    expect(getThermalBand(14, 2)).toBe("cool");
    expect(getThermalBand(16, -2)).toBe("cold");
  });
});

describe("weather adjustments", () => {
  it("detects temperature swing, rain and UV", () => {
    expect(getWeatherAdjustments(weather)).toMatchObject({
      needsRemovableLayer: true,
      needsWaterproof: true,
      needsSunProtection: true,
      needsWindproof: false,
    });
  });
});

describe("recommendation", () => {
  it("returns scene-compatible outfit and weather accessory", () => {
    const result = recommendOutfit({ weather, scene: "commute", random: () => 0 });
    expect(result.template.scenes).toContain("commute");
    expect(result.items.some((item) => item.icon === "umbrella")).toBe(true);
    expect(result.items.find((item) => item.icon === "umbrella")?.sourceIconKey).toBe("acc_umbrella");
  });

  it("maps built-in recommendations to the PRD SVG vocabulary", () => {
    const hotWeather = { ...weather, apparentMin: 29, apparentMax: 33 };
    const result = recommendOutfit({ weather: hotWeather, scene: "commute", audience: "mens", random: () => 0 });

    expect(result.items.slice(0, 3).map((item) => item.sourceIconKey)).toEqual([
      "mens_top_tshirt_short",
      "mens_bottom_shorts",
      "mens_shoe_sneaker",
    ]);
  });

  it("can return a different template when the current one is excluded", () => {
    const first = recommendOutfit({ weather, scene: "commute", random: () => 0 });
    const next = recommendOutfit({ weather, scene: "commute", excludedTemplateIds: [first.template.id], random: () => 0 });
    expect(next.template.id).not.toBe(first.template.id);
  });

  it("turns thermal bands into an explicit apparel thickness choice", () => {
    expect(getGarmentThickness("warm")).toBe("thin");
    expect(getGarmentThickness("cool")).toBe("regular");
    expect(getGarmentThickness("freezing")).toBe("thick");

    const result = recommendOutfit({ weather, scene: "commute", random: () => 0 });
    const apparel = result.items.filter((item) => item.category !== "shoes" && item.category !== "accessory");
    expect(apparel.every((item) => item.thickness === "regular")).toBe(true);
    expect(result.items.find((item) => item.category === "shoes")?.thickness).toBeUndefined();
  });

  it("reads only the selected gender template list", () => {
    const hotWeather = { ...weather, apparentMin: 29, apparentMax: 33 };
    const mens = recommendOutfit({ weather: hotWeather, scene: "date", audience: "mens", random: () => 0 });
    const womens = recommendOutfit({ weather: hotWeather, scene: "date", audience: "womens", random: () => 0 });
    expect(mens.template.id).toBe("hot-all-02");
    expect(womens.template.id).toBe("hot-date-01");
  });

  it("prioritizes an enabled personal look matching gender and thickness", () => {
    const result = recommendOutfit({ weather, scene: "commute", audience: "mens", personalLooks: [personalLook], random: () => 0 });

    expect(result.template.id).toBe("personal-grey-commute");
    expect(result.template.source).toBe("personal");
    expect(result.items[0]).toMatchObject({ sourceIconKey: "mens_top_shirt", colorHex: "#777777" });
  });

  it("does not use a personal look with the wrong thickness or gender", () => {
    const thickLook = { ...personalLook, items: personalLook.items.map((item) => ({ ...item, thickness: "thick" as const })) };
    const wrongThickness = recommendOutfit({ weather, scene: "commute", audience: "mens", personalLooks: [thickLook], random: () => 0 });
    const wrongGender = recommendOutfit({ weather, scene: "commute", audience: "womens", personalLooks: [personalLook], random: () => 0 });

    expect(wrongThickness.template.source).not.toBe("personal");
    expect(wrongGender.template.source).not.toBe("personal");
  });
});
