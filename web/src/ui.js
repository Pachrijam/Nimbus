import { createMissionHUD } from "./hud.js";

export function createUI({ canvas, statusText, toast }) {
  let toastTimeout = 0;
  const comparisonPanel = document.querySelector("#comparison");
  const missionHUD = createMissionHUD();

  function updateComparison(result, visible) {
    comparisonPanel.classList.toggle("hidden", !visible);
    document.querySelector("#gemini-replay").disabled = !visible || result?.status !== "ready";
    if (!visible) return;
    const write = (id, value) => {
      const element = document.querySelector(`#${id}`);
      // Do not repeatedly announce identical text on every game snapshot.
      if (element.textContent !== value) element.textContent = value;
    };
    const crashed = result.playerState === "CRASHED";
    write("comparison-eyebrow", crashed ? "Safe-route challenge" : "Delivery complete");
    write("player-time-label", crashed ? "Your route" : "Your flight");
    write("player-time", crashed ? `Crashed at ${result.playerTime.toFixed(2)} s`
      : `${result.playerTime.toFixed(2)} s`);
    write("best-time", Number.isFinite(result.bestTime) ? `${result.bestTime.toFixed(2)} s` : "—");
    const ready = result.status === "ready";
    const disabled = result.status === "disabled";
    const local = result.planner === "local";
    const pilot = local ? "Route planner" : "Gemini";
    write("ai-time-label", local ? "Verified flight" : "Gemini's flight");
    write("ai-route-label", local ? "Verified route (dashed)" : "Gemini's flight (dashed)");
    write("gemini-replay", local ? "Replay verified flight" : "Replay Gemini's flight");
    let title = crashed ? "Your route vs. Gemini's safe route" : disabled ? "Delivery complete" : "Your flight vs. Gemini";
    write("retry-label", crashed ? "Try another route" : disabled ? "Retry this level" : local ? "Beat the verified route" : "Try to beat Gemini");
    for (const id of ["ai-time-metric", "time-gap-metric", "route-legend", "gemini-replay"]) {
      document.querySelector(`#${id}`).classList.toggle("hidden", disabled);
    }
    document.querySelector("#time-gap-metric").classList.toggle("hidden", disabled || crashed);
    document.querySelector("#best-time-metric").classList.toggle("hidden", crashed);
    write("ai-time", ready ? `${result.aiTime.toFixed(2)} s` : "—");
    const gap = ready && !crashed ? Math.abs(result.timeDelta).toFixed(2) : null;
    const tied = ready && !crashed && gap === "0.00";
    write("time-gap", gap === null ? "—" : `${gap} s`);
    const badges = { beat: "You win!", matched: "Nearly tied", chasing: `${pilot} wins` };
    write("match-badge", crashed
      ? ready ? "Safe route found" : result.status === "pending" ? "Planning..." : "AI unavailable"
      : ready ? tied ? "Tied" : badges[result.verdict]
        : result.status === "pending" ? "Planning..." : disabled ? "Delivered!" : "AI unavailable");
    let message = result.message;
    if (crashed && ready) {
      title = local ? "Safe route found. Watch the purple drone." : "Gemini found a safe route.";
      message = `The fastest verified route reached the destination in ${result.aiTime.toFixed(2)} s. The full path is shown in purple.`;
    } else if (crashed && result.status === "pending") {
      title = "Your route hit a cloud. Gemini is searching...";
      message = "A safe route will appear here if Gemini finds one in the same conditions.";
    } else if (crashed) {
      title = result.status === "disabled" ? "AI comparison is off." : "Gemini couldn't find a safe route.";
      message = result.message || "Try another route through the same level.";
    } else if (ready) {
      title = tied
        ? `You and ${pilot} finished in the same time!`
        : result.timeDelta < 0
          ? `You beat ${pilot} by ${gap} seconds!`
          : `${pilot} finished ${gap} seconds ahead`;
      message = result.timeDelta < 0 && !tied
        ? "Lower time wins. Can you improve your record?"
        : `Lower time wins. Finish under ${result.aiTime.toFixed(2)} s to beat ${pilot}.`;
    }
    if (ready && result.planning) message += " Gemini is checking for a faster route.";
    write("comparison-title", title);
    write("comparison-message", message);
    const planner = result.planner === "gemini_predictive"
      ? "Gemini + predictive cloud planning. " : local ? "Local simulator route. " : "";
    write("comparison-note", ready
      ? `${planner}Best of ${result.tested} simulated routes (${result.refined ?? 0} time-aware refinements), not a guaranteed optimum. Both flights use the same wind, moving storms, and flight physics.`
      : disabled
        ? "Your score and best flight time are saved for this level. Press N or choose Next level to continue."
        : crashed
          ? "Gemini's routes use the same wind, moving storms, and flight physics. Retry or continue when ready."
          : "Gemini's routes are tested with the same wind, moving storms, and flight physics. Your delivery is saved for this level.");
    comparisonPanel.setAttribute("aria-busy", String(result.status === "pending" || Boolean(result.planning)));
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

  function applySnapshot(state, snapshot, acceptInput = true) {
    const { game, selectedInput, input, freeDraw } = state;
    const changed = game?.state !== snapshot.state || game?.level !== snapshot.level;
    const comparisonChanged = game?.comparison?.status !== snapshot.comparison?.status
      || game?.comparison?.planning !== snapshot.comparison?.planning
      || game?.comparison?.planner !== snapshot.comparison?.planner;
    state.game = snapshot;
    missionHUD.update(snapshot, freeDraw);
    updateComparison(snapshot.comparison, Boolean(snapshot.comparison) && !freeDraw);
    if (!freeDraw && snapshot.comparison?.status === "ready" && (changed || game?.comparison?.status !== "ready")) {
      showToast("The verified route is shown in purple. Watch the drone fly to the destination.", 5000);
    }
    if (selectedInput === "HAND" && acceptInput) Object.assign(input, snapshot.cursor);
    canvas.setAttribute("aria-label", freeDraw
      ? "Free draw canvas. One finger draws; two or more fingers change color."
      : `Mission ${String(snapshot.level).padStart(2, "0")}. Game field. Draw from the drone with one finger; hold up two or more fingers to launch.`);
    if ((changed || comparisonChanged) && !freeDraw) {
      if (selectedInput !== "HAND" && !["LANDED", "CRASHED"].includes(snapshot.state)) {
        setStatus("Select Start to draw with your camera.");
        return;
      }
      const messages = {
        READY: "Draw a route from the drone with one finger, then hold up two or more fingers to launch.",
        DRAWING: "Hold up two or more fingers when you're ready to launch. Tracking gaps pause your route.",
        FLYING: "Drone launched. Avoid the storms!",
        LANDED: snapshot.comparison?.status === "disabled"
          ? "Delivered! R to retry this level, N to continue."
          : "Delivery complete! Compare with Gemini below. R to retry this level, N to continue.",
        CRASHED: snapshot.comparison?.status === "ready"
          ? snapshot.comparison.planning
            ? "Safe route shown in purple. Gemini is checking for a faster route. R to retry."
            : "Safe route shown in purple. Replay below, or press R to try another route."
          : snapshot.comparison?.status === "disabled"
          ? "Route failed. AI comparison is off. Draw another route with R."
          : "Route failed. Gemini is searching for a safe route. Compare below, or press R to retry.",
      };
      setStatus(messages[snapshot.state]);
    }
  }

  return { setStatus, showToast, applySnapshot };
}
