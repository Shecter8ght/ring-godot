const {_electron:electron}=require('playwright'),fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process'),{unzipSync,strFromU8}=require('fflate');
const{sineWav}=require('./ring-fixture.cjs');
const root=path.resolve(__dirname,'..'),qa=path.resolve(root,'../qa-fx'),report={checks:[],errors:[]};let app,page;
function ff(args){const r=spawnSync(path.join(root,'vendor/ffmpeg.exe'),['-hide_banner','-loglevel','error',...args],{windowsHide:true});if(r.status)throw new Error(String(r.stderr));}
async function check(name,action){const detail=await action();report.checks.push({name,status:'pass',detail});console.log('PASS '+name);}
const idle=()=>page.waitForFunction(()=>!document.getElementById('busy-dialog').open);
async function numeric(selector,value){await page.locator(selector).fill(String(value));await page.locator(selector).press('Tab');}
(async()=>{await fs.mkdir(qa,{recursive:true});const userData=await fs.mkdtemp(path.join(qa,'fx-profile-')),project='';
  const env={...process.env,SONORA_USER_DATA:userData};delete env.ELECTRON_RUN_AS_NODE;
  app=await electron.launch({...(process.env.SONORA_TEST_EXECUTABLE?{executablePath:process.env.SONORA_TEST_EXECUTABLE,args:[]}:{args:[root]}),env,timeout:30000});page=await app.firstWindow();page.on('pageerror',e=>report.errors.push(e.message));page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text());});
  await page.locator('#load-demo').waitFor();await page.evaluate(async()=>{window.__qa=await import('./app.mjs');});
  const savePath=path.join(qa,'FX-project.sonora'),mp3=path.join(qa,'кандидат.mp3'),ogg=path.join(qa,'вариант.ogg'),wav=path.join(qa,'source.wav');await fs.writeFile(wav,sineWav(840,.4,.35));ff(['-y','-i',wav,'-c:a','libmp3lame',mp3]);ff(['-y','-i',wav,'-c:a','libvorbis',ogg]);
  await app.evaluate(({dialog},v)=>{globalThis.qa=v;dialog.showOpenDialog=async(_,o)=>({canceled:false,filePaths:o.title==='Папка проекта Ring с project.godot'?[v.fixture]:o.title==='Открыть проект'?[v.save]:[v.mp3,v.ogg]});dialog.showSaveDialog=async()=>({canceled:false,filePath:v.save});dialog.showMessageBox=async()=>({response:1});},{fixture:project,save:savePath,mp3,ogg});
  await check('live tone, reverb and limiter knobs; undo; clock keeps running',async()=>{
    await page.locator('#load-demo').click();await idle();await page.locator('#tab-fx').click();
    await numeric('[data-knob="tone.low"] input',4.5);await page.locator('#reverb-preset').selectOption('hall');await numeric('[data-knob="reverb.wet"] input',.35);
    await page.locator('[data-fx-enable="limiter"]').check();await numeric('[data-knob="limiter.drive"] input',6);await numeric('[data-knob="limiter.ceiling"] input',-1.5);
    await page.locator('#loop-toggle').click();await page.locator('#play').click();await page.waitForFunction(()=>window.__qa.engine.playing&&window.__qa.engine.meter()>0);
    const anchor=await page.evaluate(()=>window.__qa.engine.anchorTime);
    await numeric('[data-knob="reverb.decay"] input',1.4);await numeric('[data-knob="limiter.drive"] input',9);
    await page.waitForFunction(()=>window.__qa.engine.limiter.input.parameters.get('drive').value>8.9);
    assert.equal(await page.evaluate(()=>window.__qa.engine.anchorTime),anchor);
    const knob=page.locator('[data-knob="tone.mid"] .rotary');await knob.focus();await page.keyboard.press('ArrowUp');assert.equal(await page.evaluate(()=>window.__qa.studio.project.tracks[0].fx.tone.mid),.1);
    await page.keyboard.press('Control+z');assert.equal(await page.evaluate(()=>window.__qa.studio.project.tracks[0].fx.tone.mid),0);
    await page.locator('#stop').click();await page.locator('#loop-toggle').click();await page.screenshot({path:path.join(qa,'effects.png')});
  });
  await check('offline DSP: limiter ceiling, neutral delay compensation, reverb tail and glue bypass',async()=>{
    const result=await page.evaluate(async()=>{
      const {engine}=window.__qa,{createProject,createTrack,createClip}=await import('./model.mjs'),{renderAudio,peakOf}=await import('./audio.mjs');
      const ctx=await engine.ensureContext(),buffer=ctx.createBuffer(2,4800,48000);for(let c=0;c<2;c++)for(let i=0;i<buffer.length;i++)buffer.getChannelData(c)[i]=Math.sin(i*2*Math.PI*440/48000)*.5;
      const asset={id:'fx-test',name:'FX',duration:.1,buffer},assets=new Map([[asset.id,asset]]),p=createProject(),t=createTrack();p.masterGain=0;t.eqEnabled=false;t.clips=[createClip(asset)];t.clips[0].fadeIn=0;t.clips[0].fadeOut=0;p.tracks=[t];const range={start:0,end:.1};
      const neutral=await renderAudio(p,assets,[t.id],range);let error=0;for(let i=0;i<buffer.length;i++)error=Math.max(error,Math.abs(neutral.getChannelData(0)[i]-buffer.getChannelData(0)[i]));
      t.fx.reverb={enabled:true,wet:.5,decay:.6,preDelay:18,damping:6500,size:.7};const wet=await renderAudio(p,assets,[t.id],range),cropped=await renderAudio(p,assets,[t.id],range,{includeTail:false});let tailEnergy=0;for(const sample of wet.getChannelData(0).subarray(6000))tailEnergy+=sample*sample;
      p.limiter={enabled:true,drive:24,ceiling:-2,release:90};const limited=await renderAudio(p,assets,[t.id],range),raw=await renderAudio(p,assets,[t.id],range,{raw:true});return{neutralError:error,neutralFrames:neutral.length,wetFrames:wet.length,croppedFrames:cropped.length,tailEnergy,limitedPeak:peakOf(limited),rawPeak:peakOf(raw),rawFrames:raw.length};
    });assert.ok(result.neutralError<1e-7);assert.equal(result.neutralFrames,4800);assert.equal(result.wetFrames,34464);assert.equal(result.croppedFrames,4800);assert.ok(result.tailEnergy>.00001);assert.ok(result.limitedPeak<=10**(-2/20)+1e-6);assert.ok(result.limitedPeak>.7);assert.equal(result.rawFrames,4800);assert.ok(Math.abs(result.rawPeak-.5)<1e-5);return result;
  });
  await check('FX settings survive a self-contained project save and reopen',async()=>{
    await page.locator('#save-project').click();await idle();const archive=unzipSync(new Uint8Array(await fs.readFile(savePath))),saved=JSON.parse(strFromU8(archive['project.json']));assert.equal(saved.tracks[0].fx.reverb.decay,1.4);assert.equal(saved.limiter.drive,9);
    await page.locator('#new-project').click();await page.locator('#open-project').click();await idle();await page.waitForFunction(()=>window.__qa.studio.project.tracks.length===3);assert.equal(await page.evaluate(()=>window.__qa.studio.project.limiter.drive),9);
  });
assert.deepEqual(report.errors,[]);report.status='pass';})().catch(error=>{report.status='fail';report.failure=error.stack;console.error(error);process.exitCode=1;}).finally(async()=>{await fs.writeFile(path.join(qa,process.env.SONORA_TEST_EXECUTABLE?'effects-packaged.json':'effects.json'),JSON.stringify(report,null,2));if(app){await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows().forEach(w=>w.destroy())).catch(()=>{});await app.close().catch(()=>{});}});
