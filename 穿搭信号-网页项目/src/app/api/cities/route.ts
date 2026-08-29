import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import type { City } from "@/domain/types";

const querySchema = z.object({
  q: z.string().trim().min(1).max(60),
});

interface GeocodingResult {
  id: number;
  name: string;
  admin1?: string;
  country: string;
  latitude: number;
  longitude: number;
  timezone: string;
}

export async function GET(request: NextRequest) {
  const parsed = querySchema.safeParse({ q: request.nextUrl.searchParams.get("q") });
  if (!parsed.success) {
    return NextResponse.json({ error: "请输入城市名称" }, { status: 400 });
  }

  try {
    const url = new URL("https://geocoding-api.open-meteo.com/v1/search");
    url.searchParams.set("name", parsed.data.q);
    url.searchParams.set("count", "8");
    url.searchParams.set("language", "zh");
    url.searchParams.set("format", "json");
    const response = await fetch(url, { next: { revalidate: 86400 } });
    if (!response.ok) throw new Error(`Geocoding upstream returned ${response.status}`);
    const payload = (await response.json()) as { results?: GeocodingResult[] };
    const cities: City[] = (payload.results ?? []).map((result) => ({
      id: String(result.id),
      name: result.name,
      admin1: result.admin1,
      country: result.country,
      latitude: result.latitude,
      longitude: result.longitude,
      timezone: result.timezone,
    }));
    return NextResponse.json({ cities });
  } catch (error) {
    console.error(error);
    return NextResponse.json({ error: "城市搜索暂时不可用，请稍后再试" }, { status: 502 });
  }
}
