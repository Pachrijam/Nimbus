import random
import unittest

import game


class DifficultyTests(unittest.TestCase):
    def test_weather_and_obstacle_difficulty_ramp_with_level(self):
        levels = [game._level_conditions(level) for level in range(1, 13)]

        self.assertEqual([level["cloud_count"] for level in levels[:7]],
                         [1, 3, 4, 5, 6, 7, 8])
        for key in ("wind_strength", "cloud_speed",
                    "cloud_radius", "direction_spread"):
            values = [level[key] for level in levels]
            self.assertTrue(all(left <= right for left, right in zip(values, values[1:])), key)
            self.assertTrue(any(left < right for left, right in zip(values[:7], values[1:8])), key)
        self.assertGreater(levels[2]["direction_spread"], 0)

    def test_each_level_places_all_clouds_at_supported_sizes(self):
        original_state = random.getstate()
        try:
            for width, height in ((640, 480), (960, 600)):
                for seed in (3, 30, 59):
                    with self.subTest(width=width, height=height, seed=seed):
                        random.seed(seed)
                        flight = game.Game(width, height, headless=True)
                        for level in range(1, 13):
                            flight.level = level
                            flight.start_level()
                            settings = game._level_conditions(level)
                            self.assertEqual(len(flight.cloud_layout), settings["cloud_count"])
                            self.assertTrue(all("vy" in cloud for cloud in flight.cloud_layout))
        finally:
            random.setstate(original_state)

    def test_retry_keeps_weather_and_cloud_layout(self):
        flight = game.Game(960, 600, headless=True)
        flight.level = 5
        flight.start_level()
        layout = [dict(cloud) for cloud in flight.cloud_layout]
        wind = flight.wind

        flight.retry()

        self.assertEqual(flight.cloud_layout, layout)
        self.assertEqual(flight.clouds, layout)
        self.assertEqual(flight.wind, wind)

    def test_wind_stays_constant_during_flight(self):
        flight = game.Game(960, 600, headless=True)
        flight.wind = (12, -4)
        flight.state = "FLYING"

        flight.flight_ticks = 0
        initial_wind = flight.current_wind()
        flight.flight_ticks = 30
        changed_wind = flight.current_wind()

        self.assertEqual(initial_wind, (12, -4))
        self.assertEqual(changed_wind, initial_wind)
        flight.state = "LANDED"
        self.assertEqual(flight.current_wind(), flight.wind)


if __name__ == "__main__":
    unittest.main()
