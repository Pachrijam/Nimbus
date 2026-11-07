"""
Flight Path game: state machine, levels, collisions, score.
Owner: Person 3 (calls physics.py from Avyay and visuals.py from Paul)

States:  READY -> DRAWING -> FLYING -> LANDED  -> next level
                                   -> CRASHED -> retry
"""
import random

import paths
import physics

START_RADIUS = 40        # px: the path must start this close to the plane
STAR_RADIUS = 28
MIN_PATH_POINTS = 10     # ignore accidental tiny paths
MESSAGE_TIME = 2.0       # seconds to show LANDED / CRASHED before moving on
PAD_MARGIN = 90          # px from the left edge
MAX_CLOUDS = 6
MIN_WIDTH = 640
MIN_HEIGHT = 480


class Game:
    def __init__(self, w, h, *, headless=False):
        if w < MIN_WIDTH or h < MIN_HEIGHT:
            raise ValueError(
                f"Game requires a frame at least {MIN_WIDTH}x{MIN_HEIGHT} pixels."
            )
        self.w = w
        self.h = h
        self.headless = headless
        self.level = 1
        self.score = 0
        self.show_autopilot = False
        self.cursor_mode = "IDLE"
        self.cursor_point = None
        self.start_level()

    # ---------- Level setup ----------
    def start_level(self):
        if not self.headless:
            import visuals
            self.sky = visuals.make_sky(self.w, self.h)
        self.pad = (PAD_MARGIN, self.h // 2)
        self.star = (self.w - 120, random.randint(120, self.h - 120))
        # Increase difficulty with each level.
        if self.level == 1:
            num_clouds = 2
            wind_strength = 0
            cloud_speed = 0
        elif self.level == 2:
            num_clouds = 3
            wind_strength = 15
            cloud_speed = 0
        elif self.level == 3:
            num_clouds = 4
            wind_strength = 15
            cloud_speed = 10
        elif self.level == 4:
            num_clouds = 5
            wind_strength = 25
            cloud_speed = 20
        else:
            num_clouds = min(self.level + 1, MAX_CLOUDS)
            wind_strength = 30 + (self.level - 5) * 5
            cloud_speed = 25 + (self.level - 5) * 5

        # Generate clouds at random positions
        self.cloud_layout = []

        for i in range(num_clouds):
            for attempt in range(100):
                r = 45
                x = random.randint(180, self.w - 180)
                y = random.randint(r, self.h - r)

                position = (x, y)
                valid = True

                # Keep clouds away from the starting point and destination
                if paths.distance(position, self.pad) < r + START_RADIUS + 30:
                    valid = False

                if paths.distance(position, self.star) < r + STAR_RADIUS + 30:
                    valid = False

                # Prevent clouds from overlapping
                for cloud in self.cloud_layout:
                    other = (cloud["x"], cloud["y"])

                    if paths.distance(position, other) < r + cloud["r"] + 10:
                        valid = False

                if valid:
                    vx = random.choice([-cloud_speed, cloud_speed])

                    self.cloud_layout.append({
                        "x": x,
                        "y": y,
                        "r": r,
                        "vx": vx
                    })
                    break

        # Set wind direction and strength
        self.wind = (
            random.uniform(-wind_strength, wind_strength),
            random.uniform(-wind_strength, wind_strength)
        )

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
            if mode == "DRAW" and point is not None:
                if paths.distance(point, self.pad) <= START_RADIUS:
                    self.raw_path = [point]
                    self.state = "DRAWING"

        elif self.state == "DRAWING":
            if mode == "DRAW" and point is not None:
                if paths.distance(point, self.raw_path[-1]) >= 3:
                    self.raw_path.append(point)
            else:
                self.finish_path()

        elif self.state == "FLYING":
            self.update_flight(dt)

        elif self.state in ("LANDED", "CRASHED", "INVALID"):
            self.timer += dt
            if self.timer >= MESSAGE_TIME:
                if self.state == "LANDED":
                    self.next_level()
                else:
                    self.retry()

    def finish_path(self):
        if len(self.raw_path) < MIN_PATH_POINTS:
            self.retry()
            return
        if paths.distance(self.raw_path[-1], self.star) > STAR_RADIUS:
            self.state = "INVALID"
            self.timer = 0.0
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

        position = (self.plane["x"], self.plane["y"])
        if paths.distance(position, self.star) <= STAR_RADIUS:
            self.state = "LANDED"

            base_score = max(0, 1000 - 200 * (self.tries - 1))
            route_length = paths.path_length(self.path)
            direct_length = paths.distance(self.pad, self.star)

            efficiency = min(1.0, direct_length / max(route_length, 1))
            bonus = int(efficiency * 200)

            self.score += base_score + bonus
            self.timer = 0.0
            return

        for cloud in self.clouds:
            if paths.distance(position, (cloud["x"], cloud["y"])) <= cloud["r"]:
                self.state = "CRASHED"
                self.timer = 0.0
                return

        margin = 30
        if not (-margin <= position[0] <= self.w + margin and
                -margin <= position[1] <= self.h + margin):
            self.state = "CRASHED"
            self.timer = 0.0

    # ---------- Drawing ----------
    def draw(self, frame):
        import visuals

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
        elif self.state == "INVALID":
            visuals.draw_message(img, "ROUTE MUST REACH DESTINATION", 0.8)

        visuals.draw_cursor(img, self.cursor_mode, self.cursor_point)
        return img
