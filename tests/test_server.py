import json
import os
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import game
import gestures
from server import GameServer, Session, validate_events
from test_gestures import depth_hand


def event(mode="IDLE", point=None, dt=0.02, **kwargs):
    return {"mode": mode, "point": point, "dt": dt, **kwargs}


class EngineTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {"GEMINI_API_KEY": ""})
        environment.start()
        self.addCleanup(environment.stop)

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

    def test_route_ending_short_of_destination_launches_and_can_retry(self):
        session = Session()
        session.update(validate_events([event("DRAW", {"x": x, "y": 300}) for x in range(90, 250, 10)] + [event()]))
        self.assertEqual(session.game.state, "FLYING")
        self.assertEqual(session.game.path[-1], (240, 300))
        self.assertEqual(session.game.tries, 1)
        self.assertEqual(session.game.score, 0)
        session.update(validate_events([{"action": "retry"}]))
        self.assertEqual(session.game.state, "READY")
        self.assertEqual(session.game.clouds, session.game.cloud_layout)

    def test_hand_trackers_are_isolated_and_mirrored(self):
        first, second = Session(), Session()
        hand = [{"x": 0.74, "y": 0.7} for _ in range(21)]
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
        hand = [{"x": 1 - (gestures.ZONE_LEFT + 90 / 960 *
                                  (gestures.ZONE_RIGHT - gestures.ZONE_LEFT)),
                 "y": 0.45} for _ in range(21)]
        hand[0]["y"] = 0.9
        hand[5]["y"] = 0.8
        hand[6]["y"] = 0.7
        session.update(validate_events([event(landmarks=hand)] * 3))
        for x in range(110, 400, 10):
            hand[8]["x"] = 1 - (gestures.ZONE_LEFT + x / 960 *
                                    (gestures.ZONE_RIGHT - gestures.ZONE_LEFT))
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
        self.assertEqual(session.game.state, "FLYING")

    def test_gesture_route_pauses_and_two_fingers_launch_before_destination(self):
        flight = game.Game(960, 600, headless=True)
        flight.star = (840, 300)
        for x in range(90, 400, 10):
            flight.update("DRAW", (x, 300), 0.02, gesture_input=True)
        saved_path = list(flight.raw_path)
        for mode, point in (("IDLE", None), ("IDLE", (400, 300)),
                            ("DRAW", None), ("HOVER", None)):
            with self.subTest(mode=mode, point=point):
                for _ in range(100):
                    flight.update(mode, point, 0.05, gesture_input=True)
                self.assertEqual(flight.state, "DRAWING")
                self.assertEqual(flight.raw_path, saved_path)
        flight.update("HOVER", (400, 300), 0.05, gesture_input=True)
        self.assertEqual(flight.state, "FLYING")
        self.assertEqual(flight.tries, 1)
        self.assertEqual(flight.path[-1], saved_path[-1])
        self.assertEqual(flight.score, 0)

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

    def test_destination_snap_has_a_limit_and_only_applies_to_gestures(self):
        for gesture_input, distance in ((True, 61), (False, 60)):
            with self.subTest(gesture_input=gesture_input):
                flight = game.Game(960, 600, headless=True)
                flight.star = (840, 300)
                for x in range(90, 771, 10):
                    flight.update("DRAW", (x, 300), 0.02, gesture_input=gesture_input)
                endpoint = (840 - distance, 300)
                flight.update("DRAW", endpoint, 0.02, gesture_input=gesture_input)
                flight.update("HOVER", endpoint, 0.05, gesture_input=gesture_input)
                self.assertEqual(flight.state, "FLYING")
                self.assertEqual(flight.raw_path[-1], endpoint)
                self.assertEqual(flight.path[-1], endpoint)

    def test_hand_release_uses_drawn_endpoint_despite_cursor_movement(self):
        for offset in ((-45, 0), (45, 0), (0, -45), (0, 45)):
            with self.subTest(offset=offset):
                flight = game.Game(960, 600, headless=True)
                for x in range(90, 701, 10):
                    flight.update("DRAW", (x, 300), 0.02, gesture_input=True)
                endpoint = (flight.star[0] + offset[0], flight.star[1] + offset[1])
                flight.update("DRAW", endpoint, 0.02, gesture_input=True)
                saved_path = list(flight.raw_path)
                # Finger movement during release must not pull the endpoint away.
                flight.update("HOVER", (600, 200), 0.02, gesture_input=True)
                self.assertEqual(flight.state, "FLYING")
                self.assertEqual(flight.raw_path[:-1], saved_path)
                self.assertEqual(flight.path[-1], flight.star)

    def test_hand_arrival_at_star_edge_finishes_at_center(self):
        flight = game.Game(960, 600, headless=True)
        for x in range(90, 801, 10):
            flight.update("DRAW", (x, 300), 0.02, gesture_input=True)
        flight.update("DRAW", (840 - game.STAR_RADIUS, 300), 0.02, gesture_input=True)
        self.assertEqual(flight.state, "FLYING")
        self.assertEqual(flight.path[-1], flight.star)
        self.assertEqual(flight.tries, 1)

    def test_short_mouse_route_still_resets_without_launching(self):
        flight = game.Game(960, 600, headless=True)
        flight.update("DRAW", flight.pad, 0.02)
        flight.update("IDLE", None, 0.02)
        self.assertEqual(flight.state, "READY")
        self.assertEqual(flight.tries, 0)

    def test_route_ending_short_can_deliver_by_flying_on_to_destination(self):
        flight = game.Game(960, 600, headless=True)
        flight.star = (840, 300)
        flight.cloud_layout = []
        flight.retry()
        for x in range(90, 250, 10):
            flight.update("DRAW", (x, 300), 0.02)
        flight.update("IDLE", None, 0.02)
        self.assertEqual(flight.state, "FLYING")
        self.assertEqual(flight.score, 0)
        for _ in range(240):
            flight.update("IDLE", None, 0.02)
        self.assertEqual(flight.state, "LANDED")
        self.assertEqual(flight.score, 1200)

    def test_bad_input_is_rejected(self):
        for events in ([], [event(dt=float("nan"))], [event(dt=-1)], [event(landmarks=[])], [{"action": "unknown"}], [event(point={"x": 1e9, "y": 0})]):
            with self.subTest(events=events), self.assertRaises(ValueError):
                validate_events(events)

    def test_depth_input_preserves_route_until_deliberate_release(self):
        session = Session()

        def send_pose(x, *, tilt=0, scale=1, middle=False, frames=3):
            pose = depth_hand(tilt=tilt, scale=scale, middle=middle, aspect=4 / 3)
            target_x = gestures.ZONE_LEFT + x / 960 * (gestures.ZONE_RIGHT - gestures.ZONE_LEFT)
            offset = target_x - pose[8].x
            offset_y = (gestures.ZONE_TOP + gestures.ZONE_BOTTOM) / 2 - pose[8].y
            landmarks = [{"x": 1 - (p.x + offset), "y": p.y + offset_y, "z": p.z} for p in pose]
            session.update(validate_events([event(landmarks=landmarks, cameraAspect=4 / 3)] * frames))

        send_pose(90)
        for x in range(100, 400, 10):
            send_pose(x)
        self.assertEqual(session.game.state, "DRAWING")
        saved_path = list(session.game.raw_path)
        for tilt, scale in ((1.5, 0.2), (1.55, 1.2), (1.0, 0.5), (0, 1)):
            send_pose(450, tilt=tilt, scale=scale, frames=15)
            self.assertEqual(session.cursor[0], "DRAW")
            self.assertEqual(session.game.state, "DRAWING")
            self.assertEqual(session.game.raw_path[:len(saved_path)], saved_path)
        send_pose(450, middle=True, frames=15)
        self.assertEqual(session.game.state, "FLYING")
        self.assertEqual(session.game.tries, 1)

    def test_depth_and_camera_aspect_are_validated(self):
        hand = [{"x": 0.5, "y": 0.5, "z": -0.2} for _ in range(21)]
        clean = validate_events([event(landmarks=hand, cameraAspect=4 / 3)])[0]
        self.assertEqual(clean["landmarks"][0]["z"], -0.2)
        for bad in (float("nan"), float("inf"), "0", True, 20):
            with self.subTest(bad=bad):
                hand[0]["z"] = bad
                with self.assertRaises(ValueError):
                    validate_events([event(landmarks=hand)])
                with self.assertRaises(ValueError):
                    validate_events([event(landmarks=None, cameraAspect=bad)])


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
