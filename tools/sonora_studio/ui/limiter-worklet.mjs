import { LimiterCore } from './limiter-dsp.mjs';
class SonoraLimiter extends AudioWorkletProcessor {
  static get parameterDescriptors() {
    return [
      { name: 'enabled', defaultValue: 0, minValue: 0, maxValue: 1, automationRate: 'k-rate' },
      { name: 'drive', defaultValue: 0, minValue: 0, maxValue: 24, automationRate: 'k-rate' },
      { name: 'ceiling', defaultValue: -1, minValue: -18, maxValue: 0, automationRate: 'k-rate' },
      { name: 'release', defaultValue: 90, minValue: 10, maxValue: 600, automationRate: 'k-rate' }
    ];
  }
  constructor() { super(); this.core = new LimiterCore(sampleRate); this.blocks = 0; }
  process(inputs, outputs, parameters) {
    const input = inputs[0] || [], output = outputs[0];
    const enabled = parameters.enabled[0] > .5, drive = 10 ** (parameters.drive[0] / 20), ceiling = 10 ** (parameters.ceiling[0] / 20), release = Math.exp(-1 / (sampleRate * parameters.release[0] / 1000));
    for (let i = 0; i < output[0].length; i++) {
      this.core.processFrame(input[0]?.[i] || 0, input[1]?.[i] ?? input[0]?.[i] ?? 0, drive, ceiling, release, enabled);
      output[0][i] = this.core.outputL; if (output[1]) output[1][i] = this.core.outputR;
    }
    if (++this.blocks % 12 === 0) this.port.postMessage({ reduction: -20 * Math.log10(Math.max(1e-8, this.core.gain)) });
    return true;
  }
}
registerProcessor('sonora-limiter', SonoraLimiter);
