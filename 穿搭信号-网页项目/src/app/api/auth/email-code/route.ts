import { z } from "zod";
import { BACKEND_URL } from "@/lib/server-auth";

const schema = z.object({
  email: z.email().max(254),
  purpose: z.enum(["register", "reset"]),
  inviteCode: z.string().trim().min(1).optional(),
});

async function errorMessage(response: Response) {
  const payload = await response.json().catch(() => null) as { error?: { message?: string } } | null;
  return payload?.error?.message || "验证码发送失败，请稍后重试";
}

export async function POST(request: Request) {
  const parsed = schema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return Response.json({ error: "请填写有效的邮箱和邀请码" }, { status: 400 });
  try {
    const response = await fetch(`${BACKEND_URL}/api/v1/auth/email-code`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: parsed.data.email,
        purpose: parsed.data.purpose,
        ...(parsed.data.inviteCode ? { invite_code: parsed.data.inviteCode } : {}),
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(12000),
    });
    if (!response.ok) {
      return Response.json({ error: await errorMessage(response) }, { status: response.status });
    }
    return Response.json(await response.json());
  } catch {
    return Response.json({ error: "邮箱服务暂时不可用" }, { status: 502 });
  }
}
