import { describe, expect, it } from "vitest";
import type { Inspiration } from "@/domain/backend";
import { recognitionOutfitName } from "./InspirationApp";

describe("recognition outfit name", () => {
  it.each([
    ["mens", "commute", "利落通勤"],
    ["mens", "date", "帅气约会"],
    ["mens", "travel", "活力出行"],
    ["womens", "commute", "简约通勤"],
    ["womens", "date", "精致约会"],
    ["womens", "travel", "轻旅出行"],
  ] as const)("uses style plus scene for %s %s", (audience, scene, expected) => {
    const result = { suggested_scenes: [scene] } as Inspiration["result"];

    expect(recognitionOutfitName(result, audience)).toBe(expected);
    expect(recognitionOutfitName(result, audience)).not.toContain("＋");
    expect(recognitionOutfitName(result, audience).length).toBeLessThanOrEqual(30);
  });
});
