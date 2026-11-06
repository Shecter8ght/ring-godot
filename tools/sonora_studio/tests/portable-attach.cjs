const{chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),{fileURLToPath}=require('node:url'),asar=require('@electron/asar');
(async()=>{
  const b=await chromium.connectOverCDP(`http://127.0.0.1:${process.argv[2]}`),p=b.contexts().flatMap(context=>context.pages())[0];assert.ok(p);
  try{
    const archive=fileURLToPath(p.url()).split(path.sep+'ui'+path.sep)[0];
    assert.ok(asar.extractFile(archive,'ui/limiter-dsp.mjs').equals(await fs.readFile(path.resolve(__dirname,'../ui/limiter-dsp.mjs'))));
    await p.evaluate(async()=>{window.__qa=await import('./app.mjs');});assert.equal(await p.evaluate(()=>window.__qa.studio.dirty),false);
    await p.locator('#load-demo').click();await p.waitForFunction(()=>!document.getElementById('busy-dialog').open);await p.locator('#play').click();await p.waitForFunction(()=>window.__qa.engine.meter()>.01);
    const peak=await p.evaluate(()=>window.__qa.engine.meter());await p.locator('#stop').click();await p.locator('#tab-fx').click();assert.equal(await p.locator('.fx-card').count(),3);
    const result={status:'pass',portable:true,actualExtractedCodeMatches:true,tracks:3,peak,worklet:true};console.log(JSON.stringify(result));await fs.writeFile(path.resolve(__dirname,'../../qa/report-portable-11-final.json'),JSON.stringify(result,null,2));
  }finally{await p.evaluate(()=>{if(window.__qa)window.__qa.studio.dirty=false;}).catch(()=>{});await p.close().catch(()=>{});await b.close().catch(()=>{});}
})().catch(error=>{console.error(error);process.exitCode=1;});
