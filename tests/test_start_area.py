import unittest
import game
from server import Session


class StartAreaTests(unittest.TestCase):
    def test_browser_hint_matches_python_start_boundary(self):
        session = Session()
        self.assertEqual(session.snapshot()["startRadius"], game.START_RADIUS)
        x, y = session.game.pad
        session.game.update("DRAW", (x + game.START_RADIUS + 1, y), 0.02)
        self.assertEqual(session.game.state, "READY")
        session.game.update("DRAW", (x + game.START_RADIUS, y), 0.02)
        self.assertEqual(session.game.state, "DRAWING")
