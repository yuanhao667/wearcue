import { describe, expect, it } from "vitest";
import type { BackendRecommendation, BackendSettings, TodayWeather } from "@/domain/backend";
import { activeAIRecommendationForContext, homeHeadline, homeSwapStatus, outfitDetailActionLabel, requestFrom, withSceneRecommendation, withSeenRecommendation } from "./TodayApp";

describe("home headline", () => {
  const weather = { weather_code: 0, total_precipitation: 0, total_snowfall: 0 } as TodayWeather;
  const recommendation = {
    label: "浅灰工装日常 03",
    constraints: { thermal_band: "mild", apparent_delta: 4, needs_waterproof: false, needs_windproof: false },
  } as BackendRecommendation;

  it("waits for real weather and a recommendation", () => {
    expect(homeHeadline(null, null).secondLine).toBe("看看今天的穿搭建议");
    expect(homeHeadline(weather, null).secondLine).toBe("看看今天的穿搭建议");
  });

  it.each([
    [{ total_snowfall: 1, total_precipitation: 2 }, "今日有雪"],
    [{ weather_code: 85 }, "今日有雪"],
    [{ weather_code: 95 }, "今日有雨"],
    [{ total_precipitation: 1 }, "今日有雨"],
  ])("prioritizes precipitation over temperature for %j", (patch, expected) => {
    const coldDay = { ...recommendation, constraints: { ...recommendation.constraints, thermal_band: "severe", apparent_delta: 12 } };
    expect(homeHeadline({ ...weather, ...patch }, coldDay).firstLine).toBe(expected);
  });

  it.each([
    [{ needs_waterproof: true }, "今日可能有雨"],
    [{ apparent_delta: 8 }, "今日温差大"],
    [{ apparent_delta: 7.9 }, "今日晴朗"],
    [{ thermal_band: "cold" }, "今日偏冷"],
    [{ thermal_band: "freezing" }, "今日偏冷"],
    [{ thermal_band: "hot" }, "今日偏热"],
  ])("uses existing weather constraints for %j", (patch, expected) => {
    expect(homeHeadline(weather, { ...recommendation, constraints: { ...recommendation.constraints, ...patch } }).firstLine).toBe(expected);
  });

  it("uses the current outfit name without its legacy sequence", () => {
    expect(homeHeadline(weather, recommendation).secondLine).toBe("试试这套浅灰工装日常");
    expect(homeHeadline(weather, { ...recommendation, label: "轻盈运动风" }).secondLine).toBe("试试这套轻盈运动风");
    expect(homeHeadline(weather, { ...recommendation, label: "" }).secondLine).toBe("试试这套今日推荐");
  });

  it("caps the nickname and preserves the full current outfit title", () => {
    const rainyDay = { ...recommendation, label: "浅色工装风穿搭", constraints: { ...recommendation.constraints, needs_waterproof: true } };
    const headline = homeHeadline(weather, rainyDay, "五个字的名");
    expect(headline).toEqual({ firstLine: "五个字的名，今日可能有雨", secondLine: "试试这套浅色工装风穿搭", secondLineHighlight: "浅色工装风穿搭" });
    expect(Array.from(headline.firstLine).length).toBeLessThanOrEqual(12);
    const fullTitle = "冬日通勤温暖保暖叠穿搭配";
    const longText = homeHeadline(weather, { ...rainyDay, label: fullTitle }, "这是超过五字的昵称");
    expect(Array.from(longText.firstLine).length).toBeLessThanOrEqual(12);
    expect(longText.secondLineHighlight).toBe(fullTitle);
    expect(longText.secondLine).toBe(`试试这套${fullTitle}`);
    expect(homeHeadline(weather, recommendation, "圆号").firstLine).toBe("圆号，今日晴朗");
    expect(homeHeadline(weather, recommendation).firstLine).toBe("今日晴朗");
  });

  it("does not append style or clothing words to the recommendation title", () => {
    const headline = homeHeadline(weather, { ...recommendation, label: "浅灰工装日常" });
    expect(headline.secondLineHighlight).toBe("浅灰工装日常");
    expect(headline.secondLine).toBe(`试试这套${headline.secondLineHighlight}`);
    expect(homeHeadline(weather, { ...recommendation, label: "复古街头穿搭" }).secondLineHighlight).toBe("复古街头穿搭");
  });
});

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

  it("keeps cumulative swap exclusions per scene", () => {
    const first = { template_id: "personal-a", scene: "commute" } as BackendRecommendation;
    const second = { template_id: "system-b", scene: "commute" } as BackendRecommendation;
    const otherScene = { template_id: "date-a", scene: "date" } as BackendRecommendation;

    const history = withSeenRecommendation(
      withSeenRecommendation(withSeenRecommendation({}, first), second),
      otherScene,
    );

    expect(history.commute).toEqual(["personal-a", "system-b"]);
    expect(history.date).toEqual(["date-a"]);
  });

  it("only calls an AI recommendation a generation action", () => {
    expect(outfitDetailActionLabel("personal")).toBe("查看穿搭方案");
    expect(outfitDetailActionLabel("official")).toBe("查看穿搭方案");
    expect(outfitDetailActionLabel("system")).toBe("查看穿搭方案");
    expect(outfitDetailActionLabel("ai")).toBe("生成穿搭方案");
  });
});
