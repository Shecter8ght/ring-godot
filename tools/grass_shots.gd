extends Node
## Трава зоны 1 (DistrictGrass): снимки от первого лица — поперёк поля, под ноги, низко (лёжа),
## след после прохода (примятая полоса) и она же через время (поднялась), против солнца на закате;
## кадры в секунду с травой и без неё. Нужен рендер — только с окном.
## tools/godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/grass_shots.tscn → docs/screens/grass_*.png
## GRASS_TIME=day|dusk|night (умолч. day), GRASS_AT=x:z — другое место, GRASS_SUFFIX — к имени снимков,
## GRASS_ONLY=eye,down — выборочно.

const SCENE := "res://scenes/levels/zone01_mall.tscn"
## Поле с плотной травой на западе района (карта плотности assets/terrain/zone01_grass.png).
const DEFAULT_AT := Vector2(-255.0, -55.0)

var _suffix: String = ""
var _only: PackedStringArray = PackedStringArray()
var _level: Node3D
var _me: Player
var _rig: CameraRig


func _ready() -> void:
	RaidEvents.enabled = false
	var tod: String = OS.get_environment("GRASS_TIME") if OS.get_environment("GRASS_TIME") != "" else "day"
	_suffix = OS.get_environment("GRASS_SUFFIX")
	if OS.get_environment("GRASS_ONLY") != "":
		_only = OS.get_environment("GRASS_ONLY").split(",")
	RaidConditions.from_host = {"time": tod, "weather": "clear", "power": "on"}
	_level = (load(SCENE) as PackedScene).instantiate() as Node3D
	get_tree().root.add_child.call_deferred(_level)
	await get_tree().process_frame
	get_tree().current_scene = _level
	while _level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in _level.get_node("Marauders").get_children():
		m.queue_free()
	_me = Raid.current.local_player()
	_me.health.hp = 1e9
	_me.health.max_hp = 1e9
	_rig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	CameraRig.first_person_mode = true
	var at := DEFAULT_AT
	if OS.get_environment("GRASS_AT") != "":
		var p := OS.get_environment("GRASS_AT").split(":")
		at = Vector2(float(p[0]), float(p[1]))
	var spot := _ground(Vector3(at.x, 0.0, at.y))
	_me.global_position = spot + Vector3.UP * 0.1
	_me.set_physics_process(false)
	# клетки травы строятся по несколько за кадр — ждём, пока покроют весь радиус
	await _frames(240)
	var ahead := spot + Vector3(0.0, 0.0, -14.0)
	_look(ahead + Vector3.UP * 0.4)
	await _frames(30)
	await _shot("eye")
	_look(spot + Vector3(0.0, 0.0, -2.2))
	await _frames(20)
	await _shot("down")
	# лёжа: глаз у самой земли
	_me.global_position = spot + Vector3.UP * 0.1 + Vector3(0.0, -1.25, 0.0)
	_look(ahead + Vector3(0.0, -0.9, 0.0))
	await _frames(20)
	await _shot("low")
	_me.global_position = spot + Vector3.UP * 0.1
	# проход: игрок идёт 8 м поперёк поля — трава примята полосой, потом поднимается
	var from := spot + Vector3(-4.0, 0.0, -5.0)
	var to := spot + Vector3(4.0, 0.0, -5.0)
	for i in range(160):
		var k := float(i) / 159.0
		_me.global_position = _ground(from.lerp(to, k)) + Vector3.UP * 0.1
		await get_tree().physics_frame
	var tr := GrassTrample.current
	print("grass_shots: примято клеток %d, на следу %.2f, рядом %.2f" % [tr.active_cells() if tr else -1,
		tr.pressed_at(spot + Vector3(0.0, 0.0, -5.0)) if tr else -1.0, tr.pressed_at(spot + Vector3(0.0, 0.0, -7.0)) if tr else -1.0])
	_me.global_position = spot + Vector3(0.0, 0.1, 1.5)
	_look(spot + Vector3(0.0, 0.0, -5.0))
	await _frames(4)
	await _shot("trail")
	_me.global_position = spot + Vector3(1.0, 0.1, -2.6)
	_look(spot + Vector3(-0.5, -0.2, -5.0))
	await _frames(4)
	await _shot("trail_near")
	await get_tree().create_timer(float(Balance.GRASS.trample_recover_sec) * 0.75).timeout
	await _shot("trail_later")
	# против низкого солнца — просвет травинок
	var sun := _level.find_child("Sun", true, false) as DirectionalLight3D
	if sun:
		var sd := sun.global_basis.z
		_look(spot + Vector3(sd.x, 0.0, sd.z).normalized() * 12.0 + Vector3.UP * 0.6)
		await _frames(20)
		await _shot("backlit")
	# кадры в секунду: та же точка с травой и без
	_look(ahead + Vector3.UP * 0.4)
	await _frames(30)
	var fps_on: float = await _fps(120)
	var grass := _level.find_child("Grass", true, false) as Node3D
	var fps_off: float = fps_on
	var fps_lawn: float = fps_on
	var fps_scan: float = fps_on
	if grass:
		# только густой ярус (пучки-сканы спрятаны) и только сканы
		for part: String in ["Cell_", "Lawn_"]:
			for c in grass.get_children():
				if c is Node3D:
					(c as Node3D).visible = not String(c.name).begins_with(part)
			await _frames(10)
			var f: float = await _fps(120)
			if part == "Cell_":
				fps_lawn = f
			else:
				fps_scan = f
		for c in grass.get_children():
			if c is Node3D:
				(c as Node3D).visible = true
		grass.visible = false
		await _frames(10)
		fps_off = await _fps(120)
		grass.visible = true
	print("grass_shots: кадров в секунду: вся трава %.0f, только густой ярус %.0f, только пучки-сканы %.0f, без травы %.0f" % [fps_on, fps_lawn, fps_scan, fps_off])
	if grass and grass.has_method("stats"):
		print("grass_shots: ", grass.call("stats"))
	get_tree().quit(0)


func _ground(p: Vector3) -> Vector3:
	var q := PhysicsRayQueryParameters3D.create(p + Vector3.UP * 60.0, p + Vector3.DOWN * 60.0, Hitscan.LAYER_WORLD)
	var hit: Dictionary = _level.get_world_3d().direct_space_state.intersect_ray(q)
	return (hit.position as Vector3) if not hit.is_empty() else p


func _look(target: Vector3) -> void:
	var d := target - _me.eye_position()
	_rig._look_yaw = atan2(d.x, d.z)
	_rig._look_pitch = atan2(d.y, Vector2(d.x, d.z).length())


func _shot(name: String) -> void:
	if not _only.is_empty() and not name in _only:
		return
	await RenderingServer.frame_post_draw
	var path := "res://docs/screens/grass_%s%s.png" % [name, _suffix]
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path(path))
	print("grass_shots: ", path)


func _fps(n: int) -> float:
	var t0 := Time.get_ticks_usec()
	await _frames(n)
	return float(n) / (float(Time.get_ticks_usec() - t0) / 1e6)


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame
