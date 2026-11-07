import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import game
from server import GameServer, Session, validate_events


def event(mode="IDLE", point=None, dt=0.02, **kwargs):
    return {"mode": mode, "point": point, "dt": dt, **kwargs}


class EngineTests(unittest.TestCase):
    def test_browser_and_direct_python_follow_identical_rules(self):
        session = Session()
        direct = game.Game(960, 600, headless=True)
        for flight in (session.game, direct):
            flight.star = (840, 300)
            flight.cloud_layout = []
            flight.retry()
        inputs = [event("DRAW", {"x": x, "y": 300}) for x in range(90, 841, 15)]
        inputs += [event()] * 240
        for item in inputs:
            clean = validate_events([item])
            session.update(clean)
            direct.update(clean[0]["mode"], clean[0]["point"], clean[0]["dt"])
            self.assertEqual(session.game.state, direct.state)
            self.assertEqual(session.game.plane, direct.plane)
            self.assertEqual(session.game.score, direct.score)
        self.assertEqual(session.game.state, "LANDED")
        self.assertEqual(session.game.score, 1200)

    def test_invalid_endpoint_and_retry(self):
        session = Session()
        session.update(validate_events([event("DRAW", {"x": x, "y": 300}) for x in range(90, 250, 10)] + [event()]))
        self.assertEqual(session.game.state, "INVALID")
        self.assertEqual(session.game.tries, 0)
        session.update(validate_events([{"action": "retry"}]))
        self.assertEqual(session.game.state, "READY")
        self.assertEqual(session.game.clouds, session.game.cloud_layout)

    def test_hand_trackers_are_isolated_and_mirrored(self):
        first, second = Session(), Session()
        hand = [{"x": 0.9, "y": 0.7} for _ in range(21)]
        hand[0]["y"] = 0.9
        hand[5]["y"] = 0.8
        hand[8]["y"] = 0.5
        first.update(validate_events([event(landmarks=hand, paused=True)] * 3))
        self.assertEqual(first.cursor[0], "DRAW")
        self.assertAlmostEqual(first.cursor[1][0], 96, delta=1)
        self.assertEqual(first.game.state, "READY")
        self.assertEqual(second.cursor, ("IDLE", None))
        first.update(validate_events([event(landmarks=None)]))
        self.assertEqual(first.cursor[0], "DRAW")
        first.update(validate_events([event(landmarks=None)] * 15))
        self.assertEqual(first.cursor, ("IDLE", None))

    def test_tracking_gap_does_not_finish_route_before_destination(self):
        session = Session()
        hand = [{"x": 0.9, "y": 0.5} for _ in range(21)]
        hand[0]["y"] = 0.9
        hand[5]["y"] = 0.8
        hand[6]["y"] = 0.7
        session.update(validate_events([event(landmarks=hand)] * 3))
        for x in range(110, 400, 10):
            hand[8]["x"] = 1 - x / 960
            # Move the whole hand horizontally, keeping the drawing gesture.
            for landmark in hand:
                landmark["x"] = hand[8]["x"]
            session.update(validate_events([event(landmarks=hand)]))
        self.assertGreater(len(session.game.raw_path), game.MIN_PATH_POINTS)
        saved_path = list(session.game.raw_path)
        session.update(validate_events([event(landmarks=None, dt=0.05)] * 100))
        self.assertEqual(session.game.state, "DRAWING")
        self.assertEqual(session.game.raw_path, saved_path)
        self.assertEqual(session.cursor, ("IDLE", None))
        session.update(validate_events([event(landmarks=hand)] * 3))
        self.assertEqual(session.game.state, "DRAWING")
        # Switching to mouse still releases immediately rather than using the grace period.
        session.update(validate_events([event()]))
        self.assertEqual(session.game.state, "INVALID")

    def test_gesture_route_pauses_and_requires_two_fingers_at_destination(self):
        flight = game.Game(960, 600, headless=True)
        flight.star = (840, 300)
        for x in range(90, 400, 10):
            flight.update("DRAW", (x, 300), 0.02, gesture_input=True)
        saved_path = list(flight.raw_path)
        for mode, point in (("IDLE", None), ("IDLE", (400, 300)),
                            ("DRAW", None), ("HOVER", (400, 300))):
            with self.subTest(mode=mode, point=point):
                for _ in range(100):
                    flight.update(mode, point, 0.05, gesture_input=True)
                self.assertEqual(flight.state, "DRAWING")
                self.assertEqual(flight.raw_path, saved_path)
        for x in range(400, 841, 10):
            flight.update("DRAW", (x, 300), 0.02, gesture_input=True)
        flight.update("IDLE", None, 0.05, gesture_input=True)
        self.assertEqual(flight.state, "DRAWING")
        flight.update("HOVER", (840, 300), 0.05, gesture_input=True)
        self.assertEqual(flight.state, "FLYING")
        self.assertEqual(flight.tries, 1)

    def test_short_gesture_route_can_resume_without_being_reset(self):
        flight = game.Game(960, 600, headless=True)
        flight.update("DRAW", flight.pad, 0.02, gesture_input=True)
        flight.update("HOVER", flight.pad, 0.05, gesture_input=True)
        self.assertEqual(flight.state, "DRAWING")
        self.assertEqual(flight.raw_path, [flight.pad])
        flight.retry()
        self.assertEqual(flight.state, "READY")
        self.assertEqual(flight.raw_path, [])

    def test_hand_route_near_star_snaps_to_destination_and_flies_there(self):
        flight = game.Game(960, 600, headless=True)
        flight.star = (840, 300)
        flight.cloud_layout = []
        flight.retry()
        endpoint = (840 - game.HAND_FINISH_RADIUS, 300)
        for x in range(90, endpoint[0] + 1, 10):
            flight.update("DRAW", (x, 300), 0.02, gesture_input=True)
        flight.update("IDLE", None, 0.05, gesture_input=True)
        self.assertEqual(flight.state, "DRAWING")
        flight.update("HOVER", endpoint, 0.05, gesture_input=True)
        self.assertEqual(flight.state, "FLYING")
        self.assertEqual(flight.path[-1], flight.star)
        self.assertEqual(flight.score, 0)
        for _ in range(240):
            flight.update("IDLE", None, 0.02, gesture_input=True)
        self.assertEqual(flight.state, "LANDED")

    def test_hand_finish_tolerance_has_a_limit_and_only_applies_to_gestures(self):
        for gesture_input, distance, expected in ((True, 61, "DRAWING"),
                                                   (False, 60, "INVALID")):
            with self.subTest(gesture_input=gesture_input):
                flight = game.Game(960, 600, headless=True)
                flight.star = (840, 300)
                for x in range(90, 771, 10):
                    flight.update("DRAW", (x, 300), 0.02, gesture_input=gesture_input)
                endpoint = (840 - distance, 300)
                flight.update("DRAW", endpoint, 0.02, gesture_input=gesture_input)
                flight.update("HOVER", endpoint, 0.05, gesture_input=gesture_input)
                self.assertEqual(flight.state, expected)
                self.assertEqual(flight.raw_path[-1], endpoint)

    def test_bad_input_is_rejected(self):
        for events in ([], [event(dt=float("nan"))], [event(dt=-1)], [event(landmarks=[])], [{"action": "unknown"}], [event(point={"x": 1e9, "y": 0})]):
            with self.subTest(events=events), self.assertRaises(ValueError):
                validate_events(events)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = GameServer(("127.0.0.1", 0))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def post(self, endpoint, data):
        request = Request(self.url + endpoint, json.dumps(data).encode(), {"Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            return json.load(response)

    def test_static_assets_and_private_sessions(self):
        with urlopen(self.url, timeout=5) as response:
            self.assertIn(b"game-canvas", response.read())
        first = self.post("/api/session", {})
        second = self.post("/api/session", {})
        self.assertNotEqual(first["session"], second["session"])
        updated = self.post("/api/update", {"session": first["session"], "events": [{"action": "next"}]})
        self.assertEqual(updated["game"]["level"], 2)
        unchanged = self.post("/api/update", {"session": second["session"], "events": [event()]})
        self.assertEqual(unchanged["game"]["level"], 1)

    def test_errors_and_source_files_are_not_served(self):
        with self.assertRaises(HTTPError) as error:
            self.post("/api/update", {"session": "missing", "events": [event()]})
        self.assertEqual(error.exception.code, 404)
        error.exception.close()
        session = self.post("/api/session", {})["session"]
        with self.assertRaises(HTTPError) as error:
            self.post("/api/update", {"session": session, "events": [event(dt=-1)]})
        self.assertEqual(error.exception.code, 400)
        error.exception.close()
        with self.assertRaises(HTTPError) as error:
            urlopen(self.url + "/../server.py", timeout=5)
        self.assertEqual(error.exception.code, 404)
        error.exception.close()


if __name__ == "__main__":
    unittest.main()
