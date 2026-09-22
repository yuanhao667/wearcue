import { InspirationApp } from "@/components/InspirationApp";
import { requireSession } from "@/lib/server-auth";

export default async function InspirationPage() {
  await requireSession();
  return <InspirationApp />;
}
