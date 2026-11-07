"""
Flight physics: pure pursuit path following with a turn-rate limit and wind.
Owner: Avyay (exact-follow fallback: Person 3)
 
Plane = dict with x, y, heading (radians, 0 = right, positive = clockwise on screen),
speed (px/s), i (progress index along the path), target (look-ahead point or None).
 
Build order (test each in physics_test.py):
  1. move_plane    - fly forward along the heading, plus wind
  2. steer_toward  - turn toward a target point, with a turn-rate limit
  3. find_target   - pick the look-ahead point on the path
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
    """Move the plane forward one frame. Called by game.py while FLYING.
    path: list of evenly spaced (x, y) points (already smoothed + resampled)
    wind: (wind_x, wind_y) in px per second
    dt:   seconds since the last frame
    """
    if USE_PHYSICS:
        step_pursuit(plane, path, wind, dt)
    else:
        step_exact(plane, path, dt)
 
 
def step_pursuit(plane, path, wind, dt):
    """One frame of pure pursuit: find target -> steer toward it -> move. (Already done.)"""
    target = find_target(plane, path)
    plane["target"] = target
    if target is not None:
        steer_toward(plane, target[0], target[1], dt)
    move_plane(plane, wind, dt)
 
 
def wrap_angle(a):
    """Force an angle into -pi..pi so the plane always turns the short way. (Already done.)"""
    return (a + math.pi) % (2 * math.pi) - math.pi
 
 
# ---------------- Avyay: write these three ----------------
 
def move_plane(plane, wind, dt):
    """STEP 1. Move the plane forward along its heading, plus wind.
    x changes by (speed * cos(heading) + wind_x) * dt
    y changes by (speed * sin(heading) + wind_y) * dt
    """
    plane["x"] += (plane["speed"] * math.cos(plane["heading"]) + wind[0]) * dt
    plane["y"] += (plane["speed"] * math.sin(plane["heading"]) + wind[1]) * dt
 
 
def steer_toward(plane, tx, ty, dt):
    """STEP 2. Turn the plane toward the point (tx, ty).
    a. desired heading: angle from the plane to the target (math.atan2(dy, dx))
    b. error = wrap_angle(desired - current heading)
    c. turn_rate = K_STEER * error, then clamp it to the range -MAX_TURN .. +MAX_TURN
    d. heading changes by turn_rate * dt
    """
    dx = tx - plane["x"]
    dy = ty - plane["y"]
    desired_heading = math.atan2(dy, dx)
    error = wrap_angle(desired_heading - plane["heading"])
    turn_rate = K_STEER * error
    if turn_rate > MAX_TURN:
        turn_rate = MAX_TURN
    elif turn_rate < -MAX_TURN:
        turn_rate = -MAX_TURN
    plane["heading"] += turn_rate * dt
 
 
def find_target(plane, path):
    """STEP 3. Return the look-ahead point (x, y) on the path, or None to fly straight."""
    # a. Route too short to follow
    if len(path) < 2:
        return None
 
    # b. Update progress: the closest route point, searching forward only
    start = plane["i"]
    stop = min(len(path), start + SEARCH_WINDOW)
    best_index = start
    best_dist = float("inf")
    for k in range(start, stop):
        dist = math.hypot(path[k][0] - plane["x"], path[k][1] - plane["y"])
        if dist < best_dist:
            best_dist = dist
            best_index = k
    plane["i"] = best_index
 
    # c. Reached the end of the route: stop steering, fly straight
    if plane["i"] >= len(path) - 1:
        return None
 
    # d. Look-ahead point: the first route point at least LOOKAHEAD px away
    for k in range(plane["i"], len(path)):
        dist = math.hypot(path[k][0] - plane["x"], path[k][1] - plane["y"])
        if dist >= LOOKAHEAD:
            return path[k]
    return path[-1]
 
 
# ---------------- Person 3: fallback ----------------
 
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