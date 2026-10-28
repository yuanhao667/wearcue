import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("@/lib/backend-api", () => ({ apiJson: mocks.api, apiAsset: (path: string) => `/api/backend${path}` }));
import { OutfitDetailApp } from "./OutfitDetailApp";

afterEach(() => { cleanup(); vi.clearAllMocks(); localStorage.clear(); });

const guide = { formula: "灰色卫衣", steps: ["穿灰色卫衣"], styling_points: [], weather_note: "按体感调整", substitute: "同版型替换" };

it.each(["image", "advice"])("preserves the successful part when %s generation fails and supports retry", async (failed) => {
  localStorage.setItem("wearcue_active_outfit_v1", JSON.stringify({
    template_id: "test-detail", source: "ai", label: "灰色卫衣", scene: "commute", audience: "mens", constraints: {},
    items: [{ slot: "top", functional_icon_key: "long_sleeve", asset_key: "top_tshirt_long", variant_type: "卫衣", color_name: "灰色", thickness: "regular" }],
  }));
  let attempts = 0;
  mocks.api.mockImplementation((path: string) => {
    if (path.startsWith("/outfits/")) return Promise.reject(new Error("not saved"));
    attempts += 1;
    return Promise.resolve({
      ...(attempts === 1 && failed === "advice" ? { advice_error: "建议暂未生成" } : { replication_guide: guide, outfit_analysis: { summary: "搭配分析", structure_points: [], completion_advice: [] } }),
      ...(attempts === 1 && failed === "image" ? { image_url: null, image_error: "图片暂未生成" } : { image_url: "/recommendations/test-detail/image" }),
      ai_quota: { limit: 6, used: 1, remaining: 5 },
    });
  });
  render(<OutfitDetailApp id="test-detail" origin="home" />);
  await screen.findByRole("button", { name: "重新尝试生成" });
  if (failed === "image") {
    expect(screen.getByText("搭配分析")).toBeInTheDocument();
    expect(screen.queryByAltText("灰色卫衣穿搭参考")).not.toBeInTheDocument();
  } else {
    expect(screen.getByAltText("灰色卫衣穿搭参考")).toBeInTheDocument();
    expect(screen.getByText("建议暂未生成")).toBeInTheDocument();
  }
  fireEvent.click(screen.getByRole("button", { name: "重新尝试生成" }));
  await waitFor(() => expect(screen.queryByRole("button", { name: "重新尝试生成" })).not.toBeInTheDocument());
  expect(attempts).toBe(2);
  expect(screen.getByAltText("灰色卫衣穿搭参考")).toBeInTheDocument();
  expect(screen.getByText("搭配分析")).toBeInTheDocument();
});
