export function createControls({ gamePanel, handButton, state, camera, queueEvent, setStatus, showToast }) {
  const { input } = state;

  function retry() { queueEvent({ action: "retry" }); }
  function nextLevel() { queueEvent({ action: "next" }); }

  function setInputMode(mode) {
    if (mode !== "HAND") camera.stopCamera();
    state.selectedInput = mode;
    input.mode = "IDLE";
    input.point = null;
    state.activeStroke = null;
    handButton.classList.toggle("active", mode === "HAND");
    handButton.setAttribute("aria-pressed", String(mode === "HAND"));
  }

  handButton.addEventListener("click", () => camera.enableHandTracking());
  function setFreeDraw(enabled) {
    state.freeDraw = enabled;
    state.activeStroke = null;
    input.mode = "IDLE";
    input.point = null;
    const toggle = document.querySelector("#free-draw");
    toggle.classList.toggle("active", state.freeDraw);
    toggle.setAttribute("aria-pressed", String(state.freeDraw));
    toggle.title = state.freeDraw ? "Back to game (P)" : "Toggle free draw (P)";
    document.querySelector("#exit-free-draw").classList.toggle("hidden", !state.freeDraw);
    setStatus(state.selectedInput !== "HAND"
      ? "Enable hand tracking to draw with your camera."
      : state.freeDraw
        ? "Free draw: sketch with one finger. C clears; Back to game, Esc, or P exits."
        : "Draw a route from the drone with one finger, then hold up two fingers to launch.");
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
