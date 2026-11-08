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
  input: { mode: "IDLE", point: null },
  selectedInput: "OFF",
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
  onSnapshot(snapshot, inputEpoch) {
    const acceptInput = inputEpoch === state.inputEpoch;
    ui.applySnapshot(state, snapshot, acceptInput);
    if (acceptInput) controls.updateFreeDraw();
  },
  onError(message) {
    state.connectionError = message;
    state.input.mode = "IDLE";
    state.input.point = null;
    ui.setStatus(message);
    ui.showToast(message, 15000);
  },
});
const camera = createHandTracking({
  cameraVideo,
  cameraPreview: document.querySelector("#camera-preview"),
  getInputMode: () => state.selectedInput,
  isFreeDraw: () => state.freeDraw,
  setInputMode: (mode) => controls.setInputMode(mode),
  setStatus: ui.setStatus,
  showToast: ui.showToast,
});
const controls = createControls({
  gamePanel: document.querySelector(".game-panel"),
  handButton: document.querySelector("#camera-mode"),
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
    // Always send hand input, including null while the camera is off or unavailable.
    const event = { dt, paused: state.freeDraw, landmarks: null, cameraAspect: camera.aspectRatio };
    if (state.selectedInput === "HAND") {
      try {
        event.landmarks = camera.handLandmarks();
        event.cameraAspect = camera.aspectRatio;
      } catch (error) {
        controls.setInputMode("OFF");
        ui.setStatus("Hand tracking stopped. Select Start to try again.");
        ui.showToast(`Hand tracking stopped: ${error.message}`);
      }
    }
    client.queueEvent(event);
    client.syncGame(state.inputEpoch);
  }
  renderer.render(state, camera.active);
  requestAnimationFrame(frame);
}

ui.setStatus("Connecting to the Python game engine...");
client.connect();
requestAnimationFrame(frame);
