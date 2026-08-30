import asyncio
import unittest
from unittest.mock import patch

from app.domain.weather_rules import WeatherInput
from app.services.outfit_ai_service import OutfitAIService
from app.services.recommendation_service import (
    NoRecommendationError,
    recommend_ai_outfit,
    recommend_official_outfit,
    recommend_system_ai_outfit,
)


class RecommendationTests(unittest.TestCase):
    def test_swap_changes_a_core_template(self):
        weather = WeatherInput(apparent_min=16, apparent_max=21)
        first = recommend_official_outfit(weather, "commute", "mens", "shanghai", "2026-08-27")
        second = recommend_official_outfit(
            weather,
            "commute",
            "mens",
            "shanghai",
            "2026-08-27",
            [first["template_id"]],
        )
        self.assertNotEqual(first["template_id"], second["template_id"])

    def test_no_more_outfits_does_not_lower_weather_constraints(self):
        weather = WeatherInput(apparent_min=16, apparent_max=21)
        with self.assertRaises(NoRecommendationError):
            recommend_official_outfit(
                weather,
                "commute",
                "mens",
                excluded_template_ids=["official-cool-01", "official-cool-02"],
            )

    def test_heavy_rain_replaces_outerwear_and_shoes(self):
        weather = WeatherInput(
            apparent_min=16,
            apparent_max=21,
            total_precipitation=8,
            max_precipitation_probability=90,
        )
        result = recommend_official_outfit(weather, "travel", "womens")
        by_slot = {item["slot"]: item for item in result["items"] if item["slot"] != "equipment"}
        self.assertEqual(by_slot["outerwear"]["functional_icon_key"], "protective_outerwear")
        self.assertEqual(by_slot["shoes"]["functional_icon_key"], "protective_shoes")

    def test_temperature_delta_materializes_removable_layer(self):
        result = recommend_official_outfit(
            WeatherInput(apparent_min=25, apparent_max=34), "commute", "mens"
        )
        outerwear = [item for item in result["items"] if item["slot"] == "outerwear"]
        self.assertEqual(outerwear[0]["functional_icon_key"], "light_outerwear")
        self.assertTrue(outerwear[0]["removable"])

    def test_sun_protection_uses_baseball_cap(self):
        result = recommend_official_outfit(
            WeatherInput(apparent_min=28, apparent_max=32, uv_index_max=8),
            "travel",
            "womens",
        )
        equipment = [item for item in result["items"] if item["slot"] == "equipment"]
        self.assertEqual(equipment[0]["functional_icon_key"], "acc_baseball_cap")

    def test_system_ai_recommendations_never_cross_scenes(self):
        templates = [
            {
                "id": "commute-hot",
                "scene": "commute",
                "thermal_band": "hot",
                "audience": "mens",
                "label": "清爽通勤风",
                "items": [],
            },
            {
                "id": "date-hot",
                "scene": "date",
                "thermal_band": "hot",
                "audience": "mens",
                "label": "夏日约会感",
                "items": [],
            },
        ]
        weather = WeatherInput(apparent_min=30, apparent_max=34)
        with patch("app.services.recommendation_service.system_ai_templates", return_value=templates):
            result = recommend_system_ai_outfit(weather, "date", "mens")
            self.assertEqual(result["template_id"], "date-hot")
            self.assertEqual(result["label"], "夏日约会感")
            with self.assertRaises(NoRecommendationError):
                recommend_system_ai_outfit(weather, "travel", "mens")

    def test_live_ai_result_is_deterministically_corrected_for_snow_and_wind(self):
        captured = {}

        async def fake_generate_items(_service, context):
            captured.update(context)
            return {
                "label": "模型原始结果",
                "items": [
                    {"slot": "top", "functional_icon_key": "short_sleeve"},
                    {"slot": "bottom", "functional_icon_key": "short_bottom"},
                    {"slot": "shoes", "functional_icon_key": "daily_shoes"},
                    {"slot": "equipment", "functional_icon_key": "acc_umbrella"},
                ],
            }

        weather = WeatherInput(
            apparent_min=-12,
            apparent_max=-8,
            total_snowfall=6,
            max_wind_speed=35,
            max_wind_gust=55,
        )
        with patch.object(OutfitAIService, "generate_items", fake_generate_items):
            result = asyncio.run(recommend_ai_outfit(weather, "travel", "mens"))

        keys = {item["functional_icon_key"] for item in result["items"]}
        self.assertEqual(captured["required_top"], "warm_top")
        self.assertEqual(captured["required_bottom"], "warm_bottom")
        self.assertEqual(captured["required_outerwear"], "protective_outerwear")
        self.assertEqual(captured["required_shoes"], "protective_shoes")
        self.assertEqual(captured["apparent_min"], -12)
        self.assertEqual(captured["apparent_max"], -8)
        self.assertEqual(captured["total_snowfall"], 6)
        self.assertEqual(captured["max_wind_speed"], 35)
        self.assertEqual(captured["max_wind_gust"], 55)
        self.assertIn("max_precipitation_probability", captured)
        self.assertIn("total_precipitation", captured)
        self.assertIn("uv_index_max", captured)
        self.assertTrue(
            {"warm_top", "warm_bottom", "protective_outerwear", "protective_shoes", "acc_gloves"}
            <= keys
        )
        self.assertNotIn("acc_umbrella", keys)


if __name__ == "__main__":
    unittest.main()
