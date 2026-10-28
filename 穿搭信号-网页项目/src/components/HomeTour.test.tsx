import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { HomeTour } from "./HomeTour";

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  document.body.innerHTML = '<button id="home-tour-profile">设置</button><button id="home-tour-detail">查看穿搭方案</button><div id="home-tour-items" tabindex="-1"></div>';
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ left: 200, top: 400, right: 800, bottom: 520, width: 600, height: 120, x: 200, y: 400, toJSON() {} });
  vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockReturnValue(350);
  vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(210);
});
afterEach(() => { cleanup(); document.body.innerHTML = ""; vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("waits for recommendations, centers the first bubble and arrow, and completes all three steps", async () => {
  const view = render(<HomeTour accountKey="one" ready={false} />);
  expect(screen.queryByRole("dialog")).toBeNull();
  view.rerender(<HomeTour accountKey="one" ready />);
  const dialog = await screen.findByRole("dialog", { name: "今天穿这些" });
  expect(dialog.style.left).toBe("325px");
  expect(dialog.style.getPropertyValue("--arrow-x")).toBe("175px");
  fireEvent.click(screen.getByRole("button", { name: "下一步 →" }));
  expect(screen.getByRole("dialog", { name: "看看怎么搭" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "上一步" }));
  expect(screen.getByRole("dialog", { name: "今天穿这些" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "下一步 →" }));
  fireEvent.click(screen.getByRole("button", { name: "下一步 →" }));
  expect(screen.getByRole("dialog", { name: "让推荐更适合你" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "知道了 ✓" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(localStorage.getItem("wearcue_home_tour_v1:one")).toBe("done");
  expect(document.activeElement).toBe(document.getElementById("home-tour-profile"));
  view.unmount();
  render(<HomeTour accountKey="one" ready />);
  expect(screen.queryByRole("dialog")).toBeNull();
});

it("remembers skipping per account, without suppressing a different account", async () => {
  const first = render(<HomeTour accountKey="one" ready />);
  await screen.findByRole("dialog");
  fireEvent.click(screen.getByRole("button", { name: "跳过引导" }));
  expect(localStorage.getItem("wearcue_home_tour_v1:one")).toBe("done");
  first.unmount();
  render(<HomeTour accountKey="two" ready />);
  await screen.findByRole("dialog");
  fireEvent.keyDown(window, { key: "Escape" });
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(localStorage.getItem("wearcue_home_tour_v1:two")).toBe("done");
});

it("does not display without a logged-in account", () => {
  render(<HomeTour accountKey="" ready />);
  expect(screen.queryByRole("dialog")).toBeNull();
});
