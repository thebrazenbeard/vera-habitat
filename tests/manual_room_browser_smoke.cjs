"use strict";
// Optional browser acceptance probe. No remote models, private data, or network assets.
const puppeteer = require(process.env.PUPPETEER_MODULE || "puppeteer");

async function main() {
  const browserBinary = process.env.HABITAT_BROWSER_BINARY;
  if (!browserBinary) throw Error("Set HABITAT_BROWSER_BINARY to a local Edge/Chromium executable");
  const origin = process.argv[2];
  if (!/^http:\/\/127\.0\.0\.1:\d+\/$/.test(origin))
    throw Error("Only an explicit loopback test URL is accepted");
  const browser = await puppeteer.launch({
    executablePath: browserBinary,
    headless: true,
    args: [
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-extensions",
      "--disable-background-networking"
    ],
    defaultViewport: {width: 1024, height: 768}
  });
  try {
    const page = await browser.newPage();
    const jsErrors = [];
    page.on("pageerror", error => jsErrors.push(String(error)));
    await page.goto(origin, {waitUntil: "domcontentloaded", timeout: 15000});
    const heading = await page.$eval("h1", e => e.textContent);
    if (!heading.includes("Two-model room"))
      throw Error("Room heading not found");
    const role = await page.$eval("#log", e => e.getAttribute("role"));
    if (role !== "log") throw Error("Conversation log lacks log role");
    await page.type("#message", "synthetic browser hello");
    await page.click('button[data-target="vera"]');
    await page.waitForFunction(
      () => document.querySelector("#log").textContent.includes("VERA (unverified):"),
      {timeout: 12000}
    );
    const text = await page.$eval("#log", e => e.textContent);
    if (!text.includes("synthetic browser hello"))
      throw Error("Synthetic message missing");
    const injection = await page.evaluate(() =>
      window.habitatInjected === true ||
      document.querySelector("#log img") !== null
    );
    if (injection) throw Error("Untrusted model output was parsed as HTML");
    if (!text.includes("<img "))
      throw Error("HTML-shaped model reply not preserved as literal text");
    await page.click("#pass");
    await page.waitForFunction(
      () => document.querySelector("#log").textContent.includes("JACK (unverified):"),
      {timeout: 12000}
    );
    const entries = await page.$eval("#log", e => e.querySelectorAll("p").length);
    if (entries !== 4) throw Error("Expected 4 log entries, found " + entries);
    await page.setViewport({width: 375, height: 812});
    const overflow = await page.evaluate(() =>
      document.documentElement.scrollWidth > window.innerWidth + 1
    );
    if (overflow) throw Error("Horizontal overflow at mobile viewport");
    await page.click("#clear");
    const afterClear = await page.$eval("#log", e => e.children.length);
    if (afterClear !== 0) throw Error("Clear did not remove log entries");
    if (jsErrors.length) throw Error("Browser JS errors: " + jsErrors.join("; "));
    console.log(JSON.stringify({
      status: "PASS",
      browser: "Chromium/Edge",
      manualSend: true,
      forwardOnce: true,
      modelHtmlNotExecuted: true,
      mobileOverflow: false,
      clearSuccess: true,
      javascriptErrors: 0
    }));
  } finally {
    await browser.close();
  }
}
main().catch(error => {
  console.error(error.stack || String(error));
  process.exitCode = 1;
});
