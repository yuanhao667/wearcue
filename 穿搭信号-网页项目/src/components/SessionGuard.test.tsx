import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ path: "/", api: vi.fn(), clear: vi.fn() }));
vi.mock("next/navigation", () => ({ usePathname: () => mocks.path }));
vi.mock("@/lib/backend-api", () => ({ apiJson: mocks.api }));
vi.mock("@/lib/client-auth", () => ({ clearClientSession: mocks.clear }));
import { SessionGuard } from "./SessionGuard";
afterEach(() => { cleanup(); vi.clearAllMocks(); mocks.path = "/"; });

it("keeps the product page public without auth calls or clearing an existing session", () => {
  mocks.path = "/about";
  render(<SessionGuard />);
  fireEvent(window, new Event("focus"));
  fireEvent(window, new Event("pageshow"));
  expect(mocks.api).not.toHaveBeenCalled();
  expect(mocks.clear).not.toHaveBeenCalled();
});

it("rechecks the session when returning to an already open tab", async () => {
  mocks.api.mockResolvedValue({ user: {} });
  render(<SessionGuard />);
  await waitFor(() => expect(mocks.api).toHaveBeenCalledTimes(1));
  fireEvent(window, new Event("focus"));
  await waitFor(() => expect(mocks.api).toHaveBeenCalledTimes(2));
  fireEvent(window, new Event("pageshow"));
  await waitFor(() => expect(mocks.api).toHaveBeenCalledTimes(3));
});

it("clears the stale profile on the login page without a redirect loop", () => {
  mocks.path = "/login";
  render(<SessionGuard />);
  expect(mocks.clear).toHaveBeenCalledOnce();
  expect(mocks.api).not.toHaveBeenCalled();
});
