"""Server-only Gemini route proposals, verified in the game's real simulator.

No model-reported scores are trusted. At most two requests are made per level;
the fastest verified local route, proposal, or predictive refinement is the benchmark,
not a global optimum.
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
import route_planner
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
    moving = [index for index, cloud in enumerate(layout["clouds"])
              if cloud["vx"] or cloud.get("vy", 0.0)]
    forecast = []
    if moving:
        for frame in flight_sim.forecast_clouds(layout):
            forecast.append({"time": frame["time"], "positions": [
                {"cloud_index": index, "x": round(frame["clouds"][index]["x"], 2),
                 "y": frame["clouds"][index]["y"]} for index in moving]})
    prompt = (
        "You are the rival drone pilot in Nimbus. Minimize flight time to the destination. "
        "Propose 4 to 6 diverse routes as JSON. Each waypoints list includes the exact pad "
        "and star as its first and last point, with 0 to 14 intermediate points inside the field. "
        "Coordinates are pixels: x right, y down. Clouds are circular collision zones; their "
        "x and y move at vx and vy pixels/second, bouncing when the circle reaches a field edge. "
        "Clouds start moving only at launch. Wind is a constant velocity vector "
        "in pixels/second throughout the flight. "
        "The drone starts heading right. Routes undergo two Chaikin smoothing passes and "
        "4px jitter filtering, two Chaikin passes, and 8px resampling before pure-pursuit flight. "
        "Leave clearance for turn limits and "
        "corner cutting. Explore above and below obstacles, with gradual turns. "
        "Plan crossings using the supplied future_cloud_positions (seconds since launch), "
        "not only the clouds' initial positions. Estimate your arrival times with wind and turns. "
        "The drone cannot stop or wait; change route geometry to change arrival time. "
        "Forecast samples are guidance: the simulator checks collisions every 1/60 second. "
        "Previous simulations include closest encounters and collision positions at their actual times. "
        "Landing occurs within 28px of the star. Return routes only, never invent scores.\n"
        + json.dumps({"level": layout, "flight": {
            "speed": physics.SPEED, "max_turn_radians_per_second": physics.MAX_TURN,
            "lookahead": physics.LOOKAHEAD, "steering_gain": physics.K_STEER,
            "physics_enabled": physics.USE_PHYSICS}, "future_cloud_positions": forecast,
            "previous_simulations": feedback})
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
    return paths.flight_path(raw)


def simulation_feedback(node, source="gemini"):
    outcome = node["outcome"]
    return {"waypoints": [{"x": x, "y": y} for x, y in node["waypoints"]],
            "source": source, "state": outcome["state"], "time": round(outcome["time"], 3),
            "end_position": outcome["trajectory"][-1],
            "collision": outcome.get("collision"), "encounters": outcome.get("encounters", [])}


def build_local_benchmark(layout):
    planning = route_planner.find_route(layout)
    node = planning["best"]
    if node is None:
        return None
    outcome = node["outcome"]
    return {"status": "ready", "model": None, "planner": "local",
            "tested": planning["tested"], "refined": planning["refined"],
            "time": outcome["time"], "distance": outcome["distance"],
            "trajectory": outcome["trajectory"], "route": node["route"]}


def build_benchmark(layout, api_key, model, *, initial=None, on_result=None):
    best = initial
    feedback = []
    tested = initial["tested"] if initial else 0
    refined = initial["refined"] if initial else 0

    def snapshot(planning=False):
        return {**best, "status": "ready", "model": model if best["planner"] != "local" else None,
                "tested": tested, "refined": refined, "planning": planning}

    def consider(node, planner):
        nonlocal best
        outcome = node["outcome"]
        if outcome["state"] == "LANDED" and (best is None or outcome["time"] < best["time"]):
            best = {"time": outcome["time"], "distance": outcome["distance"],
                    "trajectory": outcome["trajectory"], "route": node["route"], "planner": planner}
            if on_result is not None:
                on_result(snapshot(planning=True))

    for _ in range(2):
        try:
            proposals = request_routes(layout, feedback, api_key, model)
        except AgentError:
            if best is not None:
                break  # Keep a verified result if refinement is unavailable.
            raise
        feedback = []
        seeds = []
        for proposal in proposals:
            try:
                route = validate_route(proposal, layout)
            except (ValueError, KeyError, TypeError, OverflowError):
                feedback.append({"state": "INVALID", "hint": "Use bounded numeric waypoints from pad to star."})
                continue
            outcome = flight_sim.simulate(route, layout, diagnostics=True)
            tested += 1
            waypoints = [(point["x"], point["y"]) for point in proposal["waypoints"]]
            waypoints[0], waypoints[-1] = tuple(layout["pad"]), tuple(layout["star"])
            node = {"waypoints": waypoints, "route": route, "outcome": outcome}
            seeds.append(node)
            feedback.append(simulation_feedback(node))
            consider(node, "gemini")
        planning = route_planner.refine_routes(seeds, layout)
        tested += planning["tested"]
        refined += planning["tested"]
        if planning["best"] is not None:
            consider(planning["best"], "gemini_predictive")
        refinement = planning["best"] or planning["feedback"]
        if refinement is not None:
            feedback.append(simulation_feedback(refinement, "predictive_refinement"))
    if best is None:
        return {"status": "unavailable", "message": "Gemini did not find a flyable route this round. Retry or continue to the next level.",
                "tested": tested, "refined": refined}
    return snapshot()


class BenchmarkJob:
    """A bounded background job. It owns detached data and never mutates a Game."""
    def __init__(self, layout):
        self.result = {"status": "pending", "message": "Gemini is planning and testing its routes..."}
        self.done = threading.Event()
        api_key, model = gemini_settings(DEFAULT_MODEL)
        if not _slots.acquire(blocking=False):
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
            initial = build_local_benchmark(layout)
            can_request = bool(api_key and re.fullmatch(r"gemini-[a-zA-Z0-9.\-]+", model))
            if initial is not None:
                self.result = {**initial, "planning": can_request}
            if can_request:
                self.result = build_benchmark(layout, api_key, model, initial=initial,
                                              on_result=self._publish)
            elif initial is None:
                self.result = {"status": "unavailable", "message": "No verified route found. Configure Gemini or try another level."}
        except AgentError as error:
            self._fail(str(error))
        except Exception:
            # Do not expose exception text: a provider error may contain credentials.
            self._fail("Gemini comparison is unavailable. You can still continue.")
        finally:
            self.done.set()
            _slots.release()

    def _publish(self, result):
        self.result = result

    def _fail(self, message):
        if self.result["status"] == "ready":
            self.result = {**self.result, "planning": False, "message": message}
        else:
            self.result = {"status": "unavailable", "message": message}
