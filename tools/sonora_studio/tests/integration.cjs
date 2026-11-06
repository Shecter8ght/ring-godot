const { _electron: electron } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { unzipSync, strFromU8 } = require('fflate');

const root = path.resolve(__dirname, '..'), qa = path.resolve(root, '../../_asset_src/sonora_qa/editor');
const ffmpeg = path.join(root, 'vendor', 'ffmpeg.exe');
let app, page;
const report = { date: new Date().toISOString(), checks: [], errors: [] };
async function check(name, action) {
  const detail = await action(); report.checks.push({ name, result: 'pass', detail }); console.log(`PASS ${name}${detail ? `: ${JSON.stringify(detail)}` : ''}`);
}
function sineWav(frequency, amplitude = .1, seconds = 1) {
  const rate = 48000, frames = Math.round(seconds * rate), bytes = Buffer.alloc(44 + frames * 2);
  bytes.write('RIFF'); bytes.writeUInt32LE(bytes.length - 8, 4); bytes.write('WAVEfmt ', 8); bytes.writeUInt32LE(16, 16);
  bytes.writeUInt16LE(1, 20); bytes.writeUInt16LE(1, 22); bytes.writeUInt32LE(rate, 24); bytes.writeUInt32LE(rate * 2, 28); bytes.writeUInt16LE(2, 32); bytes.writeUInt16LE(16, 34); bytes.write('data', 36); bytes.writeUInt32LE(frames * 2, 40);
  for (let i = 0; i < frames; i++) bytes.writeInt16LE(Math.round(Math.sin(2 * Math.PI * frequency * i / rate) * amplitude * 32767), 44 + i * 2);
  return bytes;
}
function ff(args) {
  const result = spawnSync(ffmpeg, ['-hide_banner', '-loglevel', 'error', '-nostdin', ...args], { windowsHide: true, maxBuffer: 256 * 1024 * 1024 });
  if (result.status !== 0) throw new Error(String(result.stderr) || result.error?.message || `FFmpeg ${result.status}`);
  return result.stdout;
}
async function metadata(filename) {
  const bytes = await fs.readFile(filename); let fmt = null, data = 0;
  for (let offset = 12; offset + 8 < bytes.length;) {
    const id = bytes.toString('ascii', offset, offset + 4), size = bytes.readUInt32LE(offset + 4);
    if (id === 'fmt ') fmt = { codec: bytes.readUInt16LE(offset + 8), channels: bytes.readUInt16LE(offset + 10), rate: bytes.readUInt32LE(offset + 12), bits: bytes.readUInt16LE(offset + 22) };
    if (id === 'data') { data = size; break; }
    offset += 8 + size + (size % 2);
  }
  return { ...fmt, seconds: data / (fmt.channels * fmt.bits / 8 * fmt.rate) };
}
function decodedStats(filename) {
  const bytes = ff(['-i', filename, '-f', 'f32le', '-acodec', 'pcm_f32le', '-ar', '48000', '-ac', '2', '-']);
  let energy = 0, peak = 0; const frames = bytes.length / 8;
  for (let i = 0; i < bytes.length; i += 4) { const sample = bytes.readFloatLE(i); energy += sample * sample; peak = Math.max(peak, Math.abs(sample)); }
  const probes = [500, 3100, 9000, 17000, 29000, 43000].filter(index => index < frames).map(index => [index, bytes.readFloatLE(index * 8), bytes.readFloatLE(index * 8 + 4)]);
  return { frames, rms: Math.sqrt(energy / (bytes.length / 4)), peak, probes };
}
const state = () => page.evaluate(async () => { const { studio } = await import('./app.mjs'); return { project: structuredClone(studio.project), cursor: studio.cursor, selection: studio.selection, selected: [...studio.selectedClipIds], dirty: studio.dirty }; });
const idle = () => page.waitForFunction(() => !document.getElementById('busy-dialog').open);
const saveTarget = target => app.evaluate((_, value) => { globalThis.__sonoraQa.save = value; }, target);
async function exportThroughUi({ name, mode = 'mix', format = 'wav', bits = '24', rate = '48000', stems = false }) {
  const output = path.join(qa, name); if (!stems) await saveTarget(output);
  await page.locator('#export').click(); await page.locator(`input[name="mode"][value="${mode}"]`).check();
  await page.locator('#export-format').selectOption(format); await page.locator('#export-rate').selectOption(rate);
  if (format === 'wav') await page.locator('#export-depth').selectOption(bits);
  if (mode !== 'clip') await page.locator('#export-range').selectOption('all');
  await page.locator('#export-form button[type="submit"]').click();
  await page.waitForFunction(() => !document.getElementById('export-dialog').open && !document.getElementById('busy-dialog').open);
  if (!stems) assert.ok((await fs.stat(output)).size > 100);
  return output;
}

(async () => {
  await fs.mkdir(qa, { recursive: true }); await fs.mkdir(path.join(qa, 'stems'), { recursive: true });
  const wave = path.join(qa, 'Низ.wav'), source2 = path.join(qa, 'source2.wav'), source3 = path.join(qa, 'source3.wav');
  const mp3 = path.join(qa, 'Середина.mp3'), ogg = path.join(qa, 'Верх.ogg'), projectPath = path.join(qa, 'Переносимый проект.sonora'), preset = path.join(qa, 'eq.csv');
  await fs.writeFile(wave, sineWav(110)); await fs.writeFile(source2, sineWav(1000, .08)); await fs.writeFile(source3, sineWav(8000, .06));
  ff(['-y', '-i', source2, '-c:a', 'libmp3lame', '-b:a', '320k', mp3]); ff(['-y', '-i', source3, '-c:a', 'libvorbis', '-q:a', '8', ogg]);
  await fs.writeFile(preset, 'frequency;gain;q\n80;4;0,7\n1000;1,5;1\n8500;-6;0,8');
  const env = { ...process.env, SONORA_USER_DATA: path.join(qa, `electron-data-${process.env.SONORA_TEST_EXECUTABLE ? 'packaged' : 'dev'}`) }; delete env.ELECTRON_RUN_AS_NODE;
  const executablePath = process.env.SONORA_TEST_EXECUTABLE || undefined;
  app = await electron.launch({ ...(executablePath ? { executablePath, args: [] } : { args: [root] }), env, timeout: 30000 });
  page = await app.firstWindow(); page.on('pageerror', error => report.errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') report.errors.push(message.text()); });
  await page.waitForLoadState('domcontentloaded'); await page.locator('#load-demo').waitFor();
  await page.evaluate(async () => { window.__qa = await import('./app.mjs'); });
  await app.evaluate(({ dialog }, values) => {
    globalThis.__sonoraQa = values;
    dialog.showOpenDialog = async (_, options) => ({ canceled: false, filePaths: options.title === 'Открыть проект' ? [values.project] : options.title === 'Загрузить настройки эквалайзера' ? [values.preset] : options.properties.includes('openDirectory') ? [values.stems] : values.audio });
    dialog.showSaveDialog = async () => ({ canceled: false, filePath: globalThis.__sonoraQa.save });
    dialog.showMessageBox = async () => ({ response: 1 });
  }, { audio: [wave, mp3, ogg], project: projectPath, preset, stems: path.join(qa, 'stems'), save: projectPath });

  await check('native import: WAV, MP3, OGG; stereo buses; waveform rendering', async () => {
    await page.locator('#import-audio').click(); await page.locator('.track-row').nth(2).waitFor(); await idle();
    const s = await state(); assert.equal(s.project.tracks.length, 3); assert.equal(s.project.assets.length, 3);
    for (const asset of s.project.assets) assert.ok(Math.abs(asset.duration - 1) < .06);
    assert.equal(await page.locator('canvas.clip-waveform').count(), 3); return s.project.assets.map(item => ({ name: item.name, duration: item.duration }));
  });
  await check('UI split, duplicate, undo, trim, cross-track move, clipboard and glue', async () => {
    await page.locator('.audio-clip').first().click();
    await page.evaluate(async () => { const { studio, timeline } = await import('./app.mjs'); studio.cursor = .4; timeline.renderPlayhead(.4); });
    await page.locator('#split').click(); let s = await state(); assert.equal(s.project.tracks[0].clips.length, 2); assert.equal(s.project.tracks[0].clips[1].offset, .4);
    await page.locator('#duplicate').click(); assert.equal((await state()).project.tracks[0].clips.length, 3);
    await page.keyboard.press('Control+z'); assert.equal((await state()).project.tracks[0].clips.length, 2);
    let box = await page.locator('.track-row').first().locator('.audio-clip').first().boundingBox();
    await page.mouse.move(box.x + box.width - 3, box.y + 45); await page.mouse.down(); await page.mouse.move(box.x + box.width - 65, box.y + 45, { steps: 5 }); await page.mouse.up();
    assert.ok((await state()).project.tracks[0].clips[0].duration < .4); await page.keyboard.press('Control+z');
    box = await page.locator('.track-row').first().locator('.audio-clip').nth(1).boundingBox();
    await page.mouse.move(box.x + 25, box.y + 40); await page.mouse.down(); await page.mouse.move(box.x + 80, box.y + 142, { steps: 8 }); await page.mouse.up();
    s = await state(); assert.equal(s.project.tracks[0].clips.length, 1); assert.equal(s.project.tracks[1].clips.length, 2); await page.keyboard.press('Control+z');
    const fragments = page.locator('.track-row').first().locator('.audio-clip');
    await fragments.first().click(); await fragments.nth(1).click({ modifiers: ['Shift'] }); await page.locator('#join').click(); await idle();
    s = await state(); assert.equal(s.project.tracks[0].clips.length, 1); assert.ok(Math.abs(s.project.tracks[0].clips[0].duration - 1) < .001); assert.equal(s.project.assets.length, 4);
    await page.keyboard.press('Control+c');
    await page.evaluate(async () => { const { studio } = await import('./app.mjs'); studio.cursor = 1.2; });
    await page.keyboard.press('Control+v'); assert.equal((await state()).project.tracks[0].clips.length, 2); await page.keyboard.press('Control+z');
    await page.locator('.track-row').first().locator('.audio-clip').first().click();
  });
  await check('playback end follows timeline edits', async () => {
    await page.evaluate(() => {window.__qa.studio.cursor=0;}); await page.locator('#play').click();
    await page.locator('#duplicate').click();
    await page.waitForFunction(() => window.__qa.engine.playing && window.__qa.engine.end >= 1.99);
    await page.locator('#stop').click(); await page.keyboard.press('Control+z');
    await page.locator('.track-row').first().locator('.audio-clip').first().click();
  });
  await check('selection loop and live EQ changes without restarting the audio clock', async () => {
    const zoom = await page.locator('#zoom').inputValue(), ruler = await page.locator('#ruler').boundingBox();
    await page.mouse.move(ruler.x + .1 * zoom, ruler.y + 15); await page.mouse.down(); await page.mouse.move(ruler.x + .45 * zoom, ruler.y + 15, { steps: 6 }); await page.mouse.up();
    let s = await state(); assert.ok(Math.abs(s.selection.start - .1) < .015); assert.ok(Math.abs(s.selection.end - .45) < .015);
    await page.locator('#loop-mode').selectOption('selection'); await page.locator('#loop-toggle').click(); await page.locator('#play').click();
    await page.waitForFunction(() => { const { engine } = window.__qa; return engine.playing && engine.context.currentTime - engine.anchorTime > .55 && engine.meter() > .0001; });
    const before = await page.evaluate(async () => { const { engine } = await import('./app.mjs'); return { anchor: engine.anchorTime, position: engine.position() }; });
    assert.ok(before.position >= .08 && before.position <= .47);
    const gain = page.locator('.eq-band').first().locator('.band-gain-value'); await gain.fill('6'); await gain.press('Tab');
    await page.waitForFunction(() => { const { engine, studio } = window.__qa; return engine.graphs.get(studio.selectedTrackId).filters[0].gain.value > 5.9; });
    const after = await page.evaluate(async () => { const { engine } = await import('./app.mjs'); return { anchor: engine.anchorTime, playing: engine.playing }; });
    assert.equal(after.anchor, before.anchor); assert.ok(after.playing);
    await page.locator('#range-info').click();
    await page.waitForFunction(() => window.__qa.engine.playing && !window.__qa.engine.loopRange && !window.__qa.studio.loopEnabled);
    await page.locator('#loop-mode').selectOption('track'); await page.locator('#loop-toggle').click();
    await page.locator('.track-row').nth(1).locator('.track-header').click({position:{x:100,y:15}});
    await page.waitForFunction(() => window.__qa.engine.onlyTrackId === window.__qa.studio.project.tracks[1].id && !!window.__qa.engine.loopRange);
    await page.locator('#stop').click(); await page.locator('#loop-toggle').click();
    await page.locator('.track-row').first().locator('.audio-clip').first().click(); return before;
  });
  await check('external EQ file with decimal commas and width Q', async () => {
    await page.locator('#load-preset').click(); await page.waitForFunction(() => document.querySelectorAll('.eq-band').length === 3);
    const bands = (await state()).project.tracks[0].bands; assert.equal(bands[0].frequency, 80); assert.equal(bands[0].q, .7); assert.equal(bands[1].gain, 1.5);
  });
  await check('self-contained project survives missing original audio files', async () => {
    await saveTarget(projectPath); await page.locator('#save-project').click(); await idle();
    const entries = unzipSync(new Uint8Array(await fs.readFile(projectPath))), manifest = JSON.parse(strFromU8(entries['project.json']));
    assert.equal(manifest.tracks.length, 3); assert.equal(Object.keys(entries).filter(name => name.startsWith('audio/')).length, 4);
    for (const input of [wave, mp3, ogg]) await fs.rename(input, `${input}.moved`);
    await page.locator('#new-project').click(); await page.waitForFunction(() => document.querySelectorAll('.track-row').length === 0);
    await page.locator('#open-project').click(); await page.locator('.track-row').nth(2).waitFor(); await idle();
    assert.equal((await state()).project.tracks[0].bands.length, 3); assert.equal((await state()).dirty, false);
    for (const input of [wave, mp3, ogg]) await fs.rename(`${input}.moved`, input);
    return { archiveBytes: (await fs.stat(projectPath)).size };
  });
  let expected;
  await check('checked tracks export to WAV; mute affects preview only; exact rendered samples', async () => {
    await page.locator('.track-row').nth(2).locator('.track-export').uncheck();
    await page.locator('.track-row').nth(1).locator('[data-action="mute"]').click();
    expected = await page.evaluate(async () => {
      const { studio, engine } = await import('./app.mjs'), { renderAudio } = await import('./audio.mjs'), { projectEnd } = await import('./model.mjs');
      const result = await renderAudio(studio.project, engine.assets, studio.project.tracks.filter(track => track.export).map(track => track.id), { start: 0, end: projectEnd(studio.project) });
      let energy = 0, peak = 0; for (let c = 0; c < 2; c++) for (const sample of result.getChannelData(c)) { energy += sample * sample; peak = Math.max(peak, Math.abs(sample)); }
      return { rms: Math.sqrt(energy / (result.length * 2)), peak, frames: result.length, probes: [500,3100,9000,17000,29000,43000].filter(i => i < result.length).map(i => [i, result.getChannelData(0)[i], result.getChannelData(1)[i]]) };
    });
    const output = await exportThroughUi({ name: 'mix.wav' }); const info = await metadata(output), actual = decodedStats(output);
    assert.equal(info.channels, 2); assert.equal(info.rate, 48000); assert.equal(info.bits, 24); assert.equal(actual.frames, expected.frames);
    assert.ok(Math.abs(actual.rms - expected.rms) < 0.000001);
    for (let i = 0; i < actual.probes.length; i++) for (let c = 1; c < 3; c++) assert.ok(Math.abs(actual.probes[i][c] - expected.probes[i][c]) < 0.000001);
    return { ...info, peak: actual.peak };
  });
  for (const format of ['mp3', 'ogg']) await check(`actual ${format.toUpperCase()} encoding and decoding`, async () => {
    const output = await exportThroughUi({ name: `mix.${format}`, format }); const actual = decodedStats(output);
    assert.ok(Math.abs(actual.frames - expected.frames) < 4800); assert.ok(Math.abs(actual.rms - expected.rms) / expected.rms < .13); return { bytes: (await fs.stat(output)).size, seconds: actual.frames / 48000 };
  });
  await check('separate checked-track WAV files and individual-clip 96 kHz float export', async () => {
    await exportThroughUi({ name: '', mode: 'stems', bits: '16', stems: true });
    const names = (await fs.readdir(path.join(qa, 'stems'))).filter(name => name.endsWith('.wav')); assert.equal(names.length, 2);
    for (const name of names) { const info = await metadata(path.join(qa, 'stems', name)); assert.equal(info.bits, 16); assert.ok(Math.abs(info.seconds - 1) < .06); }
    await page.locator('.track-row').first().locator('.audio-clip').first().click();
    const output = await exportThroughUi({ name: 'clip-float.wav', mode: 'clip', bits: '32f', rate: '96000' }); const info = await metadata(output);
    assert.equal(info.bits, 32); assert.equal(info.rate, 96000); assert.ok(Math.abs(info.seconds - 1) < .001); return { stems: names, clip: info };
  });
  await check('DSP: bell gain, Q width, overlap summing, cut continuity and peak protection', async () => {
    const result = await page.evaluate(async () => {
      const { engine } = await import('./app.mjs'), { renderAudio, encodeWav, peakOf } = await import('./audio.mjs'), { createProject, createTrack, createClip, splitClip } = await import('./model.mjs');
      const ctx = await engine.ensureContext(), source = ctx.createBuffer(1, 48000, 48000), data = source.getChannelData(0);
      for (let i = 0; i < data.length; i++) data[i] = .1 * (Math.sin(2*Math.PI*80*i/48000) + Math.sin(2*Math.PI*1000*i/48000) + Math.sin(2*Math.PI*8000*i/48000));
      const asset = { id:'dsp-test', name:'dsp.wav', duration:1, buffer:source }, assets = new Map([[asset.id, asset]]), project = createProject(), track = createTrack();
      project.masterGain = 0; track.bands = [{id:'test-band',type:'peaking',frequency:1000,gain:0,q:4,enabled:true}]; const clip = createClip(asset); clip.fadeIn = 0; clip.fadeOut = 0; track.clips = [clip]; project.tracks = [track];
      const render = () => renderAudio(project, assets, [track.id], {start:0,end:1});
      const tone = (buffer, hz) => { const values=buffer.getChannelData(0);let sin=0,cos=0,n=0;for(let i=2400;i<45600;i++){sin+=values[i]*Math.sin(2*Math.PI*hz*i/48000);cos+=values[i]*Math.cos(2*Math.PI*hz*i/48000);n++;}return Math.hypot(sin,cos)*2/n; };
      const flat = await render(); track.bands[0].gain=6; const boosted=await render();
      const gain1000=tone(boosted,1000)/tone(flat,1000),gain80=tone(boosted,80)/tone(flat,80),gain8000=tone(boosted,8000)/tone(flat,8000);
      track.bands[0].q=.2; const wide=await render(); const wide80=tone(wide,80)/tone(flat,80);
      track.eqEnabled=false; track.clips.push({...clip,id:'second-clip'}); const overlap=await render(); const sumRatio=tone(overlap,1000)/tone(flat,1000); track.clips=[clip];
      const original=await render(); splitClip(track,clip.id,.375); const cut=await render(); let cutError=0;for(let i=0;i<48000;i++)cutError=Math.max(cutError,Math.abs(cut.getChannelData(0)[i]-original.getChannelData(0)[i]));
      for(const item of track.clips)item.gain=24; const loud=await render();const protectedBuffer=await ctx.decodeAudioData(encodeWav(loud,true).buffer);
      return {gain1000,gain80,gain8000,wide80,sumRatio,cutError,loudPeak:peakOf(loud),protectedPeak:peakOf(protectedBuffer)};
    });
    assert.ok(Math.abs(result.gain1000 - 10**(6/20)) < .03); assert.ok(Math.abs(result.gain80 - 1) < .03); assert.ok(Math.abs(result.gain8000 - 1) < .03);
    assert.ok(result.wide80 > result.gain80 + .05); assert.ok(Math.abs(result.sumRatio - 2) < .01); assert.ok(result.cutError < .0001); assert.ok(result.loudPeak > 1); assert.ok(Math.abs(result.protectedPeak - .988553) < .00001); return result;
  });
  await check('50-track playback, enforced track limit and compact layout', async () => {
    await page.evaluate(async () => {
      const { studio, engine, timeline, equalizer, composer }=await import('./app.mjs'), {createTrack,createClip,createProject,normalizeWorkbench}=await import('./model.mjs');engine.stop();const asset=engine.assets.values().next().value,project=createProject();project.assets=[{id:asset.id,name:asset.name,duration:asset.duration,channels:asset.channels,sampleRate:asset.sampleRate}];
      project.tracks=Array.from({length:50},(_,i)=>{const t=createTrack(i);t.volume=-36;t.clips=[createClip(asset)];return t;});project.schemaVersion=1;delete project.soundTypes;normalizeWorkbench(project);studio.project=project;studio.activeLayerId=null;studio.cursor=0;studio.selectedTrackId=project.tracks[0].id;studio.selectedClipIds.clear();studio.loopEnabled=false;studio.playOnlyTrackId=null;composer.selectLayer(null);timeline.render();equalizer.render();
    });
    assert.equal(await page.locator('#add-track').isDisabled(), true); assert.equal((await state()).project.tracks.length, 50);
    await page.locator('#play').click(); await page.waitForFunction(() => {const {engine}=window.__qa;return engine.playing&&engine.graphs.size===50&&engine.context.currentTime-engine.anchorTime>.2&&engine.meter()>.0001;});
    const peak=await page.evaluate(async()=>{const {engine}=await import('./app.mjs');return engine.meter();});assert.ok(Number.isFinite(peak)&&peak>0);await page.locator('#stop').click();
    await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setSize(1100,780));
    const geometry=await page.evaluate(()=>{const bottom=document.querySelector('.eq-panel').getBoundingClientRect().bottom;return{bottom,qBottom:document.querySelector('.band-q-wrap').getBoundingClientRect().bottom,captionBottom:document.querySelector('.graph-caption').getBoundingClientRect().bottom};});
    assert.ok(geometry.qBottom<=geometry.bottom);assert.ok(geometry.captionBottom<=geometry.bottom);return {peak,...geometry};
  });
  await check('rendered UI screenshots and no runtime errors', async () => {
    await page.evaluate(async () => {const {studio}=await import('./app.mjs');studio.dirty=false;});await page.locator('#new-project').click();await page.locator('#load-demo').click();await idle();
    await page.locator('#toasts').evaluate(element=>element.replaceChildren());
    await page.screenshot({path:path.join(qa,'compact-final.png')});await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setSize(1500,960));
    await page.screenshot({path:path.join(qa,'studio-final.png')});await page.locator('#export').click();await page.screenshot({path:path.join(qa,'export-final.png')});await page.locator('[data-close-dialog="export-dialog"]').first().click();
    assert.deepEqual(report.errors,[]);
  });
  report.passed=report.checks.length;report.status='pass';
})().catch(async error=>{report.status='fail';report.failure=error.stack;console.error(error);process.exitCode=1;if(page)await page.screenshot({path:path.join(qa,'failure.png')}).catch(()=>{});}).finally(async()=>{
  await fs.writeFile(path.join(qa,process.env.SONORA_TEST_EXECUTABLE?'report-packaged.json':'report.json'),JSON.stringify(report,null,2));
  if(app){await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows().forEach(window=>window.destroy())).catch(()=>{});await app.close().catch(()=>{});}
});
