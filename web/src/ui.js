export function createUI({ canvas, statusText, toast }) {
  let toastTimeout = 0;

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
    if (selectedInput === "HAND") Object.assign(input, snapshot.cursor);
    canvas.setAttribute("aria-label", `Mission ${String(snapshot.level).padStart(2, "0")}. Game field. In mouse mode, hold the pointer near the drone and drag to draw a route.`);
    if (changed && !freeDraw) {
      const messages = {
        READY: selectedInput === "HAND"
          ? "Draw a route from the drone with one finger, then hold up two fingers to launch."
          : "Draw a route from the drone. Release to launch.",
        DRAWING: selectedInput === "HAND"
          ? "Hold up two fingers when you're ready to launch. Tracking gaps pause your route."
          : "Release when you're ready to launch.",
        FLYING: "Drone launched. Avoid the storms!",
        LANDED: "Delivery complete! Next level loading...",
        CRASHED: "Route failed. Preparing another attempt...",
      };
      setStatus(messages[snapshot.state]);
    }
  }

  return { setStatus, showToast, applySnapshot };
}
