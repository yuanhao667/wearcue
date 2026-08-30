import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
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
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.locate.mockResolvedValue({ id: "geo-39.9-116.4", name: "朝阳区", admin1: "北京市", country: "中国", latitude: 39.9, longitude: 116.4, timezone: "Asia/Shanghai" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true, user: { id: "u1", nickname: "小明", gender: "mens" } }) }));
  });

  it("blocks login and shakes until real location permission is granted", async () => {
    render(<LoginApp />);
    fireEvent.change(screen.getByPlaceholderText("怎么称呼你？"), { target: { value: "小明" } });
    fireEvent.click(screen.getByRole("button", { name: "男士" }));
    fireEvent.change(screen.getByPlaceholderText("输入邀请码"), { target: { value: "INVITE" } });

    fireEvent.click(screen.getByRole("button", { name: /进入我的/ }));
    expect(fetch).not.toHaveBeenCalled();
    expect(screen.getByText("允许访问位置和天气").closest("label")).toHaveClass("is-shaking");

    fireEvent.click(screen.getByRole("checkbox", { name: /允许访问位置和天气/ }));
    await waitFor(() => expect(screen.getByRole("checkbox", { name: /允许访问位置和天气/ })).toBeChecked());
    fireEvent.click(screen.getByRole("button", { name: /进入我的/ }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    expect(mocks.save).toHaveBeenCalledTimes(1);
    expect(mocks.replace).toHaveBeenCalledWith("/");
  });
});
