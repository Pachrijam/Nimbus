"""
Hand landmarks -> (mode, point).
Owner: Avyay

Modes:
  "DRAW"   index finger up only        -> draw the flight path
  "HOVER"  at least two fingers up     -> move without drawing (releases the path)
  "IDLE"   anything else, or no hand

Fixes for smooth air-drawing:
  1. Active zone       - the middle of the camera maps to the whole screen (no arm stretching)
  2. Depth-aware checks - compare 3D distances relative to hand size
  3. Sticky DRAW       - entering DRAW is fast, leaving it needs a stable gesture
  4. Release hold      - while switching away from DRAW, the point freezes (no jump at the route's end)
  5. Lost-hand grace   - a few missing frames don't end the route
  6. Adaptive smoothing - heavy smoothing when slow (no jitter), light when fast (no lag)
"""
import math

# MediaPipe landmark numbers
WRIST = 0
INDEX_PIP = 6
INDEX_TIP = 8
MIDDLE_PIP = 10
MIDDLE_TIP = 12
THUMB_MCP = 2
THUMB_TIP = 4
RING_PIP = 14
RING_TIP = 16
PINKY_PIP = 18
PINKY_TIP = 20

# 1. Active zone: this part of the camera image (0..1) covers the whole screen
ZONE_LEFT = 0.20
ZONE_RIGHT = 0.80
ZONE_TOP = 0.15
ZONE_BOTTOM = 0.75

# 2. Finger-up thresholds: tip distance / knuckle distance (from the wrist)
INDEX_UP_RATIO = 1.10     # index counts as up above this
MIDDLE_UP_RATIO = 1.35    # middle must be clearly up -> fewer accidental launches

# Hysteresis keeps uncertain finger estimates from toggling the gesture.
INDEX_DOWN_RATIO = 0.85   # tolerate depth noise while the index is already extended
MIDDLE_DOWN_RATIO = 1.10

# The thumb bends at its MCP; the other fingers bend at their PIP joints.
RELEASE_FINGERS = (
    ("thumb_up", THUMB_TIP, THUMB_MCP),
    ("middle_up", MIDDLE_TIP, MIDDLE_PIP),
    ("ring_up", RING_TIP, RING_PIP),
    ("pinky_up", PINKY_TIP, PINKY_PIP),
)

# Debounce in seconds: camera/display frame rates must not affect release timing.
ENTER_TIME = 0.05
EXIT_DRAW_TIME = 0.18

# 5. Lost-hand grace (seconds)
LOST_GRACE_TIME = 0.25
# 6. Adaptive, time-aware smoothing (One Euro filter)
SMOOTH_MIN_CUTOFF = 1.2
SMOOTH_BETA = 0.03
SMOOTH_DERIVATIVE_CUTOFF = 1.0
# Values that must survive between frames
_default_state = {}


def reset_gesture(tracker=None):
    """Clear one browser session, or the desktop's default tracker."""
    tracker = _default_state if tracker is None else tracker
    tracker.clear()
    tracker.update({
        "mode": "IDLE",          # official, debounced mode
        "candidate": "IDLE",     # raw mode currently being counted
        "candidate_time": 0.0,
        "smooth": None,          # smoothed (x, y) floats, or None
        "smooth_raw": None,      # previous unfiltered point
        "smooth_velocity": (0.0, 0.0),
        "draw_point": None,      # last confirmed DRAW point for the release hold
        "lost": 0.0,
        "index_up": False,
        "middle_up": False,
        "thumb_up": False,
        "ring_up": False,
        "pinky_up": False,
    })


def reset():
    reset_gesture()


reset_gesture()


def to_screen(v, lo, hi, size):
    """Map a camera value in lo..hi to 0..size, clamped to the screen."""
    t = (v - lo) / (hi - lo)
    t = max(0.0, min(1.0, t))
    return t * size


def pixel_dist(a, b, w, h):
    """3D distance: MediaPipe depth uses the same scale as normalized x."""
    return math.hypot((a.x - b.x) * w, (a.y - b.y) * h,
                      (getattr(a, "z", 0.0) - getattr(b, "z", 0.0)) * w)


def finger_ratio(landmarks, tip, pip, w, h):
    """How extended a finger is: >1 means the tip is farther from the wrist than the knuckle."""
    wrist = landmarks[WRIST]
    d_pip = pixel_dist(landmarks[pip], wrist, w, h)
    if d_pip < 1e-9:
        return 0.0
    return pixel_dist(landmarks[tip], wrist, w, h) / d_pip


def _filter_alpha(dt, cutoff):
    tau = 1 / (2 * math.pi * cutoff)
    return 1 / (1 + tau / dt)


def _smooth_position(state, x, y, dt):
    if state["smooth"] is None:
        state["smooth"] = (x, y)
        state["smooth_raw"] = (x, y)
        state["smooth_velocity"] = (0.0, 0.0)
        return state["smooth"]

    dt = max(dt, 1e-3)
    previous_x, previous_y = state["smooth"]
    raw_x, raw_y = state["smooth_raw"]
    velocity_x, velocity_y = state["smooth_velocity"]
    derivative_alpha = _filter_alpha(dt, SMOOTH_DERIVATIVE_CUTOFF)
    raw_velocity_x = (x - raw_x) / dt
    raw_velocity_y = (y - raw_y) / dt
    velocity_x += derivative_alpha * (raw_velocity_x - velocity_x)
    velocity_y += derivative_alpha * (raw_velocity_y - velocity_y)

    cutoff = SMOOTH_MIN_CUTOFF + SMOOTH_BETA * math.hypot(velocity_x, velocity_y)
    position_alpha = _filter_alpha(dt, cutoff)
    state["smooth"] = (
        previous_x + position_alpha * (x - previous_x),
        previous_y + position_alpha * (y - previous_y),
    )
    state["smooth_raw"] = (x, y)
    state["smooth_velocity"] = (velocity_x, velocity_y)
    return state["smooth"]


def get_gesture(landmarks, w, h, tracker=None, dt=1 / 30, *, camera_aspect=None):
    """
    landmarks: 21 normalized x/y/z hand points, or None if no hand
    w, h: output dimensions; camera_aspect is source width / height if different
    returns: (mode, (x, y)) with (x, y) in integer pixels, or (mode, None)
    """
    state = _default_state if tracker is None else tracker
    if not state:
        reset_gesture(state)
    dt = max(0.0, min(dt, 0.1))
    # ---- 5. No hand: short grace period, then reset ----
    if landmarks is None:
        state["lost"] += dt
        # A missing frame cannot count toward a deliberate release.
        state["candidate"] = state["mode"]
        state["candidate_time"] = 0.0
        if state["lost"] <= LOST_GRACE_TIME and state["smooth"] is not None:
            held = state["draw_point"] if state["mode"] == "DRAW" else None
            sx, sy = held or state["smooth"]
            return state["mode"], (int(sx), int(sy))
        reset_gesture(state)
        return "IDLE", None
    state["lost"] = 0

    # ---- 1. Fingertip position through the active zone ----
    tip = landmarks[INDEX_TIP]
    x = to_screen(tip.x, ZONE_LEFT, ZONE_RIGHT, w)
    y = to_screen(tip.y, ZONE_TOP, ZONE_BOTTOM, h)

    # Use source image proportions, not the stretched game canvas.
    aspect = w / h if camera_aspect is None else camera_aspect
    index_threshold = INDEX_DOWN_RATIO if state["index_up"] else INDEX_UP_RATIO
    index_up = finger_ratio(landmarks, INDEX_TIP, INDEX_PIP, aspect, 1) > index_threshold
    state["index_up"] = index_up
    raised_count = int(index_up)
    for key, finger_tip, joint in RELEASE_FINGERS:
        threshold = MIDDLE_DOWN_RATIO if state[key] else MIDDLE_UP_RATIO
        state[key] = finger_ratio(landmarks, finger_tip, joint, aspect, 1) > threshold
        raised_count += int(state[key])

    if raised_count >= 2:
        raw_mode = "HOVER"
    elif index_up:
        raw_mode = "DRAW"
    else:
        raw_mode = "IDLE"
    previous_mode = state["mode"]

    # ---- 3. Debouncing (sticky DRAW) ----
    if raw_mode == state["candidate"]:
        state["candidate_time"] += dt
    else:
        state["candidate"] = raw_mode
        state["candidate_time"] = dt

    if state["mode"] == "DRAW":
        needed = EXIT_DRAW_TIME
    else:
        needed = ENTER_TIME

    if state["candidate"] != state["mode"] and state["candidate_time"] + 1e-9 >= needed:
        state["mode"] = state["candidate"]

    # ---- 6. Adaptive smoothing ----
    if previous_mode != "DRAW" and state["mode"] == "DRAW":
        state["smooth"] = (x, y)
        state["smooth_raw"] = (x, y)
        state["smooth_velocity"] = (0.0, 0.0)
    else:
        _smooth_position(state, x, y, dt)
    sx, sy = state["smooth"]
    point = (int(sx), int(sy))

    # ---- 4. Release hold: freeze the point while leaving DRAW ----
    if state["mode"] == "DRAW":
        if state["candidate"] == "DRAW":
            state["draw_point"] = point
        elif state["draw_point"] is not None:
            return "DRAW", state["draw_point"]

    return state["mode"], point
