import { OutfitDetailApp } from "@/components/OutfitDetailApp";

export default async function OutfitDetailPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ from?: string }> }) {
  const { id } = await params;
  const { from } = await searchParams;
  return <OutfitDetailApp id={id} origin={from === "home" ? "home" : "closet"} key={id} />;
}
