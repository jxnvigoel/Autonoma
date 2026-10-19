const puppeteer = require('puppeteer-core');
const path = require('path');

const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const ARTIFACT_DIR = '/Users/janvi/.gemini/antigravity-ide/brain/1610ce5a-82fc-4fcb-95b3-5675c68b9fc4';

async function run() {
  console.log('Launching Chrome via puppeteer-core...');
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,900']
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 900 });

    console.log('1. Loading app...');
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle0' });

    // Dismiss splash screen by clicking
    await page.mouse.click(500, 400);
    await new Promise(r => setTimeout(r, 1200));

    // On Landing page, click "Get Started"
    console.log('2. Clicking Get Started...');
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const startBtn = btns.find(b => b.innerText && b.innerText.includes('Get Started'));
      if (startBtn) startBtn.click();
    });
    await new Promise(r => setTimeout(r, 1500));

    // On ProjectSelector: click "Open Project" on BioVault Lab
    console.log('3. Clicking Open Project on BioVault Lab...');
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const openBtn = btns.find(b => b.innerText && b.innerText.includes('Open Project'));
      if (openBtn) openBtn.click();
    });

    // Wait for Virtual Office floor to load
    console.log('4. Waiting for Virtual Office floor...');
    await new Promise(r => setTimeout(r, 2500));

    // Capture Virtual Office floor screenshot
    const floorPath = path.join(ARTIFACT_DIR, 'ui_architect_floor.png');
    await page.screenshot({ path: floorPath, fullPage: false });
    console.log('Saved Virtual Office floor screenshot to:', floorPath);

    // Click on Architect desk in bottom roster or desk card to open Command Center
    console.log('5. Clicking on Architect in roster/desk...');
    const clicked = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const archRoster = btns.find(b => b.innerText && b.innerText.includes('Solution Arc'));
      if (archRoster) {
        archRoster.click();
        return 'roster_clicked';
      }
      const badges = Array.from(document.querySelectorAll('span'));
      const archBadge = badges.find(s => s.innerText === 'ARCH');
      if (archBadge) {
        const card = archBadge.closest('.group');
        if (card) {
          card.click();
          return 'card_clicked';
        }
      }
      return 'none';
    });
    console.log('Click result:', clicked);
    await new Promise(r => setTimeout(r, 2000));

    // Capture Command Center with Architect TRD tab
    const ccTrdPath = path.join(ARTIFACT_DIR, 'ui_architect_command_center.png');
    await page.screenshot({ path: ccTrdPath, fullPage: false });
    console.log('Saved Command Center screenshot to:', ccTrdPath);

    // Click on Database Schema tab
    console.log('6. Clicking on Schema tab...');
    await page.evaluate(() => {
      const tabs = Array.from(document.querySelectorAll('button'));
      const t = tabs.find(x => x.innerText && x.innerText.includes('Schema'));
      if (t) t.click();
    });
    await new Promise(r => setTimeout(r, 1000));
    const ccSchemaPath = path.join(ARTIFACT_DIR, 'ui_architect_schema.png');
    await page.screenshot({ path: ccSchemaPath, fullPage: false });
    console.log('Saved Schema tab screenshot to:', ccSchemaPath);

    // Click on Validators tab
    console.log('7. Clicking on Validators tab...');
    await page.evaluate(() => {
      const tabs = Array.from(document.querySelectorAll('button'));
      const t = tabs.find(x => x.innerText && x.innerText.includes('Validators'));
      if (t) t.click();
    });
    await new Promise(r => setTimeout(r, 1000));
    const ccValidatorsPath = path.join(ARTIFACT_DIR, 'ui_architect_validators.png');
    await page.screenshot({ path: ccValidatorsPath, fullPage: false });
    console.log('Saved Validators screenshot to:', ccValidatorsPath);

    // Click on Judge Review tab
    console.log('8. Clicking on Judge Review tab...');
    await page.evaluate(() => {
      const tabs = Array.from(document.querySelectorAll('button'));
      const t = tabs.find(x => x.innerText && x.innerText.includes('Judge'));
      if (t) t.click();
    });
    await new Promise(r => setTimeout(r, 1000));
    const ccJudgePath = path.join(ARTIFACT_DIR, 'ui_architect_judge.png');
    await page.screenshot({ path: ccJudgePath, fullPage: false });
    console.log('Saved Judge screenshot to:', ccJudgePath);

    console.log('ALL UI SCREENSHOTS CAPTURED SUCCESSFULLY!');
  } catch (err) {
    console.error('Error during capture:', err);
  } finally {
    await browser.close();
  }
}

run();
