"""Shared fixed-step flight rules for players and Gemini route verification."""
import paths
import physics

STEP = 1 / 60
STAR_RADIUS = 28
SCREEN_MARGIN = 30


def advance(plane, route, wind, clouds, star, width, height):
    """Advance one tick, mutating only the supplied plane and cloud copies."""
    physics.step_plane(plane, route, wind, STEP)
    for cloud in clouds:
        cloud["x"] += cloud["vx"] * STEP
        if cloud["x"] < cloud["r"]:
            cloud["x"] = cloud["r"]
            cloud["vx"] = abs(cloud["vx"])
        elif cloud["x"] > width - cloud["r"]:
            cloud["x"] = width - cloud["r"]
            cloud["vx"] = -abs(cloud["vx"])

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
    for tick in range(1, int(max_seconds / STEP) + 1):
        state = advance(plane, route, layout["wind"], clouds, layout["star"],
                        layout["width"], layout["height"])
        position = (plane["x"], plane["y"])
        distance += paths.distance(trajectory[-1], position)
        trajectory.append(position)
        if state != "FLYING":
            return {"state": state, "time": tick * STEP, "distance": distance,
                    "trajectory": trajectory}
    return {"state": "TIMEOUT", "time": max_seconds, "distance": distance,
            "trajectory": trajectory}
