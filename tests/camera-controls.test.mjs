import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
async function load(name) {
  let source = readFileSync(new URL(`../web/src/${name}.js`, import.meta.url), "utf8");
  if (name === "controls") {
    const drawing = readFileSync(new URL("../web/src/free-draw.js", import.meta.url));
    source = source.replace('"./free-draw.js"', JSON.stringify("data:text/javascript;base64," + drawing.toString("base64")));
  }
  return import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
}
function target() {
  const handlers = new Map(), classes = new Set();
  return { handlers, children: [], append(child) {this.children.push(child)}, style: {setProperty() {}}, addEventListener(type, callback) { handlers.set(type, callback); },
    classList: {add(c){classes.add(c)},remove(c){classes.delete(c)},toggle(c,on){on?classes.add(c):classes.delete(c)},contains(c){return classes.has(c)}},
    setAttribute() {}, focus() {},
    emit(type, values = {}) { handlers.get(type)?.({button:0,isPrimary:true,pointerId:1,preventDefault(){},stopPropagation(){},...values}); } };
}

test("preview supports bounded drag, cancellation, resizing and keyboard movement", async () => {
  const {createDraggablePreview} = await load("camera-preview");
  const preview = target();
  preview.parentElement = {getBoundingClientRect:()=>({left:100,top:50})};
  preview.getBoundingClientRect = () => ({left:100+parseFloat(preview.style.left ?? 800),top:50+parseFloat(preview.style.top ?? 50),width:180,height:135});
  let width=960;
  const canvas = {getBoundingClientRect:()=>({left:120,top:70,width,height:600})};
  let resize;
  globalThis.ResizeObserver = class {constructor(callback){resize=callback} observe(){}};
  let captured = false;
  preview.setPointerCapture=()=>{captured=true};
  preview.hasPointerCapture=()=>captured;
  preview.releasePointerCapture=()=>{captured=false};
  createDraggablePreview(preview,canvas);
  preview.emit("pointerdown",{clientX:950,clientY:120});
  preview.emit("pointermove",{clientX:200,clientY:220});
  assert.equal(preview.style.left,"50px");
  assert.equal(preview.style.top,"150px");
  preview.emit("pointermove",{clientX:-500,clientY:-500});
  assert.equal(preview.style.left,"20px");
  assert.equal(preview.style.top,"20px");
  preview.emit("pointermove",{clientX:5000,clientY:5000});
  assert.equal(preview.style.left,"800px");
  assert.equal(preview.style.top,"485px");
  preview.emit("pointercancel");
  assert.equal(captured,false);
  assert.equal(preview.classList.contains("dragging"),false);
  preview.emit("pointermove",{clientX:0,clientY:0});
  assert.equal(preview.style.left,"800px");
  width=480; resize();
  assert.equal(preview.style.left,"320px");
  preview.emit("keydown",{key:"ArrowLeft"});
  assert.equal(preview.style.left,"310px");
});

test("S starts and X or Stop closes camera input without resetting the game", async () => {
  const {createControls} = await load("controls");
  const nodes=new Map();
  globalThis.document={createElement(){return target()},querySelector(id){if(!nodes.has(id)) nodes.set(id,target());return nodes.get(id)}};
  globalThis.window=target();
  const state={input:{mode:"DRAW",point:{x:100,y:100}},selectedInput:"HAND",activeStroke:[],game:{state:"DRAWING"}};
  let starts=0,stops=0,status="";
  const actions=[];
  createControls({gamePanel:target(),handButton:target(),state,
    camera:{enableHandTracking(){starts++},stopCamera(){stops++}},
    queueEvent(event){actions.push(event)},setStatus(text){status=text},showToast(){}});
  window.emit("keydown",{key:"s"});
  assert.equal(starts,1);
  window.emit("keydown",{key:"x"});
  assert.equal(stops,1);
  assert.equal(state.selectedInput,"OFF");
  assert.deepEqual(state.input,{mode:"IDLE",point:null});
  assert.ok(status.includes("press S"));
  document.querySelector("#camera-stop").emit("click");
  assert.equal(stops,2);
  assert.equal(state.game.state,"DRAWING");
  assert.equal(actions.length,0);
  window.emit("keydown",{key:"s",metaKey:true});
  window.emit("keydown",{key:"s",target:{tagName:"INPUT"}});
  window.emit("keydown",{key:"s",repeat:true});
  assert.equal(starts,1);
});
