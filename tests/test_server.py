import unittest

from game import Session
from gotypes import event
from server import validate_events


class SessionTests(unittest.TestCase):
    def test_free_draw_pauses_flight_and_resumes_without_changing_route(self):
        session = Session()
        session.update(validate_events([event("DRAW", {"x": x, "y": 300}) for x in range(90, 400, 10)] + [event()]))
        before = session.snapshot()
        for mode in ("DRAW", "HOVER", "IDLE"):
            session.update(validate_events([event(mode, {"x": 700, "y": 100}, paused=True)] * 100))
        after = session.snapshot()
        for key in ("state", "plane", "clouds", "path", "score", "tries", "level"):
            self.assertEqual(after[key], before[key], key)
        session.update(validate_events([event()]))
        self.assertNotEqual(session.snapshot()["plane"], before["plane"])

    def test_route_ending_short_of_destination_launches_and_can_retry(self):
        session = Session()
        session.update(validate_events([event("DRAW", {"x": x, "y": 300}) for x in range(90, 250, 10)] + [event()]))
        self.assertEqual(session.game.state, "LANDED")
        self.assertEqual(session.game.score, 1200)
