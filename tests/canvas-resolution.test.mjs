import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

// Load browser ES modules without changing the project's package configuration.
const config = readFileSync(new URL("../web/src/config.js", import.meta.url), "utf8");
const configURL = "data:text/javascript;base64," + Buffer.from(config).toString("base64");
const source = readFileSync(new URL("../web/src/canvas-resolution.js", import.meta.url), "utf8")
  .replace('"./config.js"', JSON.stringify(configURL));
const { updateCanvasResolution } = await import(
  "data:text/javascript;base64," + Buffer.from(source).toString("base64"));

function fixture(displayWidth) {
  const canvas = { width: 960, height: 600,
    getBoundingClientRect: () => ({ width: displayWidth }) };
  const ctx = { setTransform(...values) { this.transform = values; } };
  return { canvas, ctx };
}

test("Retina rendering increases sharpness while preserving logical coordinates", () => {
  const { canvas, ctx } = fixture(1120);
  updateCanvasResolution(canvas, ctx, 2);
  assert.equal(canvas.width, 2240);
  assert.equal(canvas.height, 1400);
  assert.equal(ctx.transform[0] * 960, canvas.width);
  assert.equal(ctx.transform[3] * 600, canvas.height);
  assert.equal(ctx.imageSmoothingQuality, "high");
});

test("mobile, fullscreen, and zoom use bounded backing dimensions", () => {
  const { canvas, ctx } = fixture(320);
  updateCanvasResolution(canvas, ctx, 3);
  assert.equal(canvas.width, 640);
  assert.equal(canvas.height, 400);
  canvas.getBoundingClientRect = () => ({ width: 4000 });
  updateCanvasResolution(canvas, ctx, 2);
  assert.equal(canvas.width, 3840);
  assert.equal(canvas.height, 2400);
});

test("unchanged frames do not clear the canvas by resetting its dimensions", () => {
  const { canvas, ctx } = fixture(960);
  Object.defineProperty(canvas, "width", { get: () => 960,
    set() { assert.fail("Unexpected backing width reset"); } });
  Object.defineProperty(canvas, "height", { get: () => 600,
    set() { assert.fail("Unexpected backing height reset"); } });
  updateCanvasResolution(canvas, ctx, 1);
  updateCanvasResolution(canvas, ctx, 1);
});
