"""Bounded, time-aware repairs of Gemini waypoints using the actual flight model.

Each search node is a complete route and its simulated, timed trajectory. A
collision expands into detours around the cloud's forecast entry/exit positions.
Wind and turn limits determine arrival times again on every evaluation. This
search is deliberately bounded and does not claim to find an optimal path.
"""
import heapq
import math

import flight_sim
import paths
import physics

MAX_REFINEMENTS_PER_ROUND = 32
MAX_WAYPOINTS = 16
MAX_LOCAL_SIMULATIONS = 96


def evaluate(waypoints, layout):
    route = paths.resample(paths.chaikin(waypoints))
    return {"waypoints": waypoints, "route": route,
            "outcome": flight_sim.simulate(route, layout, diagnostics=True)}


def _segment_at(waypoints, position):
    """Project a simulated collision back onto the proposal's unsmoothed route."""
    distances = [0.0]
    closest = None
    for index, (start, end) in enumerate(zip(waypoints, waypoints[1:])):
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        distances.append(distances[-1] + length)
        if length < 1e-6:
            continue
        fraction = max(0, min(1, ((position[0] - start[0]) * dx + (position[1] - start[1]) * dy) / length ** 2))
        projected = (start[0] + fraction * dx, start[1] + fraction * dy)
        candidate = (paths.distance(position, projected), index, distances[-2] + fraction * length,
                     (dx / length, dy / length))
        if closest is None or candidate[0] < closest[0]:
            closest = candidate
    return closest, distances


def _detours(node, layout, forecast):
    collision = node["outcome"].get("collision")
    if collision is None:
        return
    waypoints = node["waypoints"]
    segment, distances = _segment_at(waypoints, collision["drone_position"])
    if segment is None:
        return
    _, _, along, (ux, uy) = segment
    nx, ny = -uy, ux
    cloud_index = collision["cloud_index"]
    radius = layout["clouds"][cloud_index]["r"]
    turn_radius = physics.SPEED / physics.MAX_TURN
    ground_speed = max(physics.SPEED / 4, math.hypot(
        physics.SPEED * math.cos(collision["heading"]) + layout["wind"][0],
        physics.SPEED * math.sin(collision["heading"]) + layout["wind"][1]))

    def cloud_at(seconds):
        tick = min(len(forecast) - 1, max(0, round(seconds / flight_sim.STEP)))
        return forecast[tick]["clouds"][cloud_index]

    for lead in (radius + turn_radius * 1.5, radius + turn_radius * 2.5):
        # Remove nearby old corners so the detour does not return to the collision.
        prefix = [waypoints[0]] + [point for point, distance in zip(waypoints[1:-1], distances[1:-1])
                                  if distance < along - lead]
        suffix = [point for point, distance in zip(waypoints[1:-1], distances[1:-1])
                  if distance > along + lead] + [waypoints[-1]]
        for clearance in (radius + 30, radius + 65, radius + 105):
            entry = cloud_at(collision["time"] - lead / ground_speed)
            exit_cloud = cloud_at(collision["time"] + (lead + clearance) / ground_speed)
            for side in (-1, 1):
                detour = [
                    (entry["x"] - ux * lead + nx * clearance * side,
                     entry["y"] - uy * lead + ny * clearance * side),
                    (exit_cloud["x"] + ux * lead + nx * clearance * side,
                     exit_cloud["y"] + uy * lead + ny * clearance * side),
                ]
                candidate = prefix + detour + suffix
                if len(candidate) <= MAX_WAYPOINTS and all(
                        0 <= x <= layout["width"] and 0 <= y <= layout["height"] for x, y in candidate):
                    yield candidate


def refine_routes(seeds, layout, *, max_simulations=MAX_REFINEMENTS_PER_ROUND):
    """Repair collisions, keeping only routes verified to land in the full simulator.

    Stationary and moving clouds use the same collision-repair search. No waiting,
    teleporting, or different drone controls are introduced to make a route succeed.
    """
    result = {"best": None, "feedback": None, "tested": 0}
    if max_simulations <= 0:
        return result
    queue = []
    seen = set()
    sequence = 0

    def signature(points):
        return tuple((round(x, 2), round(y, 2)) for x, y in points)

    def enqueue(node):
        nonlocal sequence
        outcome = node["outcome"]
        if outcome.get("collision") is not None:
            remaining = paths.distance(outcome["trajectory"][-1], layout["star"])
            heapq.heappush(queue, (remaining, outcome["time"], sequence, node))
            sequence += 1

    for node in seeds:
        seen.add(signature(node["waypoints"]))
        enqueue(node)
    if not queue:
        return result
    forecast = flight_sim.forecast_clouds(layout, stride=1)
    while queue and result["tested"] < max_simulations:
        _, _, _, node = heapq.heappop(queue)
        for candidate in _detours(node, layout, forecast):
            key = signature(candidate)
            if key in seen:
                continue
            seen.add(key)
            trial = evaluate(candidate, layout)
            result["tested"] += 1
            outcome = trial["outcome"]
            if outcome["state"] == "LANDED":
                if result["best"] is None or outcome["time"] < result["best"]["outcome"]["time"]:
                    result["best"] = trial
            else:
                enqueue(trial)
                if result["feedback"] is None or paths.distance(outcome["trajectory"][-1], layout["star"]) < paths.distance(
                        result["feedback"]["outcome"]["trajectory"][-1], layout["star"]):
                    result["feedback"] = trial
            if result["tested"] >= max_simulations:
                break
    return result


def find_route(layout):
    """Find a verified baseline without depending on a model response.

    Explore both sides of the field, repair collisions, then shorten the best
    successful route. Every improvement must land under the real flight rules.
    """
    start, end = tuple(layout["pad"]), tuple(layout["star"])
    seeds = [evaluate([start, end], layout)]
    for fraction in (0.15, 0.3, 0.7, 0.85):
        for axis in (0, 1):
            # Horizontal and vertical corridors also handle tall/narrow levels.
            points = []
            for along in (0.25, 0.75):
                point = [start[i] + along * (end[i] - start[i]) for i in (0, 1)]
                point[axis] = fraction * layout["width" if axis == 0 else "height"]
                points.append(tuple(point))
            seeds.append(evaluate([start, *points, end], layout))
    planning = refine_routes(seeds, layout, max_simulations=64)
    successful = [node for node in seeds if node["outcome"]["state"] == "LANDED"]
    if planning["best"] is not None:
        successful.append(planning["best"])
    best = min(successful, key=lambda node: node["outcome"]["time"], default=None)
    tested = len(seeds) + planning["tested"]
    # Pull corners towards their neighbours and remove unnecessary waypoints.
    # Re-run after improvements because timing changes moving-cloud clearance.
    while best is not None and tested < MAX_LOCAL_SIMULATIONS:
        previous = best
        points = best["waypoints"]
        for index in range(1, len(points) - 1):
            before, after = points[index - 1], points[index + 1]
            midpoint = ((before[0] + after[0]) / 2, (before[1] + after[1]) / 2)
            candidates = [points[:index] + points[index + 1:]]
            for fraction in (0.75, 0.5, 0.25):
                corner = tuple(points[index][i] + fraction * (midpoint[i] - points[index][i])
                               for i in (0, 1))
                candidates.append(points[:index] + [corner] + points[index + 1:])
            for candidate in candidates:
                trial = evaluate(candidate, layout)
                tested += 1
                if (trial["outcome"]["state"] == "LANDED"
                        and trial["outcome"]["time"] < best["outcome"]["time"]):
                    best = trial
                if tested >= MAX_LOCAL_SIMULATIONS:
                    break
            if tested >= MAX_LOCAL_SIMULATIONS:
                break
        if best is previous:
            break
    return {"best": best, "tested": tested, "refined": tested - len(seeds)}
