import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Outfit, StyleId } from "@/domain/backend";
const mocks = vi.hoisted(() => ({ api: vi.fn(), clear: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/backend-api", () => ({ apiJson: mocks.api, apiAsset: (path: string) => path }));
vi.mock("@/lib/today-session", () => ({ clearTodaySession: mocks.clear }));
import { LibraryApp } from "./LibraryApp";
afterEach(() => { cleanup(); sessionStorage.clear(); vi.clearAllMocks(); });

const sortingOutfits: Outfit[] = [
  { id: "minimal", label: "简约衬衫", source: "system", style_tags: ["minimal"] },
  { id: "personal", label: "个人潮流搭配", source: "manual", style_tags: ["street"] },
  { id: "sport", label: "休闲运动套装", source: "system", style_tags: ["sport", "casual"] },
  { id: "street", label: "潮流牛仔搭配", source: "system", style_tags: ["street"] },
  { id: "outdoor", label: "户外冲锋衣", source: "system", style_tags: ["outdoor"] },
].map((outfit) => ({
  ...outfit, audience: "womens", components: [], scene_ids: ["commute"], season: "spring-autumn",
  suitable_min: 10, suitable_max: 25, favorite: false, in_pool: false, skip_count: 0, created_at: "", updated_at: "",
})) as Outfit[];

it("immediately puts preferred system styles first after saving, preserving both groups and the collection order", async () => {
  let settings = { audience: "womens", preferred_styles: [] as StyleId[], style_preferences_set: false };
  mocks.api.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path !== "/settings") return sortingOutfits;
    if (init?.method === "POST") settings = { ...settings, ...JSON.parse(String(init.body)), style_preferences_set: true };
    return settings;
  });
  const view = render(<LibraryApp />);
  await screen.findByRole("heading", { name: "选择你喜欢的风格类型" });
  fireEvent.click(screen.getByRole("button", { name: "休闲" }));
  fireEvent.click(screen.getByRole("button", { name: "潮流" }));
  fireEvent.click(screen.getByRole("button", { name: "保存并进入穿搭灵感" }));
  await screen.findByLabelText("穿搭筛选");
  const labels = () => screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent);
  const expected = ["休闲运动套装", "潮流牛仔搭配", "简约衬衫", "个人潮流搭配", "户外冲锋衣"];
  expect(labels()).toEqual(expected);
  fireEvent.click(screen.getByRole("tab", { name: "收藏穿搭5套" }));
  expect(labels()).toEqual(sortingOutfits.map((outfit) => outfit.label));
  view.unmount();
  render(<LibraryApp />);
  await screen.findByLabelText("穿搭筛选");
  expect(labels()).toEqual(expected);
});

it("keeps the original order after skipping style selection", async () => {
  let settings = { audience: "womens", preferred_styles: [], style_preferences_set: false };
  mocks.api.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path !== "/settings") return sortingOutfits;
    if (init?.method === "POST") settings = { ...settings, ...JSON.parse(String(init.body)), style_preferences_set: true };
    return settings;
  });
  render(<LibraryApp />);
  fireEvent.click(await screen.findByRole("button", { name: "跳过" }));
  await screen.findByLabelText("穿搭筛选");
  expect(screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent)).toEqual(sortingOutfits.map((outfit) => outfit.label));
});

it("shows first-visit choices, saves preferences and marks only liked filter names", async () => {
  let settings = { audience: "womens", preferred_styles: [] as string[], style_preferences_set: false };
  mocks.api.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path !== "/settings") return [];
    if (init?.method === "POST") settings = { ...settings, ...JSON.parse(String(init.body)), style_preferences_set: true };
    return settings;
  });
  const view = render(<LibraryApp />);
  await screen.findByRole("heading", { name: "选择你喜欢的风格类型" });
  fireEvent.click(screen.getByRole("button", { name: "简约" }));
  fireEvent.click(screen.getByRole("button", { name: "休闲" }));
  fireEvent.click(screen.getByRole("button", { name: "保存并进入穿搭灵感" }));
  await screen.findByLabelText("穿搭筛选");
  expect(screen.getByRole("button", { name: "简约" }).querySelector(".discovery-style-heart")).not.toBeNull();
  expect(screen.getByRole("button", { name: "运动" }).querySelector(".discovery-style-heart")).toBeNull();
  expect(mocks.clear).toHaveBeenCalled();
  view.unmount();
  render(<LibraryApp />);
  await screen.findByLabelText("穿搭筛选");
  expect(screen.queryByRole("heading", { name: "选择你喜欢的风格类型" })).toBeNull();
});

it("does not silently bypass onboarding when loading settings fails", async () => {
  mocks.api.mockRejectedValueOnce(new Error("network")).mockResolvedValue([]);
  render(<LibraryApp />);
  await waitFor(() => expect(screen.getByRole("button", { name: "重新加载" })).toBeInTheDocument());
  expect(screen.queryByLabelText("穿搭筛选")).toBeNull();
});


it("uses a text loading status without the old white skeleton blocks", () => {
  mocks.api.mockImplementation(() => new Promise(() => {}));
  const { container } = render(<LibraryApp />);
  expect(screen.getByRole("status")).toHaveTextContent("正在加载穿搭灵感");
  expect(container.querySelector(".paper-loading")).toBeNull();
});
