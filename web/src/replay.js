// Play the simulator's recorded positions; never ask Gemini to invent an animation.
export function createGeminiReplay() {
  let key = null;
  let elapsed = 0;
  let previousTime = null;
  let cloudTick = 0;
  let clouds = [];

  return {
    frame(state, now) {
      const game = state.game;
      const result = game?.comparison;
      if (game?.state !== "LANDED" || result?.status !== "ready" || result.aiTrajectory.length < 2) {
        key = null;
        previousTime = null;
        return null;
      }
      if (state.freeDraw) {
        previousTime = null;
        return null;
      }
      const nextKey = `${game.level}:${game.tries}:${state.geminiReplay ?? 0}`;
      if (nextKey !== key) {
        key = nextKey;
        elapsed = 0;
        previousTime = now;
        cloudTick = 0;
        clouds = (game.launchClouds ?? game.clouds).map(cloud => ({ ...cloud }));
      }
      // Pause while the tab is hidden or free draw is open, instead of skipping the replay.
      elapsed = Math.min(result.aiTime, elapsed + Math.min(0.1, Math.max(0, (now - (previousTime ?? now)) / 1000)));
      previousTime = now;
      const points = result.aiTrajectory;
      const step = result.aiTime / (points.length - 1);
      const sample = Math.min(points.length - 1, elapsed / step);
      const index = Math.min(points.length - 2, Math.floor(sample));
      const fraction = sample - index;
      const from = points[index], to = points[index + 1];
      const position = { x: from.x + (to.x - from.x) * fraction, y: from.y + (to.y - from.y) * fraction };
      // Match the server's fixed-step storm movement, including its boundary clamping.
      while (cloudTick < Math.floor(sample)) {
        for (const cloud of clouds) {
          cloud.x += cloud.vx * step;
          cloud.y += (cloud.vy ?? 0) * step;
          if (cloud.x < cloud.r) {
            cloud.x = cloud.r;
            cloud.vx = Math.abs(cloud.vx);
          } else if (cloud.x > game.fieldWidth - cloud.r) {
            cloud.x = game.fieldWidth - cloud.r;
            cloud.vx = -Math.abs(cloud.vx);
          }
          if (cloud.y < cloud.r) {
            cloud.y = cloud.r;
            cloud.vy = Math.abs(cloud.vy ?? 0);
          } else if (cloud.y > (game.fieldHeight ?? 600) - cloud.r) {
            cloud.y = (game.fieldHeight ?? 600) - cloud.r;
            cloud.vy = -Math.abs(cloud.vy ?? 0);
          }
        }
        cloudTick += 1;
      }
      return {
        elapsed, duration: result.aiTime, done: elapsed >= result.aiTime, clouds,
        plane: { ...position, heading: Math.atan2(to.y - from.y, to.x - from.x) },
        trail: [...points.slice(0, index + 1), position],
      };
    },
  };
}
