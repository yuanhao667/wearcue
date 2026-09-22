import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ logout: vi.fn() }));
vi.mock("@/lib/client-auth", () => ({ logoutAndRedirect: mocks.logout }));
import { ChangePassword } from "./ChangePassword";

beforeEach(() => {
  mocks.logout.mockReset();
  // jsdom does not implement the native dialog lifecycle.
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute("open", ""); } });
  Object.defineProperty(HTMLDialogElement.prototype, "close", { configurable: true, value: function (this: HTMLDialogElement) { this.removeAttribute("open"); this.dispatchEvent(new Event("close")); } });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function open() {
  render(<ChangePassword email="member@example.com" />);
  fireEvent.click(screen.getByRole("button", { name: "修改密码" }));
}
function fill(password = "new-password", confirmation = password) {
  fireEvent.change(screen.getByLabelText("邮箱验证码"), { target: { value: "123456" } });
  fireEvent.change(screen.getByLabelText("新密码", { exact: true }), { target: { value: password } });
  fireEvent.change(screen.getByLabelText("确认新密码"), { target: { value: confirmation } });
}
function submit() { fireEvent.click(screen.getByRole("button", { name: "确认修改密码" })); }

it("locks the bound email and sends reset codes only on request with a cooldown", async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json({ ok: true, retry_after: 60 }));
  vi.stubGlobal("fetch", fetch);
  open();
  expect(screen.getByLabelText("绑定邮箱")).toHaveValue("member@example.com");
  expect(screen.getByLabelText("绑定邮箱")).toHaveAttribute("readonly");
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "发送验证码" }));
  expect(await screen.findByRole("status")).toHaveTextContent("验证码已发送");
  expect(fetch).toHaveBeenCalledWith("/api/auth/email-code", expect.objectContaining({ body: JSON.stringify({ email: "member@example.com", purpose: "reset" }) }));
  expect(screen.getByRole("button", { name: "60 秒后重发" })).toBeDisabled();
});

it("validates code, password length and confirmation before contacting the server", () => {
  const fetch = vi.fn(); vi.stubGlobal("fetch", fetch); open();
  submit(); expect(screen.getByRole("alert")).toHaveTextContent("6 位邮箱验证码");
  fill("short"); submit(); expect(screen.getByRole("alert")).toHaveTextContent("8–128");
  fill("new-password", "other-password"); submit(); expect(screen.getByRole("alert")).toHaveTextContent("不一致");
  expect(fetch).not.toHaveBeenCalled();
});

it("keeps the form usable after an invalid code and does not log out", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ error: "邮箱验证码无效或已过期" }, { status: 422 })));
  open(); fill(); submit();
  expect(await screen.findByRole("alert")).toHaveTextContent("邮箱验证码无效或已过期");
  expect(screen.getByRole("button", { name: "确认修改密码" })).toBeEnabled();
  expect(mocks.logout).not.toHaveBeenCalled();
});

it("submits once and clears the current session only after a successful password change", async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json({ ok: true }));
  vi.stubGlobal("fetch", fetch); open(); fill(); submit();
  await waitFor(() => expect(mocks.logout).toHaveBeenCalledOnce());
  expect(fetch).toHaveBeenCalledExactlyOnceWith("/api/auth/reset-password", expect.objectContaining({ body: JSON.stringify({ email: "member@example.com", verificationCode: "123456", password: "new-password" }) }));
  expect(screen.getByLabelText("新密码", { exact: true })).toHaveValue("");
});

it("reports delivery errors and allows retrying", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("邮箱服务暂时不可用")));
  open(); fireEvent.click(screen.getByRole("button", { name: "发送验证码" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("邮箱服务暂时不可用");
  expect(screen.getByRole("button", { name: "发送验证码" })).toBeEnabled();
});

it("clears secret inputs when the dialog is closed", () => {
  open(); fill();
  expect(screen.getByRole("button", { name: "关闭修改密码" })).toHaveClass("library-delete-close");
  expect(screen.getByRole("button", { name: "关闭修改密码" }).querySelector("svg")).toHaveAttribute("viewBox", "0 0 24 24");
  fireEvent.click(screen.getByRole("button", { name: "关闭修改密码" }));
  fireEvent.click(screen.getByRole("button", { name: "修改密码" }));
  expect(screen.getByLabelText("新密码", { exact: true })).toHaveValue("");
  expect(screen.getByLabelText("邮箱验证码")).toHaveValue("");
});
