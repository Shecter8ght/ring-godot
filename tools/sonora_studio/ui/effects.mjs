import { defaultTrackFx, defaultLimiter, defaultCompressor } from './fx-model.mjs';
const loaded = new WeakMap();
export function loadEffects(context) {
  if (!loaded.has(context)) loaded.set(context, Promise.all(['limiter-worklet.mjs','compressor-worklet.mjs'].map(file=>context.audioWorklet.addModule(new URL(file,import.meta.url).href))));
  return loaded.get(context);
}
export const limiterLatency = rate => Math.round(rate * .005);
function set(parameter, value, context, smooth = true) {
  if (smooth && context instanceof AudioContext) parameter.setTargetAtTime(value, context.currentTime, .012);
  else parameter.setValueAtTime(value, context.currentTime);
}
function impulse(context, decay, size) {
  const length = Math.ceil(context.sampleRate * decay), buffer = context.createBuffer(2, length, context.sampleRate);
  let seed = 17263 + Math.round(decay * 1000) + Math.round(size * 100);
  for (let channel = 0; channel < 2; channel++) {
    const data = buffer.getChannelData(channel); let energy = 0;
    for (let i = 0; i < length; i++) {
      seed = (Math.imul(seed, 1664525) + 1013904223) | 0;
      const t = i / context.sampleRate;
      data[i] = ((seed >>> 0) / 2147483648 - 1) * Math.exp(-6.9078 * t / decay) * Math.min(1, t / .008);
      energy += data[i] * data[i];
    }
    const scale = .65 / Math.sqrt(Math.max(1e-9, energy));
    for (let i = 0; i < length; i++) data[i] *= scale;
    for (const [time, gain] of [[.011,.18],[.023,.14],[.038,.1],[.057,.075],[.083,.05]]) {
      const index = Math.round((time * (.6 + size * 2) + channel * .0013) * context.sampleRate);
      if (index < length) data[index] += gain * Math.exp(-time / decay);
    }
  }
  return buffer;
}
export function createTrackEffects(context, destination, initial = defaultTrackFx()) {
  const input = context.createGain(), low = context.createBiquadFilter(), mid = context.createBiquadFilter(), high = context.createBiquadFilter();
  low.type = 'lowshelf'; low.frequency.value = 120; mid.type = 'peaking'; mid.Q.value = .707; high.type = 'highshelf'; high.frequency.value = 6000;
  input.connect(low); low.connect(mid); mid.connect(high);
  const compressor=createCompressor(context,initial.compressor);
  high.connect(compressor.input);
  const dry = context.createGain(), wet = context.createGain(), preDelay = context.createDelay(.2), damping = context.createBiquadFilter();
  damping.type = 'lowpass'; damping.Q.value = -3.01;
  compressor.input.connect(dry); dry.connect(destination); compressor.input.connect(preDelay); wet.connect(destination); damping.connect(wet);
  let convolver = null, key = '', retired = [];
  function sync(fx = defaultTrackFx()) {
    compressor.sync(fx.compressor);
    set(low.gain, fx.tone.enabled ? fx.tone.low : 0, context); set(mid.gain, fx.tone.enabled ? fx.tone.mid : 0, context); set(high.gain, fx.tone.enabled ? fx.tone.high : 0, context); set(mid.frequency, fx.tone.frequency, context);
    const rev = fx.reverb, mix = rev.enabled ? rev.wet : 0;
    set(dry.gain, Math.cos(mix * Math.PI / 2), context); set(wet.gain, Math.sin(mix * Math.PI / 2), context); set(preDelay.delayTime, rev.preDelay / 1000, context); set(damping.frequency, Math.min(rev.damping, context.sampleRate / 2 - 1), context);
    const nextKey = `${rev.decay.toFixed(2)}:${rev.size.toFixed(2)}`;
    if (rev.enabled && (!convolver || key !== nextKey)) {
      const node = context.createConvolver(); node.normalize = false; node.buffer = impulse(context, rev.decay, rev.size);
      const gain = context.createGain(); gain.gain.value = convolver && context instanceof AudioContext ? 0 : 1;
      preDelay.connect(node); node.connect(gain); gain.connect(damping);
      if (convolver) {
        const old = convolver;
        if (context instanceof AudioContext) {
          gain.gain.linearRampToValueAtTime(1, context.currentTime + .04); old.gain.gain.cancelScheduledValues(context.currentTime); old.gain.gain.setValueAtTime(old.gain.gain.value, context.currentTime); old.gain.gain.linearRampToValueAtTime(0, context.currentTime + .04);
          const timer = setTimeout(() => { old.node.disconnect(); old.gain.disconnect(); try { preDelay.disconnect(old.node); } catch {} retired = retired.filter(entry => entry !== old); }, 90);
          old.timer = timer; retired.push(old);
        } else { preDelay.disconnect(old.node); old.node.disconnect(); old.gain.disconnect(); }
      }
      convolver = { node, gain }; key = nextKey;
    }
  }
  sync(initial);
  return { input, sync, compressor, destroy() { compressor.destroy(); for (const entry of [convolver, ...retired].filter(Boolean)) { clearTimeout(entry.timer); entry.node.disconnect(); entry.gain.disconnect(); } for (const node of [input, low, mid, high, dry, wet, preDelay, damping]) node.disconnect(); } };
}
function createCompressor(context,initial=defaultCompressor()) {
  const node=new AudioWorkletNode(context,'sonora-compressor',{numberOfInputs:1,numberOfOutputs:1,channelCount:2,channelCountMode:'max'}),state={reduction:0};
  node.port.onmessage=event=>{state.reduction=event.data.reduction||0;};
  function sync(settings=defaultCompressor()){for(const key of ['enabled','threshold','ratio','attack','release','knee','makeup','mix'])set(node.parameters.get(key),key==='enabled'?Number(settings.enabled):settings[key],context,key!=='enabled');}
  sync(initial);return{input:node,state,sync,destroy(){node.port.onmessage=null;node.port.close();node.disconnect();}};
}
export function createLimiter(context, destination, initial = defaultLimiter()) {
  const node = new AudioWorkletNode(context, 'sonora-limiter', { numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [2], channelCount: 2, channelCountMode: 'explicit' });
  node.connect(destination);
  const state = { reduction: 0 }; node.port.onmessage = event => { state.reduction = event.data.reduction || 0; };
  function sync(settings = defaultLimiter()) {
    for (const key of ['enabled','drive','ceiling','release']) set(node.parameters.get(key), key === 'enabled' ? Number(settings.enabled) : settings[key], context, key === 'drive');
  }
  sync(initial);
  return { input: node, sync, state, destroy() { node.port.onmessage = null; node.port.close(); node.disconnect(); } };
}
