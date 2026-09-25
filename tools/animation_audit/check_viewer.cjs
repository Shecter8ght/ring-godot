const { chromium } = require('C:/Users/Schecter_8ght/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Users/Schecter_8ght/AppData/Local/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-win64/chrome-headless-shell.exe', args: ['--use-gl=angle', '--use-angle=swiftshader'] });
  const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.goto('http://127.0.0.1:8765', { waitUntil: 'networkidle' });
  for (const key of ['unarmed/walk_forward', 'pistol/idle', 'rifle/walk_hip_forward']) {
    await page.locator('#state').selectOption(key);
    await page.waitForTimeout(2500);
    console.log(key, 'cards:', await page.locator('.card').count(), 'overlays:', await page.locator('.overlay').allTextContents());
  }
  await page.locator('#pause').click();
  await page.locator('#restart').click();
  await page.locator('.card .maybe').first().click();
  await page.reload({ waitUntil: 'networkidle' });
  await page.locator('#state').selectOption('rifle/walk_hip_forward');
  if (await page.locator('.card .maybe.on').count() !== 1) throw new Error('localStorage decision did not persist');
  await page.locator('.card .maybe.on').click();
  await page.locator('#export').click();
  await page.waitForTimeout(200);
  if (!(await page.locator('#notice').textContent()).includes('Сохранено')) throw new Error('Export failed');
  console.log('ERRORS', errors);
  await page.screenshot({ path: 'tools/animation_audit/viewer_check.png', fullPage: true });
  await browser.close();
  if (errors.length) process.exitCode = 1;
})().catch(error => { console.error(error); process.exitCode = 1; });
