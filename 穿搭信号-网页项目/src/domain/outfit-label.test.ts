import { describe, expect, it } from "vitest";
import { displayGarmentLabel, displayOutfitLabel } from "./outfit-label";

describe("displayOutfitLabel", () => {
  it("removes legacy numeric suffixes from outfit names", () => {
    expect(displayOutfitLabel("春秋运动通勤 03")).toBe("春秋运动通勤");
    expect(displayOutfitLabel("夏日约会 ２")).toBe("夏日约会");
  });

  it("preserves meaningful numbers that are not trailing sequences", () => {
    expect(displayOutfitLabel("Y2K 复古通勤")).toBe("Y2K 复古通勤");
  });
});

describe("displayGarmentLabel", () => {
  it("removes stacked modifiers while retaining the garment type", () => {
    expect(displayGarmentLabel("泼墨做旧直筒牛仔裤")).toBe("泼墨直筒牛仔裤");
    expect(displayGarmentLabel("宽松落肩条纹短袖T恤")).toBe("条纹短袖T恤");
    expect(displayGarmentLabel("宽松短袖 T 恤")).toBe("宽松短袖T恤");
  });

  it("keeps short names and protective features", () => {
    expect(displayGarmentLabel("黑色棒球帽")).toBe("黑色棒球帽");
    expect(displayGarmentLabel("浅灰色工装夹克")).toBe("浅灰色工装夹克");
    expect(displayGarmentLabel("黑色防水防风连帽外套")).toBe("黑防水防风连帽外套");
  });

  it("preserves unfamiliar long names instead of chopping off the clothing type", () => {
    const name = "彩虹条纹蝴蝶图案吊带背心";
    expect(displayGarmentLabel(name)).toBe(name);
  });
});
