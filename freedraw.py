"""
Simple free-draw mode: warm-up for judges and a backup demo.
Owner: Paul (keep it small: about 30-45 minutes)
"""
import cv2
import numpy as np

import visuals


class FreeDraw:
    def __init__(self, w, h):
        self.ink = np.zeros((h, w, 3), dtype=np.uint8)   # black = no ink
        self.color = (0, 0, 255)                         # BGR -> red
        self.thickness = 8
        self.prev_point = None

    def update(self, mode, point):
        if mode == "DRAW" and point is not None:
            if self.prev_point is None:
                cv2.circle(self.ink, point, self.thickness // 2,
                           self.color, -1, cv2.LINE_AA)
            else:
                cv2.line(self.ink, self.prev_point, point, self.color,
                         self.thickness, cv2.LINE_AA)
            self.prev_point = point
        else:
            self.prev_point = None

    def draw(self, frame):
        output = frame.copy()
        mask = np.any(self.ink != 0, axis=2)
        output[mask] = self.ink[mask]
        visuals.draw_text(output, "FREE DRAW  -  1 finger: draw   2 fingers: move   c: clear", 10, 35)
        visuals.draw_text(output, "P or Esc: back to game", 10, 65, scale=0.6)
        return output

    def clear(self):
        self.ink[:] = 0
        self.prev_point = None
