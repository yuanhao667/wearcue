import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export const SESSION_COOKIE = "wearcue_session";
export const BACKEND_URL = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

async function sessionToken() {
  return (await cookies()).get(SESSION_COOKIE)?.value;
}

export async function authenticatedBackendFetch(path: string, init?: RequestInit) {
  const token = await sessionToken();
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(`${BACKEND_URL}/api/v1${path}`, {
    ...init,
    headers,
    cache: "no-store",
    signal: init?.signal ?? AbortSignal.timeout(8000),
  });
}

export async function requireSession() {
  if (!await sessionToken()) redirect("/login");
  const session = await authenticatedBackendFetch("/auth/me").catch(() => null);
  if (session?.status === 401) redirect("/login?expired=1");
  // A backend outage is not proof of an invalid session. Let the page show retry/logout.
}
