"""
Hand landmarks -> (mode, point).
Owner: Avyay
 
Modes:
  "DRAW"   thumb and index pinched together -> draw the flight path
  "HOVER"  thumb and index apart            -> move without drawing (releases the path)
  "IDLE"   no usable hand
 
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
THUMB_TIP = 4
INDEX_MCP = 5
INDEX_TIP = 8
MIDDLE_MCP = 9
PINKY_MCP = 17
 
# 1. Active zone: this part of the camera image (0..1) covers the whole screen
ZONE_LEFT = 0.20
ZONE_RIGHT = 0.80
ZONE_TOP = 0.15
ZONE_BOTTOM = 0.75
 
# 2. Thumb/index distance relative to palm size, independent of camera distance.
# Separate thresholds prevent small tracking fluctuations from releasing a pinch.
PINCH_CLOSE_RATIO = 0.30
PINCH_OPEN_RATIO = 0.45

# Debounce in seconds: camera/display frame rates must not affect release timing.
ENTER_TIME = 0.05
EXIT_DRAW_TIME = 0.18
 
# 5. Lost-hand grace (seconds)
LOST_GRACE_TIME = 0.25
 
# 6. Adaptive smoothing
MIN_ALPHA = 0.25          # used when the finger is still (smooth)
MAX_ALPHA = 0.85          # used when the finger moves fast (responsive)
FAST_SPEED = 40.0         # px per frame that counts as "fast"
 
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
        "draw_point": None,      # last confirmed DRAW point for the release hold
        "lost": 0.0,
        "pinching": False,
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
 
 
def pinch_ratio(landmarks, aspect):
    """3D fingertip gap divided by palm size; None for a degenerate hand."""
    palm_size = max(
        pixel_dist(landmarks[WRIST], landmarks[MIDDLE_MCP], aspect, 1),
        pixel_dist(landmarks[INDEX_MCP], landmarks[PINKY_MCP], aspect, 1),
    )
    if palm_size < 1e-9:
        return None
    return pixel_dist(landmarks[THUMB_TIP], landmarks[INDEX_TIP], aspect, 1) / palm_size
 
 
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
    # Use source image proportions, not the stretched game canvas.
    aspect = w / h if camera_aspect is None else camera_aspect
    ratio = None if landmarks is None else pinch_ratio(landmarks, aspect)
    # ---- 5. No hand: short grace period, then reset ----
    if ratio is None:
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
 
    threshold = PINCH_OPEN_RATIO if state["pinching"] else PINCH_CLOSE_RATIO
    state["pinching"] = ratio < threshold
    raw_mode = "DRAW" if state["pinching"] else "HOVER"
 
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
    if state["smooth"] is None:
        state["smooth"] = (x, y)
    else:
        old_x, old_y = state["smooth"]
        speed = math.hypot(x - old_x, y - old_y)
        alpha = MIN_ALPHA + (MAX_ALPHA - MIN_ALPHA) * min(1.0, speed / FAST_SPEED)
        new_x = alpha * x + (1 - alpha) * old_x
        new_y = alpha * y + (1 - alpha) * old_y
        state["smooth"] = (new_x, new_y)
 
    sx, sy = state["smooth"]
    point = (int(sx), int(sy))
 
    # ---- 4. Release hold: freeze the point while leaving DRAW ----
    if state["mode"] == "DRAW":
        if state["candidate"] == "DRAW":
            state["draw_point"] = point
        elif state["draw_point"] is not None:
            return "DRAW", state["draw_point"]
 
    return state["mode"], point
