import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import type { City, HourlyWeather, WeatherSnapshot } from "@/domain/types";

const querySchema = z.object({
  lat: z.coerce.number().min(-90).max(90),
  lon: z.coerce.number().min(-180).max(180),
  city: z.string().trim().min(1).max(80),
  country: z.string().trim().max(80).default("中国"),
  admin1: z.string().trim().max(80).optional(),
  id: z.string().trim().max(80).default("custom"),
  timezone: z.string().trim().max(80).default("auto"),
});

interface OpenMeteoPayload {
  timezone: string;
  current: {
    time: string;
    temperature_2m: number;
    apparent_temperature: number;
    weather_code: number;
  };
  hourly: {
    time: string[];
    temperature_2m: number[];
    apparent_temperature: number[];
    precipitation_probability: number[];
    precipitation: number[];
    rain: number[];
    snowfall: number[];
    weather_code: number[];
    wind_speed_10m: number[];
    wind_gusts_10m: number[];
  };
  daily: {
    time: string[];
    temperature_2m_max: number[];
    temperature_2m_min: number[];
    apparent_temperature_max: number[];
    apparent_temperature_min: number[];
    precipitation_sum: number[];
    snowfall_sum: number[];
    precipitation_probability_max: number[];
    wind_speed_10m_max: number[];
    wind_gusts_10m_max: number[];
    weather_code: number[];
    uv_index_max: number[];
  };
}

function numberAt(values: number[] | undefined, index = 0) {
  return Number(values?.[index] ?? 0);
}

export async function GET(request: NextRequest) {
  const raw = Object.fromEntries(request.nextUrl.searchParams.entries());
  const parsed = querySchema.safeParse(raw);
  if (!parsed.success) {
    return NextResponse.json({ error: "城市坐标无效" }, { status: 400 });
  }

  try {
    const { lat, lon, city, country, admin1, id, timezone } = parsed.data;
    const url = new URL("https://api.open-meteo.com/v1/forecast");
    url.searchParams.set("latitude", String(lat));
    url.searchParams.set("longitude", String(lon));
    url.searchParams.set("timezone", timezone);
    url.searchParams.set("forecast_days", "1");
    url.searchParams.set(
      "current",
      "temperature_2m,apparent_temperature,weather_code",
    );
    url.searchParams.set(
      "hourly",
      "temperature_2m,apparent_temperature,precipitation_probability,precipitation,rain,snowfall,weather_code,wind_speed_10m,wind_gusts_10m",
    );
    url.searchParams.set(
      "daily",
      "temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,precipitation_sum,snowfall_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,weather_code,uv_index_max",
    );
    const response = await fetch(url, { next: { revalidate: 900 } });
    if (!response.ok) throw new Error(`Weather upstream returned ${response.status}`);
    const payload = (await response.json()) as OpenMeteoPayload;

    const resolvedCity: City = {
      id,
      name: city,
      admin1,
      country,
      latitude: lat,
      longitude: lon,
      timezone: payload.timezone,
    };
    const hourly: HourlyWeather[] = payload.hourly.time.map((time, index) => ({
      time,
      temperature: numberAt(payload.hourly.temperature_2m, index),
      apparentTemperature: numberAt(payload.hourly.apparent_temperature, index),
      precipitationProbability: numberAt(payload.hourly.precipitation_probability, index),
      precipitation: numberAt(payload.hourly.precipitation, index),
      rain: numberAt(payload.hourly.rain, index),
      snowfall: numberAt(payload.hourly.snowfall, index),
      weatherCode: numberAt(payload.hourly.weather_code, index),
      windSpeed: numberAt(payload.hourly.wind_speed_10m, index),
      windGust: numberAt(payload.hourly.wind_gusts_10m, index),
    }));
    const weather: WeatherSnapshot = {
      city: resolvedCity,
      date: payload.daily.time[0],
      timezone: payload.timezone,
      currentTemperature: payload.current.temperature_2m,
      currentApparentTemperature: payload.current.apparent_temperature,
      apparentMin: numberAt(payload.daily.apparent_temperature_min),
      apparentMax: numberAt(payload.daily.apparent_temperature_max),
      temperatureMin: numberAt(payload.daily.temperature_2m_min),
      temperatureMax: numberAt(payload.daily.temperature_2m_max),
      maxPrecipitationProbability: numberAt(payload.daily.precipitation_probability_max),
      totalPrecipitation: numberAt(payload.daily.precipitation_sum),
      totalSnowfall: numberAt(payload.daily.snowfall_sum),
      maxWindSpeed: numberAt(payload.daily.wind_speed_10m_max),
      maxWindGust: numberAt(payload.daily.wind_gusts_10m_max),
      uvIndexMax: numberAt(payload.daily.uv_index_max),
      weatherCode: payload.current.weather_code ?? numberAt(payload.daily.weather_code),
      hourly,
      fetchedAt: new Date().toISOString(),
    };
    return NextResponse.json({ weather });
  } catch (error) {
    console.error(error);
    return NextResponse.json({ error: "天气服务暂时不可用，请稍后重试" }, { status: 502 });
  }
}
