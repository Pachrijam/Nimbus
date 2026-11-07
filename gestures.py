"""
Hand landmarks -> (mode, point).
Owner: Avyay

Modes:
  "DRAW"   index finger up only        -> draw / draw the flight path
  "HOVER"  index + middle fingers up   -> move without drawing (releases the path)
  "IDLE"   anything else, or no hand
"""

# MediaPipe landmark numbers
WRIST = 0
INDEX_TIP = 8
INDEX_PIP = 6      # middle joint of the index finger
MIDDLE_TIP = 12
MIDDLE_PIP = 10

DEBOUNCE_FRAMES = 3   # a new mode must hold this many frames before it counts
SMOOTHING = 0.4       # 0..1: lower = smoother but laggier, higher = snappier but shakier

# Values that must survive between frames live in this dict.
# (Changing a dict's contents inside a function needs no `global` keyword.)
state = {
    "mode": "IDLE",        # the official, debounced mode
    "candidate": "IDLE",   # the raw mode we are currently seeing
    "count": 0,            # how many frames in a row we have seen the candidate
    "smooth": None,        # smoothed (x, y) as floats, or None after the hand was lost
}


def get_gesture(landmarks, w, h):
    """
    landmarks: list of 21 hand points (x and y from 0 to 1), or None if no hand
    w, h: frame width and height in pixels
    returns: (mode, (x, y)) with (x, y) in integer pixels, or (mode, None)
    """
    if landmarks is None:
        state["mode"] = "IDLE"
        state["candidate"] = "IDLE"
        state["count"] = 0
        state["smooth"] = None
        return "IDLE", None

    tip = landmarks[INDEX_TIP]
    x = max(0, min(w - 1, tip.x * w))
    y = max(0, min(h - 1, tip.y * h))

    index_up = tip.y < landmarks[INDEX_PIP].y
    middle_up = landmarks[MIDDLE_TIP].y < landmarks[MIDDLE_PIP].y
    if index_up and middle_up:
        raw_mode = "HOVER"
    elif index_up:
        raw_mode = "DRAW"
    else:
        raw_mode = "IDLE"

    if raw_mode == state["candidate"]:
        state["count"] += 1
    else:
        state["candidate"] = raw_mode
        state["count"] = 1

    if state["count"] >= DEBOUNCE_FRAMES:
        state["mode"] = raw_mode

    if state["smooth"] is not None:
        old_x, old_y = state["smooth"]
        x = SMOOTHING * x + (1 - SMOOTHING) * old_x
        y = SMOOTHING * y + (1 - SMOOTHING) * old_y
    state["smooth"] = (x, y)
    return state["mode"], (int(x), int(y))
