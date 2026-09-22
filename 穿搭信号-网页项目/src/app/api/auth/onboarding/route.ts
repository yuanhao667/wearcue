import { cookies } from "next/headers";
import { z } from "zod";
import { authenticatedBackendFetch } from "@/lib/server-auth";

const PROFILE_PENDING_COOKIE = "wearcue_profile_pending";
const schema = z.object({
  nickname: z.string().trim().min(1).max(5),
  audience: z.enum(["mens", "womens"]),
});

export async function POST(request: Request) {
  const parsed = schema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return Response.json({ error: { message: "请完整填写个人资料" } }, { status: 400 });
  try {
    const response = await authenticatedBackendFetch("/auth/onboarding", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(parsed.data),
    });
    const payload = await response.json().catch(() => null);
    if (response.ok) (await cookies()).delete(PROFILE_PENDING_COOKIE);
    return Response.json(payload, { status: response.status });
  } catch {
    return Response.json({ error: { message: "账号服务暂时不可用" } }, { status: 502 });
  }
}
