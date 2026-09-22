import { LibraryApp } from "@/components/LibraryApp";
import { requireSession } from "@/lib/server-auth";

export default async function ClosetPage() {
  await requireSession();
  return <LibraryApp />;
}
