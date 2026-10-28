import { afterEach, describe, expect, it, vi } from "vitest";

const { get, redirect } = vi.hoisted(() => ({
  get: vi.fn(), redirect: vi.fn((url: string) => { throw new Error(`redirect:${url}`); }),
}));
vi.mock("next/headers", () => ({ cookies: async () => ({ get }) }));
vi.mock("next/navigation", () => ({ redirect }));
import { requireSession } from "./server-auth";

afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks(); });
describe("protected pages", () => {
  it("sends a missing session to login without fetching", async () => {
    get.mockReturnValue(undefined);
    vi.stubGlobal("fetch", vi.fn());
    await expect(requireSession()).rejects.toThrow("redirect:/login");
    expect(fetch).not.toHaveBeenCalled();
  });
  it("rejects an existing but expired cookie", async () => {
    get.mockReturnValue({ value: "expired" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
    await expect(requireSession()).rejects.toThrow("redirect:/login?expired=1");
  });
  it.each([200, 503])("does not force logout for backend status %i", async (status) => {
    get.mockReturnValue({ value: "session" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status })));
    await requireSession();
    expect(redirect).not.toHaveBeenCalled();
  });
  it("does not confuse a network outage with expiry", async () => {
    get.mockReturnValue({ value: "session" });
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await requireSession();
    expect(redirect).not.toHaveBeenCalled();
  });
});
