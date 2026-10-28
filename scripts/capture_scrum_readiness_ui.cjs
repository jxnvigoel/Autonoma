const puppeteer = require('puppeteer-core');
const path = require('path');

const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const ARTIFACT_DIR = '/Users/janvi/.gemini/antigravity-ide/brain/5db0d861-e4bb-40df-8f09-b5be47785141';

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

    // Dismiss splash screen if present
    await page.mouse.click(500, 400);
    await new Promise(r => setTimeout(r, 1200));

    // Click Get Started
    console.log('2. Clicking Get Started...');
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const startBtn = btns.find(b => b.innerText && b.innerText.includes('Get Started'));
      if (startBtn) startBtn.click();
    });
    await new Promise(r => setTimeout(r, 1500));

    // Click Open Project on any existing project
    console.log('3. Clicking Open Project...');
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const openBtn = btns.find(b => b.innerText && b.innerText.includes('Open Project'));
      if (openBtn) openBtn.click();
    });

    // Wait for Virtual Office floor
    console.log('4. Waiting for Virtual Office floor with Scrum & Tech Lead desks...');
    await new Promise(r => setTimeout(r, 3000));

    // Capture floor screenshot showing new desks
    const floorPath = path.join(ARTIFACT_DIR, 'ui_new_desks_floor.png');
    await page.screenshot({ path: floorPath, fullPage: false });
    console.log('Saved Virtual Office floor with new desks to:', floorPath);

    // Open HR or Recruiter desk to view Gate 2 panel
    console.log('5. Clicking on HR / Recruiter to view Gate 2 panel...');
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const hrBtn = btns.find(b => b.innerText && (b.innerText.includes('HR') || b.innerText.includes('Recruiter')));
      if (hrBtn) hrBtn.click();
    });
    await new Promise(r => setTimeout(r, 2000));

    // Switch to Gate 2 sub-tab if needed
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const gate2Btn = btns.find(b => b.innerText && b.innerText.includes('Gate 2'));
      if (gate2Btn) gate2Btn.click();
    });
    await new Promise(r => setTimeout(r, 1500));

    const gate2Path = path.join(ARTIFACT_DIR, 'ui_gate2_panel.png');
    await page.screenshot({ path: gate2Path, fullPage: false });
    console.log('Saved Gate 2 panel to:', gate2Path);

    // Click on Scrum Master in roster/desk
    console.log('6. Clicking on Scrum Master desk/tab...');
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const scrumBtn = btns.find(b => b.innerText && b.innerText.includes('Scrum Master'));
      if (scrumBtn) scrumBtn.click();
    });
    await new Promise(r => setTimeout(r, 2000));

    // Backlog tab
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const bBtn = btns.find(b => b.innerText && b.innerText.includes('Backlog'));
      if (bBtn) bBtn.click();
    });
    await new Promise(r => setTimeout(r, 1500));
    const backlogPath = path.join(ARTIFACT_DIR, 'ui_backlog_tab.png');
    await page.screenshot({ path: backlogPath, fullPage: false });
    console.log('Saved Backlog tab screenshot to:', backlogPath);

    // Plan tab
    console.log('7. Switching to Plan tab (Gantt & critical path)...');
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const pBtn = btns.find(b => b.innerText && b.innerText.includes('Plan'));
      if (pBtn) pBtn.click();
    });
    await new Promise(r => setTimeout(r, 1500));
    const planPath = path.join(ARTIFACT_DIR, 'ui_plan_tab.png');
    await page.screenshot({ path: planPath, fullPage: false });
    console.log('Saved Plan tab screenshot to:', planPath);

    // Click on Tech Lead desk
    console.log('8. Clicking on Tech Lead desk for Readiness Review...');
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const tlBtn = btns.find(b => b.innerText && b.innerText.includes('Tech Lead'));
      if (tlBtn) tlBtn.click();
    });
    await new Promise(r => setTimeout(r, 2000));

    // Readiness tab
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const rBtn = btns.find(b => b.innerText && b.innerText.includes('Readiness'));
      if (rBtn) rBtn.click();
    });
    await new Promise(r => setTimeout(r, 1500));
    const readinessPath = path.join(ARTIFACT_DIR, 'ui_readiness_tab.png');
    await page.screenshot({ path: readinessPath, fullPage: false });
    console.log('Saved Readiness tab screenshot to:', readinessPath);

    console.log('ALL SCREENSHOTS CAPTURED SUCCESSFULLY!');
  } catch (err) {
    console.error('Error during screenshot capture:', err);
  } finally {
    await browser.close();
  }
}

run();
