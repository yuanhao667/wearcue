import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LoginApp } from "./LoginApp";

const mocks = vi.hoisted(() => ({
  locate: vi.fn(),
  replace: vi.fn(),
  save: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: mocks.replace }) }));
vi.mock("@/lib/browser-location", () => ({
  locateCurrentDistrict: mocks.locate,
  saveLoginLocation: mocks.save,
}));

describe("LoginApp location consent", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mocks.locate.mockResolvedValue({ id: "geo-39.9-116.4", name: "朝阳区", admin1: "北京市", country: "中国", latitude: 39.9, longitude: 116.4, timezone: "Asia/Shanghai" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true, user: { id: "u1", nickname: "小明", gender: "mens" } }) }));
  });

  it("blocks login and shakes until real location permission is granted", async () => {
    render(<LoginApp />);
    fireEvent.click(screen.getByRole("tab", { name: "登录" }));
    const permission = screen.getByText("允许访问位置和天气").closest("label");
    const submit = screen.getByRole("button", { name: "登录 WearCue" });
    expect(permission).not.toBeNull();
    expect(permission!.compareDocumentPosition(submit) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByText(/进入后直接读取|已允许/)).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText("怎么称呼你？")).not.toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("输入注册时使用的邀请码"), { target: { value: "INVITE" } });

    fireEvent.click(submit);
    expect(fetch).not.toHaveBeenCalled();
    expect(screen.getByText("允许访问位置和天气").closest("label")).toHaveClass("is-shaking");

    fireEvent.click(screen.getByRole("checkbox", { name: /允许访问位置和天气/ }));
    await waitFor(() => expect(screen.getByRole("checkbox", { name: /允许访问位置和天气/ })).toBeChecked());
    expect(screen.queryByText(/已允许/)).not.toBeInTheDocument();
    fireEvent.click(submit);

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    expect(fetch).toHaveBeenCalledWith("/api/auth/login", expect.objectContaining({
      body: JSON.stringify({ mode: "login", inviteCode: "INVITE" }),
    }));
    expect(mocks.save).toHaveBeenCalledTimes(1);
    expect(mocks.replace).toHaveBeenCalledWith("/");
    expect(JSON.parse(localStorage.getItem("wearcue_profile_v1") || "{}")).toMatchObject({
      nickname: "小明", gender: "mens",
    });
  });

  it("collects nickname and gender only on the registration tab", async () => {
    render(<LoginApp />);
    expect(screen.getByRole("tab", { name: "注册" })).toHaveAttribute("aria-selected", "true");
    fireEvent.change(screen.getByPlaceholderText("怎么称呼你？"), { target: { value: "新名字" } });
    fireEvent.click(screen.getByRole("button", { name: "女士" }));
    fireEvent.change(screen.getByPlaceholderText("输入邀请码"), { target: { value: "NEW-CODE" } });
    fireEvent.click(screen.getByRole("checkbox", { name: /允许访问位置和天气/ }));
    await waitFor(() => expect(screen.getByRole("checkbox", { name: /允许访问位置和天气/ })).toBeChecked());
    fireEvent.click(screen.getByRole("button", { name: "注册并进入" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    expect(fetch).toHaveBeenCalledWith("/api/auth/login", expect.objectContaining({
      body: JSON.stringify({ mode: "register", nickname: "新名字", gender: "womens", inviteCode: "NEW-CODE" }),
    }));
  });
});
