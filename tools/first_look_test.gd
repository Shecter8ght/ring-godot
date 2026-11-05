extends Node
## Фризы первого раза на настоящей карте, как у друга при первом запуске (чистый кэш шейдеров): первый поворот камеры
## по кругу и взгляд вверх-вниз (материалы карты), первый выстрел (свет вспышки), фонарь (прожектор с тенью),
## химсвет и фальшфейер — самый длинный кадр за каждым и сколько конвейеров движок собрал при этом. Перед замером,
## как под экраном загрузки рейда, — разогрев эффектов попаданий (ImpactFx.warm_up).
## Проверено 2026-11-05 (docs/research/road_to_vostok.md, п. 6): облёт камерой под экраном загрузки, как у Road to Vostok,
## в Godot 4.7 не нужен — недостающие конвейеры собираются в фоне (убершейдеры), фризов нет; этот стенд их сторожит.
## Нужен рендер — только с окном; чистый кэш — APPDATA и LOCALAPPDATA на пустую папку:
##   tools/godot.cmd --windowed --resolution 1600x900 res://tools/first_look_test.tscn
## FIRST_LOOK_SCENE — другая карта (по умолчанию зона 1); FIRST_LOOK_LIMIT_MS — порог кадра (100): длиннее — провал.

const ID := "wpn_ar_01"

var _me: Player
var _rig: CameraRig
var _level: Node
var _results: Array = []
var _compiled: int = 0


func _ready() -> void:
	var scene: String = OS.get_environment("FIRST_LOOK_SCENE") if OS.get_environment("FIRST_LOOK_SCENE") != "" else "res://scenes/levels/zone01_mall.tscn"
	var limit: float = float(OS.get_environment("FIRST_LOOK_LIMIT_MS")) if OS.get_environment("FIRST_LOOK_LIMIT_MS") != "" else 100.0
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "dusk", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	_level = (load(scene) as PackedScene).instantiate()
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	while _level.get_node_or_null("Marauders") and _level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	if _level.get_node_or_null("Marauders"):
		for m in _level.get_node("Marauders").get_children():
			m.queue_free()
	_me = Raid.current.local_player()
	_me.health.invulnerable = true
	_rig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	CameraRig.first_person_mode = true
	await _arm()
	# пустые кадры: сцена, тени, небо собрались до замеров (как в first_hit_test)
	for i: int in range(30):
		await get_tree().process_frame
	var t0: int = Time.get_ticks_msec()
	await ImpactFx.warm_up()
	print("first_look: эффекты попаданий %d мс" % (Time.get_ticks_msec() - t0))
	for i: int in range(10):
		await get_tree().process_frame
	_compiled = _compilations()

	await _measure_frames("поворот по кругу", 90, func(k: float) -> void:
		_rig._look_yaw = k * TAU
		_rig._look_pitch = 0.0)
	await _measure_frames("взгляд вверх-вниз", 60, func(k: float) -> void:
		_rig._look_pitch = sin(k * TAU) * 1.2)
	_rig._look_pitch = 0.0
	await _measure("первый выстрел", func() -> void:
		(_me._ws[_me.weapon_slot] as Dictionary)["jam"] = false
		Input.action_press("fire"), 12)
	Input.action_release("fire")
	await _wait(0.5)
	await _measure("фонарь", func() -> void: Input.action_press("flashlight"), 12)
	Input.action_release("flashlight")
	await _wait(0.5)
	var eye: Vector3 = _me.eye_position()
	var fwd: Vector3 = -get_viewport().get_camera_3d().global_basis.z
	await _measure("химсвет", func() -> void: ThrownLight.throw(_level, "chemlight", eye + fwd * 0.5, fwd * 4.0), 20)
	await _measure("фальшфейер", func() -> void: ThrownLight.throw(_level, "flare", eye + fwd * 0.5, fwd * 5.0), 20)

	var worst: float = 0.0
	var worst_what: String = ""
	for r: Array in _results:
		if float(r[1]) > worst:
			worst = float(r[1])
			worst_what = String(r[0])
	var fails: int = 1 if worst > limit else 0
	print("first_look_test: %s — самый длинный кадр %.1f мс (%s), порог %.0f мс; провалено %d" % [scene.get_file(), worst, worst_what, limit, fails])
	get_tree().quit(fails)


## Сколько конвейеров движок собрал при рисовании и для оптимизации сцены.
func _compilations() -> int:
	return int(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_DRAW)) \
		+ int(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_SPECIALIZATION))


## Самый длинный кадр за действием и n кадрами после него.
func _measure(what: String, action: Callable, frames: int) -> void:
	await get_tree().process_frame
	var last: int = Time.get_ticks_usec()
	action.call()
	var worst: float = 0.0
	for i: int in range(frames):
		await get_tree().process_frame
		var now: int = Time.get_ticks_usec()
		worst = maxf(worst, float(now - last) / 1000.0)
		last = now
	_report(what, worst, 0)


## Движение за n кадров (step получает долю 0..1): самый длинный кадр и сколько кадров длиннее 33 мс.
func _measure_frames(what: String, n: int, step: Callable) -> void:
	await get_tree().process_frame
	var last: int = Time.get_ticks_usec()
	var worst: float = 0.0
	var slow: int = 0
	for i: int in range(n):
		step.call(float(i + 1) / float(n))
		await get_tree().process_frame
		var now: int = Time.get_ticks_usec()
		var ms: float = float(now - last) / 1000.0
		worst = maxf(worst, ms)
		slow += 1 if ms > 33.0 else 0
		last = now
	_report(what, worst, slow)


func _report(what: String, worst: float, slow: int) -> void:
	_results.append([what, worst])
	var built: int = _compilations() - _compiled
	_compiled = _compilations()
	print("first_look: %-20s %7.1f мс%s, конвейеров собрано %d" % [what, worst, ("  (кадров > 33 мс: %d)" % slow) if slow > 0 else "", built])


func _arm() -> void:
	var rng := RandomNumberGenerator.new()
	var entry: Dictionary = WeaponDb.bare_weapon(ID, rng, [100, 100])
	entry = Gear.fit(entry, ItemDb.make(DozorGear.MOUNT, 1), "side_left")[0]
	entry = Gear.fit(entry, ItemDb.make("tac_flashlight_01", 1), "side_left/light")[0]
	entry["mag"] = {"id": WeaponDb.default_mag(ID), "ammo": WeaponDb.default_ammo("545x39"), "rounds": 30}
	_me.loadout_mode = true
	_me.cancel_weapon_action()
	_me.inventory.equipment = {"primary": entry}
	_me.inventory.items = []
	_me.weapon_slot = ""
	_me._ws.clear()
	_me._switch("primary", false)
	_me.carry_low = false
	_me.raise_weapon()
	await _wait(0.5)


func _wait(sec: float) -> void:
	await get_tree().create_timer(sec).timeout
