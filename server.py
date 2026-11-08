"""Serve the canvas client and the shared Python game engine (no extra packages)."""
import argparse
import json
import math
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import threading
import time
from types import SimpleNamespace

import game
import gestures
import paths
import physics

WEB_ROOT = Path(__file__).parent / "web"
WIDTH, HEIGHT = 960, 600
MAX_BODY = 262144
SESSION_TTL = 1800


def point(value):
    return None if value is None else {"x": value[0], "y": value[1]}


class Session:
    def __init__(self):
        self.game = game.Game(WIDTH, HEIGHT, headless=True)
        self.gesture = {}
        gestures.reset_gesture(self.gesture)
        self.touched = time.monotonic()
        self.lock = threading.Lock()
        self.cursor = ("IDLE", None)

    def update(self, events):
        for event in events:
            if "action" in event:
                if event["action"] == "retry":
                    self.game.retry()
                else:
                    self.game.next_level()
                continue
            mode, position = event["mode"], event["point"]
            if "landmarks" in event:
                landmarks = event["landmarks"]
                # The video is mirrored in the UI; mirror landmarks before Python recognition.
                hand = None if landmarks is None else [
                    SimpleNamespace(x=1 - p["x"], y=p["y"], z=p["z"]) for p in landmarks
                ]
                mode, position = gestures.get_gesture(
                    hand, WIDTH, HEIGHT, self.gesture, event["dt"],
                    camera_aspect=event["cameraAspect"],
                )
            else:
                gestures.reset_gesture(self.gesture)
            self.cursor = mode, position
            if not event["paused"]:
                self.game.update(mode, position, event["dt"], gesture_input="landmarks" in event)
                if len(self.game.raw_path) > 4096:
                    self.game.retry()

    def snapshot(self):
        flight = self.game
        preview = paths.resample(paths.chaikin(flight.raw_path)) if flight.state == "DRAWING" else []
        return {
            "level": flight.level, "score": flight.score, "tries": flight.tries,
            "state": flight.state, "pad": point(flight.pad), "star": point(flight.star),
            "wind": point(flight.wind), "clouds": flight.clouds,
            "plane": {**flight.plane, "target": point(flight.plane["target"])},
            "path": list(map(point, flight.path)), "trail": list(map(point, flight.trail)),
            "preview": list(map(point, preview)),
            "tight": paths.find_tight_turns(preview, physics.SPEED / physics.MAX_TURN),
            "starRadius": game.STAR_RADIUS,
            "startRadius": game.START_RADIUS,
            "comparison": flight.comparison(),
            "fieldWidth": flight.w,
            "launchClouds": [dict(c) for c in flight.cloud_layout] if flight.state == "LANDED" else [],
            "trajectory": list(map(point, flight.trajectory)) if flight.state == "LANDED" else [],
            "cursor": {"mode": self.cursor[0], "point": point(self.cursor[1])},
        }


def number(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError("Invalid numeric input")
    return value


def validate_events(events):
    if not isinstance(events, list) or not 1 <= len(events) <= 120:
        raise ValueError("Expected 1 to 120 input events")
    clean = []
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("Invalid event")
        if "action" in event:
            if event["action"] not in ("retry", "next"):
                raise ValueError("Unknown action")
            clean.append({"action": event["action"]})
            continue
        mode = event.get("mode", "IDLE")
        if mode not in ("IDLE", "HOVER", "DRAW"):
            raise ValueError("Unknown input mode")
        position = event.get("point")
        if position is not None:
            if not isinstance(position, dict):
                raise ValueError("Invalid point")
            position = (number(position.get("x"), 0, WIDTH), number(position.get("y"), 0, HEIGHT))
        item = {"mode": mode, "point": position, "dt": number(event.get("dt", 0), 0, 0.05), "paused": event.get("paused") is True}
        if "landmarks" in event:
            landmarks = event["landmarks"]
            if landmarks is not None:
                if not isinstance(landmarks, list) or len(landmarks) != 21 or not all(isinstance(p, dict) for p in landmarks):
                    raise ValueError("Expected 21 landmarks")
                landmarks = [{"x": number(p.get("x"), -2, 3),
                              "y": number(p.get("y"), -2, 3),
                              "z": number(p.get("z", 0), -5, 5)} for p in landmarks]
            item["landmarks"] = landmarks
            item["cameraAspect"] = number(event.get("cameraAspect", WIDTH / HEIGHT), 0.1, 10)
        clean.append(item)
    return clean


class GameServer(ThreadingHTTPServer):
    def __init__(self, address):
        super().__init__(address, Handler)
        self.sessions = {}
        self.sessions_lock = threading.Lock()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def list_directory(self, path):
        self.send_error(404)

    def reply(self, status, data):
        body = json.dumps(data, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            if self.path not in ("/api/session", "/api/update"):
                self.reply(404, {"error": "Unknown endpoint"})
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.reply(415, {"error": "Expected application/json"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                self.reply(413, {"error": "Invalid request size"})
                return
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object")
            with self.server.sessions_lock:
                now = time.monotonic()
                self.server.sessions = {key: session for key, session in self.server.sessions.items() if now - session.touched < SESSION_TTL}
                if self.path == "/api/session":
                    if len(self.server.sessions) >= 128:
                        self.reply(503, {"error": "Server is full. Try again later."})
                        return
                    token = secrets.token_urlsafe(32)
                    session = Session()
                    self.server.sessions[token] = session
                else:
                    token = data.get("session")
                    session = self.server.sessions.get(token) if isinstance(token, str) else None
                    if session is None:
                        self.reply(404, {"error": "Game session expired. Reload to start again."})
                        return
                session.touched = now
            with session.lock:
                if self.path == "/api/update":
                    session.update(validate_events(data.get("events")))
                self.reply(200, {"session": token, "game": session.snapshot()})
        except (ValueError, TypeError, OverflowError) as error:
            self.reply(400, {"error": str(error)})
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format, *args):
        # Avoid per-frame access logs; still report HTTP errors.
        if len(args) > 1 and str(args[1]).startswith(("4", "5")):
            super().log_message(format, *args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    with GameServer((args.host, args.port)) as server:
        print(f"Nimbus: http://{args.host}:{args.port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
