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
In the browser, click **Start** and allow camera access. Draw with one
index finger, then hold up two or more fingers to launch. If camera access fails, check
permissions and click **Start** again.

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

Press **P** or the pencil button for Free Draw. One raised index finger draws;
two or more raised fingers lift the pen and cycle its color once per gesture.
Use the browser's palette and Fine/Medium/Bold sizes to choose a pen, **U / Undo**
to remove the last stroke, or **C / Clear** to erase the canvas. **Esc**, **P**, or
**Back to game** resumes the paused mission. Ink stays when switching modes
and is cleared on reload. Game shortcuts R, N, and V are disabled in Free Draw.
Desktop Free Draw supports the same drawing/color gestures, C to clear, and
P or Esc to return to the game.

Hand tracking loads MediaPipe and its model from the internet and requires
HTTPS when deployed (localhost is allowed for development).

### Challenge Gemini after each flight

Successful flights and crashes stay on the results screen. If your route
crashes, Gemini tries to find a safe route through the same level; after a
successful delivery, it benchmarks your flight against its own proposals.
Gemini proposes routes for the same level, and Python flies each proposal
through the same fixed-step physics, wind, and moving clouds as the player.
The fastest successful proposal becomes the benchmark. Both actual flight paths
appear on the field; after a crash, the result calls out Gemini's safe route
instead of claiming a time win. After a delivery, the results lead with who
finished faster and the time difference in seconds. Both flight times, the time
gap, and your best time on this level appear below. Close finishes are labeled
"Nearly tied" while the headline still shows who was faster.
This is the **best verified route**, including
predictive refinements on moving-cloud levels, not
a mathematically guaranteed optimal path. Gemini's machine learning generates
the routes; the simulator computes every metric, not the model.

For levels with moving clouds, Gemini also receives a forecast of cloud positions
at one-second intervals through the 30-second simulation limit. Forecasts use the
same movement and edge-bounce rules as the game. Simulation feedback includes
the time and position of collisions and each cloud's closest encounter.

After each proposal batch, a bounded planner tries detours around predicted
collision locations. It forecasts where the cloud will be at the detour's
estimated entry and exit times, then re-simulates the entire route with wind,
turn limits, smoothing, and every other cloud. Failed detours can be repaired
again using their new collision times. Routes may cross a cloud's initial
position if the cloud has moved away by arrival; the drone cannot stop or wait.
The planner tests at most 32 refinements per batch (64 per level) without extra
Gemini calls, and accepts only successful full simulations. If a refined route
wins, the results identify it as **Gemini + predictive cloud planning**. This is
a bounded search over Gemini's proposals, not a guarantee of success or optimality.

In the browser, a purple Gemini drone automatically replays its verified flight
after the benchmark is ready. Your flight stays orange, and the storms replay
from their original launch positions. The full dashed Gemini route remains
visible afterward. Use **Replay Gemini's flight** below the field to watch again
without making another API request. Planning and unavailable messages also
appear on the field while you wait.

Press **R / Try another route** for the same layout and benchmark, or **N / Next
level** to continue. Crashes remain visible until you choose an action.
Successful rematches keep your best time without repeatedly awarding the
level's delivery points.

Put your [Gemini API key](https://ai.google.dev/gemini-api/docs/api-key) in the
repository-root `.env` file (create it if needed):

```dotenv
GEMINI_API_KEY=your-api-key
GEMINI_MODEL=gemini-2.5-flash
```

Then run `python -B server.py`. Both browser and desktop games automatically read
this file. The key stays on the Python server and is never logged or sent to the
browser. Explicit process environment variables take precedence over `.env`.
Alternatively, set them in PowerShell:

```powershell
$env:GEMINI_API_KEY = "your-api-key"
$env:GEMINI_MODEL = "gemini-2.5-flash" # optional; this is the default
python -B server.py
```

For bash, use `export GEMINI_API_KEY="your-api-key"` before starting the server.
For deployment, configure these variables in the Python service environment and
restart the service. `.env` is ignored by Git. Never put the key in `web/` or
commit it. Desktop `main.py` uses
the same settings and displays the comparison after landing.

The server uses Gemini's
[generateContent API and structured JSON output](https://ai.google.dev/api/generate-content)
through Python's standard library; there is no additional SDK dependency.
Only level geometry and simulation feedback go to Google, not camera images,
hand landmarks, or the player's route. Each completed level makes at most two
API calls (initial proposals and refinement), with a 25-second timeout per call
and up to six routes per response, plus at most 64 local predictive refinements.
Requests and local planning run in the background; the player
can retry or continue while waiting. Results are retained per level for the
session. Missing keys, API errors, and proposals that fail flight validation
show an unavailable state without blocking the game or inventing a benchmark.
API usage is subject to your Gemini account's quotas and billing.

Implementation: `gemini_agent.py` handles proposals and background requests;
`flight_sim.py` shares deterministic flight rules between players and route
verification. `tests/test_gemini_agent.py` exercises the integration using mock
responses, so the test suite needs no API key and makes no paid Gemini calls.
On Windows with Edge installed, `python -B tests/browser_check.py` also checks
the results UI and buttons in a hidden browser at desktop and narrow widths.

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
Hand tracking: Google MediaPipe HandLandmarker. Built at HackRPI 2026 by Avyay, Paul and Harry.
