import { describe, expect, it } from "vitest";
import { detailAdviceStatus, detailSteps } from "./OutfitDetailApp";

describe("detail advice progress", () => {
  it("cycles through advice-generation tasks", () => {
    expect([0, 1, 2, 3, 4].map(detailAdviceStatus)).toEqual([
      "AI 正在分析这套单品组合",
      "AI 正在生成穿搭步骤",
      "AI 正在检查天气适配",
      "AI 正在整理替代建议",
      "AI 正在分析这套单品组合",
    ]);
  });
});

describe("detail outfit steps", () => {
  const items = [
    { variant_type: "牛仔衬衫", color_name: "牛仔蓝", thickness: "regular" },
    { variant_type: "低帮鞋", color_name: "黑色", thickness: "thin" },
  ];

  it("moves each item's color and thickness into its outfit step", () => {
    expect(detailSteps(["先穿牛仔衬衫", "最后穿低帮鞋"], items)).toEqual([
      "先穿牛仔衬衫（牛仔蓝、常规）",
      "最后穿低帮鞋（黑色、薄款）",
    ]);
  });

  it("does not repeat attributes already written by AI", () => {
    expect(detailSteps(["先穿牛仔蓝、常规的牛仔衬衫"], items.slice(0, 1))).toEqual([
      "先穿牛仔蓝、常规的牛仔衬衫",
    ]);
  });

  it("adds a step when a historical guide omits an item", () => {
    expect(detailSteps(["先穿牛仔衬衫"], items)).toEqual([
      "先穿牛仔衬衫（牛仔蓝、常规）",
      "搭配黑色、薄款的低帮鞋",
    ]);
  });
});
