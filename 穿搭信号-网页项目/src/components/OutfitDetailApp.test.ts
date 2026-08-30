import { describe, expect, it } from "vitest";
import { detailAdviceStatus } from "./OutfitDetailApp";

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
