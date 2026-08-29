import { cookies } from "next/headers";
import { authenticatedBackendFetch, SESSION_COOKIE } from "@/lib/server-auth";

export async function POST() {
  await authenticatedBackendFetch("/auth/logout", { method: "POST" }).catch(() => undefined);
  (await cookies()).delete(SESSION_COOKIE);
  return Response.json({ ok: true });
}

