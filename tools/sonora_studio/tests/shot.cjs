const { _electron: electron } = require('playwright');
const fs = require('node:fs/promises'), path = require('node:path'), assert = require('node:assert/strict'), crypto = require('node:crypto');
const { unzipSync, strFromU8 } = require('fflate');
const { sineWav } = require('./ring-fixture.cjs');
const root = path.resolve(__dirname, '..'), qa = path.resolve(root, '../../_asset_src/sonora_qa/qa-shot'), report = { date: new Date().toISOString(), checks: [], errors: [] };
let app, page, bench;
const idle = () => page.waitForFunction(() => !document.getElementById('busy-dialog').open && !window.__qa.shotDesigner.working);
async function check(name, action) { const detail = await action(); report.checks.push({ name, status: 'pass', detail }); console.log('PASS ' + name + (detail ? ': ' + JSON.stringify(detail) : '')); }
const project = () => page.evaluate(() => structuredClone(window.__qa.studio.project));
function shotWav() {
  const frames = 48000, bytes = Buffer.alloc(44 + frames * 4); bytes.write('RIFF'); bytes.writeUInt32LE(bytes.length - 8, 4); bytes.write('WAVEfmt ', 8); bytes.writeUInt32LE(16,16); bytes.writeUInt16LE(1,20); bytes.writeUInt16LE(2,22); bytes.writeUInt32LE(48000,24); bytes.writeUInt32LE(192000,28); bytes.writeUInt16LE(4,32); bytes.writeUInt16LE(16,34); bytes.write('data',36); bytes.writeUInt32LE(frames*4,40);
  let seed = 145;
  for (let i = 3360; i < frames; i++) { const t = (i-3360)/48000; seed=(Math.imul(seed,1664525)+1013904223)|0; const sample=.4*Math.sin(2*Math.PI*120*t)*Math.exp(-t*26)+.22*((seed>>>0)/2147483648-1)*Math.exp(-t*14)+.15*Math.sin(2*Math.PI*6000*t)*Math.exp(-t*90); bytes.writeInt16LE(Math.round(sample*32767),44+i*4); bytes.writeInt16LE(Math.round(sample*.6*32767),46+i*4); }
  return bytes;
}
(async () => {
  await fs.mkdir(qa,{recursive:true}); const profile=await fs.mkdtemp(path.join(qa,'profile-')),folder=await fs.mkdtemp(path.join(qa,'export-')),wav=path.join(qa,'Стандартный выстрел.wav'),bolt=path.join(qa,'Длинный затвор.wav'),save=path.join(qa,'Конструктор.sonora');
  await fs.writeFile(wav,shotWav()); const mechanism=sineWav(500,.2,.8); for(let i=0;i<5760;i++)mechanism.writeInt16LE(0,44+i*2); await fs.writeFile(bolt,mechanism);
  const env={...process.env,SONORA_USER_DATA:profile}; delete env.ELECTRON_RUN_AS_NODE;
  app=await electron.launch({...(process.env.SONORA_TEST_EXECUTABLE?{executablePath:process.env.SONORA_TEST_EXECUTABLE,args:[]}:{args:[root]}),env,timeout:30000}); page=await app.firstWindow();
  page.on('pageerror',error=>report.errors.push(error.message)); page.on('console',message=>{if(message.type()==='error')report.errors.push(message.text());});
  await page.locator('#open-shot-designer').waitFor(); await page.evaluate(async()=>{window.__qa=await import('./app.mjs');});
  await app.evaluate(({dialog},values)=>{globalThis.__shot=values;dialog.showOpenDialog=async(_,o)=>({canceled:false,filePaths:o.title==='Открыть проект'?[values.save]:o.properties.includes('openDirectory')?[values.folder]:[globalThis.__shot.audio]});dialog.showSaveDialog=async()=>({canceled:false,filePath:values.save});dialog.showMessageBox=async()=>({response:1});},{save,folder,audio:wav});
  let sourceTrackId;
  await check('designer opens with four environments and the original remains editable',async()=>{
    const layer=(await project()).soundTypes[0].layers[0];await page.locator(`[data-layer="${layer.id}"]`).click();await page.locator('#add-variants').click();await idle();sourceTrackId=(await project()).tracks[0].id;
    await page.evaluate(()=>{window.__qa.studio.project.masterGain=0;});await page.locator('#open-shot-designer').click();assert.equal(await page.locator('[data-space-preset]').count(),4);assert.equal(await page.locator('#shot-suppressed').isChecked(),false);
    await page.locator('[data-space-preset="small"]').click();await page.locator('#shot-preview-b').click();await idle();assert.equal(await page.evaluate(()=>!!window.__qa.shotDesigner.previewNode),true);await page.locator('#shot-stop').click();
  });
  await check('DSP keeps the direct attack, separates room/hall/outdoor tails and softens highs without losing bass',async()=>{
    const result=await page.evaluate(async()=>{
      const {engine}=window.__qa,{createProject,createTrack,createClip}=await import('./model.mjs'),{renderAudio}=await import('./audio.mjs'),context=await engine.ensureContext();
      const impulse=context.createBuffer(2,4800,48000);impulse.getChannelData(0)[0]=.2;impulse.getChannelData(1)[0]=.12;const asset=await engine.addBuffer('test_impulse.wav',impulse),p=createProject(),t=createTrack();p.masterGain=0;t.clips=[{...createClip(asset),fadeIn:0,fadeOut:0}];p.tracks=[t];const design=p.soundTypes[0].shotDesign;Object.assign(design,{enabled:true});
      const outputs=[];for(const environment of ['dry','small','large','outdoor']){design.environment=environment;const buffer=await renderAudio(p,engine.assets,[t.id],{start:0,end:.1});let firstError=0,tailEnergy=0;const data=buffer.getChannelData(0);for(let i=0;i<300;i++)firstError=Math.max(firstError,Math.abs(data[i]-impulse.getChannelData(0)[i]));for(let i=4800;i<data.length;i++)tailEnergy+=data[i]**2;outputs.push({environment,frames:buffer.length,firstError,tailEnergy});}
      const tone=context.createBuffer(2,24000,48000);for(let c=0;c<2;c++)for(let i=0;i<tone.length;i++)tone.getChannelData(c)[i]=(.05*Math.sin(i*2*Math.PI*120/48000)+.05*Math.sin(i*2*Math.PI*6000/48000))*(c===0?1:.6);
      const toneAsset=await engine.addBuffer('test_tone.wav',tone);t.clips=[{...createClip(toneAsset),fadeIn:0,fadeOut:0}];design.environment='dry';const levels=[];
      for(const suppressed of [false,true]){design.suppressed=suppressed;const buffer=await renderAudio(p,engine.assets,[t.id],{start:0,end:.5});const data=buffer.getChannelData(0);levels.push([120,6000].map(hz=>{let re=0,im=0;for(let i=4800;i<19200;i++){re+=data[i]*Math.cos(i*2*Math.PI*hz/48000);im+=data[i]*Math.sin(i*2*Math.PI*hz/48000);}return 2*Math.hypot(re,im)/14400;}));}
      return {outputs,levels};
    });
    assert.ok(result.outputs.every(item=>item.firstError<1e-7));assert.ok(result.outputs[2].frames>result.outputs[1].frames*2);assert.ok(result.outputs[1].tailEnergy>0&&result.outputs[2].tailEnergy>0&&result.outputs[3].tailEnergy>0);assert.ok(result.outputs[3].frames<result.outputs[1].frames);
    assert.ok(result.levels[1][1]<result.levels[0][1]*.5);assert.ok(result.levels[1][0]>result.levels[0][0]*.7);return result;
  });
  await check('preset changes preserve per-layer EQ/FX and update a running audio graph without restarting',async()=>{
    await page.locator('#shot-close').click();await page.locator('#loop-toggle').click();await page.locator('#play').click();await page.waitForFunction(()=>window.__qa.engine.playing&&window.__qa.engine.meter()>.001);
    const before=await page.evaluate(()=>({anchor:window.__qa.engine.anchorTime,tracks:JSON.stringify(window.__qa.studio.project.tracks)}));
    await page.locator('#open-shot-designer').click();await page.locator('[data-space-preset="large"]').click();await page.locator('#shot-suppressed').check();
    const after=await page.evaluate(()=>({anchor:window.__qa.engine.anchorTime,tracks:JSON.stringify(window.__qa.studio.project.tracks)}));assert.deepEqual(after,before);
    await page.locator('#shot-preview-a').click();await idle();await page.locator('#shot-stop').click();await page.locator('#shot-close').click();await page.locator('#stop').click();
  });
  await check('shared processing persists in a schema 3 self-contained project',async()=>{
    await page.locator('#save-project').click();await idle();const zip=unzipSync(new Uint8Array(await fs.readFile(save))),p=JSON.parse(strFromU8(zip['project.json']));assert.equal(p.schemaVersion,3);assert.equal(p.soundTypes[0].shotDesign.environment,'large');assert.equal(p.soundTypes[0].shotDesign.suppressed,true);
    await page.locator('#new-project').click();await page.locator('#open-project').click();await idle();const restored=await project();assert.deepEqual(restored.soundTypes[0].shotDesign,p.soundTypes[0].shotDesign);
  });
  await check('six named WAV variants have distinct audio and leave the editable recipe unchanged',async()=>{
    await page.locator('#open-shot-designer').click();const before=JSON.stringify(await project());await page.locator('#shot-export-six').click();await idle();const files=await fs.readdir(folder);assert.equal(files.length,6);const hashes=[];for(const file of files){const bytes=await fs.readFile(path.join(folder,file));hashes.push(crypto.createHash('sha256').update(bytes).digest('hex'));}assert.equal(new Set(hashes).size,6);assert.equal(JSON.stringify(await project()),before);return files;
  });
  await check('the sound workshop applies shared space and suppressor processing exactly once',async()=>{
    await page.locator('#shot-close').click();await page.locator('#sound-tools').click();await page.locator('#tools-source').selectOption('mix');
    const result=await page.evaluate(async()=>{const{studio,engine,soundTools}=window.__qa,{enabledTracks,projectEnd}=await import('./model.mjs'),{renderAudio}=await import('./audio.mjs'),source=(await soundTools.sources())[0],actual=await soundTools.audible(source.buffer,source),expected=await renderAudio(studio.project,engine.assets,enabledTracks(studio.project).filter(t=>t.export).map(t=>t.id),{start:0,end:projectEnd(studio.project)});let error=0;for(let c=0;c<2;c++)for(let i=0;i<expected.length;i++)error=Math.max(error,Math.abs(actual.getChannelData(c)[i]-expected.getChannelData(c)[i]));return{actual:actual.length,expected:expected.length,maxError:error};});
    assert.equal(result.actual,result.expected);assert.ok(result.maxError<1e-5);await page.locator('#tools-close').click();await page.locator('#open-shot-designer').click();return result;
  });
  await check('one recorded shot becomes complementary editable layers without a second copy of the full shot',async()=>{
    await page.locator('[data-shot-tab="layers"]').click();await page.locator('#shot-source').selectOption(sourceTrackId);
    await page.evaluate(async()=>{const{studio,engine}=window.__qa,{renderAudio}=await import('./audio.mjs');window.__shotOriginal=await renderAudio(studio.project,engine.assets,[studio.project.tracks[0].id],{start:0,end:1});window.__shotRaw=await renderAudio(studio.project,engine.assets,[studio.project.tracks[0].id],{start:0,end:1},{includeDesign:false,includeMaster:false});});
    await page.locator('#shot-analyze').click();await idle();assert.equal(await page.locator('.shot-part-tags span').count(),5);
    await page.evaluate(async()=>{const{studio,engine}=window.__qa;studio.loopEnabled=true;studio.loopMode='selection';studio.selection={start:0,end:.5};await engine.play({start:0,loopRange:studio.selection});});
    await page.locator('#shot-create-layers').click();await idle();assert.equal(await page.evaluate(()=>window.__qa.studio.loopMode),'project');
    const result=await page.evaluate(async()=>{const{studio,engine}=window.__qa,{enabledTracks,projectEnd}=await import('./model.mjs'),{renderAudio}=await import('./audio.mjs'),tracks=enabledTracks(studio.project),actual=await renderAudio(studio.project,engine.assets,tracks.map(t=>t.id),{start:0,end:projectEnd(studio.project)}),expected=window.__shotOriginal;let error=0;for(let c=0;c<2;c++)for(let i=0;i<expected.length;i++)error=Math.max(error,Math.abs(expected.getChannelData(c)[i]-actual.getChannelData(c)[i]));const raw=await renderAudio(studio.project,engine.assets,tracks.map(t=>t.id),{start:0,end:1},{includeDesign:false,includeMaster:false});let rawError=0;for(let c=0;c<2;c++)for(let i=0;i<raw.length;i++)rawError=Math.max(rawError,Math.abs(raw.getChannelData(c)[i]-window.__shotRaw.getChannelData(c)[i]));return{rawError,tracks:tracks.length,total:studio.project.tracks.length,backup:studio.project.soundTypes[0].layers.find(l=>l.role==='reference').enabled,maxError:error,frames:actual.length,expected:expected.length};});
    assert.equal(result.tracks,5);assert.equal(result.total,6);assert.equal(result.backup,false);assert.equal(result.frames,result.expected);assert.ok(result.rawError<1e-7,JSON.stringify(result));assert.ok(result.maxError<1e-5,JSON.stringify(result));return result;
  });
  await check('automatic layer creation is one undoable edit and redo restores every source',async()=>{
    await page.locator('#shot-close').click();await page.locator('#undo').click();assert.equal((await project()).tracks.length,1);await page.locator('#redo').click();assert.equal((await project()).tracks.length,6);
  });
  await check('smart timing accelerates a loaded bolt while keeping pitch and derived bands in phase',async()=>{
    const p=await project(),layer=p.soundTypes[0].layers.find(l=>l.role==='boltBack');await app.evaluate((_,file)=>{globalThis.__shot.audio=file;},bolt);await page.locator(`[data-layer="${layer.id}"]`).click();await page.locator('#add-variants').click();await idle();
    await page.locator('#open-shot-designer').click();await page.locator('[data-shot-tab="layers"]').click();await page.locator('#shot-plan').click();await idle();assert.ok(await page.locator('#shot-plan-result tbody tr').count()>=5);await page.locator('#shot-apply-plan').click();await idle();
    const result=await page.evaluate(async()=>{const{studio,engine}=window.__qa,{analyzeShot}=await import('./shot-analysis.mjs'),p=studio.project,l=p.soundTypes[0].layers.find(l=>l.role==='boltBack'),track=p.tracks.find(t=>t.id===l.activeVariantId),clip=track.clips[0],data=engine.assets.get(clip.assetId).buffer.getChannelData(0);let crossings=0;for(let i=1800;i<Math.min(data.length-200,4200);i++)if(data[i-1]<=0&&data[i]>0)crossings++;const group=p.tracks.filter(t=>t.decompositionGroup),onset=analyzeShot([data],48000).onset,offset=clip.start+onset-group[0].clips[0].start-group[0].decompositionOnset;return{offset,speed:clip.speed,duration:clip.duration,frequency:crossings/((Math.min(data.length-200,4200)-1800)/48000),groupStarts:group.map(t=>t.clips[0].start),groupGains:group.map(t=>t.volume),sourceRetained:p.assets.some(a=>a.id===clip.sourceAssetId)};});
    assert.equal(result.speed,8);assert.ok(Math.abs(result.offset-.018)<.002,JSON.stringify(result));assert.ok(Math.abs(result.duration-.1)<.001);assert.ok(Math.abs(result.frequency-500)<30);assert.equal(new Set(result.groupStarts).size,1);assert.ok(result.groupGains.every(gain=>gain===0));assert.equal(result.sourceRetained,true);return result;
  });
  await check('all six variants can be staged in Ring without changing the real game',async()=>{
    await page.locator('[data-shot-tab="space"]').click();const registry='E:/Games/RING-godot/data/audio_events.json',before=await fs.readFile(registry),ready=app.waitForEvent('window');await page.locator('#shot-ring-six').click();bench=await ready;await idle();await bench.locator('[data-candidate]').first().waitFor();assert.equal(await bench.locator('[data-candidate]').count(),6);assert.equal(Buffer.compare(before,await fs.readFile(registry)),0);await bench.close();
  });
  await check('wide and compact designer screens render with no runtime errors',async()=>{
    await page.locator('#toasts').evaluate(el=>el.replaceChildren());await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setSize(1500,960));await page.screenshot({path:path.join(qa,'shot-presets.png')});await page.locator('[data-shot-tab="layers"]').click();await page.locator('#shot-plan').click();await idle();await page.screenshot({path:path.join(qa,'shot-layers.png')});
    await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setSize(1100,780));await page.locator('[data-shot-tab="space"]').click();await page.screenshot({path:path.join(qa,'shot-compact.png')});const geometry=await page.evaluate(()=>{const box=document.getElementById('shot-designer').getBoundingClientRect();return{left:box.left,right:box.right,top:box.top,bottom:box.bottom,width:innerWidth,height:innerHeight};});assert.ok(geometry.left>=0&&geometry.right<=geometry.width&&geometry.top>=0&&geometry.bottom<=geometry.height);assert.deepEqual(report.errors,[]);return geometry;
  });
  report.status='pass';
})().catch(async error=>{report.status='fail';report.failure=error.stack;console.error(error);process.exitCode=1;if(page)await page.screenshot({path:path.join(qa,'failure.png')}).catch(()=>{});})
.finally(async()=>{await fs.writeFile(path.join(qa,process.env.SONORA_TEST_EXECUTABLE?'report-packaged.json':'report.json'),JSON.stringify(report,null,2));if(app){await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows().forEach(w=>w.destroy())).catch(()=>{});await app.close().catch(()=>{});}});
