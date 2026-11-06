const fs=require('node:fs/promises'),path=require('node:path');
const{sineWav}=require('./ring-fixture.cjs');
async function fixture(parent){
 const root=await fs.mkdtemp(path.join(parent,'Ring-v2-')),game='E:/Games/RING-godot';
 for(const folder of ['data','src/audio','src/core','stubs','scenes/levels','assets/audio/sonora','assets/audio/guns','assets/audio/LICENSES'])await fs.mkdir(path.join(root,folder),{recursive:true});
 for(const file of ['audio_events.json','audio_actions.json','weapons.json','weapon_sound_slots.json','audio_surfaces.json','audio_mix.json'])await fs.copyFile(path.join(game,'data',file),path.join(root,'data',file));
 const registry=JSON.parse(await fs.readFile(path.join(root,'data/audio_events.json'),'utf8'));registry.ownerField={preserve:true};for(const e of registry.events)e.files=[];
 const a=registry.events.find(e=>e.id==='wpn_hg_01_shot'),b=registry.events.find(e=>e.id==='wpn_hg_02_shot');a.files=['guns/hg_01_shot_01.wav'];b.files=['guns/hg_02_shot_01.wav'];
 await fs.writeFile(path.join(root,'data/audio_events.json'),JSON.stringify(registry,null,2));
 await fs.writeFile(path.join(root,'assets/audio/guns/hg_01_shot_01.wav'),sineWav(180,.2,1));await fs.writeFile(path.join(root,'assets/audio/guns/hg_02_shot_01.wav'),sineWav(400,.2,1));
 await fs.writeFile(path.join(root,'assets/CREDITS.md'),'# Test sources\nOwner text\n');
 for(const file of ['src/audio/audio_system.gd','src/audio/acoustic_place.gd','src/core/balance.gd'])await fs.copyFile(path.join(game,file),path.join(root,file));
 const stubs={
 'lab_tuning.gd':'class_name LabTuning\nextends RefCounted\nstatic func value(_domain: String, key: String) -> Variant:\n\tif key.ends_with("_tint"):\n\t\treturn Color.WHITE\n\treturn 1.0\n',
 'settings.gd':'extends Node\nvar headset: Dictionary = {}\nstatic func bus_for(kind: String) -> StringName:\n\treturn &"Master"\n',
 'hitscan.gd':'class_name Hitscan\nextends RefCounted\nconst LAYER_WORLD: int = 1\nconst LAYER_PLAYER: int = 2\nconst LAYER_DOOR: int = 8\n',
 'player.gd':'class_name Player\nextends CharacterBody3D\nfunc is_local() -> bool:\n\treturn true\n',
 'surfaces.gd':'class_name Surfaces\nextends RefCounted\nstatic func kind_at(hit: Dictionary) -> String:\n\treturn String((hit.collider as Node).get_meta("surface", "concrete"))\n',
 'water_body.gd':'class_name WaterBody\nextends RefCounted\nstatic func depth_at(_pos: Vector3) -> float:\n\treturn 0.0\n',
 'raid_weather.gd':'class_name RaidWeather\nextends Node3D\nstatic var current: RaidWeather\nvar wet: float = 0.0\nvar puddles: float = 0.0\n'
 };
 for(const[name,text]of Object.entries(stubs))await fs.writeFile(path.join(root,'stubs',name),text);
 await fs.writeFile(path.join(root,'project.godot'),'config_version=5\n[application]\nconfig/name="Sonora v2 isolated test"\n[audio]\ndriver/driver="Dummy"\n[autoload]\nBalance="*res://src/core/balance.gd"\nSettings="*res://stubs/settings.gd"\nAudio="*res://src/audio/audio_system.gd"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n');
 await fs.writeFile(path.join(root,'scenes/levels/test_audio.tscn'),'[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://test.gd" id="1"]\n[node name="AudioRoom" type="Node3D"]\nscript = ExtResource("1")\n[node name="DoorAnchor" type="Marker3D" parent="."]\nposition = Vector3(5, 1, 0)\n');
 await fs.writeFile(path.join(root,'test.gd'),'extends Node3D\nfunc _ready() -> void:\n\tget_tree().quit()\n');
 return{root,registry};
}
module.exports={fixture,sineWav};
