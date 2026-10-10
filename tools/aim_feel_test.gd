extends Node
## Прицеливание «как в жизни» (идеи владельца 2026-10-10): пристрелка (сбитый ноль экземпляра и щелчки
## барабанчиков), дыхание в прицеле и его задержка, отдача в руках пружинами, своя инерция метки
## коллиматора. Нужен рендер модели в руках — с окном:
## tools/godot.cmd --windowed --resolution 1280x720 res://tools/aim_feel_test.tscn

const ID := "wpn_ar_01"

var _fails: int = 0
var _me: Player
var _rig: CameraRig


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	_pure()
	var level: Node = load("res://scenes/levels/f1_market.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in level.get_node("Marauders").get_children():
		m.queue_free()
	_me = Raid.current.local_player()
	_me.health.invulnerable = true
	_rig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	_me.global_position = Vector3(100.0, 0.1, -5.0)
	CameraRig.first_person_mode = true
	await get_tree().create_timer(0.5).timeout
	_rig._look_yaw = -PI * 0.5
	_rig._look_pitch = 0.0

	# --- пристрелка: ноль сбит на 30 угл. мин вправо и 18 вверх — пуля уходит туда; щелчки возвращают
	await _arm({"zero": [30.0, 18.0, 0, 0]})
	Input.action_press("aim")
	await get_tree().create_timer(float(_me.spec().aim_time) + 0.6).timeout
	var off: Vector2 = await _impact_moa()
	_check("сбитый ноль: пуля ушла вправо-вверх (%.0f, %.0f угл. мин)" % [off.x, off.y], absf(off.x - 30.0) < 6.0 and absf(off.y - 18.0) < 6.0)
	for i in range(30):
		_me.zero_click(-1, 0)
	for i in range(18):
		_me.zero_click(0, -1)
	_check("щелчки записаны: влево 30, вниз 18", _me.zero_clicks() == Vector2i(-30, -18), str(_me.zero_clicks()))
	off = await _impact_moa()
	_check("после щелчков пуля в точке прицеливания (%.0f, %.0f)" % [off.x, off.y], off.length() < 6.0)
	_me._send_ws(_me.weapon_slot)
	await get_tree().physics_frame
	var saved: Dictionary = _me.inventory.equipment.primary
	_check("хост сохранил щелчки, ошибку не тронул", Gear.zero_clicks(saved) == Vector2i(-30, -18) and Gear.zero_offset(saved).length() < 0.01, str(saved.get("zero")))

	# --- дыхание: прицел ходит; задержал — почти стоит; выдохся — одышка
	await _arm({})
	await get_tree().create_timer(0.6).timeout
	var free_swing: float = await _pitch_swing(4.0)
	Input.action_press("sprint")
	await get_tree().create_timer(0.3).timeout
	_check("бег в прицеле — дыхание задержано", _me.breath_held)
	var held_swing: float = await _pitch_swing(3.0)
	_check("задержал дыхание — прицел ходит заметно меньше (%.3f° → %.3f°)" % [free_swing, held_swing], held_swing < free_swing * 0.6 and free_swing > 0.05)
	await get_tree().create_timer(float(Balance.BREATH.hold_sec) - 3.0).timeout
	_check("воздух кончился — одышка, задержки нет", not _me.breath_held and _me.breath_gasping())
	_check("в одышке прицел ходит сильнее обычного", _me.breath_k() > 1.3, "%.2f" % _me.breath_k())
	Input.action_release("sprint")

	# --- отдача в руках: толчок назад и подброс, возврат с перелётом
	await get_tree().create_timer(float(Balance.BREATH.gasp_sec) + 0.5).timeout
	_me.fire_timer = 0.0
	_me._fire(_me.spec())
	var peak_back: float = 0.0
	var peak_rise: float = 0.0
	var low: float = 0.0
	for i in range(90):
		await get_tree().process_frame
		peak_back = maxf(peak_back, _rig._hand_kick.z)
		peak_rise = maxf(peak_rise, _rig._hand_kick.y)
		low = minf(low, _rig._hand_kick.y)
	_check("выстрел: толчок назад (%.2f) и подброс (%.2f)" % [peak_back, peak_rise], peak_back > 0.15 and peak_rise > 0.15)
	_check("возврат с небольшим перелётом (%.3f)" % low, low < -0.005 and low > -0.5)
	_check("руки успокоились", _rig._hand_kick.length() < 0.05, str(_rig._hand_kick))

	# --- метка коллиматора: при повороте взгляда корпус отстаёт сильнее, чем метка
	await _arm({}, {"optic_primary": {"id": "optic_rd_01"}})
	await get_tree().create_timer(float(_me.spec().aim_time) + 0.6).timeout
	var dot: MeshInstance3D = null
	for n: Node in _rig._viewmodel.find_children("*", "MeshInstance3D", true, false):
		if n.has_meta("reticle_dot"):
			dot = n as MeshInstance3D
	_check("у коллиматора есть метка", dot != null)
	if dot:
		var cam: Camera3D = get_viewport().get_camera_3d()
		var dot_peak: float = 0.0
		var body_peak: float = 0.0
		for i in range(8):
			_rig._look_yaw -= deg_to_rad(1.2)
			await get_tree().process_frame
			body_peak = maxf(body_peak, rad_to_deg(_rig._lag_used.get_angle()))
			var to_dot: Vector3 = (dot.global_position - cam.global_position).normalized()
			dot_peak = maxf(dot_peak, rad_to_deg(to_dot.angle_to(-cam.global_basis.z)))
		_check("корпус отстал на %.2f°, метка — только на %.2f°" % [body_peak, dot_peak], body_peak > 0.4 and dot_peak < body_peak * 0.6)
		await get_tree().create_timer(0.7).timeout
		_check("метка вернулась на место", (dot.position - (dot.get_meta("dot_rest") as Vector3)).length() < 0.0005)
		await RenderingServer.frame_post_draw
	Input.action_release("aim")
	print("aim_feel_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails else 0)


## Чистые функции пристрелки.
func _pure() -> void:
	var e: Dictionary = {"id": ID}
	_check("без поля — ствол пристрелян", Gear.zero_offset(e) == Vector2.ZERO and Gear.zero_clicks(e) == Vector2i.ZERO)
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	Gear.knock_zero(e, Balance.ZEROING.found_moa, rng)
	var size: float = Gear.zero_offset(e).length()
	_check("сбит на %.1f угл. мин (в пределах найденного)" % size, size >= float(Balance.ZEROING.found_moa[0]) - 0.2 and size <= float(Balance.ZEROING.found_moa[1]) + 0.2)
	var err: Vector2 = Gear.zero_offset(e)
	Gear.set_zero_clicks(e, Vector2i(3, -2))
	_check("щелчок двигает попадания на click_moa", (Gear.zero_offset(e) - err - Vector2(3, -2) * float(Balance.ZEROING.click_moa)).length() < 0.001)
	_check("подпись щелчков", Gear.zero_text(Vector2i(3, -2)) == "вниз 2, вправо 3" and Gear.zero_text(Vector2i.ZERO) == "", Gear.zero_text(Vector2i(3, -2)))
	Gear.set_zero_clicks(e, Vector2i(999, 0))
	_check("щелчков не больше предела", Gear.zero_clicks(e).x == int(Balance.ZEROING.max_clicks))
	# смена прицела сбивает ноль
	var w: Dictionary = WeaponDb.bare_weapon(ID, rng, [100, 100])
	var fitted: Array = Gear.fit(w, {"id": "optic_rd_01", "n": 1})
	_check("поставил прицел — ноль сбит", String(fitted[2]) == "" and Gear.zero_offset(fitted[0]).length() >= float(Balance.ZEROING.sight_moa[0]) - 0.2, str((fitted[0] as Dictionary).get("zero")))
	_check("купленный ствол пристрелян", Gear.zero_offset(ItemDb.make(ID, 1)) == Vector2.ZERO)


## Куда уходит пуля от точки прицеливания, угл. мин (вправо, вверх): выстрел без разброса и отдачи.
func _impact_moa() -> Vector2:
	var cam: Camera3D = get_viewport().get_camera_3d()
	var spec: Dictionary = _me.spec()
	spec["spread_deg"] = 0.0
	spec["kick"] = 0.0
	spec["kick_h"] = 0.0
	spec["jam"] = 0.0
	var from: Vector3 = _me.eye_position()
	var aim: Vector3 = _me.look_dir()
	_me.fire_timer = 0.0
	_me.weapon_obstruction = 0.0
	_last_hit = Vector3.INF
	var decals_before: int = get_tree().get_nodes_in_group("impact_marks").size()
	_me._fire(spec)
	await get_tree().physics_frame
	# попадание — по лучу того же выстрела: повторяем расчёт направления из данных экземпляра
	var zero: Vector2 = Gear.zero_offset(_me.entry_of(_me.weapon_slot))
	var right: Vector3 = aim.cross(Vector3.UP).normalized()
	var up: Vector3 = right.cross(aim).normalized()
	var dir: Vector3 = (aim + right * tan(deg_to_rad(zero.x / 60.0)) + up * tan(deg_to_rad(zero.y / 60.0))).normalized()
	var hit: Dictionary = cam.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(from, from + dir * 300.0, Hitscan.LAYER_WORLD))
	if hit.is_empty():
		return Vector2(INF, INF)
	var to_hit: Vector3 = ((hit.position as Vector3) - from).normalized()
	return Vector2(rad_to_deg(asin(clampf(to_hit.dot(right), -1.0, 1.0))), rad_to_deg(asin(clampf(to_hit.dot(up), -1.0, 1.0)))) * 60.0


var _last_hit: Vector3 = Vector3.INF


## Размах хода прицела по вертикали за sec секунд, град.
func _pitch_swing(sec: float) -> float:
	var lo: float = INF
	var hi: float = -INF
	var t: float = 0.0
	while t < sec:
		await get_tree().process_frame
		t += get_process_delta_time()
		lo = minf(lo, _me.look_pitch)
		hi = maxf(hi, _me.look_pitch)
	return rad_to_deg(hi - lo)


## ВЕРАС со снаряжением: дополнительные поля записи (zero) и обвес.
func _arm(extra: Dictionary, mods: Dictionary = {}) -> void:
	var rng := RandomNumberGenerator.new()
	var entry: Dictionary = WeaponDb.bare_weapon(ID, rng, [100, 100])
	entry["mag"] = {"id": WeaponDb.default_mag(ID), "ammo": WeaponDb.default_ammo("545x39"), "rounds": 30}
	entry["mods"] = mods
	for k: Variant in extra:
		entry[k] = extra[k]
	_me.loadout_mode = true
	_me.cancel_weapon_action()
	_me.inventory.equipment = {"primary": entry}
	_me.inventory.items = []
	_me.weapon_slot = ""
	_me._ws.clear()
	_me._switch("primary", false)
	await get_tree().create_timer(0.4).timeout


func _check(label: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_fails += 1
	print("%s %s%s" % ["[ok]  " if ok else "[FAIL]", label, "  (" + detail + ")" if detail != "" and not ok else ""])
