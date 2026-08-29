import unittest

from app.domain.weather_rules import ThermalBand, WeatherInput, evaluate_weather_rules, get_thermal_band


class WeatherRuleTests(unittest.TestCase):
    def test_all_temperature_boundaries(self):
        self.assertEqual(get_thermal_band(28), ThermalBand.hot)
        self.assertEqual(get_thermal_band(27.9), ThermalBand.warm)
        self.assertEqual(get_thermal_band(24), ThermalBand.warm)
        self.assertEqual(get_thermal_band(20), ThermalBand.mild)
        self.assertEqual(get_thermal_band(15), ThermalBand.cool)
        self.assertEqual(get_thermal_band(10), ThermalBand.cold)
        self.assertEqual(get_thermal_band(5), ThermalBand.freezing)
        self.assertEqual(get_thermal_band(4.9), ThermalBand.severe)

    def test_temperature_delta_boundaries(self):
        removable = evaluate_weather_rules(WeatherInput(apparent_min=20, apparent_max=28))
        forced = evaluate_weather_rules(WeatherInput(apparent_min=20, apparent_max=32))
        self.assertTrue(removable.needs_removable_layer)
        self.assertFalse(removable.requires_layering)
        self.assertEqual(removable.outerwear.functional_icon_key, "light_outerwear")
        self.assertTrue(forced.requires_layering)

    def test_rain_snow_wind_and_uv_are_hard_constraints(self):
        result = evaluate_weather_rules(
            WeatherInput(
                apparent_min=3,
                apparent_max=8,
                max_precipitation_probability=60,
                total_precipitation=6,
                total_snowfall=1,
                max_wind_speed=31,
                max_wind_gust=51,
                uv_index_max=8,
            )
        )
        self.assertEqual(result.outerwear.functional_icon_key, "protective_outerwear")
        self.assertEqual(result.shoes.functional_icon_key, "protective_shoes")
        self.assertIn("gloves", result.equipment)
        self.assertNotIn("umbrella", result.equipment)
        self.assertIn("avoid_regular_umbrella", result.warnings)
        self.assertTrue(result.needs_strong_sun_protection)

    def test_light_rain_checks_shoes_and_equipment(self):
        result = evaluate_weather_rules(
            WeatherInput(
                apparent_min=25,
                apparent_max=28,
                total_precipitation=0.3,
                max_precipitation_probability=50,
            )
        )
        self.assertTrue(result.shoes.avoid_absorbent)
        self.assertIn("umbrella", result.equipment)
        self.assertIn("avoid_absorbent_shoes", result.warnings)

    def test_cold_offset_is_clamped(self):
        self.assertEqual(get_thermal_band(25, -20), ThermalBand.cool)
        self.assertEqual(get_thermal_band(22, 20), ThermalBand.hot)


if __name__ == "__main__":
    unittest.main()
