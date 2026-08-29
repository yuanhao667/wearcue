from dataclasses import asdict, dataclass
from enum import Enum
from typing import Dict, List, Optional


RULE_VERSION = "weather-rules-v1"


class ThermalBand(str, Enum):
    hot = "hot"
    warm = "warm"
    mild = "mild"
    cool = "cool"
    cold = "cold"
    freezing = "freezing"
    severe = "severe"


@dataclass(frozen=True)
class WeatherInput:
    apparent_min: float
    apparent_max: float
    max_precipitation_probability: float = 0
    total_precipitation: float = 0
    total_snowfall: float = 0
    max_wind_speed: float = 0
    max_wind_gust: float = 0
    uv_index_max: float = 0
    cold_offset: int = 0


@dataclass(frozen=True)
class ClothingConstraint:
    functional_icon_key: str
    thickness: Optional[str] = None
    removable: bool = False
    waterproof: bool = False
    windproof: bool = False
    slip_resistant: bool = False
    avoid_absorbent: bool = False


@dataclass(frozen=True)
class WeatherConstraints:
    rule_version: str
    thermal_band: ThermalBand
    calibrated_apparent_min: float
    apparent_delta: float
    top: ClothingConstraint
    bottom: ClothingConstraint
    outerwear: Optional[ClothingConstraint]
    shoes: ClothingConstraint
    equipment: List[str]
    warnings: List[str]
    needs_removable_layer: bool
    requires_layering: bool
    needs_waterproof: bool
    needs_heavy_rain_protection: bool
    needs_snow_protection: bool
    needs_windproof: bool
    avoid_umbrella: bool
    needs_sun_protection: bool
    needs_strong_sun_protection: bool

    def to_dict(self) -> Dict[str, object]:
        value = asdict(self)
        value["thermal_band"] = self.thermal_band.value
        return value


def get_thermal_band(apparent_min: float, cold_offset: int = 0) -> ThermalBand:
    calibrated = apparent_min + max(-6, min(6, cold_offset))
    if calibrated >= 28:
        return ThermalBand.hot
    if calibrated >= 24:
        return ThermalBand.warm
    if calibrated >= 20:
        return ThermalBand.mild
    if calibrated >= 15:
        return ThermalBand.cool
    if calibrated >= 10:
        return ThermalBand.cold
    if calibrated >= 5:
        return ThermalBand.freezing
    return ThermalBand.severe


def evaluate_weather_rules(weather: WeatherInput) -> WeatherConstraints:
    offset = max(-6, min(6, weather.cold_offset))
    calibrated = weather.apparent_min + offset
    delta = max(0, weather.apparent_max - weather.apparent_min)
    band = get_thermal_band(weather.apparent_min, offset)

    needs_removable_layer = delta >= 8
    requires_layering = delta >= 12
    needs_waterproof = (
        weather.total_precipitation > 0.2 or weather.max_precipitation_probability >= 50
    )
    needs_heavy_rain = weather.total_precipitation >= 5
    needs_snow = weather.total_snowfall > 0
    needs_windproof = weather.max_wind_speed >= 30 or weather.max_wind_gust >= 40
    avoid_umbrella = weather.max_wind_gust >= 50
    needs_sun = weather.uv_index_max >= 6
    needs_strong_sun = weather.uv_index_max >= 8

    top_by_band = {
        ThermalBand.hot: ClothingConstraint("short_sleeve", "thin"),
        ThermalBand.warm: ClothingConstraint("short_sleeve", "thin"),
        ThermalBand.mild: ClothingConstraint("short_or_long_sleeve", "thin"),
        ThermalBand.cool: ClothingConstraint("long_sleeve", "regular"),
        ThermalBand.cold: ClothingConstraint("long_sleeve", "thick"),
        ThermalBand.freezing: ClothingConstraint("warm_top", "thick"),
        ThermalBand.severe: ClothingConstraint("warm_top", "thick"),
    }
    bottom_by_band = {
        ThermalBand.hot: ClothingConstraint("short_bottom", "thin"),
        ThermalBand.warm: ClothingConstraint("long_bottom", "thin"),
        ThermalBand.mild: ClothingConstraint("long_bottom", "regular"),
        ThermalBand.cool: ClothingConstraint("long_bottom", "regular"),
        ThermalBand.cold: ClothingConstraint("long_bottom", "regular"),
        ThermalBand.freezing: ClothingConstraint("warm_bottom", "thick"),
        ThermalBand.severe: ClothingConstraint("warm_bottom", "thick"),
    }

    outerwear: Optional[ClothingConstraint] = None
    if needs_removable_layer and band in (ThermalBand.hot, ThermalBand.warm, ThermalBand.mild):
        outerwear = ClothingConstraint("light_outerwear", "thin", removable=True)
    elif band == ThermalBand.cool:
        outerwear = ClothingConstraint("light_outerwear", "regular", removable=True)
    elif band in (ThermalBand.cold, ThermalBand.freezing, ThermalBand.severe):
        outerwear = ClothingConstraint(
            "warm_outerwear",
            "thick" if band == ThermalBand.severe else "regular",
            removable=needs_removable_layer,
        )

    if needs_heavy_rain or needs_snow or needs_windproof:
        outerwear = ClothingConstraint(
            "protective_outerwear",
            outerwear.thickness if outerwear else "regular",
            removable=outerwear.removable if outerwear else False,
            waterproof=needs_heavy_rain or needs_snow,
            windproof=needs_windproof,
        )

    shoes = ClothingConstraint(
        "protective_shoes" if needs_heavy_rain or needs_snow else "daily_shoes",
        waterproof=needs_heavy_rain or needs_snow,
        slip_resistant=needs_snow,
        avoid_absorbent=needs_waterproof,
    )

    equipment: List[str] = []
    warnings: List[str] = []
    if needs_waterproof and not avoid_umbrella:
        equipment.append("umbrella")
    if needs_waterproof:
        warnings.append("avoid_absorbent_shoes")
    if needs_snow and calibrated < 10:
        equipment.append("gloves")
    if needs_sun:
        equipment.append("sun_protection")
    if needs_strong_sun:
        warnings.append("strong_uv")
    if avoid_umbrella:
        warnings.append("avoid_regular_umbrella")
    if requires_layering:
        warnings.append("large_temperature_delta")

    return WeatherConstraints(
        rule_version=RULE_VERSION,
        thermal_band=band,
        calibrated_apparent_min=round(calibrated, 1),
        apparent_delta=round(delta, 1),
        top=top_by_band[band],
        bottom=bottom_by_band[band],
        outerwear=outerwear,
        shoes=shoes,
        equipment=equipment,
        warnings=warnings,
        needs_removable_layer=needs_removable_layer,
        requires_layering=requires_layering,
        needs_waterproof=needs_waterproof,
        needs_heavy_rain_protection=needs_heavy_rain,
        needs_snow_protection=needs_snow,
        needs_windproof=needs_windproof,
        avoid_umbrella=avoid_umbrella,
        needs_sun_protection=needs_sun,
        needs_strong_sun_protection=needs_strong_sun,
    )
