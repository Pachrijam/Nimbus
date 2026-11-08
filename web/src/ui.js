export function createUI({ canvas, statusText, toast }) {
  let toastTimeout = 0;
  const comparisonPanel = document.querySelector("#comparison");

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
    write("comparison-title", disabled ? "Delivery complete" : "Your flight vs. Gemini");
    write("retry-label", disabled ? "Retry this level" : "Try to beat Gemini");
    for (const id of ["ai-time-metric", "ai-performance-metric", "route-legend", "gemini-replay"]) {
      document.querySelector(`#${id}`).classList.toggle("hidden", disabled);
    }
    write("ai-time", ready ? `${result.aiTime.toFixed(2)} s` : "—");
    write("match-percent", ready ? `${result.matchPercent.toFixed(1)}%` : "—");
    const badges = { beat: "You beat Gemini!", matched: "AI performance matched", chasing: "Chase Gemini" };
    write("match-badge", ready ? badges[result.verdict] : result.status === "pending" ? "Planning..." : disabled ? "Delivered!" : "AI unavailable");
    let message = result.message;
    if (ready) {
      const gap = Math.abs(result.timeDelta).toFixed(2);
      message = result.verdict === "beat"
        ? `You delivered ${gap} s faster than Gemini. Can you improve your record?`
        : result.timeDelta <= 0.01
          ? "You matched Gemini's flight time. Try another route or take on the next mission."
          : `Gemini delivered ${gap} s faster. Study the dashed route and try again.`;
    }
    write("comparison-message", message);
    write("comparison-note", ready
      ? `Best of ${result.tested} simulated Gemini routes, not a guaranteed optimum. AI performance = Gemini time ÷ your time; 100% is equal, above 100% is faster. Matched means within 5% of AI performance.`
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

  function applySnapshot(state, snapshot) {
    const { game, selectedInput, input, freeDraw } = state;
    const changed = game?.state !== snapshot.state || game?.level !== snapshot.level;
    state.game = snapshot;
    updateComparison(snapshot.comparison, Boolean(snapshot.comparison) && !freeDraw);
    if (!freeDraw && snapshot.comparison?.status === "ready" && (changed || game?.comparison?.status !== "ready")) {
      showToast("Watch Gemini's purple drone fly its route. Your flight stays orange.", 5000);
    }
    if (selectedInput === "HAND") Object.assign(input, snapshot.cursor);
    canvas.setAttribute("aria-label", `Mission ${String(snapshot.level).padStart(2, "0")}. Game field. Draw from the drone with one finger; hold up two fingers to launch.`);
    if (changed && !freeDraw) {
      if (selectedInput !== "HAND" && snapshot.state !== "LANDED") {
        setStatus("Enable hand tracking to draw with your camera.");
        return;
      }
      const messages = {
        READY: "Draw a route from the drone with one finger, then hold up two fingers to launch.",
        DRAWING: "Hold up two fingers when you're ready to launch. Tracking gaps pause your route.",
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
