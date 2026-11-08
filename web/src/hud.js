// Render server values outside the canvas so mission information cannot hide obstacles.
export function createMissionHUD(root = document) {
  const get = id => root.querySelector(`#${id}`);
  const panel = get("mission-hud");
  const level = get("hud-level"), score = get("hud-score"), attempts = get("hud-attempts");
  const wind = get("hud-wind"), arrow = get("hud-wind-arrow");
  const formatPoints = new Intl.NumberFormat("en-US");
  const write = (element, value) => { if (element.textContent !== value) element.textContent = value; };
  return {
    update(game, freeDraw) {
      panel.classList.toggle("hidden", freeDraw);
      write(level, String(game.level));
      write(score, formatPoints.format(game.score));
      write(attempts, String(game.tries));
      const speed = Math.hypot(game.wind.x, game.wind.y);
      const conditions = speed < 1 ? "Calm"
        : speed < 20 ? "Light breeze"
        : speed < 40 ? "Steady breeze" : "Strong wind";
      write(wind, conditions);
      wind.title = `Wind speed: ${speed.toFixed(1)} pixels per second. The arrow shows its direction.`;
      arrow.style.transform = `rotate(${Math.atan2(game.wind.y, game.wind.x)}rad)`;
      arrow.style.visibility = speed < 1 ? "hidden" : "visible";
    },
  };
}
