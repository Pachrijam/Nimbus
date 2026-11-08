export const PEN_COLORS = [
  { name: "Coral", value: "#ff6d68" },
  { name: "Blue", value: "#68baff" },
  { name: "Mint", value: "#78e2bd" },
  { name: "Gold", value: "#ffda8b" },
  { name: "White", value: "#ffffff" },
];

export function createFreeDraw(state) {
  state.freeInk ??= [];
  state.penColor ??= PEN_COLORS[0].value;
  state.penSize ??= 8;
  let previousMode = "IDLE";

  function endStroke() {
    state.activeStroke = null;
    previousMode = "IDLE";
  }

  function update() {
    if (!state.freeDraw) return;
    const { mode, point } = state.input;
    if (mode === "HOVER" && previousMode !== "HOVER") {
      const index = PEN_COLORS.findIndex(color => color.value === state.penColor);
      state.penColor = PEN_COLORS[(index + 1) % PEN_COLORS.length].value;
    }
    previousMode = mode;
    if (mode !== "DRAW" || !point) {
      state.activeStroke = null;
      return;
    }
    if (!state.activeStroke) {
      state.activeStroke = { color: state.penColor, size: state.penSize, points: [] };
      state.freeInk.push(state.activeStroke);
    }
    const points = state.activeStroke.points;
    const last = points.at(-1);
    if (!last || Math.hypot(point.x - last.x, point.y - last.y) >= 1) points.push({ ...point });
  }

  return {
    update,
    endStroke,
    clear() { state.freeInk = []; state.activeStroke = null; },
    undo() { state.freeInk.pop(); state.activeStroke = null; },
    setColor(color) { state.penColor = color; state.activeStroke = null; },
    setSize(size) { state.penSize = size; state.activeStroke = null; },
  };
}
