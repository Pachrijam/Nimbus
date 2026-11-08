import math
import unittest

import paths


def roughness(points):
    return sum(
        abs(points[i + 1][1] - 2 * points[i][1] + points[i - 1][1])
        for i in range(1, len(points) - 1)
    )


class PathSmoothingTests(unittest.TestCase):
    def test_smooth_stroke_reduces_tracking_jitter(self):
        noisy = [
            (x, 100 + (8 if index % 2 else -8))
            for index, x in enumerate(range(0, 101, 4))
        ]

        smoothed = paths.smooth_stroke(noisy)

        self.assertEqual(smoothed[0], noisy[0])
        self.assertEqual(smoothed[-1], noisy[-1])
        self.assertLess(roughness(smoothed), roughness(noisy) * 0.25)

    def test_smooth_stroke_preserves_intended_curve_and_flight_endpoints(self):
        curve = [
            (x, 100 + 50 * math.sin(x * math.pi / 100))
            for x in range(0, 101, 4)
        ]

        smoothed = paths.smooth_stroke(curve)
        flight_path = paths.flight_path(curve)

        self.assertGreater(max(y for _, y in smoothed) - min(y for _, y in smoothed), 45)
        self.assertEqual(flight_path[0], curve[0])
        self.assertEqual(flight_path[-1], curve[-1])


if __name__ == "__main__":
    unittest.main()
