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

    // Dismiss splash screen
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

    // Click Open Project on BioVault Lab
    console.log('3. Clicking Open Project on BioVault Lab...');
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const openBtn = btns.find(b => b.innerText && b.innerText.includes('Open Project'));
      if (openBtn) openBtn.click();
    });

    // Wait for Virtual Office floor
    console.log('4. Waiting for Virtual Office floor with 3-pod layout...');
    await new Promise(r => setTimeout(r, 2500));

    // Capture floor screenshot
    const floorPath = path.join(ARTIFACT_DIR, 'ui_designer_floor.png');
    await page.screenshot({ path: floorPath, fullPage: false });
    console.log('Saved Virtual Office floor screenshot to:', floorPath);

    // Click on Designer desk / roster
    console.log('5. Clicking on Designer in roster/desk...');
    const clicked = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const desRoster = btns.find(b => b.innerText && b.innerText.includes('UI/UX Designer'));
      if (desRoster) {
        desRoster.click();
        return 'roster_clicked';
      }
      const badges = Array.from(document.querySelectorAll('span'));
      const desBadge = badges.find(s => s.innerText === 'DES');
      if (desBadge) {
        const card = desBadge.closest('.group');
        if (card) {
          card.click();
          return 'card_clicked';
        }
      }
      return 'none';
    });
    console.log('Click result:', clicked);
    await new Promise(r => setTimeout(r, 2000));

    // Capture App Flow tab
    const flowPath = path.join(ARTIFACT_DIR, 'ui_designer_app_flow.png');
    await page.screenshot({ path: flowPath, fullPage: false });
    console.log('Saved App Flow tab screenshot to:', flowPath);

    // Click Design Brief tab
    console.log('6. Clicking on Design Brief tab...');
    await page.evaluate(() => {
      const tabs = Array.from(document.querySelectorAll('button'));
      const t = tabs.find(x => x.innerText && x.innerText.includes('Design Brief'));
      if (t) t.click();
    });
    await new Promise(r => setTimeout(r, 1000));
    const briefPath = path.join(ARTIFACT_DIR, 'ui_designer_design_brief.png');
    await page.screenshot({ path: briefPath, fullPage: false });
    console.log('Saved Design Brief tab screenshot to:', briefPath);

    // Click Validators tab
    console.log('7. Clicking on Validators tab...');
    await page.evaluate(() => {
      const tabs = Array.from(document.querySelectorAll('button'));
      const t = tabs.find(x => x.innerText && x.innerText.includes('Validators'));
      if (t) t.click();
    });
    await new Promise(r => setTimeout(r, 1000));
    const valPath = path.join(ARTIFACT_DIR, 'ui_designer_validators.png');
    await page.screenshot({ path: valPath, fullPage: false });
    console.log('Saved Validators tab screenshot to:', valPath);

    // Click Judge Review tab
    console.log('8. Clicking on Judge Review tab...');
    await page.evaluate(() => {
      const tabs = Array.from(document.querySelectorAll('button'));
      const t = tabs.find(x => x.innerText && x.innerText.includes('Judge Review'));
      if (t) t.click();
    });
    await new Promise(r => setTimeout(r, 1000));
    const judgePath = path.join(ARTIFACT_DIR, 'ui_designer_judge.png');
    await page.screenshot({ path: judgePath, fullPage: false });
    console.log('Saved Judge Review tab screenshot to:', judgePath);

    console.log('All screenshots captured successfully!');
  } catch (err) {
    console.error('Error in capture script:', err);
  } finally {
    await browser.close();
  }
}

run();
