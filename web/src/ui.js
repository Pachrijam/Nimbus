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
    write("player-time", `${result.playerTime.toFixed(2)} s`);
    write("best-time", `${result.bestTime.toFixed(2)} s`);
    const ready = result.status === "ready";
    const disabled = result.status === "disabled";
    let title = disabled ? "Delivery complete" : "Your flight vs. Gemini";
    write("retry-label", disabled ? "Retry this level" : "Try to beat Gemini");
    for (const id of ["ai-time-metric", "time-gap-metric", "route-legend", "gemini-replay"]) {
      document.querySelector(`#${id}`).classList.toggle("hidden", disabled);
    }
    write("ai-time", ready ? `${result.aiTime.toFixed(2)} s` : "—");
    const gap = ready ? Math.abs(result.timeDelta).toFixed(2) : null;
    const tied = ready && gap === "0.00";
    write("time-gap", ready ? `${gap} s` : "—");
    const badges = { beat: "You win!", matched: "Nearly tied", chasing: "Gemini wins" };
    write("match-badge", ready ? tied ? "Tied" : badges[result.verdict] : result.status === "pending" ? "Planning..." : disabled ? "Delivered!" : "AI unavailable");
    let message = result.message;
    if (ready) {
      title = tied
        ? "You and Gemini finished in the same time!"
        : result.timeDelta < 0
          ? `You beat Gemini by ${gap} seconds!`
          : `Gemini finished ${gap} seconds ahead`;
      message = result.timeDelta < 0 && !tied
        ? "Lower time wins. Can you improve your record?"
        : `Lower time wins. Finish under ${result.aiTime.toFixed(2)} s to beat Gemini.`;
    }
    write("comparison-title", title);
    write("comparison-message", message);
    const planner = result.planner === "gemini_predictive"
      ? "Gemini + predictive cloud planning. " : "";
    write("comparison-note", ready
      ? `${planner}Best of ${result.tested} simulated routes (${result.refined ?? 0} time-aware refinements), not a guaranteed optimum. Both flights use the same wind, moving storms, and flight physics.`
      : disabled
        ? "Your score and best flight time are saved for this level. Press N or choose Next level to continue."
        : "Gemini's routes are tested with the same wind, moving storms, and flight physics. Your delivery is saved for this level.");
    comparisonPanel.setAttribute("aria-busy", String(result.status === "pending"));
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
    state.game = snapshot;
    missionHUD.update(snapshot, freeDraw);
    updateComparison(snapshot.comparison, Boolean(snapshot.comparison) && !freeDraw);
    if (!freeDraw && snapshot.comparison?.status === "ready" && (changed || game?.comparison?.status !== "ready")) {
      showToast("Watch Gemini's purple drone fly its route. Your flight stays orange.", 5000);
    }
    if (selectedInput === "HAND" && acceptInput) Object.assign(input, snapshot.cursor);
    canvas.setAttribute("aria-label", freeDraw
      ? "Free draw canvas. One finger draws; two or more fingers change color."
      : `Mission ${String(snapshot.level).padStart(2, "0")}. Game field. Draw from the drone with one finger; hold up two or more fingers to launch.`);
    if (changed && !freeDraw) {
      if (selectedInput !== "HAND" && snapshot.state !== "LANDED") {
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
        CRASHED: "Route failed. Preparing another attempt...",
      };
      setStatus(messages[snapshot.state]);
    }
  }

  return { setStatus, showToast, applySnapshot };
}
