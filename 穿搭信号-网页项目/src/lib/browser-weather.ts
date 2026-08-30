import type { TodayWeather } from "@/domain/backend";

const OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast";

type OpenMeteoPayload = {
  latitude?: number;
  longitude?: number;
  timezone?: string;
  current?: Record<string, number | string | undefined>;
  hourly?: Record<string, Array<number | string> | undefined>;
  daily?: Record<string, Array<number | string> | undefined>;
};

function numbers(value: unknown): number[] {
  return Array.isArray(value) ? value.map((item) => Number(item) || 0) : [];
}

export function openMeteoWeather(payload: OpenMeteoPayload, city: string): TodayWeather {
  const hourly = payload.hourly || {};
  const daily = payload.daily || {};
  const current = payload.current || {};
  const apparent = numbers(hourly.apparent_temperature);
  const temperatures = numbers(hourly.temperature_2m);
  const precipitation = numbers(hourly.precipitation);
  const snowfall = numbers(hourly.snowfall);
  const probabilities = numbers(hourly.precipitation_probability);
  const winds = numbers(hourly.wind_speed_10m);
  const gusts = numbers(hourly.wind_gusts_10m);
  if (!apparent.length || !temperatures.length) throw new Error("天气服务返回的数据不完整");

  return {
    city,
    latitude: Number(payload.latitude),
    longitude: Number(payload.longitude),
    date: String(daily.time?.[0] || new Date().toISOString().slice(0, 10)),
    timezone: String(payload.timezone || "UTC"),
    current_temperature: Number(current.temperature_2m ?? temperatures[0]),
    current_apparent_temperature: Number(current.apparent_temperature ?? apparent[0]),
    apparent_min: Math.min(...apparent),
    apparent_max: Math.max(...apparent),
    temperature_min: Math.min(...temperatures),
    temperature_max: Math.max(...temperatures),
    max_precipitation_probability: Math.max(...probabilities, 0),
    total_precipitation: Number(precipitation.reduce((sum, value) => sum + value, 0).toFixed(2)),
    total_snowfall: Number(snowfall.reduce((sum, value) => sum + value, 0).toFixed(2)),
    max_wind_speed: Math.max(...winds, 0),
    max_wind_gust: Math.max(...gusts, 0),
    uv_index_max: Number(daily.uv_index_max?.[0] || 0),
    weather_code: Number(current.weather_code || 0),
    hourly: (hourly.time || []).map((time, index) => ({
      time: String(time),
      temperature: temperatures[index] ?? 0,
      apparent_temperature: apparent[index] ?? 0,
      precipitation_probability: probabilities[index] ?? 0,
      precipitation: precipitation[index] ?? 0,
      snowfall: snowfall[index] ?? 0,
      wind_speed: winds[index] ?? 0,
      wind_gust: gusts[index] ?? 0,
    })),
    fetched_at: new Date().toISOString(),
    provider: "Open-Meteo",
  };
}

export async function fetchBrowserWeather(latitude: number, longitude: number, city: string) {
  const query = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
    timezone: "auto",
    forecast_days: "1",
    current: "temperature_2m,apparent_temperature,weather_code",
    hourly: "temperature_2m,apparent_temperature,precipitation_probability,precipitation,snowfall,weather_code,wind_speed_10m,wind_gusts_10m",
    daily: "temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,precipitation_sum,snowfall_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,weather_code,uv_index_max",
  });
  const response = await fetch(`${OPEN_METEO_URL}?${query}`, { cache: "no-store" });
  if (!response.ok) throw new Error("天气服务暂时不可用");
  return openMeteoWeather(await response.json() as OpenMeteoPayload, city);
}
