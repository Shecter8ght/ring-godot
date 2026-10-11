extends Node3D
## Записи владельца: сухо/мокро/после дождя/навес, ходьба и бег, положение источника, запасной звук.

var _fails: int = 0
var _heard: Array[String] = []


func _ready() -> void:
	# Изолированное сохранение до отложенного Contracts.sync, настоящий профиль не трогаем.
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://tools/_probe"))
	Profile.use_file("res://tools/_probe/wet_steps_test_profile.json", true)
	get_tree().current_scene = self
	var camera: Camera3D = Camera3D.new()
	add_child(camera)
	camera.position = Vector3(0.0, 1.6, 0.0)
	camera.current = true
	_box("asphalt", Vector3(0.0, -0.1, 0.0), Vector3(8.0, 0.2, 8.0))
	_box("tile", Vector3(10.0, -0.1, 0.0), Vector3(4.0, 0.2, 4.0))
	var canopy: StaticBody3D = _box("metal", Vector3(2.0, 3.0, 0.0), Vector3(1.8, 0.2, 4.0))
	await get_tree().physics_frame
	await get_tree().physics_frame
	Audio.stepped.connect(_on_step)
	var saved_conditions: Dictionary = RaidConditions.current.duplicate(true)
	var saved_weather: RaidWeather = RaidWeather.current
	# Не запускаем погодную сцену: проверяем реальные коллизии и звук при заданном состоянии покрытия.
	var weather: RaidWeather = RaidWeather.new()
	RaidWeather.current = weather
	RaidConditions.current["weather"] = "clear"
	var p: Vector3 = Vector3.ZERO
	_check("под ногами асфальт", Audio._surface_under(p) == "asphalt")
	_expect("сухой асфальт — прежний набор", p, false, "step_dirt")
	RaidConditions.current["weather"] = "rain"
	_expect("дождь начался, покрытие ещё сухое", p, false, "step_dirt")
	weather.wet = 1.0
	weather.puddles = 0.7
	_expect("ходьба по мокрому асфальту — новые записи", p, false, "step_asphalt_wet")
	_expect("бег сохраняет записи бега", p, true, "step_dirt_run")
	_expect("плитка в дождь сохраняет свои шаги", Vector3(10.0, 0.0, 0.0), false, "step_stone")
	_expect("асфальт под навесом — сухой звук", Vector3(2.0, 0.0, 0.0), false, "step_dirt")
	weather.wet = float(Balance.WET_STEPS.film_min) - 0.01
	weather.puddles = 0.0
	_expect("слабая сырость — без плеска луж", p, false, "step_dirt")
	weather.wet = float(Balance.WET_STEPS.film_min)
	_expect("мокрая плёнка включает набор", p, false, "step_asphalt_wet")
	RaidConditions.current["weather"] = "clear"
	weather.wet = 0.0
	weather.puddles = 0.7
	_expect("после дождя лужи ещё слышны", p, false, "step_asphalt_wet")
	weather.puddles = 0.0
	_expect("высохло — вернулся сухой набор", p, false, "step_dirt")
	weather.wet = 1.0
	_check("в Godot загружены все 16 записей", (Audio._samples.get("step_asphalt_wet", []) as Array).size() == 16)
	var samples: Array = Audio._samples.get("step_asphalt_wet", [])
	var streams_ok: bool = samples.size() == 16
	for stream: AudioStream in samples:
		streams_ok = streams_ok and stream is AudioStreamOggVorbis and stream.get_length() >= 0.24 and stream.get_length() <= 0.45
	_check("OGG распознаются и имеют длину отдельного шага", streams_ok)
	var previous: AudioStream = null
	var no_repeat: bool = true
	for _i: int in range(64):
		var picked: AudioStream = Audio._pick("step_asphalt_wet", p)
		no_repeat = no_repeat and picked != previous
		previous = picked
	_check("один вариант не повторяется подряд", no_repeat)
	Audio.step(p, false, false, 0.0, true, Vector3.RIGHT)
	var left: AudioStreamPlayer3D = _latest_player()
	_check("левая стопа — источник слева", left != null and left.global_position.is_equal_approx(Vector3(-Balance.STEP_FOOT_SIDE_M, 0.0, 0.0)))
	Audio.step(p, false, false, 0.0, false, Vector3.RIGHT)
	var right: AudioStreamPlayer3D = _latest_player()
	_check("правая стопа — источник справа", right != null and right.global_position.is_equal_approx(Vector3(Balance.STEP_FOOT_SIDE_M, 0.0, 0.0)))
	Audio.step(p, false, false, 0.0, true, Vector3.BACK)
	var turned: AudioStreamPlayer3D = _latest_player()
	_check("источник поворачивается вместе с персонажем", turned != null and turned.global_position.is_equal_approx(Vector3(0.0, 0.0, -Balance.STEP_FOOT_SIDE_M)))
	Audio.step(Vector3(0.0, 0.0, 2.0), false, true, 0.0, false, Vector3.RIGHT)
	var npc: AudioStreamPlayer3D = _latest_player()
	_check("мародёры используют тот же набор с пространственным источником", _heard.back() == "step_asphalt_wet" and npc != null and npc.stream in samples)
	# Потеря внешних записей не оставляет событие без звука.
	Audio._samples.erase("step_asphalt_wet")
	_check("без новой записи — старый набор", Audio._pick("step_asphalt_wet", p) in (Audio._samples.get("step_dirt", []) as Array))
	var dry_samples: Array = Audio._samples.get("step_dirt", [])
	Audio._samples.erase("step_dirt")
	_check("без всех записей — процедурный запасной шаг", Audio._pick("step_asphalt_wet", p) == Audio._streams["step_dirt"])
	Audio._samples["step_asphalt_wet"] = samples
	Audio._samples["step_dirt"] = dry_samples
	canopy.queue_free()
	RaidWeather.current = saved_weather
	weather.free()
	RaidConditions.current = saved_conditions
	print("wet_steps_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _box(surface: String, at: Vector3, size: Vector3) -> StaticBody3D:
	var body: StaticBody3D = StaticBody3D.new()
	body.set_meta("surface", surface)
	var shape: BoxShape3D = BoxShape3D.new()
	shape.size = size
	var collider: CollisionShape3D = CollisionShape3D.new()
	collider.shape = shape
	body.add_child(collider)
	add_child(body)
	body.position = at
	return body


func _on_step(kind: String, _surface: String, _pos: Vector3) -> void:
	_heard.append(kind)


func _latest_player() -> AudioStreamPlayer3D:
	for i: int in range(get_child_count() - 1, -1, -1):
		var player: AudioStreamPlayer3D = get_child(i) as AudioStreamPlayer3D
		if player != null:
			return player
	return null


func _expect(label: String, pos: Vector3, run: bool, kind: String) -> void:
	Audio.step(pos, run, false, 0.0, false, Vector3.RIGHT)
	_check(label, not _heard.is_empty() and _heard.back() == kind)


func _check(label: String, passed: bool) -> void:
	print("  [%s] %s" % ["ok" if passed else "FAIL", label])
	if not passed:
		_fails += 1
