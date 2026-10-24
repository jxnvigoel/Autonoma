const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const ARTIFACT_DIR = '/Users/janvi/.gemini/antigravity-ide/brain/4c218aae-0ae0-4207-a1f1-bae597e9a03f';

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

    console.log('1. Loading app at http://localhost:5173 ...');
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle0' });

    // Dismiss splash screen by clicking
    await page.mouse.click(500, 400);
    await new Promise(r => setTimeout(r, 1200));

    // Click "Get Started"
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

    // Wait for Virtual Office floor
    console.log('4. Waiting for Virtual Office floor...');
    await new Promise(r => setTimeout(r, 2500));

    // Capture specialist desk badge screenshot
    console.log('5. Capturing specialist desk badge on virtual office floor...');
    const deskBadgePath = path.join(ARTIFACT_DIR, 'specialist_desk_badge.png');
    await page.screenshot({ path: deskBadgePath, fullPage: false });
    console.log('Saved specialist desk badge to:', deskBadgePath);

    // Click on "Skills" button in header
    console.log('6. Opening Specialist Skill Library Modal...');
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const skillsBtn = btns.find(b =>
        (b.getAttribute('title') && b.getAttribute('title').includes('Specialist Skill Library')) ||
        (b.innerText && b.innerText.includes('Skills'))
      );
      if (skillsBtn) skillsBtn.click();
    });
    await new Promise(r => setTimeout(r, 1500));

    // Capture Skill Library screenshot
    console.log('7. Capturing Skill Library Modal...');
    const skillLibPath = path.join(ARTIFACT_DIR, 'skill_library.png');
    await page.screenshot({ path: skillLibPath, fullPage: false });
    console.log('Saved skill library screenshot to:', skillLibPath);

    // Click "Detect Needs (0 Tokens)" button in the modal header
    console.log('8. Clicking Detect Needs (0 Tokens)...');
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const detectBtn = btns.find(b => b.innerText && b.innerText.includes('Detect Needs'));
      if (detectBtn) detectBtn.click();
    });
    await new Promise(r => setTimeout(r, 2000));

    // Capture Signal Detector screenshot
    console.log('9. Capturing Signal Detector results in modal...');
    const detectorPath = path.join(ARTIFACT_DIR, 'signal_detector.png');
    await page.screenshot({ path: detectorPath, fullPage: false });
    console.log('Saved signal detector screenshot to:', detectorPath);

    console.log('All screenshots captured successfully!');
  } catch (err) {
    console.error('Error during screenshot capture:', err);
    throw err;
  } finally {
    await browser.close();
  }
}

run();
