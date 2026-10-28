import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Outfit } from "@/domain/backend";

const mocks = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/backend-api", () => ({ apiJson: mocks.api, apiAsset: (path: string) => path }));
import { LibraryApp } from "./LibraryApp";

afterEach(() => { cleanup(); sessionStorage.clear(); vi.clearAllMocks(); });

function outfit(id: string, label: string, color: string): Outfit {
  return {
    id, label, audience: "mens", source: "system", scene_ids: ["commute"], season: "spring-autumn", style_tags: ["minimal"],
    suitable_min: 10, suitable_max: 25, favorite: false, in_pool: false, skip_count: 0, created_at: "", updated_at: "",
    components: [{ slot: "top", color_name: color, functional_icon_key: "top", variant_type: "卫衣", thickness: "regular" }],
  };
}

it("filters garment colors locally, keeps tab counts in sync and clears only color", async () => {
  const gray = outfit("gray", "灰色卫衣", "炭灰色");
  const white = outfit("white", "白色衬衫", "白色");
  white.components.push({ slot: "equipment", color_name: "灰色", functional_icon_key: "bag", variant_type: "包", thickness: "regular" });
  mocks.api.mockImplementation(async (path: string) => path === "/settings" ? { audience: "mens", preferred_styles: [], style_preferences_set: true } : path.includes("tab=mine") ? [gray] : [gray, white]);
  render(<LibraryApp />);
  await screen.findByText("灰色卫衣");
  fireEvent.click(screen.getByRole("button", { name: "颜色：全部颜色" }));
  const palette = screen.getByRole("group", { name: "选择服装颜色" });
  expect(within(palette).queryByRole("textbox")).not.toBeInTheDocument();
  expect(within(palette).queryByRole("slider")).not.toBeInTheDocument();
  fireEvent.click(within(palette).getByRole("button", { name: "灰色" }));
  expect(screen.queryByText("白色衬衫")).not.toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "全部穿搭1套" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "收藏穿搭1套" })).toBeInTheDocument();
  expect(within(palette).getByRole("button", { name: "灰色" })).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(screen.getByRole("tab", { name: "收藏穿搭1套" }));
  expect(screen.getByText("灰色卫衣")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "颜色：灰色" })).toBeInTheDocument();
  expect(mocks.api).toHaveBeenCalledTimes(3);
  expect(screen.queryByRole("button", { name: "清除颜色筛选" })).not.toBeInTheDocument();
  fireEvent.pointerDown(document.body);
  fireEvent.click(screen.getByRole("button", { name: "颜色：灰色" }));
  fireEvent.click(screen.getByRole("button", { name: "全部颜色" }));
  fireEvent.click(screen.getByRole("tab", { name: "全部穿搭2套" }));
  expect(screen.getByText("白色衬衫")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "场景：全部场景" })).toBeInTheDocument();
  expect(mocks.api).toHaveBeenCalledTimes(3);
});

it("shows empty results, closes on Escape and outside click, and restores focus", async () => {
  mocks.api.mockImplementation(async (path: string) => path === "/settings" ? { audience: "mens", preferred_styles: [], style_preferences_set: true } : [outfit("white", "白色衬衫", "白色")]);
  render(<LibraryApp />);
  await screen.findByText("白色衬衫");
  fireEvent.click(screen.getByRole("button", { name: "颜色：全部颜色" }));
  const red = screen.getByRole("button", { name: "红色" });
  red.focus();
  fireEvent.click(red);
  expect(screen.getByText("当前筛选暂无穿搭")).toBeInTheDocument();
  fireEvent.keyDown(red, { key: "Escape" });
  expect(screen.queryByRole("group", { name: "选择服装颜色" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "颜色：红色" })).toHaveFocus();
  fireEvent.click(screen.getByRole("button", { name: "颜色：红色" }));
  fireEvent.click(screen.getByRole("button", { name: "全部颜色" }));
  expect(screen.getByText("白色衬衫")).toBeInTheDocument();
  fireEvent.pointerDown(document.body);
  expect(screen.queryByRole("group", { name: "选择服装颜色" })).not.toBeInTheDocument();
});

it("combines color with server filters and preserves them when clearing color", async () => {
  mocks.api.mockImplementation(async (path: string) => path === "/settings" ? { audience: "mens", preferred_styles: [], style_preferences_set: true } : [outfit("gray", "灰色卫衣", "灰色")]);
  render(<LibraryApp />);
  await screen.findByText("灰色卫衣");
  fireEvent.click(screen.getByRole("button", { name: "颜色：全部颜色" }));
  fireEvent.click(screen.getByRole("button", { name: "灰色" }));
  fireEvent.click(screen.getByRole("button", { name: "场景：全部场景" }));
  fireEvent.click(screen.getByRole("option", { name: "通勤" }));
  await waitFor(() => expect(mocks.api).toHaveBeenCalledWith(expect.stringContaining("scene=commute")));
  await screen.findByText("灰色卫衣");
  fireEvent.click(screen.getByRole("button", { name: "运动" }));
  await waitFor(() => expect(mocks.api).toHaveBeenCalledWith(expect.stringContaining("scene=commute&style=sport")));
  await screen.findByText("灰色卫衣");
  expect(screen.getByRole("button", { name: "颜色：灰色" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "颜色：灰色" }));
  fireEvent.click(screen.getByRole("button", { name: "全部颜色" }));
  expect(screen.getByRole("button", { name: "场景：通勤" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "运动" })).toHaveAttribute("aria-pressed", "true");
});


it("offers all five styles and filters casual/street while keeping season", async () => {
  mocks.api.mockImplementation(async (path: string) => path === "/settings" ? { audience: "mens", preferred_styles: [], style_preferences_set: true } : [outfit("gray", "灰色卫衣", "灰色")]);
  render(<LibraryApp />);
  await screen.findByText("灰色卫衣");
  for (const label of ["全部", "简约", "休闲", "潮流", "运动", "户外"]) {
    expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
  }
  for (const [label, style] of [["休闲", "casual"], ["潮流", "street"]]) {
    fireEvent.click(screen.getByRole("button", { name: label }));
    await waitFor(() => expect(mocks.api).toHaveBeenCalledWith(expect.stringContaining(`style=${style}`)));
    await screen.findByText("灰色卫衣");
    expect(screen.getByRole("button", { name: label })).toHaveAttribute("aria-pressed", "true");
  }
  fireEvent.click(screen.getByRole("button", { name: "全部" }));
  await waitFor(() => expect(mocks.api.mock.calls.slice(-3).every(([url]) => !url.includes("style="))).toBe(true));
});
