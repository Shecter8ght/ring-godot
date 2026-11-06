const fs = require('node:fs/promises');
const path = require('node:path');
const { randomUUID } = require('node:crypto');
const { readCatalog, inside, hash, json, newEvent, locations } = require('./ring-catalog.cjs');
const { importSound, editEvent, undoImport, importGodot, atomic, optional } = require('../tools/sonora_audio_import.cjs');
const DEFAULT_PROJECT = 'E:\\Games\\RING-godot';
const DEFAULT_GODOT = 'D:\\Steam\\steamapps\\common\\Godot Engine\\godot.windows.opt.tools.64.exe';
class RingService {
  constructor(folder, runFfmpeg) { this.folder=folder;this.runFfmpeg=runFfmpeg;this.busy=false;this.approval=null;this.catalog=null; }
  async init() {
    await fs.mkdir(path.join(this.folder,'candidates'),{recursive:true});
    this.settings=await json(path.join(this.folder,'settings.json')).catch(()=>({projectPath:DEFAULT_PROJECT,godotPath:DEFAULT_GODOT}));
    this.shelf=await json(path.join(this.folder,'shelf.json')).catch(()=>[]);
    this.shelf=this.shelf.filter(item=>/^[a-f0-9-]{36}$/.test(item.id)).slice(-100).map(item=>({...item,path:path.join(this.folder,'candidates',`${item.id}.wav`)}));
    return this;
  }
  async saveShelf(){await atomic(path.join(this.folder,'shelf.json'),JSON.stringify(this.shelf,null,2));}
  viewCandidate(item){const {path:_,...view}=item;return view;}
  async state(refresh=true){
    let error=null;
    try{if(refresh||!this.catalog)this.catalog=await readCatalog(this.settings.projectPath);}catch(caught){this.catalog=null;error=`Не удалось открыть Ring: ${caught.message}`;}
    const journals=[];const backupRoot=path.join(this.folder,'backups');
    for(const entry of await fs.readdir(backupRoot,{withFileTypes:true}).catch(()=>[])){
      if(!entry.isDirectory())continue;
      const record=await json(path.join(backupRoot,entry.name,'manifest.json')).catch(()=>null);
      if(record?.audioSchemaVersion===2&&['applied','pending'].includes(record.status)&&path.resolve(record.root)===path.resolve(this.settings.projectPath))journals.push({id:record.id,eventName:record.eventName,date:record.date,created:record.created,status:record.status});
    }
    journals.sort((a,b)=>b.date.localeCompare(a.date));
    return{settings:this.settings,catalog:this.catalog,error,candidates:this.shelf.map(item=>this.viewCandidate(item)),approval:this.approval,history:journals.slice(0,20),busy:this.busy};
  }
  async setProject(folder){this.assertIdle();const catalog=await readCatalog(folder);this.settings.projectPath=catalog.root;this.catalog=catalog;this.approval=null;await atomic(path.join(this.folder,'settings.json'),JSON.stringify(this.settings,null,2));return this.state(false);}
  async setGodot(file){this.assertIdle();if(!/\.exe$/i.test(file))throw new Error('Выберите исполняемый файл Godot.');await fs.access(file);this.settings.godotPath=file;await atomic(path.join(this.folder,'settings.json'),JSON.stringify(this.settings,null,2));return this.state(false);}
  assertIdle(){if(this.busy||this.staging)throw new Error('Дождитесь завершения текущей обработки звука.');}
  async stage(bytes,name,origin='file'){
    this.assertIdle();if(this.shelf.length>=100)throw new Error('На полке 100 звуков. Удалите ненужные кандидаты.');
    if(!(bytes instanceof Uint8Array)||bytes.byteLength>256*1024*1024||!bytes.byteLength)throw new Error('Звук должен занимать от 1 байта до 256 МБ.');
    const extension=String(name).split('.').pop().toLowerCase();if(!['wav','mp3','ogg'].includes(extension))throw new Error('Поддерживаются WAV, MP3 и OGG.');
    const id=randomUUID(), input=path.join(this.folder,'candidates',`${id}.input.${extension}`),output=path.join(this.folder,'candidates',`${id}.wav`);
    this.staging=true;
    try{
      await fs.writeFile(input,bytes);
      await this.runFfmpeg(['-y','-i',input,'-t','120.01','-vn','-ac','1','-ar','48000','-af','alimiter=limit=0.988553:level=false:latency=true','-c:a','pcm_s16le',output]);
      const converted=await fs.readFile(output),info=wavInfo(converted);
      if(info.duration>120||info.duration<.001)throw new Error('Для Ring выберите звук длительностью от 1 мс до 2 минут.');
      const item={id,name:String(name).replace(/[\r\n]/g,' ').slice(0,160),path:output,hash:hash(converted),duration:info.duration,peak:info.peak,origin,date:new Date().toISOString()};
      this.shelf.push(item);this.approval=null;await this.saveShelf();return this.viewCandidate(item);
    }catch(error){await fs.rm(output,{force:true}).catch(()=>{});throw error;}
    finally{await fs.rm(input,{force:true}).catch(()=>{});this.staging=false;}
  }
  async remove(id){this.assertIdle();const index=this.shelf.findIndex(item=>item.id===id);if(index<0)return;const[item]=this.shelf.splice(index,1);this.approval=null;await this.saveShelf();await fs.rm(item.path,{force:true});}
  async candidateAudio(id){const item=this.shelf.find(item=>item.id===id);if(!item)throw new Error('Кандидат не найден.');return new Uint8Array(await fs.readFile(item.path));}
  async gameAudio(relative){if(!this.catalog)throw new Error('Откройте проект Ring.');if(!this.catalog.files.includes(relative))throw new Error('Нет такого звука в каталоге.');const file=await inside(path.join(this.catalog.root,'assets/audio'),relative);if((await fs.stat(file)).size>256*1024*1024)throw new Error('Запись слишком большая для предпрослушивания.');return new Uint8Array(await fs.readFile(file));}
  async approve({eventId,newType,ids,mode,provenance}){
    this.assertIdle();if(!Array.isArray(ids)||!ids.length||ids.length>32||new Set(ids).size!==ids.length)throw new Error('Выберите от 1 до 32 разных вариантов.');
    this.catalog=await readCatalog(this.settings.projectPath);const definition=newType?await newEvent(this.catalog,newType):null,event=definition||this.catalog.events.find(item=>item.id===eventId);
    if(!event?.binding)throw new Error('Выберите тип звука или создайте новый.');
    if(!['replace','add'].includes(mode))throw new Error('Выберите способ импорта.');
    if(event.type==='loop'&&(ids.length!==1||mode!=='replace'))throw new Error('Для петли выберите один вариант и замену набора.');
    if(!provenance||!['Собственный звук / ИИ','CC0','CC-BY','Библиотека royalty-free'].includes(provenance.license))throw new Error('Укажите источник звука.');
    for(const key of ['source','author','text']){provenance[key]=String(provenance[key]||'').trim().slice(0,key==='text'?50000:2000);}
    if(provenance.license!=='Собственный звук / ИИ'&&!provenance.source)throw new Error('Для стороннего звука укажите источник или ссылку.');
    if(provenance.license==='CC-BY'&&!provenance.author)throw new Error('Для CC-BY укажите автора.');
    if(provenance.license==='Библиотека royalty-free'&&!provenance.text)throw new Error('Добавьте текст лицензии библиотеки — он сохранится в assets/audio/LICENSES.');
    const selected=[];for(const id of ids){const item=this.shelf.find(item=>item.id===id);if(!item||hash(await fs.readFile(item.path))!==item.hash)throw new Error('Кандидат отсутствует или изменился.');selected.push({id,hash:item.hash});}
    this.approval={id:randomUUID(),eventId:event.id,newDefinition:definition,ids,mode,provenance,selected,fingerprint:this.catalog.fingerprint,root:this.catalog.root};
    return this.approval;
  }
  async invalidate(){this.assertIdle();this.approval=null;}
  async importApproved(approvalId){
    this.assertIdle();const approved=this.approval;if(!approved||approved.id!==approvalId)throw new Error('Сначала утвердите текущий набор звуков.');this.busy=true;
    try{
      const candidates=approved.selected.map(entry=>{const item=this.shelf.find(item=>item.id===entry.id);if(!item||item.hash!==entry.hash)throw new Error('Набор изменился после утверждения.');return item;});
      const record=await importSound({projectPath:approved.root,eventId:approved.eventId,newDefinition:approved.newDefinition,candidates,mode:approved.mode,provenance:approved.provenance,backupRoot:path.join(this.folder,'backups'),expectedFingerprint:approved.fingerprint});
      this.approval=null;
      const executable=await fs.access(this.settings.godotPath).then(()=>this.settings.godotPath).catch(()=>null);
      const godot=await importGodot(executable,approved.root,{logFile:path.join(this.folder,'backups',record.id,'godot-engine.log'),resources:record.created});
      await fs.writeFile(path.join(this.folder,'backups',record.id,'godot.log'),godot.log||godot.detail);
      return{record,godot};
    }finally{this.busy=false;}
  }
  async undo(id){this.assertIdle();this.busy=true;try{const record=await undoImport(path.join(this.folder,'backups'),id,this.settings.projectPath);this.approval=null;return record;}finally{this.busy=false;}}
  async locations(){this.assertIdle();return locations(this.settings.projectPath);}
  async edit(options){this.assertIdle();this.busy=true;try{const record=await editEvent({...options,projectPath:this.settings.projectPath,backupRoot:path.join(this.folder,'backups')});this.approval=null;return record;}finally{this.busy=false;}}
}
function wavInfo(bytes){
  let rate=48000,channels=1,bits=16,length=0,start=0;
  for(let offset=12;offset+8<=bytes.length;){const tag=bytes.toString('ascii',offset,offset+4),size=bytes.readUInt32LE(offset+4);if(tag==='fmt '){channels=bytes.readUInt16LE(offset+10);rate=bytes.readUInt32LE(offset+12);bits=bytes.readUInt16LE(offset+22);}if(tag==='data'){length=size;start=offset+8;break;}offset+=8+size+(size%2);}
  if(!length||bits!==16||channels!==1||rate!==48000||start+length>bytes.length)throw new Error('Не удалось подготовить mono WAV 48 кГц.');
  let peak=0;for(let i=start;i<start+length;i+=2)peak=Math.max(peak,Math.abs(bytes.readInt16LE(i)/32768));return{duration:length/(channels*rate*bits/8),peak};
}
module.exports={RingService,wavInfo};
