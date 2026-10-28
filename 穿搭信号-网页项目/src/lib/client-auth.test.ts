import { afterEach, beforeEach, expect, it, vi } from "vitest";

beforeEach(() => { vi.resetModules(); localStorage.clear(); sessionStorage.clear(); });
afterEach(() => vi.unstubAllGlobals());

it("clears cached account data and redirects only once for concurrent expired requests", async () => {
  localStorage.setItem("wearcue_profile_v1", "stale profile");
  sessionStorage.setItem("wearcue_today_session_v1", "stale recommendations");
  const replace = vi.fn();
  vi.stubGlobal("window", { location: { replace }, dispatchEvent: vi.fn() });
  const { recoverExpiredSession } = await import("./client-auth");
  recoverExpiredSession();
  recoverExpiredSession();
  expect(localStorage.getItem("wearcue_profile_v1")).toBeNull();
  expect(sessionStorage.getItem("wearcue_today_session_v1")).toBeNull();
  expect(replace).toHaveBeenCalledExactlyOnceWith("/login?expired=1");
});

it("still reaches login if the logout request fails", async () => {
  const replace = vi.fn();
  vi.stubGlobal("window", { location: { replace }, dispatchEvent: vi.fn() });
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  const { logoutAndRedirect } = await import("./client-auth");
  await logoutAndRedirect();
  expect(replace).toHaveBeenCalledWith("/login");
});
