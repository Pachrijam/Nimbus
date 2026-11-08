// Render server values outside the canvas so mission information cannot hide obstacles.
export function createMissionHUD(root = document) {
  const get = id => root.querySelector(`#${id}`);
  const panel = get("mission-hud");
  const level = get("hud-level"), score = get("hud-score"), attempts = get("hud-attempts");
  const wind = get("hud-wind"), arrow = get("hud-wind-arrow");
  const write = (element, value) => { if (element.textContent !== value) element.textContent = value; };
  return {
    update(game, freeDraw) {
      panel.classList.toggle("hidden", freeDraw);
      write(level, String(game.level).padStart(2, "0"));
      write(score, String(game.score));
      write(attempts, String(game.tries));
      const speed = Math.hypot(game.wind.x, game.wind.y);
      write(wind, `${Math.round(speed)} px/s`);
      arrow.style.transform = `rotate(${Math.atan2(game.wind.y, game.wind.x)}rad)`;
      arrow.style.visibility = speed < 0.5 ? "hidden" : "visible";
    },
  };
}
