extends Node
## Дождь шейдерами: карта «что над головой» (RainOcclusion) совпадает с тем, что под лучом сверху
## (крыши, перекрытия, земля), под крышей капель нет. Нужен рендер — только с окном; снимки
## docs/screens/rain_*.png (изометрия на улице и у здания, от первого лица снаружи и изнутри).
## godot --path . res://tools/rain_test.tscn

var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": String(OS.get_environment("RAIN_TIME")) if OS.get_environment("RAIN_TIME") != "" else "day", "weather": "rain", "power": "on"}
	Profile.use_file("user://profile_rain_test.json", true)
	Profile.ensure()
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in level.get_node("Marauders").get_children():
		m.queue_free()
	var me := Raid.current.local_player()
	me.health.hp = 1e9
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	var rain := level.find_child("Rain", true, false) as RainFx
	_check("дождь — шейдерный узел", rain != null, "")
	if rain == null or DisplayServer.get_name() == "headless":
		print("rain_test: провалено %d" % _fails)
		get_tree().quit(_fails)
		return
	# карта у края здания: и крыша 1F, и улица
	var edge := SectorBuilder.polar(-92.0, 118.0)
	me.global_position = edge + Vector3(0, 0.1, 0)
	await _frames(30)
	await RenderingServer.frame_post_draw
	var img := rain.occlusion.texture().get_image()
	var space := me.get_world_3d().direct_space_state
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	var ok := 0
	var total := 0
	var worst := ""
	for i in range(400):
		var x := rain.occlusion.center.x + rng.randf_range(-40.0, 40.0)
		var z := rain.occlusion.center.z + rng.randf_range(-40.0, 40.0)
		var top := _top(space, x, z)
		if top == -INF:
			continue
		total += 1
		var h := rain.occlusion.height_at(img, x, z)
		if absf(h - top) < 0.4:
			ok += 1
		elif worst == "":
			worst = "(%.0f, %.0f): карта %.2f, лучи %.2f" % [x, z, h, top]
	# под потолком магазина — карта знает потолок (иначе там капает и мокро)
	var inside := SectorBuilder.polar(-92.0, 112.0)
	var ti := _top(space, inside.x, inside.z)
	var mi := rain.occlusion.height_at(img, inside.x, inside.z)
	_check("под потолком: карта видит потолок", absf(mi - ti) < 0.4 and mi > 3.0, "карта %.2f, лучи %.2f" % [mi, ti])
	_check("карта высот = лучи сверху", total > 100 and float(ok) / total > 0.9, "%d из %d; %s" % [ok, total, worst])
	await get_tree().create_timer(14.0).timeout
	for spot in [["iso_out", SectorBuilder.polar(-96.0, 150.0), false, 0.0, 0.0], ["iso_edge", edge, false, 0.0, 0.0],
			["fps_out", SectorBuilder.polar(-96.0, 150.0), true, -40.0, -0.12], ["fps_in", SectorBuilder.polar(-92.0, 112.0), true, 180.0, 0.05]]:
		me.global_position = (spot[1] as Vector3) + Vector3(0, 0.1, 0)
		CameraRig.first_person_mode = bool(spot[2])
		await _frames(12)
		if bool(spot[2]):
			rig._look_yaw = deg_to_rad(float(spot[3]))
			rig._look_pitch = float(spot[4])
		await _frames(50)
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/rain_%s%s.png" % [spot[0], OS.get_environment("RAIN_SUFFIX")]))
	CameraRig.first_person_mode = false
	print("rain_test: провалено %d" % _fails)
	get_tree().quit(_fails)


## Самая верхняя поверхность: луч вниз до земли, потом вверх, пока есть во что упереться
## (потолок смотрит вниз — сверху луч его не видит, снизу видит). Персонажи не в счёт.
func _top(space: PhysicsDirectSpaceState3D, x: float, z: float) -> float:
	var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(x, 60.0, z), Vector3(x, -3.0, z)))
	if hit.is_empty() or hit.collider is CharacterBody3D:
		return -INF
	var y := float((hit.position as Vector3).y)
	for i in range(4):
		var up := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(x, y + 0.05, z), Vector3(x, 60.0, z)))
		if up.is_empty() or up.collider is CharacterBody3D:
			break
		y = float((up.position as Vector3).y)
	return y


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
