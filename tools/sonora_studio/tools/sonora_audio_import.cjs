// Единственная точка записи звуков Sonora в Godot. Старые записи остаются на диске.
const fs = require('node:fs/promises');
const path = require('node:path');
const { randomUUID } = require('node:crypto');
const { spawn } = require('node:child_process');
const { readCatalog, inside, hash, json, validateRegistry } = require('../src/ring-catalog.cjs');
const absent = null;
async function optional(file) { try { return await fs.readFile(file); } catch (error) { if (error.code === 'ENOENT') return absent; throw error; } }
const digest = bytes => bytes === null ? null : hash(bytes);
async function atomic(file, bytes) {
  if (bytes === null) { await fs.rm(file, { force:true }); return; }
  await fs.mkdir(path.dirname(file), { recursive:true });
  const temp = `${file}.${randomUUID()}.tmp`;
  try { await fs.writeFile(temp, bytes, { flag:'wx' }); await fs.rename(temp, file); }
  finally { await fs.rm(temp, {force:true}).catch(() => {}); }
}
async function applyPlan(root, plan, backupRoot, details) {
  const id = `${new Date().toISOString().replace(/[:.]/g,'-')}_${randomUUID().slice(0,8)}`;
  const folder = path.join(backupRoot, id); await fs.mkdir(folder, {recursive:true});
  const manifest = { id, root, date:new Date().toISOString(), status:'pending', ...details, files:[] };
  for (let i = 0; i < plan.length; i++) {
    const item = plan[i];
    const target = await inside(root, item.relative);
    if (digest(await optional(target)) !== digest(item.before)) throw new Error(`Ресурс изменился во время подготовки: ${item.relative}. Обновите каталог.`);
    if (item.before !== null) await fs.writeFile(path.join(folder, `${i}.before`), item.before);
    manifest.files.push({ relative:item.relative, before:digest(item.before), after:digest(item.after), snapshot:item.before === null ? null : `${i}.before` });
  }
  await atomic(path.join(folder,'manifest.json'), JSON.stringify(manifest,null,2));
  const applied = [];
  try {
    for (const item of plan) {
      const target = await inside(root,item.relative);
      if (digest(await optional(target)) !== digest(item.before)) throw new Error(`Ресурс изменён другим редактором: ${item.relative}.`);
      await atomic(target,item.after); applied.push(item);
    }
    manifest.status = 'applied'; await atomic(path.join(folder,'manifest.json'),JSON.stringify(manifest,null,2));
    return manifest;
  } catch (error) {
    let complete = true;
    for (const item of applied.reverse()) {
      const target = await inside(root,item.relative);
      if (digest(await optional(target)) === digest(item.after)) await atomic(target,item.before); else complete = false;
    }
    manifest.status = complete ? 'failed-restored' : 'pending';
    manifest.error = error.message; await atomic(path.join(folder,'manifest.json'),JSON.stringify(manifest,null,2));
    throw error;
  }
}
async function importSound({ projectPath, eventId, newDefinition, candidates, mode, provenance, backupRoot, expectedFingerprint }) {
  const catalog = await readCatalog(projectPath), event = newDefinition || catalog.events.find(event => event.id === eventId)?.definition;
  if (expectedFingerprint && expectedFingerprint !== catalog.fingerprint) throw new Error('Каталог Ring изменился. Обновите его и утвердите звук ещё раз.');
  if (!event?.binding) throw new Error('Не выбран тип звука и момент воспроизведения.');
  if (!['replace','add'].includes(mode) || !candidates.length || candidates.length > 32) throw new Error('Некорректный набор вариантов.');
  if(event.type==='loop'&&(candidates.length!==1||mode!=='replace'))throw new Error('Для петли выберите один вариант с заменой набора.');
  const audioRoot = await inside(catalog.root,'assets/audio'), registryBefore = await fs.readFile(await inside(catalog.root,'data/audio_events.json'));
  const registry = JSON.parse(registryBefore.toString('utf8').replace(/^\uFEFF/,''));
  const next = structuredClone(event);
  next.files = mode==='add' ? [...event.files] : [];
  next.enabled = true;
  const index = registry.events.findIndex(item=>item.id===event.id);
  if(index<0)registry.events.push(next);else registry.events[index]=next;
  validateRegistry(registry);
  const used = new Set(catalog.files.map(file => file.toLowerCase())), created = [], plan = [];
  let number = 1;
  for (const candidate of candidates) {
    const bytes = await fs.readFile(candidate.path);
    if (hash(bytes) !== candidate.hash || bytes.toString('ascii',0,4) !== 'RIFF' || bytes.toString('ascii',8,12) !== 'WAVE') throw new Error('Утверждённый звук изменился или повреждён.');
    let relative;
    do { relative = `sonora/${event.id}_${String(number++).padStart(2,'0')}.wav`; } while (used.has(relative.toLowerCase()));
    used.add(relative.toLowerCase()); created.push(relative); next.files.push(relative);
    const target = await inside(audioRoot,relative);
    plan.push({ relative:`assets/audio/${relative}`, before:await optional(target), after:bytes });
  }
  validateRegistry(registry);
  const creditRelative = 'assets/CREDITS.md', creditPath = await inside(catalog.root, creditRelative), creditBefore = await optional(creditPath);
  const note = `${provenance.license || 'Собственный звук / ИИ'}${provenance.source ? '; источник: ' + provenance.source : ''}${provenance.author ? '; автор: ' + provenance.author : ''}`;
  const credit = `\n\n<!-- Sonora Studio ${randomUUID()} -->\nЗвук «${event.name}»: ${created.map(file => '`assets/audio/' + file + '`').join(', ')}. ${note.replace(/[\r\n]/g,' ')}. Добавлен через Sonora Studio.\n`;
  plan.push({relative:creditRelative,before:creditBefore,after:Buffer.from((creditBefore?.toString('utf8') || '# Источники ресурсов\n')+credit)});
  const recordRelative = `assets/audio/LICENSES/sonora-${randomUUID()}.txt`;
  const record = `Sonora Studio\nСобытие: ${event.id} — ${event.name}\nФайлы: ${created.join(', ')}\nЛицензия: ${note}\nОригиналы: ${candidates.map(item=>item.name).join(', ')}\n\n${provenance.text || ''}\n`;
  plan.push({relative:recordRelative,before:null,after:Buffer.from(record)});
  plan.push({relative:'data/audio_events.json',before:registryBefore,after:Buffer.from(JSON.stringify(registry,null,2)+'\n')});
  return applyPlan(catalog.root,plan,backupRoot,{audioSchemaVersion:2,eventId:event.id,eventName:event.name,created,mode});
}
async function editEvent({projectPath,eventId,operation,name,backupRoot,expectedFingerprint}){
  const catalog=await readCatalog(projectPath);if(expectedFingerprint&&catalog.fingerprint!==expectedFingerprint)throw new Error('Назначения изменились. Обновите стенд.');
  const before=await fs.readFile(await inside(catalog.root,'data/audio_events.json')),registry=JSON.parse(before.toString('utf8').replace(/^\uFEFF/,'')),event=registry.events.find(e=>e.id===eventId);if(!event)throw new Error('Тип звука не найден.');
  if(operation==='clear')event.files=[];
  else if(operation==='rename'){if(typeof name!=='string'||!name.trim()||name.trim().length>160)throw new Error('Введите название до 160 знаков.');event.name=name.trim();}
  else if(operation==='delete'){if(event.weapon)throw new Error('Слот оружия можно оставить без звука.');registry.events=registry.events.filter(e=>e.id!==eventId);}
  else throw new Error('Неизвестная операция.');validateRegistry(registry);
  return applyPlan(catalog.root,[{relative:'data/audio_events.json',before,after:Buffer.from(JSON.stringify(registry,null,2)+'\n')}],backupRoot,{audioSchemaVersion:2,eventId,eventName:event.name,created:[],operation});
}
async function undoImport(backupRoot, id, expectedRoot) {
  if (!/^[\w.-]+$/.test(id)) throw new Error('Некорректная резервная копия.');
  const folder=path.join(backupRoot,id), manifest=await json(path.join(folder,'manifest.json'));
  if(manifest.audioSchemaVersion!==2)throw new Error('Эта резервная копия относится к прежней аудиосистеме. Она сохранена в папке истории; автоматическая отмена после перехода недоступна.');
  if (!['applied','pending'].includes(manifest.status) || path.resolve(manifest.root)!==path.resolve(expectedRoot)) throw new Error('Эта операция уже отменена или принадлежит другому проекту.');
  const plan=[];
  for (const item of manifest.files) {
    const target=await inside(manifest.root,item.relative), current=await optional(target), currentHash=digest(current);
    if (currentHash === item.before) continue;
    if (currentHash !== item.after) throw new Error(`После импорта изменён ${item.relative}. Автоматическая отмена не будет перезаписывать новые правки. Резервная копия: ${folder}`);
    const before=item.snapshot ? await fs.readFile(path.join(folder,item.snapshot)) : null;
    if (digest(before)!==item.before) throw new Error('Резервная копия повреждена.');
    plan.push({relative:item.relative,before:current,after:before});
  }
  const restoration=await applyPlan(manifest.root,plan,backupRoot,{eventId:manifest.eventId,eventName:`Отмена: ${manifest.eventName}`,restores:id});
  manifest.status='undone'; await atomic(path.join(folder,'manifest.json'),JSON.stringify(manifest,null,2));
  restoration.status='restoration'; await atomic(path.join(backupRoot,restoration.id,'manifest.json'),JSON.stringify(restoration,null,2));
  return manifest;
}
async function importGodot(executable, root, { logFile = null, resources = [] } = {}) {
  if (!executable) return {ok:false,detail:'Godot не найден. Файлы готовы; игра загрузит WAV при следующем запуске. Импорт ресурсов выполнит редактор Godot.'};
  const logPath=logFile||path.join(require('node:os').tmpdir(),`sonora-godot-${randomUUID()}.log`);
  return new Promise(resolve=>{
    const env={...process.env,SDL_JOYSTICK_DIRECTINPUT:'0',VK_LOADER_LAYERS_DISABLE:'VK_LAYER_RTSS,VK_LAYER_VALVE_steam_overlay,VK_LAYER_VALVE_steam_fossilize,VK_LAYER_EOS_Overlay',DISABLE_LAYER_NV_PRESENT_1:'1'};
    const child=spawn(executable,['--headless','--path',root,'--editor','--import','--log-file',logPath,'--quit'],{windowsHide:true,env});
    let log='',done=false;
    const finish=async result=>{if(done)return;done=true;clearTimeout(timer);const saved=await fs.readFile(logPath,'utf8').catch(()=>'');log=(log+'\n'+saved).trim();
      if(result.ok){
        let invalid=/(?:SCRIPT ERROR:|ERROR:)/.test(log);
        for(const resource of resources){
          try{const definition=await fs.readFile(await inside(root,`assets/audio/${resource}.import`),'utf8');const remap=definition.match(/^path="res:\/\/([^"\r\n]+)"/m)?.[1];if(!remap||/valid=false/.test(definition))invalid=true;else await fs.access(await inside(root,remap));}catch{invalid=true;}
        }
        if(invalid)result={ok:false,detail:'Файлы записаны. Godot сообщил об ошибках проекта или не создал один из ресурсов. Подробности — в журнале резервной копии; игра умеет загружать WAV напрямую.'};
      }
      if(!logFile)await fs.rm(logPath,{force:true}).catch(()=>{});resolve({...result,log});};
    const timer=setTimeout(()=>{child.kill();finish({ok:false,detail:'Файлы записаны. Godot не завершил проверку за 2 минуты; откройте проект в редакторе.'});},120000);
    child.stdout.on('data',data=>{log=(log+data).slice(-50000);});child.stderr.on('data',data=>{log=(log+data).slice(-50000);});
    child.on('error',error=>finish({ok:false,detail:`Файлы записаны. Не удалось запустить Godot: ${error.message}`}));
    child.on('close',code=>{const errors=/(?:SCRIPT ERROR:|ERROR:)/.test(log);finish({ok:code===0&&!errors,detail:code===0&&!errors?'Godot импортировал ресурсы. Звук доступен при следующем запуске игры.':'Файлы записаны, но Godot сообщил об ошибках проекта. Журнал сохранён; звук доступен прямой загрузке игры.'});});
  });
}
module.exports={importSound,editEvent,undoImport,importGodot,atomic,optional};
