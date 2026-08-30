import hashlib
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.auth import CurrentUser
from app.schemas import (
    ComfortFeedbackRequest,
    InspirationConfirmRequest,
    NotificationTestRequest,
    OutfitSaveRequest,
    OutfitStatusRequest,
    PushSubscriptionRequest,
    SettingsUpdate,
    SkipRequest,
)
from app.services.image_service import ImagePixelLimitError, ImageService
from app.services.outfit_ai_service import (
    OutfitAIService,
    OutfitAIServiceError,
    name_follows_style_scene,
)
from app.services.push_service import PushService, SubscriptionGoneError
from app.services.store import store, user_local_date
from app.services.vision_service import VisionService, VisionServiceError


router = APIRouter()
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))


def _image_type(content: bytes) -> Optional[tuple[str, str]]:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


@router.get("/settings", tags=["settings"])
async def get_user_settings(user: CurrentUser) -> dict:
    return store.get_settings(user["id"])


@router.post("/settings", tags=["settings"])
async def save_user_settings(payload: SettingsUpdate, user: CurrentUser) -> dict:
    values = payload.model_dump(exclude_none=True)
    if "reminder_days" in values and any(day < 1 or day > 7 for day in values["reminder_days"]):
        raise HTTPException(422, "提醒日期必须使用 1–7")
    return store.save_settings(values, user["id"])


@router.get("/outfits", tags=["outfits"])
async def list_outfits(
    user: CurrentUser,
    in_pool: Optional[bool] = Query(default=None)
) -> list:
    audience = store.get_settings(user["id"])["audience"]
    return [
        outfit for outfit in store.list_outfits(in_pool=in_pool, user_id=user["id"])
        if outfit["source"] != "system" or outfit["audience"] == audience
    ]


@router.post("/outfits", tags=["outfits"])
async def create_outfit(payload: OutfitSaveRequest, user: CurrentUser) -> dict:
    if payload.suitable_min > payload.suitable_max:
        raise HTTPException(422, "适用最低温不能高于最高温")
    return store.save_outfit(payload.model_dump() | {"source": "manual"}, user_id=user["id"])


@router.get("/outfits/{outfit_id}", tags=["outfits"])
async def get_outfit(outfit_id: str, user: CurrentUser) -> dict:
    outfit = store.get_outfit(outfit_id, user["id"])
    if not outfit:
        raise HTTPException(404, "穿搭不存在")
    return outfit


@router.delete("/outfits/{outfit_id}", tags=["outfits"])
async def delete_outfit(outfit_id: str, user: CurrentUser) -> dict:
    if not store.delete_outfit(outfit_id, user["id"]):
        raise HTTPException(404, "穿搭不存在")
    return {"deleted": True, "id": outfit_id}


@router.post("/outfits/{outfit_id}/status", tags=["outfits"])
async def update_outfit_status(outfit_id: str, payload: OutfitStatusRequest, user: CurrentUser) -> dict:
    if not store.get_outfit(outfit_id, user["id"]):
        raise HTTPException(404, "穿搭不存在")
    return store.update_outfit_status(outfit_id, payload.model_dump(exclude_none=True), user["id"])


@router.get("/inspirations", tags=["inspirations"])
async def list_inspirations(user: CurrentUser) -> list:
    return store.list_inspirations(user["id"])


@router.post("/inspirations/upload", tags=["inspirations"])
async def upload_inspiration(
    user: CurrentUser,
    image: UploadFile = File(...), upload_key: Optional[str] = Form(default=None)
) -> dict:
    content = await image.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(422, "图片为空")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "图片不能超过 %d MB" % (MAX_UPLOAD_BYTES // 1024 // 1024))
    detected = _image_type(content)
    if not detected:
        raise HTTPException(415, "只支持 JPEG、PNG 或 WebP 图片")
    digest = hashlib.sha256(content).hexdigest()
    key = upload_key or digest
    existing = store.get_inspiration_by_key(key, user["id"]) or store.get_inspiration_by_hash(digest, user["id"])
    if existing:
        return existing | {"deduplicated": True}
    media_type, _ = detected
    try:
        paths = ImageService(store.upload_dir).process_and_store(content, digest)
    except ImagePixelLimitError as exc:
        raise HTTPException(413, "图片分辨率过高，请压缩后再上传") from exc
    except Exception as exc:
        raise HTTPException(415, "图片内容已损坏或无法解析") from exc
    result = store.create_inspiration(
        {
            "upload_key": key, "content_hash": digest,
            "original_name": Path(image.filename or "upload").name[:180],
            "media_type": media_type, "file_path": paths["original"],
        },
        user["id"],
    )
    return result | {"deduplicated": False}


@router.get("/inspirations/analysis-quota", tags=["inspirations"])
async def analysis_quota(user: CurrentUser) -> dict:
    local_date = user_local_date(store.get_settings(user["id"]).get("timezone"))
    return store.get_ai_quota(user["id"], local_date, "vision")


@router.get("/inspirations/{inspiration_id}", tags=["inspirations"])
async def get_inspiration(inspiration_id: str, user: CurrentUser) -> dict:
    result = store.get_inspiration(inspiration_id, user["id"])
    if not result:
        raise HTTPException(404, "识别任务不存在")
    return result


@router.get("/inspirations/{inspiration_id}/image", tags=["inspirations"], include_in_schema=False)
async def inspiration_image(
    inspiration_id: str, user: CurrentUser,
    size: str = Query(default="medium", pattern="^(original|medium|thumbnail)$")
) -> FileResponse:
    path = store.inspiration_path(inspiration_id, user["id"])
    if path:
        path = ImageService.sized_path(path, size)
    if not path or not path.is_file():
        raise HTTPException(404, "图片不存在")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.post("/inspirations/{inspiration_id}/analyze", tags=["inspirations"])
async def analyze_inspiration(inspiration_id: str, user: CurrentUser) -> dict:
    if not store.get_inspiration(inspiration_id, user["id"]):
        raise HTTPException(404, "识别任务不存在")
    local_date = user_local_date(store.get_settings(user["id"]).get("timezone"))
    reservation_id = store.reserve_ai_usage(user["id"], local_date, "vision")
    if not reservation_id:
        raise HTTPException(429, "今日识别次数已用完，请明天再试")
    path = store.inspiration_path(inspiration_id, user["id"])
    medium_path = ImageService.sized_path(path, "medium") if path else None
    if medium_path and medium_path.is_file():
        path = medium_path
    try:
        result = await VisionService().analyze(path)
    except VisionServiceError as exc:
        store.release_ai_usage(reservation_id)
        raise HTTPException(503, str(exc)) from exc
    except Exception:
        store.release_ai_usage(reservation_id)
        raise
    remaining = store.get_ai_quota(user["id"], local_date, "vision")["remaining"]
    result = store.set_analysis(inspiration_id, result, "external", user["id"])
    return result | {"remaining_analyses": remaining}


@router.post("/inspirations/{inspiration_id}/generate-name", tags=["inspirations"])
async def generate_inspiration_name(inspiration_id: str, user: CurrentUser) -> dict:
    inspiration = store.get_owned_inspiration(inspiration_id, user["id"])
    if not inspiration:
        raise HTTPException(404, "识别任务不存在")
    if inspiration["status"] not in {"needs_review", "ready"} or not inspiration["result"].get("components"):
        raise HTTPException(409, "请先完成图片识别")
    cached_name = str(inspiration["result"].get("ai_generated_name") or "").strip()
    if cached_name and name_follows_style_scene(cached_name, inspiration["result"]):
        return {"name": cached_name[:30], "cached": True}
    try:
        name = await OutfitAIService().generate_name(inspiration["result"])
    except OutfitAIServiceError as exc:
        raise HTTPException(503, str(exc)) from exc
    if not store.set_inspiration_generated_name(inspiration_id, name, user["id"]):
        raise HTTPException(404, "识别任务不存在")
    return {"name": name, "cached": False}


@router.post("/inspirations/{inspiration_id}/confirm", tags=["inspirations"])
async def confirm_inspiration(inspiration_id: str, payload: InspirationConfirmRequest, user: CurrentUser) -> dict:
    inspiration = store.get_inspiration(inspiration_id, user["id"])
    if not inspiration:
        raise HTTPException(404, "识别任务不存在")
    if inspiration["status"] not in {"needs_review", "ready"}:
        raise HTTPException(409, "识别结果尚未完成")
    existing = store.get_outfit_by_inspiration(inspiration_id, user["id"])
    values = payload.model_dump() | {"source": "inspiration", "inspiration_id": inspiration_id}
    if existing:
        values["in_pool"] = existing["in_pool"] or values["in_pool"]
    outfit = store.save_outfit(
        values, existing["id"] if existing else None, user["id"]
    )
    store.mark_inspiration_ready(inspiration_id, user["id"])
    return outfit


@router.post("/notifications/subscriptions", tags=["notifications"])
async def save_push_subscription(payload: PushSubscriptionRequest, user: CurrentUser) -> dict:
    return store.save_subscription(payload.model_dump(), user["id"])


@router.get("/notifications/public-key", tags=["notifications"])
async def push_public_key(user: CurrentUser) -> dict:
    del user
    service = PushService()
    return {"configured": service.configured, "public_key": service.public_key}


@router.post("/notifications/test", tags=["notifications"])
async def test_notification(payload: NotificationTestRequest, user: CurrentUser) -> dict:
    key = "single:%s:%s:daily" % (payload.device_id, payload.local_date)
    existing = store.get_delivery(key, user["id"])
    if existing:
        return existing
    service = PushService()
    subscriptions = store.enabled_subscriptions(user["id"])
    status = "pending_provider" if not service.configured else "pending_subscription"
    if service.configured and subscriptions:
        sent = 0
        for subscription in subscriptions:
            try:
                service.send(subscription, payload.message)
                store.set_subscription_result(subscription["id"], "sent", user["id"])
                sent += 1
            except SubscriptionGoneError:
                store.remove_subscription(subscription["id"], user["id"])
            except Exception:
                store.set_subscription_result(subscription["id"], "failed", user["id"])
        status = "sent" if sent else "failed"
    return store.record_delivery(key, payload.message, status, user["id"])


@router.post("/feedback/skips", tags=["feedback"])
async def record_skip(payload: SkipRequest, user: CurrentUser) -> dict:
    if not store.get_outfit(payload.outfit_id, user["id"]):
        raise HTTPException(404, "穿搭不存在")
    return store.record_skip(payload.outfit_id, payload.local_date, user["id"])


@router.post("/feedback/comfort", tags=["feedback"])
async def record_comfort_feedback(payload: ComfortFeedbackRequest, user: CurrentUser) -> dict:
    return store.record_feedback(payload.week_key, payload.choice, user["id"])
