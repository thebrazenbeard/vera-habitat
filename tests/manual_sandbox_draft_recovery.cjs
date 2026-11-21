"use strict";
const puppeteer=require(process.env.PUPPETEER_MODULE||"puppeteer");
async function run(){
  const base=process.argv[2];
  if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(base)) throw Error("LOCAL_ONLY");
  const browser=await puppeteer.launch({
    headless:true,executablePath:process.env.HABITAT_BROWSER_BINARY,
    defaultViewport:{width:1160,height:760},
    args:["--no-first-run","--no-default-browser-check","--disable-background-networking","--disable-extensions"]
  });
  try{
    const page=await browser.newPage();
    const outbound=[],errors=[];
    let failedOnce=false, posted=0;
    page.on("pageerror",e=>errors.push(String(e)));
    await page.setRequestInterception(true);
    page.on("request",req=>{
      if(!req.url().startsWith(base+"/")){outbound.push(req.url());req.abort();return;}
      if(req.url()===base+"/api/turn"){
        posted++;
        if(!failedOnce){
          failedOnce=true;
          req.respond({status:503,contentType:"application/json",
                       body:JSON.stringify({error:"Synthetic local model unavailable"})});
          return;
        }
        if(posted===3){
          // Leave a deterministic window for the person to edit the next draft.
          setTimeout(()=>req.continue(),750);
          return;
        }
        if(posted===4){
          setTimeout(()=>req.respond({status:503,contentType:"application/json",
            body:JSON.stringify({error:"Synthetic second failure"})}),750);
          return;
        }
        if(posted===5){
          // Clearing the composer while a request is in flight is intentional.
          setTimeout(()=>req.respond({status:503,contentType:"application/json",
            body:JSON.stringify({error:"Synthetic cleared-draft failure"})}),750);
          return;
        }
      }
      req.continue();
    });
    await page.goto(base+"/sandbox",{waitUntil:"domcontentloaded",timeout:18000});
    await page.waitForFunction(()=>document.querySelector("#world-status")?.dataset.state==="ready",{timeout:18000});
    const initialCount=await page.$eval("#transcript",e=>e.querySelectorAll("p").length);
    const original="SYNTHETIC_RECOVER_ME_ON_FAILURE";
    await page.type("#prompt",original);
    await page.click("#send");
    await page.waitForFunction(()=>document.querySelector("#transcript")?.textContent.includes("Synthetic local model unavailable"),{timeout:12000});
    const afterFailed=await page.$eval("#prompt",e=>e.value);
    if(afterFailed!==original)throw Error("DRAFT_LOST_ON_503 expected="+original+" found="+JSON.stringify(afterFailed));
    const beforeRetry=await page.$eval("#transcript",e=>e.querySelectorAll("p").length);
    if(beforeRetry!==initialCount+1)throw Error("FAILED_TURN_ADMITTED_TO_HISTORY "+JSON.stringify({beforeRetry,initialCount}));
    if(posted!==1)throw Error("AUTOMATIC_RETRY_OR_UNEXPECTED_SEND "+posted);
    await page.click("#send");
    await page.waitForFunction(()=>document.querySelector("#transcript")?.textContent.includes("SYNTHETIC_FAKE_REPLY"),{timeout:12000});
    const afterSuccess=await page.$eval("#prompt",e=>e.value);
    if(afterSuccess!=="")throw Error("SUCCESS_DID_NOT_CLEAR_UNEDITED_DRAFT");
    const lines=await page.$eval("#transcript",e=>Array.from(e.querySelectorAll("p"),x=>x.textContent));
    if(lines.length!==initialCount+3||!lines[initialCount+1].includes(original)||!lines[initialCount+2].includes("SYNTHETIC_FAKE_REPLY"))
      throw Error("TURN_HISTORY_INCORRECT "+JSON.stringify(lines));
    if(posted!==2||outbound.length||errors.length)
      throw Error("RETRY_OR_EXTERNAL_OR_BROWSER_ERROR "+JSON.stringify({posted,outbound,errors}));

    const sentWhileEditable="SYNTHETIC_IN_FLIGHT_MESSAGE";
    const newerDraft="SYNTHETIC_UNSENT_NEWER_DRAFT";
    await page.type("#prompt",sentWhileEditable);
    await page.click("#send");
    await page.waitForFunction(()=>document.querySelector("#send").disabled,{timeout:3000});
    await page.$eval("#prompt",(el,newText)=>el.value=newText,newerDraft);
    await page.waitForFunction(()=>!document.querySelector("#send").disabled,{timeout:12000});
    const retainedAfterSuccess=await page.$eval("#prompt",el=>el.value);
    if(retainedAfterSuccess!==newerDraft)throw Error("IN_FLIGHT_EDIT_CLOBBERED_AFTER_SUCCESS");
    if(posted!==3)throw Error("UNEXPECTED_THIRD_SEND "+posted);

    const newestDraft="SYNTHETIC_UNSENT_NEWEST_DRAFT";
    await page.click("#send");
    await page.waitForFunction(()=>document.querySelector("#send").disabled,{timeout:3000});
    await page.$eval("#prompt",(el,newText)=>el.value=newText,newestDraft);
    await page.waitForFunction(()=>document.querySelector("#transcript")?.textContent.includes("Synthetic second failure"),{timeout:12000});
    if(await page.$eval("#prompt",el=>el.value)!==newestDraft)
      throw Error("IN_FLIGHT_EDIT_CLOBBERED_AFTER_FAILURE");
    const remembered=await page.$eval("#transcript",e=>e.textContent);
    if(remembered.includes("No confirmed reply for earlier draft")||remembered.includes(newerDraft))
      throw Error("STALE_DRAFT_RESURRECTED_AFTER_PERSON_EDITED_IT");
    if(posted!==4||outbound.length||errors.length)
      throw Error("UNEXPECTED_AUTO_RETRY_OR_NETWORK "+JSON.stringify({posted,outbound,errors}));

    await page.click("#send");
    await page.waitForFunction(()=>document.querySelector("#send").disabled,{timeout:3000});
    await page.$eval("#prompt",el=>el.value="");
    await page.waitForFunction(()=>document.querySelector("#transcript")?.textContent.includes("Synthetic cleared-draft failure"),{timeout:12000});
    const afterCleared=await page.$eval("#prompt",el=>el.value);
    const transcriptAfterClear=await page.$eval("#transcript",el=>el.textContent);
    if(afterCleared!==""||transcriptAfterClear.includes(newestDraft))
      throw Error("INTENTIONAL_DRAFT_CLEAR_WAS_REVERSED");
    if(posted!==5||outbound.length||errors.length)
      throw Error("UNEXPECTED_AUTO_RETRY_OR_NETWORK "+JSON.stringify({posted,outbound,errors}));

    console.log(JSON.stringify({status:"PASS",first_503_retains_draft:true,
                               manual_retry_only:true,newer_draft_survives_success:true,
                               newer_draft_survives_failure:true,
                               older_edited_or_cleared_draft_not_resurrected:true,
                               posted,backend_calls_expected:2,external_requests:outbound.length,
                               page_errors:errors.length}));
  }finally{await browser.close();}
}
run().catch(e=>{console.error(e.stack||String(e));process.exit(1)});
