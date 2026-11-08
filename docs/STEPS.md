# STEPS: exactly what to do, in order

Check items off as you go. Times are targets, not suggestions.

---

## 0. Right now (11:00–11:20): everyone

### Avyay (repo owner)
1. Put these files in `C:\Users\Avyay\aircanvas\` next to `hand_landmarker.task`:
   `main.py, gestures.py, physics.py, game.py, paths.py, visuals.py, freedraw.py, requirements.txt, .gitignore, README.md, OVERVIEW.md, STEPS.md`
2. **Delete last night's test `main.py`** first if it's still there (the new one replaces it).
3. On github.com: **New repository** → name `aircanvas` → **Public** → do NOT add a README → Create.
4. In the VS Code terminal (`PS C:\Users\Avyay\aircanvas>`):
   ```
   git init
   git add .
   git commit -m "Starter structure"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/aircanvas.git
   git push -u origin main
   ```
5. On GitHub: **Settings → Collaborators → Add people** → add Paul and Harry.

### Paul and Harry
1. Accept the GitHub invite (email or github.com notifications).
2. In a terminal, in the folder where you want the project:
   ```
   git clone https://github.com/AVYAY-USERNAME/aircanvas.git
   cd aircanvas
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```
   For hand tracking, also run `python -m pip install mediapipe` in the activated environment.
3. Open the folder in VS Code (**File → Open Folder**). Select the `.venv` interpreter (**Ctrl+Shift+P → Python: Select Interpreter**).

### Everyone: the 2-minute test
```
python main.py
```
- [ ] A sky scene with a cloud, a destination and a drone (triangle); your camera in the top-right corner
- [ ] `p` switches to Free Draw (your camera) and back
- [ ] `m` turns mouse mode on (debug line says `mouse=True`)
- [ ] `q` quits

If it fails: see **Troubleshooting** at the bottom.

### Everyone: read OVERVIEW.md sections "Architecture" and "Interfaces" (5 min)
These are the agreements between files. Nobody changes them without telling the team.

---

## 1. The git routine (all day, everyone)
**Before starting work, and every ~30 min:**
```
git pull
```
**Every time something works:**
```
git add .
git commit -m "What you just got working"
git pull
git push
```
- Edit **only your own files** (see OVERVIEW.md). `main.py` changes get announced first.
- If `git pull` reports a **merge conflict**: stop, tell the team, fix it together.

---

## 2. Avyay

### Gestures (`gestures.py`), 11:20 → ~2:00
| # | Step | Done when |
|---|---|---|
| 1 | Print `landmarks[8].y` and `landmarks[6].y` every frame; raise and lower your finger | You can see: finger up means tip y is **smaller** |
| 2 | `index_up`, `middle_up` booleans | Debug line shows the right mode as you change your hand |
| 3 | Raw mode: index only → `DRAW`, two or more fingers → `HOVER`, else `IDLE` | Modes switch correctly |
| 4 | Debounce with `state["candidate"]` / `state["count"]` / `DEBOUNCE_FRAMES` | No flicker when your hand is still |
| 5 | Smoothing with `state["smooth"]`, `SMOOTHING` | Cursor moves smoothly; no jitter when your hand is still |
| 6 | Reset `state["smooth"] = None` when no hand; first frame back sets smooth = raw | No line glides in from the old position |
| 7 | **Commit + push.** Tell Harry and Paul: "hand input ready" | They can turn mouse mode off |

### Physics (`physics.py` → `step_pursuit`), ~2:00 → 6:30
Test with mouse mode in the game. **Each step: run, watch, commit.**
| # | Step | Done when |
|---|---|---|
| 1 | Straight flight (placeholder already does this) | Drone crosses the screen at a steady speed |
| 2 | **Chase test:** temporarily set the target = mouse position (pass it in for testing), then steps C, D, E | Drone curves smoothly toward the cursor and chases it |
| 3 | Clamp `±MAX_TURN` | Cursor behind the drone means a wide turn, not a snap |
| 4 | Step A: progress index `i`, forward search only (`SEARCH_WINDOW`) | `i` increases steadily during flight (print it) |
| 5 | Step B: look-ahead target ≥ `LOOKAHEAD` px; store `plane["target"]` | `v` (autopilot view) shows a red dot leading the drone along the path |
| 6 | After the last point: stop steering, fly straight | Drone continues past a short path instead of spinning |
| 7 | Wind is already in the movement; set `self.wind = (30, 0)` in `game.py` to test | Drone drifts but keeps correcting back to the path |
| 8 | Tune `LOOKAHEAD`, `K_STEER`, `MAX_TURN` (table in OVERVIEW.md) | Smooth curves, no oscillation, hairpins fail |
| 9 | Test `USE_PHYSICS = False` once Harry's `step_exact` exists | Fallback works |

### Help others: 6:30 → 7:30
Tune difficulty with Harry, test gestures in bad lighting, fix bugs.

---

## 3. Paul

### Free draw (`freedraw.py`), 11:20 → ~12:15
| # | Step | Done when |
|---|---|---|
| 1 | `update`: in DRAW with a point, `cv2.line(self.ink, prev, point, color, thickness, cv2.LINE_AA)`; then prev = point. Otherwise prev = None | Works with mouse mode (`m`) in free draw (`p`) |
| 2 | `draw`: mask = grayscale(ink) > 0; output = frame where no ink, ink where ink | Ink shows over the camera |
| 3 | Commit + push | |

### Visuals (`visuals.py`), ~12:15 → 7:30, one function at a time, commit after each
| # | Function | Target look |
|---|---|---|
| 1 | `make_sky` | Vertical gradient `SKY_TOP` → `SKY_BOTTOM` |
| 2 | `draw_cloud` | Storm cell: 5–7 overlapping circles, grey-white, slight dark shadow; must roughly fill radius `r` |
| 3 | `draw_plane` | Drone/paper-plane shape that clearly shows its heading |
| 4 | `draw_star` | Destination marker (5-point star or landing pad), pulsing |
| 5 | `draw_route` | Each segment white, **red where `tight_flags` is True** (impossible turn) |
| 6 | `draw_trail` | Fading contrail (older points thinner/lighter) |
| 7 | `draw_hud` | Clean panel: level, score, tries, wind arrow + speed |
| 8 | Crash effect | Spin + puff at the crash point for ~1 s (add a function; ask Harry to call it) |
| 9 | Delivered effect | Flash/ring at the destination |
| 10 | Wind streaks | Faint lines drifting in the wind direction |
| 11 | Title screen text + level banner | "Level 3: Gusty" style |

---

## 4. Harry

### Game core (`game.py` + `paths.py`), 11:20 → 3:30, **mouse mode the whole time**
| # | Step | Done when |
|---|---|---|
| 1 | READY → DRAWING: DRAW near the drone (`START_RADIUS`) starts `raw_path = [point]` | Pressing the mouse on the drone starts a path |
| 2 | DRAWING: append points (skip if < 3 px from the last); leaving DRAW calls `finish_path()` | A white path follows the mouse; releasing launches |
| 3 | `paths.path_length` | Prints a sensible length |
| 4 | `paths.chaikin` (25% / 75% points, keep the ends, 2 iterations) | Drawn paths look smooth |
| 5 | `paths.resample` (every 8 px) | Points are evenly spaced (print the distances) |
| 6 | `physics.step_exact` (fallback flight along the path) | With `USE_PHYSICS = False`, the drone follows the path exactly |
| 7 | Collisions in `update_flight`: destination → LANDED, cloud → CRASHED, off-screen → CRASHED | All three happen correctly |
| 8 | LANDED / CRASHED: after `MESSAGE_TIME` → `next_level()` / `retry()` | Full loop works |
| 9 | **Commit + push** | |

### Game depth, 3:30 → 7:30
| # | Step |
|---|---|
| 10 | `paths.find_tight_turns` (circle-through-3-points radius vs `min_radius`) → red segments while drawing |
| 11 | Random layouts in `start_level`: clouds never on the pad/destination, never overlapping |
| 12 | Difficulty per level: more clouds, `vx` drift, stronger `self.wind` |
| 13 | Score: `1000 − 200 × (tries − 1)` + short-path bonus via `path_length` |
| 14 | Hint when the path starts away from the drone ("Start your route at the drone") |

### Devpost (7:30 onward), see Section 7.

---

## 5. Checkpoints (everyone stops for 5 minutes)

### 1:30
- [ ] Hand modes work (Avyay) · Free draw works (Paul) · Game loop works with the mouse (Harry)
- If any is badly behind: the others help it **now**.

### 3:30 (critical)
- [ ] Turn mouse mode OFF: **full game playable with your hand**
- [ ] **Record a backup demo video now** (Windows: **Win + Alt + R** starts/stops recording the window via Xbox Game Bar; or film the screen with a phone)
- [ ] Commit + push everything
- If the hand-controlled game isn't working: **all three fix that before any new feature.**

### 6:30
- [ ] Physics on, levels on, visuals mostly in. Decide what is NOT going to make it.

### 7:30: FEATURE FREEZE
- [ ] No new features. Bug fixes only.
- [ ] Pick the final tuning values and commit them.

---

## 6. Saturday 7:30 → 9:00
1. **Test in the Great Hall** (the actual demo room): lighting, distance from the camera, 5 full games.
2. Fix the worst bug found. Commit.
3. **Record the final demo video** (1–2 min): free draw → a successful delivery → a red too-tight turn → a failed route → autopilot view (`v`).
4. Harry: Devpost draft (Section 7).
5. Everyone: `git pull`, confirm the latest version runs on **all three laptops**.
6. Agree on Sunday: who arrives at 5:00, which extras to try.

---

## 7. Devpost (Harry drafts Saturday, final Sunday by 8:45)
1. devpost.com → HackRPI 2026 → **Register / Join** → **Create project**; add teammates.
2. Fill in (text from OVERVIEW.md):
   - **Tagline:** "Sketch a drone route in the air. Physics tells you if it can fly it."
   - **Inspiration / What it does / How we built it / Challenges / Accomplishments / What we learned / What's next**
   - **Built with:** python, opencv, mediapipe, numpy
   - **Links:** GitHub repo; demo video (upload to YouTube as Unlisted)
   - **Screenshots:** 3–4 (sky with route, red tight turn, delivered, autopilot view)
3. Submit by **8:45 Sunday** (deadline 9:00).

---

## 8. Sunday 5:00 → 11:00
1. 5:00: `git pull`, run it, then create a branch for extras:
   ```
   git checkout -b extras
   ```
2. Work on extras ONLY (gusts, wind streaks, tutorial level, leaderboard). Commit on the branch.
3. **8:00 decision:**
   - Works → `git checkout main`, `git merge extras`, `git push`
   - Doesn't → `git checkout main` (the branch is abandoned; main is untouched)
4. **8:45: Devpost submitted.**
5. 9:00–11:00: practice the 60-second pitch 5+ times; each person can explain their part in one sentence.
6. Showcase: laptop charged, fullscreen (`f`), debug text off (`d`), good lighting on your hand.

---

## Troubleshooting
| Problem | Fix |
|---|---|
| `No module named cv2` | Activate the project virtual environment and run `python -m pip install -r requirements.txt` |
| Hand tracking unavailable | Activate the project virtual environment and run `python -m pip install mediapipe`; confirm `hand_landmarker.task` is beside `main.py` |
| Camera window black / camera fails | Close Zoom/Teams/Camera app; Settings → Privacy & security → Camera → allow desktop apps |
| `hand_landmarker.task` not found | Run `python main.py` **from inside** the `aircanvas` folder |
| FPS under ~20 | In `main.py`, set `CAM_WIDTH = 640`, `CAM_HEIGHT = 480` |
| Hand tracking flaky | More light on your hand, nothing bright behind you, hand 1–3 ft from the camera |
| Drone spins in circles | Missing `wrap_angle` on the heading error |
| Drone wobbles side to side | Raise `LOOKAHEAD` or lower `K_STEER` |
| Stuck 20+ minutes | Mentoring desk, Great Hall |
