export function createRenderer({ canvas, cameraVideo }) {
  const ctx = canvas?.getContext("2d");

  function drawBackground() {
    if (!ctx) return;
    ctx.fillStyle = "#dfeef8";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }

  function drawPath(points, color, width = 3) {
    if (!ctx || points.length < 2) return;
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i += 1) ctx.lineTo(points[i].x, points[i].y);
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.stroke();
  }

  function drawCursor(input, color = "#e6534a", size = 14) {
    if (!input.point || !ctx) return;
    ctx.beginPath();
    ctx.arc(input.point.x, input.point.y, input.mode === "DRAW" ? size / 2 : 10, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.strokeStyle = "#263f4c";
    ctx.lineWidth = input.mode === "DRAW" ? 0 : 2;
    if (input.mode === "DRAW") ctx.fill();
    else ctx.stroke();
  }

  function drawFreeDraw(state, cameraActive) {
    if (!ctx) return;
    ctx.fillStyle = "#07121d";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    for (const stroke of state.freeInk) {
      if (stroke.points.length === 1) {
        ctx.beginPath();
        ctx.arc(stroke.points[0].x, stroke.points[0].y, stroke.size / 2, 0, Math.PI * 2);
        ctx.fillStyle = stroke.color;
        ctx.fill();
      } else drawPath(stroke.points, stroke.color, stroke.size);
    }
    drawCursor(state.input, state.penColor, state.penSize);
  }

  function render(state, cameraActive, now = performance.now()) {
    drawBackground();
    if (state.freeDraw) {
      drawFreeDraw(state, cameraActive);
      return;
    }
    if (state.game) {
      ctx.fillStyle = "#7bb2d8";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
  }

  return { render };
}
