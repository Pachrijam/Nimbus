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
                              [(90, 300), (240, 180), (480, 180), (680, 200), (840, 300)]]}
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
      const [{createUI}, {createControls}, {createRenderer}] = await Promise.all([
        import('/src/ui.js'), import('/src/controls.js'), import('/src/renderer.js')]);
      const snapshot = SNAPSHOT;
      const canvas = document.querySelector('#game-canvas'), panel = document.querySelector('#comparison');
      const state = {game:null, input:{mode:'IDLE',point:null}, selectedInput:'HAND', freeDraw:false, freeInk:[], debug:false, autopilot:false};
      const ui = createUI({canvas, statusText:document.querySelector('#status-text'), toast:document.querySelector('#toast')});
      const events = [], check = (ok,msg) => {if (!ok) throw Error(msg)};
      createControls({gamePanel:document.querySelector('.game-panel'), handButton:document.querySelector('#camera-mode'), state,
        camera:{stopCamera(){},enableHandTracking(){}}, queueEvent:e=>events.push(e), setStatus:ui.setStatus, showToast:ui.showToast});
      const pending = structuredClone(snapshot);
      pending.comparison.status = 'pending'; pending.comparison.message = 'Planning...';
      ui.applySnapshot(state,pending); check(panel.getAttribute('aria-busy') === 'true','pending');
      ui.applySnapshot(state,snapshot); check(!panel.classList.contains('hidden'),'visible');
      check(document.querySelector('#match-percent').textContent === '100.0%','score');
      document.querySelector('#challenge-retry').click(); document.querySelector('#challenge-next').click();
      check(events[0].action === 'retry' && events[1].action === 'next','actions');
      state.freeDraw = true; ui.applySnapshot(state,snapshot); check(panel.classList.contains('hidden'),'free draw'); state.freeDraw = false;
      const disabled = structuredClone(snapshot);
      disabled.comparison.status = 'disabled'; disabled.comparison.message = 'Not configured';
      ui.applySnapshot(state,disabled);
      check(document.querySelector('#ai-time').textContent.codePointAt(0) === 8212,'stale score');
      ui.applySnapshot(state,{...snapshot,state:'READY',comparison:null}); check(panel.classList.contains('hidden'),'retry');
      ui.applySnapshot(state,snapshot);
      createRenderer({canvas,cameraVideo:document.querySelector('#camera-video')}).render(state,false);
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
        for width in (1280, 640):
            profile = tempfile.mkdtemp(prefix="nimbus-browser-")
            screenshot = str(Path(tempfile.gettempdir()) / f"nimbus-gemini-{width}.png")
            result = subprocess.run([
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                "--disable-extensions", "--disable-background-networking",
                "--user-data-dir=" + profile, f"--window-size={width},1600",
                "--virtual-time-budget=3000", "--screenshot=" + screenshot, "--dump-dom",
                f"http://127.0.0.1:{server.server_port}/__qa__"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25,
                startupinfo=startup, creationflags=subprocess.CREATE_NO_WINDOW)
            marker = re.search(r'data-qa="([^"]+)"', result.stdout.decode("utf-8", errors="replace"))
            status = marker.group(1) if marker else "no result"
            print(f"{width}px browser checks: {status}; screenshot: {screenshot}")
            if result.returncode or status != "passed":
                raise RuntimeError("Browser checks failed: " + status)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
