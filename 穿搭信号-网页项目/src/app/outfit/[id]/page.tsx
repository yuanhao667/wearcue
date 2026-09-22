import { OutfitDetailApp } from "@/components/OutfitDetailApp";
import { requireSession } from "@/lib/server-auth";

export default async function OutfitDetailPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ from?: string }> }) {
  await requireSession();
  const { id } = await params;
  const { from } = await searchParams;
  return <OutfitDetailApp id={id} origin={from === "home" ? "home" : "closet"} key={id} />;
}
