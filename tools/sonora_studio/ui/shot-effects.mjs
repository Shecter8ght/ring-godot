import { createTrackEffects } from './effects.mjs';
import { defaultTrackFx } from './fx-model.mjs';
import { spacePresets, defaultShotDesign } from './shot-model.mjs';

function set(parameter, value, context) {
  if (context instanceof AudioContext) parameter.setTargetAtTime(value, context.currentTime, .015);
  else parameter.setValueAtTime(value, context.currentTime);
}
function spaceImpulse(context, preset, size) {
  const frames = Math.ceil(context.sampleRate * preset.decay * size), buffer = context.createBuffer(2, Math.max(1, frames), context.sampleRate);
  for (let c = 0; c < 2; c++) {
    const data = buffer.getChannelData(c); let seed = 17771 + c * 5323, energy = 0;
    if (preset.dense) for (let i = 0; i < frames; i++) {
      seed = (Math.imul(seed, 1664525) + 1013904223) | 0;
      const time = i / context.sampleRate, decay = preset.decay * size;
      data[i] = ((seed >>> 0) / 2147483648 - 1) * Math.exp(-6.9078 * time / decay) * Math.min(1, time / .012);
      energy += data[i] ** 2;
    }
    if (energy) { const scale = .36 / Math.sqrt(energy); for (let i = 0; i < frames; i++) data[i] *= scale; }
    for (const [seconds, level] of preset.early) {
      const i = Math.round((seconds * size + c * .0014) * context.sampleRate);
      if (i < frames) data[i] += level;
    }
  }
  return buffer;
}
// The direct path stays at unity. Reflections are parallel, after the complete layer mix.
export function createShotEffects(context, destination, initial = defaultShotDesign()) {
  const input = context.createGain(), normal = context.createGain(), quiet = context.createGain(), styled = context.createGain(), output = context.createGain();
  input.connect(normal); normal.connect(styled);
  const softened = createTrackEffects(context, quiet, { ...defaultTrackFx(), tone: { enabled: true, low: 2.8, mid: -4.5, high: -12, frequency: 2600 }, compressor: { enabled: true, threshold: -16, ratio: 2.4, attack: .7, release: 55, knee: 6, makeup: 0, mix: .6 }, reverb: { ...defaultTrackFx().reverb, enabled: false } });
  const cutoff = context.createBiquadFilter(); cutoff.type = 'lowpass'; cutoff.frequency.value = 6800; cutoff.Q.value = -.5;
  input.connect(cutoff); cutoff.connect(softened.input); quiet.connect(styled);
  styled.connect(output); output.connect(destination);
  const delay = context.createDelay(.3), damping = context.createBiquadFilter(), wet = context.createGain();
  damping.type = 'lowpass'; damping.Q.value = -.5; styled.connect(delay); damping.connect(wet); wet.connect(output);
  let current = null, key = '', retired = [];
  function sync(design = defaultShotDesign()) {
    const preset = spacePresets[design.environment], suppression = design.enabled && design.suppressed ? design.suppression : 0;
    set(normal.gain, 1 - suppression, context); set(quiet.gain, suppression * 10 ** (-3 / 20), context);
    set(output.gain, design.enabled ? 10 ** (design.output / 20) : 1, context);
    set(wet.gain, design.enabled ? preset.wet * design.amount : 0, context);
    set(delay.delayTime, preset.preDelay * design.size, context); set(damping.frequency, preset.damping, context);
    const nextKey = `${design.environment}:${design.size.toFixed(3)}`;
    if (preset.wet && design.enabled && nextKey !== key) {
      const node = context.createConvolver(), gain = context.createGain(); node.normalize = false; node.buffer = spaceImpulse(context, preset, design.size);
      gain.gain.value = current && context instanceof AudioContext ? 0 : 1;
      delay.connect(node); node.connect(gain); gain.connect(damping);
      if (current) {
        const old = current;
        if (context instanceof AudioContext) {
          gain.gain.linearRampToValueAtTime(1, context.currentTime + .05); old.gain.gain.cancelScheduledValues(context.currentTime); old.gain.gain.setValueAtTime(old.gain.gain.value, context.currentTime); old.gain.gain.linearRampToValueAtTime(0, context.currentTime + .05);
          old.timer = setTimeout(() => { try { delay.disconnect(old.node); } catch {} old.node.disconnect(); old.gain.disconnect(); retired = retired.filter(item => item !== old); }, 120); retired.push(old);
        } else { delay.disconnect(old.node); old.node.disconnect(); old.gain.disconnect(); }
      }
      current = { node, gain }; key = nextKey;
    }
  }
  sync(initial);
  return { input, sync, destroy() {
    softened.destroy();
    for (const entry of [current, ...retired].filter(Boolean)) { clearTimeout(entry.timer); entry.node.disconnect(); entry.gain.disconnect(); }
    for (const node of [input, normal, quiet, styled, output, cutoff, delay, damping, wet]) node.disconnect();
  } };
}
