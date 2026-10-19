extends Node
## Вид «как с камеры» (CameraLook): одни и те же кадры с эффектами камеры и без — убежище, рейд днём
## и ночью; кадр на повороте головы (размытие в движении). Средняя яркость кадров — в вывод, чтобы
## видеть, что привыкание глаза не превращает ночь в день. Снимки — в LOOK_OUT (по умолчанию
## user://look_shots/), docs/screens не трогает.
## tools/godot.cmd res://tools/look_shots.tscn

const HIDEOUT_SHOTS: Array = [
	["hub", Vector3(-4.5, 0.05, 4.2), Vector3(1, 1.25, -2)],
	["firing_line", Vector3(23.2, 0.05, .6), Vector3(55, 1.35, .6)],
	["boilers", Vector3(25.5, 0.05, -4.2), Vector3(40, 3.2, -9)],
	["lamp", Vector3(-4.5, 0.05, 4.2), Vector3(-1.5, 3.6, 0.5)],
]

var _out: String = ""


func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	RaidEvents.enabled = false
	_out = OS.get_environment("LOOK_OUT")
	if _out == "":
		_out = ProjectSettings.globalize_path("user://look_shots/")
	DirAccess.make_dir_recursive_absolute(_out)
	var only: String = OS.get_environment("LOOK_ONLY")
	if only == "" or "hideout" in only:
		await _hideout()
	if "weather" in only:
		await _hideout_weather()
	if only == "" or "raid" in only:
		for t: String in ["day", "night"]:
			await _raid(t)
	get_tree().quit()


func _hideout() -> void:
	Profile.use_file("user://look_shots_test.json", true)
	Profile.modules.generator = 1
	get_tree().change_scene_to_file("res://scenes/levels/hideout.tscn")
	await _frames(150)
	var level: Node = get_tree().current_scene
	var pl: Player = level.get("_player") as Player
	var shots: Array = HIDEOUT_SHOTS.duplicate()
	# доп. кадры: LOOK_EXTRA="имя:x,y,z:x,y,z;…" — откуда (ноги) и куда смотреть
	for spec: String in OS.get_environment("LOOK_EXTRA").split(";", false):
		var parts: PackedStringArray = spec.split(":")
		var a: PackedFloat64Array = parts[1].split_floats(",")
		var b: PackedFloat64Array = parts[2].split_floats(",")
		shots.append([parts[0], Vector3(a[0], a[1], a[2]), Vector3(b[0], b[1], b[2])])
	for shot: Array in shots:
		await _pair(pl, "hideout_" + String(shot[0]), shot[1], shot[2])
	await _turn(pl, "hideout_turn", Vector3(-4.5, 0.05, 4.2), Vector3(1, 1.25, -2))
	level.queue_free()
	get_tree().current_scene = null
	await _frames(5)


## Погода за окнами убежища (ShelterWeather): те же кадры при разных условиях следующего рейда.
func _hideout_weather() -> void:
	Profile.use_file("user://look_shots_test.json", true)
	Profile.modules.generator = 1
	get_tree().change_scene_to_file("res://scenes/levels/hideout.tscn")
	await _frames(150)
	var level: Node = get_tree().current_scene
	var pl: Player = level.get("_player") as Player
	var weather: ShelterWeather = level.find_child("Weather", true, false) as ShelterWeather
	Settings.lens_fx = true
	Settings.motion_blur = false
	Settings.changed.emit()
	var views: Array = [["hall", Vector3(36, 0.05, -8), Vector3(36, 3.0, 7)], ["floor", Vector3(30, 0.05, -6), Vector3(36, 0.3, 3)], ["hub", Vector3(-4.5, 0.05, 4.2), Vector3(1, 1.25, -2)]]
	for cond: Array in [["day", "clear"], ["day", "rain"], ["dusk", "clear"], ["dusk", "overcast"], ["night", "clear"]]:
		Profile.next_conditions = {"time": cond[0], "weather": cond[1], "power": "on"}
		weather.refresh(true)
		for v: Array in views:
			_place(pl, v[1], v[2])
			await _frames(120)
			_save("weather_%s_%s_%s" % [cond[0], cond[1], v[0]])
	level.queue_free()
	get_tree().current_scene = null
	await _frames(5)


func _raid(time: String) -> void:
	Profile.use_file("user://look_shots_raid.json", true)
	Profile.ensure()
	RaidConditions.from_host = {"time": time, "weather": "clear", "power": "on"}
	var level: Node = load("res://scenes/levels/f1_ring.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m: Node in level.get_node("Marauders").get_children():
		m.queue_free()
	var pl: Player = Raid.current.local_player()
	pl.health.hp = 1e9
	var at: Vector3 = SectorBuilder.polar(-100.0, 72.0)
	await _pair(pl, "raid_%s_mall" % time, at, at + Vector3(sin(deg_to_rad(90.0)), 0.0, cos(deg_to_rad(90.0))) * 10.0 + Vector3(0, 1.5, 0))
	var out: Vector3 = SectorBuilder.polar(-96.0, 150.0)
	await _pair(pl, "raid_%s_street" % time, out, out + Vector3(0, 1.0, -10))
	if time == "day":
		# в прицеле: ствольная коробка у лица мягче, дальнее резкое
		Input.action_press("aim")
		await _pair(pl, "raid_day_ads", out, out + Vector3(0, 1.4, -10))
		Input.action_release("aim")
		# поворот с оружием в руках: за руками и стволом не должно тянуться хвоста
		await _turn(pl, "raid_day_turn", out, out + Vector3(0, 1.0, -10))
	level.queue_free()
	get_tree().current_scene = null
	await _frames(5)


## Тот же кадр без эффектов камеры и с ними.
func _pair(pl: Player, label: String, at: Vector3, look_at: Vector3) -> void:
	for on: bool in [false, true]:
		Settings.lens_fx = on
		Settings.motion_blur = false
		Settings.changed.emit()
		_place(pl, at, look_at)
		await _frames(150)
		_save("%s_%s" % [label, "on" if on else "off"])


## Поворот головы на ходу: кадр в середине поворота, с размытием и без.
func _turn(pl: Player, label: String, at: Vector3, look_at: Vector3) -> void:
	Settings.lens_fx = true
	for blur: bool in [false, true]:
		Settings.motion_blur = blur
		Settings.changed.emit()
		_place(pl, at, look_at)
		await _frames(60)
		var rig: CameraRig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
		for i: int in range(12):
			rig._look_yaw += 0.045
			await get_tree().process_frame
		_save("%s_%s" % [label, "blur" if blur else "sharp"])


func _place(pl: Player, at: Vector3, look_at: Vector3) -> void:
	pl.global_position = at
	pl.velocity = Vector3.ZERO
	var rig: CameraRig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	var eye: Vector3 = at + Vector3(0, 1.62, 0)
	var d: Vector3 = (look_at - eye).normalized()
	rig._look_yaw = atan2(d.x, d.z)
	rig._look_pitch = asin(clampf(d.y, -1.0, 1.0))


func _save(label: String) -> void:
	var img: Image = get_viewport().get_texture().get_image()
	img.save_png(_out.path_join(label + ".png"))
	var sum: float = 0.0
	var n: int = 0
	for y: int in range(0, img.get_height(), 16):
		for x: int in range(0, img.get_width(), 16):
			sum += img.get_pixel(x, y).get_luminance()
			n += 1
	print("look_shots: %s средняя яркость %.3f" % [label, sum / maxf(1.0, float(n))])


func _frames(n: int) -> void:
	for i: int in range(n):
		await get_tree().process_frame
