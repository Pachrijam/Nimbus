# AirCanvas: Flight Path (HackRPI 2026)

**Sketch a drone's route in the air with one finger. A physics simulation instantly shows whether the drone can actually fly it through the wind and around the storms.**

## Run
```
python -m pip install -r requirements.txt
python main.py
```
For hand tracking, put `hand_landmarker.task` in this folder. If it is missing or MediaPipe Tasks is unavailable, the app starts in mouse mode: move the cursor and hold the left mouse button to draw.

Keys: `q` quit · `p` Free Draw/Game · `m` mouse mode · `f` fullscreen · `r` retry · `n` next level · `v` autopilot view · `c` clear · `d` debug

## Docs
- **[OVERVIEW.md](OVERVIEW.md):** the full project: problem, solution, tech, architecture, interfaces, demo
- **[STEPS.md](STEPS.md):** exactly what each person does, in order, with checkpoints

## Credits
Hand tracking: Google MediaPipe HandLandmarker. Built at HackRPI 2026 by Avyay, Paul and Person 3.
