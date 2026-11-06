const fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
function number(value,fallback,min,max,label){const result=value===undefined?fallback:value;if(typeof result!=='number'||!Number.isFinite(result)||result<min||result>max)throw new Error(`Некорректный параметр: ${label}.`);return result;}
function validateProcessingOptions(input={}){
  const pitch=number(input.pitch,0,-12,12,'высота'),speed=number(input.speed,1,.25,8,'скорость'),mode=input.mode||'independent';
  if(!['independent','tape'].includes(mode))throw new Error('Неизвестный режим высоты и скорости.');
  return{pitch,speed:mode==='tape'?2**(pitch/12):speed,mode,formant:input.formant===true};
}
function inputInfo(bytes){
  if(bytes.length<44||bytes.toString('ascii',0,4)!=='RIFF'||bytes.toString('ascii',8,12)!=='WAVE')throw new Error('Для обработки нужен WAV.');
  let format,channels,rate,bits,frames;
  for(let offset=12;offset+8<=bytes.length;){const name=bytes.toString('ascii',offset,offset+4),size=bytes.readUInt32LE(offset+4);if(offset+8+size>bytes.length)throw new Error('Повреждённый WAV.');
    if(name==='fmt '&&size>=16){format=bytes.readUInt16LE(offset+8);channels=bytes.readUInt16LE(offset+10);rate=bytes.readUInt32LE(offset+12);bits=bytes.readUInt16LE(offset+22);}
    if(name==='data')frames=size/(channels*bits/8);offset+=8+size+(size%2);
  }
  if(![1,3].includes(format)||![1,2].includes(channels)||rate!==48000||![16,24,32].includes(bits)||!Number.isInteger(frames)||frames<48||frames>rate*120)throw new Error('Обрабатывайте моно/стерео WAV 48 кГц от 1 мс до 2 минут.');
  return{frames,rate,channels};
}
function createAudioProcessor(runFfmpeg){return async(bytes,input)=>{
  const settings=validateProcessingOptions(input),info=inputInfo(bytes);
  if(settings.pitch===0&&settings.speed===1)return new Uint8Array(bytes);
  const folder=await fs.mkdtemp(path.join(os.tmpdir(),'sonora-process-'));
  try{
    const source=path.join(folder,'source.wav'),destination=path.join(folder,'result.wav');await fs.writeFile(source,bytes);
    const factor=2**(settings.pitch/12),frames=Math.round(info.frames/settings.speed);
    const filter=settings.mode==='tape'?`asetrate=${Math.round(info.rate*factor)},aresample=48000`:`rubberband=tempo=${settings.speed.toFixed(8)}:pitch=${factor.toFixed(8)}:formant=${settings.formant?'preserved':'shifted'}:pitchq=quality:channels=together`;
    await runFfmpeg(['-y','-i',source,'-vn','-af',`${filter},apad,atrim=end_sample=${frames},asetpts=N/SR/TB`,'-ar','48000','-c:a','pcm_f32le',destination]);
    return new Uint8Array(await fs.readFile(destination));
  }finally{
    const resolved=path.resolve(folder),temp=path.resolve(os.tmpdir());
    if(resolved.startsWith(temp+path.sep)&&path.basename(resolved).startsWith('sonora-process-'))await fs.rm(resolved,{recursive:true,force:true});
  }
};}
module.exports={createAudioProcessor,validateProcessingOptions,inputInfo};
