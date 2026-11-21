"use strict";
const puppeteer=require(process.env.PUPPETEER_MODULE||"puppeteer");
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function run() {
const base=process.argv[2];
if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(base)) throw Error("LOCAL_BASE_REQUIRED");
const browser=await puppeteer.launch({
  headless:true,
  executablePath:process.env.HABITAT_BROWSER_BINARY,
  defaultViewport:{width:1280,height:800},
  args:["--no-first-run","--no-default-browser-check","--disable-background-networking","--disable-extensions"]
});
try{
const page=await browser.newPage();
const errors=[],outbound=[];
page.on("pageerror",e=>errors.push(String(e)));
page.on("console",m=>{if(m.type()==="error")errors.push(m.text().slice(0,500));});
await page.setRequestInterception(true);
page.on("request",req=>{
  if(req.url().startsWith(base+"/"))req.continue();
  else{outbound.push(req.url());req.abort();}
});
await page.goto(base+"/sandbox",{waitUntil:"domcontentloaded",timeout:20000});
await page.waitForFunction(()=>document.querySelector("#world-status")?.dataset.state==="ready",
   {timeout:20000});
await page.waitForFunction(()=>document.querySelector("#world-canvas").width>0
  && document.querySelector("#world-canvas").height>0,{timeout:10000});
const canvasSize=await page.$eval("#world-canvas",c=>({width:c.width,height:c.height}));
const original=await page.$eval("#coords",x=>x.textContent);
await page.keyboard.down("w");
await pause(1350);
await page.keyboard.up("w");
await pause(100);
const moved=await page.$eval("#coords",x=>x.textContent);
const coordZ=text=>Number((text.match(/Z (-?[0-9.]+)/)||[])[1]);
if(!(coordZ(moved)<coordZ(original)-2.1))
  throw Error("W_KEY_DID_NOT_MOVE_PLAYER "+JSON.stringify({original,moved}));
await page.keyboard.press("e");
await pause(100);
const station=await page.$eval("#nearby",e=>e.textContent);
if(!station.toLowerCase().includes("vera"))
  throw Error("NEAREST_AVATAR_INTERACTION_FAILED "+station);
// Re-focus world after E selected the model composer. Walk to the local beacon.
await page.$eval("#world-canvas",c=>c.focus());
await page.keyboard.down("a");await pause(950);await page.keyboard.up("a");
await page.keyboard.down("s");await pause(930);await page.keyboard.up("s");
await page.keyboard.press("e");await pause(80);
const beaconAction=await page.$eval("#nearby",e=>e.textContent);
if(!beaconAction.toLowerCase().includes("signal beacon off"))
  throw Error("BEACON_INTERACTION_FAILED "+beaconAction);
await page.type("#prompt","synthetic hello from 3D room");
await page.click("#send");
await page.waitForFunction(()=>document.querySelector("#transcript").textContent.includes("synthetic fake Vera reply"),
  {timeout:10000});
await page.click("#forward");
await page.waitForFunction(()=>document.querySelector("#transcript").textContent.includes("synthetic fake JACK reply"),
  {timeout:10000});
const lines=await page.$eval("#transcript",e=>e.querySelectorAll("p").length);
if(lines!==5)throw Error("UNEXPECTED_CHAT_LOG_COUNT "+lines);
await page.click("#clear");
const cleared=await page.$eval("#transcript",e=>e.textContent);
if(cleared.includes("synthetic fake JACK reply"))throw Error("CLEAR_DID_NOT_ERASE_MODEL_TEXT");
const pixel=await page.evaluate(()=>{
  const c=document.querySelector("#world-canvas");
  const gl=c.getContext("webgl2");
  if(!gl)return {webgl:false};
  const bytes=new Uint8Array(4);
  gl.readPixels(Math.floor(c.width/2),Math.floor(c.height/2),1,1,gl.RGBA,gl.UNSIGNED_BYTE,bytes);
  return {webgl:true,rgba:Array.from(bytes),glError:gl.getError()};
});
if(!pixel.webgl)throw Error("NO_WEBGL2_CONTEXT");
if(errors.length)throw Error("BROWSER_JS_ERRORS "+JSON.stringify(errors.slice(0,5)));
if(outbound.length)throw Error("EXTERNAL_REQUEST_ATTEMPT "+outbound.join(", "));
await page.screenshot({path:process.env.HABITAT_SCREENSHOT_PATH,fullPage:true});
console.log(JSON.stringify({status:"PASS",webgl:pixel,canvasSize,initial:original,afterMovement:moved,
  movedForward:true,avatarInteraction:"vera",beaconToggled:true,manualModelMessages:2,chatClear:true,
  externalRequests:outbound.length,jsErrors:errors.length,screenshot:process.env.HABITAT_SCREENSHOT_PATH}));
}finally{await browser.close();}
}
run().catch(e=>{console.error(e.stack||String(e));process.exit(1)});
