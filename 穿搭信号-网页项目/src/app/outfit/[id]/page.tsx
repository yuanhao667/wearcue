import { OutfitDetailApp } from "@/components/OutfitDetailApp";

export default async function OutfitDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <OutfitDetailApp id={id} key={id} />;
}
