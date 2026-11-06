const clamp = (x, min, max) => Math.min(max, Math.max(min, x));
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
export function analyzeShot(channels, rate) {
  if (!channels.length || !channels[0].length) throw new Error('Звук пуст.');
  const frames = channels[0].length, window = Math.max(1, Math.round(rate * .001));
  let peak = 0, peakIndex = 0, energy = 0;
  const envelope = [];
  for (let start = 0; start < frames; start += window) {
    const end = Math.min(frames, start + window); let sum = 0;
    for (let i = start; i < end; i++) {
      let square = 0;
      for (const channel of channels) { const sample = channel[i]; if (!Number.isFinite(sample)) throw new Error('Некорректные отсчёты аудио.'); if (Math.abs(sample) > peak) { peak = Math.abs(sample); peakIndex = i; } square = Math.max(square, sample * sample); }
      sum += square;
    }
    energy += sum; envelope.push(Math.sqrt(sum / (end - start)));
  }
  if (peak < 1e-7) throw new Error('Исходник почти бесшумный. Выберите запись с отчётливым звуком.');
  const top = envelope.reduce((maximum, level) => Math.max(maximum, level), 0), threshold = top * .035;
  const first = envelope.findIndex(level => level > threshold);
  let last = envelope.length - 1; while (last > first && envelope[last] <= threshold) last--;
  const onset = first * window / rate, peakTime = peakIndex / rate;
  let bodyEnd = onset + .1;
  for (let i = Math.ceil((Math.max(onset + .04, peakTime + .012)) * rate / window); i < envelope.length - 5; i++) {
    if (envelope.slice(i, i + 5).every(level => level < top * .22)) { bodyEnd = i * window / rate; break; }
  }
  bodyEnd = clamp(bodyEnd, onset + .055, onset + .16);
  return { peak, peakDb: 20 * Math.log10(peak), rms: Math.sqrt(energy / frames), onset, end: Math.min(frames / rate, (last + 1) * window / rate), activeDuration: (last - first + 1) * window / rate, peakTime, bodyEnd, duration: frames / rate };
}
function lowpass(input, rate, frequency) {
  const alpha = 1 - Math.exp(-2 * Math.PI * frequency / rate), output = Float64Array.from(input);
  // Complementary subtraction below keeps the sum equal to the source, including phase.
  for (let pass = 0; pass < 2; pass++) {
    let value = 0; for (let i = 0; i < output.length; i++) { value += alpha * (output[i] - value); output[i] = value; }
    value = 0; for (let i = output.length - 1; i >= 0; i--) { value += alpha * (output[i] - value); output[i] = value; }
  }
  return output;
}
export function splitShot(channels, rate) {
  const analysis = analyzeShot(channels, rate), frames = channels[0].length;
  const layers = Object.fromEntries(['low','mid','high','gas','tail'].map(role => [role, channels.map(() => new Float32Array(frames))]));
  for (let c = 0; c < channels.length; c++) {
    const input = channels[c], low = lowpass(input, rate, 180), upper = Float64Array.from(input, (x, i) => x - low[i]), mid = lowpass(upper, rate, 2400);
    for (let i = 0; i < frames; i++) {
      const time = i / rate, body = 1 - smooth(analysis.bodyEnd - .022, analysis.bodyEnd + .025, time), gas = smooth(analysis.onset + .012, analysis.onset + .04, time), high = upper[i] - mid[i];
      layers.low[c][i] = low[i] * body; layers.mid[c][i] = mid[i] * body;
      layers.high[c][i] = high * body * (1 - gas); layers.gas[c][i] = high * body * gas;
      layers.tail[c][i] = input[i] * (1 - body);
    }
  }
  return { analysis, layers };
}
export const timingScenarios = {
  semi: { name: 'Полуавтоматический выстрел', offsets: { low:0, mid:0, high:0, gas:12, trigger:-32, pin:-4, boltBack:18, boltForward:68, casing:130, tail:75 } },
  fast: { name: 'Быстрая автоматика', offsets: { low:0, mid:0, high:0, gas:8, trigger:-24, pin:-3, boltBack:12, boltForward:42, casing:85, tail:60 } }
};
const targetDuration = { trigger:.035, pin:.018, boltBack:.06, boltForward:.07, casing:.14 };
const roleLevel = { low:0, mid:-2, high:-3, gas:-16, trigger:-24, pin:-22, boltBack:-18, boltForward:-20, casing:-27, tail:-15 };
export function planShot(entries, { scenario = 'semi', speed = true, balance = true } = {}) {
  const timing = timingScenarios[scenario]; if (!timing) throw new Error('Неизвестный сценарий.');
  const eligible = entries.filter(item => !item.locked && Object.hasOwn(timing.offsets, item.role));
  const primary = entries.find(item => ['low','mid','high'].includes(item.role)) || eligible[0];
  if (!primary) throw new Error('Задайте роли загруженным слоям и включите хотя бы один из них.');
  const anchor = primary.start + (primary.originOnset ?? primary.stats.onset), reference = Math.max(...entries.filter(item => ['low','mid','high'].includes(item.role)).map(item => item.stats.peakDb), primary.stats.peakDb);
  const rows = eligible.map(item => {
    const current = item.speed ?? 1, rate = speed && targetDuration[item.role] && item.speed !== null ? Math.min(8, current * Math.max(1, item.stats.activeDuration / targetDuration[item.role])) : current;
    const onset = item.originOnset ?? item.stats.onset * current / rate;
    const offset = item.originOnset === undefined ? timing.offsets[item.role] / 1000 : 0;
    const delta = anchor + offset - item.start - onset;
    const volume = balance && item.originOnset === undefined ? clamp(item.volume + reference + roleLevel[item.role] - item.stats.peakDb, -60, 12) : item.volume;
    return { ...item, rate: Number(rate.toFixed(4)), delta, volume: Number(volume.toFixed(1)), offset: offset * 1000 };
  });
  const shift = Math.max(0, ...rows.map(item => -(item.start + item.delta)));
  if (shift > .00001 && primary.locked) throw new Error('Для спуска до выстрела нужен запас в начале. Сдвиньте закреплённый основной слой вправо или снимите закрепление.');
  for (const row of rows) row.delta += shift;
  return { rows, shotAt: anchor + shift, skipped: entries.length - rows.length };
}
