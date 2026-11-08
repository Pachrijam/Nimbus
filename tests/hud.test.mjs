import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
const source = readFileSync(new URL("../web/src/hud.js", import.meta.url));
const { createMissionHUD } = await import("data:text/javascript;base64," + source.toString("base64"));

function fixture() {
  const html = readFileSync(new URL("../web/index.html", import.meta.url), "utf8");
  const nodes = new Map();
  for (const [,id] of html.matchAll(/id="([^"]+)"/g)) {
    const classes = new Set();
    nodes.set(`#${id}`, {textContent:"", style:{}, classList:{toggle(k,v){v?classes.add(k):classes.delete(k)},contains(k){return classes.has(k)}}});
  }
  const root={querySelector(id){assert.ok(nodes.has(id),`Missing element ${id}`);return nodes.get(id)}};
  return {nodes, html, hud:createMissionHUD(root)};
}
const game = {level:3,score:2322,tries:2,wind:{x:3,y:4}};

test("mission and wind values render outside the playable canvas", () => {
  const {nodes,html,hud}=fixture();
  hud.update(game,false);
  assert.equal(nodes.get("#hud-level").textContent,"03");
  assert.equal(nodes.get("#hud-score").textContent,"2,322");
  assert.equal(nodes.get("#hud-attempts").textContent,"2");
  assert.equal(nodes.get("#hud-wind").textContent,"Light breeze");
  assert.ok(html.indexOf('id="mission-hud"') < html.indexOf('id="canvas-wrap"'));
  const renderer=readFileSync(new URL("../web/src/renderer.js",import.meta.url),"utf8");
  assert.ok(!renderer.includes("drawHud("));
});

test("calm wind hides its arrow and free draw hides the mission panels", () => {
  const {nodes,hud}=fixture();
  hud.update({...game,wind:{x:0,y:0}},true);
  assert.equal(nodes.get("#hud-wind-arrow").style.visibility,"hidden");
  assert.ok(nodes.get("#mission-hud").classList.contains("hidden"));
  hud.update(game,false);
  assert.equal(nodes.get("#hud-wind-arrow").style.visibility,"visible");
  assert.ok(!nodes.get("#mission-hud").classList.contains("hidden"));
});

test("wind uses readable conditions while retaining exact speed in the tooltip", () => {
  const {nodes,hud}=fixture();
  for (const [speed,label] of [[0,"Calm"],[5,"Light breeze"],[25,"Steady breeze"],[50,"Strong wind"]]) {
    hud.update({...game,wind:{x:speed,y:0}},false);
    assert.equal(nodes.get("#hud-wind").textContent,label);
    assert.ok(nodes.get("#hud-wind").title.includes(`${speed.toFixed(1)} pixels per second`));
  }
});
