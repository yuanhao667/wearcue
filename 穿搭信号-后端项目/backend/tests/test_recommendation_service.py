import unittest

from app.domain.weather_rules import WeatherInput
from app.services.recommendation_service import NoRecommendationError, recommend_official_outfit


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


if __name__ == "__main__":
    unittest.main()
