from typing import List

from fastapi import APIRouter, HTTPException, Query

from app.schemas import CityResponse
from app.services.weather_service import WeatherService, WeatherServiceError

router = APIRouter()
service = WeatherService()


@router.get("/cities", response_model=List[CityResponse], tags=["weather"])
async def search_cities(q: str = Query(min_length=1, max_length=80)) -> List[dict]:
    try:
        return await service.search_cities(q)
    except WeatherServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/weather/today", tags=["weather"])
async def today_weather(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    city: str = Query(min_length=1, max_length=100),
) -> dict:
    try:
        weather = await service.get_today(latitude, longitude, city)
    except WeatherServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"weather": weather}

