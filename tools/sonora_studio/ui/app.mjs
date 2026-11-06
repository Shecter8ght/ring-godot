import { MAX_TRACKS, MAX_LAYERS, MAX_VARIANTS, activeTracks, enabledTracks, visibleTracks, currentSoundType, addLayer, assignVariant, normalizeWorkbench, variantsOf, MAX_BANDS, uid, clamp, cleanName, createProject, createTrack, createClip, defaultBands, projectEnd, trackEnd, trackStart, splitClip, selectionBounds, parsePreset, serializePreset, validateProject, History, gainToDb } from './model.mjs';
import { AudioEngine, createDemo, renderAudio, encodeWav } from './audio.mjs';
import { Timeline, escapeHtml, formatTime } from './timeline.mjs';
import { Equalizer } from './equalizer.mjs';
import { FxControls } from './fx-controls.mjs';
import { taskPresets, recipesHtml } from './task-presets.mjs';
import { SoundTools } from './sound-tools.mjs';
import { Composer } from './composer.mjs';
import { TrackSpeed } from './track-speed.mjs';
import { ShotDesigner } from './shot-designer.mjs';
import { icon, hydrateIcons } from './icons.mjs';

const $ = id => document.getElementById(id);
hydrateIcons();
$('eq-preset').insertAdjacentHTML('beforeend',`<optgroup label="Для звуков Ring">${Object.entries(taskPresets).map(([id,preset])=>`<option value="${id}">${preset.name}</option>`).join('')}</optgroup>`);
document.querySelector('.help-content>div').insertAdjacentHTML('beforeend',recipesHtml);
export const studio = {
  project: createProject(), selectedTrackId: null, selectedClipIds: new Set(), cursor: 0, selection: null,
  zoom: 100, snap: true, tool: 'select', loopEnabled: false, loopMode: 'project', playOnlyTrackId: null,
  dirty: false, revision: 0, history: new History(), clipboard: [], activeLayerId: null
};
let savedSnapshot = JSON.stringify(studio.project), editBefore = null, previewSource = null, busy = false;
export const engine = new AudioEngine(() => studio.project, () => {
  studio.cursor = engine.lastPosition; updateTransport(); timeline.renderPlayhead(studio.cursor);
});

export function toast(message, error = false, action = null) {
  const element = document.createElement('div'); element.className = `toast ${error ? 'error' : ''}`;
  element.innerHTML = `${icon(error ? 'info' : 'check')}<span>${escapeHtml(message)}</span>`;
  if (action) { const button = document.createElement('button'); button.textContent = action.label; button.onclick = action.run; element.append(button); }
  while ($('toasts').children.length >= 3) $('toasts').firstElementChild.remove();
  const dismiss = document.createElement('button'); dismiss.textContent = '×'; dismiss.setAttribute('aria-label', 'Закрыть уведомление'); dismiss.onclick = () => element.remove(); element.append(dismiss);
  $('toasts').append(element); setTimeout(() => element.remove(), error ? 10000 : 5500);
}
function safely(action) { return (...args) => Promise.resolve().then(() => action(...args)).catch(error => { console.error(error); toast(error.message || 'Не удалось выполнить действие.', true); }); }
function setBusy(title, detail = '', progress = null) {
  busy = true; $('busy-title').textContent = title; $('busy-detail').textContent = detail;
  if (progress === null) $('busy-progress').removeAttribute('value'); else { $('busy-progress').max = 1; $('busy-progress').value = progress; }
  if (!$('busy-dialog').open) $('busy-dialog').showModal();
}
function clearBusy() { busy = false; $('busy-dialog').close(); }
$('busy-dialog').addEventListener('cancel', event => event.preventDefault());
function selectedTrack() { return studio.project.tracks.find(track => track.id === studio.selectedTrackId) || null; }
export function selectedClips() {
  return visibleTracks(studio.project, studio.activeLayerId).flatMap((track, trackIndex) => track.clips.filter(clip => studio.selectedClipIds.has(clip.id)).map(clip => ({ track, trackIndex, clip })));
}
function normalizeSelection() {
  const tracks = visibleTracks(studio.project, studio.activeLayerId);
  const clips = new Set(tracks.flatMap(track => track.clips.map(clip => clip.id)));
  studio.selectedClipIds = new Set([...studio.selectedClipIds].filter(id => clips.has(id)));
  if (!tracks.some(track => track.id === studio.selectedTrackId)) studio.selectedTrackId = tracks[0]?.id || null;
}
function markChanged() { studio.revision++; studio.dirty = JSON.stringify(studio.project) !== savedSnapshot; updateHeader(); }
function beginEdit() { if (!editBefore) editBefore = structuredClone(studio.project); }
function endEdit(audio = 'sync', render = true) {
  normalizeWorkbench(studio.project);
  if (studio.activeLayerId && selectedTrack() && activeTracks(studio.project).includes(selectedTrack()) && selectedTrack().layerId !== studio.activeLayerId) studio.activeLayerId = null;
  if (editBefore && JSON.stringify(editBefore) !== JSON.stringify(studio.project)) { studio.history.push(editBefore); markChanged(); }
  editBefore = null; normalizeSelection();
  if (audio === 'restart') refreshPlayback(); else if (audio === 'sync') engine.sync();
  if (render) renderAll(); else updateHeader();
}
function commit(action, audio = 'sync') {
  endPendingEdit(); beginEdit();
  try { action(); endEdit(audio); }
  catch (error) { if (editBefore) studio.project = editBefore; editBefore = null; normalizeSelection(); renderAll(); throw error; }
}
function endPendingEdit() { if (editBefore) endEdit('sync', false); }
function liveChange() { studio.dirty = true; updateHeader(); }

export const timeline = new Timeline(studio, engine, {
  beginEdit, endEdit, seek, selectionChanged, selectTrack, selectClip, zoom: setZoom,
  trackAction: (id, action, value) => safely(trackAction)(id, action, value),
  trackParam: (id, parameter, value) => {
    const track = studio.project.tracks.find(item => item.id === id);
    if (parameter === 'volume') track.volume = clamp(value, -60, 12); else track.pan = clamp(value / 100, -1, 1);
    liveChange(); engine.sync();
  },
  rename: (id, clipId, name) => commit(() => { const track = studio.project.tracks.find(item => item.id === id); (clipId ? track.clips.find(clip => clip.id === clipId) : track).name = name; }, 'none'),
  drop: safely(async ({ assetId, files, trackId, time }) => {
    if (assetId) addAssetToTrack(assetId, trackId, time);
    else if (files.length) await importFiles(await filesToAudio(files), { trackId, time });
  })
});
export const equalizer = new Equalizer(studio, engine, { beginEdit, endEdit, liveChange, toast });
export const effects = new FxControls(studio, engine, { beginEdit, endEdit, liveChange });
export const soundTools = new SoundTools(studio,engine,{endPendingEdit,selectedClips,commit,toast,stopPlayback:stop,afterAdd:()=>timeline.fit()});
export const composer = new Composer(studio, { commit, endPendingEdit, render: renderAll, stop, run: action => safely(action)(), openDesigner: () => shotDesigner.open(), importVariants: async layerId => importFiles(await window.sonora.openAudio(), { layerId, time: 0 }) });
export const trackSpeed = new TrackSpeed(studio, engine, { commit, endPendingEdit, setBusy, clearBusy, toast, run: action => safely(action)(), resume: startPlayback, updateTransport });
export const shotDesigner = new ShotDesigner(studio, engine, { commit, beginEdit, endEdit, liveChange, endPendingEdit, setBusy, clearBusy, toast, updateTransport, run: action => safely(action)() });

function updateHeader() {
  $('undo').disabled = !studio.history.past.length; $('redo').disabled = !studio.history.future.length;
  $('save-status').textContent = studio.dirty ? '● Изменения' : (studio.project.tracks.length || studio.project.assets.length ? 'Сохранено' : 'Новая сессия');
  $('save-status').classList.toggle('dirty', studio.dirty);
  if (document.activeElement !== $('project-name')) $('project-name').value = studio.project.name;
  const count = activeTracks(studio.project).length;
  $('track-count').textContent = `${count} слоёв`; $('asset-count').textContent = studio.project.assets.filter(asset => !asset.derived).length;
  $('session-info').textContent = `48 000 Гц · Стерео · ${currentSoundType(studio.project).name} · ${count} слоёв · ${studio.project.tracks.length} вариантов`;
  $('add-track').disabled = studio.project.tracks.length >= MAX_TRACKS || currentSoundType(studio.project).layers.length >= MAX_LAYERS;
  $('sound-tools').disabled = !projectEnd(studio.project);
  const clips = selectedClips(); $('join').disabled = clips.length < 2; $('delete').disabled = !clips.length; $('duplicate').disabled = !clips.length;
  $('split').disabled = !visibleTracks(studio.project, studio.activeLayerId).some(track => track.clips.length);
  $('tool-select').classList.toggle('active', studio.tool === 'select'); $('tool-range').classList.toggle('active', studio.tool === 'range');
  $('snap-toggle').classList.toggle('active', studio.snap); $('snap-toggle').setAttribute('aria-pressed', String(studio.snap));
  window.sonora?.setTitle(`${studio.dirty ? '● ' : ''}${studio.project.name}`);
}
function updateTransport() {
  $('play').innerHTML = icon(engine.playing ? 'pause' : 'play'); $('play').classList.toggle('is-playing', engine.playing);
  $('play').setAttribute('aria-label', engine.playing ? 'Пауза' : 'Воспроизвести');
  $('loop-toggle').classList.toggle('active', studio.loopEnabled); $('loop-toggle').setAttribute('aria-pressed', String(studio.loopEnabled));
  $('loop-mode').value = studio.loopMode;
  const selected = selectionBounds(studio.selection);
  $('range-info').textContent = selected ? `${selected.start.toFixed(3)} — ${selected.end.toFixed(3)} с` : 'Не выделен';
  $('range-info').title = selected ? `Длительность ${(selected.end - selected.start).toFixed(3)} с. Нажмите, чтобы сбросить.` : 'Выделите диапазон на линейке времени';
  $('time-display').textContent = formatTime(engine.playing ? engine.position() : studio.cursor);
  const only = studio.project.tracks.find(track => track.id === engine.onlyTrackId);
  const context = currentSoundType(studio.project).name;
  $('play-context').textContent = engine.playing ? `${studio.loopEnabled ? 'Петля · ' : ''}${only?.name || context}` : context;
  $('master-gain').value = studio.project.masterGain; $('master-value').textContent = `${studio.project.masterGain > 0 ? '+' : '−'}${Math.abs(studio.project.masterGain).toFixed(1)} дБ`;
}
function renderAssets() {
  $('asset-list').innerHTML = studio.project.assets.length ? studio.project.assets.filter(asset => !asset.derived).map(asset => `<div class="asset-item" draggable="true" data-asset-id="${asset.id}" title="Перетащите на дорожку или дважды нажмите, чтобы добавить"><span>${icon('wave')}</span><div class="asset-item-content"><strong>${escapeHtml(cleanName(asset.name))}</strong><small>${asset.duration.toFixed(3)} с <span>·</span> ${asset.channels === 1 ? 'Моно' : 'Стерео'} <span>·</span> ${asset.name.split('.').pop().toUpperCase()}</small></div><button class="asset-preview" title="Прослушать исходник" aria-label="Прослушать исходник ${escapeHtml(asset.name)}">${icon('play')}</button></div>`).join('')
    : `<div class="library-empty">${icon('wave')}<p>Исходники появятся здесь</p><small>Перетаскивайте их на дорожки</small></div>`;
}
function renderInspector() {
  const clips = selectedClips();
  if (!clips.length) { $('clip-inspector').innerHTML = `<div class="inspector-empty">${icon('cursor')}<p>Выберите фрагмент</p><small>Его границы, громкость и плавные переходы будут здесь.</small></div>`; return; }
  if (clips.length > 1) { $('clip-inspector').innerHTML = `<div class="inspector-title">${icon('range')}ВЫБРАНО: ${clips.length}</div><div class="inspector-empty"><p>Несколько фрагментов</p><small>Двигайте их вместе, копируйте или склейте фрагменты одной дорожки с помощью Ctrl+J.</small></div>`; return; }
  const clip = clips[0].clip;
  const fields = [['start', 'Позиция, с', clip.start.toFixed(3), 0, 7200, .001], ['offset', 'Начало исходника, с', clip.offset.toFixed(3), 0, engine.assets.get(clip.assetId).duration, .001], ['duration', 'Длительность, с', clip.duration.toFixed(3), .001, engine.assets.get(clip.assetId).duration - clip.offset, .001], ['gain', 'Громкость, дБ', clip.gain.toFixed(1), -60, 24, .1], ['fadeIn', 'Нарастание, мс', (clip.fadeIn * 1000).toFixed(1), 0, clip.duration * 500, .1], ['fadeOut', 'Затухание, мс', (clip.fadeOut * 1000).toFixed(1), 0, clip.duration * 500, .1]];
  $('clip-inspector').innerHTML = `<div class="inspector-title">${icon('wave')}ФРАГМЕНТ</div><div class="inspector-name" title="${escapeHtml(clip.name)}">${escapeHtml(clip.name)}</div><div class="inspector-grid">${fields.map(([key, label, value, min, max, step]) => `<label>${label}<input type="number" data-clip-param="${key}" value="${value}" min="${min}" max="${max}" step="${step}" aria-label="${label}"></label>`).join('')}</div>`;
}
function renderAll() { composer.render(); normalizeSelection(); updateHeader(); updateTransport(); renderAssets(); timeline.render(); equalizer.render(); effects.render(); renderInspector(); trackSpeed.render(); }
function selectTrack(id, clearClips = true) {
  if (id === studio.selectedTrackId && (!clearClips || !studio.selectedClipIds.size)) return;
  studio.selectedTrackId = id; if (clearClips) studio.selectedClipIds.clear();
  timeline.render(); equalizer.render(); effects.render(); renderInspector(); trackSpeed.render(); updateHeader();
  if (studio.loopEnabled && studio.loopMode === 'track') refreshPlayback();
}
function selectClip(trackId, clipId, extend = false) {
  const previousTrackId = studio.selectedTrackId;
  studio.selectedTrackId = trackId;
  if (extend) { if (studio.selectedClipIds.has(clipId)) studio.selectedClipIds.delete(clipId); else studio.selectedClipIds.add(clipId); }
  else studio.selectedClipIds = new Set([clipId]);
  timeline.render(); equalizer.render(); effects.render(); renderInspector(); trackSpeed.render(); updateHeader();
  if (trackId !== previousTrackId && studio.loopEnabled && studio.loopMode === 'track') refreshPlayback();
}
function setZoom(value) {
  const old = studio.zoom, center = (timeline.viewport.scrollLeft + Math.max(0, timeline.viewport.clientWidth - 214) / 2) / old;
  studio.zoom = clamp(Math.round(value), 24, 900); $('zoom').value = studio.zoom;
  timeline.render(); timeline.viewport.scrollLeft = Math.max(0, center * studio.zoom - Math.max(0, timeline.viewport.clientWidth - 214) / 2);
}
function stopPreview() { if (previewSource) { try { previewSource.stop(); } catch {} previewSource.disconnect(); previewSource = null; } }
function loopRange() {
  if (!studio.loopEnabled) return null;
  if (studio.loopMode === 'selection') {
    const range = selectionBounds(studio.selection);
    if (!range || range.end - range.start < .005) throw new Error('Выделите на линейке диапазон не короче 5 мс.');
    return range;
  }
  if (studio.loopMode === 'track') {
    const track = selectedTrack(); if (!track?.clips.length) throw new Error('Для петли выберите дорожку со звуком.');
    return { start: trackStart(track), end: trackEnd(track) };
  }
  return { start: 0, end: projectEnd(studio.project) };
}
async function startPlayback(position = studio.cursor) {
  stopPreview();
  const range = loopRange();
  const onlyTrackId = studio.loopEnabled && studio.loopMode === 'track' ? studio.selectedTrackId : studio.playOnlyTrackId;
  const track = studio.project.tracks.find(item => item.id === onlyTrackId);
  if (track && !range && (position < trackStart(track) || position >= trackEnd(track))) position = trackStart(track);
  const played = await engine.play({ start: position, onlyTrackId, loopRange: range, end: track ? trackEnd(track) : projectEnd(studio.project) });
  if (!played) toast('Добавьте звук на дорожку, чтобы начать прослушивание.');
  updateTransport();
}
async function togglePlayback(onlyTrackId = null) {
  endPendingEdit();
  if (engine.playing && studio.playOnlyTrackId === onlyTrackId) { studio.cursor = engine.pause(); updateTransport(); return; }
  const position = engine.playing ? engine.position() : studio.cursor;
  studio.playOnlyTrackId = onlyTrackId;
  await startPlayback(position);
}
function stop() { stopPreview(); engine.stop(); studio.cursor = 0; studio.playOnlyTrackId = null; updateTransport(); timeline.renderPlayhead(0); }
function refreshPlayback() {
  if (!engine.playing) return;
  if (!projectEnd(studio.project)) { stop(); return; }
  safely(startPlayback)(engine.position());
}
function seek(time, restart = true) {
  studio.cursor = Math.max(0, time); engine.lastPosition = studio.cursor;
  if (engine.playing && restart) safely(startPlayback)(studio.cursor);
  updateTransport(); timeline.renderPlayhead(studio.cursor);
}
function selectionChanged(final) {
  if (final && studio.loopMode === 'selection' && !selectionBounds(studio.selection)) studio.loopEnabled = false;
  updateTransport(); renderInspector(); updateHeader();
  if (final && engine.playing) safely(startPlayback)(studio.cursor);
}
async function toggleLoop() {
  studio.loopEnabled = !studio.loopEnabled;
  if (studio.loopEnabled && studio.selection && studio.loopMode === 'project') studio.loopMode = 'selection';
  updateTransport(); if (engine.playing) await startPlayback(engine.position());
}

function assetMetadata(asset) { return { id: asset.id, name: asset.name, duration: asset.duration, channels: asset.channels, sampleRate: asset.sampleRate }; }
async function filesToAudio(files) {
  const supported = files.filter(file => /\.(wav|mp3|ogg)$/i.test(file.name));
  if (!supported.length) throw new Error('Выберите звуковые файлы WAV, MP3 или OGG.');
  return Promise.all(supported.map(async file => ({ name: file.name, bytes: new Uint8Array(await file.arrayBuffer()) })));
}
export async function importFiles(files, { trackId = null, layerId = studio.activeLayerId, time = studio.cursor } = {}) {
  if (!files.length) return;
  if (studio.project.assets.length + files.length > 2000) throw new Error('В проекте может быть до 2000 исходников.');
  endPendingEdit(); setBusy('Добавляем звуки', 'Читаем аудиофайлы…', 0);
  const decoded = [], failures = [];
  try {
    for (let i = 0; i < files.length; i++) {
      $('busy-detail').textContent = `${i + 1} / ${files.length} · ${files[i].name}`; $('busy-progress').value = i / files.length;
      try { decoded.push(await engine.decode(files[i].name, files[i].bytes)); } catch (error) { failures.push(`${files[i].name}: ${error.message}`); }
    }
    if (!decoded.length) throw new Error(failures.join('\n'));
    const beforeCount = activeTracks(studio.project).length;
    let libraryOnly = 0;
    commit(() => {
      let nextTime = Math.max(0, time);
      const type = currentSoundType(studio.project), layer = type.layers.find(item => item.id === layerId);
      for (const asset of decoded) {
        studio.project.assets.push(assetMetadata(asset));
        let track = studio.project.tracks.find(item => item.id === trackId);
        if (!track) {
          if (studio.project.tracks.length >= MAX_TRACKS || (layer ? variantsOf(studio.project, layer.id).length >= MAX_VARIANTS : type.layers.length >= MAX_LAYERS)) { libraryOnly++; continue; }
          track = createTrack(studio.project.tracks.length, cleanName(asset.name));
          assignVariant(studio.project, track, layer || addLayer(studio.project, track.name));
        }
        const clip = createClip(asset, trackId ? nextTime : time); track.clips.push(clip);
        studio.selectedTrackId = track.id; studio.selectedClipIds = new Set([clip.id]);
        if (trackId) nextTime += clip.duration;
      }
    }, 'restart');
    if (!beforeCount) timeline.fit();
    if (libraryOnly) toast(`${libraryOnly} звуков добавлено только в библиотеку: достигнут лимит слоёв или вариантов.`);
    else toast(`Добавлено звуков: ${decoded.length}`);
    if (failures.length) toast(`Не удалось открыть: ${failures.join('; ')}`, true);
  } finally { clearBusy(); }
}
async function importAudio(trackId = null) { await importFiles(await window.sonora.openAudio(), { trackId }); }
function addTrack() {
  if (studio.project.tracks.length >= MAX_TRACKS || currentSoundType(studio.project).layers.length >= MAX_LAYERS) { toast(`В одном типе звука может быть до ${MAX_LAYERS} слоёв.`); return; }
  commit(() => { const track = createTrack(activeTracks(studio.project).length); assignVariant(studio.project, track, addLayer(studio.project, track.name)); studio.activeLayerId = null; studio.selectedTrackId = track.id; studio.selectedClipIds.clear(); }, 'restart');
  timeline.viewport.scrollTop = timeline.surface.scrollHeight;
}
function addAssetToTrack(assetId, trackId = studio.selectedTrackId, time = studio.cursor) {
  const asset = engine.assets.get(assetId); if (!asset) return;
  if (!studio.project.tracks.some(track => track.id === trackId) && (studio.project.tracks.length >= MAX_TRACKS || (!studio.activeLayerId && currentSoundType(studio.project).layers.length >= MAX_LAYERS))) { toast('Перетащите звук на существующую дорожку.'); return; }
  commit(() => {
    let track = studio.project.tracks.find(item => item.id === trackId);
    if (!track) { track = createTrack(studio.project.tracks.length, cleanName(asset.name)); const layer = currentSoundType(studio.project).layers.find(item => item.id === studio.activeLayerId); assignVariant(studio.project, track, layer || addLayer(studio.project, track.name)); }
    const clip = createClip(asset, time); track.clips.push(clip); studio.selectedTrackId = track.id; studio.selectedClipIds = new Set([clip.id]);
  }, 'restart');
}
async function trackAction(id, action, value) {
  const track = studio.project.tracks.find(item => item.id === id); if (!track) return;
  if (action === 'play-track') { selectTrack(id, false); await togglePlayback(id); return; }
  if (action === 'load-track') { await importAudio(id); return; }
  if (action === 'speed-track') { selectTrack(id, false); trackSpeed.focus(); return; }
  commit(() => {
    if (action === 'mute') track.muted = !track.muted;
    if (action === 'solo') track.solo = !track.solo;
    if (action === 'export-track') track.export = value;
    if (action === 'remove-track') {
      studio.project.tracks = studio.project.tracks.filter(item => item.id !== id);
      if (studio.playOnlyTrackId === id) { studio.playOnlyTrackId = null; engine.onlyTrackId = null; }
    }
  }, action === 'remove-track' ? 'restart' : 'sync');
}
function split() {
  const candidates = studio.project.tracks.flatMap(track => track.clips.filter(clip => (studio.selectedClipIds.size ? studio.selectedClipIds.has(clip.id) : track.id === studio.selectedTrackId) && studio.cursor > clip.start + .0001 && studio.cursor < clip.start + clip.duration - .0001).map(clip => ({ track, clip })));
  if (!candidates.length) { toast('Поставьте курсор внутри фрагмента и нажмите S.'); return; }
  commit(() => { const ids = []; for (const { track, clip } of candidates) { const right = splitClip(track, clip.id, studio.cursor); if (right) ids.push(right.id); } studio.selectedClipIds = new Set(ids); }, 'restart');
}
function removeClips() {
  if (!studio.selectedClipIds.size) return;
  commit(() => { for (const track of studio.project.tracks) track.clips = track.clips.filter(clip => !studio.selectedClipIds.has(clip.id)); studio.selectedClipIds.clear(); }, 'restart');
}
function copyClips(cut = false) {
  const clips = selectedClips(); if (!clips.length) return;
  const start = Math.min(...clips.map(item => item.clip.start)), trackIndex = Math.min(...clips.map(item => item.trackIndex));
  studio.clipboard = clips.map(item => ({ clip: { ...item.clip, start: item.clip.start - start }, trackOffset: item.trackIndex - trackIndex }));
  if (cut) removeClips(); else toast(`Скопировано фрагментов: ${clips.length}`);
}
function pasteClips() {
  if (!studio.clipboard.length) return;
  const tracks = visibleTracks(studio.project, studio.activeLayerId);
  const baseIndex = Math.max(0, tracks.findIndex(track => track.id === studio.selectedTrackId));
  const required = baseIndex + Math.max(...studio.clipboard.map(item => item.trackOffset)) + 1;
  if (currentSoundType(studio.project).layers.length + Math.max(0, required - tracks.length) > MAX_LAYERS || studio.project.tracks.length + Math.max(0, required - tracks.length) > MAX_TRACKS) { toast('Недостаточно дорожек для вставки.', true); return; }
  commit(() => {
    while (tracks.length < required) { const track = createTrack(studio.project.tracks.length); assignVariant(studio.project, track, addLayer(studio.project, track.name)); tracks.push(track); studio.activeLayerId = null; }
    const ids = [];
    for (const item of studio.clipboard) {
      const clip = { ...item.clip, id: uid(), start: studio.cursor + item.clip.start };
      tracks[baseIndex + item.trackOffset].clips.push(clip); ids.push(clip.id);
    }
    studio.selectedClipIds = new Set(ids); studio.selectedTrackId = tracks[baseIndex].id;
  }, 'restart');
}
function duplicate() {
  const clips = selectedClips(); if (!clips.length) return;
  const distance = Math.max(...clips.map(item => item.clip.start + item.clip.duration)) - Math.min(...clips.map(item => item.clip.start));
  commit(() => { const ids = []; for (const { track, clip } of clips) { const copy = { ...clip, id: uid(), start: clip.start + distance }; track.clips.push(copy); ids.push(copy.id); } studio.selectedClipIds = new Set(ids); }, 'restart');
}
async function join() {
  const clips = selectedClips();
  if (clips.length < 2) { toast('Выберите два или больше фрагментов одной дорожки через Shift + клик.'); return; }
  if (new Set(clips.map(item => item.track.id)).size !== 1) { toast('Для склейки переместите фрагменты на одну дорожку. Для разных дорожек используйте экспорт микса.'); return; }
  endPendingEdit(); const track = clips[0].track;
  const range = { start: Math.min(...clips.map(item => item.clip.start)), end: Math.max(...clips.map(item => item.clip.start + item.clip.duration)) };
  setBusy('Склеиваем фрагменты', 'Сохраняем их расположение, паузы и плавные переходы…');
  try {
    const project = structuredClone(studio.project); project.tracks = [{ ...structuredClone(track), clips: clips.map(item => ({ ...item.clip })) }];
    const buffer = await renderAudio(project, engine.assets, [track.id], range, { raw: true });
    const asset = await engine.addBuffer(`${track.name}_склейка.wav`, buffer);
    commit(() => {
      studio.project.assets.push(assetMetadata(asset));
      track.clips = track.clips.filter(clip => !studio.selectedClipIds.has(clip.id));
      const clip = { ...createClip(asset, range.start), fadeIn: 0, fadeOut: 0 }; track.clips.push(clip); studio.selectedClipIds = new Set([clip.id]);
    }, 'restart');
    toast('Фрагменты склеены. Эквалайзер дорожки сохранён.');
  } finally { clearBusy(); }
}
function undo(redo = false) {
  endPendingEdit(); const next = redo ? studio.history.redo(studio.project) : studio.history.undo(studio.project);
  if (!next) return; studio.project = next; normalizeSelection(); markChanged(); refreshPlayback(); renderAll();
}

async function confirmUnsaved() {
  endPendingEdit(); if (!studio.dirty) return true;
  const result = await new Promise(resolve => {
    const modal = $('confirm-dialog'); $('confirm-title').textContent = 'Сохранить изменения?'; $('confirm-text').textContent = `В проекте «${studio.project.name}» есть несохранённая работа.`;
    const finish = choice => { modal.close(); resolve(choice); };
    $('confirm-cancel').onclick = () => finish('cancel'); $('confirm-discard').onclick = () => finish('discard'); $('confirm-save').onclick = () => finish('save');
    modal.oncancel = event => { event.preventDefault(); finish('cancel'); }; modal.showModal();
  });
  if (result === 'save') return saveProject();
  return result === 'discard';
}
export async function saveProject(saveAs = false) {
  endPendingEdit(); setBusy('Сохраняем проект', 'Упаковываем дорожки, настройки и исходные звуки в один файл…');
  try {
    const document = { project: structuredClone(studio.project), assets: studio.project.assets.map(asset => ({ id: asset.id, bytes: engine.assets.get(asset.id).bytes })) };
    const result = await window.sonora.saveProject(document, saveAs);
    if (!result) return false;
    savedSnapshot = JSON.stringify(studio.project); studio.dirty = false; updateHeader(); toast('Проект сохранён вместе с исходными звуками.'); return true;
  } finally { clearBusy(); }
}
async function newProject() {
  if (!await confirmUnsaved()) return;
  $('toasts').replaceChildren();
  stop(); engine.assets.clear(); trackSpeed.cache.clear(); studio.activeLayerId = null; studio.project = createProject(); studio.history.clear(); studio.clipboard = []; studio.selectedTrackId = null; studio.selectedClipIds.clear(); studio.selection = null;
  studio.loopEnabled = false; studio.loopMode = 'project'; studio.zoom = 100; $('zoom').value = 100; timeline.viewport.scrollLeft = 0; timeline.viewport.scrollTop = 0;
  savedSnapshot = JSON.stringify(studio.project); studio.dirty = false; await window.sonora.adoptProject(null); renderAll();
}
async function openProject() {
  if (!await confirmUnsaved()) return;
  const result = await window.sonora.openProject(); if (!result) return;
  const project = validateProject(result.project); stop(); setBusy('Открываем проект', 'Восстанавливаем исходные звуки…', 0);
  try {
    const temporary = new AudioEngine(() => project); temporary.context = await engine.ensureContext();
    for (let i = 0; i < result.assets.length; i++) {
      const source = result.assets[i]; $('busy-detail').textContent = `${i + 1} / ${result.assets.length} · ${source.name}`; $('busy-progress').value = i / Math.max(1, result.assets.length);
      const asset = await temporary.decode(source.name, source.bytes, source.id);
      const metadata = project.assets.find(item => item.id === asset.id); Object.assign(metadata, assetMetadata(asset));
    }
    const validated = validateProject(project);
    $('toasts').replaceChildren();
    engine.assets = temporary.assets; trackSpeed.cache.clear(); studio.activeLayerId = null; studio.project = validated; studio.history.clear(); studio.clipboard = []; studio.selectedTrackId = validated.tracks[0]?.id || null; studio.selectedClipIds.clear(); studio.selection = null; studio.loopEnabled = false;
    savedSnapshot = JSON.stringify(studio.project); studio.dirty = false; await window.sonora.adoptProject(result.path); renderAll(); timeline.fit(); toast('Проект открыт. Все звуки восстановлены из файла.');
  } finally { clearBusy(); }
}
async function loadDemo() {
  if (!await confirmUnsaved()) return;
  $('toasts').replaceChildren();
  stop(); setBusy('Готовим пример', 'Три синтезированных слоя: удар, механика и хвост…');
  try {
    const demoEngine = new AudioEngine(() => studio.project); demoEngine.context = await engine.ensureContext();
    const assets = await createDemo(demoEngine);
    const project = createProject(); project.name = 'Удар · звуковой этюд'; project.masterGain = -3;
    const names = ['Удар · основа', 'Механика · детали', 'Хвост · пространство'];
    assets.forEach((asset, index) => {
      project.assets.push(assetMetadata(asset)); const track = createTrack(index, names[index]);
      const first = createClip(asset, [0.25, 0.27, 0.3][index]); const second = createClip(asset, [3.15, 3.17, 3.2][index]);
      track.clips.push(first, second); track.volume = [0, -4, -2][index]; track.pan = [0, -.12, .08][index];
      if (index === 0) { track.bands[2].gain = 3.5; track.bands[2].q = .8; track.bands[7].gain = -2; }
      if (index === 2) { track.bands[1].gain = -4; track.bands[8].gain = -5; }
      project.tracks.push(track);
    });
    normalizeWorkbench(project); engine.assets = demoEngine.assets; trackSpeed.cache.clear(); studio.activeLayerId = null; studio.project = project; studio.history.clear(); studio.clipboard = []; studio.selectedTrackId = project.tracks[0].id; studio.selectedClipIds = new Set([project.tracks[0].clips[0].id]); studio.selection = { start: 0, end: 2.95 }; studio.loopMode = 'selection'; studio.loopEnabled = false;
    savedSnapshot = ''; studio.dirty = true; await window.sonora.adoptProject(null); renderAll(); timeline.fit();
    toast('Пример готов. Нажмите Пробел и изменяйте полосы EQ.');
  } finally { clearBusy(); }
}

function presetBands(kind) {
  if (taskPresets[kind]) return taskPresets[kind].bands.map(([type,frequency,gain,q])=>({id:uid(),type,frequency,gain,q,enabled:true}));
  const bands = defaultBands();
  const gains = { impact: [0, 3, 4, -2, -1, 1, 2, 1, -3, -4], soft: [0, 0, 0, 0, 0, 0, -.5, -2, -7, -10], radio: [-18, -16, -10, -3, 2, 4, 2, -4, -13, -18], bass: [2, 5, 3, 1, 0, 0, 0, 0, 0, 0] }[kind] || new Array(10).fill(0);
  bands.forEach((band, index) => { band.gain = gains[index]; band.q = .75; }); return bands;
}
async function loadPreset() {
  if (!selectedTrack()) return;
  const result = await window.sonora.openPreset(); if (!result) return;
  const preset = parsePreset(result.text); commit(() => { selectedTrack().bands = preset.bands; selectedTrack().eqEnabled = true; });
  toast(`Настройки из «${result.name}» загружены: ${preset.bands.length} полос.`);
}
async function savePreset() { const track = selectedTrack(); if (track && await window.sonora.savePreset(track.name, serializePreset(track))) toast('Настройки эквалайзера сохранены.'); }

function updateExportDialog() {
  const mode = document.querySelector('input[name="mode"]:checked').value;
  $('stems-align-field').hidden = mode !== 'stems'; $('bit-depth-field').hidden = $('export-format').value !== 'wav';
  document.querySelector('.export-tracks-block').hidden = mode === 'clip'; $('export-range').disabled = mode === 'clip';
  const count = enabledTracks(studio.project).filter(track => track.export && track.clips.length).length;
  const range = mode === 'clip' && selectedClips().length === 1 ? { start: selectedClips()[0].clip.start, end: selectedClips()[0].clip.start + selectedClips()[0].clip.duration } : $('export-range').value === 'selection' ? selectionBounds(studio.selection) : { start: 0, end: projectEnd(studio.project) };
  $('export-summary').textContent = `${mode === 'clip' ? '1 фрагмент' : `${count} дорожек`} · ${range ? (range.end - range.start).toFixed(3) : '0'} с · Стерео`;
}
function openExport() {
  endPendingEdit(); if (!projectEnd(studio.project)) { toast('Добавьте звук на дорожку перед экспортом.'); return; }
  const clips = selectedClips(); document.querySelector('input[name="mode"][value="clip"]').disabled = clips.length !== 1;
  if (clips.length !== 1 && document.querySelector('input[name="mode"][value="clip"]').checked) document.querySelector('input[name="mode"][value="mix"]').checked = true;
  $('export-clip-name').textContent = clips.length === 1 ? clips[0].clip.name : 'Выберите фрагмент';
  $('export-tracks').innerHTML = enabledTracks(studio.project).map(track => `<label class="export-track-row"><input type="checkbox" data-export-id="${track.id}" ${track.export ? 'checked' : ''}><i class="track-dot" style="background:${track.color}"></i><span>${escapeHtml(track.name)}${track.clips.length ? '' : ' · пустая'}</span></label>`).join('');
  $('export-range').querySelector('[value="selection"]').disabled = !selectionBounds(studio.selection);
  if (!selectionBounds(studio.selection)) $('export-range').value = 'all';
  updateExportDialog(); $('export-dialog').showModal();
}
async function exportAudio(event, toRing = false) {
  event?.preventDefault(); endPendingEdit();
  const mode = document.querySelector('input[name="mode"]:checked').value, format = $('export-format').value, sampleRate = Number($('export-rate').value), bitDepth = $('export-depth').value, protect = $('export-protect').checked;
  let project = structuredClone(studio.project), tracks = enabledTracks(project).filter(track => track.export && track.clips.length), clipName = null;
  let range = $('export-range').value === 'selection' ? selectionBounds(studio.selection) : { start: 0, end: projectEnd(project) };
  if (mode === 'clip') {
    const clips = selectedClips(); if (clips.length !== 1) throw new Error('Выберите один фрагмент для экспорта.');
    const { track, clip } = clips[0]; project.tracks = [{ ...structuredClone(track), clips: [structuredClone(clip)] }]; tracks = project.tracks;
    range = { start: clip.start, end: clip.start + clip.duration }; clipName = clip.name;
  }
  if (!tracks.length) throw new Error('Отметьте хотя бы одну дорожку со звуком.');
  if (!range || range.end - range.start < .001) throw new Error('Выберите диапазон для экспорта.');
  const jobs = mode === 'stems' ? tracks.map(track => {
    const aligned = $('stems-align').checked;
    const start = aligned ? range.start : Math.max(range.start, trackStart(track)), end = aligned ? range.end : Math.min(range.end, trackEnd(track));
    return { name: track.name, ids: [track.id], range: { start, end } };
  }).filter(job => job.range.end > job.range.start) : [{ name: clipName || project.name, ids: tracks.map(track => track.id), range }];
  if (!jobs.length) throw new Error('В выбранном диапазоне нет звуков.');
  if (toRing && jobs.length > 32) throw new Error('На стенд можно передать до 32 вариантов за раз.');
  const destination = toRing || await window.sonora.chooseExport({ format, separate: mode === 'stems', names: jobs.map(job => job.name), name: jobs[0].name });
  if (!destination) return;
  $('export-dialog').close(); if (engine.playing) studio.cursor = engine.pause(); stopPreview(); updateTransport();
  setBusy('Экспортируем аудио', 'Собираем звучание дорожек…', 0);
  let completed = 0;
  const ringItems = [];
  try {
    for (let index = 0; index < jobs.length; index++) {
      const job = jobs[index]; $('busy-title').textContent = `Экспорт · ${index + 1} / ${jobs.length}`; $('busy-detail').textContent = `${job.name} · ${format.toUpperCase()}`; $('busy-progress').value = index / jobs.length;
      const buffer = await renderAudio(project, engine.assets, job.ids, job.range, { sampleRate: toRing ? 48000 : sampleRate, includeTail: $('export-tail').checked });
      if (toRing) ringItems.push({ name: job.name, bytes: encodeWav(buffer, protect) });
      else await window.sonora.writeExport(encodeWav(buffer, protect), { index, format, sampleRate, bitDepth }); completed++;
    }
    if (toRing) { await window.sonora.sendToRing(ringItems); toast(`Передано на стенд Ring: ${ringItems.length}. Выберите событие и утвердите звук.`); }
    else toast(`Экспорт готов: ${completed} ${completed === 1 ? 'файл' : 'файла'}.`, false, { label: 'Показать', run: () => window.sonora.revealExport() });
  } catch (error) { throw new Error(`${error.message}${completed && !toRing ? ` Успешно сохранено файлов: ${completed}.` : ''}`); }
  finally { clearBusy(); }
}

$('project-name').addEventListener('change', () => { const value = $('project-name').value.trim(); if (value && value !== studio.project.name) commit(() => { studio.project.name = value; }, 'none'); else $('project-name').value = studio.project.name; });
$('play').onclick = safely(() => togglePlayback()); $('stop').onclick = stop; $('to-start').onclick = () => seek(0);
$('loop-toggle').onclick = safely(toggleLoop); $('loop-mode').onchange = safely(async () => { studio.loopMode = $('loop-mode').value; if (engine.playing) await startPlayback(engine.position()); updateTransport(); });
$('range-info').onclick = () => { studio.selection = null; timeline.renderSelection(); selectionChanged(true); };
$('master-gain').oninput = () => { beginEdit(); studio.project.masterGain = Number($('master-gain').value); engine.sync(); liveChange(); $('master-value').textContent = `${studio.project.masterGain.toFixed(1)} дБ`; };
$('master-gain').onchange = () => endEdit('sync');
$('undo').onclick = () => undo(); $('redo').onclick = () => undo(true);
$('new-project').onclick = safely(newProject); $('open-project').onclick = safely(openProject); $('save-project').onclick = safely(() => saveProject());
$('import-audio').onclick = safely(() => importAudio()); $('empty-import').onclick = safely(() => importAudio()); $('load-demo').onclick = safely(loadDemo);
$('add-track').onclick = addTrack; $('split').onclick = split; $('join').onclick = safely(join); $('delete').onclick = removeClips; $('duplicate').onclick = duplicate;
$('tool-select').onclick = () => { studio.tool = 'select'; updateHeader(); }; $('tool-range').onclick = () => { studio.tool = 'range'; updateHeader(); };
$('snap-toggle').onclick = () => { studio.snap = !studio.snap; updateHeader(); };
$('zoom').oninput = () => setZoom(Number($('zoom').value)); $('zoom-in').onclick = () => setZoom(studio.zoom * 1.3); $('zoom-out').onclick = () => setZoom(studio.zoom / 1.3); $('zoom-fit').onclick = () => timeline.fit();
$('eq-power').onclick = () => { if (selectedTrack()) commit(() => { selectedTrack().eqEnabled = !selectedTrack().eqEnabled; }); };
$('eq-reset').onclick = () => { if (selectedTrack()) commit(() => { selectedTrack().bands = defaultBands(); selectedTrack().eqEnabled = true; }); };
$('add-band').onclick = () => { if (selectedTrack() && selectedTrack().bands.length < MAX_BANDS) { commit(() => { selectedTrack().bands.push({ id: uid(), type: 'peaking', frequency: 1000, gain: 0, q: 1, enabled: true }); }); $('eq-bands').scrollLeft = $('eq-bands').scrollWidth; } };
$('eq-preset').onchange = () => { const kind = $('eq-preset').value; if (kind && selectedTrack()) commit(() => { selectedTrack().bands = presetBands(kind); selectedTrack().eqEnabled = true; }); $('eq-preset').value = ''; };
$('load-preset').onclick = safely(loadPreset); $('save-preset').onclick = safely(savePreset);
$('export').onclick = openExport; $('export-form').onsubmit = safely(exportAudio);
$('open-ring').onclick = safely(() => window.sonora.openRing());
$('send-ring').onclick = safely(() => exportAudio(null, true));
$('export-form').onchange = event => {
  if (event.target.dataset.exportId) commit(() => { studio.project.tracks.find(track => track.id === event.target.dataset.exportId).export = event.target.checked; }, 'none');
  updateExportDialog();
};
$('export-select-all').onclick = () => {
  const all = enabledTracks(studio.project).every(track => track.export);
  commit(() => { for (const track of enabledTracks(studio.project)) track.export = !all; }, 'none');
  for (const input of $('export-tracks').querySelectorAll('input')) input.checked = !all;
  updateExportDialog();
};
$('show-help').onclick = () => $('help-dialog').showModal();
for (const button of document.querySelectorAll('[data-close-dialog]')) button.onclick = () => $(button.dataset.closeDialog).close();
$('clip-inspector').onchange = event => {
  const key = event.target.dataset.clipParam, selected = selectedClips();
  if (!key || selected.length !== 1 || !Number.isFinite(event.target.valueAsNumber)) { renderInspector(); return; }
  const clip = selected[0].clip, asset = engine.assets.get(clip.assetId); let value = event.target.valueAsNumber;
  commit(() => {
    if (key === 'start') clip.start = clamp(value, 0, 7200);
    if (key === 'offset') { clip.offset = clamp(value, 0, asset.duration - .001); clip.duration = Math.min(clip.duration, asset.duration - clip.offset); }
    if (key === 'duration') clip.duration = clamp(value, .001, asset.duration - clip.offset);
    if (key === 'gain') clip.gain = clamp(value, -60, 24);
    if (key === 'fadeIn' || key === 'fadeOut') clip[key] = clamp(value / 1000, 0, clip.duration / 2);
    clip.fadeIn = Math.min(clip.fadeIn, clip.duration / 2); clip.fadeOut = Math.min(clip.fadeOut, clip.duration / 2);
  }, 'restart');
};
$('asset-list').addEventListener('dragstart', event => { const item = event.target.closest('[data-asset-id]'); if (item) { event.dataTransfer.setData('application/x-sonora-asset', item.dataset.assetId); event.dataTransfer.effectAllowed = 'copy'; } });
$('asset-list').addEventListener('dblclick', event => { if (!event.target.closest('.asset-preview')) { const item = event.target.closest('[data-asset-id]'); if (item) addAssetToTrack(item.dataset.assetId); } });
$('asset-list').addEventListener('click', safely(async event => {
  if (!event.target.closest('.asset-preview')) return;
  const item = event.target.closest('[data-asset-id]'), asset = engine.assets.get(item.dataset.assetId); if (!asset) return;
  if (engine.playing) studio.cursor = engine.pause(); stopPreview(); updateTransport();
  const context = await engine.ensureContext(), source = context.createBufferSource(), volume = context.createGain();
  source.buffer = asset.buffer; volume.gain.value = .65; source.connect(volume); volume.connect(context.destination);
  source.onended = () => { source.disconnect(); volume.disconnect(); if (previewSource === source) { previewSource = null; updateTransport(); } };
  previewSource = source; $('play-context').textContent = `Исходник · ${cleanName(asset.name)}`; source.start();
}));
document.addEventListener('dragover', event => { if (event.dataTransfer.types.includes('Files')) event.preventDefault(); });
document.addEventListener('drop', safely(async event => {
  event.preventDefault(); if (event.target.closest('.timeline-viewport')) return;
  if(document.querySelector('dialog[open]'))return;
  if (event.dataTransfer.files.length) await importFiles(await filesToAudio([...event.dataTransfer.files]));
}));

document.addEventListener('keydown', event => {
  if (busy || document.querySelector('dialog[open]')) return;
  const typing = event.target.matches('textarea,select,input:not([type=range]):not([type=checkbox]):not([type=radio])') || event.target.isContentEditable;
  if (event.ctrlKey && event.key.toLowerCase() === 's') { event.preventDefault(); document.activeElement.blur(); safely(() => saveProject(event.shiftKey))(); return; }
  if (typing) return;
  const key = event.key.toLowerCase();
  if (event.ctrlKey) {
    const actions = { z: () => undo(event.shiftKey), y: () => undo(true), c: () => copyClips(), x: () => copyClips(true), v: pasteClips, d: duplicate, j: join, i: () => importAudio(), o: openProject, n: newProject, e: openExport, a: () => { studio.selectedClipIds = new Set(visibleTracks(studio.project, studio.activeLayerId).flatMap(track => track.clips.map(clip => clip.id))); renderAll(); } };
    if (actions[key]) { event.preventDefault(); safely(actions[key])(); } return;
  }
  if (event.repeat && [' ', 'l'].includes(key)) return;
  const actions = { ' ': () => togglePlayback(), enter: stop, home: () => seek(0), s: split, v: () => { studio.tool = 'select'; updateHeader(); }, r: () => { studio.tool = 'range'; updateHeader(); }, l: toggleLoop, f: () => timeline.fit(), delete: removeClips, backspace: removeClips, escape: () => { studio.selectedClipIds.clear(); studio.selection = null; renderAll(); } };
  if (actions[key]) { event.preventDefault(); safely(actions[key])(); }
});
window.addEventListener('beforeunload', event => { endPendingEdit(); if (studio.dirty) { event.preventDefault(); event.returnValue = false; } });
new ResizeObserver(() => timeline.render()).observe(timeline.viewport);
let lastFrame = 0, heldPeak = 0;
function animate(timestamp) {
  if (timestamp - lastFrame > 40) {
    lastFrame = timestamp;
    if (engine.playing) {
      const position = engine.position(); $('time-display').textContent = formatTime(position); timeline.renderPlayhead(position);
      const x = position * studio.zoom - timeline.viewport.scrollLeft;
      const width = timeline.viewport.clientWidth - 214;
      if (x > width - 20 || x < 0) timeline.viewport.scrollLeft = Math.max(0, position * studio.zoom - width * .25);
      equalizer.draw();
    }
    const peak = engine.meter(); heldPeak = Math.max(peak, heldPeak * .8);
    effects.meter();
    const db = gainToDb(heldPeak); $('meter-bar').style.width = `${clamp((db + 60) / 60 * 100, 0, 100)}%`;
    $('meter-bar').parentElement.classList.toggle('clipping', peak > 1); $('meter-bar').parentElement.setAttribute('aria-valuenow', String(Math.round(db)));
    $('meter-readout').textContent = db > -60 ? `${db.toFixed(0)}` : '−∞';
  }
  requestAnimationFrame(animate);
}
renderAll(); requestAnimationFrame(animate);
if (!window.sonora) toast('Запустите Sonora Studio.exe, чтобы открыть аудиофайлы и сохранить проект.', true);
