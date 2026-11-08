import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
const source = readFileSync(new URL("../web/src/start-zone.js", import.meta.url));
const { drawStartZone } = await import("data:text/javascript;base64," + source.toString("base64"));

function context() {
  return { arcs: [], saved: 0, restored: 0, save() { this.saved++; }, restore() { this.restored++; },
    beginPath() {}, arc(...args) { this.arcs.push(args); }, fill() {}, stroke() {},
    setLineDash() {}, fillText() {} };
}

test("start hint follows the server radius and drone position", () => {
  const ctx = context();
  drawStartZone(ctx, { state: "READY", startRadius: 18, plane: {x:90, y:300} }, {point:null});
  assert.deepEqual(ctx.arcs[0].slice(0,3), [90,300,18]);
  assert.equal(ctx.saved, ctx.restored);
});

test("start hint disappears after drawing starts and when old servers omit its radius", () => {
  for (const state of ["DRAWING", "FLYING", "LANDED", "CRASHED"]) {
    const ctx = context();
    drawStartZone(ctx, {state, startRadius:18, plane:{x:90,y:300}}, {});
    assert.equal(ctx.arcs.length,0);
  }
  const ctx = context();
  drawStartZone(ctx, {state:"READY", plane:{x:90,y:300}}, {});
  assert.equal(ctx.arcs.length,0);
});
