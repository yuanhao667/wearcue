import { describe, expect, it } from "vitest";
import { displayOutfitLabel } from "./outfit-label";

describe("displayOutfitLabel", () => {
  it("removes legacy numeric suffixes from outfit names", () => {
    expect(displayOutfitLabel("春秋运动通勤 03")).toBe("春秋运动通勤");
    expect(displayOutfitLabel("夏日约会 ２")).toBe("夏日约会");
  });

  it("preserves meaningful numbers that are not trailing sequences", () => {
    expect(displayOutfitLabel("Y2K 复古通勤")).toBe("Y2K 复古通勤");
  });
});
