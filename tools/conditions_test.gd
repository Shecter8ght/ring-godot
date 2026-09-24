extends Node
## Условия рейда: выбор в убежище доходит до уровня, свет ТЦ по режиму электричества, солнце/луна,
## как далеко мародёр видит (день 60, ночь 25, в помещении без света ещё меньше, фонарь выдаёт),
## лут богаче за риск. С окном — снимки docs/screens/cond_*.png.
## godot --path . res://tools/conditions_test.tscn (можно --headless)

var _fails: int = 0
var _level: Node


func _ready() -> void:
	Profile.use_file("user://profile_conditions_test.json", true)
	Profile.ensure()
	await get_tree().process_frame
	# убежище → рейд: условия из профиля
	Profile.next_conditions = {"time": "night", "weather": "fog", "power": "off"}
	Profile.pending_raid = true
	_check("выбор у лестницы доходит до рейда", RaidConditions.for_new_raid() == {"time": "night", "weather": "fog", "power": "off"}, str(RaidConditions.for_new_raid()))
	Profile.pending_raid = false
	_check("риск и награда", RaidConditions.risk({"time": "night", "weather": "fog", "power": "off"}) == 5 and is_equal_approx(RaidConditions.loot_bonus({"time": "night", "weather": "fog", "power": "off"}), 0.6), "")
	var shots := DisplayServer.get_name() != "headless"
	for c in [{"time": "day", "weather": "clear", "power": "on"}, {"time": "dusk", "weather": "clear", "power": "on"},
			{"time": "night", "weather": "clear", "power": "off"}, {"time": "night", "weather": "clear", "power": "emergency"}]:
		RaidConditions.from_host = c
		await _load()
		var atmo := RaidAtmosphere.current
		var out := SectorBuilder.polar(-100.0, 150.0)
		var inn := SectorBuilder.polar(-104.0, 94.0)
		var lit := 0
		var total := 0
		for l in get_tree().get_nodes_in_group("mall_lights"):
			total += 1
			if (l as Light3D).visible:
				lit += 1
		var tag := "%s/%s" % [c.time, c.power]
		print("   %s: снаружи видно %.0f м, в магазине %.0f м, с фонарём %.0f м; огней горит %d из %d; улица — %s, магазин — %s" % [tag,
			atmo.view_distance(out, false), atmo.view_distance(inn, false), atmo.view_distance(inn, true), lit, total,
			"помещение" if atmo.is_indoor(out) else "улица", "помещение" if atmo.is_indoor(inn) else "улица"])
		match tag:
			"day/on":
				_check("день: снаружи 60 м, свет горит", is_equal_approx(atmo.view_distance(out, false), 60.0) and lit == total and total > 0, "")
			"night/off":
				_check("ночь без света: снаружи 25 м, в магазине 12, с фонарём 70; огни погашены", is_equal_approx(atmo.view_distance(out, false), 25.0)
					and is_equal_approx(atmo.view_distance(inn, false), 12.0) and is_equal_approx(atmo.view_distance(inn, true), 70.0) and lit == 0, "")
				_check("в темноте у мародёров фонари", atmo.is_dark(inn) and atmo.is_dark(out), "")
			"night/emergency":
				_check("аварийное: горит треть огней", lit > 0 and lit < total / 2, "%d из %d" % [lit, total])
		if shots:
			var me := Raid.current.local_player()
			for place in [["out", SectorBuilder.polar(-96.0, 70.0)], ["in", SectorBuilder.polar(-100.0, 36.0)]]:
				me.global_position = (place[1] as Vector3) + Vector3(0, 0.1, 0)
				CameraRig.first_person_mode = place[0] == "in"
				await get_tree().create_timer(1.5).timeout
				get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/cond_%s_%s_%s.png" % [c.time, c.power, place[0]]))
			CameraRig.first_person_mode = false
	# мародёр видит днём, не видит ночью (та же дистанция 35 м, улица)
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await _load()
	var day_seen := _sees_at(35.0)
	RaidConditions.from_host = {"time": "night", "weather": "clear", "power": "on"}
	await _load()
	var night_seen := _sees_at(35.0)
	_check("35 м на улице: днём видит, ночью нет", day_seen and not night_seen, "днём %s, ночью %s" % [day_seen, night_seen])
	# снаряжение под темноту: ПНВ в слоте «глаза», ракета освещает место
	RaidConditions.from_host = {"time": "night", "weather": "clear", "power": "off"}
	await _load()
	var me := Raid.current.local_player()
	var inn := SectorBuilder.polar(-100.0, 36.0)
	me.global_position = inn + Vector3(0, 0.1, 0)
	Input.action_press("nvg")
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_release("nvg")
	_check("ПНВ без ПНВ в слоте не включить", not me.nvg_on, "")
	me.inventory.equipment = {"eyes": ItemDb.make("nvg", 1)}
	await get_tree().physics_frame
	Input.action_press("nvg")
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_release("nvg")
	_check("ПНВ в слоте «глаза» — включается, садится", me.nvg_on and me.nvg_charge < Balance.NVG_BATTERY_SEC, "заряд %.1f" % me.nvg_charge)
	if shots:
		CameraRig.first_person_mode = true
		await get_tree().create_timer(1.5).timeout
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/cond_nvg.png"))
		me.nvg_on = false
	var dark := RaidAtmosphere.current.view_distance(inn + Vector3(3, 0, 0), false)
	me._rpc_throw_light("flare", inn + Vector3(3, 0.4, 0), Vector3.ZERO)
	await get_tree().create_timer(0.5).timeout
	_check("ракета: место освещено — видно издалека", RaidAtmosphere.current.view_distance(inn + Vector3(3, 0, 0), false) >= Balance.FLARE_LIT_VIEW and dark < 20.0,
		"%.0f → %.0f м" % [dark, RaidAtmosphere.current.view_distance(inn + Vector3(3, 0, 0), false)])
	if shots:
		await get_tree().create_timer(1.0).timeout
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/cond_flare.png"))
		CameraRig.first_person_mode = false
	print("conditions_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _sees_at(d: float) -> bool:
	var me := Raid.current.local_player()
	var p := SectorBuilder.polar(-90.0, 160.0)
	me.global_position = p + Vector3(0, 0.1, 0)
	me.light_on = false
	var eye := p + Vector3(d, 1.6, 0)
	return Perception.can_see(me.get_world_3d(), eye, Vector3(-1, 0, 0), me, [])


func _load() -> void:
	if _level:
		_level.queue_free()
		await get_tree().process_frame
	_level = load("res://scenes/levels/f1_ring.tscn").instantiate()
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	while _level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in _level.get_node("Marauders").get_children():
		m.queue_free()
	Raid.current.local_player().health.hp = 1e9
	for i in range(5):
		await get_tree().physics_frame


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
