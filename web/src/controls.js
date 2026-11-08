import { createFreeDraw, PEN_COLORS } from "./free-draw.js";

export function createControls({ gamePanel, handButton, state, camera, queueEvent, setStatus, showToast }) {
  const { input } = state;
  const drawing = createFreeDraw(state);
  state.inputEpoch = 0;
  const palette = document.querySelector("#pen-colors");
  for (const color of PEN_COLORS) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "pen-color";
    button.style.setProperty("--pen-color", color.value);
    button.title = color.name;
    button.setAttribute("aria-label", `${color.name} pen`);
    button.addEventListener("click", () => { drawing.setColor(color.value); updatePenTools(); });
    palette.append(button);
  }
  function updatePenTools() {
    [...palette.children].forEach((button, index) => {
      button.setAttribute("aria-pressed", String(PEN_COLORS[index].value === state.penColor));
    });
    document.querySelector("#undo-drawing").disabled = !state.freeInk.length;
  }
  updatePenTools();
  document.querySelector("#pen-size").addEventListener("change", event => drawing.setSize(Number(event.target.value)));
  document.querySelector("#undo-drawing").addEventListener("click", () => {
    drawing.undo();
    updatePenTools();
  });

  function retry() { if (!state.freeDraw) queueEvent({ action: "retry" }); }
  function nextLevel() { if (!state.freeDraw) queueEvent({ action: "next" }); }
  document.querySelector("#challenge-retry").addEventListener("click", retry);
  document.querySelector("#challenge-next").addEventListener("click", nextLevel);
  document.querySelector("#gemini-replay").addEventListener("click", () => {
    if (state.game?.state !== "LANDED" || state.game.comparison?.status !== "ready") return;
    state.geminiReplay = (state.geminiReplay ?? 0) + 1;
    document.querySelector("#game-canvas").scrollIntoView({ block: "nearest", behavior: "smooth" });
    setStatus("Replaying Gemini's flight in purple. Your flight stays orange.");
  });

  function setInputMode(mode) {
    if (mode !== "HAND") camera.stopCamera();
    state.selectedInput = mode;
    input.mode = "IDLE";
    input.point = null;
    drawing.endStroke();
    state.inputEpoch += 1;
    handButton.classList.toggle("active", mode === "HAND");
    handButton.setAttribute("aria-pressed", String(mode === "HAND"));
  }

  handButton.addEventListener("click", () => camera.enableHandTracking());
  function stopTracking() {
    setInputMode("OFF");
    setStatus("Camera stopped. Select Start or press S to resume hand tracking.");
  }
  document.querySelector("#camera-stop").addEventListener("click", stopTracking);
  function setFreeDraw(enabled) {
    state.freeDraw = enabled;
    drawing.endStroke();
    state.inputEpoch += 1;
    input.mode = "IDLE";
    input.point = null;
    const toggle = document.querySelector("#free-draw");
    toggle.classList.toggle("active", state.freeDraw);
    toggle.setAttribute("aria-pressed", String(state.freeDraw));
    toggle.title = state.freeDraw ? "Back to game (P)" : "Toggle free draw (P)";
    document.querySelector("#exit-free-draw").classList.toggle("hidden", !state.freeDraw);
    document.querySelector("#free-draw-tools").classList.toggle("hidden", !enabled);
    document.querySelector("#autopilot").disabled = enabled;
    document.querySelector("#comparison").classList.toggle("hidden", enabled || !state.game?.comparison);
    document.querySelector("#game-canvas").setAttribute("aria-label", enabled
      ? "Free draw canvas. One finger draws; two or more fingers change color."
      : "Game field. Draw from the drone with one finger; hold up two or more fingers to launch.");
    document.querySelector(".quick-controls").innerHTML = enabled
      ? "<kbd>U</kbd><span>Undo</span><kbd>C</kbd><span>Clear</span><kbd>P</kbd><span>Back to game</span>"
      : "<kbd>R</kbd><span>Retry</span><kbd>N</kbd><span>Next level</span><kbd>P</kbd><span>Free draw</span>";
    const gameStatus = {
      DRAWING: "Continue your route with one finger; hold up two or more fingers to launch.",
      FLYING: "Flight resumed. Drone on its way!",
      LANDED: "Delivery complete! R to retry this level, N to continue.",
      CRASHED: "Route failed. Preparing another attempt...",
    };
    setStatus(state.selectedInput !== "HAND"
      ? "Select Start to draw with your camera."
      : state.freeDraw
        ? "Free draw: one finger draws; two or more change color. U undoes, C clears; Esc or P returns."
        : gameStatus[state.game?.state] ?? "Draw a route from the drone with one finger, then hold up two or more fingers to launch.");
  }

  document.querySelector("#free-draw").addEventListener("click", () => setFreeDraw(!state.freeDraw));
  document.querySelector("#exit-free-draw").addEventListener("click", () => setFreeDraw(false));
  document.querySelector("#autopilot").addEventListener("click", (event) => {
    state.autopilot = !state.autopilot;
    event.currentTarget.classList.toggle("active", state.autopilot);
  });
  function clearDrawing() {
    if (state.freeDraw) {
      drawing.clear();
      updatePenTools();
    }
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
    if (event.repeat || event.ctrlKey || event.metaKey || event.altKey) return;
    const target = event.target;
    if (target?.isContentEditable || target?.closest?.("input, select, textarea, [contenteditable=true]")
        || ["INPUT", "TEXTAREA", "SELECT"].includes(target?.tagName)) return;
    const key = event.key.toLowerCase();
    if (key === "s") { event.preventDefault(); camera.enableHandTracking(); }
    else if (key === "x") { event.preventDefault(); stopTracking(); }
    else if (key === "r") retry();
    else if (key === "n") nextLevel();
    else if (key === "p") document.querySelector("#free-draw").click();
    else if (key === "escape" && state.freeDraw) setFreeDraw(false);
    else if (key === "v") document.querySelector("#autopilot").click();
    else if (key === "c") clearDrawing();
    else if (key === "u" && state.freeDraw) document.querySelector("#undo-drawing").click();
    else if (key === "d") state.debug = !state.debug;
    else if (key === "f") document.querySelector("#fullscreen").click();
  });

  function updateFreeDraw() {
    drawing.update();
    updatePenTools();
  }

  return { setInputMode, updateFreeDraw };
}
