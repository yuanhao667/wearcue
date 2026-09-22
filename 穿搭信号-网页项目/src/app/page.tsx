import { TodayApp } from "@/components/TodayApp";
import { requireSession } from "@/lib/server-auth";

export default async function HomePage() {
  await requireSession();
  return <TodayApp />;
}
