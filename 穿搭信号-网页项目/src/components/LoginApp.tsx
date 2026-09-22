"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";
import { locateCurrentDistrict, saveLoginLocation } from "@/lib/browser-location";
import { clearTodaySession } from "@/lib/today-session";
import type { City } from "@/domain/types";
import { GenderIcon } from "./GenderIcon";

type Gender = "mens" | "womens";
type AuthMode = "login" | "register";
type View = AuthMode | "reset" | "onboarding";
type FieldError = "email" | "password" | "inviteCode" | "verificationCode" | "nickname" | "gender" | "";
type User = { id: string; nickname: string; gender: Gender; profileCompleted: boolean };

function validEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

function requestError(reason: unknown, fallback: string) {
  if ((reason instanceof Error || reason instanceof DOMException) && (reason.name === "TimeoutError" || reason.name === "AbortError")) {
    return "请求超时，请检查网络后重试";
  }
  if (reason instanceof TypeError) return "网络连接失败，请检查网络后重试";
  return reason instanceof Error ? reason.message : fallback;
}

export function LoginApp({ initialUser = null }: { initialUser?: User | null }) {
  const router = useRouter();
  const busy = useRef(false);
  const [view, setView] = useState<View>(initialUser ? "onboarding" : "register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [nickname, setNickname] = useState("");
  const [gender, setGender] = useState<Gender | "">("");
  const [currentUser, setCurrentUser] = useState<User | null>(initialUser);
  const [fieldError, setFieldError] = useState<FieldError>("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sendingCode, setSendingCode] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [locationAllowed, setLocationAllowed] = useState(false);
  const [loginLocation, setLoginLocation] = useState<City | null>(null);
  const [locating, setLocating] = useState(false);
  const [permissionShake, setPermissionShake] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setInterval(() => setCooldown((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [cooldown]);

  function switchView(next: View) {
    setView(next);
    setFieldError("");
    setError("");
    setNotice("");
    setVerificationCode("");
  }

  function finishLogin(user: User) {
    clearTodaySession();
    localStorage.setItem("wearcue_profile_v1", JSON.stringify({
      id: user.id, nickname: user.nickname, avatar: "", gender: user.gender, invited: true,
    }));
    window.dispatchEvent(new Event("wearcue-profile"));
    router.replace("/");
  }

  async function changeLocationPermission(checked: boolean) {
    if (!checked) { setLocationAllowed(false); setLoginLocation(null); return; }
    setError("");
    setLocating(true);
    try {
      const location = await locateCurrentDistrict();
      saveLoginLocation(location);
      setLoginLocation(location);
      setLocationAllowed(true);
    } catch (reason) {
      setLocationAllowed(false);
      setLoginLocation(null);
      setError(reason instanceof Error ? reason.message : "暂时无法获取位置");
    } finally { setLocating(false); }
  }

  async function sendCode(purpose: "register" | "reset") {
    if (busy.current || cooldown > 0) return;
    setError(""); setNotice("");
    if (!validEmail(email)) { setFieldError("email"); return; }
    if (purpose === "register" && !inviteCode.trim()) { setFieldError("inviteCode"); return; }
    setFieldError(""); busy.current = true; setSendingCode(true);
    try {
      const response = await fetch("/api/auth/email-code", {
        method: "POST", signal: AbortSignal.timeout(15000),
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(), purpose,
          ...(purpose === "register" ? { inviteCode: inviteCode.trim() } : {}),
        }),
      });
      const payload = await response.json() as { ok?: boolean; error?: string; retry_after?: number; dev_code?: string };
      if (!response.ok || !payload.ok) throw new Error(payload.error || "验证码发送失败，请稍后重试");
      setCooldown(payload.retry_after || 60);
      if (payload.dev_code) setVerificationCode(payload.dev_code);
      setNotice(payload.dev_code ? "开发环境验证码已自动填入" : "验证码已发送，请检查邮箱");
    } catch (reason) { setError(requestError(reason, "验证码发送失败，请稍后重试")); }
    finally { busy.current = false; setSendingCode(false); }
  }

  async function submitAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current) return;
    const mode = view as AuthMode;
    setError(""); setNotice("");
    if (!validEmail(email)) { setFieldError("email"); return; }
    if (password.length < 8) { setFieldError("password"); return; }
    if (mode === "register" && !inviteCode.trim()) { setFieldError("inviteCode"); return; }
    if (mode === "register" && !/^\d{6}$/.test(verificationCode)) { setFieldError("verificationCode"); return; }
    setFieldError(""); busy.current = true; setSubmitting(true);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST", signal: AbortSignal.timeout(15000),
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(mode === "register" ? {
          mode, email: email.trim(), password, inviteCode: inviteCode.trim(), verificationCode,
        } : { mode, email: email.trim(), password }),
      });
      const payload = await response.json() as { ok?: boolean; error?: string; user?: User };
      if (!response.ok || !payload.ok || !payload.user) {
        throw new Error(payload.error || (mode === "register" ? "注册失败，请稍后重试" : "登录失败，请稍后重试"));
      }
      if (!payload.user.profileCompleted) {
        setCurrentUser(payload.user);
        switchView("onboarding");
      } else {
        finishLogin(payload.user);
      }
    } catch (reason) { setError(requestError(reason, "账号操作失败，请稍后重试")); }
    finally { busy.current = false; setSubmitting(false); }
  }

  async function submitReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current) return;
    setError(""); setNotice("");
    if (!validEmail(email)) { setFieldError("email"); return; }
    if (!/^\d{6}$/.test(verificationCode)) { setFieldError("verificationCode"); return; }
    if (password.length < 8) { setFieldError("password"); return; }
    setFieldError(""); busy.current = true; setSubmitting(true);
    try {
      const response = await fetch("/api/auth/reset-password", {
        method: "POST", signal: AbortSignal.timeout(15000), headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), verificationCode, password }),
      });
      const payload = await response.json() as { ok?: boolean; error?: string };
      if (!response.ok || !payload.ok) throw new Error(payload.error || "密码重置失败，请稍后重试");
      setPassword(""); switchView("login"); setNotice("密码已重置，请使用新密码登录");
    } catch (reason) { setError(requestError(reason, "密码重置失败，请稍后重试")); }
    finally { busy.current = false; setSubmitting(false); }
  }

  async function submitOnboarding(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current) return;
    const cleanNickname = nickname.trim();
    setError("");
    if (!cleanNickname) { setFieldError("nickname"); return; }
    if (!gender) { setFieldError("gender"); return; }
    if (locating || !locationAllowed || !loginLocation) {
      setPermissionShake((value) => value + 1);
      setError("请先允许访问位置和天气，成功获取位置后再进入。");
      return;
    }
    setFieldError(""); busy.current = true; setSubmitting(true);
    try {
      const settingsResponse = await fetch("/api/backend/settings", {
        method: "POST", signal: AbortSignal.timeout(15000), headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          city_id: loginLocation.id,
          city_name: loginLocation.name,
          latitude: loginLocation.latitude,
          longitude: loginLocation.longitude,
          timezone: loginLocation.timezone,
          audience: gender,
        }),
      });
      if (!settingsResponse.ok) {
        const settingsPayload = await settingsResponse.json().catch(() => null) as { error?: { message?: string } } | null;
        throw new Error(settingsPayload?.error?.message || "位置保存失败，请稍后重试");
      }
      const response = await fetch("/api/auth/onboarding", {
        method: "POST", signal: AbortSignal.timeout(15000), headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nickname: cleanNickname, audience: gender }),
      });
      const payload = await response.json() as {
        error?: { message?: string };
        user?: { id: string; nickname: string; audience: Gender; profile_completed: boolean };
      };
      if (!response.ok || !payload.user) throw new Error(payload.error?.message || "资料保存失败，请稍后重试");
      finishLogin({ id: payload.user.id, nickname: payload.user.nickname, gender: payload.user.audience, profileCompleted: payload.user.profile_completed });
    } catch (reason) { setError(requestError(reason, "资料保存失败，请稍后重试")); }
    finally { busy.current = false; setSubmitting(false); }
  }

  const authMode = view === "login" || view === "register" ? view : null;
  const codeButton = (purpose: "register" | "reset") => (
    <button className="login-code-button" disabled={submitting || sendingCode || cooldown > 0} onClick={() => void sendCode(purpose)} type="button">
      {sendingCode ? "发送中…" : cooldown > 0 ? `${cooldown}s 后重发` : "获取验证码"}
    </button>
  );
  const locationPermission = (
    <label className={`login-permission${permissionShake ? " is-shaking" : ""}`} key={permissionShake}><input checked={locationAllowed} disabled={locating || submitting} onChange={(event) => void changeLocationPermission(event.target.checked)} type="checkbox" /><span className="login-permission-check" aria-hidden="true"><svg viewBox="0 0 18 18"><path d="m3.5 9.5 3.3 3.3 7.7-8" /></svg></span><strong>{locating ? "正在获取位置…" : "允许访问位置和天气"}</strong></label>
  );

  return <main className="login-page">
    <section className="login-brand-panel">
      <Image className="login-logo" src="/brand/wearcue-logo-20260828.png" alt="WearCue" width={1774} height={887} priority />
      <Image className="login-ip" src="/illustrations/login-ip-bear.png" alt="" width={1024} height={1536} aria-hidden="true" priority />
      <div className="login-brand-copy"><span>WEATHER × SCENE × OUTFIT</span><h1>每天少想一件事，<br /><mark>穿什么。</mark></h1><p>把天气、场景和你的穿搭灵感，变成每天可以直接执行的答案。</p><p><Link href="/about" prefetch={false}>先了解 WearCue · 查看功能和邀请码申请方式</Link></p></div>
      <strong aria-hidden="true">WearCue</strong>
    </section>

    <section className="login-form-panel">
      {authMode && <form className={`login-form login-form-simple${authMode === "register" ? " login-form-register" : ""}`} noValidate onSubmit={submitAuth}>
        <div className="login-form-head"><h2>{authMode === "login" ? "欢迎回来" : "创建账号"}</h2><p>{authMode === "login" ? "使用邮箱和密码继续你的每日穿搭" : "验证邮箱后，开始建立你的穿搭档案"}</p></div>
        <div className="login-mode-tabs" role="tablist" aria-label="账号入口">
          {(["register", "login"] as const).map((item) => <button aria-selected={authMode === item} className={authMode === item ? "active" : ""} key={item} disabled={submitting || sendingCode} onClick={() => switchView(item)} role="tab" type="button">{item === "login" ? "登录" : "注册"}</button>)}
        </div>
        <label className="login-field"><span className="login-field-label">邮箱</span><input disabled={submitting || sendingCode} aria-invalid={fieldError === "email"} autoComplete="email" autoFocus inputMode="email" value={email} onChange={(event) => { setEmail(event.target.value); if (fieldError === "email") setFieldError(""); }} placeholder="name@example.com" type="email" />{fieldError === "email" && <span className="login-field-tip" role="alert">请填写有效邮箱</span>}</label>
        <label className="login-field"><span className="login-field-label">密码</span><input disabled={submitting || sendingCode} aria-invalid={fieldError === "password"} autoComplete={authMode === "login" ? "current-password" : "new-password"} value={password} onChange={(event) => { setPassword(event.target.value); if (fieldError === "password") setFieldError(""); }} placeholder="至少 8 位字符" type="password" />{fieldError === "password" && <span className="login-field-tip" role="alert">密码至少需要 8 位</span>}</label>
        {authMode === "register" && <>
          <label className="login-field"><span className="login-field-label">邀请码</span><input disabled={submitting || sendingCode} aria-invalid={fieldError === "inviteCode"} autoComplete="off" value={inviteCode} onChange={(event) => { setInviteCode(event.target.value); if (fieldError === "inviteCode") setFieldError(""); }} placeholder="输入邀请码" />{fieldError === "inviteCode" && <span className="login-field-tip" role="alert">请填写邀请码</span>}</label>
          <label className="login-field"><span className="login-field-label">邮箱验证码</span><span className="login-code-row"><input disabled={submitting || sendingCode} aria-invalid={fieldError === "verificationCode"} autoComplete="one-time-code" inputMode="numeric" maxLength={6} value={verificationCode} onChange={(event) => { setVerificationCode(event.target.value.replace(/\D/g, "").slice(0, 6)); if (fieldError === "verificationCode") setFieldError(""); }} placeholder="6 位验证码" />{codeButton("register")}</span>{fieldError === "verificationCode" && <span className="login-field-tip" role="alert">请输入 6 位验证码</span>}</label>
        </>}
        {error && <p className="login-error" role="alert">{error}</p>}{notice && <p className="login-notice" role="status">{notice}</p>}
        {authMode === "login" && <button className="login-text-button" disabled={submitting || sendingCode} onClick={() => switchView("reset")} type="button">忘记密码？</button>}
        <button className="login-submit" disabled={submitting || sendingCode} type="submit"><span>{submitting ? (authMode === "login" ? "正在登录…" : "正在注册…") : (authMode === "login" ? "登录 WearCue" : "验证并注册")}</span><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3.5 10h12M11 5.5l4.5 4.5-4.5 4.5" /></svg></button>
        <p className="login-footnote">{authMode === "login" ? "邀请码仅在首次注册时绑定，之后无需再次输入。" : "验证码 10 分钟内有效；旧邀请码账号也在这里绑定邮箱，原资料会保留。"}</p>
      </form>}

      {view === "reset" && <form className="login-form login-form-simple" noValidate onSubmit={submitReset}>
        <div className="login-form-head"><h2>重置密码</h2><p>验证注册邮箱后设置一个新密码</p></div>
        <label className="login-field"><span className="login-field-label">邮箱</span><input disabled={submitting || sendingCode} aria-invalid={fieldError === "email"} autoComplete="email" autoFocus value={email} onChange={(event) => { setEmail(event.target.value); if (fieldError === "email") setFieldError(""); }} placeholder="name@example.com" type="email" />{fieldError === "email" && <span className="login-field-tip" role="alert">请填写有效邮箱</span>}</label>
        <label className="login-field"><span className="login-field-label">邮箱验证码</span><span className="login-code-row"><input disabled={submitting || sendingCode} aria-invalid={fieldError === "verificationCode"} autoComplete="one-time-code" inputMode="numeric" maxLength={6} value={verificationCode} onChange={(event) => { setVerificationCode(event.target.value.replace(/\D/g, "").slice(0, 6)); if (fieldError === "verificationCode") setFieldError(""); }} placeholder="6 位验证码" />{codeButton("reset")}</span>{fieldError === "verificationCode" && <span className="login-field-tip" role="alert">请输入 6 位验证码</span>}</label>
        <label className="login-field"><span className="login-field-label">新密码</span><input disabled={submitting || sendingCode} aria-invalid={fieldError === "password"} autoComplete="new-password" value={password} onChange={(event) => { setPassword(event.target.value); if (fieldError === "password") setFieldError(""); }} placeholder="至少 8 位字符" type="password" />{fieldError === "password" && <span className="login-field-tip" role="alert">密码至少需要 8 位</span>}</label>
        {error && <p className="login-error" role="alert">{error}</p>}{notice && <p className="login-notice" role="status">{notice}</p>}
        <button className="login-submit" disabled={submitting || sendingCode} type="submit">{submitting ? "正在重置…" : "确认重置密码"}</button>
        <button className="login-text-button login-text-button-center" disabled={submitting || sendingCode} onClick={() => switchView("login")} type="button">返回登录</button>
      </form>}

      {view === "onboarding" && <form className="login-form login-form-simple" noValidate onSubmit={submitOnboarding}>
        <div className="login-form-head"><h2>完善资料</h2><p>账号已创建，再补两项就可以开始使用</p></div>
        <label className="login-field"><span className="login-field-label">昵称（最多 5 个汉字）</span><input disabled={submitting || sendingCode} aria-invalid={fieldError === "nickname"} autoFocus maxLength={5} value={nickname} onChange={(event) => { setNickname(event.target.value); if (fieldError === "nickname") setFieldError(""); }} placeholder="怎么称呼你？" />{fieldError === "nickname" && <span className="login-field-tip" role="alert">请填写昵称</span>}</label>
        <fieldset className="login-gender-fieldset"><legend>性别</legend><div>
          <button type="button" className={gender === "mens" ? "active" : ""} aria-pressed={gender === "mens"} onClick={() => { setGender("mens"); if (fieldError === "gender") setFieldError(""); }}><span><GenderIcon gender="mens" /></span><b>男士</b><svg className="login-gender-check" viewBox="0 0 18 18" aria-hidden="true"><path d="m3.5 9.5 3.3 3.3 7.7-8" /></svg></button>
          <button type="button" className={gender === "womens" ? "active" : ""} aria-pressed={gender === "womens"} onClick={() => { setGender("womens"); if (fieldError === "gender") setFieldError(""); }}><span><GenderIcon gender="womens" /></span><b>女士</b><svg className="login-gender-check" viewBox="0 0 18 18" aria-hidden="true"><path d="m3.5 9.5 3.3 3.3 7.7-8" /></svg></button>
        </div>{fieldError === "gender" && <span className="login-field-tip" role="alert">请选择性别</span>}</fieldset>
        {locationPermission}
        {error && <p className="login-error" role="alert">{error}</p>}
        <button aria-disabled={submitting || locating || !locationAllowed} className="login-submit" disabled={submitting || locating} type="submit"><span>{submitting ? "正在保存…" : "保存并进入"}</span><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3.5 10h12M11 5.5l4.5 4.5-4.5 4.5" /></svg></button>
        {currentUser && <p className="login-footnote">邮箱已验证，邀请码也已绑定到你的账号。</p>}
      </form>}
    </section>
  </main>;
}
