const {_electron:electron}=require('playwright'),fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const{fixture,sineWav}=require('./ring-v2-fixture.cjs'),{readCatalog,newEvent,validateRegistry,inside}=require('../src/ring-catalog.cjs'),{RingService}=require('../src/ring-service.cjs');
const root=path.resolve(__dirname,'..'),qa=path.resolve(root, '../../_asset_src/sonora_qa/qa-ring-v2'),report={date:new Date().toISOString(),checks:[],errors:[]};let app,page,bench;
async function check(name,action){const detail=await action();report.checks.push({name,status:'pass',detail});console.log('PASS '+name+(detail?': '+JSON.stringify(detail):''));}
const env={...process.env,SDL_JOYSTICK_DIRECTINPUT:'0',DISABLE_LAYER_NV_PRESENT_1:'1',VK_LOADER_LAYERS_DISABLE:'VK_LAYER_RTSS,VK_LAYER_VALVE_steam_overlay,VK_LAYER_VALVE_steam_fossilize,VK_LAYER_EOS_Overlay'};delete env.ELECTRON_RUN_AS_NODE;
async function command(exe,args){return new Promise((resolve,reject)=>{const child=spawn(exe,args,{windowsHide:true,env});let out='';child.stdout.on('data',d=>out+=d);child.stderr.on('data',d=>out+=d);child.on('error',reject);child.on('close',code=>code===0?resolve(out):reject(new Error(out.slice(-6000)||String(code))));});}
async function waitImport(){await bench.waitForFunction(()=>document.getElementById('ring-busy').hidden);assert.equal(await bench.locator('#result-box.warning').count(),0);}
(async()=>{
 await fs.mkdir(qa,{recursive:true});const{root:project}=await fixture(qa),source=path.join(qa,'Вариант.wav');await fs.writeFile(source,sineWav(700,.2,.5));const profile=await fs.mkdtemp(path.join(qa,'profile-'));env.SONORA_USER_DATA=profile;
 await check('catalog has concrete weapons, explicit assignments and no distance/family entries',async()=>{const c=await readCatalog(project);assert.equal(c.weapons.length,Object.keys(JSON.parse(await fs.readFile(path.join(project,'data/weapons.json'),'utf8')).weapons).length);assert.ok(c.events.every(e=>!e.id.startsWith('fam_')&&!e.kind.includes('@')));assert.ok(!c.events.some(e=>/_(shot_self|shot_mid|shot_far|shot_distant)$/.test(e.id)));assert.ok(c.events.filter(e=>e.weapon==='wpn_smg_04').every(e=>e.activeFiles.length===0));const broken=structuredClone(c.registry);broken.events.push({...broken.events[0],id:'duplicate_binding'});assert.throws(()=>validateRegistry(broken),/назначен/);await assert.rejects(()=>inside(project,'../escape'));return{weapons:c.weapons.length,slots:c.events.filter(e=>e.weapon==='wpn_hg_01').length};});
 app=await electron.launch({...(process.env.SONORA_TEST_EXECUTABLE?{executablePath:process.env.SONORA_TEST_EXECUTABLE,args:[]}:{args:[root]}),env});page=await app.firstWindow();await page.locator('#load-demo').waitFor();page.on('pageerror',e=>report.errors.push(e.message));
 await app.evaluate(({dialog},values)=>{dialog.showOpenDialog=async(_,options)=>({canceled:false,filePaths:options.properties.includes('openDirectory')?[values.project]:[values.source]});},{project,source});
 const ready=app.waitForEvent('window');await page.locator('#open-ring').click();bench=await ready;bench.on('pageerror',e=>report.errors.push(e.message));await bench.locator('[data-weapon="wpn_hg_01"]').waitFor();await bench.locator('#choose-project').click();await bench.waitForFunction(p=>document.getElementById('project-path').textContent===p,project);
 await check('workbench shows one model and its actions; switching models cannot import an old approval',async()=>{assert.equal(await bench.locator('[data-weapon]').count(),17);await bench.locator('[data-weapon="wpn_hg_02"]').click();assert.equal(await bench.locator('[data-event="wpn_hg_01_shot"]').count(),0);await bench.locator('[data-event="wpn_hg_02_shot"]').click();await bench.locator('#add-candidates').click();await bench.waitForFunction(()=>document.getElementById('ring-busy').hidden);await bench.locator('#approve').click();await bench.waitForFunction(()=>!document.getElementById('import-game').disabled);await bench.locator('[data-weapon="wpn_smg_04"]').click();assert.equal(await bench.locator('#import-game').isDisabled(),true);await bench.locator('[data-weapon="wpn_hg_02"]').click();await bench.locator('[data-event="wpn_hg_02_shot"]').click();});
 await check('import changes only the chosen weapon, preserves other assignments and loads in Godot',async()=>{await bench.locator('#approve').click();await bench.locator('#import-game').click();await waitImport();const c=await readCatalog(project),e=c.events.find(e=>e.id==='wpn_hg_02_shot');assert.equal(e.files.length,1);assert.match(e.files[0],/^sonora\/wpn_hg_02_shot_/);assert.deepEqual(c.events.find(e=>e.id==='wpn_hg_01_shot').files,['guns/hg_01_shot_01.wav']);assert.deepEqual(c.registry.ownerField,{preserve:true});await fs.access(path.join(project,'assets/audio/guns/hg_02_shot_01.wav'));await fs.access(path.join(project,'assets/audio',e.files[0]+'.import'));return e.files;});
 await check('empty environment slots clearly use only the assigned main shot of this model',async()=>{await bench.locator('[data-event="wpn_hg_02_shot_room"]').click();assert.match(await bench.locator('#current-info').textContent(),/этой же модели/);assert.equal(await bench.locator('#play-current').isEnabled(),true);await bench.locator('[data-weapon="wpn_smg_04"]').click();await bench.locator('[data-event="wpn_smg_04_shot_room"]').click();assert.equal(await bench.locator('#play-current').isDisabled(),true);});
 async function createThroughUI(name,type,fields={}){await bench.locator('#new-type').click();await bench.locator('#new-name').fill(name);await bench.locator('#new-trigger').selectOption(type);if(fields.hook)await bench.locator('#new-action').selectOption(fields.hook);if(['object_action','area','scene_start'].includes(type)){await bench.locator('#new-scene').selectOption('res://scenes/levels/test_audio.tscn');await bench.locator('#new-node').selectOption('DoorAnchor');}if(type==='scene_start'&&fields.loop)await bench.locator('#new-playback').selectOption('loop');await bench.locator('#new-type-continue').click();await bench.locator('#approve').click();await bench.locator('#import-game').click();await waitImport();return(await readCatalog(project)).events.find(e=>e.name===name);}
 let door,objectDoor,sceneStart,area;
 await check('new named game event is created and bound automatically from the workbench',async()=>{door=await createThroughUI('Двери склада','action',{hook:'door_metal'});assert.equal(door.binding.hook,'door_metal');assert.equal(door.files.length,1);return{id:door.id,binding:door.binding};});
 await check('new event can target a particular door, keeping the global action separate',async()=>{objectDoor=await createThroughUI('Скрип выбранной двери','object_action',{hook:'door_metal'});assert.equal(objectDoor.binding.type,'object_action');assert.equal(objectDoor.binding.node,'DoorAnchor');const c=await readCatalog(project);assert.equal(c.events.find(e=>e.id===door.id).files.length,1);return objectDoor.binding;});
 await check('scene-start and area-enter events need no hand-edited game files',async()=>{sceneStart=await createThroughUI('Появление объекта','scene_start');area=await createThroughUI('Вход в склад','area');assert.equal(sceneStart.binding.type,'scene_start');assert.equal(area.binding.radius,3);return{start:sceneStart.binding,area:area.binding};});
 await check('rename, clear, delete and history undo restore exact event definitions',async()=>{await bench.locator('#mode-events').click();await bench.locator(`[data-event="${door.id}"]`).click();await bench.locator('#rename-type').click();await bench.locator('#edit-name').fill('Переименованная дверь');await bench.locator('#edit-confirm').click();await bench.waitForFunction(()=>document.getElementById('ring-busy').hidden);assert.equal((await readCatalog(project)).events.find(e=>e.id===door.id).name,'Переименованная дверь');await bench.locator('#clear-sound').click();await bench.locator('#edit-confirm').click();await bench.waitForFunction(()=>document.getElementById('ring-busy').hidden);assert.equal((await readCatalog(project)).events.find(e=>e.id===door.id).files.length,0);await bench.locator('#history').click();await bench.locator('[data-undo-import]').first().click();await bench.waitForFunction(()=>document.getElementById('ring-busy').hidden);assert.equal((await readCatalog(project)).events.find(e=>e.id===door.id).files.length,1);await bench.locator('#delete-type').click();await bench.locator('#edit-confirm').click();await bench.waitForFunction(()=>document.getElementById('ring-busy').hidden);assert.equal((await readCatalog(project)).events.some(e=>e.id===door.id),false);await bench.locator('#history').click();await bench.locator('[data-undo-import]').first().click();await bench.waitForFunction(()=>document.getElementById('ring-busy').hidden);assert.equal((await readCatalog(project)).events.some(e=>e.id===door.id),true);});
 await check('actual production Audio routes concrete weapons, distances, doors and area physics',async()=>{
  const script=`extends Node3D
var failed: int = 0
var heard: Array[String] = []
func check(ok: bool, name: String) -> void:
 if not ok:
  failed += 1
  push_error(name)
func _ready() -> void:
 Audio.event_played.connect(func(id: String, _hook: String, _pos: Vector3) -> void: heard.append(id))
 var camera: Camera3D = Camera3D.new()
 add_child(camera)
 camera.current = true
 check(Audio._pick("wpn_smg_04_shot", Vector3.ZERO) == null, "unassigned weapon must be silent")
 check(Audio._pick("shot_pistol", Vector3.ZERO) == null, "legacy shared pool must be silent")
 check(Audio._pick("wpn_hg_01_shot_sup", Vector3.ZERO) == null, "suppressor must not use normal shot")
 check(Audio.resolve_event("wpn_hg_02_shot", "room") == "wpn_hg_02_shot", "room uses only this model's main shot")
 Audio.play("wpn_hg_02_shot", Vector3(2, 0, 0))
 Audio.play("wpn_hg_02_shot", Vector3(100, 0, 0))
 var anchor: Node3D = $DoorAnchor
 Audio.play("door_metal", anchor.global_position, 0.0, 1.0, anchor)
 check(heard.has("${objectDoor.id}"), "specific door binding")
 Audio.play("door_metal", Vector3.ZERO)
 check(heard.has("${door.id}"), "global action remains separate")
 await get_tree().create_timer(0.4).timeout
 check(heard.count("wpn_hg_02_shot") == 2, "near and far use same event")
 check(heard.has("${sceneStart.id}"), "scene trigger starts automatically")
 var body: Player = Player.new()
 body.collision_layer = 2
 body.collision_mask = 0
 var shape: CollisionShape3D = CollisionShape3D.new()
 shape.shape = SphereShape3D.new()
 body.add_child(shape)
 add_child(body)
 body.global_position = Vector3(20, 1, 0)
 await get_tree().physics_frame
 await get_tree().physics_frame
 body.global_position = anchor.global_position
 for i: int in 5:
  await get_tree().physics_frame
 check(heard.has("${area.id}"), "area enter physics automatically plays event")
 var file: FileAccess = FileAccess.open("res://runtime-report.json", FileAccess.WRITE)
 file.store_string(JSON.stringify({"failed": failed, "heard": heard}))
 file.close()
 print("SONORA_V2_RUNTIME_PASS ", failed)
 get_tree().quit(1 if failed else 0)
`;await fs.writeFile(path.join(project,'test.gd'),script);const godot='D:/Steam/steamapps/common/Godot Engine/godot.windows.opt.tools.64.exe';const output=await command(godot,['--headless','--path',project,'res://scenes/levels/test_audio.tscn','--log-file',path.join(project,'runtime.log')]);const result=JSON.parse(await fs.readFile(path.join(project,'runtime-report.json'),'utf8'));assert.equal(result.failed,0,output);assert.ok(!/SCRIPT ERROR/.test(output));return result;
 });
 await check('undo guards later owner edits; unknown registry fields are preserved',async()=>{const service=await new RingService(await fs.mkdtemp(path.join(qa,'service-')),async()=>{}).init();await service.setProject(project);const record=await service.edit({eventId:door.id,operation:'rename',name:'Temporary'}),file=path.join(project,'data/audio_events.json'),after=await fs.readFile(file),changed=JSON.parse(after);changed.ownerLater='keep';await fs.writeFile(file,JSON.stringify(changed));await assert.rejects(()=>service.undo(record.id),/изменён/);assert.equal(JSON.parse(await fs.readFile(file,'utf8')).ownerLater,'keep');await fs.writeFile(file,after);await service.undo(record.id);assert.deepEqual(JSON.parse(await fs.readFile(file,'utf8')).ownerField,{preserve:true});});
 await check('normal and compact layouts, editor transfer and no renderer errors',async()=>{await bench.locator('#mode-weapons').click();await bench.locator('[data-weapon="wpn_hg_01"]').click();await bench.locator('[data-event="wpn_hg_01_shot_room"]').click();await bench.locator('#toasts').evaluate(e=>e.replaceChildren());await bench.screenshot({path:path.join(qa,'workbench-tested.png')});await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows().find(w=>w.getTitle().includes('Ring'))?.setSize(1120,780));await bench.screenshot({path:path.join(qa,'workbench-compact.png')});const forbidden=await bench.evaluate(async()=>{try{await window.sonora.processAudio(new Uint8Array(),{});return false;}catch{return true;}});assert.equal(forbidden,true);assert.deepEqual(report.errors,[]);});
 report.status='pass';report.project=project;
})().catch(async error=>{report.status='fail';report.failure=error.stack;console.error(error);process.exitCode=1;if(bench)await bench.screenshot({path:path.join(qa,'failure.png')}).catch(()=>{});}).finally(async()=>{await fs.mkdir(qa,{recursive:true});await fs.writeFile(path.join(qa,process.env.SONORA_TEST_EXECUTABLE?'report-packaged.json':'report.json'),JSON.stringify(report,null,2));if(app){await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows().forEach(w=>w.destroy())).catch(()=>{});await app.close().catch(()=>{});}});
