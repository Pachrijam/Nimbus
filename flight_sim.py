"""Shared fixed-step flight rules for players and Gemini route verification."""
import paths
import physics

STEP = 1 / 60
MAX_SECONDS = 30
STAR_RADIUS = 28
SCREEN_MARGIN = 30


def advance_clouds(clouds, width, height):
    """Shared storm motion for live flights, forecasts, and route verification."""
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


def forecast_clouds(layout, *, seconds=MAX_SECONDS, stride=60):
    """Detached future positions, including the same discrete bounces as the game."""
    clouds = [dict(c) for c in layout["clouds"]]
    frames = [{"time": 0.0, "clouds": [dict(c) for c in clouds]}]
    ticks = int(seconds / STEP)
    for tick in range(1, ticks + 1):
        advance_clouds(clouds, layout["width"], layout["height"])
        if tick % stride == 0 or tick == ticks:
            frames.append({"time": tick * STEP, "clouds": [dict(c) for c in clouds]})
    return frames


def advance(plane, route, wind, clouds, star, width, height):
    """Advance one tick, mutating only the supplied plane and cloud copies."""
    physics.step_plane(plane, route, wind, STEP)
    advance_clouds(clouds, width, height)

    position = (plane["x"], plane["y"])
    if paths.distance(position, star) <= STAR_RADIUS:
        return "LANDED"
    if any(paths.distance(position, (c["x"], c["y"])) <= c["r"] for c in clouds):
        return "CRASHED"
    if not (-SCREEN_MARGIN <= position[0] <= width + SCREEN_MARGIN and
            -SCREEN_MARGIN <= position[1] <= height + SCREEN_MARGIN):
        return "CRASHED"
    return "FLYING"


def simulate(route, layout, max_seconds=MAX_SECONDS, *, diagnostics=False):
    """Evaluate an already smoothed route from the original level conditions."""
    plane = physics.make_plane(*layout["pad"])
    clouds = [dict(c) for c in layout["clouds"]]
    trajectory = [tuple(layout["pad"])]
    distance = 0.0
    encounters = [None for _ in clouds]
    collision = None
    for tick in range(1, int(max_seconds / STEP) + 1):
        state = advance(plane, route, layout["wind"], clouds, layout["star"],
                        layout["width"], layout["height"])
        position = (plane["x"], plane["y"])
        distance += paths.distance(trajectory[-1], position)
        trajectory.append(position)
        if diagnostics:
            for index, cloud in enumerate(clouds):
                clearance = paths.distance(position, (cloud["x"], cloud["y"])) - cloud["r"]
                encounter = {"cloud_index": index, "time": tick * STEP,
                             "clearance": clearance, "cloud_position": (cloud["x"], cloud["y"]),
                             "drone_position": position, "heading": plane["heading"]}
                if encounters[index] is None or clearance < encounters[index]["clearance"]:
                    encounters[index] = encounter
                if state == "CRASHED" and clearance <= 0 and collision is None:
                    collision = encounter
        if state != "FLYING":
            break
    else:
        state = "TIMEOUT"
    result = {"state": state, "time": (len(trajectory) - 1) * STEP,
              "distance": distance, "trajectory": trajectory}
    if diagnostics:
        result.update(collision=collision, encounters=[item for item in encounters if item is not None])
    return result
