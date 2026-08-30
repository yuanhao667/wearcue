import { describe, expect, it } from "vitest";
import type { BackendRecommendation, BackendSettings, TodayWeather } from "@/domain/backend";
import { activeAIRecommendationForContext, homeSwapStatus, requestFrom, withSceneRecommendation } from "./TodayApp";

describe("home swap progress", () => {
  it("uses cached context and rotates AI generation copy", () => {
    expect([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((step) => homeSwapStatus(step, true))).toEqual([
      "AI 正在查看地理位置",
      "AI 正在查看气温与体感温度",
      "AI 正在查看降水概率与降水量",
      "AI 正在查看最大风速与阵风",
      "AI 正在查看紫外线指数",
      "AI 正在帮你挑选帽子",
      "AI 正在帮你搭配上装",
      "AI 正在帮你搭配下装",
      "AI 正在帮你挑选鞋子",
      "AI 正在检查整套搭配",
      "AI 正在帮你挑选帽子",
    ]);
  });

  it("never claims AI work after the daily AI quota is exhausted", () => {
    expect([0, 1, 2, 3, 4, 5, 6, 7, 8].map((step) => homeSwapStatus(step, false))).toEqual([
      "正在查看地理位置",
      "正在查看气温与体感温度",
      "正在查看降水概率与降水量",
      "正在查看最大风速与阵风",
      "正在查看紫外线指数",
      "正在匹配个人首页推荐",
      "正在匹配系统推荐",
      "正在检查天气适配",
      "正在匹配个人首页推荐",
    ]);
  });

  it("copies the complete existing weather snapshot without fetching it again", () => {
    const weather = {
      city: "上海市浦东新区", latitude: 31.2304, longitude: 121.4737,
      timezone: "Asia/Shanghai", date: "2026-08-30",
      current_temperature: 32.4, current_apparent_temperature: 36.1,
      temperature_min: 28.2, temperature_max: 34.6,
      apparent_min: 29, apparent_max: 35,
      max_precipitation_probability: 65, total_precipitation: 1.2,
      total_snowfall: 0, max_wind_speed: 24, max_wind_gust: 42,
      uv_index_max: 8, weather_code: 61,
    } as TodayWeather;
    const settings = {
      city_id: "shanghai-pudong", city_name: "上海市浦东新区",
      cold_offset: 0, audience: "mens",
    } as BackendSettings;

    expect(requestFrom(weather, settings, "commute")).toMatchObject({
      city_id: "shanghai-pudong", city_name: "上海市浦东新区",
      latitude: 31.2304, longitude: 121.4737, timezone: "Asia/Shanghai",
      current_temperature: 32.4, current_apparent_temperature: 36.1,
      temperature_min: 28.2, temperature_max: 34.6,
      apparent_min: 29, apparent_max: 35,
      max_precipitation_probability: 65, total_precipitation: 1.2,
      total_snowfall: 0, max_wind_speed: 24, max_wind_gust: 42,
      uv_index_max: 8, weather_code: 61,
    });
  });

  it("restores the same AI outfit only for the same date, city and audience", () => {
    const weather = { date: "2026-08-30" } as TodayWeather;
    const settings = { city_id: "shanghai", audience: "mens" } as BackendSettings;
    const recommendation = {
      source: "ai",
      template_id: "ai-same-detail",
      scene: "date",
      audience: "mens",
      constraints: { local_date: "2026-08-30", city_id: "shanghai" },
      items: [],
    } as unknown as BackendRecommendation;

    expect(activeAIRecommendationForContext(JSON.stringify(recommendation), weather, settings)?.template_id).toBe("ai-same-detail");
    expect(activeAIRecommendationForContext(JSON.stringify({
      ...recommendation,
      constraints: { ...recommendation.constraints, local_date: "2026-08-29" },
    }), weather, settings)).toBeNull();
  });

  it("replaces only the recommendation for the generated scene", () => {
    const commute = { template_id: "commute-1", scene: "commute" } as BackendRecommendation;
    const date = { template_id: "date-1", scene: "date" } as BackendRecommendation;
    const travel = { template_id: "travel-1", scene: "travel" } as BackendRecommendation;
    const nextDate = { ...date, template_id: "date-2" };

    const updated = withSceneRecommendation({ commute, date, travel }, nextDate);

    expect(updated.commute).toBe(commute);
    expect(updated.date?.template_id).toBe("date-2");
    expect(updated.travel).toBe(travel);
  });
});
