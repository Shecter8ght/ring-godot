import { icon } from './icons.mjs';
import { clamp, projectEnd, activeTracks, visibleTracks, layerOf, trimLeft, trimRight } from './model.mjs';
import { trackSpeed } from './speed-model.mjs';

export const escapeHtml = value => String(value).replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
export const formatTime = seconds => {
  const value = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(value / 60), whole = Math.floor(value % 60), ms = Math.floor((value - Math.floor(value)) * 1000 + 0.000001);
  return `${String(minutes).padStart(2, '0')}:${String(whole).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
};
const HEAD = 214, ROW = 102;

export class Timeline {
  constructor(state, engine, hooks) {
    this.state = state; this.engine = engine; this.hooks = hooks;
    this.viewport = document.getElementById('timeline-viewport');
    this.surface = document.getElementById('timeline-surface');
    this.rows = document.getElementById('track-rows');
    this.ruler = document.getElementById('ruler');
    this.width = 1000;
    this.viewport.addEventListener('pointerdown', event => this.pointerDown(event));
    document.addEventListener('pointermove', event => this.pointerMove(event));
    document.addEventListener('pointerup', event => this.pointerUp(event));
    this.viewport.addEventListener('click', event => this.click(event));
    this.viewport.addEventListener('dblclick', event => this.doubleClick(event));
    this.viewport.addEventListener('input', event => this.input(event));
    this.viewport.addEventListener('change', event => this.change(event));
    this.viewport.addEventListener('dragover', event => this.dragOver(event));
    this.viewport.addEventListener('dragleave', event => { if (!this.viewport.contains(event.relatedTarget)) this.clearDrop(); });
    this.viewport.addEventListener('drop', event => this.drop(event));
    this.viewport.addEventListener('wheel', event => {
      if (event.ctrlKey) { event.preventDefault(); this.hooks.zoom(clamp(this.state.zoom * Math.exp(-event.deltaY * 0.002), 24, 900)); }
    }, { passive: false });
  }
  render() {
    const state = this.state, project = state.project;
    const tracks = visibleTracks(project, state.activeLayerId);
    const duration = Math.max(10, projectEnd(project) + 1.2, (state.selection?.end || 0) + 1, state.cursor + 1);
    this.width = Math.max(this.viewport.clientWidth - HEAD - 10, Math.ceil(duration * state.zoom));
    this.surface.style.width = `${HEAD + this.width}px`;
    this.rows.innerHTML = tracks.map((track, index) => `<div class="track-row ${track.id === state.selectedTrackId ? 'selected' : ''} ${layerOf(project, track)?.enabled === false ? 'layer-off' : ''}" data-track-id="${track.id}" style="--track-color:${track.color}"><div class="track-header"><div class="track-header-top"><span class="track-index">${String(index + 1).padStart(2, '0')}</span><span class="track-name" title="Двойной клик — переименовать">${escapeHtml(track.name)}</span><input class="track-export" type="checkbox" data-action="export-track" ${track.export ? 'checked' : ''} aria-label="Экспорт дорожки ${escapeHtml(track.name)}" title="Включить в экспорт"></div><div class="track-layer-label" title="${escapeHtml(layerOf(project, track)?.name || track.name)}">${escapeHtml(layerOf(project, track)?.name || track.name)}</div><div class="track-actions"><button class="track-button ${track.muted ? 'muted' : ''}" data-action="mute" title="Выключить дорожку" aria-label="Mute ${escapeHtml(track.name)}">M</button><button class="track-button ${track.solo ? 'solo' : ''}" data-action="solo" title="Соло" aria-label="Solo ${escapeHtml(track.name)}">S</button><button class="track-button play-track" data-action="play-track" title="Слушать только эту дорожку" aria-label="Слушать дорожку ${escapeHtml(track.name)}">${icon('play')}</button><button class="track-button load-track" data-action="load-track" title="Загрузить звук в эту дорожку" aria-label="Загрузить звук в дорожку">${icon('plus')}</button><button class="track-button speed-track" data-action="speed-track" title="Изменить скорость, сохраняя высоту звука" aria-label="Скорость дорожки ${escapeHtml(track.name)}">${trackSpeed(track) === null ? "×?" : trackSpeed(track) + "×"}</button><button class="track-button remove-track" data-action="remove-track" title="Удалить дорожку" aria-label="Удалить дорожку ${escapeHtml(track.name)}">${icon('close')}</button></div><div class="track-volume-row"><input class="track-volume" data-action="volume" aria-label="Громкость дорожки ${escapeHtml(track.name)}" type="range" min="-60" max="12" step="0.5" value="${track.volume}"><span class="track-volume-value">${track.volume.toFixed(1)} дБ</span><input class="track-pan" data-action="pan" type="number" min="-100" max="100" step="1" value="${Math.round(track.pan * 100)}" title="Панорама: −100 влево, 100 вправо" aria-label="Панорама дорожки ${escapeHtml(track.name)}"></div></div><div class="track-lane" data-track-id="${track.id}" style="width:${this.width}px;background-size:${this.gridStep() * state.zoom}px 100%">${track.clips.map(clip => this.clipHtml(clip)).join('')}</div></div>`).join('');
    document.getElementById('empty-state').hidden = tracks.length > 0;
    this.renderRuler();
    this.renderSelection();
    this.renderPlayhead(this.engine.playing ? this.engine.position() : state.cursor);
    for (const canvas of this.rows.querySelectorAll('canvas.clip-waveform')) {
      const track = project.tracks.find(item => item.id === canvas.closest('[data-track-id]').dataset.trackId);
      const clip = track.clips.find(item => item.id === canvas.dataset.clipId);
      drawWave(canvas, this.engine.assets.get(clip.assetId), clip, track.color);
    }
  }
  clipHtml(clip) {
    return `<div class="audio-clip ${this.state.selectedClipIds.has(clip.id) ? 'selected' : ''}" data-clip-id="${clip.id}" style="left:${clip.start * this.state.zoom}px;width:${Math.max(3, clip.duration * this.state.zoom)}px" tabindex="0" role="option" aria-selected="${this.state.selectedClipIds.has(clip.id)}" aria-label="${escapeHtml(clip.name)}, ${formatTime(clip.start)}, длительность ${clip.duration.toFixed(3)} с"><div class="clip-title">${escapeHtml(clip.name)}<small>${clip.duration.toFixed(3)} с</small></div><canvas class="clip-waveform" data-clip-id="${clip.id}"></canvas><div class="clip-trim left" data-trim="left" title="Обрезать начало"></div><div class="clip-trim right" data-trim="right" title="Обрезать конец"></div></div>`;
  }
  gridStep() { return [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30, 60].find(value => value * this.state.zoom >= 70) || 120; }
  renderRuler() {
    const step = this.gridStep(), minor = step / 5;
    let html = '';
    for (let i = 0; i * minor * this.state.zoom < this.width && i < 4000; i++) {
      const major = i % 5 === 0;
      const value = Math.round(i * minor * 10000) / 10000;
      html += `<div class="ruler-tick ${major ? '' : 'minor'}" style="left:${value * this.state.zoom}px">${major ? `<span>${value < 60 ? `${value.toFixed(step < 1 ? 2 : 0)} с` : formatTime(value).slice(0, 5)}</span>` : ''}</div>`;
    }
    this.ruler.innerHTML = html + '<div class="ruler-range"></div><div class="ruler-cursor"></div>';
  }
  renderSelection() {
    const selection = this.state.selection;
    const overlay = document.getElementById('time-selection');
    const rulerRange = this.ruler.querySelector('.ruler-range');
    overlay.hidden = !selection;
    if (selection) {
      overlay.style.left = `${HEAD + selection.start * this.state.zoom}px`;
      overlay.style.width = `${(selection.end - selection.start) * this.state.zoom}px`;
    }
    if (rulerRange) {
      rulerRange.hidden = !selection;
      rulerRange.style.cssText = selection ? `position:absolute;top:0;bottom:0;left:${selection.start * this.state.zoom}px;width:${(selection.end - selection.start) * this.state.zoom}px;background:#edb27f20;border-top:2px solid #edb27f;pointer-events:none` : '';
    }
  }
  renderPlayhead(position) {
    document.getElementById('playhead').style.left = `${HEAD + position * this.state.zoom}px`;
    const marker = this.ruler.querySelector('.ruler-cursor');
    if (marker) marker.style.cssText = `position:absolute;bottom:0;left:${position * this.state.zoom - 4}px;width:9px;height:8px;clip-path:polygon(0 0,100% 0,50% 100%);background:#edb27f;pointer-events:none`;
  }
  eventTime(event) { return clamp((event.clientX - this.surface.getBoundingClientRect().left - HEAD) / this.state.zoom, 0, this.width / this.state.zoom); }
  snap(value, event, excluded = new Set()) {
    if (!this.state.snap || event.altKey) return Math.max(0, value);
    const points = [0, this.state.cursor];
    if (this.state.selection) points.push(this.state.selection.start, this.state.selection.end);
    for (const track of activeTracks(this.state.project)) for (const clip of track.clips) if (!excluded.has(clip.id)) points.push(clip.start, clip.start + clip.duration);
    let result = Math.round(value / 0.01) * 0.01, distance = 7 / this.state.zoom;
    for (const point of points) if (Math.abs(value - point) < distance) { result = point; distance = Math.abs(value - point); }
    return Math.max(0, result);
  }
  pointerDown(event) {
    if (event.button !== 0 || event.target.closest('button,input,select,.empty-state')) return;
    const row = event.target.closest('.track-row');
    const clipElement = event.target.closest('.audio-clip');
    if (event.target.closest('.track-header')) { this.hooks.selectTrack(row.dataset.trackId); return; }
    if (clipElement && this.state.tool !== 'range') {
      const trackId = row.dataset.trackId, clipId = clipElement.dataset.clipId;
      const track = this.state.project.tracks.find(item => item.id === trackId);
      const clip = track.clips.find(item => item.id === clipId);
      const trim = event.target.dataset.trim;
      if (event.shiftKey && !trim) { this.hooks.selectClip(trackId, clipId, true); return; }
      if (!this.state.selectedClipIds.has(clipId) || trim) this.hooks.selectClip(trackId, clipId, false);
      else this.hooks.selectTrack(trackId, false);
      const selected = [];
      const tracks = visibleTracks(this.state.project, this.state.activeLayerId);
      tracks.forEach((source, trackIndex) => source.clips.forEach(item => { if (this.state.selectedClipIds.has(item.id)) selected.push({ clip: item, original: { ...item }, trackIndex }); }));
      this.drag = { kind: trim || 'move', x: event.clientX, y: event.clientY, trackId, trackIndex: tracks.indexOf(track), clipId, original: { ...clip }, selected, tracks, started: false };
      event.preventDefault();
      return;
    }
    if (event.target.closest('.ruler,.track-lane')) {
      if (row) this.hooks.selectTrack(row.dataset.trackId, false);
      const time = this.snap(this.eventTime(event), event);
      this.drag = { kind: 'range', x: event.clientX, y: event.clientY, time, started: false };
      this.hooks.seek(time, false);
      this.state.selectedClipIds.clear();
      this.state.selection = null; this.renderSelection();
      this.hooks.selectionChanged(false);
      event.preventDefault();
    }
  }
  pointerMove(event) {
    if (!this.drag) return;
    const drag = this.drag;
    if (!drag.started && Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 3) return;
    if (drag.kind === 'range') {
      drag.started = true;
      const time = this.snap(this.eventTime(event), event);
      this.state.selection = { start: Math.min(time, drag.time), end: Math.max(time, drag.time) };
      this.renderSelection(); this.hooks.selectionChanged(false); return;
    }
    if (!drag.started) { this.hooks.beginEdit(); drag.started = true; document.body.classList.add(drag.kind === 'move' ? 'is-dragging' : 'is-trimming'); }
    const delta = (event.clientX - drag.x) / this.state.zoom;
    if (drag.kind === 'move') {
      const excluded = this.state.selectedClipIds;
      let dt = this.snap(drag.original.start + delta, event, excluded) - drag.original.start;
      dt = Math.max(dt, -Math.min(...drag.selected.map(item => item.original.start)));
      const rawIndex = Math.floor((event.clientY - this.surface.getBoundingClientRect().top - 32) / ROW);
      const minimum = Math.min(...drag.selected.map(item => item.trackIndex));
      const maximum = Math.max(...drag.selected.map(item => item.trackIndex));
      const trackDelta = clamp(rawIndex - drag.trackIndex, -minimum, drag.tracks.length - 1 - maximum);
      for (const track of this.state.project.tracks) track.clips = track.clips.filter(clip => !excluded.has(clip.id));
      for (const item of drag.selected) {
        item.clip.start = Math.max(0, item.original.start + dt);
        drag.tracks[item.trackIndex + trackDelta].clips.push(item.clip);
      }
      this.state.selectedTrackId = drag.tracks[drag.trackIndex + trackDelta].id;
    } else {
      const track = this.state.project.tracks.find(item => item.id === drag.trackId);
      const clip = track.clips.find(item => item.id === drag.clipId);
      Object.assign(clip, drag.original);
      const asset = this.engine.assets.get(clip.assetId);
      if (drag.kind === 'left') trimLeft(clip, this.snap(drag.original.start + delta, event, new Set([clip.id])), asset.duration);
      else trimRight(clip, this.snap(drag.original.start + drag.original.duration + delta, event, new Set([clip.id])), asset.duration);
    }
    if (!this.renderPending) this.renderPending = requestAnimationFrame(() => { this.renderPending = null; this.render(); });
  }
  pointerUp() {
    if (!this.drag) return;
    const drag = this.drag; this.drag = null;
    document.body.classList.remove('is-dragging', 'is-trimming');
    if (drag.kind === 'range') {
      if (this.state.selection && this.state.selection.end - this.state.selection.start < 0.001) this.state.selection = null;
      if (this.state.selection) this.hooks.seek(this.state.selection.start, false);
      this.hooks.selectionChanged(true);
      this.render();
    } else if (drag.started) this.hooks.endEdit('restart');
  }
  click(event) {
    const button = event.target.closest('button[data-action]');
    if (!button) return;
    const row = button.closest('.track-row');
    if (row) this.hooks.trackAction(row.dataset.trackId, button.dataset.action);
  }
  input(event) {
    const input = event.target;
    if (!['volume', 'pan'].includes(input.dataset.action)) return;
    const row = input.closest('.track-row'), value = Number(input.value);
    if (!Number.isFinite(value)) return;
    if (!this.inputGesture) { this.hooks.beginEdit(); this.inputGesture = true; }
    this.hooks.trackParam(row.dataset.trackId, input.dataset.action, value);
    if (input.dataset.action === 'volume') row.querySelector('.track-volume-value').textContent = `${value.toFixed(1)} дБ`;
  }
  change(event) {
    const input = event.target;
    const row = input.closest('.track-row');
    if (input.dataset.action === 'export-track') this.hooks.trackAction(row.dataset.trackId, 'export-track', input.checked);
    else if (this.inputGesture && ['volume', 'pan'].includes(input.dataset.action)) { this.inputGesture = false; this.hooks.endEdit('sync'); }
  }
  doubleClick(event) {
    const name = event.target.closest('.track-name,.clip-title');
    if (!name) return;
    const row = name.closest('.track-row');
    const clipId = name.closest('.audio-clip')?.dataset.clipId;
    const track = this.state.project.tracks.find(item => item.id === row.dataset.trackId);
    const item = clipId ? track.clips.find(clip => clip.id === clipId) : track;
    const input = document.createElement('input'); input.value = item.name; input.maxLength = 120;
    input.style.cssText = 'background:#162133;border:1px solid #edb27f;color:#e0e6f0;font-size:10px;width:100%;min-width:0;outline:none;border-radius:3px;padding:1px 3px';
    name.replaceWith(input); input.focus(); input.select();
    let finished = false;
    const finish = cancel => { if (finished) return; finished = true; const value = input.value.trim(); if (!cancel && value && value !== item.name) this.hooks.rename(track.id, clipId, value); else this.render(); };
    input.addEventListener('blur', () => finish(false));
    input.addEventListener('keydown', key => { if (key.key === 'Enter') { key.stopPropagation(); finish(false); } if (key.key === 'Escape') { key.stopPropagation(); finish(true); } });
  }
  dragOver(event) {
    if (!event.dataTransfer.types.some(type => ['Files', 'application/x-sonora-asset'].includes(type))) return;
    event.preventDefault(); event.dataTransfer.dropEffect = 'copy';
    this.clearDrop(); this.viewport.classList.add('drag-over');
    event.target.closest('.track-lane')?.classList.add('drop-target');
  }
  clearDrop() { this.viewport.classList.remove('drag-over'); for (const lane of this.rows.querySelectorAll('.drop-target')) lane.classList.remove('drop-target'); }
  drop(event) {
    event.preventDefault(); event.stopPropagation(); this.clearDrop();
    const lane = event.target.closest('.track-lane');
    this.hooks.drop({ assetId: event.dataTransfer.getData('application/x-sonora-asset'), files: [...event.dataTransfer.files], trackId: lane?.dataset.trackId || null, time: this.snap(this.eventTime(event), event) });
  }
  fit() {
    const duration = Math.max(1.5, projectEnd(this.state.project) + 0.3);
    this.hooks.zoom(clamp((this.viewport.clientWidth - HEAD - 40) / duration, 24, 900));
    this.viewport.scrollLeft = 0;
  }
}

export function drawWave(canvas, asset, clip, color = '#99b7e3') {
  if (!asset) return;
  const width = Math.max(1, Math.min(4096, Math.ceil(canvas.clientWidth)));
  const height = Math.max(1, canvas.clientHeight);
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = width * ratio; canvas.height = height * ratio;
  const context = canvas.getContext('2d'); context.scale(ratio, ratio);
  const peaks = asset.peaks, center = height / 2, amplitude = height * 0.45;
  context.strokeStyle = `${color}20`; context.beginPath(); context.moveTo(0, center); context.lineTo(width, center); context.stroke();
  context.fillStyle = color;
  for (let x = 0; x < width; x++) {
    const first = Math.floor((clip.offset + clip.duration * x / width) / asset.duration * peaks.count);
    const last = Math.min(peaks.count - 1, Math.ceil((clip.offset + clip.duration * (x + 1) / width) / asset.duration * peaks.count));
    let lo = 0, hi = 0;
    for (let i = first; i <= last; i++) { lo = Math.min(lo, peaks.min[i] || 0); hi = Math.max(hi, peaks.max[i] || 0); }
    context.fillRect(x, center - hi * amplitude, 1, Math.max(.65, (hi - lo) * amplitude));
  }
  context.fillStyle = '#0c152a66';
  const fadeInWidth = clip.fadeIn / clip.duration * width, fadeOutWidth = clip.fadeOut / clip.duration * width;
  if (fadeInWidth > 1) { context.beginPath(); context.moveTo(0, 0); context.lineTo(fadeInWidth, 0); context.lineTo(0, height); context.closePath(); context.fill(); }
  if (fadeOutWidth > 1) { context.beginPath(); context.moveTo(width - fadeOutWidth, 0); context.lineTo(width, 0); context.lineTo(width, height); context.closePath(); context.fill(); }
}
