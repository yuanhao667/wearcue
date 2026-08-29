from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.system import router as system_router
from app.api.mvp import router as mvp_router
from app.api.weather import router as weather_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(system_router)
api_router.include_router(mvp_router)
api_router.include_router(weather_router)
