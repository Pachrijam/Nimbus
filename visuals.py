"""
Everything the game looks like. Every function here is a simple PLACEHOLDER
that already works, so the game is visible from minute one. Replace them with
nicer versions one at a time.
Owner: Paul

Colors are BGR, not RGB.
"""
import math

import cv2
import numpy as np

SKY_TOP = (235, 190, 120)       # deeper blue
SKY_BOTTOM = (250, 235, 205)    # pale blue near the horizon
CLOUD_COLOR = (255, 255, 255)
STAR_COLOR = (0, 215, 255)      # gold
PLANE_COLOR = (70, 70, 70)
PATH_COLOR = (255, 255, 255)
PAD_COLOR = (90, 160, 90)


def make_sky(w, h):
    """Background image, built once per level.
    TODO (Paul): vertical gradient SKY_TOP -> SKY_BOTTOM, faint background clouds."""
    sky = np.zeros((h, w, 3), dtype=np.uint8)
    sky[:] = SKY_TOP
    return sky


def draw_cloud(img, x, y, r):
    """TODO (Paul): puffy cloud from several overlapping circles + soft shadow.
    Keep the collision circle (x, y, r) roughly matching what players see."""
    cv2.circle(img, (int(x), int(y)), int(r), CLOUD_COLOR, -1, cv2.LINE_AA)


def draw_star(img, x, y, r):
    """TODO (Paul): real 5-point star (cv2.fillPoly), maybe pulsing glow."""
    cv2.circle(img, (int(x), int(y)), int(r), STAR_COLOR, -1, cv2.LINE_AA)


def draw_pad(img, x, y):
    """Start pad under the plane's starting spot."""
    cv2.rectangle(img, (int(x) - 30, int(y) + 12), (int(x) + 30, int(y) + 20), PAD_COLOR, -1)


def draw_plane(img, x, y, heading, size=18):
    """Triangle pointing along heading (radians). TODO (Paul): nicer paper-plane shape."""
    nose = (x + size * math.cos(heading), y + size * math.sin(heading))
    left = (x + size * 0.7 * math.cos(heading + 2.5), y + size * 0.7 * math.sin(heading + 2.5))
    right = (x + size * 0.7 * math.cos(heading - 2.5), y + size * 0.7 * math.sin(heading - 2.5))
    pts = np.array([nose, left, right], dtype=np.int32)
    cv2.fillPoly(img, [pts], PLANE_COLOR, cv2.LINE_AA)


def draw_path(img, points, color=PATH_COLOR, thickness=3):
    """TODO (Paul): dotted/dashed line looks more like a flight plan."""
    if len(points) < 2:
        return
    pts = np.array(points, dtype=np.int32).reshape(-1, 1, 2)
    cv2.polylines(img, [pts], False, color, thickness, cv2.LINE_AA)


def draw_route(img, points, tight_flags):
    """Planned route with infeasible (too-tight) turns highlighted in red.
    TODO (Paul): draw each segment white, or red if either end is flagged."""
    draw_path(img, points)


def draw_trail(img, trail):
    """Contrail behind the plane. TODO (Paul): fade older points out."""
    draw_path(img, trail, (245, 245, 245), 2)


def draw_autopilot(img, plane_xy, target_xy):
    """Autopilot view: the point the controller is aiming at."""
    if target_xy is None:
        return
    p = (int(plane_xy[0]), int(plane_xy[1]))
    t = (int(target_xy[0]), int(target_xy[1]))
    cv2.line(img, p, t, (0, 0, 255), 1, cv2.LINE_AA)
    cv2.circle(img, t, 5, (0, 0, 255), -1, cv2.LINE_AA)


def draw_wind(img, wind, x, y):
    """Wind arrow in the HUD. TODO (Paul): drifting wind streaks across the sky."""
    wx, wy = wind
    end = (int(x + wx), int(y + wy))
    cv2.arrowedLine(img, (int(x), int(y)), end, (80, 80, 80), 2, cv2.LINE_AA, tipLength=0.3)


def draw_camera_inset(img, frame, scale=0.22):
    """Small live camera view in a corner so players can see their hand."""
    h, w, _ = img.shape
    small_w = int(w * scale)
    small_h = int(h * scale)
    small = cv2.resize(frame, (small_w, small_h))
    img[10:10 + small_h, w - small_w - 10:w - 10] = small
    cv2.rectangle(img, (w - small_w - 10, 10), (w - 10, 10 + small_h), (255, 255, 255), 2)


def draw_cursor(img, mode, point):
    """Solid dot while drawing, hollow ring while hovering."""
    if point is None:
        return
    if mode == "DRAW":
        cv2.circle(img, point, 8, (0, 0, 255), -1, cv2.LINE_AA)
    else:
        cv2.circle(img, point, 12, (40, 40, 40), 2, cv2.LINE_AA)


def draw_text(img, text, x, y, scale=0.8):
    """Readable text: dark outline + white fill."""
    cv2.putText(img, text, (int(x), int(y)), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(img, text, (int(x), int(y)), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 2, cv2.LINE_AA)


def draw_message(img, text, scale=1.6):
    """Big centered message (READY / LANDED! / TURBULENCE!)."""
    h, w, _ = img.shape
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 3)
    draw_text(img, text, (w - tw) // 2, h // 3, scale)


def draw_hud(img, level, score, tries, wind):
    """TODO (Paul): nicer panel. Placeholder: one line top-left + wind arrow."""
    draw_text(img, f"Level {level}   Score {score}   Tries {tries}", 15, 35)
    draw_text(img, "Wind", 15, 75, 0.6)
    draw_wind(img, wind, 90, 70)
