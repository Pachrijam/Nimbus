import { WIDTH, HEIGHT } from "./config.js";
import { createGeminiReplay } from "./replay.js";
import { updateCanvasResolution } from "./canvas-resolution.js";
import { drawStartZone } from "./start-zone.js";

export function createRenderer({ canvas, cameraVideo }) {
  const ctx = canvas.getContext("2d");
  const geminiReplay = createGeminiReplay();

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

  function drawCloud(cloud, debug) {
    ctx.save();
    ctx.translate(cloud.x, cloud.y);
    ctx.scale(cloud.r, cloud.r);

    // One continuous outline: the shadow belongs to the whole cloud.
    ctx.beginPath();
    ctx.moveTo(-0.9, 0.25);
    ctx.bezierCurveTo(-1.16, -0.02, -1.04, -0.47, -0.68, -0.48);
    ctx.bezierCurveTo(-0.7, -0.86, -0.26, -1.08, 0, -0.82);
    ctx.bezierCurveTo(0.25, -1.06, 0.7, -0.88, 0.72, -0.51);
    ctx.bezierCurveTo(1.12, -0.47, 1.2, 0.05, 0.99, 0.29);
    ctx.bezierCurveTo(1.14, 0.64, 0.68, 0.91, 0.4, 0.78);
    ctx.bezierCurveTo(0.1, 1.02, -0.32, 0.9, -0.45, 0.74);
    ctx.bezierCurveTo(-0.84, 0.85, -1.15, 0.63, -0.9, 0.25);
    ctx.closePath();
    const body = ctx.createLinearGradient(0, -1, 0.25, 1);
    body.addColorStop(0, "#ffffff");
    body.addColorStop(0.35, "#edf3f6");
    body.addColorStop(0.7, "#c1d1df");
    body.addColorStop(1, "#829bb4");
    ctx.fillStyle = body;
    ctx.shadowColor = "rgba(35,63,86,.23)";
    ctx.shadowBlur = cloud.r * 0.18;
    ctx.shadowOffsetY = cloud.r * 0.12;
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.shadowOffsetY = 0;
    ctx.shadowColor = "transparent";

    ctx.save();
    ctx.clip();
    const light = ctx.createRadialGradient(-0.36, -0.5, 0.05, -0.24, -0.35, 1.05);
    light.addColorStop(0, "rgba(255,255,255,.9)");
    light.addColorStop(0.5, "rgba(255,255,255,.35)");
    light.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = light;
    ctx.fillRect(-1.3, -1.3, 2.6, 2.6);
    const shade = ctx.createRadialGradient(0.5, 0.55, 0, 0.5, 0.55, 0.95);
    shade.addColorStop(0, "rgba(74,100,135,.24)");
    shade.addColorStop(1, "rgba(74,100,135,0)");
    ctx.fillStyle = shade;
    ctx.fillRect(-1.3, -1.3, 2.6, 2.6);
    ctx.restore();

    ctx.strokeStyle = "rgba(48,74,98,.8)";
    ctx.lineWidth = 2 / cloud.r;
    ctx.stroke();

    if (debug) {
      ctx.strokeStyle = "rgba(58,91,105,.6)";
      ctx.lineWidth = 1 / cloud.r;
      ctx.setLineDash([4 / cloud.r, 4 / cloud.r]);
      ctx.beginPath();
      ctx.arc(0, 0, 1, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawDestination(x, y, radius) {
    ctx.save();
    ctx.translate(x, y);
    ctx.shadowColor = "rgba(239,68,68,.6)";
    ctx.shadowBlur = 22;
    ctx.fillStyle = "#ef4444";
    ctx.beginPath();
    ctx.moveTo(0, radius);
    ctx.bezierCurveTo(-radius * 0.35, radius * 0.55, -radius * 0.8, 0, -radius * 0.8, -radius * 0.3);
    ctx.arc(0, -radius * 0.3, radius * 0.8, Math.PI, 0);
    ctx.bezierCurveTo(radius * 0.8, 0, radius * 0.35, radius * 0.55, 0, radius);
    ctx.closePath();
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.strokeStyle = "rgba(153,27,27,.7)";
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.fillStyle = "#fff1f2";
    ctx.beginPath();
    ctx.arc(0, -radius * 0.3, radius * 0.3, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function drawDrone(plane, gemini = false) {
    ctx.save();
    ctx.translate(plane.x, plane.y);
    ctx.rotate(plane.heading);
    ctx.lineCap = "round";

    // Four arms and guarded rotors make the silhouette readable at game size.
    const rotors = [[-13, -11], [13, -11], [-13, 11], [13, 11]];
    ctx.strokeStyle = "#243746";
    ctx.lineWidth = 5;
    for (const [x, y] of rotors) {
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(x, y);
      ctx.stroke();
    }
    for (const [x, y] of rotors) {
      ctx.fillStyle = "#243746";
      ctx.strokeStyle = "#edf5f7";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(x, y, 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.strokeStyle = "#9db9c7";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(x - 4, y - 3);
      ctx.lineTo(x + 4, y + 3);
      ctx.moveTo(x - 3, y + 4);
      ctx.lineTo(x + 3, y - 4);
      ctx.stroke();
      ctx.fillStyle = "#edf5f7";
      ctx.beginPath();
      ctx.arc(x, y, 2, 0, Math.PI * 2);
      ctx.fill();
    }

    // Light body and a cyan front camera show which way the drone is heading.
    ctx.fillStyle = gemini ? "#b897f4" : "#edf5f7";
    ctx.strokeStyle = "#243746";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(-9, -6);
    ctx.lineTo(6, -6);
    ctx.lineTo(11, -3);
    ctx.lineTo(11, 3);
    ctx.lineTo(6, 6);
    ctx.lineTo(-9, 6);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#243746";
    roundedRect(ctx, -6, -3, 8, 6, 2);
    ctx.fill();
    ctx.fillStyle = "#36cbe0";
    ctx.beginPath();
    ctx.arc(7, 0, 2.5, 0, Math.PI * 2);
    ctx.fill();
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

  function drawRoutePreview(game) {
    const { preview, tight } = game;
    for (let i = 1; i < preview.length; i += 1) {
      drawPath([preview[i - 1], preview[i]], tight[i] || tight[i - 1] ? "#e45d53" : "#fff", 4);
    }
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
    ctx.font = "600 30px 'Manrope', sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(text, WIDTH / 2, HEIGHT / 2 + 10);
    ctx.restore();
  }

  function drawCursor(input, color = "#e6534a", size = 14) {
    if (!input.point) return;
    ctx.beginPath();
    ctx.arc(input.point.x, input.point.y, input.mode === "DRAW" ? size / 2 : 10, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.strokeStyle = "#263f4c";
    ctx.lineWidth = input.mode === "DRAW" ? 0 : 2;
    if (input.mode === "DRAW") ctx.fill();
    else ctx.stroke();
  }

  function drawFreeDraw(state, cameraActive) {
    ctx.fillStyle = "#07121d";
    ctx.fillRect(0, 0, WIDTH, HEIGHT);
    if (cameraActive && cameraVideo.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
      ctx.save();
      ctx.translate(WIDTH, 0);
      ctx.scale(-1, 1);
      ctx.drawImage(cameraVideo, 0, 0, WIDTH, HEIGHT);
      ctx.restore();
    } else {
      ctx.fillStyle = "#b4c7d4";
      ctx.font = "20px 'Manrope', sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("Enable your camera to draw over a live view", WIDTH / 2, HEIGHT / 2);
    }
    ctx.fillStyle = "rgba(7,18,29,.48)";
    ctx.fillRect(0, 0, WIDTH, HEIGHT);
    for (const stroke of state.freeInk) {
      if (stroke.points.length === 1) {
        ctx.beginPath();
        ctx.arc(stroke.points[0].x, stroke.points[0].y, stroke.size / 2, 0, Math.PI * 2);
        ctx.fillStyle = stroke.color;
        ctx.fill();
      } else drawPath(stroke.points, stroke.color, stroke.size);
    }
    drawCursor(state.input, state.penColor, state.penSize);
    ctx.textAlign = "left";
    ctx.fillStyle = "#fff";
    ctx.font = "600 15px 'Manrope', sans-serif";
    ctx.fillText("FREE DRAW  ·  C to clear  ·  Esc or P to return to game", 24, 35);
  }

  function drawComparisonStatus(game, replay) {
    const result = game.comparison;
    const pilot = result?.planner === "local" ? "Verified route" : "Gemini";
    if (game.state === "CRASHED") {
      const title = replay
        ? replay.done ? `${pilot}: destination reached` : `${pilot} safe route: ${replay.elapsed.toFixed(1)} / ${replay.duration.toFixed(1)} s`
        : result?.status === "pending" ? "Route failed. Gemini is searching for a safe route..."
          : result?.status === "ready" ? `Gemini found a safe route in ${result.aiTime.toFixed(2)} s`
            : result?.status === "disabled" ? "Route failed. AI comparison is off."
              : "Route failed. Gemini could not find a safe route.";
      const detail = replay
        ? result.planning ? "Purple: fastest verified route so far. Gemini is checking alternatives."
          : `Orange: your failed route   |   Purple: ${pilot}'s flight`
        : "Your failed route is orange. Gemini's verified route will appear in purple.";
      ctx.save();
      roundedRect(ctx, 90, HEIGHT - 82, WIDTH - 180, 66, 10);
      ctx.fillStyle = "rgba(10,26,38,.94)";
      ctx.fill();
      ctx.textAlign = "center";
      ctx.fillStyle = replay ? "#d8c3ff" : "#ffda8b";
      ctx.font = "600 17px 'Manrope', sans-serif";
      ctx.fillText(title, WIDTH / 2, HEIGHT - 55, WIDTH - 210);
      ctx.fillStyle = "#edf5f7";
      ctx.font = "13px 'Manrope', sans-serif";
      ctx.fillText(detail, WIDTH / 2, HEIGHT - 32, WIDTH - 210);
      ctx.restore();
      return;
    }
    let title = "Delivered! Gemini is planning and testing its routes...";
    let detail = "Your flight is orange. Gemini's flight will appear in purple.";
    if (replay) {
      title = replay.done ? `${pilot}: flight complete` : `Watch ${pilot} fly: ${replay.elapsed.toFixed(1)} / ${replay.duration.toFixed(1)} s`;
      detail = result.planning ? "Gemini is checking alternatives. The fastest verified route stays visible."
        : `Orange: your flight   |   Purple: ${pilot}   |   Replay and results below`;
    } else if (result?.status === "disabled") {
      title = "Delivered! Mission complete.";
      detail = "AI comparison is off. Press N for the next level or R to retry.";
    } else if (result?.status === "ready") {
      title = "Delivered! Flight comparison ready.";
      detail = "Compare your time below. Press N to continue or R to retry.";
    } else if (result && result.status !== "pending") {
      title = "Delivered! AI comparison is unavailable this round.";
      detail = "Your delivery counts. Press N to continue or R to retry.";
    }
    ctx.save();
    roundedRect(ctx, 90, HEIGHT - 82, WIDTH - 180, 66, 10);
    ctx.fillStyle = "rgba(10,26,38,.94)";
    ctx.fill();
    ctx.textAlign = "center";
    ctx.fillStyle = replay ? "#d8c3ff" : "#ffda8b";
    ctx.font = "600 17px 'Manrope', sans-serif";
    ctx.fillText(title, WIDTH / 2, HEIGHT - 55, WIDTH - 210);
    ctx.fillStyle = "#edf5f7";
    ctx.font = "13px 'Manrope', sans-serif";
    ctx.fillText(detail, WIDTH / 2, HEIGHT - 32, WIDTH - 210);
    ctx.restore();
  }

  function render(state, cameraActive, now = performance.now()) {
    updateCanvasResolution(canvas, ctx, window.devicePixelRatio || 1);
    const { game, input, connectionError, freeDraw, autopilot, debug } = state;
    const replay = geminiReplay.frame(state, now);
    if (!game || connectionError) {
      drawBackground();
      drawMessage(connectionError ? "CONNECTION LOST" : "CONNECTING...");
      return;
    }
    if (freeDraw) {
      drawFreeDraw(state, cameraActive);
      return;
    }
    drawBackground();
    drawDestination(game.star.x, game.star.y, game.starRadius);
    for (const cloud of replay?.clouds ?? game.clouds) drawCloud(cloud, debug);

    if (game.state === "DRAWING") drawRoutePreview(game);
    else if (game.state === "FLYING") drawPath(game.path, "rgba(255,255,255,.86)", 3, true);
    else if (["LANDED", "CRASHED"].includes(game.state)) {
      drawPath(game.trajectory, "#b43b13", 7);
      if (game.comparison?.status === "ready") {
        // Show the entire verified trajectory immediately, even before replay
        // advances. A light outline keeps it visible over clouds and player ink.
        drawPath(game.comparison.aiTrajectory, "rgba(255,255,255,.9)", 8);
        drawPath(game.comparison.aiTrajectory, "#6334a7", 4, true);
        if (replay && !replay.done) drawPath(replay.trail, "#8d50df", 5);
      }
    }

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
    drawStartZone(ctx, game, input);
    drawDrone(game.plane);
    if (replay) {
      ctx.save();
      ctx.strokeStyle = "#6334a7";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(replay.plane.x, replay.plane.y, 28, 0, Math.PI * 2);
      ctx.stroke();
      drawDrone(replay.plane, true);
      ctx.fillStyle = "#412074";
      ctx.font = "700 13px 'Manrope', sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(game.comparison.planner === "local" ? "VERIFIED" : "GEMINI", replay.plane.x, replay.plane.y - 35);
      ctx.restore();
    }
    drawCursor(input);
    if (["LANDED", "CRASHED"].includes(game.state)) drawComparisonStatus(game, replay);

    if (game.state === "READY") {
      ctx.fillStyle = "rgba(14,39,50,.78)";
      roundedRect(ctx, WIDTH / 2 - 171, HEIGHT - 55, 342, 32, 16);
      ctx.fill();
      ctx.fillStyle = "#fff";
      ctx.font = "12px 'Manrope', sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("Start at the drone · release to launch", WIDTH / 2, HEIGHT - 34);
      ctx.textAlign = "left";
    }

    if (debug) {
      ctx.fillStyle = "#0a1926";
      ctx.font = "12px 'Manrope', sans-serif";
      ctx.fillText(`${game.state} · ${input.mode} · ${input.mode === "DRAW" ? "drawing" : "idle"}`, 18, HEIGHT - 17);
    }
  }

  return { render };
}
