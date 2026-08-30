"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { locateCurrentDistrict, saveLoginLocation } from "@/lib/browser-location";
import { clearTodaySession } from "@/lib/today-session";

type Gender = "mens" | "womens";
type FieldError = "nickname" | "gender" | "inviteCode" | "";

function GenderIcon({ gender }: { gender: Gender }) {
  return gender === "mens" ? (
    <svg className="login-gender-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="4" r="2.6" /><path d="M7.2 8.2h9.6l2.1 6.2-2.4.8-1.4-4v10h-2.3v-6.5h-1.6v6.5H8.9v-10l-1.4 4-2.4-.8 2.1-6.2Z" /></svg>
  ) : (
    <svg className="login-gender-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="4" r="2.6" /><path d="M8.1 8.2h7.8l3.2 7.6h-3.5v5.4h-2.3v-5.4h-2.6v5.4H8.4v-5.4H4.9l3.2-7.6Z" /></svg>
  );
}

export function LoginApp() {
  const router = useRouter();
  const [nickname, setNickname] = useState("");
  const [gender, setGender] = useState<Gender | "">("");
  const [inviteCode, setInviteCode] = useState("");
  const [fieldError, setFieldError] = useState<FieldError>("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [locationAllowed, setLocationAllowed] = useState(false);
  const [locating, setLocating] = useState(false);
  const [permissionShake, setPermissionShake] = useState(0);

  async function changeLocationPermission(checked: boolean) {
    if (!checked) {
      setLocationAllowed(false);
      return;
    }
    setError("");
    setLocating(true);
    try {
      const location = await locateCurrentDistrict();
      saveLoginLocation(location);
      setLocationAllowed(true);
    } catch (reason) {
      setLocationAllowed(false);
      setError(reason instanceof Error ? reason.message : "暂时无法获取位置");
    } finally {
      setLocating(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanNickname = nickname.trim();
    setError("");
    if (!cleanNickname) { setFieldError("nickname"); return; }
    if (!gender) { setFieldError("gender"); return; }
    if (!inviteCode.trim()) { setFieldError("inviteCode"); return; }
    if (!locationAllowed) { setPermissionShake((current) => current + 1); return; }
    setFieldError(""); setSubmitting(true);
    try {
      const result = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nickname: cleanNickname, gender, inviteCode }),
      });
      const payload = await result.json() as { ok?: boolean; error?: string; user?: { id: string; nickname: string; gender: Gender } };
      if (!result.ok || !payload.ok) throw new Error(payload.error || "登录失败，请稍后重试");
      const user = payload.user || { nickname: cleanNickname.slice(0, 5), gender };
      clearTodaySession();
      localStorage.setItem("wearcue_profile_v1", JSON.stringify({ id: "id" in user ? user.id : undefined, nickname: user.nickname, avatar: "", gender: user.gender, invited: true }));
      window.dispatchEvent(new Event("wearcue-profile"));
      router.replace("/");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "登录失败，请稍后重试"); }
    finally { setSubmitting(false); }
  }

  return <main className="login-page">
    <section className="login-brand-panel">
      <Image className="login-logo" src="/brand/wearcue-logo-20260828.png" alt="WearCue" width={1774} height={887} priority />
      <Image className="login-ip" src="/illustrations/login-ip-bear.png" alt="" width={1024} height={1536} aria-hidden="true" priority />
      <div className="login-brand-copy">
        <span>WEATHER × SCENE × OUTFIT</span>
        <h1>每天少想一件事，<br /><mark>穿什么。</mark></h1>
        <p>把天气、场景和你的穿搭灵感，变成每天可以直接执行的答案。</p>
      </div>
      <strong aria-hidden="true">WearCue</strong>
    </section>

    <section className="login-form-panel">
      <form className="login-form login-form-simple" noValidate onSubmit={submit}>
        <div className="login-form-head"><h2>登录</h2><p>欢迎来到 WearCue，搞定你的每日穿搭</p></div>
        <label className="login-field"><span className="login-field-label">昵称（最多 5 个汉字）</span><input aria-invalid={fieldError === "nickname"} aria-required="true" autoFocus maxLength={5} value={nickname} onChange={(event) => { setNickname(event.target.value); if (fieldError === "nickname") setFieldError(""); }} placeholder="怎么称呼你？" />{fieldError === "nickname" && <span className="login-field-tip" role="alert">请填写昵称</span>}</label>
        <fieldset className="login-gender-fieldset"><legend>性别</legend><div>
          <button type="button" className={gender === "mens" ? "active" : ""} aria-pressed={gender === "mens"} onClick={() => { setGender("mens"); if (fieldError === "gender") setFieldError(""); }}><span><GenderIcon gender="mens" /></span><b>男士</b><svg className="login-gender-check" viewBox="0 0 18 18" aria-hidden="true"><path d="m3.5 9.5 3.3 3.3 7.7-8" /></svg></button>
          <button type="button" className={gender === "womens" ? "active" : ""} aria-pressed={gender === "womens"} onClick={() => { setGender("womens"); if (fieldError === "gender") setFieldError(""); }}><span><GenderIcon gender="womens" /></span><b>女士</b><svg className="login-gender-check" viewBox="0 0 18 18" aria-hidden="true"><path d="m3.5 9.5 3.3 3.3 7.7-8" /></svg></button>
        </div>{fieldError === "gender" && <span className="login-field-tip" role="alert">请选择性别</span>}</fieldset>
        <label className="login-field"><span className="login-field-label">邀请码</span><input aria-invalid={fieldError === "inviteCode"} aria-required="true" autoComplete="one-time-code" value={inviteCode} onChange={(event) => { setInviteCode(event.target.value); if (fieldError === "inviteCode") setFieldError(""); }} placeholder="输入邀请码" />{fieldError === "inviteCode" && <span className="login-field-tip" role="alert">请填写邀请码</span>}</label>
        {error && <p className="login-error" role="alert">{error}</p>}
        <label className={`login-permission${permissionShake ? " is-shaking" : ""}`} key={permissionShake}>
          <input checked={locationAllowed} disabled={locating} onChange={(event) => void changeLocationPermission(event.target.checked)} type="checkbox" />
          <span className="login-permission-check" aria-hidden="true"><svg viewBox="0 0 18 18"><path d="m3.5 9.5 3.3 3.3 7.7-8" /></svg></span>
          <strong>允许访问位置和天气</strong>
        </label>
        <button aria-disabled={submitting || locating || !locationAllowed} className="login-submit" disabled={submitting || locating} type="submit"><span>{submitting ? "正在进入…" : "进入我的 WearCue"}</span><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3.5 10h12M11 5.5l4.5 4.5-4.5 4.5" /></svg></button>
        <p className="login-footnote">继续即表示你接受邀请并同意保存上述个人偏好。</p>
      </form>
    </section>
  </main>;
}
