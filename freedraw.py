import cv2
import numpy as np

from visuals import draw_text

# Free-draw colors match the browser palette for desktop testing.
COLORS = [
    (255, 109, 104),
    (104, 186, 255),
    (120, 226, 189),
    (255, 218, 139),
    (255, 255, 255),
]


class FreeDraw:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.ink = np.zeros((h, w, 3), dtype=np.uint8)
        self.color_index = 0
        self.color = COLORS[self.color_index]
        self.thickness = 8
        self.prev_point = None
        self.prev_mode = "IDLE"

    def update(self, mode, point):
        # A held peace sign changes the pen once and immediately previews it.
        if mode == "HOVER" and self.prev_mode != "HOVER":
            self.color_index = (self.color_index + 1) % len(COLORS)
            self.color = COLORS[self.color_index]
        self.prev_mode = mode

        if mode == "DRAW" and point is not None:
            if self.prev_point is not None:
                cv2.line(self.ink, self.prev_point, point, self.color, self.thickness, cv2.LINE_AA)
            else:
                cv2.circle(self.ink, point, self.thickness // 2, self.color, -1, cv2.LINE_AA)
            self.prev_point = point
        else:
            self.prev_point = None

    def draw(self, frame):
        output = frame.copy()
        gray = cv2.cvtColor(self.ink, cv2.COLOR_BGR2GRAY)
        mask = gray > 0
        output[mask] = self.ink[mask]

        draw_text(output, "FREE DRAW", 15, 35, 0.8)
        draw_text(output, "point: draw   peace: next color   c: clear   p: back to game", 15, 62, 0.5)
        cv2.circle(output, (200, 28), 10, self.color, -1, cv2.LINE_AA)
        return output

    def end_stroke(self):
        self.prev_point = None
        self.prev_mode = "IDLE"

    def clear(self):
        self.ink[:] = 0
        self.prev_point = None
