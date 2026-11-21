import * as THREE from "./vendor/three.module.js";
import { GLTFLoader } from "./vendor/loaders/GLTFLoader.js";

"use strict";
// Browser-only exploratory geometry. No geometry, pose, or interaction is authoritative.
const canvas = document.getElementById("world-canvas");
const status = document.getElementById("world-status");
const coords = document.getElementById("coords");
const nearbyLabel = document.getElementById("nearby");
const activity = document.getElementById("activity");
const transcript = document.getElementById("transcript");
const prompt = document.getElementById("prompt");
const sendButton = document.getElementById("send");
const forwardButton = document.getElementById("forward");
const targetLabel = document.getElementById("target-label");
const scene = new THREE.Scene();
scene.background = new THREE.Color("#07111d");
scene.fog = new THREE.FogExp2("#0b1d2a", 0.028);

const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 80);
let renderer;
try {
  renderer = new THREE.WebGLRenderer({canvas, antialias: true, powerPreference: "low-power"});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.4));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.25;
  status.textContent = "Play in 3D · engine initialized";
  status.dataset.state = "ready";
} catch (error) {
  status.dataset.state = "unavailable";
  status.textContent = "3D unavailable: WebGL could not initialize in this browser";
  activity.textContent = "Use the original text room to continue conversations.";
  throw error;
}

const hemi = new THREE.HemisphereLight(0xaac9e5, 0x203047, 2.1);
scene.add(hemi);
const keyLight = new THREE.DirectionalLight(0xc0d9ff, 2.2);
keyLight.position.set(-3, 9, 5);
scene.add(keyLight);
const moon = new THREE.PointLight(0x9e8ded, 65, 12, 2);
moon.position.set(-3, 4.3, -2);
scene.add(moon);
const lamp = new THREE.PointLight(0x75f3e4, 60, 10, 2);
lamp.position.set(2.8, 3.5, -0.2);
scene.add(lamp);
const floor = new THREE.Mesh(
  new THREE.PlaneGeometry(19, 19),
  new THREE.MeshStandardMaterial({color: 0x0e2434, roughness: 0.82, metalness: 0.15})
);
floor.rotation.x = -Math.PI / 2;
floor.receiveShadow = true;
scene.add(floor);
const grid = new THREE.GridHelper(18, 18, 0x3f7688, 0x1d4252);
grid.position.y = 0.011;
grid.material.opacity = 0.33;
grid.material.transparent = true;
scene.add(grid);

function mesh(geometry, color, metalness = 0.15, roughness = 0.58, emissive = 0) {
  return new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({
    color, metalness, roughness, emissive, emissiveIntensity: emissive ? 0.6 : 0
  }));
}
function box(width, height, depth, color, x, y, z, metal = 0.1) {
  const m = mesh(new THREE.BoxGeometry(width, height, depth), color, metal);
  m.position.set(x, y, z);
  scene.add(m);
  return m;
}
const roomWalls = [
  box(18, 3.8, .24, 0x142d3c, 0, 1.9, -9.05),
  box(.24, 3.8, 18, 0x153041, -9.05, 1.9, 0),
  box(.24, 3.8, 18, 0x153041, 9.05, 1.9, 0)
];
roomWalls.forEach(w => w.material.side = THREE.DoubleSide);
for (let i = -8; i <= 8; i += 2) {
  box(.07, 3.25, .06, 0x416c7d, i, 1.75, -8.88, 0.45);
}
for (const z of [-8, -5, -2, 1, 4, 7]) {
  box(.07, .06, 1.4, 0x2c6772, -8.89, 2.6, z, 0.4);
  box(.07, .06, 1.4, 0x2c6772, 8.89, 2.6, z, 0.4);
}
// The room is authored with abstract, explicitly noncanonical mannequin geometry.
const stations = {};
const interactables = [];
const pickTargets = [];
function register(id, group, radius = 2.2, description = "") {
  group.userData.interaction = id;
  interactables.push({id, group, radius, description});
  group.traverse(o => {if (o.isMesh) pickTargets.push(o);});
}
function createAvatar(id, x, color, accent) {
  const group = new THREE.Group();
  group.position.set(x, 0, -1.9);
  const base = mesh(new THREE.CylinderGeometry(0.68, 0.81, .20, 32), 0x213d51, 0.6, 0.3);
  base.position.y = .1;
  group.add(base);
  const rim = mesh(new THREE.TorusGeometry(.62, .035, 8, 48), accent, .6, .25, accent);
  rim.rotation.x = Math.PI / 2;
  rim.position.y = .23;
  group.add(rim);
  const body = mesh(new THREE.IcosahedronGeometry(.52, 1), color, .65, .2, accent);
  body.scale.set(.88, 1.36, .65);
  body.position.y = 1.10;
  group.add(body);
  const head = mesh(new THREE.IcosahedronGeometry(.31, 1), accent, .65, .22, accent);
  head.position.y = 2.13;
  group.add(head);
  const halo = mesh(new THREE.TorusGeometry(.42, .019, 6, 40), accent, .6, .24, accent);
  halo.rotation.x = .2;
  halo.position.y = 2.52;
  group.add(halo);
  scene.add(group);
  register(id, group, 2.55, id === "vera" ? "Speak with unverified Vera test model" : "Speak with native analytic JACK or its configured test model");
  stations[id] = {group, head, halo, body, baseY: head.position.y};
}
createAvatar("vera", -2.05, 0x7962aa, 0xb5a1f7);
createAvatar("jack", 2.05, 0x9b754b, 0xf4c980);
const rug = mesh(new THREE.CircleGeometry(3.25, 48),
  0x16464c, .25, .9);
rug.rotation.x = -Math.PI / 2;
rug.position.set(0, .017, -1.9);
scene.add(rug);
const rugRing = mesh(new THREE.RingGeometry(2.95, 3.0, 48), 0x37a4a4, 0.4, 0.4, 0x36bcb1);
rugRing.rotation.x = -Math.PI / 2;
rugRing.position.set(0, .018, -1.9);
scene.add(rugRing);

const beacon = new THREE.Group();
beacon.position.set(-4.75, 0, 2.0);
const beaconBase = mesh(new THREE.CylinderGeometry(.53, .65, .75, 24), 0x264554, 0.45);
beaconBase.position.y = .38; beacon.add(beaconBase);
const beaconCore = mesh(new THREE.OctahedronGeometry(.4), 0x5cdbcf, .2, .19, 0x2bf3c7);
beaconCore.position.y = 1.12; beacon.add(beaconCore);
const beaconLight = new THREE.PointLight(0x3af8d6, 24, 5, 2);
beaconLight.position.y = 1.15; beacon.add(beaconLight);
scene.add(beacon);
register("beacon", beacon, 2.1, "Toggle the signal beacon");
let beaconOn = true;

const archive = new THREE.Group();
archive.position.set(4.75, 0, 2.0);
archive.add((() => {const m=mesh(new THREE.CylinderGeometry(.67, .75, .9, 6), 0x31506d, .5);m.position.y=.45;return m;})());
const archiveStone = mesh(new THREE.DodecahedronGeometry(.38), 0xb1d8e0, .6, .26, 0x407e91);
archiveStone.position.y = 1.20; archive.add(archiveStone);
scene.add(archive);
register("archive", archive, 2.1, "Read the local room's memory limits");

const desk = new THREE.Group();
desk.position.set(0, 0, 4.85);
const deskTop = mesh(new THREE.BoxGeometry(2.25, .15, .9), 0x345469, .5);
deskTop.position.y = 1.05; desk.add(deskTop);
for (const x of [-.92, .92]) {
  const leg = mesh(new THREE.BoxGeometry(.11, 1.0, .12), 0x264050, .4);
  leg.position.set(x,.5,0);desk.add(leg);
}
const deskScreen = mesh(new THREE.BoxGeometry(1.2, .53, .09), 0x4ba6b1, .55, .16, 0x225c6a);
deskScreen.position.set(0,1.42,-.23);deskScreen.rotation.x=-.18;desk.add(deskScreen);
scene.add(desk);
register("console", desk, 1.8, "Inspect the interaction console");

const seat = new THREE.Group();
seat.position.set(-.2,0,-5.7);
const cushion = mesh(new THREE.BoxGeometry(2.1,.24,.78),0x475778,.15,.79);
cushion.position.y=.48;seat.add(cushion);
const back = mesh(new THREE.BoxGeometry(2.1,1.05,.16),0x3d4c6d,.15,.8);
back.position.set(0,.9,-.36);seat.add(back);
scene.add(seat);
register("bench", seat, 1.8, "Rest near the conversation stations");

const player = new THREE.Group();
player.position.set(0,0,3.4);
const playerCore = mesh(new THREE.SphereGeometry(.22,20,12),0x83eadd,.4,.24,0x3fb3a7);
playerCore.position.y=.47;player.add(playerCore);
const playerRing = mesh(new THREE.TorusGeometry(.41,.028,8,32),0x84e5d4,.4,.3,0x43a8a2);
playerRing.rotation.x=Math.PI/2;playerRing.position.y=.11;player.add(playerRing);
scene.add(player);
const WORLD_LIMIT = 8.25;
const obstruction = [
  {x:0,z:4.85,rx:1.43,rz:.7},
  {x:-.2,z:-5.7,rx:1.25,rz:.7},
  {x:-4.75,z:2.0,rx:.65,rz:.7},
  {x:4.75,z:2.0,rx:.65,rz:.7},
  {x:-2.05,z:-1.9,rx:.75,rz:.75},
  {x:2.05,z:-1.9,rx:.75,rz:.75}
];
function canWalk(x,z) {
  if(Math.abs(x)>WORLD_LIMIT || Math.abs(z)>WORLD_LIMIT) return false;
  return !obstruction.some(a=>Math.abs(x-a.x)<a.rx && Math.abs(z-a.z)<a.rz);
}

let yaw = .15, pitch = .62, distance = 6.6, dragging = false, dragDistance = 0;
let selected = "vera", busy = false, history = [], last = null, lastElapsed = performance.now();
const keys = new Set();
const moveButtons = new Set();
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

let actionVisibleUntil = 0;
function setActivity(title, detail) {
  nearbyLabel.textContent = title;
  activity.textContent = detail;
  actionVisibleUntil = performance.now() + 2100;
}
function choose(target) {
  selected = target;
  document.querySelectorAll(".identity").forEach(button=>{
    button.classList.toggle("selected",button.dataset.target===target);
    button.setAttribute("aria-pressed",String(button.dataset.target===target));
  });
  targetLabel.textContent = target.toUpperCase()+" station";
}
document.querySelectorAll(".identity").forEach(b=>b.addEventListener("click",()=>choose(b.dataset.target)));
const labels = {vera: document.getElementById("tag-vera"), jack:document.getElementById("tag-jack")};
function distanceTo(group) {
  return Math.hypot(group.position.x-player.position.x,group.position.z-player.position.z);
}
function nearest() {
  return interactables
    .map(item =>({...item,distance:distanceTo(item.group)}))
    .sort((a,b)=>a.distance-b.distance)[0];
}
function interact(id) {
  const item = interactables.find(a=>a.id===id);
  if(!item)return;
  const d=distanceTo(item.group);
  if(d>item.radius) {
    setActivity(item.id.toUpperCase()+" · out of reach", "Walk closer (WASD) before interacting. Distance "+d.toFixed(1)+"m");
    return;
  }
  if (id==="vera" || id==="jack") {
    choose(id);
    setActivity(id.toUpperCase()+" station selected","Use the conversation deck to talk to the configured local model. This avatar is not identity-qualified.");
    prompt.focus({preventScroll:true});
  } else if(id==="beacon") {
    beaconOn=!beaconOn;
    beaconLight.intensity=beaconOn?24:0;
    beaconCore.material.emissiveIntensity=beaconOn?.8:0;
    setActivity("Signal beacon "+(beaconOn?"on":"off"),"A local in-browser world-state change; no remote effects.");
  } else if(id==="archive") {
    archiveStone.rotation.y+=.6;
    setActivity("The archive","This room stores no transcript beyond this tab and holds no canonical AI memory.");
  } else if(id==="console") {
    deskScreen.material.emissiveIntensity=deskScreen.material.emissiveIntensity?0:.6;
    setActivity("The console","Vera and JACK are independent local model slots. Model-to-model forwarding requires your explicit click.");
  } else if(id==="bench") {
    setActivity("The waiting place","No task. No automatic loop. The room remains available while you choose what happens next.");
  }
}
function writeLine(name,text,isSystem=false) {
  const p=document.createElement("p");
  if(isSystem)p.className="system-line";
  else {
    const b=document.createElement("b");b.textContent=name; p.append(b);
  }
  p.append(document.createTextNode(text));
  transcript.append(p); transcript.scrollTop=transcript.scrollHeight;
}
function setBusy(value) {
  busy=value;sendButton.disabled=value;forwardButton.disabled=value||!last;
}
async function ask(target,message,forwardedFrom=null) {
  const body=String(message||"").trim();
  if(!body||busy)return;
  const ctx=history.slice(-10);
  const turn={target,message:body,context:ctx};
  if(forwardedFrom)turn.forwarded_from=forwardedFrom;
  setBusy(true);
  try {
    const reply=await fetch("/api/turn",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify(turn)
    });
    const data=await reply.json();
    if(!reply.ok)throw Error(data.error||"Local inference request failed");
    if(!forwardedFrom) {
      writeLine("YOU",body);
      history.push({speaker:"human",text:body});
      // Do not erase a newer draft typed while the request was in flight.
      if(prompt.value.trim()===body) prompt.value="";
    } else {
      writeLine("FORWARDED",body);
    }
    writeLine(target.toUpperCase()+" · UNVERIFIED",data.reply);
    // HTTP replies may be 4,000 chars; context entries are capped at 2,000.
    // Preserve the full visible answer, but bound subsequent model context.
    history.push({speaker:target,text:data.reply.slice(0,2000)});
    history=history.slice(-10);
    last={speaker:target,text:data.reply};
    setActivity("Received "+target.toUpperCase()+" reply", "Unverified model response. No virtual-world authority was granted.");
  } catch(err) {
    // Leave the current draft untouched; a newer edit or deletion may be
    // intentional, so never resurrect an older request into the transcript.
    // No failed request is automatically retried or admitted to model history.
    writeLine("ERROR",String(err.message||err),true);
  } finally {setBusy(false);}
}
sendButton.addEventListener("click",()=>{
  const text=prompt.value.trim();if(!text)return;ask(selected,text);
});
prompt.addEventListener("keydown",e=>{if(e.key==="Enter"&&(e.ctrlKey||e.metaKey)){e.preventDefault();sendButton.click();}});
forwardButton.addEventListener("click",()=>{
  if(!last||busy)return;
  const to=last.speaker==="vera"?"jack":"vera";
  choose(to);
  // Preserve claimed source separately from its text, not as a natural-
  // language authority claim; local room still treats the claim as unverified.
  ask(to,last.text.slice(0,1900),last.speaker);
});
document.getElementById("clear").addEventListener("click",()=>{
  if(busy)return;
  history=[];last=null;
  transcript.replaceChildren();setBusy(false);
  writeLine("SYSTEM","Conversation cleared from this tab.",true);
});

document.addEventListener("keydown",e=>{
  if(e.target.closest("textarea,input,button,select") || e.ctrlKey || e.altKey || e.metaKey) return;
  const k=e.key.toLowerCase();
  if(["w","a","s","d","arrowup","arrowdown","arrowleft","arrowright","e"].includes(k)){
    e.preventDefault();keys.add(k);
  }
  if(k==="e"&&!e.repeat) {
    const item=nearest();
    if(item && item.distance<item.radius)interact(item.id);
    else setActivity("Nothing within reach","Move closer to an avatar or object, then press E.");
  }
});
document.addEventListener("keyup",e=>keys.delete(e.key.toLowerCase()));
window.addEventListener("blur",()=>{keys.clear();moveButtons.clear();dragging=false;});
document.querySelectorAll("[data-move]").forEach(button=>{
  button.addEventListener("pointerdown",e=>{e.preventDefault();moveButtons.add(button.dataset.move);button.setPointerCapture(e.pointerId);});
  for(const name of ["pointerup","pointercancel","lostpointercapture"])
    button.addEventListener(name,()=>moveButtons.delete(button.dataset.move));
});
canvas.addEventListener("pointerdown",e=>{
  dragging=true;dragDistance=0;
  canvas.setPointerCapture(e.pointerId);
});
canvas.addEventListener("pointermove",e=>{
  if(!dragging)return;
  const dx=e.movementX||0,dy=e.movementY||0;
  dragDistance+=Math.abs(dx)+Math.abs(dy);
  yaw+=dx*.005; pitch=Math.max(.2,Math.min(1.18,pitch+dy*.004));
});
canvas.addEventListener("pointerup",e=>{
  if(!dragging)return;
  dragging=false;
  if(dragDistance>7)return;
  const rect=canvas.getBoundingClientRect();
  pointer.set(((e.clientX-rect.left)/rect.width)*2-1,
              -((e.clientY-rect.top)/rect.height)*2+1);
  raycaster.setFromCamera(pointer,camera);
  const hits=raycaster.intersectObjects(pickTargets,false);
  if(!hits.length)return;
  let object=hits[0].object;
  while(object&&!object.userData.interaction)object=object.parent;
  if(object)interact(object.userData.interaction);
});
canvas.addEventListener("wheel",e=>{
  e.preventDefault();distance=Math.max(3.5,Math.min(10.5,distance+Math.sign(e.deltaY)*.5));
},{passive:false});
function resize() {
  const rect=canvas.getBoundingClientRect();
  if(!rect.width||!rect.height)return;
  renderer.setSize(rect.width,rect.height,false);
  camera.aspect=rect.width/rect.height;camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(canvas);
window.addEventListener("resize",resize);
resize();
choose("vera");

// Private preview assets are explicit, hash-gated by the localhost server.
// A loaded mesh is a visual *candidate*, never canonical identity or permission.
async function loadOptInPreviews() {
  try {
    const response = await fetch("/api/preview-assets", {cache: "no-store"});
    if (!response.ok) return;
    const payload = await response.json();
    if (!Array.isArray(payload.previews)) return;
    const loader = new GLTFLoader();
    for (const binding of payload.previews) {
      const id = binding.slot;
      if (!(id === "vera" || id === "jack") ||
          binding.approval !== "UNVERIFIED_EXPERIMENTAL_PREVIEW" ||
          binding.url !== "/sandbox/previews/" + id + ".glb") continue;
      loader.load(binding.url, gltf => {
        const root = gltf.scene;
        if (!root) return;
        const bounds = new THREE.Box3().setFromObject(root);
        const extent = bounds.getSize(new THREE.Vector3());
        const largest = Math.max(extent.x, extent.y, extent.z);
        if (!Number.isFinite(largest) || largest <= 0) return;
        const scale = 2.6 / largest;
        root.scale.multiplyScalar(scale);
        bounds.setFromObject(root);
        const center = bounds.getCenter(new THREE.Vector3());
        root.position.set(-center.x, 0.24 - bounds.min.y, -center.z);
        const station = stations[id];
        station.group.add(root);
        root.traverse(object => {if (object.isMesh) pickTargets.push(object);});
        station.body.visible = false;
        station.head.visible = false;
        station.halo.visible = false;
        labels[id].textContent = id.toUpperCase() + " · EXPERIMENTAL GLB · NOT APPROVED";
        status.textContent = "3D ready · private experimental " + id.toUpperCase() + " mesh loaded (unapproved)";
        status.dataset.state = "ready";
      }, undefined, () => {
        status.textContent = "3D ready · experimental GLB unavailable; placeholder retained";
      });
    }
  } catch (_) {
    status.textContent = "3D ready · experimental preview metadata unavailable";
  }
}
loadOptInPreviews();
function frame(now) {
  const delta=Math.min(.06,(now-lastElapsed)/1000);lastElapsed=now;
  let f=0,s=0;
  if(keys.has("w")||keys.has("arrowup")||moveButtons.has("forward"))f+=1;
  if(keys.has("s")||keys.has("arrowdown")||moveButtons.has("back"))f-=1;
  if(keys.has("a")||keys.has("arrowleft")||moveButtons.has("left"))s-=1;
  if(keys.has("d")||keys.has("arrowright")||moveButtons.has("right"))s+=1;
  if(f||s) {
    const len=Math.hypot(f,s),speed=3.0*delta/len;
    const x=player.position.x+speed*(s*Math.cos(yaw)-f*Math.sin(yaw));
    const z=player.position.z+speed*(-f*Math.cos(yaw)-s*Math.sin(yaw));
    if(canWalk(x,player.position.z))player.position.x=x;
    if(canWalk(player.position.x,z))player.position.z=z;
  }
  playerCore.position.y=.47+(f||s?Math.sin(now*.018)*.035:0);
  playerRing.rotation.z=now*.0001;
  beaconCore.rotation.y=now*.0005;
  beaconCore.position.y=1.12+Math.sin(now*.0015)*.09;
  archiveStone.rotation.y+=delta*.14;
  for(const id of ["vera","jack"]) {
    const a=stations[id];
    a.head.position.y=a.baseY+Math.sin(now*.0018+(id==="jack"?1.8:0))*.045;
    a.halo.rotation.y+=delta*.23;
  }
  const look=new THREE.Vector3(player.position.x,1.14,player.position.z);
  camera.position.set(look.x+Math.sin(yaw)*Math.cos(pitch)*distance,
                      look.y+Math.sin(pitch)*distance,
                      look.z+Math.cos(yaw)*Math.cos(pitch)*distance);
  camera.lookAt(look);
  for(const id of ["vera","jack"]) {
    const tag=labels[id];
    const p=stations[id].group.position.clone().add(new THREE.Vector3(0,2.94,0));
    p.project(camera);
    const visible=p.z<1&&p.z>-1&&Math.abs(p.x)<1.15&&Math.abs(p.y)<1.15;
    tag.style.opacity=visible?"1":"0";
    if(visible) {
      tag.style.left=((p.x+1)*.5*canvas.clientWidth)+"px";
      tag.style.top=((-p.y+1)*.5*canvas.clientHeight)+"px";
    }
  }
  const near=nearest();
  if(now > actionVisibleUntil) {
    if(near && near.distance<near.radius && !document.activeElement?.matches("textarea")) {
      nearbyLabel.textContent=near.id.toUpperCase()+" · E to interact";
    } else if(!near || near.distance>=near.radius) {
      if(nearbyLabel.textContent.includes("· E to interact"))
        nearbyLabel.textContent="Explore the room";
    }
  }
  coords.textContent="X "+player.position.x.toFixed(1)+" · Z "+player.position.z.toFixed(1);
  renderer.render(scene,camera);
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
