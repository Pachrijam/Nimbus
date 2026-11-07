"""
Free Draw: simple air drawing over the camera (warm-up mode). Toggle with 'p', clear with 'c'.
"""
import cv2
import numpy as np
 
import visuals
 
COLORS = [(40, 40, 230), (230, 160, 40), (60, 200, 60), (40, 200, 255), (255, 255, 255)]
 
 
class FreeDraw:
    def __init__(self, w, h):
        self.ink = np.zeros((h, w, 3), dtype=np.uint8)   # black = no ink
        self.color_index = 0
        self.color = COLORS[0]
        self.thickness = 8
        self.prev_point = None
        self.prev_mode = "IDLE"
 
    def update(self, mode, point):
        # A new pinch after opening the fingers switches to the next color.
        if mode == "DRAW" and self.prev_mode == "HOVER":
            self.color_index = (self.color_index + 1) % len(COLORS)
            self.color = COLORS[self.color_index]
        self.prev_mode = mode
 
        if mode == "DRAW" and point is not None:
            if self.prev_point is not None:
                cv2.line(self.ink, self.prev_point, point, self.color, self.thickness, cv2.LINE_AA)
            self.prev_point = point
        else:
            self.prev_point = None
 
    def draw(self, frame):
        output = frame.copy()
        gray = cv2.cvtColor(self.ink, cv2.COLOR_BGR2GRAY)
        mask = gray > 0
        output[mask] = self.ink[mask]
 
        visuals.draw_text(output, "FREE DRAW", 15, 35, 0.8, (120, 230, 255))
        visuals.draw_text(output, "pinch: draw   open: next color   c: clear   p: back to game", 15, 62, 0.5)
        cv2.circle(output, (200, 28), 10, self.color, -1, cv2.LINE_AA)
        return output
 
    def clear(self):
        self.ink[:] = 0
        self.prev_point = None
