const WIDTH = 960;
const HEIGHT = 600;
const SPEED = 180;
const LOOKAHEAD = 60;
const STEER_GAIN = 4;
const MAX_TURN = 2.5;
const MIN_PATH_POINTS = 10;
const START_RADIUS = 42;
const STAR_RADIUS = 28;
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
const handState = { mode: "IDLE", candidate: "IDLE", count: 0, smooth: null };
let handLandmarker = null;
let cameraStream = null;
let cameraError = "";
let selectedInput = "MOUSE";
let toastTimeout = 0;
let previousFrameTime = performance.now();
let freeDraw = false;
let autopilot = false;
let debug = false;

const game = {
  level: 1,
  score: 0,
  tries: 0,
  state: "READY",
  timer: 0,
  rawPath: [],
  path: [],
  trail: [],
  clouds: [],
  wind: { x: 0, y: 0 },
  plane: null,
  pad: { x: 90, y: HEIGHT / 2 },
  star: { x: WIDTH - 120, y: HEIGHT / 2 },
};

function randomBetween(min, max) {
  return min + Math.random() * (max - min);
}

function distance(a, b) {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

function makeLevel() {
  game.pad = { x: 90, y: HEIGHT / 2 };
  game.star = { x: WIDTH - 120, y: randomBetween(140, HEIGHT - 140) };
  game.wind = game.level < 2
    ? { x: 0, y: 0 }
    : { x: randomBetween(-1, 1) * Math.min(24 + game.level * 5, 60), y: randomBetween(-1, 1) * Math.min(12 + game.level * 3, 34) };
  const count = Math.min(1 + Math.floor((game.level - 1) / 2), 5);
  game.clouds = [];

  for (let i = 0; i < count; i += 1) {
    let cloud;
    for (let attempt = 0; attempt < 100; attempt += 1) {
      cloud = {
        x: randomBetween(270, 700),
        y: randomBetween(90, HEIGHT - 90),
        r: randomBetween(46, 67),
        vx: game.level < 3 ? 0 : randomBetween(-10, 10) * Math.min(game.level - 2, 4),
      };
      const clearOfEndpoints = distance(cloud, game.pad) > cloud.r + 105 && distance(cloud, game.star) > cloud.r + 90;
      const clearOfClouds = game.clouds.every((other) => distance(cloud, other) > cloud.r + other.r + 35);
      if (clearOfEndpoints && clearOfClouds) break;
    }
    game.clouds.push(cloud);
  }
}

function makePlane() {
  return { x: game.pad.x, y: game.pad.y, heading: 0, speed: SPEED, index: 0, target: null };
}

function retry() {
  game.state = "READY";
  game.timer = 0;
  game.rawPath = [];
  game.path = [];
  game.trail = [];
  game.plane = makePlane();
  game.clouds = game.clouds.map((cloud) => ({ ...cloud }));
}

function nextLevel() {
  game.level += 1;
  makeLevel();
  retry();
  setStatus(`Level ${game.level}: draw a route from the drone to the destination.`);
}

function pathLength(points) {
  let length = 0;
  for (let i = 1; i < points.length; i += 1) length += distance(points[i - 1], points[i]);
  return length;
}

function chaikin(points, iterations = 2) {
  let result = points.map((point) => ({ ...point }));
  for (let iteration = 0; iteration < iterations && result.length > 2; iteration += 1) {
    const smooth = [result[0]];
    for (let i = 0; i < result.length - 1; i += 1) {
      const a = result[i];
      const b = result[i + 1];
      smooth.push({ x: 0.75 * a.x + 0.25 * b.x, y: 0.75 * a.y + 0.25 * b.y });
      smooth.push({ x: 0.25 * a.x + 0.75 * b.x, y: 0.25 * a.y + 0.75 * b.y });
    }
    smooth.push(result[result.length - 1]);
    result = smooth;
  }
  return result;
}

function resample(points, spacing = 8) {
  if (points.length < 2) return points.map((point) => ({ ...point }));
  const result = [{ ...points[0] }];
  let carry = 0;
  let previous = { ...points[0] };
  for (let i = 1; i < points.length; i += 1) {
    const end = points[i];
    let segmentLength = distance(previous, end);
    if (segmentLength < 1e-8) continue;
    while (carry + segmentLength >= spacing) {
      const amount = (spacing - carry) / segmentLength;
      previous = {
        x: previous.x + amount * (end.x - previous.x),
        y: previous.y + amount * (end.y - previous.y),
      };
      result.push(previous);
      segmentLength = distance(previous, end);
      carry = 0;
    }
    carry += segmentLength;
    previous = { ...end };
  }
  const last = points[points.length - 1];
  if (distance(result[result.length - 1], last) > 1) result.push({ ...last });
  return result;
}

function tightTurns(points, minRadius) {
  const tight = Array(points.length).fill(false);
  for (let i = 1; i < points.length - 1; i += 1) {
    const a = points[i - 1];
    const b = points[i];
    const c = points[i + 1];
    const ab = distance(a, b);
    const bc = distance(b, c);
    const ca = distance(c, a);
    const cross = Math.abs((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x));
    if (cross > 1e-5 && (ab * bc * ca) / (2 * cross) < minRadius) tight[i] = true;
  }
  return tight;
}

function wrapAngle(angle) {
  return (angle + Math.PI) % (2 * Math.PI) - Math.PI;
}

function stepPlane(dt) {
  const plane = game.plane;
  const lastSearch = Math.min(game.path.length - 1, plane.index + 20);
  let closest = plane.index;
  for (let i = plane.index + 1; i <= lastSearch; i += 1) {
    if (distance(plane, game.path[i]) < distance(plane, game.path[closest])) closest = i;
  }
  plane.index = closest;

  if (plane.index < game.path.length - 1) {
    let target = game.path[game.path.length - 1];
    for (let i = plane.index; i < game.path.length; i += 1) {
      if (distance(plane, game.path[i]) >= LOOKAHEAD) {
        target = game.path[i];
        break;
      }
    }
    plane.target = target;
    const desired = Math.atan2(target.y - plane.y, target.x - plane.x);
    const turn = Math.max(-MAX_TURN, Math.min(MAX_TURN, STEER_GAIN * wrapAngle(desired - plane.heading)));
    plane.heading += turn * dt;
  } else {
    plane.target = null;
  }

  plane.x += (plane.speed * Math.cos(plane.heading) + game.wind.x) * dt;
  plane.y += (plane.speed * Math.sin(plane.heading) + game.wind.y) * dt;
}

function startDrawing(point) {
  if (game.state !== "READY" || !point || distance(point, game.plane) > START_RADIUS) {
    if (game.state === "READY" && point) setStatus("Start your route near the drone on the launch pad.");
    return;
  }
  game.rawPath = [{ ...point }];
  game.state = "DRAWING";
  setStatus("Keep dragging to plan your route. Release to launch.");
}

function finishDrawing() {
  if (game.rawPath.length < MIN_PATH_POINTS) {
    game.rawPath = [];
    game.state = "READY";
    setStatus("Route too short. Start at the drone and draw a longer route.");
    return;
  }
  game.path = resample(chaikin(game.rawPath));
  game.tries += 1;
  game.state = "FLYING";
  setStatus("Drone launched. Reach the destination without hitting a storm.");
}

function updateGame(mode, point, dt) {
  if (game.state === "READY") {
    if (mode === "DRAW" && point) startDrawing(point);
  } else if (game.state === "DRAWING") {
    if (mode === "DRAW" && point) {
      const previous = game.rawPath[game.rawPath.length - 1];
      if (distance(previous, point) >= 3) game.rawPath.push({ ...point });
    } else {
      finishDrawing();
    }
  } else if (game.state === "FLYING") {
    stepPlane(dt);
    for (const cloud of game.clouds) cloud.x += cloud.vx * dt;
    game.trail.push({ x: game.plane.x, y: game.plane.y });
    if (game.trail.length > 60) game.trail.shift();

    if (distance(game.plane, game.star) <= STAR_RADIUS) {
      const bonus = Math.max(0, Math.round(300 - pathLength(game.path) * 0.1));
      game.score += Math.max(100, 1000 - 200 * (game.tries - 1) + bonus);
      game.state = "LANDED";
      game.timer = 0;
      setStatus("Delivery complete! Next level loading…");
    } else if (
      game.clouds.some((cloud) => distance(game.plane, cloud) <= cloud.r)
      || game.plane.x < -25 || game.plane.x > WIDTH + 25
      || game.plane.y < -25 || game.plane.y > HEIGHT + 25
    ) {
      game.state = "CRASHED";
      game.timer = 0;
      setStatus("Route failed. You can retry or draw a new route.");
    }
  } else if (game.state === "LANDED" || game.state === "CRASHED") {
    game.timer += dt;
    if (game.timer >= 2) {
      if (game.state === "LANDED") nextLevel();
      else retry();
    }
  }
}

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
    const radius = i % 2 === 0 ? STAR_RADIUS : STAR_RADIUS * 0.46;
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
  const preview = resample(chaikin(game.rawPath));
  const tight = tightTurns(preview, SPEED / MAX_TURN);
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
  drawPath(freeInk, "#ff6d68", 8);
  ctx.textAlign = "left";
  ctx.fillStyle = "#fff";
  ctx.font = "600 15px 'DM Sans', sans-serif";
  ctx.fillText("FREE DRAW  ·  drag to draw  ·  C to clear", 24, 35);
}

let freeInk = [];

function render() {
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
  selectedInput = mode;
  input.mode = "IDLE";
  for (const [key, button] of Object.entries(inputButtons)) {
    const active = (key === "mouse" && mode !== "HAND") || (key === "hand" && mode === "HAND");
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  }
}

function recognizeHand(landmarks) {
  if (!landmarks) {
    handState.candidate = "IDLE";
    handState.count = 0;
    handState.mode = "IDLE";
    handState.smooth = null;
    return { mode: "IDLE", point: null };
  }
  const indexUp = landmarks[8].y < landmarks[6].y;
  const middleUp = landmarks[12].y < landmarks[10].y;
  const rawMode = indexUp && !middleUp ? "DRAW" : indexUp && middleUp ? "HOVER" : "IDLE";
  if (rawMode === handState.candidate) handState.count += 1;
  else {
    handState.candidate = rawMode;
    handState.count = 1;
  }
  if (handState.count >= 3) handState.mode = rawMode;

  const rawPoint = { x: (1 - landmarks[8].x) * WIDTH, y: landmarks[8].y * HEIGHT };
  if (!handState.smooth) handState.smooth = rawPoint;
  else {
    handState.smooth.x = 0.4 * rawPoint.x + 0.6 * handState.smooth.x;
    handState.smooth.y = 0.4 * rawPoint.y + 0.6 * handState.smooth.y;
  }
  return { mode: handState.mode, point: { ...handState.smooth } };
}

async function enableCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error("Camera access requires HTTPS or localhost and a browser that supports webcam input.");
  }
  if (!cameraStream) {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
    });
    cameraVideo.srcObject = cameraStream;
    await cameraVideo.play();
    cameraPreview.classList.remove("hidden");
  }
}

async function enableHandTracking() {
  setStatus("Requesting camera access…");
  try {
    await enableCamera();
    if (!handLandmarker) {
      setStatus("Loading hand-tracking model…");
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
    }
    cameraError = "";
    setInputMode("HAND");
    setStatus("Hand tracking is on. Raise one finger to draw; raise two to release.");
  } catch (error) {
    cameraError = error instanceof Error ? error.message : String(error);
    setInputMode("MOUSE");
    setStatus("Hand tracking could not start. Mouse drawing is ready.");
    showToast(`Camera/hand tracking unavailable: ${cameraError}`);
  }
}

function updateHandInput() {
  if (selectedInput !== "HAND" || !handLandmarker || cameraVideo.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return;
  const result = handLandmarker.detectForVideo(cameraVideo, performance.now());
  const landmarks = result.landmarks?.[0] ?? null;
  const gesture = recognizeHand(landmarks);
  input.mode = gesture.mode;
  input.point = gesture.point;
}

function frame(now) {
  const dt = Math.min((now - previousFrameTime) / 1000, 0.05);
  previousFrameTime = now;
  if (selectedInput === "HAND") {
    updateHandInput();
    if (freeDraw) {
      if (input.mode === "DRAW" && input.point) freeInk.push({ ...input.point });
    } else {
      updateGame(input.mode, input.point, dt);
    }
  } else {
    const mode = input.drawing ? "DRAW" : (input.point ? "HOVER" : "IDLE");
    if (!freeDraw) updateGame(mode, input.point, dt);
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
  handState.mode = "IDLE";
  setStatus("Drag from the drone to draw a route. Release to launch.");
});
inputButtons.hand.addEventListener("click", enableHandTracking);
document.querySelector("#free-draw").addEventListener("click", (event) => {
  freeDraw = !freeDraw;
  event.currentTarget.classList.toggle("active", freeDraw);
  setStatus(freeDraw ? "Free draw: drag anywhere to sketch. Press C to clear." : "Drag from the drone to draw a route. Release to launch.");
});
document.querySelector("#autopilot").addEventListener("click", (event) => {
  autopilot = !autopilot;
  event.currentTarget.classList.toggle("active", autopilot);
});
document.querySelector("#clear").addEventListener("click", () => {
  freeInk = [];
  if (!freeDraw && game.state !== "FLYING") retry();
});
document.querySelector("#fullscreen").addEventListener("click", async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await canvasWrap.requestFullscreen();
  } catch (error) {
    showToast(`Could not enter fullscreen: ${error.message}`);
  }
});

canvas.addEventListener("pointermove", (event) => {
  if (freeDraw && input.drawing) freeInk.push(canvasPoint(event));
});
canvas.addEventListener("pointerdown", (event) => {
  if (freeDraw) freeInk = [canvasPoint(event)];
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
    if (!freeDraw && game.state !== "FLYING") retry();
  } else if (key === "d") debug = !debug;
  else if (key === "f") document.querySelector("#fullscreen").click();
  else if (key === "m") inputButtons.mouse.click();
});

makeLevel();
retry();
requestAnimationFrame(frame);
