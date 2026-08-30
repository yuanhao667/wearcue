import { describe, expect, it } from "vitest";
import { openMeteoWeather } from "./browser-weather";

describe("openMeteoWeather", () => {
  it("keeps the full weather context used by recommendations", () => {
    const weather = openMeteoWeather({
      latitude: 39.9,
      longitude: 116.4,
      timezone: "Asia/Shanghai",
      current: { temperature_2m: 26, apparent_temperature: 27, weather_code: 1 },
      hourly: {
        time: ["08:00", "09:00"],
        temperature_2m: [25, 28],
        apparent_temperature: [26, 30],
        precipitation_probability: [10, 70],
        precipitation: [0, 1.2],
        snowfall: [0, 0],
        wind_speed_10m: [8, 16],
        wind_gusts_10m: [12, 24],
      },
      daily: { time: ["2026-08-30"], uv_index_max: [7.4] },
    }, "北京");

    expect(weather).toMatchObject({
      city: "北京",
      apparent_min: 26,
      apparent_max: 30,
      max_precipitation_probability: 70,
      total_precipitation: 1.2,
      max_wind_speed: 16,
      max_wind_gust: 24,
      uv_index_max: 7.4,
    });
  });
});
