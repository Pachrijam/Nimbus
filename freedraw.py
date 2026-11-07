"""
Simple free-draw mode: warm-up for judges and a backup demo.
Owner: Paul (keep it small: about 30-45 minutes)
"""
import numpy as np

import visuals


class FreeDraw:
    def __init__(self, w, h):
        self.ink = np.zeros((h, w, 3), dtype=np.uint8)   # black = no ink
        self.color = (0, 0, 255)                         # BGR -> red
        self.thickness = 8
        self.prev_point = None

    def update(self, mode, point):
        # TODO (Paul): in DRAW mode with a point, draw a line from prev_point to point on self.ink
        # (cv2.line with cv2.LINE_AA), then prev_point = point.
        # In any other mode, set prev_point back to None.
        pass

    def draw(self, frame):
        # TODO (Paul): combine self.ink with the camera frame using a mask
        # (pixels with ink show the ink, everything else shows the camera).
        output = frame.copy()
        visuals.draw_text(output, "FREE DRAW  -  1 finger: draw   2 fingers: move   c: clear", 10, 35)
        return output

    def clear(self):
        self.ink[:] = 0
