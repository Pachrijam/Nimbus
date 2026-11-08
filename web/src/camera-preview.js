// Move only the preview overlay; camera input and game coordinates stay unchanged.
export function createDraggablePreview(preview, canvas) {
  let position = null;
  let drag = null;

  function limits() {
    const parent = preview.parentElement.getBoundingClientRect();
    const area = canvas.getBoundingClientRect();
    const box = preview.getBoundingClientRect();
    if (!area.width || !area.height || !box.width || !box.height) return null;
    return { minX: area.left - parent.left, minY: area.top - parent.top,
      rangeX: Math.max(0, area.width - box.width),
      rangeY: Math.max(0, area.height - box.height), parent, box };
  }

  function place(x, y) {
    const area = limits();
    if (!area) return;
    x = Math.max(area.minX, Math.min(area.minX + area.rangeX, x));
    y = Math.max(area.minY, Math.min(area.minY + area.rangeY, y));
    preview.style.left = `${x}px`;
    preview.style.top = `${y}px`;
    preview.style.right = "auto";
    position = { x: area.rangeX ? (x - area.minX) / area.rangeX : 0,
      y: area.rangeY ? (y - area.minY) / area.rangeY : 0 };
  }

  preview.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || event.isPrimary === false) return;
    const area = limits();
    if (!area) return;
    event.preventDefault();
    event.stopPropagation();
    preview.focus({ preventScroll: true });
    drag = { id: event.pointerId, offsetX: event.clientX - area.box.left,
      offsetY: event.clientY - area.box.top };
    preview.setPointerCapture(event.pointerId);
    preview.classList.add("dragging");
  });

  preview.addEventListener("pointermove", (event) => {
    if (!drag || event.pointerId !== drag.id) return;
    const area = limits();
    if (!area) return;
    event.preventDefault();
    event.stopPropagation();
    place(event.clientX - area.parent.left - drag.offsetX,
      event.clientY - area.parent.top - drag.offsetY);
  });

  function endDrag(event) {
    if (!drag || event.pointerId !== drag.id) return;
    drag = null;
    preview.classList.remove("dragging");
    if (preview.hasPointerCapture(event.pointerId)) preview.releasePointerCapture(event.pointerId);
  }
  for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) {
    preview.addEventListener(type, endDrag);
  }

  preview.addEventListener("keydown", (event) => {
    const directions = { ArrowLeft: [-1, 0], ArrowRight: [1, 0],
      ArrowUp: [0, -1], ArrowDown: [0, 1] };
    const direction = directions[event.key];
    const area = limits();
    if (!direction || !area) return;
    event.preventDefault();
    event.stopPropagation();
    const step = event.shiftKey ? 30 : 10;
    place(area.box.left - area.parent.left + direction[0] * step,
      area.box.top - area.parent.top + direction[1] * step);
  });

  // Preserve relative placement on resize, fullscreen changes and camera restart.
  if (typeof ResizeObserver !== "undefined") {
    const observer = new ResizeObserver(() => {
      const area = limits();
      if (!position || !area) return;
      place(area.minX + position.x * area.rangeX, area.minY + position.y * area.rangeY);
    });
    observer.observe(canvas);
    observer.observe(preview);
  }
}
