import { afterEach, describe, expect, it, vi } from "vitest";

const { remove } = vi.hoisted(() => ({ remove: vi.fn() }));
vi.mock("next/headers", () => ({ cookies: async () => ({
  get: () => ({ value: "stale" }), delete: remove,
}) }));
import { POST } from "./route";

afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks(); });
describe("logout escape hatch", () => {
  it.each([200, 401, 503])("clears local cookies even if revoke returns %i", async (status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status })));
    expect((await POST()).status).toBe(200);
    expect(remove).toHaveBeenCalledWith("wearcue_session");
    expect(remove).toHaveBeenCalledWith("wearcue_profile_pending");
  });
  it("bounds a stuck upstream call and still logs out", async () => {
    const controller = new AbortController();
    vi.spyOn(AbortSignal, "timeout").mockReturnValueOnce(controller.signal);
    vi.stubGlobal("fetch", vi.fn((_url, init) => new Promise((_resolve, reject) => {
      init.signal.addEventListener("abort", () => reject(new Error("timeout")));
    })));
    const response = POST();
    await vi.waitFor(() => expect(fetch).toHaveBeenCalled());
    controller.abort();
    expect((await response).status).toBe(200);
    expect(remove).toHaveBeenCalledWith("wearcue_session");
    vi.restoreAllMocks();
  });
});
