"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore, type CSSProperties } from "react";
import { useRouter } from "next/navigation";
import { CityPicker } from "./CityPicker";
import { TimePicker } from "./TimePicker";
import { profileSnapshot, subscribeProfile } from "./AppNav";
import { apiJson } from "@/lib/backend-api";
import { ensurePushSubscription } from "@/lib/push";
import { clearTodaySession } from "@/lib/today-session";
import type { City } from "@/domain/types";
import { locateCurrentDistrict, simplifyLocationName } from "@/lib/browser-location";
import type { Audience, BackendSettings } from "@/domain/backend";

type UserProfile = { id?: string; nickname: string; avatar: string; gender?: "mens" | "womens"; invited?: boolean };
type CurrentUser = { id: string };
type BodyProfile = Pick<BackendSettings, "height_group" | "weight_group">;
const heightGroups: BodyProfile["height_group"][] = ["偏矮", "中等", "偏高"];
const weightGroups: BodyProfile["weight_group"][] = ["偏轻", "中等", "偏重"];
const emptyProfile: UserProfile = { nickname: "", avatar: "" };

function rangeProgress(value: number, min: number, max: number) {
  return { "--range-progress": `${((value - min) / (max - min)) * 100}%` } as CSSProperties;
}

function asCity(settings: BackendSettings): City {
  return { id: settings.city_id, name: simplifyLocationName(settings.city_name), country: "中国", latitude: settings.latitude, longitude: settings.longitude, timezone: settings.timezone };
}

export function SettingsApp() {
  const router = useRouter();
  const savedProfile = useSyncExternalStore(subscribeProfile, profileSnapshot, () => "");
  let profile: UserProfile = emptyProfile;
  try { profile = savedProfile ? JSON.parse(savedProfile) : emptyProfile; } catch { profile = emptyProfile; }
  const nickname = profile.nickname.trim() || "我";
  const avatarLetter = nickname.charAt(0);
  const avatarInputRef = useRef<HTMLInputElement>(null);
  const [nicknameDraft, setNicknameDraft] = useState<string | null>(null);
  const displayNickname = nicknameDraft ?? nickname;
  const [userId, setUserId] = useState("");
  const [settings, setSettings] = useState<BackendSettings | null>(null);
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");
  const [cityOpen, setCityOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [bodyDraft, setBodyDraft] = useState<BodyProfile | null>(null);
  const bodySaveTimer = useRef<number | null>(null);

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      const [nextSettings, session] = await Promise.all([
        apiJson<BackendSettings>("/settings"),
        apiJson<{ user: CurrentUser }>("/auth/me"),
      ]);
      setSettings(nextSettings);
      setUserId(session.user.id);
      setStatus("success");
    }
    catch (error) { setMessage(error instanceof Error ? error.message : "设置加载失败"); setStatus("error"); }
  }, []);
  useEffect(() => {
    // Loading the backend is the intended external-system synchronization.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  useEffect(() => {
    if (!message || saving || status !== "success") return;
    const timer = window.setTimeout(() => setMessage(""), 2400);
    return () => window.clearTimeout(timer);
  }, [message, saving, status]);

  useEffect(() => () => {
    if (bodySaveTimer.current !== null) window.clearTimeout(bodySaveTimer.current);
  }, []);

  async function update(patch: Record<string, unknown>, successMessage = "设置已保存") {
    setSaving(true); setMessage("");
    try { setSettings(await apiJson<BackendSettings>("/settings", { method: "POST", body: JSON.stringify(patch) })); clearTodaySession(); setMessage(successMessage); return true; }
    catch (error) { setMessage(error instanceof Error ? error.message : "保存失败"); return false; }
    finally { setSaving(false); }
  }

  async function chooseCity(city: City) {
    setCityOpen(false);
    await update({ city_id: city.id, city_name: city.name, latitude: city.latitude, longitude: city.longitude, timezone: city.timezone });
  }

  async function locate() {
    await chooseCity(await locateCurrentDistrict());
  }

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => undefined);
    localStorage.removeItem("wearcue_profile_v1");
    clearTodaySession();
    window.dispatchEvent(new Event("wearcue-profile"));
    router.replace("/login");
  }

  function saveProfile(patch: Partial<UserProfile>) {
    const next = { ...profile, ...patch };
    localStorage.setItem("wearcue_profile_v1", JSON.stringify(next));
    window.dispatchEvent(new Event("wearcue-profile"));
    setNicknameDraft(null);
  }

  async function changeAvatar(file?: File) {
    if (!file || !file.type.startsWith("image/")) return;
    const source = URL.createObjectURL(file);
    try {
      const image = document.createElement("img");
      image.src = source;
      await image.decode();
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 256;
      const context = canvas.getContext("2d");
      if (context) {
        const side = Math.min(image.naturalWidth, image.naturalHeight);
        context.drawImage(image, (image.naturalWidth - side) / 2, (image.naturalHeight - side) / 2, side, side, 0, 0, 256, 256);
        saveProfile({ avatar: canvas.toDataURL("image/jpeg", 0.82) });
      }
    } catch {
      setMessage("头像处理失败，请换一张图片");
    } finally {
      URL.revokeObjectURL(source);
      if (avatarInputRef.current) avatarInputRef.current.value = "";
    }
  }

  async function saveNickname() {
    const name = displayNickname.trim().slice(0, 5);
    if (!name || name === profile.nickname) { setNicknameDraft(null); return; }
    saveProfile({ nickname: name });
    try {
      await apiJson("/auth/profile", { method: "POST", body: JSON.stringify({ nickname: name }) });
    } catch {
      /* 本地已更新，后端同步失败时不打断 */
    }
  }

  async function toggleReminder(enabled: boolean) {
    setSaving(true); setMessage("");
    try {
      // 权限请求需在用户手势上下文内，先于网络请求执行（Safari 要求）
      const pushStatus = enabled ? await ensurePushSubscription() : null;
      await apiJson<BackendSettings>("/settings", { method: "POST", body: JSON.stringify({ reminder_enabled: enabled }) });
      clearTodaySession();
      setSettings(await apiJson<BackendSettings>("/settings"));
      if (enabled) {
        if (pushStatus === "enabled") setMessage("提醒已开启，浏览器通知已就绪");
        else if (pushStatus === "denied") setMessage("提醒已开启，但浏览器通知被拒绝，请在浏览器设置里允许");
        else if (pushStatus === "unsupported") setMessage("提醒已开启，但当前浏览器不支持系统通知");
        else if (pushStatus === "provider_missing") setMessage("提醒已开启，但服务端推送未配置");
        else setMessage("提醒已开启，通知订阅失败，请稍后重试");
      } else {
        setMessage("提醒已关闭");
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  const bodyProfile = settings ? bodyDraft ?? {
    height_group: settings.height_group,
    weight_group: settings.weight_group,
  } : null;

  function changeBodyProfile<K extends keyof BodyProfile>(key: K, value: BodyProfile[K]) {
    if (!bodyProfile) return;
    const next = { ...bodyProfile, [key]: value };
    setBodyDraft(next);
    if (bodySaveTimer.current !== null) window.clearTimeout(bodySaveTimer.current);
    bodySaveTimer.current = window.setTimeout(async () => {
      bodySaveTimer.current = null;
      if (await update(next, "改动已实时更新保存")) setBodyDraft(null);
    }, 250);
  }

  return <main className="paper-page settings-paper">
    <header className="settings-profile-head">
      <div className="settings-profile-id">
        <button type="button" className="settings-avatar-button" onClick={() => avatarInputRef.current?.click()} aria-label="更换头像" title="更换头像">
          {profile.avatar ? <span className="settings-avatar-photo" style={{ backgroundImage: `url(${profile.avatar})` }} /> : <span className="settings-avatar-letter">{avatarLetter}</span>}
        </button>
        <input ref={avatarInputRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(event) => void changeAvatar(event.target.files?.[0])} />
        <div className="settings-profile-copy">
          <input className="settings-nickname-input" value={displayNickname} maxLength={5} aria-label="昵称" onChange={(event) => setNicknameDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void saveNickname(); }} />
          {userId && <span className="settings-user-id">ID：{userId}</span>}
        </div>
        {displayNickname.trim() && displayNickname.trim() !== nickname ? <button type="button" className="settings-nickname-save" onClick={() => void saveNickname()}>保存</button> : null}
      </div>
    </header>
    {status === "loading" && <section className="paper-loading"><div /><div /><div /></section>}
    {status === "error" && <section className="paper-state"><h2>设置暂时打不开</h2><p>{message}</p><button className="sunshine-button" onClick={() => void load()}>重新加载</button></section>}
    {status === "success" && settings && <div className="settings-paper-grid">
      {bodyProfile && <section className="settings-paper-card body-profile-card"><div className="card-caption">基本信息</div><h2>身高</h2><p>用于生成更贴近你的穿搭建议与人物效果图。</p><div className="body-profile-ranges"><label><input aria-label="身高段" className="paper-range" type="range" min="0" max="2" step="1" value={heightGroups.indexOf(bodyProfile.height_group)} style={rangeProgress(heightGroups.indexOf(bodyProfile.height_group), 0, 2)} onChange={(event) => changeBodyProfile("height_group", heightGroups[Number(event.target.value)])} /><div className="range-labels">{heightGroups.map((group) => group === bodyProfile.height_group ? <b key={group}>{group}</b> : <span key={group}>{group}</span>)}</div></label></div></section>}
      {bodyProfile && <section className="settings-paper-card body-profile-card"><div className="card-caption">基本信息</div><h2>体重</h2><p>用于生成更贴近你的穿搭建议与人物效果图。</p><div className="body-profile-ranges"><label><input aria-label="体重段" className="paper-range" type="range" min="0" max="2" step="1" value={weightGroups.indexOf(bodyProfile.weight_group)} style={rangeProgress(weightGroups.indexOf(bodyProfile.weight_group), 0, 2)} onChange={(event) => changeBodyProfile("weight_group", weightGroups[Number(event.target.value)])} /><div className="range-labels">{weightGroups.map((group) => group === bodyProfile.weight_group ? <b key={group}>{group}</b> : <span key={group}>{group}</span>)}</div></label></div></section>}
      <section className="settings-paper-card"><div className="card-caption">所在城市</div><h2>常用城市</h2><p>天气与推荐默认按这里的城市计算。</p><button className="setting-value" onClick={() => setCityOpen(true)}><span><b>{simplifyLocationName(settings.city_name)}</b><small>{settings.timezone}</small></span><strong>更改 →</strong></button></section>
      <section className="settings-paper-card"><div className="card-caption">每日提醒</div><div className="settings-card-title-row"><h2>晨间提醒</h2><label className="settings-switch"><input aria-label="开启晨间提醒" type="checkbox" checked={settings.reminder_enabled} onChange={(event) => void toggleReminder(event.target.checked)} /></label></div><p>每天在你设定的时间提醒查看穿搭。</p>{settings.reminder_enabled && <div className="paper-field"><span>提醒时间</span><TimePicker value={settings.reminder_time} onChange={(value) => void update({ reminder_time: value })} /></div>}</section>
      <section className="settings-paper-card"><div className="card-caption">体感偏好</div><h2>冷热偏好</h2><p>怕冷就向右微调，怕热就向左微调。</p><input className="paper-range" type="range" min="-6" max="6" step="2" value={settings.cold_offset} style={{ "--range-progress": `${((settings.cold_offset + 6) / 12) * 100}%` } as CSSProperties} onChange={(event) => void update({ cold_offset: Number(event.target.value) })} /><div className="range-labels"><span>更怕热</span><b>{settings.cold_offset === 0 ? "标准体感" : `${settings.cold_offset > 0 ? "+" : ""}${settings.cold_offset}°`}</b><span>更怕冷</span></div></section>
      <section className="settings-paper-card"><div className="card-caption">穿搭偏好</div><h2>性别与服饰</h2><p>选择一次，上传识别和每日推荐都会默认沿用；配件继续共用。</p><div className="choice-grid">{(["mens", "womens"] as Audience[]).map((audience) => <button key={audience} className={settings.audience === audience ? "selected-choice" : ""} onClick={() => void update({ audience })}><b>{audience === "mens" ? "男装" : "女装"}</b><span>{audience === "mens" ? "男士相关穿搭" : "女士相关穿搭"}</span></button>)}</div></section>
    </div>}
    <button className="settings-logout-button" onClick={() => void logout()}>退出登录</button>
    {message && status === "success" && <div className={`save-notice ${saving ? "" : "ready"}`} aria-live="polite">{saving ? "正在保存…" : message}</div>}
    {cityOpen && settings && <CityPicker current={asCity(settings)} onSelect={chooseCity} onLocate={locate} onClose={() => setCityOpen(false)} />}
  </main>;
}
