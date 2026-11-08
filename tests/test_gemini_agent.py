import io
import json
import os
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import flight_sim
import game
import gemini_agent
from server import Session


def proposal(points):
    return {"waypoints": [{"x": x, "y": y} for x, y in points]}


PAD = (game.PAD_MARGIN, 300)
SAFE_ROUTE = proposal([PAD, (240, 180), (480, 180), (680, 200), (840, 300)])
DIRECT_ROUTE = proposal([PAD, (840, 300)])


class GeminiTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {"GEMINI_API_KEY": "", "GEMINI_MODEL": gemini_agent.DEFAULT_MODEL})
        environment.start()
        self.addCleanup(environment.stop)
        self.flight = game.Game(960, 600, headless=True)
        self.layout = self.flight.level_layout()

    def response(self, routes):
        body = {"candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"text": json.dumps({"routes": routes})}]}}]}
        return io.BytesIO(json.dumps(body).encode())

    def fly(self, flight, route=SAFE_ROUTE, frame_dt=0.02):
        flight.path = gemini_agent.validate_route(route, flight.level_layout())
        flight.state = "FLYING"
        flight.tries += 1
        for _ in range(2000):
            flight.update("IDLE", None, frame_dt)
            if flight.state != "FLYING":
                return
        self.fail("Flight never ended")

    def test_rest_request_keeps_key_in_header_and_uses_structured_output(self):
        with patch("gemini_agent.urlopen", return_value=self.response([SAFE_ROUTE])) as call:
            routes = gemini_agent.request_routes(self.layout, [], "secret-test-key", "gemini-2.5-flash")
        self.assertEqual(routes, [SAFE_ROUTE])
        request = call.call_args.args[0]
        self.assertNotIn("secret-test-key", request.full_url)
        self.assertEqual(request.get_header("X-goog-api-key"), "secret-test-key")
        payload = json.loads(request.data)
        self.assertEqual(payload["generationConfig"]["responseMimeType"], "application/json")
        self.assertNotIn("secret-test-key", json.dumps(payload))
        self.assertEqual(call.call_args.kwargs["timeout"], 25)

    def test_provider_errors_are_safe(self):
        failures = [HTTPError("secret-test-key", 429, "secret-test-key", {}, None),
                    HTTPError("secret-test-key", 403, "secret-test-key", {}, None),
                    URLError("secret-test-key"), TimeoutError("secret-test-key")]
        for failure in failures:
            with self.subTest(error=type(failure)), patch("gemini_agent.urlopen", side_effect=failure):
                with self.assertRaises(gemini_agent.AgentError) as caught:
                    gemini_agent.request_routes(self.layout, [], "secret-test-key", "gemini-2.5-flash")
                self.assertNotIn("secret-test-key", str(caught.exception))

    def test_prompt_contains_future_cloud_positions_including_bounces(self):
        self.layout["clouds"][0].update(x=914, vx=150)
        with patch("gemini_agent.urlopen", return_value=self.response([SAFE_ROUTE])) as call:
            gemini_agent.request_routes(self.layout, [], "key", "gemini-test")
        prompt = json.loads(call.call_args.args[0].data)["contents"][0]["parts"][0]["text"]
        context = json.loads(prompt.split("\n", 1)[1])
        forecast = context["future_cloud_positions"]
        self.assertEqual(forecast[0]["positions"][0]["x"], 914)
        self.assertEqual(forecast[1]["time"], 1)
        self.assertEqual(forecast[1]["positions"][0]["x"], 767.5)

    def test_predictive_repairs_feed_next_round_and_keep_verified_result_on_api_error(self):
        self.layout["clouds"] = [{"x": 800, "y": 180, "r": 45, "vx": -60}]
        self.layout["wind"] = (12, -4)
        with patch("gemini_agent.request_routes", side_effect=[
                [SAFE_ROUTE], gemini_agent.AgentError("offline")]) as request:
            result = gemini_agent.build_benchmark(self.layout, "key", "gemini-test")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["planner"], "gemini_predictive")
        self.assertGreater(result["refined"], 0)
        self.assertEqual(result["tested"], 1 + result["refined"])
        feedback = request.call_args_list[1].args[1]
        self.assertEqual(feedback[0]["state"], "CRASHED")
        self.assertEqual(feedback[0]["collision"]["cloud_index"], 0)
        self.assertEqual(feedback[-1]["source"], "predictive_refinement")
        self.assertEqual(feedback[-1]["state"], "LANDED")
        self.assertEqual(flight_sim.simulate(result["route"], self.layout)["trajectory"], result["trajectory"])

    def test_prompt_forecasts_clouds_moving_only_vertically(self):
        self.layout["clouds"][0].update(y=200, vx=0, vy=40)
        with patch("gemini_agent.urlopen", return_value=self.response([SAFE_ROUTE])) as call:
            gemini_agent.request_routes(self.layout, [], "key", "gemini-test")
        prompt = json.loads(call.call_args.args[0].data)["contents"][0]["parts"][0]["text"]
        forecast = json.loads(prompt.split("\n", 1)[1])["future_cloud_positions"]
        self.assertEqual(forecast[0]["positions"][0]["y"], 200)
        self.assertAlmostEqual(forecast[1]["positions"][0]["y"], 240)

    def test_two_rounds_keep_api_and_simulation_budgets(self):
        self.layout["clouds"][0]["vx"] = -30
        with patch("gemini_agent.request_routes", return_value=[DIRECT_ROUTE]) as request:
            result = gemini_agent.build_benchmark(self.layout, "key", "gemini-test")
        self.assertEqual(request.call_count, 2)
        self.assertEqual(result["tested"], 2 + result["refined"])
        self.assertLessEqual(result["refined"], 64)

    def test_malformed_blocked_and_oversized_responses_are_rejected(self):
        for body in (b"not json", b"{}", b'{"candidates": []}',
                     b'{"candidates": [{"finishReason": "MAX_TOKENS"}]}',
                     b"x" * (gemini_agent.MAX_RESPONSE_BYTES + 1)):
            with self.subTest(size=len(body)), patch("gemini_agent.urlopen", return_value=io.BytesIO(body)):
                with self.assertRaises(gemini_agent.AgentError):
                    gemini_agent.request_routes(self.layout, [], "key", "gemini-2.5-flash")

    def test_untrusted_waypoints_cannot_skip_start_or_leave_field(self):
        invalid = [proposal([(840, 300), (840, 300)]),
                   proposal([PAD, (841, 400)]),
                   proposal([PAD, (float("nan"), 200), (840, 300)]),
                   proposal([PAD, (True, 200), (840, 300)]),
                   proposal([PAD, (400, -1), (840, 300)]),
                   {"waypoints": []}, proposal([PAD] * 17)]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                gemini_agent.validate_route(value, self.layout)

    def test_crashing_candidates_never_become_benchmarks_and_feedback_is_sent(self):
        with patch("gemini_agent.request_routes", side_effect=[[DIRECT_ROUTE], [SAFE_ROUTE]]) as request:
            benchmark = gemini_agent.build_benchmark(self.layout, "key", "gemini-test")
        self.assertEqual(benchmark["status"], "ready")
        self.assertEqual(benchmark["tested"], 2 + benchmark["refined"])
        self.assertEqual(request.call_args_list[1].args[1][0]["state"], "CRASHED")
        outcome = flight_sim.simulate(benchmark["route"], self.layout)
        self.assertEqual(outcome["state"], "LANDED")
        self.assertEqual(outcome["time"], benchmark["time"])
        self.assertEqual(self.layout["clouds"], self.flight.cloud_layout)

    def test_fastest_verified_candidate_wins_and_refinement_failure_keeps_it(self):
        layout = {**self.layout, "clouds": []}
        with patch("gemini_agent.request_routes", side_effect=[
                [SAFE_ROUTE, DIRECT_ROUTE], gemini_agent.AgentError("offline")]):
            result = gemini_agent.build_benchmark(layout, "key", "gemini-test")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["time"], flight_sim.simulate(
            gemini_agent.validate_route(DIRECT_ROUTE, layout), layout)["time"])

    def test_no_valid_route_has_no_fabricated_ai_score(self):
        self.layout["clouds"] = [{"x": PAD[0], "y": PAD[1], "r": 500, "vx": 0}]
        with patch("gemini_agent.request_routes", return_value=[DIRECT_ROUTE, {}]):
            result = gemini_agent.build_benchmark(self.layout, "key", "gemini-test")
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("time", result)
        self.assertNotIn("You delivered", result["message"])

    def test_missing_key_does_not_make_a_request(self):
        with patch("gemini_agent.urlopen") as request:
            job = gemini_agent.BenchmarkJob(self.layout)
        self.assertTrue(job.done.is_set())
        self.assertEqual(job.result["status"], "disabled")
        request.assert_not_called()

    def test_worker_does_not_block_game_or_attach_to_a_later_level(self):
        entered, release = threading.Event(), threading.Event()

        def build(*args):
            entered.set()
            release.wait(3)
            return {"status": "unavailable", "message": "test result"}

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), patch("gemini_agent.build_benchmark", side_effect=build):
            try:
                self.fly(self.flight)
                self.assertTrue(entered.wait(1))
                old_job = self.flight.benchmark_job
                self.assertEqual(self.flight.comparison()["status"], "pending")
                self.flight.next_level()
                self.assertIsNone(self.flight.benchmark_job)
                release.set()
                self.assertTrue(old_job.done.wait(1))
                self.assertIsNone(self.flight.comparison())
                self.assertIsNone(self.flight.benchmark_job)
            finally:
                release.set()

    def test_player_and_agent_use_identical_steps_with_wind_and_moving_clouds(self):
        self.flight.wind = (12, -4)
        self.flight.wind_gust = (6, -8)
        self.flight.gust_period = 3.0
        self.flight.cloud_layout[0]["vx"] = 20
        self.flight.cloud_layout[0]["vy"] = 11
        self.flight.retry()
        route = gemini_agent.validate_route(SAFE_ROUTE, self.flight.level_layout())
        expected = flight_sim.simulate(route, self.flight.level_layout())
        self.assertEqual(expected["state"], "LANDED")
        for dt in (0.01, 0.02, 0.05):
            self.flight.retry()
            self.fly(self.flight, frame_dt=dt)
            self.assertEqual(self.flight.state, "LANDED")
            result = self.flight.comparison()
            self.assertEqual(result["playerTime"], expected["time"])
            self.assertAlmostEqual(result["playerDistance"], expected["distance"])
            self.assertEqual(self.flight.trajectory, expected["trajectory"])

    def test_results_persist_rematches_reuse_benchmark_and_next_resets(self):
        with patch("gemini_agent.request_routes", return_value=[SAFE_ROUTE]):
            benchmark = gemini_agent.build_benchmark(self.layout, "key", "gemini-test")
        self.fly(self.flight)
        job = self.flight.benchmark_job
        job.result = benchmark
        score = self.flight.score
        self.assertEqual(self.flight.comparison()["matchPercent"], 100)
        self.assertEqual(self.flight.comparison()["verdict"], "matched")
        self.flight.update("IDLE", None, 10)
        self.assertEqual(self.flight.state, "LANDED")
        self.flight.retry()
        self.assertIsNone(self.flight.comparison())
        self.fly(self.flight)
        self.assertIs(self.flight.benchmark_job, job)
        self.assertEqual(self.flight.score, score)
        self.flight.next_level()
        self.assertIsNone(self.flight.best_time)
        self.assertIsNone(self.flight.benchmark_job)

    def test_faster_and_slower_player_results_and_snapshot(self):
        session = Session()
        self.fly(session.game)
        job = session.game.benchmark_job
        elapsed = session.game.flight_ticks * flight_sim.STEP
        for factor, verdict in ((1.1, "beat"), (0.8, "chasing")):
            job.result = {"status": "ready", "time": elapsed * factor, "distance": 800,
                          "model": "gemini-test", "tested": 3, "trajectory": [PAD, (840, 300)]}
            snapshot = session.snapshot()
            self.assertEqual(snapshot["comparison"]["verdict"], verdict)
            self.assertEqual(snapshot["comparison"]["matchPercent"], round(factor * 100, 1))
            self.assertTrue(snapshot["trajectory"])
            json.dumps(snapshot, allow_nan=False)
        session.game.retry()
        self.assertIsNone(session.snapshot()["comparison"])
        self.assertEqual(session.snapshot()["trajectory"], [])

    def test_crash_starts_safe_route_search_and_waits_for_player_action(self):
        with patch("gemini_agent.BenchmarkJob") as job:
            job.return_value.done.is_set.return_value = False
            self.fly(self.flight, DIRECT_ROUTE)
            self.assertEqual(self.flight.state, "CRASHED")
            job.assert_called_once_with(self.flight.level_layout())
            comparison = self.flight.comparison()
            self.assertEqual(comparison["playerState"], "CRASHED")
            self.assertEqual(comparison["status"], "pending")
            self.flight.update("IDLE", None, 10)
            self.assertEqual(self.flight.state, "CRASHED")

    def test_crash_comparison_reports_verified_ai_route_without_claiming_a_time_win(self):
        with patch("gemini_agent.BenchmarkJob") as job:
            self.fly(self.flight, DIRECT_ROUTE)
        benchmark = job.return_value
        benchmark.done.is_set.return_value = True
        benchmark.result = {
            "status": "ready", "time": 8.5, "distance": 900,
            "model": "gemini-test", "tested": 4, "refined": 2,
            "planner": "gemini_predictive", "trajectory": [PAD, (840, 300)],
        }

        result = self.flight.comparison()

        self.assertEqual(result["playerState"], "CRASHED")
        self.assertTrue(result["aiRescued"])
        self.assertEqual(result["aiTime"], 8.5)
        self.assertNotIn("verdict", result)
        self.assertNotIn("timeDelta", result)
        session = Session()
        session.game = self.flight
        snapshot = session.snapshot()
        self.assertTrue(snapshot["trajectory"])
        self.assertEqual(snapshot["launchClouds"], self.flight.cloud_layout)
        json.dumps(snapshot, allow_nan=False)

    def test_player_cloud_collision_produces_verified_route_even_when_gemini_proposals_crash(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), patch(
                "gemini_agent.request_routes", return_value=[DIRECT_ROUTE]) as request:
            self.fly(self.flight, DIRECT_ROUTE)
            self.assertEqual(self.flight.state, "CRASHED")
            job = self.flight.benchmark_job
            self.assertTrue(job.done.wait(10))
            self.assertEqual(request.call_count, 2)

        result = self.flight.comparison()
        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["aiRescued"])
        self.assertGreater(result["refined"], 0)
        verified = flight_sim.simulate(job.result["route"], self.layout)
        self.assertEqual(verified["state"], "LANDED")
        self.assertEqual(verified["time"], result["aiTime"])
        self.assertEqual(verified["trajectory"], job.result["trajectory"])
        self.assertEqual(self.flight.score, 0)
        self.assertIsNone(self.flight.best_time)
        self.assertNotIn("verdict", result)
        self.flight.retry()
        self.assertIs(self.flight.benchmark_job, job)


if __name__ == "__main__":
    unittest.main()
