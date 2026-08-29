from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

from app.config import get_settings


class WeatherServiceError(RuntimeError):
    pass


def _numbers(values: List[Any]) -> List[float]:
    return [float(value or 0) for value in values]


class WeatherService:
    async def search_cities(self, query: str, count: int = 8) -> List[Dict[str, Any]]:
        settings = get_settings()
        params = {"name": query.strip(), "count": min(max(count, 1), 20), "language": "zh", "format": "json"}
        if not params["name"]:
            return []
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                response = await client.get("%s/search" % settings.openmeteo_geocoding_url, params=params)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise WeatherServiceError("城市搜索服务暂时不可用") from exc
        return [
            {
                "id": str(item.get("id")),
                "name": item.get("name"),
                "admin1": item.get("admin1"),
                "country": item.get("country"),
                "latitude": item.get("latitude"),
                "longitude": item.get("longitude"),
                "timezone": item.get("timezone"),
            }
            for item in response.json().get("results", [])
        ]

    async def get_today(self, latitude: float, longitude: float, city: str) -> Dict[str, Any]:
        settings = get_settings()
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": "auto",
            "forecast_days": 1,
            "current": "temperature_2m,apparent_temperature,weather_code",
            "hourly": "temperature_2m,apparent_temperature,precipitation_probability,precipitation,snowfall,weather_code,wind_speed_10m,wind_gusts_10m",
            "daily": "temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,precipitation_sum,snowfall_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,weather_code,uv_index_max",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                response = await client.get("%s/forecast" % settings.openmeteo_url, params=params)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise WeatherServiceError("天气服务暂时不可用") from exc

        payload = response.json()
        daily = payload.get("daily", {})
        hourly = payload.get("hourly", {})
        current = payload.get("current", {})
        apparent = _numbers(hourly.get("apparent_temperature", []))
        temperatures = _numbers(hourly.get("temperature_2m", []))
        precipitation = _numbers(hourly.get("precipitation", []))
        snowfall = _numbers(hourly.get("snowfall", []))
        probabilities = _numbers(hourly.get("precipitation_probability", []))
        winds = _numbers(hourly.get("wind_speed_10m", []))
        gusts = _numbers(hourly.get("wind_gusts_10m", []))

        if not apparent:
            raise WeatherServiceError("天气服务返回的数据不完整")

        return {
            "city": city,
            "latitude": latitude,
            "longitude": longitude,
            "date": (daily.get("time") or [datetime.now(timezone.utc).date().isoformat()])[0],
            "timezone": payload.get("timezone", "UTC"),
            "current_temperature": float(current.get("temperature_2m", temperatures[0])),
            "current_apparent_temperature": float(current.get("apparent_temperature", apparent[0])),
            "apparent_min": min(apparent),
            "apparent_max": max(apparent),
            "temperature_min": min(temperatures),
            "temperature_max": max(temperatures),
            "max_precipitation_probability": max(probabilities or [0]),
            "total_precipitation": round(sum(precipitation), 2),
            "total_snowfall": round(sum(snowfall), 2),
            "max_wind_speed": max(winds or [0]),
            "max_wind_gust": max(gusts or [0]),
            "uv_index_max": float((daily.get("uv_index_max") or [0])[0] or 0),
            "weather_code": int(current.get("weather_code", 0) or 0),
            "hourly": [
                {
                    "time": value,
                    "temperature": temperatures[index],
                    "apparent_temperature": apparent[index],
                    "precipitation_probability": probabilities[index] if index < len(probabilities) else 0,
                    "precipitation": precipitation[index] if index < len(precipitation) else 0,
                    "snowfall": snowfall[index] if index < len(snowfall) else 0,
                    "wind_speed": winds[index] if index < len(winds) else 0,
                    "wind_gust": gusts[index] if index < len(gusts) else 0,
                }
                for index, value in enumerate(hourly.get("time", []))
            ],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "provider": "Open-Meteo",
        }

