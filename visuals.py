"""
Everything the game looks like. Every function here is a simple PLACEHOLDER
that already works, so the game is visible from minute one. Replace them with
nicer versions one at a time.
Owner: Paul

Colors are BGR, not RGB.
"""
import math
from functools import lru_cache

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


@lru_cache(maxsize=32)
def _cloud_sprite(radius):
    """Cache a shaded cloud and its soft outer shadow at each display size."""
    margin = math.ceil(radius * 1.4)
    side = margin * 2 + 1
    # Sample a continuous Bezier outline, then antialias the silhouette.
    curves = [
        (-1.16, -0.02, -1.04, -0.47, -0.68, -0.48),
        (-0.7, -0.86, -0.26, -1.08, 0, -0.82),
        (0.25, -1.06, 0.7, -0.88, 0.72, -0.51),
        (1.12, -0.47, 1.2, 0.05, 0.99, 0.29),
        (1.14, 0.64, 0.68, 0.91, 0.4, 0.78),
        (0.1, 1.02, -0.32, 0.9, -0.45, 0.74),
        (-0.84, 0.85, -1.15, 0.63, -0.9, 0.25),
    ]
    start = np.array([-0.9, 0.25])
    outline = [start]
    t = np.linspace(0, 1, 20)[:, None]
    for curve in curves:
        a, b, end = np.array(curve).reshape(3, 2)
        outline.extend((1 - t) ** 3 * start + 3 * (1 - t) ** 2 * t * a
                       + 3 * (1 - t) * t ** 2 * b + t ** 3 * end)
        start = end
    mask = np.zeros((side * 2, side * 2), dtype=np.uint8)
    points = np.rint((np.array(outline) * radius + margin) * 2).astype(np.int32)
    cv2.fillPoly(mask, [points], 255, cv2.LINE_AA)
    alpha = cv2.resize(mask, (side, side), interpolation=cv2.INTER_AREA) / 255.0

    yy, xx = np.mgrid[:side, :side].astype(float)
    xx, yy = (xx - margin) / radius, (yy - margin) / radius
    stops = [0, 0.35, 0.7, 1]
    colors = np.array([(255, 255, 255), (246, 243, 237),
                       (223, 209, 193), (180, 155, 130)])  # BGR
    height = np.clip((yy + 1) / 2, 0, 1)
    color = np.stack([np.interp(height, stops, colors[:, c]) for c in range(3)], axis=-1)
    light = np.clip(1 - np.hypot(xx + 0.3, yy + 0.4) / 1.05, 0, 1) * 0.8
    color += (255 - color) * light[..., None]
    shade = np.clip(1 - np.hypot(xx - 0.5, yy - 0.55) / 0.95, 0, 1) * 0.24
    color += (np.array([135, 100, 74]) - color) * shade[..., None]

    shadow = cv2.warpAffine(alpha, np.float32([[1, 0, 0], [0, 1, radius * 0.12]]),
                            (side, side))
    shadow = cv2.GaussianBlur(shadow, (0, 0), max(0.5, radius * 0.09)) * 0.23
    opacity = alpha + shadow * (1 - alpha)
    premultiplied = (color * alpha[..., None]
                     + np.array([86, 63, 35]) * (shadow * (1 - alpha))[..., None])
    return margin, premultiplied, opacity[..., None]


def draw_cloud(img, x, y, r):
    """Composite one softly shaded cloud, clipping safely at screen edges."""
    margin, color, opacity = _cloud_sprite(max(1, round(r)))
    left, top = round(x) - margin, round(y) - margin
    x0, y0 = max(0, left), max(0, top)
    x1, y1 = min(img.shape[1], left + color.shape[1]), min(img.shape[0], top + color.shape[0])
    if x0 >= x1 or y0 >= y1:
        return
    crop = np.s_[y0 - top:y1 - top, x0 - left:x1 - left]
    img[y0:y1, x0:x1] = np.clip(
        color[crop] + img[y0:y1, x0:x1] * (1 - opacity[crop]), 0, 255).astype(np.uint8)


def draw_star(img, x, y, r):
    """TODO (Paul): real 5-point star (cv2.fillPoly), maybe pulsing glow."""
    cv2.circle(img, (int(x), int(y)), int(r), STAR_COLOR, -1, cv2.LINE_AA)


def draw_pad(img, x, y):
    """Start pad under the plane's starting spot."""
    cv2.rectangle(img, (int(x) - 30, int(y) + 12), (int(x) + 30, int(y) + 20), PAD_COLOR, -1)


def draw_plane(img, x, y, heading, size=18):
    """Top-down quadcopter, with its front camera pointing along heading."""
    scale = size / 18
    c, s = math.cos(heading), math.sin(heading)
    dark, light = (70, 55, 36), (247, 245, 237)

    def point(px, py):
        return (round(x + scale * (px * c - py * s)),
                round(y + scale * (px * s + py * c)))

    def line(a, b, color, thickness):
        cv2.line(img, point(*a), point(*b), color,
                 max(1, round(thickness * scale)), cv2.LINE_AA)

    rotors = [(-13, -11), (13, -11), (-13, 11), (13, 11)]
    for rotor in rotors:
        line((0, 0), rotor, dark, 5)
    for rx, ry in rotors:
        center = point(rx, ry)
        radius = max(1, round(8 * scale))
        cv2.circle(img, center, radius, dark, -1, cv2.LINE_AA)
        cv2.circle(img, center, radius, light, max(1, round(scale)), cv2.LINE_AA)
        line((rx - 4, ry - 3), (rx + 4, ry + 3), (199, 185, 157), 2)
        line((rx - 3, ry + 4), (rx + 3, ry - 4), (199, 185, 157), 2)
        cv2.circle(img, center, max(1, round(2 * scale)), light, -1, cv2.LINE_AA)

    body = np.array([point(*p) for p in
                     [(-9, -6), (6, -6), (11, -3), (11, 3), (6, 6), (-9, 6)]],
                    dtype=np.int32)
    cv2.fillPoly(img, [body], light, cv2.LINE_AA)
    cv2.polylines(img, [body], True, dark, max(1, round(scale)), cv2.LINE_AA)
    line((-5, 0), (0, 0), dark, 5)
    cv2.circle(img, point(7, 0), max(1, round(2.5 * scale)), (224, 203, 54), -1, cv2.LINE_AA)


def draw_path(img, points, color=PATH_COLOR, thickness=3):
    """TODO (Paul): dotted/dashed line looks more like a flight plan."""
    if len(points) < 2:
        return
    pts = np.array(points, dtype=np.int32).reshape(-1, 1, 2)
    cv2.polylines(img, [pts], False, color, thickness, cv2.LINE_AA)


def draw_route(img, points, tight_flags):
    """Planned route with infeasible (too-tight) turns highlighted in red."""
    for i in range(1, len(points)):
        color = PATH_COLOR
        if tight_flags[i - 1] or tight_flags[i]:
            color = (0, 0, 255)
        start = (int(points[i - 1][0]), int(points[i - 1][1]))
        end = (int(points[i][0]), int(points[i][1]))
        cv2.line(img, start, end, color, 3, cv2.LINE_AA)


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
