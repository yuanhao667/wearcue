import { cookies } from "next/headers";
import { z } from "zod";
import { BACKEND_URL, SESSION_COOKIE } from "@/lib/server-auth";

const PROFILE_PENDING_COOKIE = "wearcue_profile_pending";

const loginSchema = z.discriminatedUnion("mode", [
  z.object({
    mode: z.literal("login"),
    email: z.email().max(254),
    password: z.string().min(8).max(128),
  }),
  z.object({
    mode: z.literal("register"),
    email: z.email().max(254),
    password: z.string().min(8).max(128),
    inviteCode: z.string().trim().min(1),
    verificationCode: z.string().regex(/^\d{6}$/),
  }),
]);

type BackendLogin = {
  token: string;
  expires_at: string;
  user: {
    id: string;
    email: string;
    nickname: string;
    audience: "mens" | "womens";
    profile_completed: boolean;
  };
};

async function errorMessage(response: Response, fallback: string) {
  const payload = await response.json().catch(() => null) as { error?: { message?: string } } | null;
  return payload?.error?.message || fallback;
}

export async function POST(request: Request) {
  const parsed = loginSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return Response.json({ error: "请完整填写账号信息" }, { status: 400 });

  let response: Response;
  try {
    response = await fetch(`${BACKEND_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: parsed.data.mode,
        email: parsed.data.email,
        password: parsed.data.password,
        ...(parsed.data.mode === "register" ? {
          invite_code: parsed.data.inviteCode,
          verification_code: parsed.data.verificationCode,
        } : {}),
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
  } catch {
    return Response.json({ error: "账号服务暂时不可用" }, { status: 502 });
  }
  if (!response.ok) {
    const action = parsed.data.mode === "register" ? "注册" : "登录";
    return Response.json(
      { error: await errorMessage(response, `${action}失败，请稍后重试`) },
      { status: response.status },
    );
  }

  const result = await response.json() as BackendLogin;
  const expires = new Date(result.expires_at);
  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE, result.token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    expires,
    priority: "high",
  });
  cookieStore.set(PROFILE_PENDING_COOKIE, result.user.profile_completed ? "" : "1", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    ...(result.user.profile_completed ? { maxAge: 0 } : { expires }),
  });
  return Response.json({
    ok: true,
    user: {
      id: result.user.id,
      nickname: result.user.nickname,
      gender: result.user.audience,
      profileCompleted: result.user.profile_completed,
    },
  });
}
