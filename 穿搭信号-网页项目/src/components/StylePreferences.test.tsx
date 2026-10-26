import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { StylePreferences } from "./StylePreferences";

afterEach(cleanup);

it("explains settings styles on hover or focus, dismisses with Escape, and does not save", () => {
  const save = vi.fn();
  render(<StylePreferences embedded audience="mens" selected={[]} onSave={save} />);
  const card = screen.getByRole("button", { name: "运动" });
  fireEvent.mouseEnter(card);
  expect(screen.getByRole("tooltip")).toHaveTextContent("随季节调整层次");
  expect(card).toHaveAttribute("aria-describedby", screen.getByRole("tooltip").id);
  fireEvent.mouseLeave(card);
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  fireEvent.focus(card);
  expect(screen.getByRole("tooltip")).toBeInTheDocument();
  fireEvent.keyDown(card, { key: "Escape" });
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  expect(save).not.toHaveBeenCalled();
});

it("keeps the explanation row in layout while hiding it when no styles are selected", () => {
  const { container } = render(<StylePreferences onboarding audience="mens" selected={[]} onSave={vi.fn()} />);
  const explanation = container.querySelector(".style-preferences-actions > span");
  expect(explanation).toBeInTheDocument();
  expect(explanation).not.toBeVisible();
  expect(explanation).toHaveStyle({ visibility: "hidden" });
  fireEvent.click(screen.getByRole("button", { name: "休闲" }));
  expect(screen.getByText("已选择 1 种风格，可在设置中更改")).toBe(explanation);
  expect(explanation).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "休闲" }));
  expect(container.querySelector(".style-preferences-actions > span")).toBe(explanation);
  expect(explanation).not.toBeVisible();
});

it("uses the same gender-specific photos, allows all five and empty preferences, and saves only on confirmation", async () => {
  const save = vi.fn().mockResolvedValue(true);
  const view = render(<StylePreferences onboarding audience="mens" selected={[]} onSave={save} />);
  const cards = screen.getAllByRole("button", { pressed: false });
  expect(cards).toHaveLength(5);
  expect(screen.getAllByRole("img").every((image) => image.getAttribute("src")?.includes("/mens-"))).toBe(true);
  cards.forEach((card) => fireEvent.click(card));
  expect(screen.getAllByRole("button", { pressed: true })).toHaveLength(5);
  expect(save).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "保存并进入穿搭灵感" }));
  await waitFor(() => expect(save).toHaveBeenCalledWith(["minimal", "casual", "street", "sport", "outdoor"]));
  await waitFor(() => expect(screen.getAllByRole("button", { pressed: false })).toHaveLength(5));
  view.rerender(<StylePreferences onboarding audience="womens" selected={[]} onSave={save} />);
  expect(screen.getAllByRole("img").every((image) => image.getAttribute("src")?.includes("/womens-"))).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "保存并进入穿搭灵感" }));
  await waitFor(() => expect(save).toHaveBeenLastCalledWith([]));
});

it("retains adjacent choices on a failed save, then supports retry", async () => {
  const save = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValue(true);
  render(<StylePreferences audience="womens" selected={[]} onSave={save} />);
  expect(screen.getByRole("button", { name: "保存风格偏好" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "简约" }));
  fireEvent.click(screen.getByRole("button", { name: "休闲" }));
  fireEvent.click(screen.getByRole("button", { name: "保存风格偏好" }));
  await screen.findByRole("alert");
  expect(screen.getAllByRole("button", { pressed: true })).toHaveLength(2);
  fireEvent.click(screen.getByRole("button", { name: "保存风格偏好" }));
  await waitFor(() => expect(save).toHaveBeenCalledTimes(2));
  expect(save).toHaveBeenLastCalledWith(["minimal", "casual"]);
});


it("skips onboarding with no style restriction even when cards were selected", async () => {
  const save = vi.fn().mockResolvedValue(true);
  const { container } = render(<StylePreferences onboarding audience="mens" selected={[]} onSave={save} />);
  expect(container.querySelector(".style-preference-heart")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "潮流" }));
  fireEvent.click(screen.getByRole("button", { name: "跳过" }));
  await waitFor(() => expect(save).toHaveBeenCalledWith([]));
});


it("autosaves embedded deselection and retains unsaved choices with a retry on failure", async () => {
  const save = vi.fn().mockResolvedValueOnce(false).mockResolvedValueOnce(true);
  render(<StylePreferences embedded audience="mens" selected={["minimal"]} onSave={save} />);
  expect(screen.queryByRole("button", { name: "保存风格偏好" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "简约" }));
  await screen.findByRole("alert");
  expect(save).toHaveBeenCalledWith([]);
  expect(screen.getByRole("button", { name: "简约" })).toHaveAttribute("aria-pressed", "false");
  fireEvent.click(screen.getByRole("button", { name: "重试保存" }));
  await waitFor(() => expect(save).toHaveBeenCalledTimes(2));
  expect(save).toHaveBeenLastCalledWith([]);
  await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
});
