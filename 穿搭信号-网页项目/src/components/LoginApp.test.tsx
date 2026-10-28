import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LoginApp } from "./LoginApp";

const mocks = vi.hoisted(() => ({ locate: vi.fn(), replace: vi.fn(), save: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: mocks.replace }) }));
vi.mock("@/lib/browser-location", () => ({
  locateCurrentDistrict: mocks.locate,
  saveLoginLocation: mocks.save,
}));

describe("LoginApp email account flow", () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mocks.locate.mockResolvedValue({ id: "geo-39.9-116.4", name: "朝阳区", admin1: "北京市", country: "中国", latitude: 39.9, longitude: 116.4, timezone: "Asia/Shanghai" });
  });

  it("logs in with email and password without asking for the invitation again", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, user: { id: "u1", nickname: "小明", gender: "mens", profileCompleted: true } }),
    }));
    render(<LoginApp />);
    fireEvent.click(screen.getByRole("tab", { name: "登录" }));
    expect(screen.queryByPlaceholderText("输入邀请码")).not.toBeInTheDocument();
    expect(screen.queryByText("允许访问位置和天气")).not.toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("name@example.com"), { target: { value: "me@example.com" } });
    fireEvent.change(screen.getByPlaceholderText("至少 8 位字符"), { target: { value: "safe-password" } });
    fireEvent.click(screen.getByRole("button", { name: "登录 WearCue" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    expect(fetch).toHaveBeenCalledWith("/api/auth/login", expect.objectContaining({
      body: JSON.stringify({ mode: "login", email: "me@example.com", password: "safe-password" }),
    }));
    expect(mocks.replace).toHaveBeenCalledWith("/");
    expect(JSON.parse(localStorage.getItem("wearcue_profile_v1") || "{}")).toMatchObject({ nickname: "小明", gender: "mens" });
  });

  it("verifies email first, then requires gender and location before completing the profile", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ ok: true, retry_after: 60, dev_code: "123456" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ ok: true, user: { id: "u2", nickname: "new", gender: "mens", profileCompleted: false } }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ audience: "womens" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ user: { id: "u2", nickname: "新名字", audience: "womens", profile_completed: true } }) });
    vi.stubGlobal("fetch", fetchMock);
    render(<LoginApp />);
    expect(screen.queryByPlaceholderText("怎么称呼你？")).not.toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("name@example.com"), { target: { value: "new@example.com" } });
    fireEvent.change(screen.getByPlaceholderText("至少 8 位字符"), { target: { value: "safe-password" } });
    fireEvent.change(screen.getByPlaceholderText("输入邀请码"), { target: { value: "NEW-CODE" } });
    fireEvent.click(screen.getByRole("button", { name: "获取验证码" }));
    await waitFor(() => expect(screen.getByPlaceholderText("6 位验证码")).toHaveValue("123456"));
    fireEvent.click(screen.getByRole("button", { name: "验证并注册" }));

    await waitFor(() => expect(screen.getByPlaceholderText("怎么称呼你？")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/auth/login", expect.objectContaining({
      body: JSON.stringify({ mode: "register", email: "new@example.com", password: "safe-password", inviteCode: "NEW-CODE", verificationCode: "123456" }),
    }));
    fireEvent.change(screen.getByPlaceholderText("怎么称呼你？"), { target: { value: "新名字" } });
    expect(screen.getByRole("group", { name: "性别" })).toBeInTheDocument();
    expect(screen.queryByText("穿搭偏好")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "保存并进入" }));
    expect(screen.getByRole("alert")).toHaveTextContent("请选择性别");
    fireEvent.click(screen.getByRole("button", { name: "女士" }));
    expect(screen.getByRole("checkbox", { name: /允许访问位置和天气/ })).not.toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "保存并进入" }));
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.getByText("允许访问位置和天气").closest("label")).toHaveClass("is-shaking");
    fireEvent.click(screen.getByRole("checkbox", { name: /允许访问位置和天气/ }));
    await waitFor(() => expect(screen.getByRole("checkbox", { name: /允许访问位置和天气/ })).toBeChecked());
    fireEvent.click(screen.getByRole("button", { name: "保存并进入" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/backend/settings", expect.objectContaining({
      body: JSON.stringify({ city_id: "geo-39.9-116.4", city_name: "朝阳区", latitude: 39.9, longitude: 116.4, timezone: "Asia/Shanghai", audience: "womens" }),
    }));
    expect(fetchMock).toHaveBeenLastCalledWith("/api/auth/onboarding", expect.objectContaining({
      body: JSON.stringify({ nickname: "新名字", audience: "womens" }),
    }));
    expect(mocks.save).toHaveBeenCalledTimes(1);
    expect(mocks.replace).toHaveBeenCalledWith("/");
  });

  it("does not complete onboarding or navigate when location permission is denied", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    mocks.locate.mockRejectedValue(new Error("请允许浏览器获取位置"));
    render(<LoginApp initialUser={{ id: "pending", nickname: "", gender: "mens", profileCompleted: false }} />);
    fireEvent.change(screen.getByPlaceholderText("怎么称呼你？"), { target: { value: "小明" } });
    fireEvent.click(screen.getByRole("button", { name: "男士" }));
    fireEvent.click(screen.getByRole("checkbox", { name: /允许访问位置和天气/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("请允许浏览器获取位置");
    expect(screen.getByRole("checkbox", { name: /允许访问位置和天气/ })).not.toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "保存并进入" }));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(mocks.replace).not.toHaveBeenCalled();
    expect(mocks.save).not.toHaveBeenCalled();
  });

  it("prevents repeated submission and switching views while login is pending", async () => {
    let resolveRequest!: (value: unknown) => void;
    const fetchMock = vi.fn(() => new Promise((resolve) => { resolveRequest = resolve; }));
    vi.stubGlobal("fetch", fetchMock);
    render(<LoginApp />);
    fireEvent.click(screen.getByRole("tab", { name: "登录" }));
    fireEvent.change(screen.getByPlaceholderText("name@example.com"), { target: { value: "me@example.com" } });
    fireEvent.change(screen.getByPlaceholderText("至少 8 位字符"), { target: { value: "safe-password" } });
    const submit = screen.getByRole("button", { name: "登录 WearCue" });
    fireEvent.submit(submit.closest("form")!);
    fireEvent.submit(submit.closest("form")!);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("tab", { name: "注册" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "忘记密码？" })).toBeDisabled();
    expect(screen.getByPlaceholderText("name@example.com")).toBeDisabled();
    resolveRequest({ ok: false, json: async () => ({ error: "邮箱或密码错误" }) });
    expect(await screen.findByRole("alert")).toHaveTextContent("邮箱或密码错误");
    expect(screen.getByRole("button", { name: "登录 WearCue" })).toBeEnabled();
  });

  it.each([
    [new DOMException("Timed out", "TimeoutError"), "请求超时，请检查网络后重试"],
    [new TypeError("Failed to fetch"), "网络连接失败，请检查网络后重试"],
  ])("recovers from request failure with a useful message: %s", async (reason, message) => {
    const fetchMock = vi.fn().mockRejectedValue(reason);
    vi.stubGlobal("fetch", fetchMock);
    render(<LoginApp />);
    fireEvent.click(screen.getByRole("tab", { name: "登录" }));
    fireEvent.change(screen.getByPlaceholderText("name@example.com"), { target: { value: "me@example.com" } });
    fireEvent.change(screen.getByPlaceholderText("至少 8 位字符"), { target: { value: "safe-password" } });
    fireEvent.click(screen.getByRole("button", { name: "登录 WearCue" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(fetchMock.mock.calls[0][1].signal).toBeInstanceOf(AbortSignal);
    expect(screen.getByRole("button", { name: "登录 WearCue" })).toBeEnabled();
    expect(screen.getByPlaceholderText("name@example.com")).toHaveValue("me@example.com");
    expect(mocks.replace).not.toHaveBeenCalled();
  });

  it("keeps resumed onboarding blocked without location permission", () => {
    const fetchMock = vi.fn(); vi.stubGlobal("fetch", fetchMock);
    render(<LoginApp initialUser={{ id: "pending", nickname: "", gender: "mens", profileCompleted: false }} />);
    fireEvent.change(screen.getByPlaceholderText("怎么称呼你？"), { target: { value: "小明" } });
    fireEvent.click(screen.getByRole("button", { name: "男士" }));
    fireEvent.click(screen.getByRole("button", { name: "保存并进入" }));
    expect(screen.getByRole("alert")).toHaveTextContent("请先允许访问位置和天气");
    expect(fetchMock).not.toHaveBeenCalled();
    expect(mocks.replace).not.toHaveBeenCalled();
  });
});
