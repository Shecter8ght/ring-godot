extends Node
## Главный рубильник света ТЦ: стоит в электрощитовой; «свет погас» — рубильник внизу, поднять:
## аварийный → весь → выкл; генератор встал — только аварийный, починили — снова весь. С окном —
## снимок breaker.png (от первого лица у шкафа). godot --path . res://tools/breaker_test.tscn

var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "night", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var inst: Node = load(Balance.RAID_SCENE).instantiate()
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	for i in range(30):
		await get_tree().physics_frame
	var br := inst.find_child("MainBreaker", true, false) as MallBreaker
	_check("рубильник на месте", br != null, "")
	if br == null:
		get_tree().quit(1)
		return
	var p := br.global_position
	var a := rad_to_deg(atan2(p.z, p.x))
	var r := Vector2(p.x, p.z).length()
	_check("в электрощитовой", a > -27.5 and a < -19.5 and r > 109.0 and r < 121.0, "a %.1f r %.1f" % [a, r])
	var ev := RaidEvents.current
	var pl := get_tree().get_first_node_in_group("players") as Player
	pl.health.hp = 1e9
	pl.global_position = br.global_transform * Vector3(0, 0.1, -1.2)
	await get_tree().create_timer(0.5).timeout
	_check("подойти можно — стоит на полу щитовой", absf(pl.global_position.y) < 0.3 and pl.global_position.distance_to(br.global_position) < 1.6, str(pl.global_position))
	_check("есть подсказка", br.prompt() != "", br.prompt())
	ev._rpc_event("outage")
	_check("свет погас — рубильник внизу", ev.breaker == "off" and String(RaidConditions.current.power) == "off", ev.breaker)
	br._use(1)
	_check("поднял — аварийный", String(RaidConditions.current.power) == "emergency", String(RaidConditions.current.power))
	br._use(1)
	_check("ещё раз — весь свет", String(RaidConditions.current.power) == "on", String(RaidConditions.current.power))
	await get_tree().create_timer(0.4).timeout
	if DisplayServer.get_name() != "headless":
		# лицом к шкафу
		var d := br.global_position - pl.global_position
		pl.cursor_ground = br.global_position
		pl.get_node("Body").rotation.y = atan2(d.x, d.z)
		await get_tree().create_timer(0.3).timeout
		CameraRig.set_first_person_mode(true)
		await get_tree().create_timer(0.3).timeout
		var rig := get_tree().get_first_node_in_group("camera_rig")
		rig.set("_look_yaw", atan2(d.x, d.z))
		rig.set("_look_pitch", -0.15)
		await get_tree().create_timer(0.5).timeout
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/breaker.png"))
		CameraRig.set_first_person_mode(false)
	br._use(1)
	_check("ещё раз — выключил сам", String(RaidConditions.current.power) == "off", String(RaidConditions.current.power))
	br._use(1)
	br._use(1)
	ev._rpc_event("generator")
	_check("генератор встал — только аварийный", String(RaidConditions.current.power) == "emergency" and ev.generator_down, String(RaidConditions.current.power))
	_check("при стоящем генераторе рубильник: аварийный ↔ выкл", ev.next_breaker() == "off", ev.next_breaker())
	br._use(1)
	br._use(1)
	_check("…и снова аварийный, не весь", String(RaidConditions.current.power) == "emergency", String(RaidConditions.current.power))
	ev._rpc_event("generator_fixed")
	_check("починили генератор — весь свет", String(RaidConditions.current.power) == "on", String(RaidConditions.current.power))
	print("breaker_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
