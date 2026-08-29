import os
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services.store import store


bearer = HTTPBearer(auto_error=False)


def allowed_invite_codes() -> set[str]:
    configured = {code.strip() for code in os.getenv("INVITE_CODES", "").split(",") if code.strip()}
    if configured:
        return configured
    return set() if os.getenv("APP_ENV") == "production" else {"WC829GREEN"}


def require_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "请先登录")
    user = store.user_for_token(credentials.credentials)
    if not user:
        raise HTTPException(401, "登录状态已失效，请重新登录")
    return user


CurrentUser = Annotated[dict, Depends(require_user)]

