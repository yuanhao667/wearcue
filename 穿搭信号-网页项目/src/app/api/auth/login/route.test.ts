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
      nickname: "圆号", gender: "mens", inviteCode: "PRIVATE-01",
    }));
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      ok: true, user: { nickname: "圆号", gender: "mens" },
    });
    expect(setCookie).toHaveBeenCalledWith(
      "wearcue_session", "secret-session-token",
      expect.objectContaining({ httpOnly: true, sameSite: "lax", path: "/" }),
    );
  });

  it("rejects incomplete profiles and forwards backend invite errors", async () => {
    expect((await POST(request({
      nickname: "", gender: "mens", inviteCode: "PRIVATE-01",
    }))).status).toBe(400);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(
      { error: { message: "邀请码无效，请向邀请人确认" } }, { status: 403 },
    )));
    const response = await POST(request({
      nickname: "圆号", gender: "womens", inviteCode: "WRONG",
    }));
    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({ error: "邀请码无效，请向邀请人确认" });
  });
});

