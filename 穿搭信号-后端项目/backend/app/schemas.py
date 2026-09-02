import json
from typing import List, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


SceneId = Literal["commute", "date", "travel"]


class LoginRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=5)
    audience: Literal["mens", "womens"]
    invite_code: str = Field(min_length=1, max_length=120)


class ProfileUpdateRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=5)


class WeatherRuleRequest(BaseModel):
    apparent_min: float
    apparent_max: float
    max_precipitation_probability: float = Field(default=0, ge=0, le=100)
    total_precipitation: float = Field(default=0, ge=0)
    total_snowfall: float = Field(default=0, ge=0)
    max_wind_speed: float = Field(default=0, ge=0)
    max_wind_gust: float = Field(default=0, ge=0)
    uv_index_max: float = Field(default=0, ge=0)
    cold_offset: int = Field(default=0, ge=-6, le=6, multiple_of=2)


class RecommendationRequest(WeatherRuleRequest):
    scene: SceneId
    city_id: str = Field(default="unknown", max_length=120)
    city_name: str = Field(default="", max_length=100)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    timezone: str = Field(default="UTC", max_length=80)
    local_date: str = Field(default="today", max_length=20)
    current_temperature: Optional[float] = None
    current_apparent_temperature: Optional[float] = None
    temperature_min: Optional[float] = None
    temperature_max: Optional[float] = None
    weather_code: Optional[int] = None
    excluded_template_ids: List[str] = Field(default_factory=list, max_length=50)


class GarmentAssetResponse(BaseModel):
    key: str
    collection: str
    category: str
    url: str
    label: str
    format: Literal["svg"] = "svg"


class CityResponse(BaseModel):
    id: str
    name: str
    admin1: Optional[str] = None
    country: Optional[str] = None
    latitude: float
    longitude: float
    timezone: str


class SettingsUpdate(BaseModel):
    city_id: Optional[str] = None
    city_name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    timezone: Optional[str] = None
    audience: Optional[Literal["mens", "womens"]] = None
    height_group: Optional[Literal["偏矮", "中等", "偏高"]] = None
    weight_group: Optional[Literal["偏轻", "中等", "偏重"]] = None
    cold_offset: Optional[int] = Field(default=None, ge=-6, le=6, multiple_of=2)
    reminder_enabled: Optional[bool] = None
    reminder_time: Optional[str] = Field(default=None, pattern="^([01]\\d|2[0-3]):[0-5]\\d$")
    reminder_days: Optional[List[int]] = None


class OutfitComponent(BaseModel):
    slot: Literal["top", "bottom", "outerwear", "onepiece", "shoes", "equipment"]
    functional_icon_key: str = Field(min_length=1, max_length=60)
    variant_type: str = Field(min_length=1, max_length=60)
    color_type: Literal["solid", "pattern"] = "solid"
    color_name: str = Field(default="基础色", min_length=1, max_length=30)
    color_value: Optional[str] = Field(default=None, pattern="^#[0-9A-Fa-f]{6}$")
    pattern_description: Optional[str] = Field(default=None, max_length=80)
    thickness: Literal["thin", "regular", "thick"] = "regular"
    confidence: float = Field(default=1, ge=0, le=1)
    approximate: bool = False
    suggested: bool = False
    asset_key: Optional[str] = None


class ReplicationGuide(BaseModel):
    formula: str = Field(min_length=1, max_length=60)
    steps: List[str] = Field(min_length=2, max_length=6)
    styling_points: List[str] = Field(default_factory=list, max_length=3)
    weather_note: str = Field(default="按当天体感增减外层。", max_length=80)
    substitute: str = Field(default="同类基础款即可替换。", max_length=80)


class SuggestedTemperature(BaseModel):
    min: int = Field(default=10, ge=-30, le=50)
    max: int = Field(default=24, ge=-30, le=50)


class OutfitAnalysis(BaseModel):
    summary: str = Field(default="基础款组合，按现有层次直接复刻即可。", min_length=1, max_length=60)
    structure_points: List[str] = Field(default_factory=list, max_length=3)
    completion_advice: List[str] = Field(default_factory=list, max_length=3)


class OutfitSaveRequest(BaseModel):
    label: str = Field(default="我的穿搭", min_length=1, max_length=30)
    audience: Literal["mens", "womens"] = "mens"
    components: List[OutfitComponent] = Field(min_length=1, max_length=8)
    scene_ids: List[SceneId] = Field(default_factory=lambda: ["commute"], min_length=1, max_length=3)
    suitable_min: float = Field(default=15, ge=-40, le=50)
    suitable_max: float = Field(default=28, ge=-40, le=60)
    in_pool: bool = False
    outfit_analysis: Optional[OutfitAnalysis] = None
    replication_guide: Optional[ReplicationGuide] = None


class OutfitStatusRequest(BaseModel):
    in_pool: Optional[bool] = None
    scene_ids: Optional[List[SceneId]] = Field(default=None, min_length=1, max_length=3)


class InspirationConfirmRequest(OutfitSaveRequest):
    pass


class VisionResult(BaseModel):
    model_version: str
    garment_audience: Literal["mens", "womens", "unisex"] = "unisex"
    image_coverage: Literal["full_body", "partial", "unknown"] = "unknown"
    requires_user_confirmation: bool = True
    suggested_scenes: List[Literal["commute", "date", "travel"]] = Field(default_factory=list)
    suggested_temperature: SuggestedTemperature = Field(default_factory=SuggestedTemperature)
    suggested_season: Literal["spring-autumn", "winter", "summer"] = "spring-autumn"
    components: List[OutfitComponent]
    outfit_analysis: OutfitAnalysis = Field(default_factory=OutfitAnalysis)
    replication_guide: ReplicationGuide


class PushSubscriptionRequest(BaseModel):
    endpoint: str = Field(min_length=10, max_length=2048)
    p256dh: str = Field(min_length=1, max_length=512)
    auth: str = Field(min_length=1, max_length=512)

    @field_validator("endpoint")
    @classmethod
    def endpoint_must_be_https(_cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("推送地址必须为有效的 HTTPS URL")
        return value


class NotificationTestRequest(BaseModel):
    local_date: str = Field(pattern="^\\d{4}-\\d{2}-\\d{2}$")
    message: str = Field(default="今日穿搭已经准备好", min_length=1, max_length=180)
    device_id: str = Field(default="local-preview", min_length=1, max_length=80)


class SkipRequest(BaseModel):
    outfit_id: str
    local_date: str = Field(pattern="^\\d{4}-\\d{2}-\\d{2}$")


class ComfortFeedbackRequest(BaseModel):
    week_key: str = Field(pattern="^\\d{4}-W\\d{2}$")
    choice: Literal["cold", "just_right", "hot", "not_followed"]


class RecommendationAdviceRequest(BaseModel):
    recommendation_id: str = Field(min_length=1, max_length=80, pattern="^[A-Za-z0-9_-]+$")
    label: str = Field(default="今日穿搭", min_length=1, max_length=30)
    scene: SceneId
    items: List[OutfitComponent] = Field(min_length=1, max_length=12)
    constraints: dict = Field(default_factory=dict)
    generate_advice: bool = True

    @field_validator("constraints")
    @classmethod
    def constraints_must_be_bounded(_cls, value: dict) -> dict:
        if len(json.dumps(value, ensure_ascii=False, separators=(",", ":"))) > 16_384:
            raise ValueError("天气约束内容过大")
        return value
