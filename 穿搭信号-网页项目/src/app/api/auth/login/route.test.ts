import { afterEach, describe, expect, it, vi } from "vitest";

const setCookie = vi.fn();
vi.mock("next/headers", () => ({ cookies: async () => ({ set: setCookie }) }));

import { POST } from "./route";

function request(body: object) {
  return new Request("http://localhost/api/auth/login", { method: "POST", body: JSON.stringify(body) });
}

describe("email login route", () => {
  afterEach(() => { vi.unstubAllGlobals(); setCookie.mockClear(); });

  it("stores the backend session in an HttpOnly cookie", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({
      token: "secret-session-token", expires_at: "2026-09-29T00:00:00+00:00",
      user: { id: "user_a", email: "me@example.com", nickname: "圆号", audience: "mens", profile_completed: true },
    })));
    const response = await POST(request({ mode: "login", email: "me@example.com", password: "safe-password" }));
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({ ok: true, user: { nickname: "圆号", gender: "mens", profileCompleted: true } });
    expect(setCookie).toHaveBeenCalledWith("wearcue_session", "secret-session-token", expect.objectContaining({ httpOnly: true, sameSite: "lax", path: "/" }));
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/api/v1/auth/login"), expect.objectContaining({
      body: JSON.stringify({ mode: "login", email: "me@example.com", password: "safe-password" }),
    }));
  });

  it("rejects incomplete registration and forwards backend invite errors", async () => {
    expect((await POST(request({ mode: "register", email: "bad", password: "short", inviteCode: "PRIVATE-01", verificationCode: "123" }))).status).toBe(400);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ error: { message: "邀请码无效，请向邀请人确认" } }, { status: 403 })));
    const response = await POST(request({ mode: "register", email: "new@example.com", password: "safe-password", inviteCode: "WRONG", verificationCode: "123456" }));
    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({ error: "邀请码无效，请向邀请人确认" });
  });

  it("sends verification and invitation only when registering", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({
      token: "new-session-token", expires_at: "2026-09-29T00:00:00+00:00",
      user: { id: "user_b", email: "new@example.com", nickname: "new", audience: "mens", profile_completed: false },
    })));
    const response = await POST(request({ mode: "register", email: "new@example.com", password: "safe-password", inviteCode: "PRIVATE-02", verificationCode: "123456" }));
    expect(response.status).toBe(200);
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/api/v1/auth/login"), expect.objectContaining({
      body: JSON.stringify({ mode: "register", email: "new@example.com", password: "safe-password", invite_code: "PRIVATE-02", verification_code: "123456" }),
    }));
  });
});
