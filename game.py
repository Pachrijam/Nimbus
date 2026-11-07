"""
SKYWRITER: Storm Run - game logic.
Owner: Avyay (v2). Calls physics.py, hazards.py, pickups.py, effects.py, visuals.py.
 
Hand tools:
  DRAW  (point)  - draw the route; mid-flight, reroute near the drone or extend from the path's end (costs ink)
  HOVER (peace)  - launch (only HOVER launches; anything else just pauses the route)
  PALM  (palm)   - sweep fast to gust: shoves storms AND the drone (costs energy)
  FIST  (fist)   - slow-mo while held (costs energy)
 
States:  READY -> DRAWING -> FLYING -> LANDED  -> next level
                                   -> CRASHED -> retry
"""
import math
import random
 
import effects
import hazards
import paths
import physics
import pickups
 
# ---------- Route drawing ----------
START_RADIUS = 90          # px: a route must start this close to the drone
STAR_RADIUS = 32           # px: landing zone
HAND_FINISH_RADIUS = 70    # px: a route ending this close to the star snaps onto it
MIN_PATH_POINTS = 8        # ignore accidental tiny routes
INK_FACTOR = 1.6           # ink = 1.6 x straight-line distance pad -> star
LIVE_SPACING = 8           # px between points drawn during flight
REROUTE_RADIUS = 120       # px: a mid-flight stroke starting this close to the drone replaces the route ahead
EXTEND_RADIUS = 70         # px: a mid-flight stroke starting this close to the route's end extends it
 
# ---------- Palm gust ----------
GUST_RADIUS = 150          # px around the palm that gets pushed
GUST_MIN_SPEED = 250.0     # px/s: the palm must sweep at least this fast
GUST_CLOUD_BLEND = 8.0     # how quickly pushed clouds pick up the sweep's speed
GUST_CLOUD_GAIN = 0.6      # pushed cloud speed = 0.6 x palm speed
GUST_DRONE_GAIN = 0.3      # extra wind on the drone = 0.3 x palm speed (gusts are risky!)
MAX_CLOUD_SPEED = 400.0    # px/s cap
CLOUD_FRICTION = 1.5       # how quickly pushed clouds settle back to their drift
 
# ---------- Energy + slow-mo ----------
ENERGY_MAX = 100.0
PALM_COST = 30.0           # per second of gusting
FIST_COST = 40.0           # per second of slow-mo
ENERGY_REGEN = 8.0         # per second while neither is used
SLOWMO = 0.3               # game speed while the fist is held
 
# ---------- General ----------
MESSAGE_TIME = 2.0         # seconds to show LANDED / CRASHED
PAD_MARGIN = 90            # px from the left edge
MAX_CLOUDS = 7
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
        self.hazards = hazards.Hazards()
        self.pickups = pickups.Pickups()
        self.start_level()
 
    # ================= Level setup =================
    def start_level(self):
        if not self.headless:
            import visuals
            self.sky = visuals.make_sky(self.w, self.h)
        self.pad = (PAD_MARGIN, self.h // 2)
        self.star = (self.w - 120, random.randint(120, self.h - 120))
 
        # Difficulty per level
        if self.level == 1:
            num_clouds = 3
            wind_strength = 0
            storm_speed = 15
        elif self.level == 2:
            num_clouds = 4
            wind_strength = 15
            storm_speed = 25
        elif self.level == 3:
            num_clouds = 5
            wind_strength = 20
            storm_speed = 35
        elif self.level == 4:
            num_clouds = 6
            wind_strength = 30
            storm_speed = 45
        else:
            num_clouds = MAX_CLOUDS
            wind_strength = 30 + (self.level - 4) * 5
            storm_speed = 45 + (self.level - 4) * 8
        self.storm_speed = storm_speed
 
        # Clouds at random spots: off the pad, off the star, not overlapping
        self.cloud_layout = []
        for i in range(num_clouds):
            for attempt in range(100):
                r = random.randint(50, 70)
                x = random.randint(200, self.w - 200)
                y = random.randint(r, self.h - r)
                position = (x, y)
                valid = True
                if paths.distance(position, self.pad) < r + START_RADIUS + 30:
                    valid = False
                if paths.distance(position, self.star) < r + STAR_RADIUS + 40:
                    valid = False
                for cloud in self.cloud_layout:
                    if paths.distance(position, (cloud["x"], cloud["y"])) < r + cloud["r"] + 15:
                        valid = False
                if valid:
                    self.cloud_layout.append({"x": x, "y": y, "r": r})
                    break
 
        self.base_wind = (
            random.uniform(-wind_strength, wind_strength),
            random.uniform(-wind_strength, wind_strength),
        )
        self.ink_max = INK_FACTOR * paths.distance(self.pad, self.star)
        self.tries = 0
        self.retry()
 
    def retry(self):
        """Same layout, fresh attempt."""
        self.state = "READY"
        self.timer = 0.0
        self.flight_time = 0.0
        self.raw_path = []
        self.path = []
        self.trail = []
        self.plane = physics.make_plane(self.pad[0], self.pad[1])
        self.clouds = []
        for c in self.cloud_layout:
            self.clouds.append({
                "x": float(c["x"]), "y": float(c["y"]), "r": c["r"],
                "vx": 0.0, "vy": 0.0, "base_vx": 0.0, "base_vy": 0.0,
            })
        self.ink = self.ink_max
        self.energy = ENERGY_MAX
        self.flight_points = 0
        self.stroke_active = False
        self.palm_prev = None
        self.gust = None
        self.slowmo = False
        self.hint = ""
        self.hint_timer = 0.0
        self.hazards.reset(self.level, self.w, self.h)
        self.pickups.reset(self.level, self.w, self.h, self.clouds, self.pad, self.star)
 
    def next_level(self):
        self.level += 1
        self.start_level()
 
    # ================= Per-frame update =================
    def update(self, mode, point, dt, *, gesture_input=False):
        self.cursor_mode = mode
        self.cursor_point = point
        effects.update(dt)
        if self.hint_timer > 0:
            self.hint_timer -= dt
 
        # ---- FIST: slow-mo ----
        self.slowmo = False
        if mode == "FIST" and self.energy > 0 and self.state in ("DRAWING", "FLYING"):
            self.slowmo = True
            self.energy -= FIST_COST * dt
        if self.slowmo:
            game_dt = dt * SLOWMO
        else:
            game_dt = dt
 
        # ---- PALM: gust ----
        self.gust = self.read_gust(mode, point, dt)
 
        # ---- Energy regen ----
        if not self.slowmo and self.gust is None:
            self.energy += ENERGY_REGEN * dt
        self.energy = max(0.0, min(ENERGY_MAX, self.energy))
 
        # ---- State machine ----
        if self.state == "READY":
            if mode == "DRAW" and point is not None:
                if paths.distance(point, self.pad) <= START_RADIUS:
                    self.raw_path = [point]
                    self.state = "DRAWING"
                else:
                    self.show_hint("Start your route at the drone")
 
        elif self.state == "DRAWING":
            if mode == "DRAW" and point is not None:
                self.add_ink_point(self.raw_path, point, 3)
            elif mode == "HOVER" and len(self.raw_path) >= MIN_PATH_POINTS:
                self.finish_path()
            # IDLE / FIST / PALM / lost hand: pause, keep the route
 
        elif self.state == "FLYING":
            self.live_draw(mode, point)
            self.update_flight(game_dt)
 
        elif self.state == "LANDED" or self.state == "CRASHED":
            self.timer += dt
            if self.timer >= MESSAGE_TIME:
                if self.state == "LANDED":
                    self.next_level()
                else:
                    self.retry()
 
    def show_hint(self, text):
        self.hint = text
        self.hint_timer = 1.5
 
    # ---------- Ink ----------
    def add_ink_point(self, route, point, min_step):
        """Append point to route if it's far enough from the last one and there's ink left."""
        d = paths.distance(point, route[-1])
        if d < min_step:
            return
        if d > self.ink:
            self.show_hint("Out of ink!")
            return
        self.ink -= d
        route.append(point)
 
    # ---------- Launch ----------
    def finish_path(self):
        if paths.distance(self.raw_path[-1], self.star) <= HAND_FINISH_RADIUS:
            if self.raw_path[-1] != self.star:
                self.raw_path.append(self.star)
        smooth = paths.chaikin(self.raw_path)
        self.path = paths.resample(smooth)
        self.tries += 1
        self.state = "FLYING"
        self.flight_time = 0.0
        self.aim_storms()
 
    def aim_storms(self):
        """Each storm drifts slowly toward a random point in the middle of the route."""
        n = len(self.path)
        for cloud in self.clouds:
            if n < 4:
                break
            tx, ty = self.path[random.randint(n // 4, (3 * n) // 4)]
            dx = tx - cloud["x"]
            dy = ty - cloud["y"]
            d = math.hypot(dx, dy)
            if d < 1:
                continue
            speed = self.storm_speed * random.uniform(0.7, 1.3)
            cloud["base_vx"] = dx / d * speed
            cloud["base_vy"] = dy / d * speed
            cloud["vx"] = cloud["base_vx"]
            cloud["vy"] = cloud["base_vy"]
 
    # ---------- Live redraw during flight ----------
    def live_draw(self, mode, point):
        if mode != "DRAW" or point is None:
            self.stroke_active = False
            return
 
        if self.stroke_active:
            self.add_ink_point(self.path, point, LIVE_SPACING)
            return
 
        drone = (self.plane["x"], self.plane["y"])
        if paths.distance(point, drone) <= REROUTE_RADIUS:
            # Reroute: keep the route up to the drone, then follow the new stroke
            self.path = self.path[:self.plane["i"] + 1]
            if len(self.path) == 0:
                self.path = [drone]
                self.plane["i"] = 0
            self.stroke_active = True
            self.add_ink_point(self.path, point, 0)
        elif len(self.path) > 0 and paths.distance(point, self.path[-1]) <= EXTEND_RADIUS:
            # Extend from the end of the route
            self.stroke_active = True
            self.add_ink_point(self.path, point, 0)
        else:
            self.show_hint("Redraw near the drone or the end of the route")
 
    # ---------- Palm gust ----------
    def read_gust(self, mode, point, dt):
        """Returns (palm_point, (vx, vy)) while the palm sweeps fast enough, else None."""
        if mode != "PALM" or point is None:
            self.palm_prev = None
            return None
        if self.palm_prev is None:
            self.palm_prev = point
            return None
        step = max(dt, 0.001)
        vx = (point[0] - self.palm_prev[0]) / step
        vy = (point[1] - self.palm_prev[1]) / step
        self.palm_prev = point
        if self.state != "FLYING" or self.energy <= 0:
            return None
        if math.hypot(vx, vy) < GUST_MIN_SPEED:
            return None
        self.energy -= PALM_COST * dt
        return (point, (vx, vy))
 
    # ---------- Flight ----------
    def update_flight(self, dt):
        self.flight_time += dt
 
        # Wind = base wind (+ gusts from hazards) + palm push on the drone
        wx, wy = self.hazards.wind(self.base_wind, self.flight_time)
        drone = (self.plane["x"], self.plane["y"])
        if self.gust is not None:
            palm, (gvx, gvy) = self.gust
            if paths.distance(drone, palm) <= GUST_RADIUS:
                wx += gvx * GUST_DRONE_GAIN
                wy += gvy * GUST_DRONE_GAIN
 
        physics.step_plane(self.plane, self.path, (wx, wy), dt)
        self.move_clouds(dt)
        self.hazards.update(dt, self.plane, self.path)
 
        self.trail.append((self.plane["x"], self.plane["y"]))
        if len(self.trail) > 60:
            self.trail.pop(0)
 
        # Stars, combos, near misses
        self.flight_points += self.pickups.update(self.plane, self.clouds)
 
        # Landed?
        position = (self.plane["x"], self.plane["y"])
        if paths.distance(position, self.star) <= STAR_RADIUS:
            self.land()
            return
 
        # Crashed?
        for cloud in self.clouds:
            if paths.distance(position, (cloud["x"], cloud["y"])) <= cloud["r"]:
                self.crash()
                return
        if self.hazards.crashed(self.plane):
            self.crash()
            return
        margin = 30
        if not (-margin <= position[0] <= self.w + margin and -margin <= position[1] <= self.h + margin):
            self.crash()
 
    def move_clouds(self, dt):
        for cloud in self.clouds:
            # Palm push: blend the cloud's velocity toward the sweep
            if self.gust is not None:
                palm, (gvx, gvy) = self.gust
                if paths.distance(palm, (cloud["x"], cloud["y"])) <= GUST_RADIUS + cloud["r"]:
                    blend = min(1.0, GUST_CLOUD_BLEND * dt)
                    cloud["vx"] += (gvx * GUST_CLOUD_GAIN - cloud["vx"]) * blend
                    cloud["vy"] += (gvy * GUST_CLOUD_GAIN - cloud["vy"]) * blend
                    effects.puff(cloud["x"], cloud["y"])
 
            # Settle back toward the storm's own drift
            settle = min(1.0, CLOUD_FRICTION * dt)
            cloud["vx"] += (cloud["base_vx"] - cloud["vx"]) * settle
            cloud["vy"] += (cloud["base_vy"] - cloud["vy"]) * settle
 
            # Speed cap
            speed = math.hypot(cloud["vx"], cloud["vy"])
            if speed > MAX_CLOUD_SPEED:
                cloud["vx"] *= MAX_CLOUD_SPEED / speed
                cloud["vy"] *= MAX_CLOUD_SPEED / speed
 
            cloud["x"] += cloud["vx"] * dt
            cloud["y"] += cloud["vy"] * dt
 
            # Bounce off the screen edges so storms stay in play
            if cloud["x"] < cloud["r"] or cloud["x"] > self.w - cloud["r"]:
                cloud["vx"] = -cloud["vx"]
                cloud["base_vx"] = -cloud["base_vx"]
                cloud["x"] = min(max(cloud["x"], cloud["r"]), self.w - cloud["r"])
            if cloud["y"] < cloud["r"] or cloud["y"] > self.h - cloud["r"]:
                cloud["vy"] = -cloud["vy"]
                cloud["base_vy"] = -cloud["base_vy"]
                cloud["y"] = min(max(cloud["y"], cloud["r"]), self.h - cloud["r"])
 
    def land(self):
        self.state = "LANDED"
        self.timer = 0.0
        bonus = 500 + int(self.ink * 0.5) + int(self.energy * 2)
        earned = bonus + self.flight_points
        self.score += earned
        effects.popup(f"+{earned}", self.star[0] - 40, self.star[1] - 40)
        effects.flash()
 
    def crash(self):
        self.state = "CRASHED"
        self.timer = 0.0
        effects.shake(15)
        effects.puff(self.plane["x"], self.plane["y"])
 
    # ================= Drawing =================
    def draw(self, frame):
        import visuals
 
        img = self.sky.copy()
 
        visuals.draw_pad(img, self.pad[0], self.pad[1])
        visuals.draw_star(img, self.star[0], self.star[1], STAR_RADIUS)
        for cloud in self.clouds:
            visuals.draw_cloud(img, cloud["x"], cloud["y"], cloud["r"])
        self.hazards.draw(img)
        self.pickups.draw(img)
 
        if self.state == "DRAWING":
            preview = paths.resample(paths.chaikin(self.raw_path))
            visuals.draw_path(img, preview)
        elif self.state == "FLYING":
            visuals.draw_path(img, self.path, (230, 230, 230), 2)
 
        visuals.draw_trail(img, self.trail)
        visuals.draw_plane(img, self.plane["x"], self.plane["y"], self.plane["heading"])
 
        if self.show_autopilot:
            visuals.draw_autopilot(img, (self.plane["x"], self.plane["y"]), self.plane["target"])
 
        visuals.draw_hud(img, self.level, self.score, self.tries, self.base_wind)
        effects.draw_bars(img, self.ink / max(self.ink_max, 1), self.energy / ENERGY_MAX)
        visuals.draw_camera_inset(img, frame)
 
        if self.slowmo:
            effects.slowmo_tint(img)
 
        if self.state == "READY":
            visuals.draw_message(img, "Point to draw a route from the drone - peace sign to launch", 0.9)
        elif self.state == "LANDED":
            visuals.draw_message(img, "DELIVERED!")
        elif self.state == "CRASHED":
            visuals.draw_message(img, "ROUTE FAILED")
        if self.hint_timer > 0 and self.hint:
            visuals.draw_text(img, self.hint, self.w // 2 - 220, self.h - 60, 0.8)
 
        # Cursor for the current tool
        if self.cursor_mode == "PALM":
            effects.draw_palm_cursor(img, self.cursor_point, GUST_RADIUS, self.gust is not None)
        elif self.cursor_mode == "FIST":
            effects.draw_fist_cursor(img, self.cursor_point)
        else:
            visuals.draw_cursor(img, self.cursor_mode, self.cursor_point)
 
        return effects.apply(img)
 