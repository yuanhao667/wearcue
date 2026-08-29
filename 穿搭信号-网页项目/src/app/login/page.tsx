import { LoginApp } from "@/components/LoginApp";
import { redirect } from "next/navigation";
import { authenticatedBackendFetch } from "@/lib/server-auth";

export const dynamic = "force-dynamic";

export default async function LoginPage() {
  const session = await authenticatedBackendFetch("/auth/me").catch(() => null);
  if (session?.ok) redirect("/");
  return <LoginApp />;
}
