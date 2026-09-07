import { describe, expect, it } from "vitest";
import { detailAdviceStatus, detailSteps, recommendationSavePayload } from "./OutfitDetailApp";
import type { BackendRecommendation, ReplicationGuide } from "@/domain/backend";

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

  it("matches abbreviated AI steps to the right item instead of the visual sort order", () => {
    const sortedItems = [
      { variant_type: "针织冷帽", color_name: "焦糖色", thickness: "regular" },
      { variant_type: "黑色内搭上衣", color_name: "黑色", thickness: "thin" },
      { variant_type: "拼色短款面包羽绒服", color_name: "棕色与黑色拼接", thickness: "thick" },
    ];
    expect(detailSteps(["穿着黑色内搭", "套上拼色短款面包服", "戴上焦糖色冷帽"], sortedItems)).toEqual([
      "戴上焦糖色冷帽（焦糖色、常规）",
      "穿着黑色内搭（黑色、薄款）",
      "套上拼色短款面包服（棕色与黑色拼接、厚款）",
    ]);
  });

  it("recognizes a short T-shirt alias instead of appending a duplicate step", () => {
    expect(detailSteps(
      ["内搭白T恤并露出下摆"],
      [{ variant_type: "基础款短袖T恤", color_name: "白色", thickness: "thin" }],
    )).toEqual(["内搭白T恤并露出下摆（白色、薄款）"]);
  });

  it("falls back to item-derived steps for historical guides without a steps array", () => {
    expect(detailSteps(undefined, items)).toEqual([
      "搭配牛仔蓝、常规的牛仔衬衫",
      "搭配黑色、薄款的低帮鞋",
    ]);
  });

  it("repairs historical thin or thick wording for regular-only accessories", () => {
    expect(detailSteps(
      ["佩戴黑色薄款窄框墨镜"],
      [{
        variant_type: "窄框墨镜", color_name: "黑色", thickness: "thin",
        functional_icon_key: "sunglasses", asset_key: "acc_glasses",
      }],
    )).toEqual(["佩戴黑色常规窄框墨镜"]);
  });
});

describe("recommendation save payload", () => {
  it("preserves the generated outfit and its weather range", () => {
    const recommendation = {
      label: "清爽通勤风", audience: "mens", scene: "commute", items: [{ slot: "top", functional_icon_key: "short_sleeve", variant_type: "短袖", color_name: "白色", thickness: "thin", asset_key: "top_tshirt_short" }],
      constraints: { apparent_min: 19, apparent_max: 32 },
      season: "summer", style_tags: ["minimal", "sport"],
    } as BackendRecommendation;
    const guide = { formula: "短袖", steps: ["穿短袖"], styling_points: [], weather_note: "注意温差", substitute: "同版型即可" } as ReplicationGuide;

    expect(recommendationSavePayload(recommendation, guide, null, true)).toMatchObject({
      label: "清爽通勤风", scene_ids: ["commute"], season: "summer", style_tags: ["minimal", "sport"], suitable_min: 19, suitable_max: 32, in_pool: true, replication_guide: guide,
    });
  });
});
