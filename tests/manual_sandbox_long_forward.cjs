"use strict";
const puppeteer=require(process.env.PUPPETEER_MODULE||"puppeteer");
async function run(){
  const base=process.argv[2];
  if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(base))throw Error("LOCAL_BASE_REQUIRED");
  const browser=await puppeteer.launch({
    headless:true,executablePath:process.env.HABITAT_BROWSER_BINARY,
    defaultViewport:{width:1100,height:700},
    args:["--no-first-run","--no-default-browser-check","--disable-background-networking","--disable-extensions"]});
  try{
    const page=await browser.newPage();
    const out=[],errors=[],turns=[];
    page.on("pageerror",e=>errors.push(String(e)));
    await page.setRequestInterception(true);
    page.on("request",req=>{
      if(!req.url().startsWith(base+"/")){out.push(req.url());req.abort();return;}
      if(req.url()===base+"/api/turn")turns.push(JSON.parse(req.postData()));
      req.continue();
    });
    await page.goto(base+"/sandbox",{waitUntil:"domcontentloaded",timeout:16000});
    await page.waitForFunction(()=>document.querySelector("#world-status")?.dataset.state==="ready",{timeout:16000});
    await page.type("#prompt","synthetic hello");
    await page.click("#send");
    await page.waitForFunction(()=>document.querySelector("#transcript")?.textContent.includes("SYNTHETIC_OPTIONAL_OFFER_"),{timeout:12000});
    await page.click("#forward");
    await page.waitForFunction(()=>document.querySelector("#transcript")?.textContent.includes("SYNTHETIC_JACK_ACK"),{timeout:12000});
    if(turns.length!==2||turns[1].forwarded_from!=="vera")
      throw Error("TYPED_SOURCE_CLAIM_MISSING "+JSON.stringify(turns.map(t=>Object.keys(t))));
    if(turns[1].message!=="SYNTHETIC_OPTIONAL_OFFER_"+("x".repeat(1900-("SYNTHETIC_OPTIONAL_OFFER_".length))))
      throw Error("FORWARD_TEXT_MISMATCH");
    if(turns[1].context.at(-1).speaker!=="vera"||turns[1].context.at(-1).text.length>2000)
      throw Error("CONTEXT_LENGTH_OR_SOURCE_MISMATCH");
    if(out.length||errors.length)throw Error("BROWSER_ERRORS "+JSON.stringify({out,errors}));
    console.log(JSON.stringify({status:"PASS",requests:turns.length,
      context_length:turns[1].context.at(-1).text.length,
      claim:turns[1].forwarded_from,outbound:out.length,errors:errors.length}));
  }finally{await browser.close();}
}
run().catch(e=>{console.error(e.stack||String(e));process.exit(1)});
