# OVERVIEW: Nimbus Flight Path

**HackRPI 2026 · Theme: "In The Clouds" · Team: Avyay, Paul, Person 3**

> **Sketch a drone's route in the air with one finger. A physics simulation instantly shows whether the drone can actually fly it through the wind and around the storms.**

---

## 1. The problem
Planning a route for a drone (deliveries, inspections, search and rescue) means getting around **storm cells and no-fly zones** while respecting what the aircraft can physically do: a **minimum turning radius** and **drift from wind**. Routes are usually planned by clicking waypoints on map software, with no instant, visual feedback on whether the drone can truly fly the line you drew. A route that looks fine on a map can contain a turn the aircraft physically can't make.

## 2. Our solution
A touchless, webcam-only route planner and simulator:
1. **Sketch** the route in the air with your index finger. No mouse, touchscreen or hardware.
2. **See infeasible turns immediately:** any part of the route tighter than the drone's minimum turn radius turns **red** while you draw.
3. **Launch** the route. A simulated drone flies it under **real path-following control** (pure pursuit) with a **turn-rate limit** and **wind**.
4. **Outcome:** **DELIVERED** at the destination, or **ROUTE FAILED** (hit a storm cell, swung wide on a turn too tight, or blown off course).

A **game layer** (levels, score, increasing difficulty) makes it fun and turns it into a training simulator, like a flight simulator for route planning.

**Honest scope:** a proof of concept. The physics is a simplified 2D model and the "map" is a sky scene. A real version would use real maps, drone specifications and weather data.

## 3. Pitch (memorize)
*"Draw a drone's route in the air. Our physics engine, using pure pursuit (the same path-following algorithm real robots use), tells you instantly whether the drone can actually fly it through the wind and around the storms. Turns it can't make light up red before you even launch."*

---

## 4. User experience (walkthrough)
1. The screen shows a **sky** with a **drone** on a launch pad (left), **storm cells** (clouds) in between, a **destination** (right), a **wind arrow** in the HUD, and a small **live camera view** in the top-right corner.
2. The user raises their **index finger** near the drone and draws a route. The route is **smoothed live**; any too-tight turn shows **red**.
3. The user raises **two fingers** to release, and the drone **launches**.
4. The drone follows the route, **banking smoothly**, **drifting in wind** and **correcting back**. Storm cells may **drift** across the route mid-flight.
5. **DELIVERED!** shows the score, then the next level. Or **ROUTE FAILED** with a crash effect, then a retry of the same layout.
6. Press `v` for the **autopilot view**: a red dot shows exactly where the controller is aiming.
7. Press `p` for **Free Draw**: simple air drawing over the camera (warm-up and backup demo).

### Gestures
| Hand | Mode | Effect |
|---|---|---|
| ☝ index finger up | `DRAW` | draw route / ink |
| ✌ index + middle up | `HOVER` | move without drawing; **releases the route** |
| other / no hand | `IDLE` | nothing |

### Keys
`q` quit · `p` Free Draw/Game · `f` fullscreen · `r` retry · `n` next level · `v` autopilot view · `c` clear ink · `d` debug text

---

## 5. Game states
```
READY ──(DRAW near drone)──> DRAWING ──(leave DRAW)──> FLYING ──(reach destination)──> LANDED ──(2 s)──> next level
  ^                              │                         └──(cloud / off-screen)──> CRASHED ──(2 s)──> retry
  └──────(path < 10 points)──────┘
```
| State | Behavior | Message |
|---|---|---|
| READY | Scene shown; drone on pad | "Draw a route from the drone to the destination" |
| DRAWING | Points recorded; live smoothed preview with red tight turns | (none) |
| FLYING | Physics runs; clouds drift; contrail | (none) |
| LANDED | Score added | "DELIVERED!" |
| CRASHED | Crash effect | "ROUTE FAILED" |

Rules: the route must start within **40 px** of the drone; routes under **10 points** are ignored; LANDED/CRASHED show for **2 s**.

---

## 6. The technology (how each part works)

### 6.1 Hand tracking (`main.py`, MediaPipe)
- Webcam frame (BGR) → mirrored → converted to RGB → **MediaPipe HandLandmarker** in VIDEO mode → **21 landmarks**, normalized 0–1.
- A real clock (`time.monotonic`) supplies increasing timestamps for MediaPipe and **`dt`** (seconds per frame, capped at 0.05) for physics.

### 6.2 Gesture recognition (`gestures.py`)
- **Finger up:** fingertip y < middle-joint y (screen y grows downward). Index 8 vs 6; middle 12 vs 10.
- **Debouncing:** a new mode must hold **3 consecutive frames** (about 0.1 s) to take effect. A small state machine (`mode`, `candidate`, `count`).
- **Smoothing:** exponential moving average, `smooth = 0.4 · raw + 0.6 · smooth`, a first-order low-pass filter. Reset when the hand reappears.

### 6.3 Path processing (`paths.py`)
1. **Chaikin smoothing** (2 iterations): each segment P→Q becomes points at 25% and 75%; endpoints kept. Turns a jagged hand path into a smooth curve.
2. **Resampling:** evenly spaced points every **8 px**, so speed and curvature are measured consistently.
3. **Feasibility check:** at each interior point b (with neighbors a, c), the radius of the circle through a, b, c is
   **R = |ab| · |bc| · |ca| / (4 · Area)**, where Area = |cross(b − a, c − a)| / 2.
   If **R < R_min = SPEED / MAX_TURN = 180 / 2.5 = 72 px**, that point is **infeasible** and drawn red.

### 6.4 Flight physics (`physics.py`): pure pursuit
Drone state: `x, y` (px), `heading` (rad), `speed` = 180 px/s, progress index `i`, `target`.
Each frame:
1. **Progress:** closest path point, searching **forward only** (20 points), so a self-crossing path can't skip ahead.
2. **Look-ahead target:** the first path point ≥ **60 px** from the drone (else the last point).
3. **Desired heading:** `atan2(ty − y, tx − x)`.
4. **Heading error:** `wrap(desired − heading)` into [−π, π], so the drone turns the short way.
5. **Steering:** `turn = 4.0 · error` (proportional control), **clamped to ±2.5 rad/s**; `heading += turn · dt`.
6. **Motion:** `x += (speed · cos(heading) + wind_x) · dt`, and the same for y.
7. **Past the final point:** no steering; fly straight.

**Minimum turn radius = speed / max turn rate = 72 px.** Turns tighter than that physically fail.
**Safety switch:** `USE_PHYSICS = False` means exact path following (no physics), for demo emergencies.

| Parameter | Value | Too low | Too high |
|---|---|---|---|
| `SPEED` | 180 px/s | boring | no time to react |
| `LOOKAHEAD` | 60 px | wobble | cuts corners |
| `K_STEER` | 4.0 | sluggish | overshoot/oscillation |
| `MAX_TURN` | 2.5 rad/s | can't turn | unrealistic |

### 6.5 Collisions and scoring (`game.py`)
- Drone within **28 px** of the destination → LANDED. Within a cloud's radius → CRASHED. Off-screen (with margin) → CRASHED.
- **Score** = 1000 − 200 × (tries − 1) + short-route bonus (from `path_length`).

### 6.6 Levels (`game.py`)
| Level | Clouds | Cloud drift | Wind |
|---|---|---|---|
| 1 | 1–2 | none | none |
| 2 | 3 | none | light |
| 3 | 4 | slow | light |
| 4 | 5 | medium | medium |
| 5+ | +1 each | faster | stronger, random direction |
Clouds are placed randomly but never on the pad or the destination, and never overlapping. Retry restores the **same** layout.

### 6.7 Visual design (`visuals.py`)
Sky gradient; storm cells as clustered circles with shadow; a drone/paper-plane shape showing heading; a pulsing destination; a route preview (white, red where infeasible); a fading contrail; crash puff and spin; delivery flash; wind arrow + drifting wind streaks; HUD panel; camera inset; cursor (solid dot = drawing, ring = hovering); autopilot view (red look-ahead dot + line).

### 6.8 Free Draw (`freedraw.py`)
A persistent ink layer (NumPy image) over the mirrored camera; lines drawn from the previous point to the current one; ink combined with the camera via a mask. One color, `c` clears.

---

## 7. Architecture
```
webcam ─> main.py ─> MediaPipe ─> gestures.get_gesture() ─> (mode, point)
                                                                  │
                     ┌────────────────────────────────────────────┴──────────────┐
                     v                                                           v
             freedraw.FreeDraw                                            game.Game
             update / draw                     update(mode, point, dt) / draw(frame)
                                                 │            │             │
                                             paths.py     physics.py     visuals.py
                                    (smooth, resample,  (step_plane:   (everything
                                     feasibility)        pure pursuit)   on screen)
```

### Files and owners
| File | Owner | Responsibility |
|---|---|---|
| `main.py` | shared (announce changes) | camera, MediaPipe, clock, input, keys, mode switching |
| `gestures.py` | **Avyay** | finger-up checks, debouncing, smoothing |
| `physics.py` | **Avyay** (`step_exact`: Person 3) | pure pursuit, turn limit, wind |
| `freedraw.py` | **Paul** | free-draw mode |
| `visuals.py` | **Paul** | all rendering and effects |
| `game.py` | **Person 3** | states, collisions, levels, score |
| `paths.py` | **Person 3** | Chaikin, resampling, path length, feasibility check |

### Interfaces (do not change without telling the team)
- `get_gesture(landmarks, w, h) -> (mode, point)`: mode is `"DRAW"`, `"HOVER"` or `"IDLE"`; point is `(x, y)` ints or `None`.
- A **path** is a list of `(x, y)` tuples.
- A **plane** is a dict: `x, y, heading, speed, i, target`.
- `physics.step_plane(plane, path, wind, dt)` updates `plane` in place.
- `paths.find_tight_turns(points, min_radius) -> list of bool` (same length as points).
- `visuals.*(img, ...)` draw onto `img` in place.
- `Game.update(mode, point, dt)`, `Game.draw(frame) -> image`, `Game.retry()`, `Game.next_level()`.

---

## 8. Scope tiers and odds (estimates)
| Tier | Contents | Odds |
|---|---|---|
| **Core** | Gestures + game loop with hand input + collisions + free draw | ~90% |
| **Expected** | + Chaikin/resampling, levels, drift, score, real visuals, red infeasible turns | ~80% |
| **Best case (target)** | + pure pursuit physics with wind, autopilot view, polished effects | ~70% |
| **Sunday extras** (branch) | wind gusts, wind streaks, tutorial level, leaderboard | partial |
| **Cut** | toolbar/colors/brush sizes, palm eraser, shape snapping, undo, two-player | — |

---

## 9. Demo (60 seconds)
1. **(10 s)** Free Draw: write a word in the air. "Any laptop webcam, no hardware."
2. **(15 s)** Game: sketch a route around the storm cells, release: **DELIVERED**.
3. **(15 s)** Sketch a hairpin: it turns **red** while drawing; launch anyway: the drone swings wide: **ROUTE FAILED**. "Minimum turn radius 72 px. Physics wins."
4. **(10 s)** Press `v`: "Pure pursuit. The red dot is where the autopilot aims, the same method used in real robots and self-driving vehicles."
5. **(10 s)** "Next: a real robot that follows routes you draw in the air." Hand the judge the controls.

### Talking points for technical judges
- First-order low-pass filter on the fingertip; debounced gesture state machine.
- Chaikin corner-cutting and arc-length resampling.
- Circumradius-based curvature check against the kinematic turn limit (R_min = v / ω_max).
- Pure pursuit with heading-error wrapping and saturated proportional steering; frame-rate-independent `dt` physics.

### Known limitations (say them before judges find them)
- 2D model only; no altitude, battery or real aerodynamics.
- Hand tracking needs decent lighting; a tilted hand can confuse the finger-up check.
- Sky scene instead of real maps.

## 10. What's next (freshman year)
Robust tracking → saving routes as data → a **physical robot (XY plotter or small drone/rover) that follows routes sketched in the air**, live, with latency compensation.
