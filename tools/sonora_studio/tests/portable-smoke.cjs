const { chromium } = require('playwright');
const { spawn } = require('node:child_process');
const net = require('node:net');
const path = require('node:path');
const fs = require('node:fs/promises');
const assert = require('node:assert/strict');

(async () => {
  const root = path.resolve(__dirname, '..'), qa = path.resolve(root, '..', 'qa');
  const label = (process.env.SONORA_SMOKE_LABEL || 'portable').replace(/[^a-z0-9_-]/gi, '') || 'portable';
  const executable = process.argv[2] || path.join(root, 'dist', 'Sonora-Studio-1.5.0.exe');
  await fs.access(executable);
  const server = net.createServer(); await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port; await new Promise(resolve => server.close(resolve));
  const env = { ...process.env, SONORA_USER_DATA: path.join(qa, `${label}-user-data`) }; delete env.ELECTRON_RUN_AS_NODE;
  const child = spawn(executable, [`--remote-debugging-port=${port}`], { env, windowsHide: true, stdio: 'ignore' });
  let browser;
  const started = Date.now();
  try {
    let info;
    while (Date.now() - started < 90000) {
      try { info = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json(); if (info.webSocketDebuggerUrl) break; } catch {}
      await new Promise(resolve => setTimeout(resolve, 250));
    }
    if (!info?.webSocketDebuggerUrl) throw new Error('Portable app did not open its window within 90 seconds.');
    browser = await chromium.connectOverCDP(info.webSocketDebuggerUrl);
    let page;
    const pageDeadline=Date.now()+30000;
    while(!page && Date.now()<pageDeadline){page=browser.contexts().flatMap(context=>context.pages())[0];if(!page)await new Promise(resolve=>setTimeout(resolve,100));}
    assert.ok(page,'Portable app did not create a page');
    await page.locator('#load-demo').waitFor();
    await page.evaluate(async () => { window.__qa = await import('./app.mjs'); });
    await page.locator('#load-demo').click(); await page.locator('.track-row').nth(2).waitFor();
    await page.waitForFunction(() => !document.getElementById('busy-dialog').open);
    await page.locator('#play').click();
    await page.waitForFunction(() => window.__qa.engine.playing && window.__qa.engine.meter() > .01);
    const result = await page.evaluate(() => ({ tracks: window.__qa.studio.project.tracks.length, peak: window.__qa.engine.meter(), bridge: typeof window.sonora.writeExport === 'function' }));
    assert.equal(result.tracks, 3); assert.ok(result.peak > 0); assert.ok(result.bridge);
    await page.locator('#stop').click(); await page.locator('#toasts').evaluate(element => element.replaceChildren());
    await page.locator('#tab-compressor').click();await page.locator('#compressor-preset').selectOption('voice');await page.locator('#sound-tools').click();await page.locator('[data-tools-mode="batch"]').click();await page.locator('#variation-count').fill('1');await page.locator('#variation-count').press('Tab');await page.locator('#tools-generate').click();await page.waitForFunction(()=>!window.__qa.soundTools.working&&window.__qa.soundTools.results.length>0);result.preparedVariants=await page.locator('.prepared-result').count();assert.ok(result.preparedVariants>0);await page.locator('#tools-close').click();
    await page.screenshot({ path: path.join(qa, `${label}-final.png`) });
    await fs.writeFile(path.join(qa, `report-${label}.json`), JSON.stringify({ status: 'pass', executable, startupAndCheckMs: Date.now() - started, ...result }, null, 2));
    console.log(JSON.stringify({ status: 'pass', startupAndCheckMs: Date.now() - started, ...result }));
    await page.evaluate(() => { window.__qa.studio.dirty = false; });
    await page.close();
  } finally {
    if(browser)for(const context of browser.contexts())for(const page of context.pages()){
      await page.evaluate(()=>{if(window.__qa)window.__qa.studio.dirty=false;}).catch(()=>{});
      await page.close().catch(()=>{});
    }
    await browser?.close().catch(() => {});
    if (child.exitCode === null) await Promise.race([new Promise(resolve=>child.once('exit',resolve)),new Promise(resolve=>setTimeout(resolve,3000))]);
    if (child.exitCode === null) child.kill();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
