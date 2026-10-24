extends Node
## Стойка оружия «наискосок» (Balance.WEAPON_CARRY, Player.carry_low): по умолчанию ствол опущен; колесо
## вверх — от бедра, вниз — снова наискосок; бегом — всегда наискосок; огонь из опущенного — оружие
## поднимается и стреляет (короткое нажатие не теряется), бег прерывается; из прицела — в ту стойку, из
## которой вскинул; лёжа и на перезарядке — на изготовку; колесо в прицеле стойку не трогает.
## tools/godot.cmd --headless res://tools/carry_test.tscn

var _fails: int = 0
var _me: Player
var _rig: CameraRig


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	Engine.max_fps = 144
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
	_face_open()
	await _sec(0.5)
	# пистолет — одиночный: проверяет, что короткое нажатие не теряется
	var keys: Array = _me.weapon_keys()
	var pistol := ""
	var rifle := ""
	for k: Variant in keys:
		# ключ песочницы — сборка (GLOCK17_BASE), класс — у ствола в руках
		_me._switch(String(k), false)
		await _frames(3)
		var cls := String(WeaponDb.weapon(_me.weapon_id).get("class", ""))
		if cls == "PISTOL" and pistol == "":
			pistol = String(k)
		elif cls != "PISTOL" and rifle == "":
			rifle = String(k)
	_me._switch(rifle if rifle != "" else String(keys[0]), false)
	await _sec(1.0)
	_check("по умолчанию — наискосок, ствол опущен", _me.carry_low and _me.weapon_lowered > 0.95, "%.2f" % _me.weapon_lowered)

	# колесо: вверх — от бедра, вниз — наискосок
	_check("колесо вверх берёт стойку", _me.wheel_carry(1), "")
	var t_up := await _until(func() -> bool: return _me.weapon_lowered < 0.05, 1.0)
	_check("колесо вверх — на изготовку от бедра, быстро", not _me.carry_low and t_up < 0.45, "%.2f с" % t_up)
	_me.wheel_carry(-1)
	var t_down := await _until(func() -> bool: return _me.weapon_lowered > 0.95, 1.5)
	_check("колесо вниз — снова наискосок", _me.carry_low and t_down < 0.7, "%.2f с" % t_down)

	# огонь из опущенного: поднимается и стреляет, стойка — от бедра
	var shot0 := _me.last_shot_ms
	# обычный короткий клик, ~50 мс (несколько тиков физики)
	Input.action_press("fire")
	await _sec(0.05)
	_check("огонь из опущенного — сразу не стреляет (ствол смотрит вниз)", _me.last_shot_ms == shot0, "")
	Input.action_release("fire")
	var t_fire := await _until(func() -> bool: return _me.last_shot_ms != shot0, 1.0)
	_check("короткое нажатие не теряется: поднял и выстрелил", _me.last_shot_ms != shot0 and t_fire < 0.45, "%.2f с" % t_fire)
	_check("после выстрела — на изготовку от бедра", not _me.carry_low and _me.weapon_lowered < 0.15, "%.2f" % _me.weapon_lowered)

	# бег — всегда наискосок; отпустил — обратно от бедра
	Input.action_press("move_forward")
	Input.action_press("sprint")
	await _sec(1.2)
	_check("бегом — наискосок (из стойки от бедра)", _me.weapon_lowered > 0.9, "%.2f" % _me.weapon_lowered)
	# огонь на бегу: бег прерывается, ствол поднимается, выстрел
	shot0 = _me.last_shot_ms
	Input.action_press("fire")
	var t_run_fire := await _until(func() -> bool: return _me.last_shot_ms != shot0, 1.0)
	var speed := Vector2(_me.velocity.x, _me.velocity.z).length()
	Input.action_release("fire")
	_check("огонь на бегу — бег прерван, выстрел", _me.last_shot_ms != shot0 and speed < Balance.PLAYER_SPRINT_SPEED * 0.8,
		"%.2f с, скорость %.1f м/с" % [t_run_fire, speed])
	Input.action_release("sprint")
	await _sec(0.8)
	_check("отпустил бег — снова от бедра", _me.weapon_lowered < 0.05, "%.2f" % _me.weapon_lowered)
	Input.action_release("move_forward")
	await _sec(0.5)

	# прицел из «наискосок» и обратно
	_me.wheel_carry(-1)
	await _sec(0.8)
	Input.action_press("aim")
	await _sec(0.6)
	_check("ПКМ из наискосок — ствол поднят", _me.weapon_lowered < 0.05, "%.2f" % _me.weapon_lowered)
	_check("колесо в прицеле стойку не трогает", not _me.wheel_carry(1) and _me.carry_low, "")
	Input.action_release("aim")
	await _sec(0.8)
	_check("отпустил ПКМ — снова наискосок", _me.weapon_lowered > 0.9, "%.2f" % _me.weapon_lowered)

	# лёжа — на изготовку
	Input.action_press("prone")
	await _frames(2)
	Input.action_release("prone")
	await _sec(1.0)
	_check("лёжа — не опускается", _me.weapon_lowered < 0.05, "%.2f" % _me.weapon_lowered)
	Input.action_press("prone")
	await _frames(2)
	Input.action_release("prone")
	await _sec(1.0)

	# перезарядка — руки заняты, ствол на изготовку
	Input.action_press("reload")
	await _frames(3)
	Input.action_release("reload")
	var lifted := await _until(func() -> bool: return _me.weapon_lowered < 0.1, 1.0)
	_check("перезарядка — ствол поднимается к рукам", lifted < 1.0 and _me.reload_timer > 0.0 or _me.weapon_lowered < 0.1, "%.2f с" % lifted)
	await _until(func() -> bool: return _me.reload_timer <= 0.0, 6.0)
	await _sec(0.8)
	_check("после перезарядки — снова наискосок", _me.weapon_lowered > 0.9, "%.2f" % _me.weapon_lowered)

	# пистолет: та же стойка своей позой
	if pistol != "":
		_me._switch(pistol, false)
		await _sec(1.2)
		_check("пистолет — тоже наискосок", _me.weapon_lowered > 0.9, "%.2f" % _me.weapon_lowered)
	print("carry_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _face_open() -> void:
	var space := _me.get_world_3d().direct_space_state
	var from := _me.global_position + Vector3.UP
	var best := 0.0
	for i in 24:
		var a := TAU * float(i) / 24.0
		var q := PhysicsRayQueryParameters3D.create(from, from + Vector3(sin(a), 0.0, cos(a)) * 60.0, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR, [_me.get_rid()])
		var hit := space.intersect_ray(q)
		var d := 60.0 if hit.is_empty() else from.distance_to(hit.position)
		if d > best:
			best = d
			_rig._look_yaw = a


## Ждёт условие не дольше limit секунд; сколько ждали.
func _until(cond: Callable, limit: float) -> float:
	var t := 0.0
	while t < limit and not bool(cond.call()):
		await get_tree().process_frame
		t += get_process_delta_time()
	return t


func _sec(s: float) -> void:
	await _until(func() -> bool: return false, s)


func _check(what: String, ok: bool, note: String = "") -> void:
	print("[%s] %s %s" % ["ok" if ok else "ПРОВАЛ", what, note])
	if not ok:
		_fails += 1


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame
