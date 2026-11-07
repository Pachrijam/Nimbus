# Nimbus: Flight Path (HackRPI 2026)

**Sketch a drone's route in the air with one finger. A physics simulation instantly shows whether the drone can actually fly it through the wind and around the storms.**

## Architecture

```text
.
├── main.py                 # Desktop OpenCV application entry point
├── server.py               # HTTP API and per-browser game sessions
├── game.py                 # Game states, levels, scoring, and collisions
├── physics.py              # Flight movement and steering
├── paths.py                # Route smoothing, resampling, and turn checks
├── gestures.py             # Hand landmark gesture recognition and smoothing
├── visuals.py              # Desktop game rendering
├── freedraw.py             # Desktop free-draw mode
├── requirements.txt        # Python dependencies
├── hand_landmarker.task    # MediaPipe hand-tracking model for desktop use
├── web/
│   ├── index.html          # Browser page and controls
│   ├── styles.css          # Browser layout and styling
│   ├── images/
│   │   └── favicon.png     # Nimbus browser icon
│   └── src/
│       ├── app.js          # Connects client, camera, controls, UI, and renderer
│       ├── camera.js       # Webcam access and MediaPipe hand landmarks
│       ├── config.js       # Canvas dimensions
│       ├── controls.js     # Hand tracking, keyboard, and free-draw controls
│       ├── game-client.js  # Game session and update API requests
│       ├── renderer.js     # Canvas game rendering
│       └── ui.js           # Status messages and UI updates
├── tests/
│   ├── test_gestures.py    # Gesture recognition tests
│   └── test_server.py      # Game engine and HTTP API tests
└── docs/
    ├── OVERVIEW.md         # Project overview and design
    └── STEPS.md            # Development tasks and checkpoints
```

### How the pieces fit together

- **Browser:** `web/src/app.js` coordinates the camera, controls, game client,
  UI, and renderer. `camera.js` processes webcam frames locally with MediaPipe;
  only hand landmarks (not camera video) are sent to `server.py`. The server
  creates an in-memory game session for each browser tab, recognizes gestures,
  runs the shared game logic, and returns snapshots for `renderer.js` to draw.
- **Shared game logic:** `game.py` manages levels, routes, collisions, and
  scoring; `paths.py` smooths and resamples routes; `physics.py` moves the
  aircraft; and `gestures.py` recognizes and smooths hand gestures. `server.py`
  uses these modules for browser sessions.
- **Desktop:** `main.py` captures webcam frames, runs MediaPipe hand tracking,
  and updates either `game.Game` or `freedraw.FreeDraw`. `visuals.py` renders
  the game with OpenCV.
- **Deployment:** Nginx provides HTTPS and reverse-proxies browser requests to
  `server.py` on `127.0.0.1:8000`; HTTPS is needed for browser camera access.

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
In the browser, click **Hand tracking** and allow camera access. Draw with one
index finger, then hold up two fingers to launch. If camera access fails, check
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
