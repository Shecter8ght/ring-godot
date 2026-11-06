export function extractClip(buffer,clip){
  const rate=buffer.sampleRate,start=Math.round(clip.offset*rate),frames=Math.max(1,Math.min(Math.round(clip.duration*rate),buffer.length-start));
  const output=new AudioBuffer({numberOfChannels:buffer.numberOfChannels,length:frames,sampleRate:rate}),gain=10**(clip.gain/20);
  for(let channel=0;channel<buffer.numberOfChannels;channel++){const input=buffer.getChannelData(channel),data=output.getChannelData(channel);for(let i=0;i<frames;i++){const local=i/rate,envelope=Math.max(0,Math.min(1,clip.fadeIn>0?local/clip.fadeIn:1,clip.fadeOut>0?(clip.duration-local)/clip.fadeOut:1));data[i]=input[start+i]*gain*envelope;}}return output;
}
export function audioStats(channels){let peak=0,energy=0;const frames=channels[0]?.length||0;for(const data of channels)for(const sample of data){peak=Math.max(peak,Math.abs(sample));energy+=sample*sample;}return{peak,rms:Math.sqrt(energy/Math.max(1,frames*channels.length)),frames};}
export function trimBounds(channels,rate,{threshold=-48,before=3,after=60}={}){
  const frames=channels[0].length,window=Math.max(1,Math.round(rate*.002)),limit=10**(threshold/10);let first=-1,last=-1;
  for(let from=0;from<frames;from+=window){const to=Math.min(frames,from+window);let energy=0;for(let i=from;i<to;i++){let sample=0;for(const data of channels)sample=Math.max(sample,data[i]*data[i]);energy+=sample;}if(energy/(to-from)>=limit){if(first<0)first=from;last=to;}}
  if(first<0)throw new Error('Звук целиком ниже порога обрезки. Уменьшите порог или отключите обрезку.');
  return{start:Math.max(0,first-Math.round(before*rate/1000)),end:Math.min(frames,last+Math.round(after*rate/1000))};
}
export function prepareInput(buffer,settings){const data=Array.from({length:buffer.numberOfChannels},(_,i)=>buffer.getChannelData(i)),range=settings.trim?trimBounds(data,buffer.sampleRate,settings):{start:0,end:buffer.length};
  const output=new AudioBuffer({numberOfChannels:buffer.numberOfChannels,length:range.end-range.start,sampleRate:buffer.sampleRate});
  for(let channel=0;channel<output.numberOfChannels;channel++)output.copyToChannel(data[channel].subarray(range.start,range.end),channel);return output;
}
export function finishBuffer(buffer,{normalization='none',target=-18,ceiling=-1,gain=0,fadeIn=0,fadeOut=0,protect=true}={}){
  const channels=Array.from({length:buffer.numberOfChannels},(_,i)=>buffer.getChannelData(i)),stats=audioStats(channels),limit=10**(ceiling/20);
  let scale=1;if(normalization==='peak'&&stats.peak>1e-9)scale=10**(target/20)/stats.peak;
  if(normalization==='rms'&&stats.rms>1e-9)scale=10**(target/20)/stats.rms;
  // Сначала общий уровень, затем разброс варианта; потолок ограничивает только итоговый пик.
  scale*=10**(gain/20);if(protect&&stats.peak*scale>limit)scale=limit/stats.peak;
  const start=fadeIn*buffer.sampleRate/1000,end=fadeOut*buffer.sampleRate/1000,output=new AudioBuffer({numberOfChannels:buffer.numberOfChannels,length:buffer.length,sampleRate:buffer.sampleRate});
  for(let channel=0;channel<channels.length;channel++){const data=output.getChannelData(channel);for(let i=0;i<data.length;i++){const envelope=Math.max(0,Math.min(1,start>0?i/start:1,end>0?(data.length-1-i)/end:1));data[i]=channels[channel][i]*scale*envelope;}}
  return output;
}
export function variationPlan(count,{pitchRange=.4,speedRange=0,gainRange=1.5,seed=1}={}){
  if(!Number.isInteger(count)||count<1||count>32)throw new Error('Выберите от 1 до 32 вариантов.');
  if(![pitchRange,speedRange,gainRange,seed].every(Number.isFinite)||pitchRange<0||pitchRange>12||speedRange<0||speedRange>30||gainRange<0||gainRange>12)throw new Error('Некорректный разброс вариантов.');
  let state=seed>>>0;const random=()=>{state=(Math.imul(state,1664525)+1013904223)>>>0;return state/4294967296;};
  const plans=Array.from({length:count},(_,i)=>({pitch:Number((((i+random())/count*2-1)*pitchRange).toFixed(4)),speed:Number((1+(random()*2-1)*speedRange/100).toFixed(5)),gain:Number(((random()*2-1)*gainRange).toFixed(3))}));
  for(let i=plans.length-1;i>0;i--){const j=Math.floor(random()*(i+1));[plans[i],plans[j]]=[plans[j],plans[i]];}return plans;
}
