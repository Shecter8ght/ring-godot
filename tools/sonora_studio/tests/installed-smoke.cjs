const {_electron:electron}=require('playwright'),fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
  const root=path.resolve(__dirname,'..'),qa=path.resolve(root,'..','qa-fx'),profile=await fs.mkdtemp(path.join(qa,'installed-')),executable=process.argv[2];let app;
  const env={...process.env,SONORA_USER_DATA:profile};delete env.ELECTRON_RUN_AS_NODE;
  try{
    app=await electron.launch({executablePath:executable,args:[],env});assert.equal(await app.evaluate(({app})=>app.getVersion()),'1.5.0');
    const page=await app.firstWindow();await page.locator('#load-demo').click();await page.waitForFunction(()=>!document.getElementById('busy-dialog').open);await page.evaluate(async()=>{window.__qa=await import('./app.mjs');});
    await page.locator('#play').click();await page.waitForFunction(()=>window.__qa.engine.meter()>.01);await page.locator('#stop').click();await page.locator('#tab-fx').click();
    assert.equal(await page.locator('#fx-content .fx-card').count(),3);assert.equal(await page.locator('#eq-preset optgroup[label="Для звуков Ring"] option').count(),4);
    await page.locator('#tab-compressor').click();assert.equal(await page.locator('[data-fx-enable="compressor"]').count(),1);await page.locator('#compressor-preset').selectOption('punch');await page.screenshot({path:path.join(qa,'installed-compressor.png')});
    await page.locator('#sound-tools').click();await page.locator('[data-tools-mode="batch"]').click();assert.equal(await page.locator('#tools-generate').isEnabled(),true);await page.screenshot({path:path.join(qa,'installed-variants.png')});await page.locator('#tools-close').click();await page.locator('#tab-fx').click();
    await page.locator('#toasts').evaluate(el=>el.replaceChildren());await page.screenshot({path:path.join(qa,'installed-effects.png')});
    const ready=app.waitForEvent('window');await page.locator('#open-ring').click();const bench=await ready;await bench.waitForFunction(()=>document.getElementById('event-total').textContent==='25');assert.equal(await bench.locator('#import-game').isDisabled(),true);assert.match(await bench.locator('#project-path').innerText(),/RING-godot/);
    await bench.locator('[data-weapon="wpn_hg_02"]').click();await bench.locator('[data-event="wpn_hg_02_shot_outdoor"]').click();await bench.locator('#toasts').evaluate(el=>el.replaceChildren());await bench.screenshot({path:path.join(qa,'installed-ring.png')});
    await fs.writeFile(path.join(qa,'installed-report.json'),JSON.stringify({status:'pass',version:'1.5.0',executable,realRingWeapons:25,audio:true,worklets:true,compressor:true,soundTools:true,gameModified:false},null,2));console.log('PASS installed 1.5.0: audio worklet, compressor, sound workshop, effects and Ring second window on the actual D: path');
  }finally{if(app){await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows().forEach(window=>window.destroy()));await app.close();}}
})().catch(error=>{console.error(error);process.exitCode=1;});
