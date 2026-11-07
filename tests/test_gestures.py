import math
from types import SimpleNamespace
import unittest

import gestures


def hand(*, middle=False, folded=False, angle=0, offset=0):
    points = [(0.5, 0.7)] * 21
    points[0] = (0.5, 0.9)
    points[5], points[6] = (0.45, 0.7), (0.45, 0.55)
    points[8] = (0.45, 0.75 if folded else 0.35)
    points[9], points[10] = (0.55, 0.7), (0.55, 0.55)
    points[12] = (0.55, 0.35 if middle else 0.75)
    c, s = math.cos(angle), math.sin(angle)
    return [SimpleNamespace(
        x=0.5 + (x - 0.5) * c - (y - 0.5) * s + offset,
        y=0.5 + (x - 0.5) * s + (y - 0.5) * c,
    ) for x, y in points]


class GestureTests(unittest.TestCase):
    def setUp(self):
        self.tracker = {}
        gestures.reset_gesture(self.tracker)

    def sample(self, landmarks, frames=1, dt=1 / 30):
        for _ in range(frames):
            result = gestures.get_gesture(landmarks, 600, 600, self.tracker, dt)
        return result

    def test_rotated_hands_keep_same_gestures(self):
        for angle in (0, math.pi / 2, math.pi, -math.pi / 2):
            for middle, expected in ((False, "DRAW"), (True, "HOVER")):
                with self.subTest(angle=angle, middle=middle):
                    gestures.reset_gesture(self.tracker)
                    self.assertEqual(self.sample(hand(angle=angle, middle=middle), 3)[0], expected)

    def test_folded_index_does_not_draw(self):
        for angle in (0, math.pi / 2, math.pi):
            self.assertEqual(self.sample(hand(folded=True, angle=angle), 10)[0], "IDLE")

    def test_brief_loss_holds_position_then_recovers(self):
        drawing = self.sample(hand(), 3)
        self.assertEqual(self.sample(None, 4), drawing)
        self.assertEqual(self.sample(hand(offset=0.1))[0], "DRAW")
        self.assertEqual(self.sample(None, 10), ("IDLE", None))

    def test_release_requires_stable_gesture(self):
        self.sample(hand(), 3)
        self.assertEqual(self.sample(hand(middle=True), 2)[0], "DRAW")
        self.assertEqual(self.sample(hand())[0], "DRAW")
        self.assertEqual(self.sample(hand(middle=True), 6)[0], "HOVER")

    def test_release_timing_is_consistent_across_frame_rates(self):
        for fps in (20, 30, 60):
            with self.subTest(fps=fps):
                gestures.reset_gesture(self.tracker)
                self.sample(hand(), fps // 5, dt=1 / fps)
                self.assertEqual(self.sample(hand(middle=True), fps // 10, dt=1 / fps)[0], "DRAW")
                self.assertEqual(self.sample(hand(middle=True), fps // 5, dt=1 / fps)[0], "HOVER")

    def test_cursor_follows_movement_without_long_smoothing_delay(self):
        _, start = self.sample(hand(), 3)
        _, moved = self.sample(hand(offset=0.1))
        self.assertGreaterEqual(moved[0] - start[0], 40)
        self.assertLessEqual(moved[0] - start[0], 60)

    def test_explicit_reset_clears_tracking_immediately(self):
        self.sample(hand(), 3)
        gestures.reset_gesture(self.tracker)
        self.assertEqual(self.sample(None), ("IDLE", None))


if __name__ == "__main__":
    unittest.main()
