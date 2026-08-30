import { TodayApp } from "@/components/TodayApp";
import type { BackendRecommendation, BackendSettings, TodayWeather } from "@/domain/backend";
import { authenticatedBackendFetch } from "@/lib/server-auth";

export const dynamic = "force-dynamic";

async function privateBackendJson<T>(path: string, init?: RequestInit) {
  const response = await authenticatedBackendFetch(path, init);
  if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  return response.json() as Promise<T>;
}

async function initialToday() {
  try {
    const settings = await privateBackendJson<BackendSettings>("/settings");
    const query = new URLSearchParams({ latitude: String(settings.latitude), longitude: String(settings.longitude), city: settings.city_name });
    const { weather } = await privateBackendJson<{ weather: TodayWeather }>(`/weather/today?${query}`);
    const recommendation = await privateBackendJson<BackendRecommendation>("/recommendations/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        apparent_min: weather.apparent_min,
        apparent_max: weather.apparent_max,
        max_precipitation_probability: weather.max_precipitation_probability,
        total_precipitation: weather.total_precipitation,
        total_snowfall: weather.total_snowfall,
        max_wind_speed: weather.max_wind_speed,
        max_wind_gust: weather.max_wind_gust,
        uv_index_max: weather.uv_index_max,
        cold_offset: settings.cold_offset,
        scene: "commute",
        city_id: settings.city_id,
        local_date: weather.date,
        excluded_template_ids: [],
      }),
    });
    return { settings, weather, recommendation };
  } catch {
    return null;
  }
}

export default async function HomePage() {
  return <TodayApp initial={await initialToday()} />;
}
