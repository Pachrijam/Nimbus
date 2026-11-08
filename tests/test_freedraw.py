"""Desktop ink regressions; optional dependencies are not needed by the server."""
import unittest

try:
    import cv2
    import numpy as np
    from freedraw import COLORS, FreeDraw
except ImportError:
    cv2 = None


@unittest.skipIf(cv2 is None, "Desktop OpenCV dependencies are not installed")
class FreeDrawTests(unittest.TestCase):
    def test_dot_and_separate_strokes(self):
        drawing = FreeDraw(200, 200)
        drawing.update("DRAW", (20, 100))
        self.assertTrue(np.array_equal(drawing.ink[100, 20], COLORS[0]))
        drawing.update("IDLE", None)
        drawing.update("DRAW", (180, 100))
        self.assertFalse(drawing.ink[100, 100].any())

    def test_hover_changes_color_once_and_preserves_existing_ink(self):
        drawing = FreeDraw(200, 200)
        drawing.update("DRAW", (20, 100))
        for _ in range(10):
            drawing.update("HOVER", (100, 100))
        self.assertEqual(drawing.color, COLORS[1])
        drawing.update("DRAW", (180, 100))
        self.assertTrue(np.array_equal(drawing.ink[100, 20], COLORS[0]))
        self.assertTrue(np.array_equal(drawing.ink[100, 180], COLORS[1]))

    def test_clear_and_mode_switch_end_strokes(self):
        drawing = FreeDraw(200, 200)
        drawing.update("DRAW", (20, 100))
        drawing.end_stroke()
        drawing.update("DRAW", (180, 100))
        self.assertFalse(drawing.ink[100, 100].any())
        drawing.clear()
        self.assertFalse(drawing.ink.any())
        drawing.update("DRAW", (100, 100))
        self.assertFalse(drawing.ink[100, 150].any())

    def test_overlay_preserves_camera_frame(self):
        drawing = FreeDraw(640, 480)
        drawing.update("DRAW", (300, 300))
        frame = np.full((480, 640, 3), 80, dtype=np.uint8)
        output = drawing.draw(frame)
        self.assertTrue((frame == 80).all())
        self.assertTrue(np.array_equal(output[300, 300], COLORS[0]))
        self.assertTrue((output[400, 400] == 80).all())
