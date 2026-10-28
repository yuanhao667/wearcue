import { clearTodaySession } from "./today-session";

let redirecting = false;

export function clearClientSession() {
  try { localStorage.removeItem("wearcue_profile_v1"); } catch { /* Storage may be disabled. */ }
  clearTodaySession();
  window.dispatchEvent(new Event("wearcue-profile"));
}

export function recoverExpiredSession() {
  if (typeof window === "undefined" || redirecting) return;
  redirecting = true;
  clearClientSession();
  // Full navigation discards any previously prefetched authenticated page.
  window.location.replace("/login?expired=1");
}

export async function logoutAndRedirect() {
  clearClientSession();
  try {
    await fetch("/api/auth/logout", { method: "POST", signal: AbortSignal.timeout(3000) });
  } catch { /* Still provide an escape from an unavailable backend. */ }
  window.location.replace("/login");
}
