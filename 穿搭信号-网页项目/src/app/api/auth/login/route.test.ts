import { afterEach, describe, expect, it, vi } from "vitest";

const setCookie = vi.fn();
vi.mock("next/headers", () => ({ cookies: async () => ({ set: setCookie }) }));

import { POST } from "./route";

function request(body: object) {
  return new Request("http://localhost/api/auth/login", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

describe("invitation login route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    setCookie.mockClear();
  });

  it("stores the backend session in an HttpOnly cookie", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({
      token: "secret-session-token",
      expires_at: "2026-09-29T00:00:00+00:00",
      user: { id: "user_a", nickname: "圆号", audience: "mens" },
    })));
    const response = await POST(request({
      mode: "login", inviteCode: "PRIVATE-01",
    }));
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      ok: true, user: { nickname: "圆号", gender: "mens" },
    });
    expect(setCookie).toHaveBeenCalledWith(
      "wearcue_session", "secret-session-token",
      expect.objectContaining({ httpOnly: true, sameSite: "lax", path: "/" }),
    );
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/auth/login"),
      expect.objectContaining({
        body: JSON.stringify({ mode: "login", invite_code: "PRIVATE-01" }),
      }),
    );
  });

  it("rejects incomplete registration profiles and forwards backend invite errors", async () => {
    expect((await POST(request({
      mode: "register", nickname: "", gender: "mens", inviteCode: "PRIVATE-01",
    }))).status).toBe(400);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(
      { error: { message: "邀请码无效，请向邀请人确认" } }, { status: 403 },
    )));
    const response = await POST(request({
      mode: "register", nickname: "圆号", gender: "womens", inviteCode: "WRONG",
    }));
    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({ error: "邀请码无效，请向邀请人确认" });
  });

  it("sends nickname and gender only when registering", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({
      token: "new-session-token",
      expires_at: "2026-09-29T00:00:00+00:00",
      user: { id: "user_b", nickname: "新用户", audience: "womens" },
    })));
    const response = await POST(request({
      mode: "register", nickname: "新用户", gender: "womens", inviteCode: "PRIVATE-02",
    }));
    expect(response.status).toBe(200);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/auth/login"),
      expect.objectContaining({
        body: JSON.stringify({
          mode: "register", nickname: "新用户", audience: "womens", invite_code: "PRIVATE-02",
        }),
      }),
    );
  });
});
