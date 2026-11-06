import { uid, cleanName, dbToGain, clamp, audibleTracks, activeTracks, projectEnd } from './model.mjs';
import { loadEffects, createTrackEffects, createLimiter, limiterLatency } from './effects.mjs';
import { reverbTail } from './fx-model.mjs';
import { createShotEffects } from './shot-effects.mjs';
import { currentShotDesign } from './shot-model.mjs';

function filterQ(band) { return ['lowpass', 'highpass'].includes(band.type) ? 20 * Math.log10(band.q) : band.q; }
function activeBands(track) { return track.eqEnabled ? track.bands.filter(band => band.enabled) : []; }
function graphSignature(track) { return activeBands(track).map(band => `${band.id}:${band.type}`).join('|'); }
function makeTrackGraph(context, track, destination, raw = false) {
  const input = context.createGain();
  let last = input;
  const filters = [];
  if (!raw) for (const band of activeBands(track)) {
    const filter = context.createBiquadFilter();
    filter.type = band.type;
    filter.frequency.value = Math.min(band.frequency, context.sampleRate / 2 - 1);
    filter.gain.value = band.gain;
    filter.Q.value = filterQ(band);
    last.connect(filter); last = filter; filters.push(filter);
  }
  const analyser = context.createAnalyser();
  analyser.fftSize = 2048; analyser.smoothingTimeConstant = 0.8;
  const volume = context.createGain(); volume.gain.value = raw ? 1 : dbToGain(track.volume);
  const pan = context.createStereoPanner(); pan.pan.value = raw ? 0 : track.pan;
  const effects = raw ? null : createTrackEffects(context, analyser, track.fx);
  last.connect(effects?.input || analyser); analyser.connect(volume); volume.connect(pan); pan.connect(destination);
  return { input, filters, effects, analyser, volume, pan, signature: graphSignature(track), destroy() { effects?.destroy(); for (const node of [input, ...filters, analyser, volume, pan]) node.disconnect(); } };
}
function envelopeAt(clip, local) {
  return Math.max(0, Math.min(1, clip.fadeIn > 0 ? local / clip.fadeIn : 1, clip.fadeOut > 0 ? (clip.duration - local) / clip.fadeOut : 1));
}
function scheduleClip(context, clip, buffer, input, when, from, to, collection) {
  const begin = Math.max(clip.start, from);
  const end = Math.min(clip.start + clip.duration, to);
  if (end - begin < 1 / context.sampleRate) return;
  const source = context.createBufferSource(); source.buffer = buffer;
  const gain = context.createGain();
  const localStart = begin - clip.start;
  const localEnd = end - clip.start;
  const startTime = when + begin - from;
  const level = dbToGain(clip.gain);
  gain.gain.setValueAtTime(level * envelopeAt(clip, localStart), startTime);
  const points = [clip.fadeIn, clip.duration - clip.fadeOut, localEnd];
  if (clip.fadeIn + clip.fadeOut > clip.duration) points.push(clip.duration * clip.fadeIn / (clip.fadeIn + clip.fadeOut));
  for (const point of [...new Set(points)].sort((a, b) => a - b)) {
    if (point > localStart && point <= localEnd) gain.gain.linearRampToValueAtTime(level * envelopeAt(clip, point), startTime + point - localStart);
  }
  source.connect(gain); gain.connect(input);
  if (collection) {
    collection.add(source);
    source.onended = () => { collection.delete(source); source.disconnect(); gain.disconnect(); };
  }
  source.start(startTime, Math.max(0, clip.offset + localStart), Math.min(end - begin, buffer.duration - clip.offset - localStart));
}

export function makePeaks(buffer, buckets = 12000) {
  const count = Math.min(buffer.length, buckets);
  const min = new Float32Array(count), max = new Float32Array(count);
  const channels = Array.from({ length: buffer.numberOfChannels }, (_, c) => buffer.getChannelData(c));
  for (let i = 0; i < count; i++) {
    let lo = 0, hi = 0;
    const start = Math.floor(i * buffer.length / count), end = Math.floor((i + 1) * buffer.length / count);
    for (let sample = start; sample < end; sample++) {
      for (const data of channels) { lo = Math.min(lo, data[sample]); hi = Math.max(hi, data[sample]); }
    }
    min[i] = lo; max[i] = hi;
  }
  return { min, max, count };
}

export class AudioEngine {
  constructor(getProject, onEnded) {
    this.getProject = getProject; this.onEnded = onEnded;
    this.assets = new Map(); this.context = null; this.playing = false;
    this.sources = new Set(); this.graphs = new Map(); this.lastPosition = 0;
    this.onlyTrackId = null; this.loopRange = null; this.end = 0;
    this.masterData = new Float32Array(1024);
  }
  async ensureContext() {
    if (!this.context) this.context = new AudioContext({ sampleRate: 48000, latencyHint: 'interactive' });
    await loadEffects(this.context);
    if (this.context.state === 'suspended') await this.context.resume();
    return this.context;
  }
  async decode(name, bytes, id = uid()) {
    const context = await this.ensureContext();
    const data = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
    let buffer;
    try { buffer = await context.decodeAudioData(data.slice().buffer); }
    catch {
      const wav = await window.sonora.decodeAudio(data, name.split('.').pop().toLowerCase());
      buffer = await context.decodeAudioData(new Uint8Array(wav).buffer);
    }
    if (!buffer.length || buffer.duration > 7200) throw new Error(`Звук «${name}» пуст или длиннее двух часов.`);
    const asset = { id, name, duration: buffer.duration, sampleRate: buffer.sampleRate, channels: buffer.numberOfChannels, bytes: data, buffer, peaks: makePeaks(buffer) };
    this.assets.set(id, asset);
    return asset;
  }
  async addBuffer(name, buffer) {
    return this.decode(name, encodeWav(buffer));
  }
  position() {
    if (!this.playing) return this.lastPosition;
    const elapsed = Math.max(0, this.context.currentTime - this.anchorTime - limiterLatency(this.context.sampleRate) / this.context.sampleRate);
    const firstDuration = this.end - this.anchorPosition;
    if (this.loopRange && elapsed >= firstDuration) return this.loopRange.start + (elapsed - firstDuration) % (this.loopRange.end - this.loopRange.start);
    return Math.min(this.end, this.anchorPosition + elapsed);
  }
  async play({ start = 0, onlyTrackId = null, loopRange = null, end } = {}) {
    const context = await this.ensureContext();
    this.stop(false);
    const project = this.getProject();
    this.onlyTrackId = onlyTrackId;
    this.loopRange = loopRange && loopRange.end - loopRange.start >= 0.005 ? { ...loopRange } : null;
    this.end = this.loopRange ? this.loopRange.end : (end ?? projectEnd(project));
    if (this.end <= 0.0001) return false;
    if (this.loopRange && (start < this.loopRange.start || start >= this.loopRange.end)) start = this.loopRange.start;
    if (start >= this.end) start = this.loopRange?.start || 0;
    this.master = context.createGain(); this.master.gain.value = dbToGain(project.masterGain);
    this.masterAnalyser = context.createAnalyser(); this.masterAnalyser.fftSize = 1024;
    this.limiter = createLimiter(context, this.masterAnalyser, project.limiter);
    this.master.connect(this.limiter.input); this.masterAnalyser.connect(context.destination);
    this.shotEffects = createShotEffects(context, this.master, currentShotDesign(project));
    for (const track of activeTracks(project)) this.graphs.set(track.id, makeTrackGraph(context, track, this.shotEffects.input));
    this.anchorTime = context.currentTime + 0.035;
    this.anchorPosition = Math.max(0, start);
    this.nextSegment = { when: this.anchorTime, from: this.anchorPosition, to: this.end };
    this.playing = true;
    this.sync(project);
    this.schedule();
    this.timer = setInterval(() => this.schedule(), 25);
    return true;
  }
  schedule() {
    if (!this.playing) return;
    const project = this.getProject();
    const now = this.context.currentTime;
    let count = 0;
    while (this.nextSegment && this.nextSegment.when < now + 0.22 && count++ < 100) {
      const segment = this.nextSegment;
      for (const track of activeTracks(project)) {
        const graph = this.graphs.get(track.id);
        if (!graph) continue;
        for (const clip of track.clips) {
          const asset = this.assets.get(clip.assetId);
          if (asset) scheduleClip(this.context, clip, asset.buffer, graph.input, segment.when, segment.from, segment.to, this.sources);
        }
      }
      const nextTime = segment.when + segment.to - segment.from;
      this.finishTime = nextTime;
      this.nextSegment = this.loopRange ? { when: nextTime, from: this.loopRange.start, to: this.loopRange.end } : null;
    }
    const tail = reverbTail(project, audibleTracks(project, this.onlyTrackId).map(track => track.id));
    if (!this.loopRange && !this.nextSegment && now >= this.finishTime + tail + limiterLatency(this.context.sampleRate) / this.context.sampleRate) {
      this.lastPosition = this.end;
      this.stop(false);
      this.onEnded?.();
    }
  }
  sync(project = this.getProject()) {
    if (!this.playing) return;
    const now = this.context.currentTime;
    const audible = new Set(audibleTracks(project, this.onlyTrackId).map(track => track.id));
    const tracks = activeTracks(project);
    if (tracks.length !== this.graphs.size || tracks.some(track => this.graphs.get(track.id)?.signature !== graphSignature(track))) { this.restart(); return; }
    this.master.gain.setTargetAtTime(dbToGain(project.masterGain), now, 0.012);
    this.limiter.sync(project.limiter);
    this.shotEffects.sync(currentShotDesign(project));
    for (const track of tracks) {
      const graph = this.graphs.get(track.id);
      graph.volume.gain.setTargetAtTime(audible.has(track.id) ? dbToGain(track.volume) : 0, now, 0.012);
      graph.pan.pan.setTargetAtTime(track.pan, now, 0.012);
      graph.effects.sync(track.fx);
      activeBands(track).forEach((band, index) => {
        const filter = graph.filters[index];
        filter.frequency.setTargetAtTime(Math.min(band.frequency, this.context.sampleRate / 2 - 1), now, 0.012);
        filter.gain.setTargetAtTime(band.gain, now, 0.012);
        filter.Q.setTargetAtTime(filterQ(band), now, 0.012);
      });
    }
  }
  restart() {
    if (!this.playing) return;
    const options = { start: this.position(), onlyTrackId: this.onlyTrackId, loopRange: this.loopRange, end: this.end };
    this.play(options).catch(error => console.error(error));
  }
  pause() { this.lastPosition = this.position(); this.stop(false); return this.lastPosition; }
  stop(reset = true) {
    clearInterval(this.timer); this.playing = false;
    for (const source of this.sources) { try { source.stop(); } catch {} source.disconnect(); }
    this.sources.clear();
    for (const graph of this.graphs.values()) graph.destroy();
    this.graphs.clear(); this.shotEffects?.destroy(); this.shotEffects = null; this.master?.disconnect(); this.limiter?.destroy(); this.limiter = null; this.masterAnalyser?.disconnect();
    if (reset) this.lastPosition = 0;
  }
  meter() {
    if (!this.playing || !this.masterAnalyser) return 0;
    this.masterAnalyser.getFloatTimeDomainData(this.masterData);
    let peak = 0;
    for (const value of this.masterData) peak = Math.max(peak, Math.abs(value));
    return peak;
  }
  spectrum(trackId, data) {
    const analyser = this.graphs.get(trackId)?.analyser;
    if (!analyser) return false;
    analyser.getByteFrequencyData(data); return true;
  }
  response(track, frequencies) {
    const context = this.context;
    if (!context) return new Float32Array(frequencies.length).fill(0);
    const sum = new Float32Array(frequencies.length), phase = new Float32Array(frequencies.length), magnitude = new Float32Array(frequencies.length);
    const tone = track.fx?.tone;
    const bands = [...activeBands(track), ...(tone?.enabled ? [{type:'lowshelf',frequency:120,gain:tone.low,q:.707},{type:'peaking',frequency:tone.frequency,gain:tone.mid,q:.707},{type:'highshelf',frequency:6000,gain:tone.high,q:.707}] : [])];
    for (const band of bands) {
      const filter = context.createBiquadFilter(); filter.type = band.type;
      filter.frequency.value = Math.min(band.frequency, context.sampleRate / 2 - 1); filter.gain.value = band.gain; filter.Q.value = filterQ(band);
      filter.getFrequencyResponse(frequencies, magnitude, phase);
      for (let i = 0; i < sum.length; i++) sum[i] += 20 * Math.log10(Math.max(1e-8, magnitude[i]));
    }
    return sum;
  }
}

export async function renderAudio(project, assets, trackIds, range, { sampleRate = 48000, raw = false, includeTail = true, includeDesign = true, includeMaster = true } = {}) {
  const duration = range.end - range.start;
  if (!(duration > 0) || duration > 600) throw new Error('Для одного экспорта выберите диапазон от 1 мс до 10 минут.');
  const latency = raw || !includeMaster ? 0 : limiterLatency(sampleRate);
  const frames = Math.max(1, Math.round((duration + (!raw && includeTail ? reverbTail(project, trackIds, { includeDesign }) : 0)) * sampleRate));
  const context = new OfflineAudioContext(2, frames + latency, sampleRate);
  const master = context.createGain(); master.gain.value = raw || !includeMaster ? 1 : dbToGain(project.masterGain);
  let limiter;
  if (raw || !includeMaster) { if (!raw) await loadEffects(context); master.connect(context.destination); }
  else { await loadEffects(context); limiter = createLimiter(context, context.destination, project.limiter); master.connect(limiter.input); }
  const shotEffects = !raw && includeDesign ? createShotEffects(context, master, currentShotDesign(project)) : null;
  for (const track of project.tracks.filter(track => trackIds.includes(track.id))) {
    const graph = makeTrackGraph(context, track, shotEffects?.input || master, raw);
    for (const clip of track.clips) {
      const asset = assets.get(clip.assetId);
      if (asset) scheduleClip(context, clip, asset.buffer, graph.input, 0, range.start, range.end);
    }
  }
  const rendered = await context.startRendering();
  shotEffects?.destroy();
  limiter?.destroy();
  if (!latency) return rendered;
  const aligned = new AudioBuffer({ numberOfChannels: 2, length: frames, sampleRate });
  for (let channel = 0; channel < 2; channel++) aligned.copyToChannel(rendered.getChannelData(channel).subarray(latency, latency + frames), channel);
  return aligned;
}
export function peakOf(buffer) {
  let peak = 0;
  for (let c = 0; c < buffer.numberOfChannels; c++) for (const sample of buffer.getChannelData(c)) peak = Math.max(peak, Math.abs(sample));
  return peak;
}
export function encodeWav(buffer, protect = false) {
  const channels = Math.min(2, buffer.numberOfChannels), samples = buffer.length;
  const bytes = new ArrayBuffer(44 + samples * channels * 4), view = new DataView(bytes);
  const text = (offset, value) => { for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i)); };
  text(0, 'RIFF'); view.setUint32(4, bytes.byteLength - 8, true); text(8, 'WAVE'); text(12, 'fmt '); view.setUint32(16, 16, true);
  view.setUint16(20, 3, true); view.setUint16(22, channels, true); view.setUint32(24, buffer.sampleRate, true); view.setUint32(28, buffer.sampleRate * channels * 4, true); view.setUint16(32, channels * 4, true); view.setUint16(34, 32, true);
  text(36, 'data'); view.setUint32(40, samples * channels * 4, true);
  const peak = protect ? peakOf(buffer) : 0;
  const scale = peak > 0.988553 ? 0.988553 / peak : 1;
  const data = Array.from({ length: channels }, (_, c) => buffer.getChannelData(c));
  let offset = 44;
  for (let i = 0; i < samples; i++) for (let c = 0; c < channels; c++, offset += 4) view.setFloat32(offset, data[c][i] * scale, true);
  return new Uint8Array(bytes);
}

// A small original, deterministic demo made from noise and oscillators; no bundled media.
export async function createDemo(engine) {
  const context = await engine.ensureContext();
  const definitions = [
    ['01_Удар.wav', 1.35, 'body'], ['02_Механика.wav', 0.7, 'click'], ['03_Хвост.wav', 2.7, 'tail']
  ];
  const result = [];
  let seed = 90871;
  const noise = () => { seed = (Math.imul(seed, 1664525) + 1013904223) | 0; return ((seed >>> 0) / 4294967296) * 2 - 1; };
  for (const [name, duration, type] of definitions) {
    const buffer = context.createBuffer(2, Math.round(context.sampleRate * duration), context.sampleRate);
    for (let c = 0; c < 2; c++) {
      const data = buffer.getChannelData(c); let smooth = 0;
      for (let i = 0; i < data.length; i++) {
        const t = i / context.sampleRate, random = noise(); smooth += 0.055 * (random - smooth);
        const envelope = Math.min(1, t * 1500);
        data[i] = type === 'body'
          ? envelope * (Math.sin(2 * Math.PI * (74 * t + 19 * (1 - Math.exp(-t * 18)))) * Math.exp(-t * 9) * 0.58 + smooth * Math.exp(-t * 12) * 1.8 + random * Math.exp(-t * 140) * 0.4)
          : type === 'click'
            ? envelope * (random * Math.exp(-t * 100) * 0.4 + Math.sin(2 * Math.PI * 1900 * t) * Math.exp(-t * 65) * 0.16 + (t > 0.14 ? random * Math.exp(-(t - 0.14) * 95) * 0.16 : 0))
            : envelope * (smooth * Math.exp(-t * 2.8) * 0.75 + Math.sin(2 * Math.PI * 121 * t) * Math.exp(-t * 5) * 0.035);
      }
    }
    result.push(await engine.addBuffer(name, buffer));
  }
  return result;
}
