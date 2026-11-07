"""
Hand landmarks -> (mode, point).
Owner: Avyay
 
Modes:
  "DRAW"   index finger up only        -> draw the flight path
  "HOVER"  index + middle fingers up   -> move without drawing (releases the path)
  "IDLE"   anything else, or no hand
 
Fixes for smooth air-drawing:
  1. Active zone       - the middle of the camera maps to the whole screen (no arm stretching)
  2. Tilt-proof checks - "finger up" = tip farther from the wrist than the knuckle (any hand angle)
  3. Sticky DRAW       - entering DRAW is fast, leaving it needs more frames (no broken routes)
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
 
# 1. Active zone: this part of the camera image (0..1) covers the whole screen
ZONE_LEFT = 0.20
ZONE_RIGHT = 0.80
ZONE_TOP = 0.15
ZONE_BOTTOM = 0.75
 
# 2. Finger-up thresholds: tip distance / knuckle distance (from the wrist)
INDEX_UP_RATIO = 1.10     # index counts as up above this
MIDDLE_UP_RATIO = 1.20    # middle must be clearly up -> fewer accidental launches
 
# 3. Debouncing (frames)
ENTER_FRAMES = 2          # frames to switch into a new mode
EXIT_DRAW_FRAMES = 4      # frames to leave DRAW (sticky, so routes don't break)
 
# 5. Lost-hand grace (frames)
LOST_GRACE_FRAMES = 6
 
# 6. Adaptive smoothing
MIN_ALPHA = 0.25          # used when the finger is still (smooth)
MAX_ALPHA = 0.85          # used when the finger moves fast (responsive)
FAST_SPEED = 40.0         # px per frame that counts as "fast"
 
# Values that must survive between frames
state = {
    "mode": "IDLE",          # official, debounced mode
    "candidate": "IDLE",     # raw mode currently being counted
    "count": 0,              # frames in a row the candidate has been seen
    "smooth": None,          # smoothed (x, y) floats, or None
    "draw_point": None,      # last point while firmly in DRAW (used by the release hold)
    "lost": 0,               # frames in a row without a hand
}
 
 
def reset():
    state["mode"] = "IDLE"
    state["candidate"] = "IDLE"
    state["count"] = 0
    state["smooth"] = None
    state["draw_point"] = None
 
 
def to_screen(v, lo, hi, size):
    """Map a camera value in lo..hi to 0..size, clamped to the screen."""
    t = (v - lo) / (hi - lo)
    t = max(0.0, min(1.0, t))
    return t * size
 
 
def pixel_dist(a, b, w, h):
    """Distance between two landmarks in pixels (fair in x and y)."""
    return math.hypot((a.x - b.x) * w, (a.y - b.y) * h)
 
 
def finger_ratio(landmarks, tip, pip, w, h):
    """How extended a finger is: >1 means the tip is farther from the wrist than the knuckle."""
    wrist = landmarks[WRIST]
    d_pip = pixel_dist(landmarks[pip], wrist, w, h)
    if d_pip < 1:
        return 0.0
    return pixel_dist(landmarks[tip], wrist, w, h) / d_pip
 
 
def get_gesture(landmarks, w, h):
    """
    landmarks: list of 21 hand points (x and y from 0 to 1), or None if no hand
    w, h: frame width and height in pixels
    returns: (mode, (x, y)) with (x, y) in integer pixels, or (mode, None)
    """
    # ---- 5. No hand: short grace period, then reset ----
    if landmarks is None:
        state["lost"] += 1
        if state["lost"] <= LOST_GRACE_FRAMES and state["smooth"] is not None:
            sx, sy = state["smooth"]
            return state["mode"], (int(sx), int(sy))
        reset()
        return "IDLE", None
    state["lost"] = 0
 
    # ---- 1. Fingertip position through the active zone ----
    tip = landmarks[INDEX_TIP]
    x = to_screen(tip.x, ZONE_LEFT, ZONE_RIGHT, w)
    y = to_screen(tip.y, ZONE_TOP, ZONE_BOTTOM, h)
 
    # ---- 2. Tilt-proof finger checks -> raw mode ----
    index_up = finger_ratio(landmarks, INDEX_TIP, INDEX_PIP, w, h) > INDEX_UP_RATIO
    middle_up = finger_ratio(landmarks, MIDDLE_TIP, MIDDLE_PIP, w, h) > MIDDLE_UP_RATIO
 
    if index_up and not middle_up:
        raw_mode = "DRAW"
    elif index_up and middle_up:
        raw_mode = "HOVER"
    else:
        raw_mode = "IDLE"
 
    # ---- 3. Debouncing (sticky DRAW) ----
    if raw_mode == state["candidate"]:
        state["count"] += 1
    else:
        state["candidate"] = raw_mode
        state["count"] = 1
 
    if state["mode"] == "DRAW":
        needed = EXIT_DRAW_FRAMES
    else:
        needed = ENTER_FRAMES
 
    if state["candidate"] != state["mode"] and state["count"] >= needed:
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