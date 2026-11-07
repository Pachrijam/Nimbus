"""
Hand landmarks -> (mode, point).
Owner: Avyay

Modes:
  "DRAW"   index finger up only        -> draw / draw the flight path
  "HOVER"  index + middle fingers up   -> move without drawing (releases the path)
  "IDLE"   anything else, or no hand
"""
import math

# MediaPipe landmark numbers
WRIST = 0
INDEX_MCP = 5
INDEX_TIP = 8
INDEX_PIP = 6      # middle joint of the index finger
MIDDLE_TIP = 12
MIDDLE_PIP = 10
MIDDLE_MCP = 9

ENGAGE_TIME = 0.04    # seconds of a stable gesture to start drawing
RELEASE_TIME = 0.16   # ignore brief finger-classification flicker while drawing
LOST_HAND_GRACE = 0.25
SMOOTHING = 0.7       # response at 30 fps; adjusted for elapsed time below

# Values that must survive between frames live in this dict.
# (Changing a dict's contents inside a function needs no `global` keyword.)
state = {
    "mode": "IDLE",        # the official, debounced mode
    "candidate": "IDLE",   # the raw mode we are currently seeing
    "elapsed": 0.0,        # seconds of a stable candidate
    "missing": 0.0,        # seconds without a detected hand
    "smooth": None,        # smoothed (x, y) as floats, or None after the hand was lost
}


def reset_gesture(tracker_state=None):
    tracker = tracker_state if tracker_state is not None else state
    tracker.clear()
    tracker.update(mode="IDLE", candidate="IDLE", elapsed=0.0, missing=0.0, smooth=None)


def finger_extended(landmarks, mcp, pip, tip, w, h):
    """Use joint geometry so rotating the hand does not change the gesture."""
    base, joint, end, wrist = (landmarks[i] for i in (mcp, pip, tip, WRIST))
    inward = ((base.x - joint.x) * w, (base.y - joint.y) * h)
    outward = ((end.x - joint.x) * w, (end.y - joint.y) * h)
    lengths = math.hypot(*inward) * math.hypot(*outward)
    if lengths < 1e-6:
        return False
    cosine = sum(a * b for a, b in zip(inward, outward)) / lengths
    tip_distance = math.hypot((end.x - wrist.x) * w, (end.y - wrist.y) * h)
    joint_distance = math.hypot((joint.x - wrist.x) * w, (joint.y - wrist.y) * h)
    return cosine < -0.5 and tip_distance > joint_distance * 1.08


def get_gesture(landmarks, w, h, tracker_state=None, dt=1 / 30):
    """
    landmarks: list of 21 hand points (x and y from 0 to 1), or None if no hand
    w, h: frame width and height in pixels
    returns: (mode, (x, y)) with (x, y) in integer pixels, or (mode, None)
    """
    # Desktop callers retain the default tracker; web sessions use their own.
    state = tracker_state if tracker_state is not None else globals()["state"]
    dt = max(0.0, min(dt, 0.1))
    if landmarks is None:
        state["missing"] = state.get("missing", 0.0) + dt
        state["elapsed"] = 0.0
        if state["smooth"] is not None and state["missing"] < LOST_HAND_GRACE:
            return state["mode"], tuple(int(v) for v in state["smooth"])
        reset_gesture(state)
        return "IDLE", None
    state["missing"] = 0.0

    tip = landmarks[INDEX_TIP]
    x = max(0, min(w - 1, tip.x * w))
    y = max(0, min(h - 1, tip.y * h))

    index_up = finger_extended(landmarks, INDEX_MCP, INDEX_PIP, INDEX_TIP, w, h)
    middle_up = finger_extended(landmarks, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP, w, h)
    if index_up and middle_up:
        raw_mode = "HOVER"
    elif index_up:
        raw_mode = "DRAW"
    else:
        raw_mode = "IDLE"

    if raw_mode == state["candidate"]:
        state["elapsed"] = state.get("elapsed", 0.0) + dt
    else:
        state["candidate"] = raw_mode
        state["elapsed"] = dt

    delay = RELEASE_TIME if state["mode"] == "DRAW" else ENGAGE_TIME
    if state["elapsed"] >= delay:
        state["mode"] = raw_mode

    if state["smooth"] is not None:
        old_x, old_y = state["smooth"]
        alpha = 1 - (1 - SMOOTHING) ** (dt * 30)
        x = alpha * x + (1 - alpha) * old_x
        y = alpha * y + (1 - alpha) * old_y
    state["smooth"] = (x, y)
    return state["mode"], (int(x), int(y))
