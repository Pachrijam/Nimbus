export function createUI({ canvas, statusText, toast }) {
  return {
    setStatus(message) {
      if (statusText) statusText.textContent = message;
    },
    showToast(message, duration = 3000) {
      if (toast) {
        toast.textContent = message;
        toast.classList.remove("hidden");
        window.clearTimeout(toast._timer);
        toast._timer = window.setTimeout(() => toast.classList.add("hidden"), duration);
      }
    },
    applySnapshot(state, snapshot, acceptInput = true) {
      state.game = snapshot;
      if (state.selectedInput === "HAND" && acceptInput) Object.assign(state.input, snapshot.cursor ?? state.input);
      canvas?.setAttribute("aria-label", state.freeDraw
        ? "Free draw canvas. One finger draws; two or more fingers change color."
        : "Mission field. Draw from the drone with one finger; hold up two or more fingers to launch.");
    },
  };
}
