"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { CityPicker } from "./CityPicker";
import { profileSnapshot, subscribeProfile } from "./AppNav";
import { OutfitIcon } from "./OutfitIcon";
import { TypingHeadline } from "./TypingHeadline";
import { apiJson } from "@/lib/backend-api";
import { locateCurrentDistrict, simplifyLocationName } from "@/lib/browser-location";
import type { City } from "@/domain/types";
import type { AIQuota, AIUsageQuota, BackendRecommendation, BackendSettings, RecommendationRequest, SceneId, TodayWeather } from "@/domain/backend";
import { outfitItemSortKey } from "@/domain/outfit-order";

export interface TodayInitialData {
  settings: BackendSettings;
  weather: TodayWeather;
  recommendation: BackendRecommendation;
}

type RecommendationsByScene = Partial<Record<SceneId, BackendRecommendation>>;

export function withSceneRecommendation(current: RecommendationsByScene, next: BackendRecommendation): RecommendationsByScene {
  return { ...current, [next.scene]: next };
}

const scenes: Array<{ id: SceneId; label: string }> = [
  { id: "commute", label: "通勤" },
  { id: "date", label: "约会" },
  { id: "travel", label: "出行" },
];

const HOME_SWAP_CONTEXT_STEP_COUNT = 5;
const HOME_SWAP_AI_STEPS = [
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
];
const HOME_SWAP_NON_AI_STEPS = [
  "正在查看地理位置",
  "正在查看气温与体感温度",
  "正在查看降水概率与降水量",
  "正在查看最大风速与阵风",
  "正在查看紫外线指数",
  "正在匹配个人首页推荐",
  "正在匹配系统推荐",
  "正在检查天气适配",
];

export function homeSwapStatus(step: number, aiAvailable: boolean) {
  const matchingSteps = aiAvailable ? HOME_SWAP_AI_STEPS : HOME_SWAP_NON_AI_STEPS;
  if (step < HOME_SWAP_CONTEXT_STEP_COUNT) return matchingSteps[step];
  return matchingSteps[
    HOME_SWAP_CONTEXT_STEP_COUNT
    + (step - HOME_SWAP_CONTEXT_STEP_COUNT) % (matchingSteps.length - HOME_SWAP_CONTEXT_STEP_COUNT)
  ];
}

function dateLabel() {
  return new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "long" }).format(new Date());
}

function AnimatedWeatherCharacters({ text, start = 0 }: { text: string; start?: number }) {
  return Array.from(text).map((character, index) => <span aria-hidden="true" className="masked-weather-character" key={`${character}-${index}`} style={{ animationDelay: `${(start + index) * .12}s` }}>{character}</span>);
}

function weatherLabel(code: number) {
  if (code === 0) return "晴朗";
  if (code <= 3) return "多云";
  if (code <= 48) return "有雾";
  if (code <= 67 || code >= 80 && code <= 82) return "有雨";
  if (code <= 77 || code >= 85) return "有雪";
  return "雷雨";
}

function asCity(settings: BackendSettings): City {
  return { id: settings.city_id, name: simplifyLocationName(settings.city_name), country: "中国", latitude: settings.latitude, longitude: settings.longitude, timezone: settings.timezone };
}

export function requestFrom(weather: TodayWeather, settings: BackendSettings, scene: SceneId, excluded: string[] = []): RecommendationRequest {
  return {
    apparent_min: weather.apparent_min,
    apparent_max: weather.apparent_max,
    max_precipitation_probability: weather.max_precipitation_probability,
    total_precipitation: weather.total_precipitation,
    total_snowfall: weather.total_snowfall,
    max_wind_speed: weather.max_wind_speed,
    max_wind_gust: weather.max_wind_gust,
    uv_index_max: weather.uv_index_max,
    cold_offset: settings.cold_offset,
    scene,
    audience: settings.audience,
    city_id: settings.city_id,
    city_name: weather.city || settings.city_name,
    latitude: weather.latitude,
    longitude: weather.longitude,
    timezone: weather.timezone,
    local_date: weather.date,
    current_temperature: weather.current_temperature,
    current_apparent_temperature: weather.current_apparent_temperature,
    temperature_min: weather.temperature_min,
    temperature_max: weather.temperature_max,
    weather_code: weather.weather_code,
    excluded_template_ids: excluded,
  };
}

export function activeAIRecommendationForContext(
  raw: string,
  weather: TodayWeather,
  settings: BackendSettings,
): BackendRecommendation | null {
  try {
    const cached = JSON.parse(raw) as BackendRecommendation;
    return cached.source === "ai"
      && cached.constraints.local_date === weather.date
      && cached.constraints.city_id === settings.city_id
      && cached.audience === settings.audience
      ? cached
      : null;
  } catch {
    return null;
  }
}

function cacheActiveRecommendation(recommendation: BackendRecommendation) {
  try { localStorage.setItem("wearcue_active_outfit_v1", JSON.stringify(recommendation)); } catch { /* 无本地缓存时仍可正常使用 */ }
}

function subscribeActiveRecommendation() { return () => undefined; }
function activeRecommendationSnapshot() { return localStorage.getItem("wearcue_active_outfit_v1") || ""; }

export function TodayApp({ initial }: { initial: TodayInitialData | null }) {
  const router = useRouter();
  const savedProfile = useSyncExternalStore(subscribeProfile, profileSnapshot, () => "");
  const activeRecommendationRaw = useSyncExternalStore(subscribeActiveRecommendation, activeRecommendationSnapshot, () => "");
  let nickname = "";
  try { nickname = savedProfile ? String(JSON.parse(savedProfile).nickname || "").trim() : ""; } catch { nickname = ""; }
  const loadedOnce = useRef(Boolean(initial));
  const [settings, setSettings] = useState<BackendSettings | null>(initial?.settings ?? null);
  const outfitAreaRef = useRef<HTMLDivElement>(null);
  const [weather, setWeather] = useState<TodayWeather | null>(initial?.weather ?? null);
  const [recommendationsByScene, setRecommendationsByScene] = useState<RecommendationsByScene>(
    initial ? { [initial.recommendation.scene]: initial.recommendation } : {},
  );
  const [sceneState, setScene] = useState<SceneId>(initial?.recommendation.scene ?? "commute");
  const [useRestoredRecommendation, setUseRestoredRecommendation] = useState(true);
  const [status, setStatus] = useState<"loading" | "success" | "error">(initial ? "success" : "loading");
  const [message, setMessage] = useState("");
  const [cityPickerOpen, setCityPickerOpen] = useState(false);
  const [swapping, setSwapping] = useState(false);
  const [swapRequestPending, setSwapRequestPending] = useState(false);
  const [swapStatusStep, setSwapStatusStep] = useState(0);
  const [swapQuota, setSwapQuota] = useState<AIQuota | null>(null);
  const cachedRecommendation = weather && settings
    ? activeAIRecommendationForContext(activeRecommendationRaw, weather, settings)
    : null;
  const restoredRecommendation = useRestoredRecommendation ? cachedRecommendation : null;
  const scene = restoredRecommendation?.scene ?? sceneState;
  const recommendation = restoredRecommendation ?? recommendationsByScene[scene] ?? null;
  const minimumTemperature = weather ? `${Math.round(weather.apparent_min)}°` : "";
  const maximumTemperature = weather ? `${Math.round(weather.apparent_max)}°` : "";

  const loadToday = useCallback(async (activeScene: SceneId) => {
    setStatus("loading");
    setMessage("");
    try {
      const nextSettings = await apiJson<BackendSettings>("/settings");
      const query = new URLSearchParams({ latitude: String(nextSettings.latitude), longitude: String(nextSettings.longitude), city: nextSettings.city_name });
      const { weather: nextWeather } = await apiJson<{ weather: TodayWeather }>(`/weather/today?${query}`);
      const nextRecommendation = await apiJson<BackendRecommendation>("/recommendations/preview", {
        method: "POST",
        body: JSON.stringify(requestFrom(nextWeather, nextSettings, activeScene)),
      });
      cacheActiveRecommendation(nextRecommendation);
      setSettings(nextSettings);
      setWeather(nextWeather);
      setRecommendationsByScene((current) => withSceneRecommendation(current, nextRecommendation));
      setStatus("success");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "今日数据暂时不可用");
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    if (loadedOnce.current) return;
    loadedOnce.current = true;
    void loadToday("commute");
  }, [loadToday]);

  useEffect(() => {
    void apiJson<AIUsageQuota>("/ai-usage-quota")
      .then((quota) => setSwapQuota(quota.swap))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!swapRequestPending) return;
    const contextTimers = Array.from(
      { length: HOME_SWAP_CONTEXT_STEP_COUNT },
      (_, index) => window.setTimeout(() => setSwapStatusStep(index + 1), (index + 1) * 100),
    );
    const cycleTimer = window.setInterval(
      () => setSwapStatusStep((step) => step < HOME_SWAP_CONTEXT_STEP_COUNT ? step : step + 1),
      3000,
    );
    return () => {
      contextTimers.forEach((timer) => window.clearTimeout(timer));
      window.clearInterval(cycleTimer);
    };
  }, [swapRequestPending]);

  async function selectScene(nextScene: SceneId) {
    const existing = nextScene === scene ? recommendation : recommendationsByScene[nextScene];
    if (recommendation) {
      setRecommendationsByScene((current) => withSceneRecommendation(current, recommendation));
    }
    setUseRestoredRecommendation(false);
    setScene(nextScene);
    if (!weather || !settings) return;
    if (existing) {
      cacheActiveRecommendation(existing);
      return;
    }
    setSwapping(true);
    setMessage("");
    try {
      const nextRecommendation = await apiJson<BackendRecommendation>("/recommendations/preview", {
        method: "POST",
        body: JSON.stringify(requestFrom(weather, settings, nextScene)),
      });
      cacheActiveRecommendation(nextRecommendation);
      setRecommendationsByScene((current) => withSceneRecommendation(current, nextRecommendation));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "推荐暂时不可用");
    } finally { setSwapping(false); }
  }

  async function swap() {
    if (!weather || !settings || !recommendation) return;
    setRecommendationsByScene((current) => withSceneRecommendation(current, recommendation));
    setUseRestoredRecommendation(false);
    setSwapping(true);
    setSwapStatusStep(0);
    setSwapRequestPending(true);
    setMessage("");
    try {
      const nextRecommendation = await apiJson<BackendRecommendation>("/recommendations/swap", {
        method: "POST",
        body: JSON.stringify(requestFrom(weather, settings, scene, [recommendation.template_id])),
      });
      cacheActiveRecommendation(nextRecommendation);
      setRecommendationsByScene((current) => withSceneRecommendation(current, nextRecommendation));
      if (nextRecommendation.ai_quota) setSwapQuota(nextRecommendation.ai_quota);
      if (nextRecommendation.ai_fallback_reason === "quota_exhausted") {
        setMessage("今日实时 AI 换一套已用完，已为你切换非 AI 方案，仍可无限换。");
      } else if (nextRecommendation.ai_fallback_reason === "provider_failed") {
        setMessage("实时 AI 暂时不可用，已为你切换非 AI 方案，本次不扣额度。");
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "暂时没有更多合适方案");
    } finally { setSwapRequestPending(false); setSwapping(false); }
  }

  async function chooseCity(city: City) {
    setCityPickerOpen(false);
    setMessage("");
    try {
      await apiJson<BackendSettings>("/settings", {
        method: "POST",
        body: JSON.stringify({ city_id: city.id, city_name: city.name, latitude: city.latitude, longitude: city.longitude, timezone: city.timezone }),
      });
      setUseRestoredRecommendation(false);
      setRecommendationsByScene({});
      await loadToday(scene);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "城市切换失败");
      setStatus("error");
    }
  }

  async function locate() {
    await chooseCity(await locateCurrentDistrict());
  }

  function outfitItem(item: BackendRecommendation["items"][number], index: number) {
    return <div className="recommendation-outfit-item" key={`${item.slot}-${index}`}><OutfitIcon item={item} audience={recommendation!.audience} /><div><strong>{item.variant_type}</strong><em>{item.color_name}、{thicknessLabel(item.thickness)}</em></div></div>;
  }

  function viewOutfit() {
    if (!recommendation) return;
    let activeRecommendation = recommendation;
    try {
      const cached = JSON.parse(localStorage.getItem("wearcue_active_outfit_v1") || "null") as BackendRecommendation | null;
      if (cached?.template_id === recommendation.template_id && cached.replication_guide && cached.outfit_analysis) {
        activeRecommendation = {
          ...recommendation,
          replication_guide: cached.replication_guide,
          outfit_analysis: cached.outfit_analysis,
        };
      }
    } catch { /* 使用当前推荐覆盖无效缓存 */ }
    cacheActiveRecommendation(activeRecommendation);
    router.push(`/outfit/${recommendation.template_id}`);
  }

  return (
    <main className="paper-page today-paper">
      <section className="paper-hero compact-hero">
        <p className="paper-kicker">天气 × 场景 × 穿搭</p>
        <TypingHeadline key={nickname || "guest"} firstLine={nickname ? `${nickname}，今天穿什么，` : "今天穿什么，"} secondLine="现在就有答案。" />
      </section>

      {status === "error" && !weather && !recommendation && <section className="paper-state" role="alert"><span>连接中断</span><h2>今天的天气还没拿到</h2><p>{message}</p><button className="sunshine-button" onClick={() => void loadToday(scene)}>重新获取</button></section>}

      {weather && recommendation && <>
        <section className="today-overview">
          <article className="weather-paper-card">
            <div className="weather-card-head">
              <div className="card-caption weather-date-caption">{dateLabel()}</div>
              <button className="card-location-button" onClick={() => setCityPickerOpen(true)} aria-label={`选择位置，当前${simplifyLocationName(settings?.city_name) || "北京"}`}><span className="status-dot" />{simplifyLocationName(settings?.city_name) || "北京"}<svg className="location-chevron" viewBox="0 0 12 12" aria-hidden="true"><path d="m2.5 4.5 3.5 3 3.5-3" /></svg></button>
            </div>
            <div className="temperature-range" aria-label={`体感温度 ${minimumTemperature} 到 ${maximumTemperature}`}><strong key={`min-${minimumTemperature}`}><AnimatedWeatherCharacters text={minimumTemperature} /></strong><i aria-hidden="true" className="masked-weather-character" style={{ animationDelay: `${minimumTemperature.length * .12}s` }}>—</i><strong key={`max-${maximumTemperature}`}><AnimatedWeatherCharacters text={maximumTemperature} start={minimumTemperature.length + 1} /></strong></div>
            <div className="weather-summary"><h2>{weatherLabel(weather.weather_code)}</h2><p>全天体感范围 · 当前体感 {Math.round(weather.current_apparent_temperature)}°</p></div>
            {(recommendation.constraints.needs_waterproof || recommendation.constraints.needs_sun_protection || recommendation.constraints.needs_windproof) && <div className="weather-alerts">
              {recommendation.constraints.needs_waterproof && <span>注意防雨</span>}
              {recommendation.constraints.needs_sun_protection && <span>注意防晒</span>}
              {recommendation.constraints.needs_windproof && <span>注意防风</span>}
            </div>}
            <div className="weather-metrics">
              <span><b key={`precipitation-${Math.round(weather.max_precipitation_probability)}`} className="masked-weather-value reveal-delay-2">{Math.round(weather.max_precipitation_probability)}%</b>降水概率</span>
              <span><b key={`gust-${Math.round(weather.max_wind_gust)}`} className="masked-weather-value reveal-delay-3">{Math.round(weather.max_wind_gust)}</b>最大阵风</span>
              <span><b key={`uv-${Math.round(weather.uv_index_max)}`} className="masked-weather-value reveal-delay-4">{Math.round(weather.uv_index_max)}</b>紫外线</span>
            </div>
          </article>
          <div className="recommendation-card-wrap">
            <Image className="recommendation-mascot" src="/brand/wearcue-bear.png" alt="" width={1536} height={1024} priority />
            <article className="recommendation-copy-card">
            <div className="recommendation-card-head">
              <div className="card-caption"><span className="status-dot mint" />今日推荐 <small className="recommendation-source">{recommendation.source === "personal" ? "来自个人首页推荐" : recommendation.source === "system_ai" ? "系统推荐" : "AI推荐方案"}</small></div>
              <div className="card-scene-switch" aria-label="穿搭场景">
                {scenes.map((item) => <button key={item.id} className={scene === item.id ? "active" : ""} disabled={swapping} onClick={() => void selectScene(item.id)}>{item.label}</button>)}
              </div>
            </div>
            <div className="recommendation-title-row"><div className="recommendation-title-copy"><h2>{recommendation.label}</h2><p>{recommendation.constraints.apparent_delta >= 8 ? "早晚温差明显，建议把外层做成可以随时穿脱的一层。" : "今天温差相对稳定，按这一套出门就够了。"}</p></div><button className="view-outfit-button" onClick={viewOutfit}>{recommendation.source === "ai" ? "生成 AI 穿搭方案" : "查看穿搭"}<svg viewBox="0 0 18 18" aria-hidden="true"><path d="M4 9h10M10 5l4 4-4 4" /></svg></button></div>
            {message && <p className="inline-message" role="status">{message}</p>}
            <div className="recommendation-outfit-area" ref={outfitAreaRef}>
              <div className="recommendation-outfit-head"><span>今日搭配<small>{recommendation.items.length} 件{recommendation.items.length > 6 ? " · 可滚动" : ""}{swapQuota ? ` · 今日 AI 生成剩余 ${swapQuota.remaining}/${swapQuota.limit}` : ""} · 非 AI 不限次</small></span><button aria-busy={swapRequestPending} disabled={swapping} onClick={() => void swap()}>{!swapRequestPending && <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M13.5 5.5A6 6 0 1 0 14 9" /><path d="M10.5 2.5h3v3" /></svg>}<span>{swapRequestPending ? homeSwapStatus(swapStatusStep, swapQuota?.remaining !== 0) : "换一套"}</span></button></div>
              <div className="recommendation-outfit-strip" aria-label={`今日搭配，共 ${recommendation.items.length} 件`} tabIndex={recommendation.items.length > 6 ? 0 : undefined}>
                {[...recommendation.items].sort((a, b) => outfitItemSortKey(a) - outfitItemSortKey(b)).map(outfitItem)}
              </div>
            </div>
            </article>
          </div>
        </section>

      </>}

      {cityPickerOpen && settings && <CityPicker current={asCity(settings)} onSelect={chooseCity} onLocate={locate} onClose={() => setCityPickerOpen(false)} />}

    </main>
  );
}

function thicknessLabel(value: string) {
  return ({ thin: "薄款", regular: "常规", thick: "厚款" } as Record<string, string>)[value] ?? value;
}
