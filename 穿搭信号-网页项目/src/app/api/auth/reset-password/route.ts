import { z } from "zod";
import { BACKEND_URL } from "@/lib/server-auth";

const schema = z.object({
  email: z.email().max(254),
  verificationCode: z.string().regex(/^\d{6}$/),
  password: z.string().min(8).max(128),
});

export async function POST(request: Request) {
  const parsed = schema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return Response.json({ error: "请完整填写重置密码信息" }, { status: 400 });
  try {
    const response = await fetch(`${BACKEND_URL}/api/v1/auth/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: parsed.data.email,
        verification_code: parsed.data.verificationCode,
        password: parsed.data.password,
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    const payload = await response.json().catch(() => null) as {
      ok?: boolean;
      error?: { message?: string };
    } | null;
    if (!response.ok) {
      return Response.json(
        { error: payload?.error?.message || "密码重置失败，请稍后重试" },
        { status: response.status },
      );
    }
    return Response.json({ ok: true });
  } catch {
    return Response.json({ error: "账号服务暂时不可用" }, { status: 502 });
  }
}
