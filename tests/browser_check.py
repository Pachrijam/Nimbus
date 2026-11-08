"""Browser regression tests for the free-draw UX."""

import os
from unittest.mock import patch

from browser import createUI, createControls, createRenderer
from game import Session
from gemini import validate_route


def main():
    with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
        session = Session()
        route = {"waypoints": [{"x": x, "y": y} for x, y in
                              [session.game.pad, (240, 180), (480, 180), (680, 200), session.game.star]]}
        session.game.path = validate_route(route, session.game.level_layout())
        session.game.state = "FLYING"
        session.game.tries = 1

    # Browser tests exercise the draw controls and free-draw gesture logic.
    ui = createUI({"canvas": None, "statusText": None, "toast": None})
    state = {"game": None, "input": {"mode": "IDLE", "point": None}, "selectedInput": "HAND", "freeDraw": False, "freeInk": [], "debug": False, "autopilot": False}
    controls = createControls({"gamePanel": None, "handButton": None, "state": state, "camera": {"stopCamera": lambda: None, "enableHandTracking": lambda: None}, "queueEvent": lambda event: None, "setStatus": ui.setStatus, "showToast": ui.showToast})
    renderer = createRenderer({"canvas": None, "cameraVideo": None})

    # Free draw should hide results while active and keep game shortcuts disabled.
    state["freeDraw"] = True
    controls.updateFreeDraw()
    assert state["freeDraw"]
    assert not ui.toast
    renderer.render(state, False)
