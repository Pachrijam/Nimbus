"""
Path helpers: turn a messy hand-drawn path into a clean flight plan.
Owner: Person 3

Order used by the game:  raw points -> chaikin() -> resample() -> flight path
"""
import math


def distance(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def path_length(points):
    """Total length of the path in pixels."""
    total = 0.0
    for i in range(1, len(points)):
        total += distance(points[i - 1], points[i])
    return total


def chaikin(points, iterations=2):
    """Smooth corners: each segment P->Q becomes two points at 25% and 75% of the way.
    Keep the first and last points unchanged. Repeat `iterations` times."""
    result = list(points)
    if len(result) < 2:
        return result
    for iteration in range(iterations):
        smooth = [result[0]]
        for i in range(len(result) - 1):
            p = result[i]
            q = result[i + 1]
            smooth.append((0.75 * p[0] + 0.25 * q[0],
                           0.75 * p[1] + 0.25 * q[1]))
            smooth.append((0.25 * p[0] + 0.75 * q[0],
                           0.25 * p[1] + 0.75 * q[1]))
        smooth.append(result[-1])
        result = smooth
    return result


def find_tight_turns(points, min_radius):
    """Feasibility check: for each point, True if the turn there is tighter than the
    drone can fly. For points a, b, c in a row, the turn radius at b is the radius of
    the circle through all three: R = (|ab| * |bc| * |ca|) / (4 * triangle area).
    Triangle area = abs(cross product) / 2. Straight lines have area ~0 -> R is huge (fine).
    Mark b as tight if R < min_radius. First and last points are never tight."""
    tight = [False] * len(points)
    for i in range(1, len(points) - 1):
        a, b, c = points[i - 1], points[i], points[i + 1]
        cross = abs((b[0] - a[0]) * (c[1] - a[1]) -
                    (b[1] - a[1]) * (c[0] - a[0]))
        if cross > 1e-9:
            radius = distance(a, b) * distance(b, c) * distance(c, a) / (2 * cross)
            tight[i] = radius < min_radius
        else:
            incoming = (b[0] - a[0], b[1] - a[1])
            outgoing = (c[0] - b[0], c[1] - b[1])
            reverses_direction = (
                incoming[0] * outgoing[0] + incoming[1] * outgoing[1] < 0
            )
            tight[i] = reverses_direction and min_radius > 0
    return tight


def resample(points, spacing=8.0):
    """Space points along the path; the final segment may be shorter."""
    if spacing <= 0:
        raise ValueError("spacing must be positive")
    if len(points) < 2:
        return list(points)

    result = [points[0]]
    remaining = spacing
    for i in range(1, len(points)):
        start = points[i - 1]
        end = points[i]
        length = distance(start, end)
        while length >= remaining:
            fraction = remaining / length
            start = (start[0] + fraction * (end[0] - start[0]),
                     start[1] + fraction * (end[1] - start[1]))
            result.append(start)
            length = distance(start, end)
            remaining = spacing
        remaining -= length

    if distance(result[-1], points[-1]) > 1e-9:
        result.append(points[-1])
    return result
