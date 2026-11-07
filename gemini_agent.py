"""Server-only Gemini route proposals, verified in the game's real simulator.

No model-reported scores are trusted. At most two requests are made per level;
the fastest successful proposal is the benchmark, not a global optimum.
"""
import json
import math
import re
import threading
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import flight_sim
import paths
import physics
from settings import gemini_settings

DEFAULT_MODEL = "gemini-2.5-flash"
REQUEST_TIMEOUT = 25
MAX_RESPONSE_BYTES = 262144
_slots = threading.BoundedSemaphore(4)

ROUTE_SCHEMA = {
    "type": "OBJECT",
    "properties": {"routes": {
        "type": "ARRAY", "minItems": 1, "maxItems": 6,
        "items": {"type": "OBJECT", "properties": {"waypoints": {
            "type": "ARRAY", "minItems": 2, "maxItems": 16,
            "items": {"type": "OBJECT", "properties": {
                "x": {"type": "NUMBER"}, "y": {"type": "NUMBER"}},
                "required": ["x", "y"]}}}, "required": ["waypoints"]}}},
    "required": ["routes"],
}


class AgentError(Exception):
    """A safe, user-facing failure message (never includes provider responses)."""


def request_routes(layout, feedback, api_key, model):
    prompt = (
        "You are the rival drone pilot in Nimbus. Minimize flight time to the destination. "
        "Propose 4 to 6 diverse routes as JSON. Each waypoints list includes the exact pad "
        "and star as its first and last point, with 0 to 14 intermediate points inside the field. "
        "Coordinates are pixels: x right, y down. Clouds are circular collision zones; their "
        "x moves at vx pixels/second and bounces when the circle reaches the field edges. "
        "Clouds start moving only at launch. Wind is constant velocity added to drone motion. "
        "The drone starts heading right. Routes undergo two Chaikin smoothing passes and "
        "8px resampling before pure-pursuit flight. Leave clearance for turn limits and "
        "corner cutting. Explore above and below obstacles, with gradual turns. "
        "Landing occurs within 28px of the star. Return routes only, never invent scores.\n"
        + json.dumps({"level": layout, "flight": {
            "speed": physics.SPEED, "max_turn_radians_per_second": physics.MAX_TURN,
            "lookahead": physics.LOOKAHEAD, "steering_gain": physics.K_STEER,
            "physics_enabled": physics.USE_PHYSICS}, "previous_simulations": feedback})
    )
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
               "generationConfig": {"responseMimeType": "application/json",
                                    "responseSchema": ROUTE_SCHEMA,
                                    "maxOutputTokens": 8192}}
    request = Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        json.dumps(payload).encode(),
        {"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise AgentError("Gemini returned too much data. Try another level.")
        result = json.loads(body)
        candidate = result["candidates"][0]
        if candidate.get("finishReason") != "STOP":
            raise AgentError("Gemini could not finish its routes. Try another level.")
        output = "".join(part.get("text", "") for part in candidate["content"]["parts"]
                         if not part.get("thought"))
        routes = json.loads(output)["routes"]
        if not isinstance(routes, list) or not 1 <= len(routes) <= 6:
            raise ValueError("Invalid routes")
        return routes
    except HTTPError as error:
        status = error.code
        error.close()
        if status in (401, 403):
            raise AgentError("Gemini access was denied. Check the server API key.") from None
        if status == 429:
            raise AgentError("Gemini's request limit was reached. Play on and try a later level.") from None
        raise AgentError("Gemini is unavailable. Check the server's model configuration.") from None
    except (URLError, TimeoutError, OSError):
        raise AgentError("Gemini could not be reached. You can still retry or continue.") from None
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise AgentError("Gemini returned invalid route data. Try another level.") from None


def validate_route(candidate, layout):
    """Reject untrusted, unbounded, or out-of-field model coordinates."""
    points = candidate["waypoints"]
    if not isinstance(points, list) or not 2 <= len(points) <= 16:
        raise ValueError("Expected 2 to 16 waypoints")
    raw = []
    for point in points:
        x, y = point["x"], point["y"]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
               for v in (x, y)):
            raise ValueError("Coordinates must be finite numbers")
        if not (0 <= x <= layout["width"] and 0 <= y <= layout["height"]):
            raise ValueError("Waypoints must stay inside the field")
        raw.append((x, y))
    if paths.distance(raw[0], layout["pad"]) > 1 or paths.distance(raw[-1], layout["star"]) > 1:
        raise ValueError("Route must connect the pad and destination")
    raw[0], raw[-1] = tuple(layout["pad"]), tuple(layout["star"])
    return paths.resample(paths.chaikin(raw))


def build_benchmark(layout, api_key, model):
    best = None
    feedback = []
    tested = 0
    for _ in range(2):
        try:
            proposals = request_routes(layout, feedback, api_key, model)
        except AgentError:
            if best is not None:
                break  # Keep a verified result if refinement is unavailable.
            raise
        feedback = []
        for proposal in proposals:
            try:
                route = validate_route(proposal, layout)
            except (ValueError, KeyError, TypeError, OverflowError):
                feedback.append({"state": "INVALID", "hint": "Use bounded numeric waypoints from pad to star."})
                continue
            outcome = flight_sim.simulate(route, layout)
            tested += 1
            feedback.append({"waypoints": proposal["waypoints"], "state": outcome["state"],
                             "time": round(outcome["time"], 3),
                             "end_position": outcome["trajectory"][-1]})
            if outcome["state"] == "LANDED" and (best is None or outcome["time"] < best["time"]):
                best = {"time": outcome["time"], "distance": outcome["distance"],
                        "trajectory": outcome["trajectory"], "route": route}
    if best is None:
        return {"status": "unavailable", "message": "You delivered! Gemini did not find a flyable route this round.",
                "tested": tested}
    return {"status": "ready", "model": model, "tested": tested, **best}


class BenchmarkJob:
    """A bounded background job. It owns detached data and never mutates a Game."""
    def __init__(self, layout):
        self.result = {"status": "pending", "message": "Gemini is planning and testing its routes..."}
        self.done = threading.Event()
        api_key, model = gemini_settings(DEFAULT_MODEL)
        if not api_key:
            self.result = {"status": "disabled", "message": "Gemini challenge is not configured. Set GEMINI_API_KEY on the server."}
        elif not re.fullmatch(r"gemini-[a-zA-Z0-9.\-]+", model):
            self.result = {"status": "unavailable", "message": "Check GEMINI_MODEL on the server."}
        elif not _slots.acquire(blocking=False):
            self.result = {"status": "unavailable", "message": "Gemini pilots are busy. You can still retry or continue."}
        else:
            worker = threading.Thread(target=self._run, args=(layout, api_key, model), daemon=True)
            try:
                worker.start()
            except RuntimeError:
                _slots.release()
                self.result = {"status": "unavailable", "message": "Gemini could not start. You can still continue."}
            else:
                return
        self.done.set()

    def _run(self, layout, api_key, model):
        try:
            self.result = build_benchmark(layout, api_key, model)
        except AgentError as error:
            self.result = {"status": "unavailable", "message": str(error)}
        except Exception:
            # Do not expose exception text: a provider error may contain credentials.
            self.result = {"status": "unavailable", "message": "Gemini comparison is unavailable. You can still continue."}
        finally:
            self.done.set()
            _slots.release()
