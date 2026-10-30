extends Node
## Пылезащитная шторка AR-15 «ГРАНЬ-15» (владелец 2026-10-30): закрыта только у ствола, рама которого ещё не отходила, —
## каким он попал в руки; выстрел, перезарядка с пустым магазином и устранение задержки (рукоятка заряжания) её
## откидывают, и открытой она остаётся — сама не закрывается: ни перезарядкой, ни сменой ствола. Хранится на экземпляре
## (Player.dust_cover_open → запись ствола у хоста). В руках (CameraRig._tick_cover) — откидывается на cover_deg
## с отскоком от упора; достали открытый ствол — сразу открыт. Заодно: рама в руках отходит на выстреле.
## tools/godot.cmd --headless res://tools/dust_cover_test.tscn

const ID := "wpn_ar_09"
const COVER := "DustCover_Receiver"

var _fails: int = 0
var _raid: Raid
var _me: Player
var _camera: CameraRig


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in level.get_node("Marauders").get_children():
		m.queue_free()
	_raid = Raid.current
	_me = _raid.local_player()
	_me.health.invulnerable = true
	_me._rng.seed = 30
	_camera = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	await get_tree().create_timer(0.3).timeout

	# --- данные
	_check("у ГРАНЬ-15 шторка — узел " + COVER, WeaponDb.dust_cover(ID) == COVER, WeaponDb.dust_cover(ID))
	_check("у ВЕРАС-54 шторки нет", WeaponDb.dust_cover("wpn_ar_01") == "", WeaponDb.dust_cover("wpn_ar_01"))
	var deg: float = float((WeaponDb.model("ar15").get("action", {}) as Dictionary).get("cover_deg", 0.0))
	_check("угол откидывания из исходника (112°)", absf(deg - 112.0) < 0.5, str(deg))

	# --- новый ствол: закрыта; выстрел — откинулась, рама отошла
	await _arm(30)
	_check("ствол только попал в руки — шторка закрыта", not _me.dust_cover_open())
	_check("в руках — закрыта", absf(_angle()) < 0.5, "%.1f°" % _angle())
	var peak: float = 0.0
	var travel: float = 0.0
	(_me._ws[_me.weapon_slot] as Dictionary)["jam"] = false
	var before: int = _me.ammo
	Input.action_press("fire")
	for _f in range(40):
		await get_tree().process_frame
		peak = maxf(peak, _angle())
		travel = maxf(travel, _carrier_off())
	Input.action_release("fire")
	_check("выстрел (%d → %d) — шторка открыта" % [before, _me.ammo], _me.ammo < before and _me.dust_cover_open())
	_check("в руках откинулась до упора (%.1f°)" % _angle(), absf(_angle() - deg) < 1.0, "%.1f°" % _angle())
	_check("рама на выстреле отошла (%.3f м)" % travel, travel > 0.05, "%.3f м" % travel)
	_check("откидывание не перелетает упор", peak <= deg + 0.5, "%.1f°" % peak)
	await get_tree().create_timer(0.8).timeout
	var stored: bool = bool((_me.inventory.equipment.get("primary", {}) as Dictionary).get("cover_open", false))
	_check("открытая шторка ушла в запись ствола (хост)", stored)

	# --- открытая остаётся: перезарядка, убрал и достал
	_me.cancel_weapon_action()
	await _tap_reload()
	await _wait_reload()
	_check("после перезарядки — открыта", _me.dust_cover_open() and absf(_angle() - deg) < 1.0, "%.1f°" % _angle())
	_me._holster()
	await get_tree().create_timer(0.3).timeout
	_me._switch("primary", false)
	await get_tree().process_frame
	await get_tree().process_frame
	_check("убрал и достал — сразу открыта, без нового откидывания", absf(_angle() - deg) < 1.0, "%.1f°" % _angle())

	# --- полный магазин в новый ствол: рама не отходит — закрыта
	await _arm(12)
	_me.cancel_weapon_action()
	await _tap_reload()
	await _wait_reload()
	_check("смена неполного магазина у нового ствола — закрыта", not _me.dust_cover_open())

	# --- пустой магазин: рукоятку заряжания оттягивают — откинулась
	await _arm(0)
	_me.cancel_weapon_action()
	await _tap_reload()
	await _wait_reload()
	await get_tree().create_timer(0.3).timeout
	_check("перезарядка с пустым магазином — открыта", _me.dust_cover_open() and absf(_angle() - deg) < 1.0, "%.1f°" % _angle())

	# --- задержка: передёрнуть — откинулась
	await _arm(30)
	(_me._ws[_me.weapon_slot] as Dictionary)["jam"] = true
	await _tap_reload()
	await _wait_reload()
	await get_tree().create_timer(0.3).timeout
	_check("устранение задержки — открыта", _me.dust_cover_open() and not _me.is_jammed(), "jam %s" % _me.is_jammed())
	print("dust_cover_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails else 0)


## Новый ГРАНЬ-15 (шторка закрыта) с магазином на rounds патронов и запасным в рюкзаке, ствол поднят.
func _arm(rounds: int) -> void:
	var rng := RandomNumberGenerator.new()
	var entry: Dictionary = WeaponDb.bare_weapon(ID, rng, [100, 100])
	entry["mag"] = {"id": WeaponDb.default_mag(ID), "ammo": WeaponDb.default_ammo("556x45"), "rounds": rounds}
	entry.erase("cover_open")
	_me.loadout_mode = true
	_me.cancel_weapon_action()
	_me.inventory.equipment = {"primary": entry}
	_me.inventory.items = [WeaponDb.make_mag(WeaponDb.default_mag(ID), WeaponDb.default_ammo("556x45"), 30)]
	_me.weapon_slot = ""
	_me._ws.clear()
	_me._switch("primary", false)
	_me.carry_low = false
	_me.raise_weapon()
	await get_tree().create_timer(0.6).timeout


## Угол шторки модели в руках, градусы (0 — закрыта).
func _angle() -> float:
	var n: Node3D = _node(COVER)
	if n == null or not n.has_meta("rest"):
		return -999.0
	var rest: Transform3D = n.get_meta("rest")
	return rad_to_deg(rest.basis.get_rotation_quaternion().angle_to(n.basis.get_rotation_quaternion()))


## Насколько рама в руках отошла назад от места, м.
func _carrier_off() -> float:
	var n: Node3D = _node("BoltCarrier_Steel")
	return (n.get_meta("rest") as Transform3D).origin.z - n.position.z if n and n.has_meta("rest") else 0.0


func _node(node_name: String) -> Node3D:
	var frame: Node3D = _camera._vm_frame() if _camera else null
	return frame.find_child(node_name, true, false) as Node3D if frame else null


func _tap_reload() -> void:
	Input.action_press("reload")
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_release("reload")


func _wait_reload() -> void:
	var guard: float = 0.0
	await get_tree().physics_frame
	while _me.reload_timer > 0.0 and guard < 8.0:
		await get_tree().physics_frame
		guard += get_physics_process_delta_time()
	await get_tree().create_timer(0.3).timeout


func _check(label: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_fails += 1
	print("%s %s%s" % ["[ok]  " if ok else "[FAIL]", label, "  (" + detail + ")" if detail != "" and not ok else ""])
