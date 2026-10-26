"use client";

import { useRef, useState, type FormEvent } from "react";
import { apiJson } from "@/lib/backend-api";
import { logoutAndRedirect } from "@/lib/client-auth";

export function DeleteAccount() {
  const dialog = useRef<HTMLDialogElement>(null);
  const busy = useRef(false);
  const [password, setPassword] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  function clearForm() {
    setPassword(""); setConfirmed(false); setError("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current) return;
    setError("");
    if (!confirmed) { setError("请先确认已了解注销后果"); return; }
    if (password.length < 8 || password.length > 128) { setError("请输入当前登录密码（8–128 位）"); return; }
    busy.current = true; setPending(true);
    try {
      await apiJson("/auth/delete-account", {
        method: "POST", body: JSON.stringify({ password, confirmed: true }),
      });
      setPassword("");
      await logoutAndRedirect();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "注销失败，请稍后重试");
    } finally { busy.current = false; setPending(false); }
  }

  return <>
    <button type="button" className="settings-delete-account-button" onClick={() => dialog.current?.showModal()}>注销账户</button>
    <dialog ref={dialog} className="settings-password-dialog" aria-labelledby="delete-account-title" aria-describedby="delete-account-hint" onClose={clearForm} onCancel={(event) => { if (busy.current) event.preventDefault(); }}>
      <div className="settings-password-heading">
        <h2 id="delete-account-title">注销账户</h2>
        <button className="library-delete-close" type="button" aria-label="关闭注销账户" disabled={pending} onClick={() => dialog.current?.close()}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg></button>
      </div>
      <p id="delete-account-hint">注销会删除你的账号、个人资料、风格偏好、收藏和个人穿搭记录，并退出所有设备。此操作无法撤销，再次使用需重新注册。</p>
      <form className="settings-password-form" noValidate onSubmit={submit}>
        <label className="login-field"><span className="login-field-label">当前密码</span><input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" maxLength={128} placeholder="输入当前登录密码" disabled={pending} /></label>
        <label className="settings-delete-confirm"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} disabled={pending} /><span>我已了解，确认注销并删除个人数据</span></label>
        {error && <p className="settings-password-error" role="alert">{error}</p>}
        <div className="settings-delete-dialog-actions">
          <button type="button" className="settings-password-button" disabled={pending} onClick={() => dialog.current?.close()}>取消</button>
          <button type="submit" className="settings-delete-account-button" disabled={pending || !confirmed}>{pending ? "正在注销…" : "确认注销账户"}</button>
        </div>
      </form>
    </dialog>
  </>;
}
