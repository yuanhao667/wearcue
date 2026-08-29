import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Tuple


@dataclass(frozen=True)
class Settings:
    app_env: str
    app_host: str
    app_port: int
    cors_origins: Tuple[str, ...]
    openmeteo_url: str
    openmeteo_geocoding_url: str

    @property
    def debug(self) -> bool:
        return self.app_env != "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    origins = tuple(
        value.strip()
        for value in os.getenv("CORS_ORIGINS", "http://localhost:3456").split(",")
        if value.strip()
    )
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        app_host=os.getenv("APP_HOST", "0.0.0.0"),
        app_port=int(os.getenv("APP_PORT", "8000")),
        cors_origins=origins,
        openmeteo_url=os.getenv("OPENMETEO_URL", "https://api.open-meteo.com/v1"),
        openmeteo_geocoding_url=os.getenv(
            "OPENMETEO_GEOCODING_URL", "https://geocoding-api.open-meteo.com/v1"
        ),
    )

