import { SettingsApp } from "@/components/SettingsApp";
import { requireSession } from "@/lib/server-auth";

export default async function SettingsPage() {
  await requireSession();
  return <SettingsApp />;
}
