import { cookies } from "next/headers";
import { authenticatedBackendFetch, SESSION_COOKIE } from "@/lib/server-auth";

export async function POST() {
  const cookieStore = await cookies();
  // Capture the token before clearing it, but never let upstream availability block logout.
  const revoke = authenticatedBackendFetch("/auth/logout", {
    method: "POST", signal: AbortSignal.timeout(1500),
  }).catch(() => undefined);
  await revoke;
  cookieStore.delete(SESSION_COOKIE);
  cookieStore.delete("wearcue_profile_pending");
  return Response.json({ ok: true });
}
