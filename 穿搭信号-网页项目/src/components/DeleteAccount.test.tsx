import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ api: vi.fn(), logout: vi.fn() }));
vi.mock("@/lib/backend-api", () => ({ apiJson: mocks.api }));
vi.mock("@/lib/client-auth", () => ({ logoutAndRedirect: mocks.logout }));
import { DeleteAccount } from "./DeleteAccount";

beforeEach(() => {
  mocks.api.mockReset(); mocks.logout.mockReset();
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute("open", ""); } });
  Object.defineProperty(HTMLDialogElement.prototype, "close", { configurable: true, value: function (this: HTMLDialogElement) { this.removeAttribute("open"); this.dispatchEvent(new Event("close")); } });
});
afterEach(cleanup);

function open() {
  render(<DeleteAccount />);
  fireEvent.click(screen.getByRole("button", { name: "注销账户" }));
}
function fill() {
  fireEvent.change(screen.getByLabelText("当前密码"), { target: { value: "current-password" } });
  fireEvent.click(screen.getByRole("checkbox"));
}
function submit() { fireEvent.click(screen.getByRole("button", { name: "确认注销账户" })); }

it("opens a warning without deleting, requires confirmation, and clears secrets on cancel", () => {
  open();
  expect(screen.getByRole("dialog")).toHaveTextContent("此操作无法撤销");
  expect(screen.getByRole("button", { name: "确认注销账户" })).toBeDisabled();
  fill();
  fireEvent.click(screen.getByRole("button", { name: "取消" }));
  fireEvent.click(screen.getByRole("button", { name: "注销账户" }));
  expect(screen.getByLabelText("当前密码")).toHaveValue("");
  expect(screen.getByRole("checkbox")).not.toBeChecked();
  expect(mocks.api).not.toHaveBeenCalled();
});

it("rejects an empty password and keeps the session after server errors", async () => {
  open(); fireEvent.click(screen.getByRole("checkbox")); submit();
  expect(screen.getByRole("alert")).toHaveTextContent("请输入当前登录密码");
  expect(mocks.api).not.toHaveBeenCalled();
  mocks.api.mockRejectedValue(new Error("当前密码不正确，账户未注销"));
  fireEvent.change(screen.getByLabelText("当前密码"), { target: { value: "wrong-password" } });
  submit();
  expect(await screen.findByRole("alert")).toHaveTextContent("当前密码不正确");
  expect(mocks.logout).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "确认注销账户" })).toBeEnabled();
});

it("submits once and logs out only after successful deletion", async () => {
  let finish!: (value: unknown) => void;
  mocks.api.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
  open(); fill(); submit();
  expect(screen.getByRole("button", { name: "正在注销…" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "取消" })).toBeDisabled();
  expect(mocks.logout).not.toHaveBeenCalled();
  finish({ ok: true });
  await waitFor(() => expect(mocks.logout).toHaveBeenCalledOnce());
  expect(mocks.api).toHaveBeenCalledExactlyOnceWith("/auth/delete-account", {
    method: "POST", body: JSON.stringify({ password: "current-password", confirmed: true }),
  });
  expect(screen.getByLabelText("当前密码")).toHaveValue("");
});
