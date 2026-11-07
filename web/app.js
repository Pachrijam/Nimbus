const WIDTH = 960;
const HEIGHT = 600;
const MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task";
const MEDIAPIPE_VERSION = "1.2.2";

const canvas = document.querySelector("#game-canvas");
const ctx = canvas.getContext("2d");
const statusText = document.querySelector("#status-text");
const toast = document.querySelector("#toast");
const cameraVideo = document.querySelector("#camera-video");
const cameraPreview = document.querySelector("#camera-preview");
const canvasWrap = document.querySelector("#canvas-wrap");
const inputButtons = {
  mouse: document.querySelector("#mouse-mode"),
  hand: document.querySelector("#camera-mode"),
};

const input = { mode: "IDLE", point: null, drawing: false };

let handLandmarker = null;
let cameraStream = null;
let lastVideoTime = -1;
let lastHandLandmarks = null;
let cameraRequest = 0;
let handTrackingLoad = null;
let handTrackingStarting = false;
let cameraError = "";
let selectedInput = "MOUSE";
let toastTimeout = 0;
let previousFrameTime = performance.now();
let freeDraw = false;
let autopilot = false;
let debug = false;

// Python owns all game rules and state. JavaScript captures input and renders snapshots.
let game = null;
let session = null;
let pendingEvents = [];
let requestInFlight = false;
let connectionError = "";

async function api(endpoint, data) {
  const response = await fetch(`/api/${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
    signal: AbortSignal.timeout(10000),
  });
  if (!response.headers.get("content-type")?.includes("application/json")) {
    throw new Error("Start the website with python server.py, then open http://localhost:8000.");
  }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Python server unavailable.");
  return result;
}

function applySnapshot(snapshot) {
  const changed = game?.state !== snapshot.state || game?.level !== snapshot.level;
  game = snapshot;
  if (selectedInput === "HAND") Object.assign(input, game.cursor);
  document.querySelector(".mission-chip strong").textContent = String(game.level).padStart(2, "0");
  if (changed && !freeDraw) {
    const messages = {
      READY: "Draw from the drone to the destination. Release to launch.",
      DRAWING: "Keep drawing to the destination. Release to launch.",
      FLYING: "Drone launched. Avoid the storms!",
      LANDED: "Delivery complete! Next level loading...",
      CRASHED: "Route failed. Preparing another attempt...",
      INVALID: "Your route must end at the gold destination. Try again.",
    };
    setStatus(messages[game.state]);
  }
}

function failConnection(error) {
  connectionError = `${error.message} Reload the page to reconnect.`;
  pendingEvents = [];
  input.drawing = false;
  setStatus(connectionError);
  showToast(connectionError, 15000);
}

async function syncGame() {
  if (!session || requestInFlight || connectionError || !pendingEvents.length) return;
  requestInFlight = true;
  const events = pendingEvents;
  pendingEvents = [];
  try {
    const result = await api("update", { session, events });
    applySnapshot(result.game);
  } catch (error) {
    failConnection(error);
  } finally {
    requestInFlight = false;
  }
}

function queueEvent(event) {
  if (!session || connectionError) return;
  if (pendingEvents.length >= 120) {
    failConnection(new Error("Connection is too slow to keep up with the game."));
    return;
  }
  pendingEvents.push(event);
}

function retry() { queueEvent({ action: "retry" }); }
function nextLevel() { queueEvent({ action: "next" }); }

function roundedRect(context, x, y, width, height, radius) {
  context.beginPath();
  context.roundRect(x, y, width, height, radius);
}

function drawBackground() {
  const gradient = ctx.createLinearGradient(0, 0, 0, HEIGHT);
  gradient.addColorStop(0, "#83bad0");
  gradient.addColorStop(1, "#e5f0e9");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, WIDTH, HEIGHT);

  ctx.save();
  ctx.globalAlpha = 0.11;
  ctx.fillStyle = "#fff";
  for (let i = 0; i < 9; i += 1) {
    const x = (i * 193 + 60) % WIDTH;
    const y = 52 + ((i * 71) % 205);
    ctx.beginPath();
    ctx.ellipse(x, y, 80, 14, -0.07, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();

  ctx.strokeStyle = "rgba(255,255,255,.16)";
  ctx.lineWidth = 1;
  for (let x = 0; x < WIDTH; x += 48) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, HEIGHT);
    ctx.stroke();
  }
}

function drawCloud(cloud) {
  ctx.save();
  ctx.shadowColor = "rgba(40,70,78,.2)";
  ctx.shadowBlur = 12;
  ctx.fillStyle = "#f4f6ee";
  const circles = [
    [-0.46, 0.14, 0.56], [-0.22, -0.22, 0.63], [0.12, -0.26, 0.7],
    [0.43, -0.02, 0.54], [0.05, 0.17, 0.65],
  ];
  for (const [dx, dy, scale] of circles) {
    ctx.beginPath();
    ctx.arc(cloud.x + dx * cloud.r, cloud.y + dy * cloud.r, scale * cloud.r, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.shadowBlur = 0;
  ctx.strokeStyle = "rgba(58,91,105,.24)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(cloud.x, cloud.y, cloud.r, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();
}

function drawStar(x, y) {
  ctx.save();
  ctx.translate(x, y);
  ctx.shadowColor = "rgba(255,191,76,.6)";
  ctx.shadowBlur = 22;
  ctx.fillStyle = "#ffc758";
  ctx.beginPath();
  for (let i = 0; i < 10; i += 1) {
    const radius = i % 2 === 0 ? game.starRadius : game.starRadius * 0.46;
    const angle = -Math.PI / 2 + i * Math.PI / 5;
    const px = Math.cos(angle) * radius;
    const py = Math.sin(angle) * radius;
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();
  ctx.fill();
  ctx.shadowBlur = 0;
  ctx.strokeStyle = "rgba(133,86,20,.55)";
  ctx.lineWidth = 1.5;
  ctx.stroke();
  ctx.restore();
}

function drawPlane() {
  const plane = game.plane;
  ctx.save();
  ctx.translate(plane.x, plane.y);
  ctx.rotate(plane.heading);
  ctx.fillStyle = "#243746";
  ctx.strokeStyle = "rgba(255,255,255,.8)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(20, 0);
  ctx.lineTo(-13, -12);
  ctx.lineTo(-7, -2);
  ctx.lineTo(-16, 4);
  ctx.lineTo(-11, 9);
  ctx.lineTo(-4, 5);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

function drawPath(points, color, width = 3, dashed = false) {
  if (points.length < 2) return;
  ctx.save();
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  if (dashed) ctx.setLineDash([8, 8]);
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  for (let i = 1; i < points.length; i += 1) ctx.lineTo(points[i].x, points[i].y);
  ctx.stroke();
  ctx.restore();
}

function drawRoutePreview() {
  const { preview, tight } = game;
  for (let i = 1; i < preview.length; i += 1) {
    drawPath([preview[i - 1], preview[i]], tight[i] || tight[i - 1] ? "#e45d53" : "#fff", 4);
  }
}

function drawHud() {
  roundedRect(ctx, 18, 17, 282, 58, 8);
  ctx.fillStyle = "rgba(10,31,43,.75)";
  ctx.fill();
  ctx.fillStyle = "#fff";
  ctx.font = "600 15px 'DM Sans', sans-serif";
  ctx.fillText(`LEVEL ${String(game.level).padStart(2, "0")}`, 34, 41);
  ctx.fillStyle = "#ffe09a";
  ctx.fillText(`SCORE ${game.score}`, 153, 41);
  ctx.fillStyle = "rgba(255,255,255,.72)";
  ctx.font = "12px 'DM Sans', sans-serif";
  ctx.fillText(`ATTEMPTS ${game.tries}`, 34, 61);

  const start = { x: 220, y: 56 };
  const length = Math.hypot(game.wind.x, game.wind.y);
  const angle = length > 1 ? Math.atan2(game.wind.y, game.wind.x) : 0;
  const end = { x: start.x + Math.cos(angle) * (18 + length * 0.35), y: start.y + Math.sin(angle) * (18 + length * 0.35) };
  ctx.strokeStyle = "rgba(255,255,255,.8)";
  ctx.fillStyle = "rgba(255,255,255,.8)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(start.x, start.y);
  ctx.lineTo(end.x, end.y);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(end.x, end.y);
  ctx.lineTo(end.x - 6 * Math.cos(angle - 0.5), end.y - 6 * Math.sin(angle - 0.5));
  ctx.lineTo(end.x - 6 * Math.cos(angle + 0.5), end.y - 6 * Math.sin(angle + 0.5));
  ctx.closePath();
  ctx.fill();
  ctx.font = "10px 'DM Mono', monospace";
  ctx.fillText("WIND", 240, 60);
}

function drawMessage(text) {
  ctx.save();
  ctx.fillStyle = "rgba(8,20,29,.26)";
  ctx.fillRect(0, 0, WIDTH, HEIGHT);
  roundedRect(ctx, WIDTH / 2 - 205, HEIGHT / 2 - 46, 410, 92, 12);
  ctx.fillStyle = "rgba(10,26,38,.9)";
  ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,.27)";
  ctx.stroke();
  ctx.fillStyle = text === "DELIVERED!" ? "#ffda8b" : "#fff";
  ctx.font = "600 30px 'Space Grotesk', sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(text, WIDTH / 2, HEIGHT / 2 + 10);
  ctx.restore();
}

function drawCursor() {
  if (!input.point) return;
  ctx.beginPath();
  ctx.arc(input.point.x, input.point.y, input.mode === "DRAW" ? 7 : 10, 0, Math.PI * 2);
  ctx.fillStyle = input.mode === "DRAW" ? "#e6534a" : "rgba(255,255,255,.75)";
  ctx.strokeStyle = "#263f4c";
  ctx.lineWidth = input.mode === "DRAW" ? 0 : 2;
  if (input.mode === "DRAW") ctx.fill();
  else ctx.stroke();
}

function drawFreeDraw() {
  ctx.fillStyle = "rgba(7,18,29,.74)";
  ctx.fillRect(0, 0, WIDTH, HEIGHT);
  if (cameraStream && cameraVideo.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
    ctx.save();
    ctx.translate(WIDTH, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(cameraVideo, 0, 0, WIDTH, HEIGHT);
    ctx.restore();
  } else {
    ctx.fillStyle = "rgba(220,236,237,.12)";
    ctx.font = "20px 'DM Sans', sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("Enable your camera to draw over a live view", WIDTH / 2, HEIGHT / 2);
  }
  ctx.fillStyle = "rgba(7,18,29,.48)";
  ctx.fillRect(0, 0, WIDTH, HEIGHT);
  for (const stroke of freeInk) drawPath(stroke, "#ff6d68", 8);
  ctx.textAlign = "left";
  ctx.fillStyle = "#fff";
  ctx.font = "600 15px 'DM Sans', sans-serif";
  ctx.fillText("FREE DRAW  ·  drag to draw  ·  C to clear", 24, 35);
}

let freeInk = [];
let activeStroke = null;

function render() {
  if (!game || connectionError) {
    drawBackground();
    drawMessage(connectionError ? "CONNECTION LOST" : "CONNECTING...");
    return;
  }
  if (freeDraw) {
    drawFreeDraw();
    return;
  }
  drawBackground();
  ctx.fillStyle = "#578b70";
  ctx.fillRect(game.pad.x - 33, game.pad.y + 14, 66, 9);
  ctx.fillStyle = "rgba(255,255,255,.85)";
  ctx.fillRect(game.pad.x - 40, game.pad.y + 24, 80, 3);
  drawStar(game.star.x, game.star.y);
  for (const cloud of game.clouds) drawCloud(cloud);

  if (game.state === "DRAWING") drawRoutePreview();
  else if (game.state === "FLYING") drawPath(game.path, "rgba(255,255,255,.86)", 3, true);

  if (game.trail.length > 1) {
    for (let i = 1; i < game.trail.length; i += 1) {
      const alpha = i / game.trail.length;
      ctx.strokeStyle = `rgba(255,255,255,${alpha * 0.7})`;
      ctx.lineWidth = Math.max(1, alpha * 3);
      ctx.beginPath();
      ctx.moveTo(game.trail[i - 1].x, game.trail[i - 1].y);
      ctx.lineTo(game.trail[i].x, game.trail[i].y);
      ctx.stroke();
    }
  }
  if (autopilot && game.plane.target) {
    ctx.strokeStyle = "#e94b4b";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(game.plane.x, game.plane.y);
    ctx.lineTo(game.plane.target.x, game.plane.target.y);
    ctx.stroke();
    ctx.fillStyle = "#e94b4b";
    ctx.beginPath();
    ctx.arc(game.plane.target.x, game.plane.target.y, 6, 0, Math.PI * 2);
    ctx.fill();
  }
  drawPlane();
  drawHud();
  drawCursor();

  if (game.state === "READY") {
    ctx.fillStyle = "rgba(14,39,50,.78)";
    roundedRect(ctx, WIDTH / 2 - 171, HEIGHT - 55, 342, 32, 16);
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.font = "12px 'DM Sans', sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("Start at the drone · release to launch", WIDTH / 2, HEIGHT - 34);
    ctx.textAlign = "left";
  } else if (game.state === "LANDED") drawMessage("DELIVERED!");
  else if (game.state === "CRASHED") drawMessage("ROUTE FAILED");
  else if (game.state === "INVALID") drawMessage("REACH THE DESTINATION");

  if (debug) {
    ctx.fillStyle = "#0a1926";
    ctx.font = "12px 'DM Mono', monospace";
    ctx.fillText(`${game.state} · ${input.mode} · ${input.mode === "DRAW" ? "drawing" : "idle"}`, 18, HEIGHT - 17);
  }
}

function setStatus(message) {
  statusText.textContent = message;
}

function showToast(message, duration = 3200) {
  toast.textContent = message;
  toast.classList.remove("hidden");
  window.clearTimeout(toastTimeout);
  toastTimeout = window.setTimeout(() => toast.classList.add("hidden"), duration);
}

function canvasPoint(event) {
  const bounds = canvas.getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(WIDTH, (event.clientX - bounds.left) * WIDTH / bounds.width)),
    y: Math.max(0, Math.min(HEIGHT, (event.clientY - bounds.top) * HEIGHT / bounds.height)),
  };
}

function setInputMode(mode) {
  if (mode !== "HAND") stopCamera();
  selectedInput = mode;
  input.mode = "IDLE";
  input.point = null;
  input.drawing = false;
  activeStroke = null;
  for (const [key, button] of Object.entries(inputButtons)) {
    const active = (key === "mouse" && mode !== "HAND") || (key === "hand" && mode === "HAND");
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  }
}

function stopCamera() {
  lastVideoTime = -1;
  lastHandLandmarks = null;
  cameraRequest += 1;
  handTrackingStarting = false;
  if (cameraStream) cameraStream.getTracks().forEach((track) => track.stop());
  cameraStream = null;
  cameraVideo.pause();
  cameraVideo.srcObject = null;
  cameraPreview.classList.add("hidden");
}

async function enableCamera(request) {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error("Camera access requires HTTPS or localhost and a browser that supports webcam input.");
  }
  if (!cameraStream) {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
    });
    // A permission prompt can finish after the user has switched back to mouse.
    if (request !== cameraRequest) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }
    cameraStream = stream;
    cameraVideo.srcObject = cameraStream;
    await cameraVideo.play();
    if (request !== cameraRequest) return;
    cameraPreview.classList.remove("hidden");
  }
}

async function enableHandTracking() {
  if (selectedInput === "HAND" || handTrackingStarting) return;
  const request = ++cameraRequest;
  handTrackingStarting = true;
  setStatus("Requesting camera access…");
  try {
    await enableCamera(request);
    if (request !== cameraRequest) return;
    if (!handLandmarker) {
      setStatus("Loading hand-tracking model…");
      if (!handTrackingLoad) {
        handTrackingLoad = (async () => {
          const vision = await import(`https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MEDIAPIPE_VERSION}`);
          const fileset = await vision.FilesetResolver.forVisionTasks(
            `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MEDIAPIPE_VERSION}/wasm`,
          );
          const options = {
            baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
            runningMode: "VIDEO",
            numHands: 1,
          };
          try {
            handLandmarker = await vision.HandLandmarker.createFromOptions(fileset, options);
          } catch {
            handLandmarker = await vision.HandLandmarker.createFromOptions(fileset, {
              ...options,
              baseOptions: { modelAssetPath: MODEL_URL, delegate: "CPU" },
            });
          }
        })().finally(() => {
          handTrackingLoad = null;
        });
      }
      await handTrackingLoad;
    }
    if (request !== cameraRequest) return;
    handTrackingStarting = false;
    cameraError = "";
    setInputMode("HAND");
    setStatus("Hand tracking is on. Raise one finger to draw; raise two to release.");
  } catch (error) {
    if (request !== cameraRequest) return;
    cameraError = error instanceof Error ? error.message : String(error);
    setInputMode("MOUSE");
    setStatus("Hand tracking could not start. Mouse drawing is ready.");
    showToast(`Camera/hand tracking unavailable: ${cameraError}`);
  }
}

function handLandmarks() {
  if (!cameraStream || !handLandmarker || cameraVideo.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return null;
  // Display refresh can be faster than the camera; infer only on new video frames.
  if (cameraVideo.currentTime === lastVideoTime) return lastHandLandmarks;
  const result = handLandmarker.detectForVideo(cameraVideo, performance.now());
  lastVideoTime = cameraVideo.currentTime;
  lastHandLandmarks = result.landmarks?.[0]?.map(({ x, y }) => ({ x, y })) ?? null;
  return lastHandLandmarks;
}

function frame(now) {
  const dt = Math.min((now - previousFrameTime) / 1000, 0.05);
  previousFrameTime = now;
  if (session && !connectionError) {
    const event = { dt, paused: freeDraw, mode: input.mode, point: input.point };
    if (selectedInput === "HAND") {
      try {
        event.landmarks = handLandmarks();
      } catch (error) {
        setInputMode("MOUSE");
        showToast(`Hand tracking stopped: ${error.message}`);
      }
    } else {
      event.mode = input.drawing ? "DRAW" : (input.point ? "HOVER" : "IDLE");
      input.mode = event.mode;
    }
    queueEvent(event);
    if (freeDraw) {
      if (input.mode === "DRAW" && input.point) {
        if (!activeStroke) { activeStroke = []; freeInk.push(activeStroke); }
        activeStroke.push({ ...input.point });
      } else activeStroke = null;
    }
    syncGame();
  }
  render();
  requestAnimationFrame(frame);
}

canvas.addEventListener("pointermove", (event) => {
  if (selectedInput === "HAND") return;
  input.point = canvasPoint(event);
  if (input.drawing) input.mode = "DRAW";
});
canvas.addEventListener("pointerdown", (event) => {
  if (selectedInput === "HAND") return;
  event.preventDefault();
  canvas.setPointerCapture(event.pointerId);
  input.point = canvasPoint(event);
  input.drawing = true;
  input.mode = "DRAW";
});
canvas.addEventListener("pointerup", (event) => {
  if (selectedInput === "HAND") return;
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
inputButtons.hand.addEventListener("click", enableHandTracking);
document.querySelector("#free-draw").addEventListener("click", (event) => {
  freeDraw = !freeDraw;
  activeStroke = null;
  event.currentTarget.classList.toggle("active", freeDraw);
  setStatus(freeDraw ? "Free draw: drag anywhere to sketch. Press C to clear." : "Drag from the drone to draw a route. Release to launch.");
});
document.querySelector("#autopilot").addEventListener("click", (event) => {
  autopilot = !autopilot;
  event.currentTarget.classList.toggle("active", autopilot);
});
document.querySelector("#clear").addEventListener("click", () => {
  freeInk = [];
  activeStroke = null;
  if (!freeDraw && game?.state !== "FLYING") retry();
});
document.querySelector("#fullscreen").addEventListener("click", async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await canvasWrap.requestFullscreen();
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
  else if (key === "v") document.querySelector("#autopilot").click();
  else if (key === "c") {
    freeInk = [];
    activeStroke = null;
    if (!freeDraw && game?.state !== "FLYING") retry();
  } else if (key === "d") debug = !debug;
  else if (key === "f") document.querySelector("#fullscreen").click();
  else if (key === "m") inputButtons.mouse.click();
});

setStatus("Connecting to the Python game engine...");
api("session", {}).then((result) => {
  session = result.session;
  applySnapshot(result.game);
}).catch(failConnection);
requestAnimationFrame(frame);
