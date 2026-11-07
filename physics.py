"""
Flight physics: pure pursuit path following with a turn-rate limit and wind.
Owner: Avyay (exact-follow fallback: Person 3)

Plane = dict with x, y, heading (radians, 0 = right, positive = clockwise on screen),
speed (px/s), i (progress index along the path), target (look-ahead point or None).
"""
import math

USE_PHYSICS = True    # False -> plane follows the path exactly (safety switch for the demo)

SPEED = 180.0         # px per second
LOOKAHEAD = 60.0      # px: how far ahead on the path the autopilot aims
K_STEER = 4.0         # steering gain (proportional control)
MAX_TURN = 2.5        # rad per second -> minimum turn radius = SPEED / MAX_TURN = 72 px
SEARCH_WINDOW = 20    # only search this many points ahead for the closest point


def make_plane(x, y):
    return {
        "x": float(x),
        "y": float(y),
        "heading": 0.0,
        "speed": SPEED,
        "i": 0,
        "target": None,
    }


def step_plane(plane, path, wind, dt):
    """Move the plane forward one frame.
    path: list of evenly spaced (x, y) points (already smoothed + resampled)
    wind: (wind_x, wind_y) in px per second
    dt:   seconds since the last frame
    """
    if USE_PHYSICS:
        step_pursuit(plane, path, wind, dt)
    else:
        step_exact(plane, path, dt)


def wrap_angle(a):
    """Force an angle into -pi..pi so the plane always turns the short way."""
    return (a + math.pi) % (2 * math.pi) - math.pi


def step_pursuit(plane, path, wind, dt):
    """TODO (Avyay), in order:
    A. update plane["i"]: closest path point, searching forward only (SEARCH_WINDOW)
    B. look-ahead point: walk forward from i until a point is >= LOOKAHEAD from the plane
       (or use the last point); store it in plane["target"]
       -> after the last path point is reached, stop steering and fly straight
    C. desired = atan2(target_y - y, target_x - x)
    D. error = wrap_angle(desired - heading)
    E. turn_rate = K_STEER * error, clamped to +-MAX_TURN; heading += turn_rate * dt
    F. move (below), including wind
    Placeholder: flies straight with wind.
    """
    plane["x"] += (plane["speed"] * math.cos(plane["heading"]) + wind[0]) * dt
    plane["y"] += (plane["speed"] * math.sin(plane["heading"]) + wind[1]) * dt


def step_exact(plane, path, dt):
    """Fallback: move along the path points at SPEED, no physics, no wind.
    TODO (Person 3): move plane["i"] forward by SPEED * dt / spacing points,
    set x, y to that point, heading = atan2 toward the next point.
    After the last point, keep flying straight.
    Placeholder: flies straight."""
    plane["x"] += plane["speed"] * math.cos(plane["heading"]) * dt
    plane["y"] += plane["speed"] * math.sin(plane["heading"]) * dt
