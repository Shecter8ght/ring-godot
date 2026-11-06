import { test } from 'node:test';
import assert from 'node:assert/strict';
import { LimiterCore } from '../ui/limiter-dsp.mjs';
import { defaultTrackFx,validateTrackFx,validateLimiter,reverbTail } from '../ui/fx-model.mjs';
import { createProject,createTrack,validateProject } from '../ui/model.mjs';
test('linked limiter catches random stereo transients and preserves the stereo ratio',()=>{
  const core=new LimiterCore(48000),ceiling=10**(-1/20),release=Math.exp(-1/(48000*.09));let seed=7,peak=0,error=0;
  for(let i=0;i<100000;i++){
    seed=(Math.imul(seed,1664525)+1013904223)|0;const sample=i<96000?((seed>>>0)/2147483648-1)*3:0;
    core.processFrame(sample,sample*.37,4,ceiling,release,true);peak=Math.max(peak,Math.abs(core.outputL),Math.abs(core.outputR));error=Math.max(error,Math.abs(core.outputR-core.outputL*.37));
  }
  assert.ok(peak<=ceiling+1e-7);assert.ok(peak>ceiling*.9);assert.ok(error<1e-7);
});
test('bypass is an exact fixed delay; recovery never exceeds the current peak ceiling',()=>{
  const core=new LimiterCore(48000),samples=Array.from({length:2000},(_,i)=>Math.sin(i)*.9);
  for(let i=0;i<samples.length+core.delay;i++){core.processFrame(samples[i]||0,-(samples[i]||0),10,.1,.999,false);const expected=i<core.delay?0:Math.fround(samples[i-core.delay]);assert.ok(core.outputL===expected);assert.ok(core.outputR===-expected);}
  const limiter=new LimiterCore(48000);let last=0;
  for(let i=0;i<24000;i++){limiter.processFrame(i<500?2:.02,0,1,.5,Math.exp(-1/4800),true);if(i>1000)assert.ok(limiter.gain>=last);last=limiter.gain;assert.ok(Math.abs(limiter.outputL)<=.500001);}
  assert.ok(limiter.gain>.98);
});
test('old projects open with neutral FX; new settings survive validation and are bounded',()=>{
  const project=createProject(),track=createTrack();project.tracks=[track];project.schemaVersion=1;delete project.soundTypes;delete project.limiter;delete track.fx;
  const old=validateProject(project);assert.equal(old.limiter.enabled,false);assert.deepEqual(old.tracks[0].fx,defaultTrackFx());
  old.limiter.enabled=true;old.limiter.drive=6;old.tracks[0].fx.reverb.enabled=true;old.tracks[0].fx.reverb.decay=2.2;
  const checked=validateProject(old);assert.deepEqual(checked.tracks[0].fx,old.tracks[0].fx);assert.deepEqual(checked.limiter,old.limiter);assert.ok(Math.abs(reverbTail(old)-2.218)<1e-9);
  assert.throws(()=>validateTrackFx({reverb:{decay:100}}),/эффекта/);assert.throws(()=>validateLimiter({ceiling:1}),/эффекта/);
});
test('live bypass never leaks previously driven samples; drive changes keep the ceiling',()=>{
  const core=new LimiterCore(48000);for(let i=0;i<1000;i++)core.processFrame(.5,.25,10,.8,.999,true);
  assert.ok(Math.abs(core.outputL-.8)<1e-7);
  core.processFrame(.5,.25,10,.8,.999,false);assert.equal(core.outputL,.5);assert.equal(core.outputR,.25);
  for(const drive of [2,16,1,12,4])for(let i=0;i<500;i++){core.processFrame(.5,.25,drive,.8,.999,true);assert.ok(Math.abs(core.outputL)<=.8000001);}
});
