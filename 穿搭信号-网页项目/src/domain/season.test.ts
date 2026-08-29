import { describe, expect, it } from "vitest";
import { seasonLabel } from "./season";

describe("seasonLabel", () => {
  it.each([
    [-5, 8, "冬"],
    [8, 15, "冬"],
    [10, 30, "春秋"],
    [22, 30, "夏"],
    [28, 36, "夏"],
  ])("maps %s°—%s° to %s", (minimum, maximum, expected) => {
    expect(seasonLabel(minimum, maximum)).toBe(expected);
  });
});
