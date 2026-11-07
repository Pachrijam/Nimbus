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
        hand[8]["y"] = 0.5
        first.update(validate_events([event(landmarks=hand, paused=True)] * 3))
        self.assertEqual(first.cursor[0], "DRAW")
        self.assertAlmostEqual(first.cursor[1][0], 96, delta=1)
        self.assertEqual(first.game.state, "READY")
        self.assertEqual(second.cursor, ("IDLE", None))
        first.update(validate_events([event(landmarks=None)]))
        self.assertEqual(first.cursor, ("IDLE", None))

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
