import { LoginApp } from "@/components/LoginApp";
import { redirect } from "next/navigation";
import { authenticatedBackendFetch } from "@/lib/server-auth";

export const dynamic = "force-dynamic";

export default async function LoginPage() {
  const session = await authenticatedBackendFetch("/auth/me").catch(() => null);
  if (!session?.ok) return <LoginApp />;
  const payload = await session.json() as {
    user: {
      id: string;
      nickname: string;
      audience: "mens" | "womens";
      profile_completed: boolean;
    };
  };
  if (payload.user.profile_completed) redirect("/");
  return <LoginApp initialUser={{
    id: payload.user.id,
    nickname: payload.user.nickname,
    gender: payload.user.audience,
    profileCompleted: false,
  }} />;
}
