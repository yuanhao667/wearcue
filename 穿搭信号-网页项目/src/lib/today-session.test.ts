import { beforeEach, describe, expect, it } from "vitest";
import type { BackendRecommendation, BackendSettings, TodayWeather } from "@/domain/backend";
import { clearTodaySession, readTodaySession, saveTodaySession } from "./today-session";

describe("today session cache", () => {
  beforeEach(() => clearTodaySession());

  it("reuses the current session snapshot and expires stale weather", () => {
    const now = Date.parse("2026-08-30T12:00:00Z");
    const settings = { city_id: "shanghai", audience: "mens" } as BackendSettings;
    const weather = { date: "2026-08-30", timezone: "Asia/Shanghai" } as TodayWeather;
    const recommendation = { template_id: "commute-1", scene: "commute" } as BackendRecommendation;

    saveTodaySession(settings, weather, recommendation, now);
    expect(readTodaySession(now + 1_000)?.recommendation.template_id).toBe("commute-1");
    expect(readTodaySession(now + 31 * 60 * 1_000)).toBeNull();
    expect(readTodaySession(Date.parse("2026-08-31T00:00:00Z"))).toBeNull();
  });
});
