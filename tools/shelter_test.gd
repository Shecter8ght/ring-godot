extends Node
## Acceptance-проверка migrated gameplay, профиль до ремейка, collision и связность navmesh.
## Все операции с вещами и сохранениями выполняются в отдельном тестовом файле.

var _fails: int = 0
var _level: Node

func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://shelter_acceptance_test.json", true)
	# Действительный старый профиль копируется только для чтения; оригинал не меняется.
	var old_path: String = ""
	var available: Array = Saves.list()
	if not available.is_empty():
		old_path = String(available[0].path)
	elif FileAccess.file_exists(Profile.PATH):
		old_path = Profile.PATH
	if old_path != "":
		var original: String = FileAccess.get_file_as_string(old_path)
		var file: FileAccess = FileAccess.open("user://shelter_old_save_test.json", FileAccess.WRITE)
		file.store_string(original)
		file.close()
		Profile.use_file("user://shelter_old_save_test.json", false)
		var before: Dictionary = _profile_data()
		get_tree().change_scene_to_file("res://levels/shelter/Shelter_Interior.tscn")
		await _frames(12)
		Profile.save()
		Profile.use_file("user://shelter_old_save_test.json", false)
		_check("real old save: inventory/money/progression roundtrip", _profile_data() == before)
		_check("original old save untouched", FileAccess.get_file_as_string(old_path) == original)
	Profile.use_file("user://shelter_acceptance_test.json", true)
	# Старый формат без hideout_media: additive migration не требует пользовательских действий.
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(Profile.path)) as Dictionary
	fixture.erase("hideout_media")
	var fixture_file: FileAccess = FileAccess.open(Profile.path,FileAccess.WRITE)
	fixture_file.store_string(JSON.stringify(fixture))
	fixture_file.close()
	Profile.use_file(Profile.path,false)
	_check("pre-remake JSON without media loads", Profile.hideout_media.is_empty() and Profile.money == Balance.START_MONEY)
	get_tree().change_scene_to_file("res://levels/shelter/Shelter_Interior.tscn")
	await _frames(20)
	_level = get_tree().current_scene
	var environment: Environment = (_level.get_node("WorldEnvironment") as WorldEnvironment).environment
	for quality: String in ["low","medium","high"]:
		Settings.quality = quality
		Settings.apply_graphics()
		_check("shelter SSR stays disabled on " + quality,not environment.ssr_enabled)
	_check("room signs are sixteen mesh assets",_level.get_node("Signs").get_child_count()==16 and _level.get_node("Signs").find_children("*","Label3D",true,false).is_empty())
	_check("physical emitter size enables soft shadows",(_level.get_node("Lights/HubWest") as Light3D).light_size>.0)
	var pl: Player = _level.get("_player") as Player
	_check("solo inside return area", absf(pl.position.x)<=2.0 and pl.position.z>8.5 and pl.position.z<11)
	_check("three distinct spawns", _spawns_valid())
	_check("quest logical hideout preserved", Quests.world.level == "hideout")
	_check("existing quest anchor moved", _level.get_node("Gameplay/AntonExistingQuestAnchor") is QuestAnchor)
	var tv: HideoutActivity = _level.get_node("Activities/Tv") as HideoutActivity
	var radio: HideoutActivity = _level.get_node("Activities/Radio") as HideoutActivity
	for activity: HideoutActivity in [tv,radio]:
		for state: int in range(1,5):
			activity.request_use()
			await get_tree().create_timer(.25).timeout
			_check("%s channel %d + shader/audio" % [activity.name,state%4], activity.state == state%4 and (activity._screen_mat != null if activity == tv else activity._sound != null))
	# Дождаться фонового синтеза и убедиться, что воспроизведение реально запущено.
	radio._switch(1)
	tv._switch(2)
	await get_tree().create_timer(2.0).timeout
	_check("radio PCM playback", radio._sound.playing and radio._sound.stream != null)
	_check("TV PCM playback and glow", tv._sound.playing and (_level.get_node("Lights/TvGlow") as Light3D).visible)
	Profile.save()
	Profile.use_file(Profile.path,false)
	_check("media saved and loaded", int(Profile.hideout_media.get("tv",-1)) == 2 and int(Profile.hideout_media.get("radio",-1)) == 1)
	var power: ShelterPower = _level.get_node("Gameplay/GeneratorPower") as ShelterPower
	power.request_use()
	await _frames(2)
	_check("generator OFF: normal lights and hum stop",not power.enabled and (_level.get_node("Lights/HubWest") as Light3D).light_energy==0 and not (_level.get_node("Audio/ExistingAudioBridge/GeneratorHum") as AudioStreamPlayer3D).playing)
	_check("backup illumination remains",(_level.get_node("Lights/EmergencyEntry") as Light3D).light_energy>0)
	Profile.use_file(Profile.path,false)
	_check("generator power saved",not bool(Profile.hideout_media.get("power",true)))
	power.request_use()
	await _frames(2)
	_check("generator ON: normal lights and hum return",power.enabled and (_level.get_node("Lights/HubWest") as Light3D).light_energy>0 and (_level.get_node("Audio/ExistingAudioBridge/GeneratorHum") as AudioStreamPlayer3D).playing)
	var beer: HideoutActivity = _level.get_node("Activities/Beer") as HideoutActivity
	beer.request_use()
	_check("beer preserved", float(_level.get("_tipsy"))>0.0)
	(_level.get_node("Activities/SeatM") as HideoutActivity).request_use()
	_check("couch preserved", pl.seated)
	pl.seated = false
	for station: Node in _level.get_node("Stations").get_children():
		(station as HideoutStation).request_use()
		_check("station %s opens existing UI" % station.name, (_level.get("_ui") as HideoutUI).is_open())
		(_level.get("_ui") as HideoutUI).close_ui()
	var money: int = Profile.money
	_check("trader buy", Profile.buy("bandage",1))
	_check("trader money + goods", Profile.money<money and _idx("bandage")>=0)
	money = Profile.money
	_check("trader sell", Profile.sell(_idx("bandage"),1))
	_check("sale returns money", Profile.money>money)
	var index: int = _idx("bandage")
	_check("item storage transfer", index>=0 and Profile.stash_to_backpack(index,1))
	Profile.money = 300000
	Profile.trust = 20
	for pair: Array in [["battery",2],["wires",5],["toolset",1]]:
		ItemDb.add_to(Profile.stash,ItemDb.make(String(pair[0]),int(pair[1])),Profile.stash_grid())
	_check("existing generator module build", Upgrades.build("generator") and Upgrades.level("generator")==1)
	_check("existing workbench module build", Upgrades.build("workbench") and Upgrades.level("workbench")==2)
	ItemDb.add_to(Profile.stash,ItemDb.make("wpn_ar_03",1),Profile.stash_grid())
	var gun_index: int = _idx("wpn_ar_03")
	_check("weapon storage equip", gun_index>=0 and Profile.equip_from_stash(gun_index))
	ItemDb.add_to(Profile.stash,ItemDb.make("grip_vertical_01",1),Profile.stash_grid())
	_check("workbench install attachment", Profile.install_mod("primary",_idx("grip_vertical_01")))
	var saved: Dictionary = _profile_data()
	# Инвентарь в руках синхронизируется в _process перед сравнением сохранения.
	await _frames(2)
	saved = _profile_data()
	Profile.save()
	Profile.use_file(Profile.path,false)
	_check("save after trade/modules/workbench/storage", _profile_data()==saved)
	if _profile_data()!=saved:
		print("SAVE_BEFORE ",JSON.stringify(saved))
		print("SAVE_AFTER ",JSON.stringify(_profile_data()))
	_navigation_paths()
	await _walk_stairs(pl)
	_check("finished environment has no visible primitives", _primitive_count()==0)
	print("SHELTER_ACCEPTANCE failures=%d" % _fails)
	# Не освобождать activity во время фонового PCM worker.
	await get_tree().create_timer(.5).timeout
	_level.queue_free()
	await get_tree().create_timer(.4).timeout
	get_tree().quit(1 if _fails>0 else 0)

func _profile_data() -> Dictionary:
	# JSON числа возвращает как float; сравниваем сохранённые значения, а не Variant int/float.
	return JSON.parse_string(JSON.stringify({"money":Profile.money,"stash":Profile.stash,"equipment":Profile.equipment,"backpack":Profile.backpack,"modules":Profile.modules,"quests":Profile.quests,"flags":Profile.flags,"floor":Profile.floor,"trust":Profile.trust})) as Dictionary

func _spawns_valid() -> bool:
	var nodes: Array[Node] = _level.get_node("Gameplay/SpawnPoints").get_children()
	return nodes.size()==3 and (nodes[0] as Node3D).position.distance_to((nodes[1] as Node3D).position)>1.2 and (nodes[1] as Node3D).position.distance_to((nodes[2] as Node3D).position)>1.2

func _navigation_paths() -> void:
	var map: RID = (_level as Node3D).get_world_3d().navigation_map
	for destination: Vector3 in [Vector3(0,0,4),Vector3(-11,0,-8),Vector3(-11,0,-2),Vector3(-10.2,0,4),Vector3(11,0,-8),Vector3(11,0,-2),Vector3(11,0,4),Vector3(1,2.6,-7.25)]:
		var path: PackedVector3Array = NavigationServer3D.map_get_path(map,Vector3(0,0,9.55),destination,true)
		print("NAV endpoint ", path[-1] if not path.is_empty() else Vector3.INF)
		_check("navmesh reaches %s" % destination, path.size()>1 and path[-1].distance_to(destination)<.8)

func _walk_stairs(pl: Player) -> void:
	pl.global_position = Vector3(5.3,.05,-1.8)
	pl.stance = Player.Stance.STAND
	pl._apply_stance()
	var body: Node3D = pl.get_node("Body") as Node3D
	body.rotation.y = PI
	var rig: CameraRig = _level.get_node("CameraRig") as CameraRig
	rig.rotation.y = 0
	Input.action_press("move_forward")
	for i: int in range(240):
		await get_tree().physics_frame
		if pl.global_position.z < -7.1:
			break
	Input.action_release("move_forward")
	await get_tree().create_timer(.12).timeout
	print("STAIR physical end ",pl.global_position)
	_check("physical stairs reach upper landing", pl.global_position.y>2.55 and pl.global_position.z < -6.7)
	Input.action_press("move_left")
	await get_tree().create_timer(1.35).timeout
	Input.action_release("move_left")
	_check("upper landing connects to sleeping floor",pl.global_position.y>2.55 and pl.global_position.x<3)
	pl.global_position = Vector3(5.3,2.62,-7.3)
	Input.action_press("move_forward")
	await get_tree().create_timer(.8).timeout
	Input.action_release("move_forward")
	_check("upper rear guard prevents falling",pl.global_position.y>2.55 and pl.global_position.z > -8.2)

func _primitive_count() -> int:
	var count: int = 0
	for n: Node in _level.find_children("*","GeometryInstance3D",true,false):
		if n is MeshInstance3D and (n as MeshInstance3D).is_visible_in_tree() and (n as MeshInstance3D).mesh is PrimitiveMesh:
			if not n.is_in_group("players") and not "Player_" in String(n.get_path()) and not "CameraRig" in String(n.get_path()) and not "QuestWorld" in String(n.get_path()):
				count+=1
		if n is CSGShape3D:count+=1
	return count

func _idx(id: String) -> int:
	for i: int in range(Profile.stash.size()):
		if String(Profile.stash[i].id)==id:return i
	return -1

func _frames(n: int) -> void:
	for i: int in range(n):await get_tree().process_frame

func _check(what: String,ok: bool) -> void:
	if not ok:_fails+=1
	print("[%s] %s" % ["ok" if ok else "FAIL",what])
