import {test} from 'node:test';
import assert from 'node:assert/strict';
import {CompressorCore,compressionReduction} from '../ui/compressor-dsp.mjs';
import {audioStats,trimBounds,variationPlan} from '../ui/preparation.mjs';
import {createProject,createTrack,validateProject} from '../ui/model.mjs';
import processor from '../src/audio-process.cjs';
test('compressor soft knee is continuous and 4:1 has the expected slope',()=>{
  assert.equal(compressionReduction(-30,-20,4,0),0);assert.equal(compressionReduction(-4,-20,4,0),12);
  for(const boundary of [-24,-16])assert.ok(Math.abs(compressionReduction(boundary-1e-6,-20,4,8)-compressionReduction(boundary+1e-6,-20,4,8))<2e-6);
});
test('RMS compression settles correctly, links stereo, and recovers after the signal',()=>{
  const core=new CompressorCore(48000);core.configure({threshold:-20,ratio:4,knee:0,attack:10,release:100,makeup:0,mix:1});
  let gain;for(let i=0;i<48000;i++)gain=core.processFrame(.5,.1);assert.ok(Math.abs(core.reduction-(20*Math.log10(.5)+20)*.75)<.001);assert.ok(gain<.31&&gain>.29);
  const reduction=core.reduction;for(let i=0;i<48000;i++)core.processFrame(0,0);assert.ok(core.reduction<reduction*.001);
  core.configure({threshold:-40,ratio:20,knee:6,attack:1,release:100,makeup:12,mix:0});assert.equal(core.processFrame(1,.25),1);
});
test('preparation trims edges across channels, keeps padding, and rejects an entirely silent file',()=>{
  const left=new Float32Array(48000),right=new Float32Array(48000);right.fill(.1,9600,19200);
  const range=trimBounds([left,right],48000,{threshold:-40,before:5,after:20});assert.equal(range.start,9360);assert.equal(range.end,20160);
  assert.throws(()=>trimBounds([left],48000),/ниже порога/);const stats=audioStats([left,right]);assert.ok(Math.abs(stats.rms-Math.sqrt(.001))<1e-8);
});
test('variants are repeatable, diverse, and stay in the chosen ranges',()=>{
  const settings={pitchRange:.5,speedRange:3,gainRange:1,seed:42},a=variationPlan(12,settings);assert.deepEqual(a,variationPlan(12,settings));assert.notDeepEqual(a,variationPlan(12,{...settings,seed:43}));
  assert.equal(new Set(a.map(item=>item.pitch)).size,12);for(const item of a){assert.ok(Math.abs(item.pitch)<=.5);assert.ok(item.speed>=.97&&item.speed<=1.03);assert.ok(Math.abs(item.gain)<=1);}
  assert.throws(()=>variationPlan(33,settings));assert.throws(()=>variationPlan(2,{pitchRange:NaN}));
});
test('audio processing validates independent and tape modes; old FX stay neutral',()=>{
  assert.equal(processor.validateProcessingOptions({pitch:12,mode:'tape'}).speed,2);assert.equal(processor.validateProcessingOptions({pitch:12,speed:.75}).speed,.75);
  for(const input of [{pitch:NaN},{pitch:13},{speed:0},{mode:'custom;file'}])assert.throws(()=>processor.validateProcessingOptions(input));
  const project=createProject();project.tracks=[createTrack()];project.schemaVersion=1;delete project.soundTypes;delete project.tracks[0].fx.compressor;const old=validateProject(project);assert.equal(old.tracks[0].fx.compressor.enabled,false);old.tracks[0].fx.compressor.enabled=true;old.tracks[0].fx.compressor.threshold=-25;assert.equal(validateProject(old).tracks[0].fx.compressor.threshold,-25);
});
