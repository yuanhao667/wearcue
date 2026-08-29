"use client";

import { useCallback, useEffect, useState } from "react";
import { CityPicker } from "./CityPicker";
import { apiJson } from "@/lib/backend-api";
import type { City } from "@/domain/types";
import { simplifyLocationName } from "@/lib/browser-location";
import type { Audience, BackendSettings } from "@/domain/backend";

function asCity(settings: BackendSettings): City {
  return { id: settings.city_id, name: simplifyLocationName(settings.city_name), country: "中国", latitude: settings.latitude, longitude: settings.longitude, timezone: settings.timezone };
}

export function SettingsApp() {
  const [settings, setSettings] = useState<BackendSettings | null>(null);
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");
  const [cityOpen, setCityOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setStatus("loading");
    try { setSettings(await apiJson<BackendSettings>("/settings")); setStatus("success"); }
    catch (error) { setMessage(error instanceof Error ? error.message : "设置加载失败"); setStatus("error"); }
  }, []);
  useEffect(() => {
    // Loading the backend is the intended external-system synchronization.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function update(patch: Record<string, unknown>) {
    setSaving(true); setMessage("");
    try { setSettings(await apiJson<BackendSettings>("/settings", { method: "POST", body: JSON.stringify(patch) })); setMessage("设置已保存"); }
    catch (error) { setMessage(error instanceof Error ? error.message : "保存失败"); }
    finally { setSaving(false); }
  }

  async function chooseCity(city: City) {
    setCityOpen(false);
    await update({ city_id: city.id, city_name: city.name, latitude: city.latitude, longitude: city.longitude, timezone: city.timezone });
  }

  return <main className="paper-page settings-paper">
    {status === "loading" && <section className="paper-loading"><div /><div /><div /></section>}
    {status === "error" && <section className="paper-state"><h2>设置暂时打不开</h2><p>{message}</p><button className="sunshine-button" onClick={() => void load()}>重新加载</button></section>}
    {status === "success" && settings && <div className="settings-paper-grid">
      <section className="settings-paper-card"><div className="card-caption">所在城市</div><h2>常用城市</h2><p>天气与推荐默认按这里的城市计算。</p><button className="setting-value" onClick={() => setCityOpen(true)}><span><b>{simplifyLocationName(settings.city_name)}</b><small>{settings.timezone}</small></span><strong>更改 →</strong></button></section>
      <section className="settings-paper-card"><div className="card-caption">穿搭偏好</div><h2>默认服装</h2><p>选择一次，上传识别和每日推荐都会默认沿用；配件继续共用。</p><div className="choice-grid">{(["mens", "womens"] as Audience[]).map((audience) => <button key={audience} className={settings.audience === audience ? "selected-choice" : ""} onClick={() => void update({ audience })}><b>{audience === "mens" ? "男装" : "女装"}</b><span>{audience === "mens" ? "男性基础款" : "女性基础款与裙装"}</span></button>)}</div></section>
      <section className="settings-paper-card"><div className="card-caption">体感偏好</div><h2>冷热偏好</h2><p>怕冷就向右微调，怕热就向左微调。</p><input className="paper-range" type="range" min="-6" max="6" step="2" value={settings.cold_offset} onChange={(event) => void update({ cold_offset: Number(event.target.value) })} /><div className="range-labels"><span>更怕热</span><b>{settings.cold_offset === 0 ? "标准体感" : `${settings.cold_offset > 0 ? "+" : ""}${settings.cold_offset}°`}</b><span>更怕冷</span></div></section>
      <section className="settings-paper-card"><div className="card-caption">每日提醒</div><div className="settings-card-title-row"><h2>晨间提醒</h2><label className="settings-switch"><input aria-label="开启晨间提醒" type="checkbox" checked={settings.reminder_enabled} onChange={(event) => void update({ reminder_enabled: event.target.checked })} /></label></div><p>每天在你设定的时间提醒查看穿搭。</p>{settings.reminder_enabled && <label className="paper-field"><span>提醒时间</span><input type="time" value={settings.reminder_time} onChange={(event) => void update({ reminder_time: event.target.value })} /></label>}</section>
    </div>}
    {message && status === "success" && <div className={`save-notice ${saving ? "" : "ready"}`} aria-live="polite">{saving ? "正在保存…" : message}</div>}
    {cityOpen && settings && <CityPicker current={asCity(settings)} onSelect={chooseCity} onClose={() => setCityOpen(false)} />}
  </main>;
}
