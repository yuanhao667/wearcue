import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.config import get_settings
from app.services.recommendation_service import NoRecommendationError

settings = get_settings()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="穿搭信号 API",
    description="天气规则、个人穿搭、图片识别流程、提醒与反馈服务",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
app.mount(
    "/assets",
    StaticFiles(directory=str(Path(__file__).resolve().parent / "static")),
    name="assets",
)
app.include_router(api_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    return FileResponse(Path(__file__).resolve().parent / "static" / "index.html")


@app.get("/assets-review", include_in_schema=False)
async def assets_review() -> FileResponse:
    return FileResponse(Path(__file__).resolve().parent / "static" / "assets.html")


@app.exception_handler(NoRecommendationError)
async def no_recommendation_handler(request: Request, exc: NoRecommendationError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": {"code": "NO_MORE_OUTFITS", "message": str(exc)}})


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "请求参数不符合接口约束",
                "fields": jsonable_encoder(exc.errors()),
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "REQUEST_ERROR", "message": str(exc.detail)}},
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "服务暂时不可用，请稍后重试"}},
    )
