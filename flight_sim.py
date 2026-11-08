"""Shared fixed-step flight rules for players and Gemini route verification."""
import math

import paths
import physics

STEP = 1 / 60
STAR_RADIUS = 28
SCREEN_MARGIN = 30


def wind_at(wind, gust, elapsed, gust_period):
    """Return the deterministic wind vector at a point in the flight."""
    if gust_period <= 0:
        raise ValueError("gust_period must be positive")
    phase = 2 * math.pi * elapsed / gust_period
    return (
        wind[0] + gust[0] * math.sin(phase),
        wind[1] + gust[1] * math.cos(phase),
    )


def advance(plane, route, wind, clouds, star, width, height, *, elapsed=0.0,
            gust=(0.0, 0.0), gust_period=4.0):
    """Advance one tick, mutating only the supplied plane and cloud copies."""
    physics.step_plane(plane, route, wind_at(wind, gust, elapsed, gust_period), STEP)
    for cloud in clouds:
        cloud["x"] += cloud["vx"] * STEP
        cloud["y"] += cloud.get("vy", 0.0) * STEP
        if cloud["x"] < cloud["r"]:
            cloud["x"] = cloud["r"]
            cloud["vx"] = abs(cloud["vx"])
        elif cloud["x"] > width - cloud["r"]:
            cloud["x"] = width - cloud["r"]
            cloud["vx"] = -abs(cloud["vx"])
        if cloud["y"] < cloud["r"]:
            cloud["y"] = cloud["r"]
            cloud["vy"] = abs(cloud.get("vy", 0.0))
        elif cloud["y"] > height - cloud["r"]:
            cloud["y"] = height - cloud["r"]
            cloud["vy"] = -abs(cloud.get("vy", 0.0))

    position = (plane["x"], plane["y"])
    if paths.distance(position, star) <= STAR_RADIUS:
        return "LANDED"
    if any(paths.distance(position, (c["x"], c["y"])) <= c["r"] for c in clouds):
        return "CRASHED"
    if not (-SCREEN_MARGIN <= position[0] <= width + SCREEN_MARGIN and
            -SCREEN_MARGIN <= position[1] <= height + SCREEN_MARGIN):
        return "CRASHED"
    return "FLYING"


def simulate(route, layout, max_seconds=30):
    """Evaluate an already smoothed route from the original level conditions."""
    plane = physics.make_plane(*layout["pad"])
    clouds = [dict(c) for c in layout["clouds"]]
    trajectory = [tuple(layout["pad"])]
    distance = 0.0
    gust = layout.get("wind_gust", (0.0, 0.0))
    gust_period = layout.get("gust_period", 4.0)
    for tick in range(int(max_seconds / STEP)):
        state = advance(plane, route, layout["wind"], clouds, layout["star"],
                        layout["width"], layout["height"], elapsed=tick * STEP,
                        gust=gust, gust_period=gust_period)
        position = (plane["x"], plane["y"])
        distance += paths.distance(trajectory[-1], position)
        trajectory.append(position)
        if state != "FLYING":
            return {"state": state, "time": (tick + 1) * STEP, "distance": distance,
                    "trajectory": trajectory}
    return {"state": "TIMEOUT", "time": max_seconds, "distance": distance,
            "trajectory": trajectory}
