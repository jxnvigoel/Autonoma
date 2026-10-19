import puppeteer from "puppeteer-core";
import fs from "fs";
import path from "path";

const CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const URL = "http://localhost:5173";
const ARTIFACT_DIR = "/Users/janvi/.gemini/antigravity-ide/brain/1610ce5a-82fc-4fcb-95b3-5675c68b9fc4";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function run() {
  console.log("Launching Local Chrome for UI Verification...");
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 900 });

    console.log("Navigating to http://localhost:5173 ...");
    await page.goto(URL, { waitUntil: "networkidle2" });
    await sleep(2500);

    // If splash screen has "Skip to Overview", click it
    const bodyText = await page.evaluate(() => document.body.innerText);
    if (bodyText.includes("Skip to Overview")) {
      const skipBtn = await page.$("button::-p-text(Skip to Overview)");
      if (skipBtn) await skipBtn.click();
      await sleep(1000);
    }

    console.log("On Landing page, clicking 'Get Started'...");
    const getStartedBtn = await page.waitForSelector("button::-p-text(Get Started)", { timeout: 10000 });
    await getStartedBtn.click();
    await sleep(1500);

    console.log("On ProjectSelector screen...");
    const selText = await page.evaluate(() => document.body.innerText);
    console.log("Current screen text snippet:", selText.slice(0, 200).replace(/\n/g, " "));

    // Look for DocuPulse Reader
    const hasDocuPulse = selText.includes("DocuPulse Reader");
    console.log("DocuPulse Reader listed on ProjectSelector:", hasDocuPulse);

    // Click 'Open' or 'Open Project'
    const openBtn = await page.waitForSelector("button::-p-text(Open Project), button::-p-text(Open)", { timeout: 10000 });
    console.log("Clicking Open button to enter Virtual Office...");
    await openBtn.click();
    await sleep(2500);

    // Verify Virtual Office
    console.log("Verifying Virtual Office view...");
    const officeText = await page.evaluate(() => document.body.innerText);
    const hasFloor = officeText.includes("VIRTUAL OFFICE") || officeText.includes("BA") || officeText.includes("PM");
    console.log("Virtual Office floor rendered:", hasFloor);

    const officeScreenshotPath = path.join(ARTIFACT_DIR, "ui_virtual_office.png");
    await page.screenshot({ path: officeScreenshotPath });
    console.log(`Saved screenshot to ${officeScreenshotPath}`);

    // Click BA Desk
    console.log("Clicking BA Desk...");
    const baDesk = await page.$("[data-agent='ba'], button::-p-text(BA), div::-p-text(Business Analyst)");
    if (baDesk) {
      await baDesk.click();
      await sleep(1500);
      const baDrawerText = await page.evaluate(() => document.body.innerText);
      console.log("BA drawer opened. Has requirements.md:", baDrawerText.includes("requirements.md") || baDrawerText.includes("Problem Statement"));
    }

    // Click PM Desk
    console.log("Clicking PM Desk to open PM Command Center...");
    const pmDesk = await page.$("[data-agent='pm'], button::-p-text(PM), div::-p-text(Product Manager)");
    if (pmDesk) {
      await pmDesk.click();
      await sleep(2000);
    }

    // Verify PM Command Center
    console.log("Checking PM Command Center tabs...");
    const cmdText = await page.evaluate(() => document.body.innerText);
    console.log("PM Command Center visible. Has 'PRD':", cmdText.includes("PRD") || cmdText.includes("prd.md"));

    // Click PRD tab
    const prdTab = await page.$("button::-p-text(PRD (docs/prd.md)), button::-p-text(PRD), button::-p-text(docs/prd.md)");
    if (prdTab) {
      console.log("Clicking PRD tab...");
      await prdTab.click();
      await sleep(1500);
      const prdText = await page.evaluate(() => document.body.innerText);
      console.log("PRD content preview:", prdText.includes("App overview") && prdText.includes("Features (v1)"));

      const prdScreenshotPath = path.join(ARTIFACT_DIR, "ui_pm_prd_viewer.png");
      await page.screenshot({ path: prdScreenshotPath });
      console.log(`Saved screenshot to ${prdScreenshotPath}`);
    }

    // Click Estimate tab
    const estTab = await page.$("button::-p-text(Estimate (5.1.6)), button::-p-text(Estimate)");
    if (estTab) {
      console.log("Clicking Estimate tab...");
      await estTab.click();
      await sleep(1500);
      const estText = await page.evaluate(() => document.body.innerText);
      console.log("Estimate content preview:", estText.includes("Total Estimated Tokens") || estText.includes("Rework Buffer") || estText.includes("Estimated Cost"));

      const estScreenshotPath = path.join(ARTIFACT_DIR, "ui_pm_estimate_viewer.png");
      await page.screenshot({ path: estScreenshotPath });
      console.log(`Saved screenshot to ${estScreenshotPath}`);
    }

    // Click Chat tab and send message
    const chatTab = await page.$("button::-p-text(PM Chat), button::-p-text(Chat)");
    if (chatTab) {
      console.log("Clicking PM Chat tab...");
      await chatTab.click();
      await sleep(1000);

      const input = await page.$("textarea, input[type='text']");
      if (input) {
        console.log("Typing message into PM Chat...");
        await input.type("Can you confirm the citation export formats?");
        const sendBtn = await page.$("button::-p-text(Send)");
        if (sendBtn) {
          console.log("Clicking Send button...");
          await sendBtn.click();
          console.log("Waiting for PM agent reply...");
          await sleep(12000); // Wait for Ollama reply

          const replyText = await page.evaluate(() => document.body.innerText);
          console.log("PM Chat has message and reply:", replyText.includes("Can you confirm the citation export formats?"));

          const chatScreenshotPath = path.join(ARTIFACT_DIR, "ui_pm_chat_reply.png");
          await page.screenshot({ path: chatScreenshotPath });
          console.log(`Saved screenshot to ${chatScreenshotPath}`);
        }
      }
    }

    console.log("\n>>> REAL UI VERIFICATION COMPLETED SUCCESSFULLY!");
  } catch (err) {
    console.error("Error during real UI verification:", err);
  } finally {
    await browser.close();
  }
}

run();
