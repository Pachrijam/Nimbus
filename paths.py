"""
Path helpers: turn a messy hand-drawn path into a clean flight plan.
Owner: Person 3

Order used by the game:  raw points -> chaikin() -> resample() -> flight path
"""
import math


def distance(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def path_length(points):
    """Total length of the path in pixels.
    TODO (Person 3): add up distance() between each pair of neighboring points."""
    return 0.0


def chaikin(points, iterations=2):
    """Smooth corners: each segment P->Q becomes two points at 25% and 75% of the way.
    Keep the first and last points unchanged. Repeat `iterations` times.
    TODO (Person 3)."""
    return list(points)


def find_tight_turns(points, min_radius):
    """Feasibility check: for each point, True if the turn there is tighter than the
    drone can fly. For points a, b, c in a row, the turn radius at b is the radius of
    the circle through all three: R = (|ab| * |bc| * |ca|) / (4 * triangle area).
    Triangle area = abs(cross product) / 2. Straight lines have area ~0 -> R is huge (fine).
    Mark b as tight if R < min_radius. First and last points are never tight.
    TODO (Person 3)."""
    return [False] * len(points)


def resample(points, spacing=8.0):
    """Return points spaced evenly every `spacing` pixels along the path,
    so the plane flies at a steady speed.
    TODO (Person 3): walk along the segments, dropping a new point every `spacing` px."""
    return list(points)
