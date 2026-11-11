const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process');
const{fixture,sineWav}=require('./ring-v2-fixture.cjs'),{RingService}=require('../src/ring-service.cjs');
(async()=>{
  const root=path.resolve(__dirname,'..'),qa=path.resolve(root,'../../_asset_src/sonora_qa/qa-fx');await fs.mkdir(qa,{recursive:true});const{root:project}=await fixture(qa),profile=await fs.mkdtemp(path.join(qa,'safety-'));
  const run=async args=>{const result=spawnSync(path.join(root,'vendor/ffmpeg.exe'),['-hide_banner','-loglevel','error','-nostdin',...args],{windowsHide:true});if(result.status!==0)throw new Error(String(result.stderr));};
  const service=await new RingService(profile,run).init();await service.setProject(project);
  const staged=await service.stage(new Uint8Array(sineWav()),'synthetic.wav');await service.approve({eventId:'wpn_hg_02_shot_outdoor',ids:[staged.id],mode:'replace',provenance:{license:'Собственный звук / ИИ'}});
  await fs.writeFile(path.join(project,'broken.gd'),'class_name BrokenFixture\nextends Node\nvar syntax_error =\n');
  await fs.appendFile(path.join(project,'project.godot'),'\n[autoload]\nBroken="*res://broken.gd"\n');
  const result=await service.importApproved(service.approval.id);assert.equal(result.godot.ok,false);assert.match(result.godot.log,/ERROR/);await fs.access(path.join(project,'assets/audio',result.record.created[0]));
  console.log('PASS Godot project errors are reported while valid imported audio remains available');
  const credits=path.join(project,'assets/CREDITS.md'),after=await fs.readFile(credits,'utf8'),manual=after+'\nOwner subsequent edit\n';await fs.writeFile(credits,manual);
  await assert.rejects(()=>service.undo(result.record.id),/изменён/);assert.equal(await fs.readFile(credits,'utf8'),manual);
  console.log('PASS undo refuses to overwrite subsequent owner edits');
  await fs.writeFile(credits,after);await service.undo(result.record.id);assert.equal(await fs.readFile(credits,'utf8'),'# Test sources\nOwner text\n');
  console.log('PASS backup restores the original state after conflict is resolved');
  await fs.writeFile(path.join(qa,'safety-report.json'),JSON.stringify({status:'pass',checks:3,fixture:project,godotErrorReported:!result.godot.ok,subsequentEditsPreserved:true},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
