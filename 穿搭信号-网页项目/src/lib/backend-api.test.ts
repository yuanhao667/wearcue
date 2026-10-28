import { afterEach, describe, expect, it, vi } from "vitest";
import { apiForm, apiJson, parseError } from "./backend-api";
import { recoverExpiredSession } from "./client-auth";

vi.mock("./client-auth", () => ({ recoverExpiredSession: vi.fn() }));
afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks(); });

describe("expired sessions", () => {
  it.each(["json", "form"])("recovers on 401 from %s requests", async (kind) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "expired" }, { status: 401 })));
    const request = kind === "json" ? apiJson("/settings") : apiForm("/upload", new FormData());
    await expect(request).rejects.toMatchObject({ status: 401 });
    expect(recoverExpiredSession).toHaveBeenCalledOnce();
  });

  it.each([403, 500, 502])("does not log out on a %i response", async (status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({}, { status })));
    await expect(apiJson("/settings")).rejects.toMatchObject({ status });
    expect(recoverExpiredSession).not.toHaveBeenCalled();
  });
});

describe("parseError", () => {
  it("reads the backend error envelope instead of rendering an object", async () => {
    const response = new Response(JSON.stringify({ error: { message: "视觉模型响应超时" } }), { status: 503 });
    await expect(parseError(response)).resolves.toBe("视觉模型响应超时");
  });
});
