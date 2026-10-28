import asyncio
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import CurrentUser, allowed_invite_codes, bearer
from app.schemas import (
    AccountDeletionRequest,
    EmailCodeRequest,
    LoginRequest,
    OnboardingRequest,
    PasswordResetRequest,
    ProfileUpdateRequest,
)
from app.services.email_service import (
    EmailDeliveryError,
    code_digest,
    delivery_mode,
    generate_code,
    send_verification_email,
)
from app.services.store import store


router = APIRouter(prefix="/auth", tags=["auth"])


def verification_digest(email: str, purpose: str, code: str) -> str:
    try:
        return code_digest(email, purpose, code)
    except EmailDeliveryError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/login")
async def login(payload: LoginRequest) -> dict:
    if payload.mode == "register":
        invite_code = (payload.invite_code or "").strip()
        verification_code = (payload.verification_code or "").strip()
        if not invite_code or not verification_code:
            raise HTTPException(422, "请完整填写注册信息")
        if not any(hmac.compare_digest(invite_code, code) for code in allowed_invite_codes()):
            raise HTTPException(403, "邀请码无效，请向邀请人确认")
        if store.email_exists(payload.email):
            raise HTTPException(409, "该邮箱已注册，请直接登录")
        if store.invite_is_claimed(invite_code):
            raise HTTPException(409, "该邀请码已注册，请更换邀请码")
        if not store.consume_email_code(
            payload.email, "register", verification_digest(payload.email, "register", verification_code)
        ):
            raise HTTPException(422, "邮箱验证码无效或已过期")
        session, conflict = store.register(payload.email, payload.password, invite_code)
        if not session:
            message = "该邮箱已注册，请直接登录" if conflict == "email" else "该邀请码已注册，请更换邀请码"
            raise HTTPException(409, message)
        return session
    session = store.login(payload.email, payload.password)
    if not session:
        raise HTTPException(401, "邮箱或密码错误")
    return session


@router.post("/email-code")
async def send_email_code(payload: EmailCodeRequest) -> dict:
    if payload.purpose == "register":
        invite_code = (payload.invite_code or "").strip()
        if not invite_code:
            raise HTTPException(422, "请先填写邀请码")
        if not any(hmac.compare_digest(invite_code, code) for code in allowed_invite_codes()):
            raise HTTPException(403, "邀请码无效，请向邀请人确认")
        if store.invite_is_claimed(invite_code):
            raise HTTPException(409, "该邀请码已注册，请更换邀请码")
        if store.email_exists(payload.email):
            raise HTTPException(409, "该邮箱已注册，请直接登录")
    elif not store.email_exists(payload.email):
        return {"ok": True, "retry_after": 60}

    code = generate_code()
    digest = verification_digest(payload.email, payload.purpose, code)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    issued, retry_after = store.issue_email_code(
        payload.email, payload.purpose, digest, expires_at,
    )
    if not issued:
        raise HTTPException(429, f"请在 {retry_after} 秒后重新获取验证码")
    try:
        await asyncio.to_thread(send_verification_email, payload.email, code, payload.purpose)
    except EmailDeliveryError as exc:
        store.discard_email_code(payload.email, payload.purpose, digest)
        raise HTTPException(503, str(exc)) from exc

    result = {"ok": True, "retry_after": 60}
    if delivery_mode() == "console" and os.getenv("APP_ENV") != "production":
        result["dev_code"] = code
    return result


@router.post("/reset-password")
async def reset_password(payload: PasswordResetRequest) -> dict:
    if not store.consume_email_code(
        payload.email,
        "reset",
        verification_digest(payload.email, "reset", payload.verification_code),
    ):
        raise HTTPException(422, "邮箱验证码无效或已过期")
    if not store.reset_password(payload.email, payload.password):
        raise HTTPException(422, "邮箱验证码无效或已过期")
    return {"ok": True}


@router.get("/me")
async def me(user: CurrentUser) -> dict:
    return {"user": user}


@router.post("/profile")
async def update_profile(payload: ProfileUpdateRequest, user: CurrentUser) -> dict:
    return {"user": store.update_nickname(user["id"], payload.nickname.strip())}


@router.post("/onboarding")
async def onboarding(payload: OnboardingRequest, user: CurrentUser) -> dict:
    return {
        "user": store.complete_profile(user["id"], payload.nickname.strip(), payload.audience)
    }


@router.post("/logout")
async def logout(
    user: CurrentUser,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict:
    del user
    if credentials:
        store.logout(credentials.credentials)
    return {"ok": True}


@router.post("/delete-account")
async def delete_account(payload: AccountDeletionRequest, user: CurrentUser) -> dict:
    result = store.delete_account(user["id"], payload.password)
    if result == "rate_limited":
        raise HTTPException(429, "密码尝试次数过多，请在 15 分钟后重试")
    if result != "deleted":
        raise HTTPException(422, "当前密码不正确，账户未注销")
    return {"ok": True}
