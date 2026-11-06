import { defaultTrackFx, defaultLimiter, validateTrackFx, validateLimiter } from './fx-model.mjs';
import { createSoundTypes, enabledTracks, normalizeWorkbench, validateWorkbench, MAX_STORED_TRACKS } from './workbench-model.mjs';
export { activeTracks, enabledTracks, visibleTracks, currentSoundType, layerOf, variantsOf, addLayer, assignVariant, normalizeWorkbench, newCombination, MAX_LAYERS, MAX_VARIANTS } from './workbench-model.mjs';
export const MAX_TRACKS = MAX_STORED_TRACKS;
export const MAX_BANDS = 24;
export const COLORS = ['#98b8ef', '#ad9ce3', '#8bc7b1', '#ddb17b', '#d88eab', '#7fbecb', '#bcbd87', '#b1a5df'];
export const CENTERS = [31, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000];
export const uid = () => globalThis.crypto.randomUUID();
export const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
export const dbToGain = db => 10 ** (db / 20);
export const gainToDb = value => value > 0 ? 20 * Math.log10(value) : -100;
export const cleanName = name => String(name).replace(/\.(wav|mp3|ogg)$/i, '');
export function defaultBands() { return CENTERS.map(frequency => ({ id: uid(), type: 'peaking', frequency, gain: 0, q: 0.707, enabled: true })); }
export function createProject() {
  return { schemaVersion: 3, id: uid(), name: 'Новый проект', sampleRate: 48000, masterGain: -6, limiter: defaultLimiter(), assets: [], tracks: [], soundTypes: createSoundTypes(), activeSoundTypeId: 'gunshots' };
}
export function createTrack(index = 0, name) {
  return { id: uid(), name: name || `Дорожка ${index + 1}`, color: COLORS[index % COLORS.length], volume: 0, pan: 0, muted: false, solo: false, export: true, eqEnabled: true, bands: defaultBands(), fx: defaultTrackFx(), clips: [] };
}
export function createClip(asset, start = 0) {
  return { id: uid(), assetId: asset.id, sourceAssetId: asset.id, speed: 1, name: cleanName(asset.name), start: Math.max(0, start), offset: 0, duration: asset.duration, gain: 0, fadeIn: Math.min(0.002, asset.duration / 2), fadeOut: Math.min(0.004, asset.duration / 2) };
}
export function trackEnd(track) { return Math.max(0, ...track.clips.map(clip => clip.start + clip.duration)); }
export function trackStart(track) { return track.clips.length ? Math.min(...track.clips.map(clip => clip.start)) : 0; }
export function projectEnd(project) { return Math.max(0, ...enabledTracks(project).map(trackEnd)); }
export function audibleTracks(project, onlyTrackId = null) {
  if (onlyTrackId) return project.tracks.filter(track => track.id === onlyTrackId);
  const tracks = enabledTracks(project), solo = tracks.some(track => track.solo);
  return tracks.filter(track => !track.muted && (!solo || track.solo));
}
export function splitClip(track, clipId, position) {
  const index = track.clips.findIndex(clip => clip.id === clipId);
  if (index === -1) return null;
  const clip = track.clips[index];
  const delta = position - clip.start;
  if (delta < 0.0001 || delta > clip.duration - 0.0001) return null;
  const right = { ...clip, id: uid(), start: position, offset: clip.offset + delta, duration: clip.duration - delta, fadeIn: 0, fadeOut: Math.min(clip.fadeOut, clip.duration - delta) };
  clip.duration = delta;
  clip.fadeIn = Math.min(clip.fadeIn, delta);
  clip.fadeOut = 0;
  track.clips.splice(index + 1, 0, right);
  return right;
}
export function trimLeft(clip, start, sourceDuration) {
  const bounded = clamp(start, Math.max(0, clip.start - clip.offset), clip.start + clip.duration - 0.001);
  const delta = bounded - clip.start;
  clip.start = bounded;
  clip.offset = clamp(clip.offset + delta, 0, sourceDuration);
  clip.duration -= delta;
  clip.fadeIn = Math.min(clip.fadeIn, clip.duration / 2);
  clip.fadeOut = Math.min(clip.fadeOut, clip.duration / 2);
}
export function trimRight(clip, end, sourceDuration) {
  const bounded = clamp(end, clip.start + 0.001, clip.start + sourceDuration - clip.offset);
  clip.duration = bounded - clip.start;
  clip.fadeIn = Math.min(clip.fadeIn, clip.duration / 2);
  clip.fadeOut = Math.min(clip.fadeOut, clip.duration / 2);
}
export function selectionBounds(selection) {
  if (!selection || !Number.isFinite(selection.start) || !Number.isFinite(selection.end) || selection.end - selection.start < 0.001) return null;
  return { start: Math.max(0, selection.start), end: Math.max(0, selection.end) };
}
function finite(value, min, max, label) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max) throw new Error(`Некорректное значение: ${label}.`);
  return value;
}
export function validateBands(bands) {
  if (!Array.isArray(bands) || !bands.length || bands.length > MAX_BANDS) throw new Error(`В эквалайзере должно быть от 1 до ${MAX_BANDS} полос.`);
  return bands.map((band, index) => {
    if (!band || typeof band !== 'object') throw new Error(`Некорректная полоса ${index + 1}.`);
    const type = band.type || 'peaking';
    if (!['peaking', 'lowshelf', 'highshelf', 'lowpass', 'highpass'].includes(type)) throw new Error(`Неизвестный тип фильтра: ${type}.`);
    return { id: uid(), type, frequency: finite(Number(band.frequency ?? band.freq ?? band.hz), 20, 20000, `частота полосы ${index + 1}`), gain: finite(Number(band.gain ?? band.gain_db ?? 0), -24, 24, `усиление полосы ${index + 1}`), q: finite(Number(band.q ?? band.Q ?? 0.707), 0.1, 18, `ширина Q полосы ${index + 1}`), enabled: band.enabled !== false };
  });
}
export function parsePreset(text) {
  const input = text.replace(/^\uFEFF/, '').trim();
  if (!input) throw new Error('Файл настроек пуст.');
  if (/^[\[{]/.test(input)) {
    let data;
    try { data = JSON.parse(input); } catch { throw new Error('Ошибка синтаксиса JSON. Проверьте запятые и кавычки.'); }
    return { name: data.name || 'Из файла', bands: validateBands(Array.isArray(data) ? data : data.bands) };
  }
  const rows = input.split(/\r?\n/).map(row => row.trim()).filter(row => row && !row.startsWith('#'));
  if (!rows.length) throw new Error('В файле нет значений частот.');
  const delimiter = rows[0].includes(';') ? ';' : rows[0].includes('\t') ? '\t' : ',';
  const cells = rows.map(row => row.split(delimiter).map(cell => cell.trim().replace(/^"|"$/g, '')));
  let headers = ['frequency', 'gain', 'q', 'type'];
  if (/[a-zа-я]/i.test(cells[0][0])) {
    headers = cells.shift().map(header => ({ frequency: 'frequency', freq: 'frequency', hz: 'frequency', frequency_hz: 'frequency', частота: 'frequency', 'частота_гц': 'frequency', gain: 'gain', gain_db: 'gain', усиление: 'gain', q: 'q', ширина: 'q', type: 'type', тип: 'type' })[header.toLowerCase()] || header.toLowerCase());
  }
  const bands = cells.map(row => Object.fromEntries(headers.map((header, i) => [header, header === 'type' ? (row[i] || 'peaking') : Number(String(row[i] ?? (header === 'q' ? '0.707' : '0')).replace(',', '.'))])));
  return { name: 'Из файла', bands: validateBands(bands) };
}
export function serializePreset(track) { return JSON.stringify({ name: track.name, version: 1, bands: track.bands.map(({ type, frequency, gain, q, enabled }) => ({ type, frequency, gain, q, enabled })) }, null, 2); }
export function validateProject(input) {
  if (!input || ![1, 2, 3].includes(input.schemaVersion)) throw new Error('Неподдерживаемая версия проекта.');
  if (!Array.isArray(input.tracks) || input.tracks.length > (input.schemaVersion === 1 ? 50 : MAX_TRACKS) || !Array.isArray(input.assets) || input.assets.length > 2000) throw new Error('Некорректное число дорожек или звуков.');
  const project = structuredClone(input);
  project.name = String(project.name || 'Проект').slice(0, 200);
  project.limiter = validateLimiter(project.limiter);
  finite(project.masterGain, -60, 12, 'громкость мастера');
  finite(project.sampleRate, 8000, 192000, 'частота дискретизации');
  const ids = new Set();
  const checkId = id => { if (!/^[a-zA-Z0-9_-]{1,80}$/.test(id) || ids.has(id)) throw new Error('Повторяющийся или некорректный идентификатор.'); ids.add(id); };
  const assets = new Map();
  for (const asset of project.assets) {
    checkId(asset.id); asset.name = String(asset.name).slice(0, 250);
    finite(asset.duration, 0.00001, 7200, 'длительность исходника'); assets.set(asset.id, asset);
  }
  for (const track of project.tracks) {
    checkId(track.id); track.name = String(track.name || 'Дорожка').slice(0, 200);
    if (track.decompositionGroup !== undefined) {
      if (typeof track.decompositionGroup !== 'string' || !/^[a-zA-Z0-9_-]{1,80}$/.test(track.decompositionGroup)) throw new Error('Некорректная группа разложения.');
      finite(track.decompositionOnset, 0, 7200, 'начало разложенного выстрела');
    }
    if (!/^#[\da-f]{6}$/i.test(track.color)) track.color = COLORS[0];
    finite(track.volume, -60, 12, 'громкость дорожки'); finite(track.pan, -1, 1, 'панорама');
    track.bands = validateBands(track.bands);
    track.fx = validateTrackFx(track.fx);
    track.muted = !!track.muted; track.solo = !!track.solo; track.export = track.export !== false; track.eqEnabled = track.eqEnabled !== false;
    if (!Array.isArray(track.clips) || track.clips.length > 10000) throw new Error('Некорректное число фрагментов.');
    for (const clip of track.clips) {
      checkId(clip.id); const asset = assets.get(clip.assetId);
      if (!asset) throw new Error('Фрагмент ссылается на отсутствующий звук.');
      clip.sourceAssetId ??= clip.assetId;
      if (!assets.has(clip.sourceAssetId)) throw new Error('Исходник ускоренного фрагмента отсутствует.');
      clip.speed = finite(clip.speed ?? 1, 0.25, 8, 'скорость фрагмента');
      clip.name = String(clip.name || asset.name).slice(0, 200);
      finite(clip.start, 0, 7200, 'позиция фрагмента'); finite(clip.offset, 0, asset.duration, 'начало исходника'); finite(clip.duration, 0.00001, asset.duration + 0.001, 'длительность фрагмента');
      if (clip.offset + clip.duration > asset.duration + 0.002) throw new Error('Фрагмент выходит за границы исходника.');
      finite(clip.gain, -60, 24, 'усиление фрагмента'); finite(clip.fadeIn, 0, clip.duration + 0.001, 'нарастание'); finite(clip.fadeOut, 0, clip.duration + 0.001, 'затухание');
    }
  }
  if (input.schemaVersion < 3) normalizeWorkbench(project);
  validateWorkbench(project, checkId);
  return project;
}
export class History {
  constructor(limit = 80) { this.limit = limit; this.past = []; this.future = []; }
  push(project) { this.past.push(structuredClone(project)); if (this.past.length > this.limit) this.past.shift(); this.future = []; }
  undo(project) { if (!this.past.length) return null; this.future.push(structuredClone(project)); return this.past.pop(); }
  redo(project) { if (!this.future.length) return null; this.past.push(structuredClone(project)); return this.future.pop(); }
  clear() { this.past = []; this.future = []; }
}
