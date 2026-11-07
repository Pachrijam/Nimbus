# Nimbus: Flight Path (HackRPI 2026)

**Sketch a drone's route in the air with one finger. A physics simulation instantly shows whether the drone can actually fly it through the wind and around the storms.**

## Run

Create and activate a virtual environment so packages are installed separately
from your system or Conda Python:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

In VS Code, select the `.venv` interpreter for this workspace after creating
the environment.

For hand tracking, install MediaPipe in the activated environment and put
`hand_landmarker.task` in this folder:

```sh
python -m pip install mediapipe
```

If the model or MediaPipe is unavailable, the app starts in mouse mode: move
the cursor and hold the left mouse button to draw.

Keys: `q` quit · `p` Free Draw/Game · `m` mouse mode · `f` fullscreen · `r` retry · `n` next level · `v` autopilot view · `c` clear · `d` debug

## Browser version (Python-powered)

From the repository root, run:

```sh
python server.py
```

Open `http://localhost:8000`. The web server needs only Python's standard
library; the desktop dependencies in `requirements.txt` are not needed for it.
Use `--port 8080` to choose another port.

The browser renders the canvas and sends input to `server.py`. Each tab gets an
independent in-memory `game.Game` instance. Levels, route validation, smoothing,
turn warnings, physics, collisions, retries, and scoring use `game.py`,
`paths.py`, and `physics.py` directly. Hand landmark detection stays in the
browser; only landmark coordinates go to `gestures.py` for gesture recognition.
Camera images are never uploaded. Free-draw ink and display controls stay in
the browser. Reloading starts a new game; idle sessions expire after 30 minutes.
If the connection fails, the game stops and asks you to reload.

Hand tracking loads MediaPipe and its model from the internet and requires
HTTPS when deployed (localhost is allowed for development).

### Vultr / nginx

The website now requires the Python process; copying `web/` to a static host
or using `python -m http.server` is no longer sufficient. Run `python3 server.py`
from the repository on the VPS (use your service manager to keep it running).
Proxy the site to that process in your nginx server block:

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Keep the Python listener on localhost behind nginx. Configure HTTPS on nginx
for webcam access. After updating the Python source, restart the Python
process. Sessions are held in memory, so use one process; restarting clears
active games. This lightweight server is intended for the hackathon demo.

### Checks

```sh
python -m unittest discover -s tests -v
```

## Docs
- **[OVERVIEW.md](OVERVIEW.md):** the full project: problem, solution, tech, architecture, interfaces, demo
- **[STEPS.md](STEPS.md):** exactly what each person does, in order, with checkpoints

## Credits
Hand tracking: Google MediaPipe HandLandmarker. Built at HackRPI 2026 by Avyay, Paul and Person 3.
