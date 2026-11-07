import { WIDTH, HEIGHT } from "./config.js";

export function createControls({ canvas, gamePanel, inputButtons, state, camera, queueEvent, setStatus, showToast }) {
  const { input } = state;

  function retry() { queueEvent({ action: "retry" }); }
  function nextLevel() { queueEvent({ action: "next" }); }

  function canvasPoint(event) {
    const bounds = canvas.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(WIDTH, (event.clientX - bounds.left) * WIDTH / bounds.width)),
      y: Math.max(0, Math.min(HEIGHT, (event.clientY - bounds.top) * HEIGHT / bounds.height)),
    };
  }

  function setInputMode(mode) {
    if (mode !== "HAND") camera.stopCamera();
    state.selectedInput = mode;
    input.mode = "IDLE";
    input.point = null;
    input.drawing = false;
    state.activeStroke = null;
    for (const [key, button] of Object.entries(inputButtons)) {
      const active = (key === "mouse" && mode !== "HAND") || (key === "hand" && mode === "HAND");
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    }
  }

  canvas.addEventListener("pointermove", (event) => {
    if (state.selectedInput === "HAND") return;
    input.point = canvasPoint(event);
    if (input.drawing) input.mode = "DRAW";
  });
  canvas.addEventListener("pointerdown", (event) => {
    if (state.selectedInput === "HAND") return;
    event.preventDefault();
    canvas.setPointerCapture(event.pointerId);
    input.point = canvasPoint(event);
    input.drawing = true;
    input.mode = "DRAW";
  });
  canvas.addEventListener("pointerup", (event) => {
    if (state.selectedInput === "HAND") return;
    input.point = canvasPoint(event);
    input.drawing = false;
    input.mode = "HOVER";
  });
  canvas.addEventListener("pointercancel", () => {
    input.drawing = false;
    input.mode = "IDLE";
  });

  inputButtons.mouse.addEventListener("click", () => {
    setInputMode("MOUSE");
    setStatus("Drag from the drone to draw a route. Release to launch.");
  });
  inputButtons.hand.addEventListener("click", () => camera.enableHandTracking());
  function setFreeDraw(enabled) {
    state.freeDraw = enabled;
    state.activeStroke = null;
    input.drawing = false;
    input.mode = "IDLE";
    input.point = null;
    const toggle = document.querySelector("#free-draw");
    toggle.classList.toggle("active", state.freeDraw);
    toggle.setAttribute("aria-pressed", String(state.freeDraw));
    toggle.title = state.freeDraw ? "Back to game (P)" : "Toggle free draw (P)";
    document.querySelector("#exit-free-draw").classList.toggle("hidden", !state.freeDraw);
    setStatus(state.freeDraw
      ? "Free draw: sketch anywhere. C clears; Back to game, Esc, or P exits."
      : state.selectedInput === "HAND"
        ? "Draw to the gold destination with one finger, then hold up two fingers to launch."
        : "Drag from the drone to draw a route. Release to launch.");
  }

  document.querySelector("#free-draw").addEventListener("click", () => setFreeDraw(!state.freeDraw));
  document.querySelector("#exit-free-draw").addEventListener("click", () => setFreeDraw(false));
  document.querySelector("#autopilot").addEventListener("click", (event) => {
    state.autopilot = !state.autopilot;
    event.currentTarget.classList.toggle("active", state.autopilot);
  });
  function clearDrawing() {
    state.freeInk = [];
    state.activeStroke = null;
    if (!state.freeDraw && state.game?.state !== "FLYING") retry();
  }

  document.querySelector("#clear").addEventListener("click", clearDrawing);
  document.querySelector("#fullscreen").addEventListener("click", async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await gamePanel.requestFullscreen();
    } catch (error) {
      showToast(`Could not enter fullscreen: ${error.message}`);
    }
  });

  window.addEventListener("keydown", (event) => {
    if (event.repeat) return;
    const key = event.key.toLowerCase();
    if (key === "r") retry();
    else if (key === "n") nextLevel();
    else if (key === "p") document.querySelector("#free-draw").click();
    else if (key === "escape" && state.freeDraw) setFreeDraw(false);
    else if (key === "v") document.querySelector("#autopilot").click();
    else if (key === "c") clearDrawing();
    else if (key === "d") state.debug = !state.debug;
    else if (key === "f") document.querySelector("#fullscreen").click();
    else if (key === "m") inputButtons.mouse.click();
  });

  function updateFreeDraw() {
    if (!state.freeDraw) return;
    if (input.mode === "DRAW" && input.point) {
      if (!state.activeStroke) {
        state.activeStroke = [];
        state.freeInk.push(state.activeStroke);
      }
      state.activeStroke.push({ ...input.point });
    } else state.activeStroke = null;
  }

  return { setInputMode, updateFreeDraw };
}
