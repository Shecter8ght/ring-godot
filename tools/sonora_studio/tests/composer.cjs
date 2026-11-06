const { _electron: electron } = require('playwright');
const fs = require('node:fs/promises'), path = require('node:path'), assert = require('node:assert/strict');
const { unzipSync, zipSync, strFromU8, strToU8 } = require('fflate');
const { sineWav } = require('./ring-fixture.cjs');
const root = path.resolve(__dirname, '..'), qa = path.resolve(root, '..', 'qa-composer');
const report = { date: new Date().toISOString(), checks: [], errors: [] };
let app, page;
async function check(name, action) { const detail = await action(); report.checks.push({ name, status: 'pass', detail }); console.log('PASS ' + name + (detail ? ': ' + JSON.stringify(detail) : '')); }
const idle = () => page.waitForFunction(() => !document.getElementById('busy-dialog').open && !window.__qa.trackSpeed.working);
const state = () => page.evaluate(() => structuredClone(window.__qa.studio.project));
async function setAudio(files) { await app.evaluate((_, files) => { globalThis.__composer.audio = files; }, files); }
async function mixProbe() {
  return page.evaluate(async () => {
    const { studio, engine } = window.__qa, { enabledTracks, projectEnd } = await import('./model.mjs'), { renderAudio } = await import('./audio.mjs');
    const ids = enabledTracks(studio.project).map(t => t.id), buffer = await renderAudio(studio.project, engine.assets, ids, { start: 0, end: projectEnd(studio.project) });
    const data = buffer.getChannelData(0), start = 4800, length = 9600;
    const levels = [220, 330, 660, 990, 880].map(hz => { let re = 0, im = 0; for (let i = start; i < start + length; i++) { re += data[i] * Math.cos(2 * Math.PI * hz * i / 48000); im += data[i] * Math.sin(2 * Math.PI * hz * i / 48000); } return 2 * Math.hypot(re, im) / length; });
    return { ids, frames: buffer.length, levels };
  });
}
(async () => {
  await fs.mkdir(qa, { recursive: true });
  const profile = await fs.mkdtemp(path.join(qa, 'profile-'));
  const files = ['НЧ удар A', 'НЧ удар B', 'Хлопок A', 'Хлопок B', 'Голос'].map(name => path.join(qa, name + '.wav'));
  for (const [i, [hz, seconds]] of [[220, 2], [330, 2], [660, 1], [990, 1], [880, 1]].entries()) await fs.writeFile(files[i], sineWav(hz, .12, seconds));
  const save = path.join(qa, 'Сборка со слоями.sonora'), exported = path.join(qa, 'Собранный звук.wav');
  const env = { ...process.env, SONORA_USER_DATA: profile }; delete env.ELECTRON_RUN_AS_NODE;
  app = await electron.launch({ ...(process.env.SONORA_TEST_EXECUTABLE ? { executablePath: process.env.SONORA_TEST_EXECUTABLE, args: [] } : { args: [root] }), env, timeout: 30000 });
  page = await app.firstWindow(); page.on('pageerror', error => report.errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') report.errors.push(message.text()); });
  await page.locator('[data-sound-type="gunshots"]').waitFor();
  await page.evaluate(async () => { window.__qa = await import('./app.mjs'); });
  await app.evaluate(({ dialog }, values) => {
    globalThis.__composer = values;
    dialog.showOpenDialog = async (_, options) => ({ canceled: false, filePaths: options.title === 'Открыть проект' ? [values.save] : globalThis.__composer.audio });
    dialog.showSaveDialog = async (_, options) => ({ canceled: false, filePath: options.title === 'Сохранить проект' ? values.save : values.exported });
    dialog.showMessageBox = async () => ({ response: 1 });
  }, { save, exported, audio: files.slice(0, 2) });
  let bodyId, clapId, originalId;
  await check('four sound types and multi-file variants in one layer', async () => {
    assert.equal(await page.locator('[data-sound-type]').count(), 4);
    const project = await state(); bodyId = project.soundTypes[0].layers[0].id; clapId = project.soundTypes[0].layers[1].id;
    await page.locator(`[data-layer="${bodyId}"]`).click(); await page.locator('#add-variants').click(); await idle();
    const next = await state(); assert.equal(next.tracks.length, 2); assert.equal(new Set(next.tracks.map(t => t.layerId)).size, 1);
    assert.equal(await page.locator('[data-variant]').count(), 2); assert.equal(await page.locator('.track-row').count(), 1);
    await page.locator('[data-layer=""]').click(); assert.equal(await page.locator('.track-row').count(), 1);
    return { variants: next.tracks.length, simultaneousTracks: 1 };
  });
  await check('layer tabs edit one layer while preview and export keep the complete combination', async () => {
    await setAudio(files.slice(2, 4)); await page.locator(`[data-layer="${clapId}"]`).click(); await page.locator('#add-variants').click(); await idle();
    await page.evaluate(() => { window.__qa.studio.project.masterGain = 0; });
    const selected = await mixProbe(); assert.ok(selected.levels[1] > .07 && selected.levels[3] > .07); assert.ok(selected.levels[0] < .0001 && selected.levels[2] < .0001);
    await page.locator(`[data-layer="${bodyId}"]`).click(); assert.equal(await page.locator('.track-row').count(), 1);
    const focused = await mixProbe(); assert.deepEqual(focused, selected);
    await page.locator('#loop-toggle').click(); await page.locator('#play').click();
    await page.waitForFunction(() => window.__qa.engine.playing && window.__qa.engine.graphs.size === 2 && window.__qa.engine.meter() > .005);
    await page.locator('#stop').click();
    return { active: selected.ids.length, levels: selected.levels };
  });
  await check('locked variants survive new combinations and choices stay independent across sound types', async () => {
    await page.locator('#layer-locked').check(); const before = await state();
    await page.locator('#new-combination').click(); const after = await state();
    assert.equal(after.soundTypes[0].layers[0].activeVariantId, before.soundTypes[0].layers[0].activeVariantId);
    assert.notEqual(after.soundTypes[0].layers[1].activeVariantId, before.soundTypes[0].layers[1].activeVariantId);
    await page.locator('[data-sound-type="voices"]').click(); const voiceLayer = (await state()).soundTypes[3].layers[0].id;
    await page.locator(`[data-layer="${voiceLayer}"]`).click(); await setAudio([files[4]]); await page.locator('#add-variants').click(); await idle();
    const voice = await mixProbe(); assert.equal(voice.ids.length, 1); assert.ok(voice.levels[4] > .07 && voice.levels[1] < .0001);
    await page.locator('[data-sound-type="gunshots"]').click(); const shot = await mixProbe(); assert.equal(shot.ids.length, 2); assert.ok(shot.levels[4] < .0001);
    return { locked: true, shotLayers: shot.ids.length, voiceLayers: voice.ids.length };
  });
  await check('track speed reaches 4x and 8x with preserved pitch; undo and 1x recover the original', async () => {
    await page.locator(`[data-layer="${bodyId}"]`).click();
    const before = await state(), selected = before.tracks.find(t => t.id === before.soundTypes[0].layers[0].activeVariantId);
    originalId = selected.clips[0].assetId;
    await page.locator('[data-rate="4"]').click(); await idle();
    const result = await page.evaluate(() => {
      const { studio, engine } = window.__qa, clip = studio.project.tracks.find(t => t.id === studio.selectedTrackId).clips[0], buffer = engine.assets.get(clip.assetId).buffer;
      const data = buffer.getChannelData(0); let crossings = 0; const start = Math.round(data.length * .2), end = Math.round(data.length * .8);
      for (let i = start + 1; i < end; i++) if (data[i - 1] <= 0 && data[i] > 0) crossings++;
      return { duration: clip.duration, speed: clip.speed, source: clip.sourceAssetId, frequency: crossings / ((end - start) / 48000) };
    });
    assert.equal(result.duration, .5); assert.equal(result.speed, 4); assert.equal(result.source, originalId); assert.ok(Math.abs(result.frequency - 330) < 5);
    await page.locator('#undo').click(); let track = (await state()).tracks.find(t => t.id === selected.id); assert.equal(track.clips[0].assetId, originalId); assert.equal(track.clips[0].duration, 2);
    await page.locator('#redo').click(); await page.locator('[data-rate="8"]').click(); await idle();
    track = (await state()).tracks.find(t => t.id === selected.id); assert.equal(track.clips[0].duration, .25); assert.equal(track.clips[0].sourceAssetId, originalId);
    await page.locator('[data-rate="1"]').click(); await idle(); track = (await state()).tracks.find(t => t.id === selected.id); assert.equal(track.clips[0].assetId, originalId); assert.equal(track.clips[0].duration, 2);
    await page.locator('[data-rate="4"]').click(); await idle(); return result;
  });
  await check('dragging between visible layers never drops a clip into a hidden variant', async () => {
    await page.locator('[data-layer=""]').click();
    const project = await state(), body = project.soundTypes[0].layers[0].activeVariantId, clap = project.soundTypes[0].layers[1].activeVariantId;
    const source = await page.locator(`.track-row[data-track-id="${body}"] .audio-clip`).boundingBox(), target = await page.locator(`.track-row[data-track-id="${clap}"] .track-lane`).boundingBox();
    await page.mouse.move(source.x + 45, source.y + 35); await page.mouse.down(); await page.mouse.move(source.x + 45, target.y + 40, { steps: 8 }); await page.mouse.up();
    const moved = await state(); assert.equal(moved.tracks.find(t => t.id === body).clips.length, 0); assert.equal(moved.tracks.find(t => t.id === clap).clips.length, 2);
    assert.equal(moved.tracks.find(t => t.name === 'НЧ удар A').clips.length, 1);
    await page.locator('#undo').click(); await page.locator(`[data-layer="${bodyId}"]`).click();
  });
  await check('an existing layer can move to another sound type together with every variant and its effects', async () => {
    await page.locator('#layer-sound-type').selectOption('footsteps');
    let project = await state(); assert.equal(project.activeSoundTypeId, 'footsteps');
    const layer = project.soundTypes[1].layers.find(layer => layer.id === bodyId); assert.ok(layer); assert.equal(project.tracks.filter(t => t.layerId === bodyId && t.soundTypeId === 'footsteps').length, 2);
    assert.equal(await page.locator('[data-variant]').count(), 2);
    await page.locator('#layer-sound-type').selectOption('gunshots');
    project = await state(); assert.equal(project.activeSoundTypeId, 'gunshots'); assert.equal(project.tracks.filter(t => t.layerId === bodyId && t.soundTypeId === 'gunshots').length, 2);
    // The layer is now at the end; find it by id in subsequent checks.
    await page.locator('#undo').click(); await page.locator('#undo').click();
  });
  await check('cut and copy to a new layer retain speed and source, with reversible track edits', async () => {
    await page.evaluate(() => { const { studio } = window.__qa; studio.cursor = .25; });
    await page.locator('#split').click(); const before = await state(), sourceTrack = before.tracks.find(t => t.id === before.soundTypes[0].layers[0].activeVariantId);
    assert.equal(sourceTrack.clips.length, 2); assert.equal(sourceTrack.clips[1].sourceAssetId, originalId);
    await page.locator('[data-rate="1"]').click(); await idle();
    let scaled = (await state()).tracks.find(t => t.id === sourceTrack.id);
    assert.equal(scaled.clips[0].start + scaled.clips[0].duration, scaled.clips[1].start);
    assert.equal(scaled.clips[1].start + scaled.clips[1].duration, 2);
    await page.locator('#undo').click();
    await page.keyboard.press('Control+c'); await page.locator('#add-track').click(); await page.keyboard.press('Control+v');
    const next = await state(), pasted = next.tracks.at(-1).clips[0]; assert.ok(pasted); assert.equal(pasted.speed, 4); assert.equal(pasted.sourceAssetId, originalId);
    await page.locator('#undo').click(); await page.locator('#undo').click(); await page.locator('#undo').click();
    assert.equal((await state()).tracks.length, before.tracks.length); return { sourceSpeed: pasted.speed, cutPreservedSource: true };
  });
  await check('native project round trip preserves variants, all types, speed and original audio bytes', async () => {
    await page.locator('#save-project').click(); await idle();
    const zip = unzipSync(new Uint8Array(await fs.readFile(save))), manifest = JSON.parse(strFromU8(zip['project.json']));
    assert.equal(manifest.schemaVersion, 3); assert.equal(manifest.tracks.length, 5); assert.equal(manifest.soundTypes.length, 4);
    assert.ok(Object.values(zip).some(bytes => Buffer.from(bytes).equals(sineWav(330, .12, 2))));
    await page.locator('#new-project').click(); await page.locator('#open-project').click(); await idle();
    const project = await state(); assert.equal(project.tracks.length, 5);
    const clip = project.tracks.find(t => t.id === project.soundTypes[0].layers[0].activeVariantId).clips[0];
    assert.equal(clip.speed, 4); assert.equal(clip.sourceAssetId, originalId); assert.equal(clip.duration, .5);
    return { tracks: project.tracks.length, assets: project.assets.length, schema: project.schemaVersion };
  });
  await check('export writes only the selected variants of the active type', async () => {
    await page.locator('#export').click(); assert.equal(await page.locator('[data-export-id]').count(), 2);
    await page.locator('input[name="mode"][value="mix"]').check(); await page.locator('#export-depth').selectOption('32f');
    await page.locator('#export-form button[type="submit"]').click(); await idle();
    const bytes = await fs.readFile(exported);
    const result = await page.evaluate(async bytes => {
      const { studio, engine } = window.__qa, { renderAudio } = await import('./audio.mjs'), { enabledTracks, projectEnd } = await import('./model.mjs');
      const expected = await renderAudio(studio.project, engine.assets, enabledTracks(studio.project).filter(t => t.export).map(t => t.id), { start: 0, end: projectEnd(studio.project) });
      const context = await engine.ensureContext(), actual = await context.decodeAudioData(new Uint8Array(bytes).buffer);
      let maxError = 0; for (let c = 0; c < 2; c++) for (let i = 0; i < expected.length; i++) maxError = Math.max(maxError, Math.abs(actual.getChannelData(c)[i] - expected.getChannelData(c)[i]));
      return { expected: expected.length, actual: actual.length, maxError };
    }, [...bytes]);
    assert.equal(result.expected, result.actual); assert.ok(result.maxError < 1e-6); return result;
  });
  await check('wide and compact UI keep the timeline and speed controls usable', async () => {
    await page.locator(`[data-layer="${bodyId}"]`).click();
    await page.locator('#toasts').evaluate(el => el.replaceChildren());
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(1500, 960));
    await page.screenshot({ path: path.join(qa, 'composer-wide.png') });
    await page.locator('[data-layer=""]').click(); await page.screenshot({ path: path.join(qa, 'composition-wide.png') });
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(1100, 780));
    await page.locator(`[data-layer="${bodyId}"]`).click(); await page.screenshot({ path: path.join(qa, 'composer-compact.png') });
    const geometry = await page.evaluate(() => { const bounds = id => { const r = document.getElementById(id).getBoundingClientRect(); return { top: r.top, bottom: r.bottom, width: r.width, height: r.height }; }; return { timeline: bounds('timeline-viewport'), speed: bounds('apply-track-speed'), bodyWidth: document.body.scrollWidth, width: innerWidth }; });
    assert.ok(geometry.timeline.height >= 100); assert.ok(geometry.speed.top >= 0 && geometry.speed.bottom <= 780); assert.ok(geometry.bodyWidth <= geometry.width);
    assert.deepEqual(report.errors, []); return geometry;
  });
  await check('a real schema 1 audio archive opens with its entire old parallel mix intact', async () => {
    const zip = unzipSync(new Uint8Array(await fs.readFile(save))), legacy = JSON.parse(strFromU8(zip['project.json']));
    legacy.schemaVersion = 1; delete legacy.soundTypes; delete legacy.activeSoundTypeId;
    for (const track of legacy.tracks) { delete track.layerId; delete track.soundTypeId; for (const clip of track.clips) { delete clip.sourceAssetId; delete clip.speed; } }
    for (const asset of legacy.assets) delete asset.derived;
    zip['project.json'] = strToU8(JSON.stringify(legacy)); const legacyFile = path.join(qa, 'Старый проект.sonora'); await fs.writeFile(legacyFile, zipSync(zip));
    await page.evaluate(async legacy => {
      const { renderAudio } = await import('./audio.mjs'), { projectEnd } = await import('./model.mjs');
      window.__legacyExpected = await renderAudio(legacy, window.__qa.engine.assets, legacy.tracks.map(t => t.id), { start: 0, end: projectEnd(legacy) });
    }, legacy);
    await app.evaluate((_, filename) => { globalThis.__composer.save = filename; }, legacyFile);
    await page.locator('#open-project').click(); await idle();
    const result = await page.evaluate(async () => {
      const { studio, engine } = window.__qa, { activeTracks, projectEnd } = await import('./model.mjs'), { renderAudio } = await import('./audio.mjs');
      const tracks = activeTracks(studio.project), actual = await renderAudio(studio.project, engine.assets, tracks.map(t => t.id), { start: 0, end: projectEnd(studio.project) }), expected = window.__legacyExpected;
      let maxError = 0; for (let c = 0; c < 2; c++) for (let i = 0; i < expected.length; i++) maxError = Math.max(maxError, Math.abs(actual.getChannelData(c)[i] - expected.getChannelData(c)[i]));
      return { schema: studio.project.schemaVersion, tracks: tracks.length, layers: studio.project.soundTypes[0].layers.length, frames: actual.length, expected: expected.length, maxError };
    });
    assert.equal(result.schema, 3); assert.equal(result.tracks, 5); assert.equal(result.layers, 5); assert.equal(result.frames, result.expected); assert.ok(result.maxError < 1e-6); assert.deepEqual(report.errors, []); return result;
  });
  report.status = 'pass';
})().catch(async error => { report.status = 'fail'; report.failure = error.stack; console.error(error); process.exitCode = 1; if (page) await page.screenshot({ path: path.join(qa, 'failure.png') }).catch(() => {}); })
.finally(async () => { await fs.writeFile(path.join(qa, process.env.SONORA_TEST_EXECUTABLE ? 'report-packaged.json' : 'report.json'), JSON.stringify(report, null, 2)); if (app) { await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows().forEach(window => window.destroy())).catch(() => {}); await app.close().catch(() => {}); } });
