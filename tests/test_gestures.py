import math
from itertools import combinations
from types import SimpleNamespace
import unittest

import gestures


def hand(*, middle=False, folded=False, thumb=False, ring=False, pinky=False, angle=0, offset=0):
    points = [(0.5, 0.7)] * 21
    points[0] = (0.5, 0.9)
    points[5], points[6] = (0.45, 0.7), (0.45, 0.55)
    points[8] = (0.45, 0.75 if folded else 0.35)
    points[9], points[10] = (0.55, 0.7), (0.55, 0.55)
    points[12] = (0.55, 0.35 if middle else 0.75)
    points[2], points[4] = (0.4, 0.75), (0.2, 0.65) if thumb else (0.45, 0.8)
    points[14], points[16] = (0.6, 0.55), (0.6, 0.35 if ring else 0.75)
    points[18], points[20] = (0.65, 0.6), (0.65, 0.4 if pinky else 0.8)
    c, s = math.cos(angle), math.sin(angle)
    return [SimpleNamespace(
        x=0.5 + (x - 0.5) * c - (y - 0.5) * s + offset,
        y=0.5 + (x - 0.5) * s + (y - 0.5) * c,
    ) for x, y in points]


def depth_hand(*, tilt=0, scale=1, middle=False, folded=False, aspect=1):
    """Rotate a hand toward the lens, then change its apparent size."""
    c, s = math.cos(tilt), math.sin(tilt)
    return [SimpleNamespace(
        x=0.5 + scale * (p.x - 0.5) / aspect,
        y=0.7 + scale * (p.y - 0.9) * c,
        z=scale * (p.y - 0.9) * s / aspect,
    ) for p in hand(middle=middle, folded=folded)]


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

    def test_any_two_or_more_raised_fingers_release_drawing(self):
        fingers = ("index", "middle", "ring", "pinky", "thumb")
        for count in range(2, 6):
            for raised in combinations(fingers, count):
                for angle in (0, math.pi / 2, math.pi):
                    with self.subTest(raised=raised, angle=angle):
                        gestures.reset_gesture(self.tracker)
                        drawing = self.sample(hand(), 3)
                        pose = hand(folded="index" not in raised, angle=angle,
                                    **{finger: finger in raised for finger in fingers[1:]})
                        self.assertEqual(self.sample(pose, 2), drawing)
                        self.assertEqual(self.sample(pose, 4)[0], "HOVER")

    def test_single_non_index_finger_does_not_draw_or_release(self):
        for finger in ("middle", "ring", "pinky", "thumb"):
            with self.subTest(finger=finger):
                gestures.reset_gesture(self.tracker)
                self.assertEqual(self.sample(hand(folded=True, **{finger: True}), 6)[0], "IDLE")

    def test_release_timing_is_consistent_across_frame_rates(self):
        for fps in (20, 30, 60):
            with self.subTest(fps=fps):
                gestures.reset_gesture(self.tracker)
                self.sample(hand(), fps // 5, dt=1 / fps)
                self.assertEqual(self.sample(hand(middle=True), fps // 10, dt=1 / fps)[0], "DRAW")
                self.assertEqual(self.sample(hand(middle=True), fps // 5, dt=1 / fps)[0], "HOVER")

    def test_cursor_follows_movement_without_long_smoothing_delay(self):
        _, start = self.sample(hand(), 3)
        # Measure filter responsiveness relative to the configured cursor sensitivity.
        displacement = 0.06 * 600 / (gestures.ZONE_RIGHT - gestures.ZONE_LEFT)
        _, moved = self.sample(hand(offset=0.06))
        self.assertGreaterEqual(moved[0] - start[0], displacement * 0.6)
        self.assertLessEqual(moved[0] - start[0], displacement + 1)

    def test_smoothing_reduces_small_hand_jitter(self):
        self.sample(hand(), 3)
        offsets = (0, 0.002, -0.002, 0.001, -0.001, 0, 0.002, -0.002)
        raw_x = [gestures.to_screen(0.45 + offset, gestures.ZONE_LEFT,
                                    gestures.ZONE_RIGHT, 600) for offset in offsets]
        filtered_x = [
            self.sample(hand(offset=offset))[1][0]
            for offset in offsets[1:]
        ]

        self.assertLess(max(filtered_x) - min(filtered_x), max(raw_x) - min(raw_x))

    def test_explicit_reset_clears_tracking_immediately(self):
        self.sample(hand(), 3)
        gestures.reset_gesture(self.tracker)
        self.assertEqual(self.sample(None), ("IDLE", None))

    def test_depth_and_distance_changes_keep_one_continuous_draw(self):
        self.sample(depth_hand(), 3)
        for degrees in (30, 60, 85, 89, 60, 0):
            for scale in (0.2, 0.5, 1, 1.3, 0.5):
                with self.subTest(degrees=degrees, scale=scale):
                    pose = depth_hand(tilt=math.radians(degrees), scale=scale)
                    for _ in range(10):
                        self.assertEqual(self.sample(pose)[0], "DRAW")
                        self.assertEqual(self.tracker["candidate"], "DRAW")

    def test_depth_still_allows_intentional_release_and_fold(self):
        for degrees in (0, 60, 89):
            with self.subTest(degrees=degrees):
                gestures.reset_gesture(self.tracker)
                tilt = math.radians(degrees)
                self.sample(depth_hand(tilt=tilt), 3)
                self.assertEqual(self.sample(depth_hand(tilt=tilt, middle=True), 6)[0], "HOVER")
                self.assertEqual(self.sample(depth_hand(tilt=tilt, folded=True), 6)[0], "IDLE")

    def test_uncertain_index_estimate_does_not_cut_stroke(self):
        self.sample(hand(), 3)
        uncertain = depth_hand(tilt=math.radians(85))
        # Depth noise can shorten the extended index and lengthen the folded middle.
        uncertain[8].z = uncertain[6].z * 0.9
        uncertain[12].z = uncertain[10].z * 1.25
        for _ in range(20):
            self.assertEqual(self.sample(uncertain)[0], "DRAW")
            self.assertEqual(self.tracker["candidate"], "DRAW")
        self.assertEqual(self.sample(hand(folded=True), 6)[0], "IDLE")

    def test_missing_frames_do_not_complete_pending_release(self):
        drawing = self.sample(hand(), 3)
        self.assertEqual(self.sample(hand(middle=True, offset=0.1), 3), drawing)
        self.assertEqual(self.sample(None, 4), drawing)
        self.assertEqual(self.sample(hand(middle=True), 2)[0], "DRAW")
        self.assertEqual(self.sample(hand())[0], "DRAW")

    def test_source_aspect_is_independent_of_canvas_size(self):
        for aspect in (4 / 3, 16 / 9, 3 / 4):
            gestures.reset_gesture(self.tracker)
            pose = depth_hand(tilt=math.radians(89), aspect=aspect)
            for _ in range(3):
                mode, _ = gestures.get_gesture(pose, 960, 600, self.tracker,
                                               camera_aspect=aspect)
            self.assertEqual(mode, "DRAW")

    def test_desktop_default_tracker_accepts_dt_and_resets(self):
        gestures.reset_gesture()
        for _ in range(3):
            mode, _ = gestures.get_gesture(depth_hand(), 640, 480, dt=1 / 30)
        self.assertEqual(mode, "DRAW")
        gestures.reset_gesture()
        self.assertEqual(gestures.get_gesture(None, 640, 480), ("IDLE", None))


if __name__ == "__main__":
    unittest.main()
