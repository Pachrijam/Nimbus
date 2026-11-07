# Nimbus: Flight Path (HackRPI 2026)

**Pinch your thumb and index finger to sketch a drone's route in the air. A physics simulation instantly shows whether the drone can actually fly it through the wind and around the storms.**

## Architecture

### Repository layout

```text
.
├── main.py                 # Desktop OpenCV application entry point
├── server.py               # HTTP API and per-browser game sessions
├── game.py                 # Game states, levels, scoring, and collisions
├── physics.py              # Flight movement and steering
├── paths.py                # Route smoothing, resampling, and turn checks
├── gestures.py             # Hand landmark gesture recognition
├── visuals.py              # Desktop game rendering
├── freedraw.py             # Desktop free-draw mode
├── requirements.txt        # Python dependencies for the desktop app
├── web/
│   ├── index.html          # Browser page and controls
│   ├── styles.css          # Browser layout and styling
│   ├── images/
│   │   └── favicon.png     # Nimbus browser icon
│   └── src/
│       ├── app.js          # Browser app entry point and animation loop
│       ├── camera.js       # Webcam access and hand landmark detection
│       ├── config.js       # Browser game and display constants
│       ├── controls.js     # Hand tracking controls, keyboard, and free-draw input
│       ├── game-client.js  # Requests and session updates to server.py
│       ├── renderer.js     # Canvas rendering
│       └── ui.js           # Status messages and browser UI updates
├── tests/
│   ├── test_gestures.py    # Gesture recognition tests
│   └── test_server.py      # Game engine and HTTP API tests
└── documentation/
    ├── OVERVIEW.md         # Project overview and design
    └── STEPS.md            # Development tasks and checkpoints
```

### How the pieces fit together

- **Browser version:** `web/src/app.js` connects the camera, controls, renderer,
  UI, and game client. It sends hand-landmark input to `server.py`;
  the server creates an isolated game session and applies the shared game logic
  from `game.py`, `gestures.py`, `paths.py`, and `physics.py`. The browser
  renders returned snapshots on the canvas. Camera video is processed locally
  and is not sent to the server.
- **Desktop version:** `main.py` captures and mirrors webcam frames, runs
  MediaPipe hand tracking when available, and sends gestures to `game.Game` or
  `freedraw.FreeDraw`. The game uses `paths.py` and `physics.py`; `visuals.py`
  draws the result with OpenCV.
- **Deployment:** Nginx serves HTTPS and reverse-proxies requests to the
  `server.py` process on `127.0.0.1:8000`. See the Vultr instructions below.

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

Drawing uses hand gestures only. The desktop app requires MediaPipe, the model,
and a working webcam; if any is unavailable, it exits with setup instructions.
In the browser, click **Hand tracking** and allow camera access. Pinch your thumb
and index finger to draw, then open the pinch to launch. If camera access fails, check
permissions and click **Hand tracking** again.

Keys: `q` quit · `p` Free Draw/Game · `f` fullscreen · `r` retry · `n` next level · `v` autopilot view · `c` clear · `d` debug

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
