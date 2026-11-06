import { shotTail } from './shot-model.mjs';
export const defaultCompressor = () => ({enabled:false,threshold:-20,ratio:3,attack:12,release:120,knee:6,makeup:0,mix:1});
export const defaultTrackFx = () => ({ tone: { enabled: true, low: 0, mid: 0, high: 0, frequency: 1000 }, reverb: { enabled: false, wet: .2, decay: 1.2, preDelay: 18, damping: 6500, size: .5 }, compressor:defaultCompressor() });
export const defaultLimiter = () => ({ enabled: false, drive: 0, ceiling: -1, release: 90 });
function checked(value, fallback, min, max, name) {
  if (value === undefined) return fallback;
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max) throw new Error(`Некорректный параметр эффекта: ${name}.`);
  return value;
}
export function validateTrackFx(input) {
  if (input !== undefined && (!input || typeof input !== 'object')) throw new Error('Некорректные эффекты дорожки.');
  const defaults = defaultTrackFx(), tone = input?.tone || {}, reverb = input?.reverb || {}, comp=input?.compressor||{};
  return {
    tone: { enabled: tone.enabled !== false, low: checked(tone.low, 0, -18, 18, 'НЧ'), mid: checked(tone.mid, 0, -18, 18, 'СЧ'), high: checked(tone.high, 0, -18, 18, 'ВЧ'), frequency: checked(tone.frequency, 1000, 200, 5000, 'частота середины') },
    reverb: { enabled: reverb.enabled === true, wet: checked(reverb.wet, defaults.reverb.wet, 0, 1, 'доля реверберации'), decay: checked(reverb.decay, 1.2, .15, 6, 'затухание'), preDelay: checked(reverb.preDelay, 18, 0, 150, 'задержка'), damping: checked(reverb.damping, 6500, 500, 18000, 'тембр реверберации'), size: checked(reverb.size, .5, 0, 1, 'пространство') },
    compressor:{enabled:comp.enabled===true,threshold:checked(comp.threshold,-20,-60,0,'порог компрессора'),ratio:checked(comp.ratio,3,1,20,'степень сжатия'),attack:checked(comp.attack,12,.1,100,'атака компрессора'),release:checked(comp.release,120,10,1500,'восстановление компрессора'),knee:checked(comp.knee,6,0,24,'колено'),makeup:checked(comp.makeup,0,-12,24,'компенсация усиления'),mix:checked(comp.mix,1,0,1,'доля компрессии')}
  };
}
export function validateLimiter(input) {
  if (input !== undefined && (!input || typeof input !== 'object')) throw new Error('Некорректные настройки лимитера.');
  return { enabled: input?.enabled === true, drive: checked(input?.drive, 0, 0, 24, 'усиление лимитера'), ceiling: checked(input?.ceiling, -1, -18, 0, 'потолок'), release: checked(input?.release, 90, 10, 600, 'восстановление') };
}
export function reverbTail(project, ids = null, { includeDesign = true } = {}) {
  return Math.max(0, ...project.tracks.filter(track => !ids || ids.includes(track.id)).map(track => track.fx?.reverb?.enabled && track.fx.reverb.wet > 0 ? track.fx.reverb.decay + track.fx.reverb.preDelay / 1000 : 0)) + (includeDesign ? shotTail(project) : 0);
}
