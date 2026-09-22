import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

const { get, remove } = vi.hoisted(() => ({ get: vi.fn(), remove: vi.fn() }));
vi.mock("next/headers", () => ({ cookies: async () => ({ get, delete: remove }) }));
import { GET } from "./route";

afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks(); });
describe("API session recovery", () => {
  it.each(["expired", undefined])("clears rejected credentials: %s", async (token) => {
    get.mockReturnValue(token ? { value: token } : undefined);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "expired" }, { status: 401 })));
    const response = await GET(new NextRequest("https://wearcue.test/api/backend/settings"), { params: Promise.resolve({ path: ["settings"] }) });
    expect(response.status).toBe(401);
    expect(remove).toHaveBeenCalledWith("wearcue_session");
    expect(remove).toHaveBeenCalledWith("wearcue_profile_pending");
  });
  it("keeps the session cookie when upstream is temporarily unavailable", async () => {
    get.mockReturnValue({ value: "valid" });
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const response = await GET(new NextRequest("https://wearcue.test/api/backend/settings"), { params: Promise.resolve({ path: ["settings"] }) });
    expect(response.status).toBe(502);
    expect(remove).not.toHaveBeenCalled();
  });
});
