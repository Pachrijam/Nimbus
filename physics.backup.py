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
    """Steer toward a point ahead on the route, then apply speed and wind."""
    plane["target"] = None
    if path and plane["i"] < len(path):
        closest = plane["i"]
        best_distance = float("inf")
        stop = min(len(path), closest + SEARCH_WINDOW)
        for i in range(closest, stop):
            dx = path[i][0] - plane["x"]
            dy = path[i][1] - plane["y"]
            distance_squared = dx * dx + dy * dy
            if distance_squared < best_distance:
                best_distance = distance_squared
                closest = i
        plane["i"] = closest

        finished = False
        if closest == len(path) - 1:
            finished = math.hypot(path[-1][0] - plane["x"],
                                  path[-1][1] - plane["y"]) <= max(8, plane["speed"] * dt)
            if len(path) > 1:
                # A positive dot product means we have passed the endpoint.
                dx = path[-1][0] - path[-2][0]
                dy = path[-1][1] - path[-2][1]
                if dx * dx + dy * dy > 0:
                    passed = ((plane["x"] - path[-1][0]) * dx +
                              (plane["y"] - path[-1][1]) * dy) >= 0
                    finished = finished or passed

        if finished:
            plane["i"] = len(path)
        else:
            target = path[-1]
            for i in range(closest, len(path)):
                dx = path[i][0] - plane["x"]
                dy = path[i][1] - plane["y"]
                if dx * dx + dy * dy >= LOOKAHEAD * LOOKAHEAD:
                    target = path[i]
                    break
            plane["target"] = target
            desired = math.atan2(target[1] - plane["y"], target[0] - plane["x"])
            error = wrap_angle(desired - plane["heading"])
            turn_rate = max(-MAX_TURN, min(MAX_TURN, K_STEER * error))
            plane["heading"] = wrap_angle(plane["heading"] + turn_rate * dt)

    plane["x"] += (plane["speed"] * math.cos(plane["heading"]) + wind[0]) * dt
    plane["y"] += (plane["speed"] * math.sin(plane["heading"]) + wind[1]) * dt


def step_exact(plane, path, dt):

    """Use a distance budget to follow segments exactly, then fly straight."""
    remaining = plane["speed"] * dt
    plane["target"] = None
    while plane["i"] < len(path):
        target = path[plane["i"]]
        dx = target[0] - plane["x"]
        dy = target[1] - plane["y"]
        length = math.hypot(dx, dy)
        if length > 0:
            plane["heading"] = math.atan2(dy, dx)
        if length > remaining:
            plane["x"] += dx * remaining / length
            plane["y"] += dy * remaining / length
            plane["target"] = target
            return
        plane["x"], plane["y"] = target
        remaining -= length
        plane["i"] += 1

    plane["x"] += remaining * math.cos(plane["heading"])
    plane["y"] += remaining * math.sin(plane["heading"])
