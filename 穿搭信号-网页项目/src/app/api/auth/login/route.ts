import { cookies } from "next/headers";
import { z } from "zod";
import { BACKEND_URL, SESSION_COOKIE } from "@/lib/server-auth";

const loginSchema = z.object({
  nickname: z.string().trim().min(1).max(5),
  gender: z.enum(["mens", "womens"]),
  inviteCode: z.string().trim().min(1),
});

type BackendLogin = {
  token: string;
  expires_at: string;
  user: { id: string; nickname: string; audience: "mens" | "womens" };
};

async function errorMessage(response: Response) {
  const payload = await response.json().catch(() => null) as { error?: { message?: string } } | null;
  return payload?.error?.message || "登录失败，请稍后重试";
}

export async function POST(request: Request) {
  const parsed = loginSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return Response.json({ error: "请完整填写登录信息" }, { status: 400 });

  let response: Response;
  try {
    response = await fetch(`${BACKEND_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nickname: parsed.data.nickname,
        audience: parsed.data.gender,
        invite_code: parsed.data.inviteCode,
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
  } catch {
    return Response.json({ error: "登录服务暂时不可用" }, { status: 502 });
  }
  if (!response.ok) return Response.json({ error: await errorMessage(response) }, { status: response.status });

  const result = await response.json() as BackendLogin;
  const expires = new Date(result.expires_at);
  (await cookies()).set(SESSION_COOKIE, result.token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    expires,
    priority: "high",
  });
  return Response.json({
    ok: true,
    user: { id: result.user.id, nickname: result.user.nickname, gender: result.user.audience },
  });
}

