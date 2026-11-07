import { createGameClient } from "./game-client.js";
import { createHandTracking } from "./camera.js";
import { createControls } from "./controls.js";
import { createRenderer } from "./renderer.js";
import { createUI } from "./ui.js";

const canvas = document.querySelector("#game-canvas");
const cameraVideo = document.querySelector("#camera-video");

// Python owns game rules and snapshots; this state holds the browser's view and input.
const state = {
  game: null,
  connectionError: "",
  input: { mode: "IDLE", point: null, drawing: false },
  selectedInput: "MOUSE",
  freeDraw: false,
  freeInk: [],
  activeStroke: null,
  autopilot: false,
  debug: false,
};

const ui = createUI({
  canvas,
  statusText: document.querySelector("#status-text"),
  toast: document.querySelector("#toast"),
});
const client = createGameClient({
  onSnapshot: (snapshot) => ui.applySnapshot(state, snapshot),
  onError(message) {
    state.connectionError = message;
    state.input.drawing = false;
    ui.setStatus(message);
    ui.showToast(message, 15000);
  },
});
const camera = createHandTracking({
  cameraVideo,
  cameraPreview: document.querySelector("#camera-preview"),
  getInputMode: () => state.selectedInput,
  setInputMode: (mode) => controls.setInputMode(mode),
  setStatus: ui.setStatus,
  showToast: ui.showToast,
});
const controls = createControls({
  canvas,
  gamePanel: document.querySelector(".game-panel"),
  inputButtons: {
    mouse: document.querySelector("#mouse-mode"),
    hand: document.querySelector("#camera-mode"),
  },
  state,
  camera,
  queueEvent: client.queueEvent,
  setStatus: ui.setStatus,
  showToast: ui.showToast,
});
const renderer = createRenderer({ canvas, cameraVideo });
let previousFrameTime = performance.now();

function frame(now) {
  const dt = Math.min((now - previousFrameTime) / 1000, 0.05);
  previousFrameTime = now;
  if (client.connected) {
    const { input } = state;
    const event = { dt, paused: state.freeDraw, mode: input.mode, point: input.point };
    if (state.selectedInput === "HAND") {
      try {
        event.landmarks = camera.handLandmarks();
        event.cameraAspect = camera.aspectRatio;
      } catch (error) {
        controls.setInputMode("MOUSE");
        ui.showToast(`Hand tracking stopped: ${error.message}`);
      }
    } else {
      event.mode = input.drawing ? "DRAW" : (input.point ? "HOVER" : "IDLE");
      input.mode = event.mode;
    }
    client.queueEvent(event);
    controls.updateFreeDraw();
    client.syncGame();
  }
  renderer.render(state, camera.active);
  requestAnimationFrame(frame);
}

ui.setStatus("Connecting to the Python game engine...");
client.connect();
requestAnimationFrame(frame);
