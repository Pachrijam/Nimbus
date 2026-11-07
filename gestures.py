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
        # TODO (Avyay): reset the smoothing so the point doesn't glide in from the old spot
        state["smooth"] = None
        state["mode"] = "IDLE"
        state["candidate"] = "IDLE"
        state["count"] = 0
        return "IDLE", None

    tip = landmarks[INDEX_TIP]
    x = int(tip.x * w)
    y = int(tip.y * h)

    # TODO (Avyay): finger-up checks (tip y < joint y)  -> raw mode
    index_up = landmarks[INDEX_TIP].y < landmarks[INDEX_PIP].y
    middle_up = landmarks[MIDDLE_TIP].y < landmarks[MIDDLE_PIP].y
    
    if index_up and not middle_up:
        raw_mode = "DRAW"
    elif index_up and middle_up:
        raw_mode = "HOVER"
    else:
        raw_mode = "IDLE"
    
    # TODO (Avyay): debouncing with state["candidate"] / state["count"]
    if raw_mode == state["candidate"]:
        state["count"] += 1
        
    else:
        state["candidate"] = raw_mode
        state["count"] = 1
        
    if state["count"] >= DEBOUNCE_FRAMES:
        state["mode"] = state["candidate"]
        
    # TODO (Avyay): smoothing with state["smooth"] and SMOOTHING
    if state["smooth"] is None:
        state["smooth"] = (x,y)
    else:
        old_x, old_y = state["smooth"]
        new_x = SMOOTHING*x + (1-SMOOTHING)*old_x
        new_y = SMOOTHING*y + (1-SMOOTHING)*old_y
        state["smooth"] = (new_x, new_y)

    smooth_x, smooth_y = state["smooth"]
    return state["mode"], (int(smooth_x), int(smooth_y))