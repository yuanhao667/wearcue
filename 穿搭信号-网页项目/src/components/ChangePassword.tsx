"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { logoutAndRedirect } from "@/lib/client-auth";

export function ChangePassword({ email }: { email: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const busy = useRef(false);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [pending, setPending] = useState<"send" | "save" | null>(null);
  const [cooldown, setCooldown] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setTimeout(() => setCooldown(cooldown - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  function clearForm() {
    setCode(""); setPassword(""); setConfirmation(""); setError(""); setNotice("");
  }

  async function request(path: string, body: object) {
    const response = await fetch(path, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body), signal: AbortSignal.timeout(15000),
    });
    const result = await response.json() as { ok?: boolean; error?: string; retry_after?: number };
    if (!response.ok || !result.ok) throw new Error(result.error || "操作失败，请稍后重试");
    return result;
  }

  async function sendCode() {
    if (busy.current || cooldown > 0) return;
    busy.current = true; setPending("send"); setError(""); setNotice("");
    try {
      const result = await request("/api/auth/email-code", { email, purpose: "reset" });
      setCooldown(result.retry_after || 60);
      setNotice("验证码已发送，请查收绑定邮箱。");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "验证码发送失败，请稍后重试"); }
    finally { busy.current = false; setPending(null); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current) return;
    setError(""); setNotice("");
    if (!/^\d{6}$/.test(code)) { setError("请输入 6 位邮箱验证码"); return; }
    if (password.length < 8 || password.length > 128) { setError("新密码需要 8–128 位字符"); return; }
    if (password !== confirmation) { setError("两次输入的密码不一致"); return; }
    busy.current = true; setPending("save");
    try {
      await request("/api/auth/reset-password", { email, verificationCode: code, password });
      setPassword(""); setConfirmation(""); setCode("");
      setNotice("密码修改成功，正在返回登录页…");
      await logoutAndRedirect();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "密码修改失败，请稍后重试"); }
    finally { busy.current = false; setPending(null); }
  }

  return <>
    <button type="button" className="settings-password-button" onClick={() => dialog.current?.showModal()}>修改密码</button>
    <dialog ref={dialog} className="settings-password-dialog" aria-labelledby="change-password-title" onClose={clearForm} onCancel={(event) => { if (busy.current) event.preventDefault(); }}>
      <div className="settings-password-heading"><h2 id="change-password-title">修改密码</h2><button className="library-delete-close" type="button" aria-label="关闭修改密码" disabled={!!pending} onClick={() => dialog.current?.close()}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg></button></div>
      <p id="change-password-hint">通过绑定邮箱验证身份。修改成功后，所有设备需使用新密码重新登录。</p>
      <form className="settings-password-form" aria-describedby="change-password-hint" noValidate onSubmit={submit}>
        <label className="login-field"><span className="login-field-label">绑定邮箱</span><input type="email" value={email} readOnly autoComplete="email" /></label>
        <label className="login-field"><span className="login-field-label">邮箱验证码</span><span className="login-code-row"><input value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))} autoComplete="one-time-code" inputMode="numeric" maxLength={6} placeholder="6 位验证码" disabled={!!pending} /><button className="login-code-button" type="button" onClick={() => void sendCode()} disabled={!!pending || cooldown > 0}>{pending === "send" ? "发送中…" : cooldown > 0 ? `${cooldown} 秒后重发` : "发送验证码"}</button></span></label>
        <label className="login-field"><span className="login-field-label">新密码</span><input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" maxLength={128} placeholder="8–128 位字符" disabled={!!pending} /></label>
        <label className="login-field"><span className="login-field-label">确认新密码</span><input type="password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoComplete="new-password" maxLength={128} placeholder="再次输入新密码" disabled={!!pending} /></label>
        {error && <p className="settings-password-error" role="alert">{error}</p>}
        {notice && <p role="status">{notice}</p>}
        <button className="login-submit" type="submit" disabled={!!pending}>{pending === "save" ? "正在修改…" : "确认修改密码"}</button>
      </form>
    </dialog>
  </>;
}
