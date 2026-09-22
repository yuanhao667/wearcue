import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ logout: vi.fn(), api: vi.fn() }));
vi.mock("@/lib/backend-api", () => ({ apiJson: mocks.api }));
vi.mock("@/lib/client-auth", () => ({ logoutAndRedirect: mocks.logout }));
import { SettingsApp } from "./SettingsApp";
afterEach(cleanup);

it("keeps logout available when settings cannot load", async () => {
  mocks.api.mockRejectedValue(new Error("后端不可用"));
  render(<SettingsApp />);
  await screen.findByText("设置暂时打不开");
  expect(screen.getByRole("button", { name: "退出登录" }).closest("section")?.parentElement).toHaveClass("settings-paper-grid");
  fireEvent.click(screen.getByRole("button", { name: "退出登录" }));
  expect(mocks.logout).toHaveBeenCalledOnce();
});

it("groups preferences and system settings while keeping the account card in a grid", async () => {
  mocks.api.mockImplementation(async (path: string) => path === "/auth/me"
    ? { user: { id: "layout-test" } }
    : { city_name: "北京市", timezone: "Asia/Shanghai", height_group: "适中", weight_group: "适中", cold_offset: 0, audience: "womens", reminder_enabled: false });
  const { container } = render(<SettingsApp />);
  await screen.findByText("常用城市");
  const preferences = screen.getByRole("region", { name: "偏好设置" });
  const system = screen.getByRole("region", { name: "系统设置" });
  expect(screen.queryByRole("heading", { name: "偏好设置" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "系统设置" })).not.toBeInTheDocument();
  const grid = system.querySelector(".settings-paper-grid");
  const account = container.querySelector(".settings-account-card");
  expect(account?.parentElement).toBe(grid);
  expect(grid?.lastElementChild).toBe(account);
  expect(grid?.children).toHaveLength(2);
  expect(preferences.querySelector(".settings-paper-grid")?.children).toHaveLength(3);
  expect(preferences.querySelector(".settings-paper-grid")?.firstElementChild).toHaveClass("basic-info-card");
  for (const name of ["基本信息", "常用城市", "冷热偏好"]) {
    expect(within(preferences).getByRole("heading", { name })).toBeInTheDocument();
  }
  expect(within(system).getByRole("heading", { name: "晨间提醒" })).toBeInTheDocument();
  expect(within(system).getByRole("button", { name: "退出登录" })).toBeInTheDocument();
  expect(container.querySelectorAll(".settings-account-card")).toHaveLength(1);
  expect(screen.queryByText(/已绑定邮箱/)).not.toBeInTheDocument();
});

it("keeps height and weight sliders and registration gender icons inside basic information", async () => {
  mocks.api.mockClear();
  mocks.api.mockImplementation(async (path: string) => path === "/auth/me"
    ? { user: { id: "body-test" } }
    : { city_name: "北京市", timezone: "Asia/Shanghai", height_group: "中等", weight_group: "中等", cold_offset: 0, audience: "womens", reminder_enabled: false });
  render(<SettingsApp />);
  const card = (await screen.findByRole("heading", { name: "基本信息" })).closest("section")!;
  const height = within(card).getByRole("group", { name: "身高" });
  const weight = within(card).getByRole("group", { name: "体重" });
  const clothing = within(card).getByRole("group", { name: "性别与服饰" });
  expect(within(clothing).getAllByRole("radio")).toHaveLength(2);
  expect(card.querySelectorAll(".basic-info-choice")).toHaveLength(2);
  expect(clothing.querySelectorAll("svg.login-gender-icon")).toHaveLength(2);
  expect(within(card).getAllByRole("slider")).toHaveLength(2);
  const heightSlider = within(height).getByRole("slider", { name: "身高" });
  const weightSlider = within(weight).getByRole("slider", { name: "体重" });
  expect(heightSlider).toHaveValue("1");
  expect(weightSlider).toHaveValue("1");
  expect(heightSlider).toHaveAttribute("min", "0");
  expect(heightSlider).toHaveAttribute("max", "2");
  expect(heightSlider).toHaveAttribute("step", "1");
  fireEvent.change(heightSlider, { target: { value: "2" } });
  expect(heightSlider).toHaveAttribute("aria-valuetext", "偏高");
  expect(weightSlider).toHaveValue("1");
  fireEvent.change(weightSlider, { target: { value: "0" } });
  await waitFor(() => expect(mocks.api).toHaveBeenCalledWith("/settings", {
    method: "POST", body: JSON.stringify({ height_group: "偏高", weight_group: "偏轻" }),
  }));
  fireEvent.click(within(clothing).getByRole("radio", { name: /男装\s*男士相关穿搭/ }));
  await waitFor(() => expect(mocks.api).toHaveBeenCalledWith("/settings", {
    method: "POST", body: JSON.stringify({ audience: "mens" }),
  }));
});

it("shows the current account's bound email inside the logout card", async () => {
  mocks.api.mockImplementation(async (path: string) => path === "/auth/me"
    ? { user: { id: "email-test", email: "member@example.com" } }
    : { city_name: "北京市", timezone: "Asia/Shanghai", height_group: "中等", weight_group: "中等", cold_offset: 0, audience: "womens", reminder_enabled: false });
  render(<SettingsApp />);
  const email = await screen.findByText("已绑定邮箱：member@example.com");
  const account = screen.getByRole("heading", { name: "退出当前账号" }).closest("section")!;
  expect(account).toContainElement(email);
  expect(email).toHaveStyle({ overflowWrap: "anywhere" });
  expect(within(account).getByRole("button", { name: "退出登录" })).toBeInTheDocument();
  const passwordButton = within(account).getByRole("button", { name: "修改密码" });
  expect(passwordButton.parentElement).toHaveClass("settings-account-actions");
  expect(passwordButton.parentElement).toBe(within(account).getByRole("button", { name: "退出登录" }).parentElement);
  expect(account.parentElement).toHaveClass("settings-paper-grid");
});
