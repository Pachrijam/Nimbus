"""
Flight Path game: state machine, levels, collisions, score.
Owner: Person 3 (calls physics.py from Avyay and visuals.py from Paul)

States:  READY -> DRAWING -> FLYING -> LANDED  -> next level
                                   -> CRASHED -> retry
"""
import random

import paths
import physics
import visuals

START_RADIUS = 40        # px: the path must start this close to the plane
STAR_RADIUS = 28
MIN_PATH_POINTS = 10     # ignore accidental tiny paths
MESSAGE_TIME = 2.0       # seconds to show LANDED / CRASHED before moving on
PAD_MARGIN = 90          # px from the left edge


class Game:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.level = 1
        self.score = 0
        self.show_autopilot = False
        self.cursor_mode = "IDLE"
        self.cursor_point = None
        self.start_level()

    # ---------- Level setup ----------
    def start_level(self):
        """Build a new layout for self.level.
        TODO (Person 3): random cloud positions (never on the pad or the star,
        never overlapping), more clouds + faster drift + stronger wind each level."""
        self.sky = visuals.make_sky(self.w, self.h)
        self.pad = (PAD_MARGIN, self.h // 2)
        self.star = (self.w - 120, random.randint(120, self.h - 120))
        self.cloud_layout = [
            {"x": self.w // 2, "y": self.h // 2, "r": 70, "vx": 0.0},
        ]
        self.wind = (0.0, 0.0)
        self.tries = 0
        self.retry()

    def retry(self):
        """Same layout, fresh attempt."""
        self.state = "READY"
        self.timer = 0.0
        self.raw_path = []
        self.path = []
        self.trail = []
        self.plane = physics.make_plane(self.pad[0], self.pad[1])
        self.clouds = [dict(c) for c in self.cloud_layout]   # copies, so drifting doesn't change the layout

    def next_level(self):
        self.level += 1
        self.start_level()

    # ---------- Per-frame update ----------
    def update(self, mode, point, dt):
        self.cursor_mode = mode
        self.cursor_point = point

        if self.state == "READY":
            # TODO (Person 3): if mode == "DRAW" and point is within START_RADIUS of the plane
            #   -> self.raw_path = [point], state = "DRAWING"
            # if mode == "DRAW" but far from the plane -> show a hint ("Start at the plane")
            pass

        elif self.state == "DRAWING":
            # TODO (Person 3): while mode == "DRAW", append point (skip it if it's within ~3 px of the last one)
            # when mode is no longer "DRAW" -> self.finish_path()
            pass

        elif self.state == "FLYING":
            self.update_flight(dt)

        elif self.state == "LANDED" or self.state == "CRASHED":
            self.timer += dt
            # TODO (Person 3): after MESSAGE_TIME -> next_level() if LANDED, retry() if CRASHED
            pass

    def finish_path(self):
        if len(self.raw_path) < MIN_PATH_POINTS:
            self.retry()
            return
        smooth = paths.chaikin(self.raw_path)
        self.path = paths.resample(smooth)
        self.tries += 1
        self.state = "FLYING"

    def update_flight(self, dt):
        physics.step_plane(self.plane, self.path, self.wind, dt)

        for cloud in self.clouds:
            cloud["x"] += cloud["vx"] * dt

        self.trail.append((self.plane["x"], self.plane["y"]))
        if len(self.trail) > 60:
            self.trail.pop(0)

        # TODO (Person 3), using paths.distance():
        #   plane within STAR_RADIUS of the star       -> state = "LANDED", add score, timer = 0
        #   plane within a cloud's radius               -> state = "CRASHED", timer = 0
        #   plane off the screen (with a small margin)  -> state = "CRASHED", timer = 0
        # Score idea: 1000 - 200 * (tries - 1) + bonus for a short path (paths.path_length)

    # ---------- Drawing ----------
    def draw(self, frame):
        img = self.sky.copy()

        visuals.draw_pad(img, self.pad[0], self.pad[1])
        visuals.draw_star(img, self.star[0], self.star[1], STAR_RADIUS)
        for cloud in self.clouds:
            visuals.draw_cloud(img, cloud["x"], cloud["y"], cloud["r"])

        if self.state == "DRAWING":
            preview = paths.resample(paths.chaikin(self.raw_path))
            min_radius = physics.SPEED / physics.MAX_TURN
            tight = paths.find_tight_turns(preview, min_radius)
            visuals.draw_route(img, preview, tight)
        elif self.state == "FLYING":
            visuals.draw_path(img, self.path, (230, 230, 230), 2)

        visuals.draw_trail(img, self.trail)
        visuals.draw_plane(img, self.plane["x"], self.plane["y"], self.plane["heading"])

        if self.show_autopilot:
            visuals.draw_autopilot(img, (self.plane["x"], self.plane["y"]), self.plane["target"])

        visuals.draw_hud(img, self.level, self.score, self.tries, self.wind)
        visuals.draw_camera_inset(img, frame)

        if self.state == "READY":
            visuals.draw_message(img, "Draw a route from the drone to the destination", 1.0)
        elif self.state == "LANDED":
            visuals.draw_message(img, "DELIVERED!")
        elif self.state == "CRASHED":
            visuals.draw_message(img, "ROUTE FAILED")

        visuals.draw_cursor(img, self.cursor_mode, self.cursor_point)
        return img
