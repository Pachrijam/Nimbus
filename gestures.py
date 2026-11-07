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
        return "IDLE", None

    tip = landmarks[INDEX_TIP]
    print("tip y:", round(landmarks[8].y, 2), " knuckle y:", round(landmarks[6].y,2))
    x = int(tip.x * w)
    y = int(tip.y * h)

    # TODO (Avyay): finger-up checks (tip y < joint y)  -> raw mode
    # TODO (Avyay): debouncing with state["candidate"] / state["count"]
    # TODO (Avyay): smoothing with state["smooth"] and SMOOTHING

    return "HOVER", (x, y)
