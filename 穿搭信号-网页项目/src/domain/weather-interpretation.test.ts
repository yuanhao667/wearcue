import { describe, expect, it } from "vitest";
import { interpretPrecipitationProbability, interpretUvIndex, interpretWindGust } from "./weather-interpretation";

describe("weather metric interpretation", () => {
  it("turns a 22 km/h gust into plain-language guidance", () => {
    expect(interpretWindGust(22)).toMatchObject({
      label: "有点风",
      action: "正常出行，轻薄外套更稳",
      scaleMax: "75+",
    });
  });

  it("places UV 5 on the standard 0–11+ scale", () => {
    expect(interpretUvIndex(5)).toMatchObject({
      label: "中等",
      action: "需要基础防晒",
      scaleMax: "11+",
    });
  });

  it("explains when rain probability means bringing an umbrella", () => {
    expect(interpretPrecipitationProbability(65)).toMatchObject({
      label: "较高",
      action: "建议随身带伞",
    });
  });
});
