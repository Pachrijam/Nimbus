"""Optional Windows Edge smoke check: python -B tests/browser_check.py.

Uses real UI modules and simulated Gemini data. No camera or API key required.
Screenshots and isolated browser profiles are written to the system temp folder.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import gemini_agent
from server import GameServer, Handler, Session


def main():
    with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
        session = Session()
        route = {"waypoints": [{"x": x, "y": y} for x, y in
                              [session.game.pad, (240, 180), (480, 180), (680, 200), session.game.star]]}
        session.game.path = gemini_agent.validate_route(route, session.game.level_layout())
        session.game.state = "FLYING"
        session.game.tries = 1
        for _ in range(400):
            if session.game.state != "FLYING":
                break
            session.game.update("IDLE", None, .02)
        with patch("gemini_agent.request_routes", return_value=[route]):
            session.game.benchmark_job.result = gemini_agent.build_benchmark(
                session.game.level_layout(), "mock", "gemini-test")
        snapshot = session.snapshot()

    script = """<script type="module">
    try {
      const [{createUI}, {createControls}, {createRenderer}, {createGeminiReplay}] = await Promise.all([
        import('/src/ui.js'), import('/src/controls.js'), import('/src/renderer.js'), import('/src/replay.js')]);
      const snapshot = SNAPSHOT;
      const canvas = document.querySelector('#game-canvas'), panel = document.querySelector('#comparison');
      const state = {game:null, input:{mode:'IDLE',point:null}, selectedInput:'HAND', freeDraw:false, freeInk:[], debug:false, autopilot:false};
      const ui = createUI({canvas, statusText:document.querySelector('#status-text'), toast:document.querySelector('#toast')});
      const events = [], check = (ok,msg) => {if (!ok) throw Error(msg)};
      const controls = createControls({gamePanel:document.querySelector('.game-panel'), handButton:document.querySelector('#camera-mode'), state,
        camera:{stopCamera(){},enableHandTracking(){}}, queueEvent:e=>events.push(e), setStatus:ui.setStatus, showToast:ui.showToast});
      const pending = structuredClone(snapshot);
      pending.comparison.status = 'pending'; pending.comparison.message = 'Planning...';
      ui.applySnapshot(state,pending); check(panel.getAttribute('aria-busy') === 'true','pending');
      const replayButton = document.querySelector('#gemini-replay');
      check(replayButton.disabled, 'cannot replay while planning');
      ui.applySnapshot(state,snapshot); check(!panel.classList.contains('hidden'),'visible');
      check(document.querySelector('#time-gap').textContent === '0.00 s','tied gap');
      check(document.querySelector('#comparison-title').textContent === 'You and Gemini finished in the same time!','tied outcome');
      for (const [delta, verdict, title, badge] of [
        [-1.2, 'beat', 'You beat Gemini by 1.20 seconds!', 'You win!'],
        [2, 'chasing', 'Gemini finished 2.00 seconds ahead', 'Gemini wins'],
        [0.2, 'matched', 'Gemini finished 0.20 seconds ahead', 'Nearly tied'],
      ]) {
        const comparison = {...snapshot.comparison, aiTime:10, playerTime:10+delta, timeDelta:delta, verdict};
        ui.applySnapshot(state,{...snapshot,comparison});
        check(document.querySelector('#comparison-title').textContent === title,'winner and time gap');
        check(document.querySelector('#match-badge').textContent === badge,'accurate result badge');
        check(!panel.textContent.includes('%'),'no percentage to decode');
        if (delta > 0) check(document.querySelector('#comparison-message').textContent.includes('Finish under 10.00 s'),'clear retry target');
        check(document.documentElement.scrollWidth <= innerWidth,'outcome fits viewport');
      }
      ui.applySnapshot(state,pending);
      check(document.querySelector('#time-gap').textContent.codePointAt(0) === 8212,'pending clears old gap');
      check(document.querySelector('#comparison-title').textContent === 'Your flight vs. Gemini','pending clears old winner');
      ui.applySnapshot(state,{...snapshot,comparison:{...snapshot.comparison,planner:'gemini_predictive',refined:12,tested:14}});
      check(document.querySelector('#comparison-note').textContent.includes('Gemini + predictive cloud planning'), 'refined route attribution');
      check(document.querySelector('#comparison-note').textContent.includes('12 time-aware refinements'), 'refinement count');
      ui.applySnapshot(state,snapshot);
      check(!replayButton.disabled, 'ready to replay');
      replayButton.click(); check(state.geminiReplay === 1 && events.length === 0, 'replay does not change the game');
      document.querySelector('#challenge-retry').click(); document.querySelector('#challenge-next').click();
      check(events[0].action === 'retry' && events[1].action === 'next','actions');
      state.freeDraw = true; ui.applySnapshot(state,snapshot); check(panel.classList.contains('hidden'),'free draw'); state.freeDraw = false;
      const disabled = structuredClone(snapshot);
      disabled.comparison.status = 'disabled'; disabled.comparison.message = 'Not configured';
      ui.applySnapshot(state,disabled);
      check(replayButton.disabled, 'cannot replay unavailable result');
      check(document.querySelector('#ai-time').textContent.codePointAt(0) === 8212,'stale score');
      ui.applySnapshot(state,{...snapshot,state:'READY',comparison:null}); check(panel.classList.contains('hidden'),'retry');
      ui.applySnapshot(state,snapshot);
      const replay = createGeminiReplay();
      const path = snapshot.comparison.aiTrajectory;
      let frame = replay.frame(state, 0);
      check(frame.plane.x === path[0].x && frame.elapsed === 0, 'replay starts at launch');
      state.game = structuredClone(snapshot);
      frame = replay.frame(state, 100);
      check(frame.elapsed > 0 && frame.plane.x !== path[0].x, 'new snapshots do not restart replay');
      state.freeDraw = true; check(replay.frame(state, 200) === null, 'free draw hides replay');
      state.freeDraw = false;
      check(replay.frame(state, 10000).elapsed === frame.elapsed, 'free draw pauses replay');
      for (let time = 10100; time <= 18000; time += 100) frame = replay.frame(state, time);
      check(frame.done && frame.plane.x === path.at(-1).x && frame.plane.y === path.at(-1).y, 'replay reaches recorded destination');
      check(frame.trail.length === path.length, 'complete route remains visible');
      replayButton.click(); frame = replay.frame(state, 18100);
      check(frame.elapsed === 0, 'replay button restarts animation');
      state.game = {...snapshot, state:'READY', comparison:null};
      check(replay.frame(state, 18200) === null, 'retry clears replay');
      state.game = structuredClone(snapshot);
      state.game.launchClouds = [{x: snapshot.fieldWidth - 45 - 0.1, y:100, r:45, vx:60}];
      frame = replay.frame(state, 18300);
      check(frame.clouds[0].x === state.game.launchClouds[0].x, 'storms start at launch positions');
      frame = replay.frame(state, 18400);
      check(frame.clouds[0].vx < 0 && frame.clouds[0].x <= snapshot.fieldWidth - 45, 'replay storms bounce');
      check(state.game.launchClouds[0].vx === 60, 'replay does not mutate game storms');
      state.game = snapshot;
      const renderer = createRenderer({canvas,cameraVideo:document.querySelector('#camera-video')});
      const context = canvas.getContext('2d'), labels = [], fillText = context.fillText.bind(context);
      context.fillText = (text,...args) => {labels.push(text); fillText(text,...args)};
      renderer.render({...state,game:pending},false,0);
      check(labels.some(text => text.includes('Gemini is planning')), 'planning visible on field');
      renderer.render({...state,game:disabled},false,0);
      check(labels.some(text => text.startsWith('AI comparison is off.')), 'disabled comparison visible on field');
      for (let time = 0; time <= 2000; time += 100) renderer.render(state,false,time);
      check(labels.includes('GEMINI') && labels.some(text => text.startsWith('Watch Gemini fly:')), 'animated drone and timer visible');
      context.fillText = fillText;
      const toggle = document.querySelector('#free-draw');
      toggle.click();
      check(state.freeDraw && panel.classList.contains('hidden'), 'enter free draw immediately hides results');
      check(!document.querySelector('#free-draw-tools').classList.contains('hidden'), 'drawing tools visible');
      check(canvas.getAttribute('aria-label').includes('Free draw'), 'free draw accessible label');
      const eventCount = events.length;
      for (const key of ['r','n','v']) window.dispatchEvent(new KeyboardEvent('keydown',{key}));
      check(events.length === eventCount && !state.autopilot, 'game shortcuts cannot change paused mission');
      const sample = (mode, x = 300, y = 300) => {
        state.input = Object.assign(state.input, {mode, point:x === null ? null : {x,y}});
        controls.updateFreeDraw();
      };
      renderer.render(state,false,20500);
      const pixel = (x,y) => [...context.getImageData(
        Math.floor(x * canvas.width / 960), Math.floor(y * canvas.height / 600), 1, 1).data];
      const blankDot = pixel(300,300), blankGap = pixel(350,300);
      sample('DRAW');
      for (let i = 0; i < 100; i++) sample('DRAW');
      check(state.freeInk.length === 1 && state.freeInk[0].points.length === 1, 'stationary input creates one dot');
      const firstColor = state.penColor;
      sample('HOVER'); const secondColor = state.penColor;
      sample('HOVER');
      check(firstColor !== secondColor && state.penColor === secondColor, 'held peace sign changes color once');
      document.querySelector('#pen-colors').children[1].click(); sample('HOVER');
      check(state.penColor === secondColor, 'palette selection survives a held peace sign');
      sample('DRAW', 400, 300); sample('DRAW', 500, 300);
      check(state.freeInk.length === 2 && state.freeInk[0].color === firstColor && state.freeInk[1].color === secondColor, 'stroke colors retained');
      sample('IDLE', null); sample('DRAW', 600, 300);
      check(state.freeInk.length === 3, 'tracking loss separates strokes');
      window.dispatchEvent(new KeyboardEvent('keydown',{key:'u'}));
      check(state.freeInk.length === 2, 'undo removes last stroke');
      const size = document.querySelector('#pen-size'); size.value = '16'; size.dispatchEvent(new Event('change'));
      document.querySelector('#pen-colors').children[3].click();
      sample('DRAW', 300, 400); sample('DRAW', 600, 400); sample('IDLE', null);
      check(state.freeInk[2].size === 16 && state.freeInk[0].size === 8, 'brush size applies to new strokes');
      renderer.render(state,false,21000);
      check(canvas.width === Math.round(canvas.getBoundingClientRect().width * Math.min(2, devicePixelRatio)), 'canvas preserves high-DPI rendering');
      check(pixel(300,300)[0] === 255 && pixel(300,300)[1] === 109, 'single point stroke is visible');
      check(JSON.stringify(pixel(350,300)) === JSON.stringify(blankGap), 'pen lift does not connect separate strokes');
      check(pixel(450,400)[0] === 255 && pixel(450,400)[1] === 218, 'selected pen color rendered');
      const ink = state.freeInk;
      window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}));
      check(!state.freeDraw && !panel.classList.contains('hidden'), 'escape restores game and results');
      check(document.querySelector('#status-text').textContent.includes('Delivery complete'), 'exit restores mission status');
      document.querySelector('#clear').click();
      check(state.freeInk === ink && state.freeInk.length === 3, 'clearing game preserves free drawing');
      toggle.click(); sample('DRAW', 700, 400);
      check(state.freeInk.length === 4, 'returning to free draw starts a separate stroke');
      ui.applySnapshot(state,{...snapshot,cursor:{mode:'DRAW',point:{x:100,y:100}}},false);
      check(state.input.point.x === 700, 'stale snapshots cannot change the pen');
      window.dispatchEvent(new KeyboardEvent('keydown',{key:'c'}));
      check(!state.freeInk.length && !state.activeStroke && document.querySelector('#undo-drawing').disabled, 'clear removes ink and resets stroke');
      renderer.render(state,false,22000);
      check(JSON.stringify(pixel(300,300)) === JSON.stringify(blankDot), 'cleared ink does not leave ghosts');
      sample('DRAW', 280, 260); sample('DRAW', 360, 340); sample('DRAW', 470, 220); sample('HOVER');
      sample('DRAW', 520, 220); sample('DRAW', 620, 340); sample('DRAW', 700, 260); sample('IDLE', null);
      renderer.render(state,false,23000);
      document.querySelector('#toast').classList.add('hidden');
      window.scrollTo(0,0);
      check(document.documentElement.scrollWidth <= innerWidth,'overflow');
      document.body.dataset.qa = 'passed';
    } catch(error) {document.body.dataset.qa = 'FAILED: ' + error.message;}
    </script>""".replace("SNAPSHOT", json.dumps(snapshot))
    page = (ROOT / "web/index.html").read_text(encoding="utf-8").replace(
        '<script type="module" src="./src/app.js"></script>', script)

    class QAHandler(Handler):
        def do_GET(self):
            if self.path != "/__qa__":
                return super().do_GET()
            data = page.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = GameServer(("127.0.0.1", 0))
    server.RequestHandlerClass = QAHandler
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    try:
        # Headless Edge clamps very narrow layout viewports; 640 tests the
        # mobile breakpoint without producing a cropped screenshot.
        for width, density in ((1280, 1), (640, 1), (1280, 2), (640, 2)):
            profile = tempfile.mkdtemp(prefix="nimbus-browser-")
            screenshot = str(Path(tempfile.gettempdir()) / f"nimbus-gemini-{width}-{density}x.png")
            result = subprocess.run([
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                "--disable-extensions", "--disable-background-networking",
                f"--force-device-scale-factor={density}",
                "--user-data-dir=" + profile, f"--window-size={width},1600",
                "--virtual-time-budget=3000", "--screenshot=" + screenshot, "--dump-dom",
                f"http://127.0.0.1:{server.server_port}/__qa__"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25,
                startupinfo=startup, creationflags=subprocess.CREATE_NO_WINDOW)
            marker = re.search(r'data-qa="([^"]+)"', result.stdout.decode("utf-8", errors="replace"))
            status = marker.group(1) if marker else "no result"
            print(f"{width}px at {density}x browser checks: {status}; screenshot: {screenshot}")
            if result.returncode or status != "passed":
                raise RuntimeError("Browser checks failed: " + status)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
