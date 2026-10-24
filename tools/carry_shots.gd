extends Node
## Стойка оружия от первого лица: «от бедра» и «наискосок» (Balance.WEAPON_CARRY) у каждого ствола
## в слотах песочницы — снимки docs/screens/carry_<ствол>_<hip|low>.png.
## Подбор позы: CARRY_VARIANTS="yaw=35 pitch=30 roll=-8 back=0.25 sx=0 sy=0 sz=0 px=… py=… pz=…;…" — свои числа
## поверх Balance (любые из них), снимки …_low_v1, _v2;
## CARRY_ONLY=wpn_ar_01,wpn_hg_02 — только эти стволы.
## tools/godot.cmd --windowed --resolution 1280x720 res://tools/carry_shots.tscn

const OUT := "res://docs/screens"

var _me: Player
var _rig: CameraRig


func _ready() -> void:
	if DisplayServer.get_name() == "headless":
		push_error("carry_shots: снимки — только с окном")
		get_tree().quit(1)
		return
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in level.get_node("Marauders").get_children():
		m.queue_free()
	_me = Raid.current.local_player()
	_me.health.invulnerable = true
	_rig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	await _frames(60)
	_rig._look_pitch = deg_to_rad(-4.0)
	var only := OS.get_environment("CARRY_ONLY").split(",", false)
	var variants := OS.get_environment("CARRY_VARIANTS").split(";", false)
	for key: Variant in _me.weapon_keys():
		_me._switch(String(key), false)
		await _frames(90)
		var wid: String = _me.weapon_id
		if not only.is_empty() and not wid in only:
			continue
		_me.carry_low = false
		await _frames(60)
		_shot("carry_%s_hip" % wid)
		if variants.is_empty():
			_me.carry_low = true
			await _frames(60)
			_shot("carry_%s_low" % wid)
			continue
		var clips: bool = _rig._viewmodel is ViewmodelClips
		var base: Dictionary = _rig._carry_spec(wid, clips).duplicate()
		for i in variants.size():
			var pose := base.duplicate()
			for pair: String in variants[i].split(" ", false):
				var kv := pair.split("=")
				match kv[0]:
					"yaw": pose.yaw_deg = float(kv[1])
					"pitch": pose.pitch_deg = float(kv[1])
					"roll": pose.roll_deg = float(kv[1])
					"back": pose.pivot_back = float(kv[1])
					"sx": pose.shift = Vector3(float(kv[1]), (pose.shift as Vector3).y, (pose.shift as Vector3).z)
					"sy": pose.shift = Vector3((pose.shift as Vector3).x, float(kv[1]), (pose.shift as Vector3).z)
					"sz": pose.shift = Vector3((pose.shift as Vector3).x, (pose.shift as Vector3).y, float(kv[1]))
					"px": pose.clips_pivot = Vector3(float(kv[1]), (pose.clips_pivot as Vector3).y, (pose.clips_pivot as Vector3).z)
					"py": pose.clips_pivot = Vector3((pose.clips_pivot as Vector3).x, float(kv[1]), (pose.clips_pivot as Vector3).z)
					"pz": pose.clips_pivot = Vector3((pose.clips_pivot as Vector3).x, (pose.clips_pivot as Vector3).y, float(kv[1]))
			_rig._carry_specs[CameraRig.carry_key(wid, clips)] = pose
			_me.carry_low = true
			await _frames(60)
			_shot("carry_%s_low_v%d" % [wid, i + 1])
			_me.carry_low = false
			await _frames(30)
	get_tree().quit(0)


func _shot(name: String) -> void:
	var img := get_viewport().get_texture().get_image()
	img.resize(960, 540)
	img.save_png(ProjectSettings.globalize_path("%s/%s.png" % [OUT, name]))
	print("   снимок %s" % name)


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame
