import { WIDTH, HEIGHT } from "./config.js";

// Display more pixels on Retina screens without changing game coordinates.
export function updateCanvasResolution(canvas, ctx, pixelRatio = 1) {
  const displayWidth = canvas.getBoundingClientRect().width;
  if (displayWidth <= 0) return;
  const density = Math.min(2, Math.max(1, pixelRatio));
  // Bound GPU memory use when fullscreen or heavily zoomed.
  const width = Math.min(3840, Math.max(1, Math.round(displayWidth * density)));
  const height = Math.max(1, Math.round(width * HEIGHT / WIDTH));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  // Setting the transform also restores it after resizing resets the context.
  ctx.setTransform(width / WIDTH, 0, 0, height / HEIGHT, 0, 0);
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
}
