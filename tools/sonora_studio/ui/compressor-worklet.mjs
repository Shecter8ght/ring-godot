import { CompressorCore } from './compressor-dsp.mjs';
class SonoraCompressor extends AudioWorkletProcessor {
  static get parameterDescriptors() {
    return [
      ['enabled',0,0,1],['threshold',-20,-60,0],['ratio',3,1,20],['attack',12,.1,100],
      ['release',120,10,1500],['knee',6,0,24],['makeup',0,-12,24],['mix',1,0,1]
    ].map(([name,defaultValue,minValue,maxValue]) => ({name,defaultValue,minValue,maxValue,automationRate:'k-rate'}));
  }
  constructor() { super(); this.core = new CompressorCore(sampleRate); this.blocks = 0; this.active = false; }
  process(inputs, outputs, parameters) {
    const input = inputs[0] || [], output = outputs[0], enabled = parameters.enabled[0] > .5;
    if (!enabled) {
      for (let channel = 0; channel < output.length; channel++) { const data = input[channel] || input[0]; if(data) output[channel].set(data); else output[channel].fill(0); }
      this.core.reset();
      if(this.active) this.port.postMessage({reduction:0}); this.active = false; return true;
    }
    this.active = true;
    this.core.configure(Object.fromEntries(['threshold','ratio','attack','release','knee','makeup','mix'].map(key=>[key,parameters[key][0]])));
    for(let i=0;i<output[0].length;i++) {
      const left=input[0]?.[i]||0,right=input[1]?.[i]??left,gain=this.core.processFrame(left,right);
      output[0][i]=left*gain;if(output[1])output[1][i]=right*gain;
    }
    if(++this.blocks%16===0)this.port.postMessage({reduction:this.core.reduction});return true;
  }
}
registerProcessor('sonora-compressor',SonoraCompressor);
