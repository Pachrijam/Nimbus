"""
Flight Path game: state machine, levels, collisions, score.
Owner: Person 3 (calls physics.py from Avyay and visuals.py from Paul)
 
States:  READY -> DRAWING -> FLYING -> LANDED  -> next level
                                   -> CRASHED -> retry
"""
import random
 
import flight_sim
import gemini_agent
import paths
import physics
 
START_RADIUS = 90        # px: the path must start this close to the plane
STAR_RADIUS = flight_sim.STAR_RADIUS
HAND_FINISH_RADIUS = 60  # px: snap a nearby hand-drawn endpoint to the star
MIN_PATH_POINTS = 10     # ignore accidental tiny paths
MESSAGE_TIME = 2.0       # seconds to show LANDED / CRASHED before moving on
PAD_MARGIN = 90          # px from the left edge
MAX_CLOUDS = 6
CLOUD_RADIUS = 45
DRAWING_PAUSE_TIME = 0.3  # seconds allowed for a brief tracking dropout
SCREEN_MARGIN = flight_sim.SCREEN_MARGIN
MIN_POINT_DISTANCE = 3
MAX_TRAIL_POINTS = 60
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
        if self.level == 1:
            self.star = (self.w - 120, self.h // 2)
        else:
            self.star = (self.w - 120, random.randint(120, self.h - 120))
        # Increase difficulty with each level.
        if self.level == 1:
            num_clouds = 1
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
 
        self.cloud_layout = []
        if self.level == 1:
            # A fixed first level makes learning and testing repeatable.
            self.cloud_layout.append({
                "x": self.w // 2,
                "y": self.h // 2,
                "r": CLOUD_RADIUS,
                "vx": 0.0
            })
 
        # Later levels use random positions.
        for i in range(num_clouds - len(self.cloud_layout)):
            for attempt in range(100):
                r = CLOUD_RADIUS
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
        self.level_score = 0
        self.best_time = None
        self.benchmark_job = None
        self.retry()
 
    def retry(self):
        """Same layout, fresh attempt."""
        self.state = "READY"
        self.timer = 0.0
        self.raw_path = []
        self.drawing_pause = 0.0
        self.path = []
        self.trail = []
        self.trajectory = [self.pad]
        self.flight_ticks = 0
        self.flight_distance = 0.0
        self.flight_accumulator = 0.0
        self.plane = physics.make_plane(self.pad[0], self.pad[1])
        self.clouds = [dict(c) for c in self.cloud_layout]   # copies, so drifting doesn't change the layout
 
    def next_level(self):
        self.level += 1
        self.start_level()
 
    # ---------- Per-frame update ----------
    def update(self, mode, point, dt, *, gesture_input=False):
        self.cursor_mode = mode
        self.cursor_point = point
 
        if self.state == "READY":
            if mode == "DRAW" and point is not None:
                drone_position = (self.plane["x"], self.plane["y"])
 
                if paths.distance(point, drone_position) <= START_RADIUS:
                    self.raw_path = [drone_position]
 
                    if point != drone_position:
                        self.raw_path.append(point)
 
                    self.state = "DRAWING"
 
        elif self.state == "DRAWING":
            if mode == "DRAW" and point is not None:
                self.drawing_pause = 0.0
                if paths.distance(point, self.raw_path[-1]) >= MIN_POINT_DISTANCE:
                    self.raw_path.append(point)
                if (gesture_input and len(self.raw_path) >= MIN_PATH_POINTS and
                        paths.distance(point, self.star) <= STAR_RADIUS):
                    if self.raw_path[-1] != self.star:
                        self.raw_path.append(self.star)
                    self.finish_path()
            elif (gesture_input and mode == "HOVER" and point is not None
                  and len(self.raw_path) >= MIN_PATH_POINTS):
                # Use the drawn endpoint, not finger movement during release.
                if (self.raw_path[-1] != self.star
                        and paths.distance(self.raw_path[-1], self.star) <= HAND_FINISH_RADIUS):
                    self.raw_path.append(self.star)
                self.finish_path()
            elif gesture_input:
                self.drawing_pause += dt
            else:
                self.finish_path()
 
        elif self.state == "FLYING":
            self.update_flight(dt)
 
        elif self.state == "CRASHED":
            self.timer += dt
            if self.timer >= MESSAGE_TIME:
                self.retry()
        # Successful flights stay visible until the player chooses retry or next.
 
    def finish_path(self):
        if len(self.raw_path) < MIN_PATH_POINTS:
            self.retry()
            return
        smooth = paths.chaikin(self.raw_path)
        self.path = paths.resample(smooth)
        self.tries += 1
        self.state = "FLYING"
 
    def update_flight(self, dt):
        self.flight_accumulator += dt
        while self.flight_accumulator + 1e-12 >= flight_sim.STEP and self.state == "FLYING":
            self.flight_accumulator -= flight_sim.STEP
            self.state = flight_sim.advance(self.plane, self.path, self.wind, self.clouds,
                                            self.star, self.w, self.h)
            self.flight_ticks += 1
            position = (self.plane["x"], self.plane["y"])
            self.flight_distance += paths.distance(self.trajectory[-1], position)
            self.trajectory.append(position)
            self.trail.append(position)
            if len(self.trail) > MAX_TRAIL_POINTS:
                self.trail.pop(0)
            if self.state != "FLYING":
                self.timer = 0.0
                if self.state == "LANDED":
                    self.complete_delivery()

    def level_layout(self):
        """Detached launch conditions; camera and player input never go to Gemini."""
        return {"width": self.w, "height": self.h, "pad": self.pad, "star": self.star,
                "wind": self.wind, "clouds": [dict(c) for c in self.cloud_layout]}

    def complete_delivery(self):
        elapsed = self.flight_ticks * flight_sim.STEP
        self.best_time = min(self.best_time, elapsed) if self.best_time is not None else elapsed
        # Award a level only once; rematches improve the time record without farming points.
        if not self.level_score:
            base_score = max(0, 1000 - 200 * (self.tries - 1))
            route_length = paths.path_length(self.path)
            direct_length = paths.distance(self.pad, self.star)
            efficiency = min(1.0, direct_length / max(route_length, 1))
            self.level_score = base_score + int(efficiency * 200)
            self.score += self.level_score
        if self.benchmark_job is None:
            self.benchmark_job = gemini_agent.BenchmarkJob(self.level_layout())

    def comparison(self):
        if self.state != "LANDED":
            return None
        elapsed = self.flight_ticks * flight_sim.STEP
        result = {"playerTime": elapsed, "playerDistance": self.flight_distance,
                  "bestTime": self.best_time, "status": "pending"}
        if self.benchmark_job is None or not self.benchmark_job.done.is_set():
            return {**result, "message": "Gemini is planning and testing its routes..."}
        benchmark = self.benchmark_job.result
        result.update({"status": benchmark["status"], "message": benchmark.get("message", "")})
        if benchmark["status"] == "ready":
            ratio = benchmark["time"] / max(elapsed, flight_sim.STEP)
            delta = elapsed - benchmark["time"]
            verdict = "beat" if delta < -flight_sim.STEP / 2 else "matched" if ratio >= 0.95 else "chasing"
            result.update({"aiTime": benchmark["time"], "aiDistance": benchmark["distance"],
                           "matchPercent": round(100 * ratio, 1), "timeDelta": delta,
                           "verdict": verdict, "model": benchmark["model"],
                           "tested": benchmark["tested"],
                           "planner": benchmark.get("planner", "gemini"),
                           "refined": benchmark.get("refined", 0),
                           "aiTrajectory": [{"x": x, "y": y} for x, y in benchmark["trajectory"]]})
        return result
 
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
        elif self.state == "LANDED":
            visuals.draw_path(img, self.trajectory, (40, 120, 230), 3)
            result = self.comparison()
            if result["status"] == "ready":
                ai_path = [(p["x"], p["y"]) for p in result["aiTrajectory"]]
                visuals.draw_path(img, ai_path, (170, 80, 100), 2)
 
        visuals.draw_trail(img, self.trail)
        visuals.draw_plane(img, self.plane["x"], self.plane["y"], self.plane["heading"])
 
        if self.show_autopilot:
            visuals.draw_autopilot(img, (self.plane["x"], self.plane["y"]), self.plane["target"])
 
        visuals.draw_hud(img, self.level, self.score, self.tries, self.wind)
        visuals.draw_camera_inset(img, frame)
 
        if self.state == "READY":
            visuals.draw_message(img, "Draw a route from the drone to the destination", 1.0)
        elif self.state == "LANDED":
            result = self.comparison()
            if result["status"] == "ready":
                message = f"Gemini match: {result['matchPercent']:.0f}% | R: retry  N: next"
            elif result["status"] == "pending":
                message = "Delivered! Gemini planning... R: retry  N: next"
            elif result["status"] == "disabled":
                message = "Delivered! R: retry  N: next"
            else:
                message = "Delivered! AI unavailable. R: retry  N: next"
            visuals.draw_message(img, message, 0.6)
        elif self.state == "CRASHED":
            visuals.draw_message(img, "ROUTE FAILED")
 
        visuals.draw_cursor(img, self.cursor_mode, self.cursor_point)
        return img
