import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import CurrentUser, allowed_invite_codes, bearer
from app.schemas import LoginRequest, ProfileUpdateRequest
from app.services.store import store


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(payload: LoginRequest) -> dict:
    invite_code = payload.invite_code.strip()
    if not any(hmac.compare_digest(invite_code, code) for code in allowed_invite_codes()):
        raise HTTPException(403, "邀请码无效，请向邀请人确认")
    return store.login(invite_code, payload.nickname.strip(), payload.audience)


@router.get("/me")
async def me(user: CurrentUser) -> dict:
    return {"user": user}


@router.post("/profile")
async def update_profile(payload: ProfileUpdateRequest, user: CurrentUser) -> dict:
    return {"user": store.update_nickname(user["id"], payload.nickname.strip())}


@router.post("/logout")
async def logout(
    user: CurrentUser,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict:
    del user
    if credentials:
        store.logout(credentials.credentials)
    return {"ok": True}

