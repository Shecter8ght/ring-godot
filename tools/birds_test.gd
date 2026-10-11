extends Node
## Птицы зоны 1 (BirdFlocks): стаи сидят по районам и кружат; взлетают от выстрела и от того, кто
## пробежал рядом; дальний шум и тот, кто крадётся поодаль, не пугают; покружив, садятся; ночью птиц нет,
## в дождь меньше. С окном — снимки birds_sit / birds_up.
## tools/godot.cmd --headless res://tools/birds_test.tscn

var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/zone01_mall.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	var t0: int = Time.get_ticks_msec()
	while int(level.get("_marauders_spawned")) <= 0 and Time.get_ticks_msec() - t0 < 120000:
		await get_tree().process_frame
	for m: Node in level.get_node("Marauders").get_children():
		m.queue_free()
	var birds: BirdFlocks = level.get_node_or_null("Birds") as BirdFlocks
	_check("у карты есть птицы", birds != null)
	if birds == null:
		get_tree().quit(1)
		return
	await get_tree().create_timer(float(Balance.BIRDS.start_sec) + 1.0).timeout
	var sitting: Array = birds.flocks.filter(func(f: Dictionary) -> bool: return not bool(f.circling))
	var circling: Array = birds.flocks.filter(func(f: Dictionary) -> bool: return bool(f.circling))
	_check("стаи расселись по районам и кружат", sitting.size() >= 8 and circling.size() >= 1 and birds._perches.size() > sitting.size(),
		"сидят %d, кружат %d, мест %d" % [sitting.size(), circling.size(), birds._perches.size()])
	var me: Player = get_tree().get_first_node_in_group("players") as Player
	me.health.hp = 1e9
	me.set_physics_process(false)
	me.global_position = Vector3(0, -200, 0)
	await get_tree().create_timer(1.0).timeout
	_check("никто не шумел — сидящие сидят", birds.startled() == 0, str(birds.startled()))
	var a: Dictionary = sitting[0]
	var b: Dictionary = sitting[1]
	# снимок сидящей стаи
	await _look(me, a.perch as Vector3)
	await _shot("birds_sit")
	me.global_position = Vector3(0, -200, 0)
	# дальний выстрел не пугает, ближний — пугает
	NoiseBus.emit((a.perch as Vector3) + Vector3(float(Balance.BIRDS.noise_cap_m) + 30.0, 0, 0), 300.0, "shot")
	await get_tree().create_timer(0.3).timeout
	_check("выстрел за пределом слышимости птиц — сидят", int(a.state) == BirdFlocks.State.SIT)
	await _look(me, a.perch as Vector3)
	NoiseBus.emit((a.perch as Vector3) + Vector3(25, 0, 0), 120.0, "shot")
	await get_tree().create_timer(1.6).timeout
	_check("выстрел рядом — стая взлетела", int(a.state) == BirdFlocks.State.UP and birds.startled() >= 1)
	await _shot("birds_up")
	var up: Array = birds._bird_at(a, a.birds[0])
	_check("птицы поднимаются и машут крыльями", (up[0] as Vector3).y > (a.perch as Vector3).y + 0.5 and float(up[2]) > 0.5, str(up[0]))
	# крадётся поодаль — сидят; пробежал рядом — взлетели
	me.set_physics_process(false)
	me.velocity = Vector3.ZERO
	me.global_position = (b.perch as Vector3) + Vector3(float(Balance.BIRDS.near_m) - 2.0, 0.2, 0)
	await get_tree().create_timer(1.0).timeout
	_check("стоит в нескольких метрах — стая сидит", int(b.state) == BirdFlocks.State.SIT)
	me.velocity = Vector3(4.5, 0, 0)
	await get_tree().create_timer(1.0).timeout
	_check("пробежал рядом — стая взлетела", int(b.state) != BirdFlocks.State.SIT)
	me.velocity = Vector3.ZERO
	me.global_position = Vector3(0, -200, 0)
	# покружив, садятся
	Engine.time_scale = 12.0
	await get_tree().create_timer(float(Balance.BIRDS.air_sec[1]) + float(Balance.BIRDS.climb_sec) + float(Balance.BIRDS.land_sec) + 6.0).timeout
	Engine.time_scale = 1.0
	_check("покружив, стаи сели", birds.startled() == 0, str(birds.startled()))
	# ночь и дождь
	RaidConditions.current["weather"] = "rain"
	birds._refresh_presence()
	var in_rain: int = birds.flocks.filter(func(f: Dictionary) -> bool: return bool(f.present)).size()
	_check("в дождь стай меньше", in_rain < birds.flocks.size() and in_rain > 0, "%d из %d" % [in_rain, birds.flocks.size()])
	RaidConditions.current["weather"] = "clear"
	RaidConditions.current["time"] = "night"
	var dc: DayCycle = level.get_node_or_null("DayCycle") as DayCycle
	if dc:
		dc.hour = 1.0
	birds._refresh_presence()
	_check("ночью птиц нет", birds.flocks.filter(func(f: Dictionary) -> bool: return bool(f.present)).is_empty())
	print("birds_test: провалено %d" % _fails)
	get_tree().quit(_fails)


## Поставить игрока в 14 м от точки и повернуть взгляд на неё (для снимка).
func _look(me: Player, at: Vector3) -> void:
	if DisplayServer.get_name() == "headless":
		return
	CameraRig.first_person_mode = true
	me.global_position = at + Vector3(7.0, 0.3, 3.0)
	var rig: CameraRig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	var d: Vector3 = (at + Vector3.UP * 1.2 - (me.global_position + Vector3.UP * 1.6)).normalized()
	rig._look_yaw = atan2(d.x, d.z)
	rig._look_pitch = asin(clampf(d.y, -1.0, 1.0))
	for i: int in range(30):
		await get_tree().process_frame


func _shot(n: String) -> void:
	if DisplayServer.get_name() == "headless":
		return
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))


func _check(what: String, ok: bool, note: String = "") -> void:
	print("[%s] %s %s" % ["ok" if ok else "ПРОВАЛ", what, note])
	if not ok:
		_fails += 1
