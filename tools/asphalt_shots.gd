extends Node
## Мокрый асфальт (шейдер wet_asphalt): снимки у фасада кольца — сухо, сыро, мокро с лужами;
## от первого лица вдоль фасада и в изометрии. Ночь по умолчанию (ASPH_TIME=day|dusk|night).
## Нужен рендер — только с окном; docs/screens/asphalt_*.png.
## godot --path . res://tools/asphalt_shots.tscn

func _ready() -> void:
	RaidEvents.enabled = false
	var tod := OS.get_environment("ASPH_TIME") if OS.get_environment("ASPH_TIME") != "" else "night"
	RaidConditions.from_host = {"time": tod, "weather": "rain", "power": "on"}
	Profile.use_file("user://profile_asphalt_shots.json", true)
	Profile.ensure()
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/f1_ring.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in level.get_node("Marauders").get_children():
		m.queue_free()
	var me := Raid.current.local_player()
	me.health.hp = 1e9
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	var we := level.find_child("WorldEnvironment", true, false) as WorldEnvironment
	print("asphalt_shots: SSR ", we.environment.ssr_enabled if we else false, ", качество ", Settings.quality)
	var weather := RaidWeather.current
	# сырость задаём сами — погода её не двигает
	weather.set_process(false)
	var at := SectorBuilder.polar(-100.0, 134.0)
	var look := SectorBuilder.polar(-88.0, 127.0) + Vector3(0, 2.5, 0)
	me.global_position = at + Vector3(0, 0.1, 0)
	await _frames(20)
	for st in [["dry", 0.0, 0.0, 0.0], ["damp", 0.45, 0.0, 0.6], ["wet", 1.0, 0.75, 1.0]]:
		weather.wet = float(st[1])
		weather.puddles = float(st[2])
		weather._push_wet(float(st[3]))
		(level.find_child("Rain", true, false) as RainFx).set_amount(float(st[3]))
		CameraRig.first_person_mode = true
		await _frames(10)
		var d := look - me.eye_position()
		rig._look_yaw = atan2(d.x, d.z)
		rig._look_pitch = atan2(d.y, Vector2(d.x, d.z).length()) - 0.12
		await _frames(60)
		var ce := get_viewport().get_camera_3d()
		var env := get_viewport().find_world_3d().environment if get_viewport().find_world_3d().environment else (we.environment if we else null)
		print("asphalt_shots: камера %s, env камеры %s, SSR мира %s, msaa %d, scale %.2f" % [ce.name, ce.environment, env.ssr_enabled if env else "—", get_viewport().msaa_3d, get_viewport().scaling_3d_scale])
		if OS.get_environment("ASPH_NOMSAA") == "1":
			get_viewport().msaa_3d = Viewport.MSAA_DISABLED
			await _frames(30)
		_save("asphalt_%s_%s_fps" % [tod, st[0]])
		CameraRig.first_person_mode = false
		await _frames(40)
		_save("asphalt_%s_%s_iso" % [tod, st[0]])
	get_tree().quit(0)


func _save(n: String) -> void:
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))
	print("asphalt_shots: ", n)


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame
