// Match the Python start area exactly; this hint never changes game rules.
export function drawStartZone(ctx, game, input) {
  if (game.state !== "READY" || !(game.startRadius > 0)) return;
  const { x, y } = game.plane;
  const radius = game.startRadius;
  const nearby = input?.point && Math.hypot(input.point.x - x, input.point.y - y) <= radius;
  ctx.save();
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.fillStyle = nearby ? "rgba(120,226,189,.24)" : "rgba(120,226,189,.12)";
  ctx.fill();
  ctx.strokeStyle = nearby ? "#c0ffe8" : "#3f997e";
  ctx.lineWidth = 2;
  ctx.setLineDash(nearby ? [] : [4, 4]);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = "#183f38";
  ctx.font = "600 11px 'DM Sans', sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("START HERE", x, y + radius + 19);
  ctx.restore();
}
