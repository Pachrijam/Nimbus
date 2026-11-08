import copy
import unittest
from unittest.mock import patch

import flight_sim
import game
import physics
import route_planner


CURVED_ROUTE = [(90, 300), (240, 180), (480, 180), (680, 200), (840, 300)]


def layout(clouds, wind=(12, -4)):
    return {"width": 960, "height": 600, "pad": (90, 300), "star": (840, 300),
            "wind": wind, "clouds": [dict(zip(("x", "y", "r", "vx"), cloud)) for cloud in clouds]}


class PredictivePlanningTests(unittest.TestCase):
    def test_forecast_matches_live_motion_and_bounces_without_mutating_layout(self):
        scene = layout([(914, 300, 45, 150), (46, 120, 45, -150), (480, 450, 45, 0)])
        original = copy.deepcopy(scene)
        forecast = flight_sim.forecast_clouds(scene, seconds=2, stride=1)
        plane = physics.make_plane(*scene["pad"])
        clouds = copy.deepcopy(scene["clouds"])
        for tick, frame in enumerate(forecast[1:], 1):
            flight_sim.advance(plane, [scene["pad"], scene["star"]], scene["wind"], clouds,
                               scene["star"], scene["width"], scene["height"])
            self.assertEqual(frame["time"], tick * flight_sim.STEP)
            self.assertEqual(frame["clouds"], clouds)
        self.assertEqual(forecast[1]["clouds"][0]["x"], 915)
        self.assertEqual(forecast[1]["clouds"][0]["vx"], -150)
        self.assertEqual(forecast[1]["clouds"][1]["x"], 45)
        self.assertEqual(forecast[1]["clouds"][1]["vx"], 150)
        self.assertEqual(scene, original)

    def test_repairs_route_that_is_safe_on_initial_map_but_hit_by_future_cloud(self):
        scene = layout([(800, 180, 45, -60)])
        frozen = copy.deepcopy(scene)
        frozen["clouds"][0]["vx"] = 0
        self.assertEqual(route_planner.evaluate(CURVED_ROUTE, frozen)["outcome"]["state"], "LANDED")
        node = route_planner.evaluate(CURVED_ROUTE, scene)
        self.assertEqual(node["outcome"]["state"], "CRASHED")
        collision = node["outcome"]["collision"]
        self.assertEqual(collision["cloud_index"], 0)
        self.assertAlmostEqual(collision["cloud_position"][0], 800 - 60 * collision["time"])
        self.assertLessEqual(collision["clearance"], 0)
        result = route_planner.refine_routes([node], scene)
        self.assertIsNotNone(result["best"])
        best = result["best"]
        self.assertNotEqual(best["waypoints"], CURVED_ROUTE)
        verified = flight_sim.simulate(best["route"], scene)
        self.assertEqual(verified["state"], "LANDED")
        self.assertEqual(verified["trajectory"], best["outcome"]["trajectory"])
        self.assertLessEqual(result["tested"], route_planner.MAX_REFINEMENTS_PER_ROUND)

    def test_future_opening_is_not_rejected_as_a_static_obstacle(self):
        scene = layout([(400, 180, 45, 100)], wind=(0, 0))
        frozen = copy.deepcopy(scene)
        frozen["clouds"][0]["vx"] = 0
        self.assertEqual(route_planner.evaluate(CURVED_ROUTE, frozen)["outcome"]["state"], "CRASHED")
        node = route_planner.evaluate(CURVED_ROUTE, scene)
        self.assertEqual(node["outcome"]["state"], "LANDED")
        self.assertEqual(route_planner.refine_routes([node], scene)["tested"], 0)

    def test_multiple_clouds_and_wind_are_verified_in_the_player_game(self):
        scene = layout([(480, 300, 45, -30), (600, 225, 45, -25), (600, 375, 45, -25)])
        original = copy.deepcopy(scene)
        node = route_planner.evaluate([scene["pad"], scene["star"]], scene)
        result = route_planner.refine_routes([node], scene)
        best = result["best"]
        self.assertIsNotNone(best)
        self.assertLessEqual(len(best["waypoints"]), route_planner.MAX_WAYPOINTS)
        self.assertEqual(best["waypoints"][0], scene["pad"])
        self.assertEqual(best["waypoints"][-1], scene["star"])
        flight = game.Game(960, 600, headless=True)
        flight.pad = scene["pad"]
        flight.star = scene["star"]
        flight.wind = scene["wind"]
        flight.cloud_layout = copy.deepcopy(scene["clouds"])
        flight.retry()
        flight.path = best["route"]
        flight.state = "FLYING"
        # Stop at landing without starting a real Gemini request.
        with patch.object(flight, "complete_delivery"):
            for _ in range(1800):
                flight.update("IDLE", None, flight_sim.STEP)
                if flight.state != "FLYING":
                    break
        self.assertEqual(flight.state, "LANDED")
        self.assertEqual(flight.trajectory, best["outcome"]["trajectory"])
        self.assertEqual(scene, original)

    def test_repairs_a_cloud_that_bounces_before_arrival(self):
        scene = layout([(700, 300, 45, 150)])
        node = route_planner.evaluate([scene["pad"], scene["star"]], scene)
        collision = node["outcome"]["collision"]
        self.assertIsNotNone(collision)
        self.assertGreater(collision["time"], (915 - 700) / 150)
        result = route_planner.refine_routes([node], scene)
        self.assertIsNotNone(result["best"])
        self.assertEqual(result["best"]["outcome"]["state"], "LANDED")

    def test_search_budget_is_enforced(self):
        scene = layout([(480, 300, 45, -30), (600, 225, 45, -25), (600, 375, 45, -25)])
        node = route_planner.evaluate([scene["pad"], scene["star"]], scene)
        self.assertEqual(route_planner.refine_routes([node], scene, max_simulations=3)["tested"], 3)
        self.assertEqual(route_planner.refine_routes([node], scene, max_simulations=0)["tested"], 0)

    def test_static_collision_returns_fastest_verified_detour(self):
        scene = layout([(480, 300, 45, 0)], wind=(0, 0))
        original = copy.deepcopy(scene)
        node = route_planner.evaluate([scene["pad"], scene["star"]], scene)
        self.assertEqual(node["outcome"]["state"], "CRASHED")
        evaluated = []
        evaluate = route_planner.evaluate

        def record(points, layout):
            trial = evaluate(points, layout)
            evaluated.append(trial)
            return trial

        with patch("route_planner.evaluate", side_effect=record):
            result = route_planner.refine_routes([node], scene)
        successful = [trial for trial in evaluated if trial["outcome"]["state"] == "LANDED"]
        self.assertGreater(len(successful), 1)
        self.assertEqual(result["best"]["outcome"]["time"],
                         min(trial["outcome"]["time"] for trial in successful))
        self.assertEqual(flight_sim.simulate(result["best"]["route"], scene)["state"], "LANDED")
        self.assertLessEqual(result["tested"], route_planner.MAX_REFINEMENTS_PER_ROUND)
        self.assertEqual(scene, original)

    def test_repairs_vertical_only_cloud_collision(self):
        scene = layout([(480, 200, 45, 0)], wind=(0, 0))
        scene["clouds"][0]["vy"] = 40
        node = route_planner.evaluate([scene["pad"], scene["star"]], scene)
        self.assertEqual(node["outcome"]["state"], "CRASHED")
        result = route_planner.refine_routes([node], scene)
        self.assertIsNotNone(result["best"])
        self.assertEqual(flight_sim.simulate(result["best"]["route"], scene)["state"], "LANDED")

    def test_impossible_scene_does_not_invent_a_success(self):
        scene = layout([(200, 300, 500, 1)])
        node = route_planner.evaluate([scene["pad"], scene["star"]], scene)
        result = route_planner.refine_routes([node], scene)
        self.assertIsNone(result["best"])
        self.assertLessEqual(result["tested"], route_planner.MAX_REFINEMENTS_PER_ROUND)


if __name__ == "__main__":
    unittest.main()
