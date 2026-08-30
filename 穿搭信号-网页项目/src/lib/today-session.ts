import type { BackendRecommendation, BackendSettings, TodayWeather } from "@/domain/backend";

export type TodaySessionCache = {
  settings: BackendSettings;
  weather: TodayWeather;
  recommendation: BackendRecommendation;
  savedAt: number;
};

const TODAY_SESSION_KEY = "wearcue_today_session_v1";
const TODAY_SESSION_TTL = 30 * 60 * 1000;

function dateInTimezone(timestamp: number, timezone: string) {
  const parts = new Intl.DateTimeFormat("en", { timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit" })
    .formatToParts(new Date(timestamp));
  const part = (type: string) => parts.find((item) => item.type === type)?.value;
  return `${part("year")}-${part("month")}-${part("day")}`;
}

export function saveTodaySession(settings: BackendSettings, weather: TodayWeather, recommendation: BackendRecommendation, savedAt = Date.now()) {
  try { sessionStorage.setItem(TODAY_SESSION_KEY, JSON.stringify({ settings, weather, recommendation, savedAt })); } catch { /* 缓存不可用时仍可实时加载 */ }
}

export function readTodaySession(now = Date.now()): TodaySessionCache | null {
  try {
    const cached = JSON.parse(sessionStorage.getItem(TODAY_SESSION_KEY) || "null") as TodaySessionCache | null;
    return cached
      && now - cached.savedAt < TODAY_SESSION_TTL
      && cached.weather.date === dateInTimezone(now, cached.weather.timezone)
      ? cached
      : null;
  } catch {
    return null;
  }
}

export function clearTodaySession() {
  try { sessionStorage.removeItem(TODAY_SESSION_KEY); } catch { /* 无本地缓存时无需处理 */ }
}
