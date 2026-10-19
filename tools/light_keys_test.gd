extends Node
## Клавиши света (решение владельца 2026-10-19): Y — зелёный химсвет в руку, бросок как граната (ЛКМ / ПКМ, держать — сильнее);
## G — ракетница в руки из слота оружия (в руках — тип следующего патрона), дважды быстро G — красный фальшфейер в руку и бросок;
## B — тащить раненого, X — режим огня. Химсвет и фальшфейер тратятся у хоста по броску, свет лежит на земле (ThrownLight).
## tools/godot.cmd --headless res://tools/light_keys_test.tscn

var _fails: int = 0
var _me: Player


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "night", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/f1_market.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in level.get_node("Marauders").get_children():
		m.queue_free()
	_me = Raid.current.local_player()
	_me.health.invulnerable = true
	await get_tree().create_timer(0.3).timeout

	_check("клавиши: X — режим огня, B — тащить, Y — химсвет, G — ракетница / фальшфейер",
		_key("fire_mode") == KEY_X and _key("drag") == KEY_B and _key("throw_chem") == KEY_Y and _key("throw_flare") == KEY_G,
		"%d %d %d %d" % [_key("fire_mode"), _key("drag"), _key("throw_chem"), _key("throw_flare")])
	await _arm(true)
	var rifle: String = _me.weapon_id

	# --- Y: химсвет в руку, бросок ЛКМ
	await _tap("throw_chem")
	_check("Y — химсвет в руке", _me.grenade_equipped and _me.throwable_id == "chemlight" and _me.held_model_id() == "chemlight", _me.held_model_id())
	await get_tree().create_timer(float(Balance.GRENADE_HAND.equip_sec) + 0.1).timeout
	var lights: int = _lights("chemlight")
	await _throw(0.5)
	_check("ЛКМ — химсвет брошен, лежит свет", _lights("chemlight") == lights + 1, str(_lights("chemlight")))
	_check("химсвет израсходован один", _me.inventory.count("chemlight") == 1, str(_me.inventory.count("chemlight")))
	_check("после броска химсвет снова в руке (остался ещё один)", _me.grenade_equipped and _me.throwable_id == "chemlight")
	await _tap("throw_chem")
	await get_tree().create_timer(0.5).timeout
	_check("Y ещё раз — химсвет убран, в руках прежний ствол", not _me.grenade_equipped and _me.weapon_id == rifle, _me.weapon_id)

	# --- двойное G: фальшфейер в руку, бросок
	await _tap("throw_flare")
	await get_tree().create_timer(0.08).timeout
	await _tap("throw_flare")
	_check("двойное G — фальшфейер в руке", _me.grenade_equipped and _me.throwable_id == "flare", _me.throwable_id)
	await get_tree().create_timer(float(Balance.LIGHT_KEYS.double_tap_sec) + 0.2).timeout
	_check("двойное G не достаёт ракетницу", _me.weapon_id != "signal_launcher" and _me.grenade_equipped)
	var flares: int = _lights("flare")
	await _throw(0.3)
	_check("фальшфейер брошен — горит на земле", _lights("flare") == flares + 1, str(_lights("flare")))
	_check("фальшфейер израсходован один", _me.inventory.count("flare") == 1, str(_me.inventory.count("flare")))

	# --- граната и смена бросаемого в руке
	await _tap("grenade")
	_check("4 — граната в руке (вместо фальшфейера)", _me.grenade_equipped and _me.throwable_id == "grenade", _me.throwable_id)
	await _tap("throw_chem")
	_check("Y с гранатой в руке — химсвет вместо неё", _me.grenade_equipped and _me.throwable_id == "chemlight", _me.throwable_id)
	await _tap("throw_chem")
	await get_tree().create_timer(0.5).timeout

	# --- клавиши слотов (2026-10-19): 1, 2 — крупное, 3 — пистолет, 5 — ракетница
	_check("клавиши слотов: 1, 2, 3 — оружие, 4 — граната, 5 — ракетница",
		_key("weapon_1") == KEY_1 and _key("weapon_2") == KEY_2 and _key("weapon_3") == KEY_3 and _key("grenade") == KEY_4 and _key("weapon_4") == KEY_5)
	await _tap("weapon_4")
	await get_tree().create_timer(0.5).timeout
	_check("5 — ракетница из своего слота", _me.weapon_id == "signal_launcher" and _me.weapon_slot == "launcher", _me.weapon_slot)
	await _tap("weapon_1")
	await get_tree().create_timer(0.5).timeout
	_check("1 — снова ВЕРАС", _me.weapon_id == rifle, _me.weapon_id)
	# --- одно G: ракетница из слота; в руках — тип патрона
	await _tap("throw_flare")
	await get_tree().create_timer(float(Balance.LIGHT_KEYS.double_tap_sec) + 0.2).timeout
	_check("G — ракетница в руках", _me.weapon_id == "signal_launcher", _me.weapon_id)
	var ammo_before: String = _me.signal_reload_ammo
	await _tap("throw_flare")
	await get_tree().create_timer(float(Balance.LIGHT_KEYS.double_tap_sec) + 0.2).timeout
	_check("G с ракетницей — другой патрон на перезарядку", _me.signal_reload_ammo != ammo_before and _me.weapon_id == "signal_launcher",
		"%s → %s" % [ammo_before, _me.signal_reload_ammo])

	# --- без ракетницы: G ничего не достаёт
	await _arm(false)
	await _tap("throw_flare")
	await get_tree().create_timer(float(Balance.LIGHT_KEYS.double_tap_sec) + 0.2).timeout
	_check("без ракетницы G оставляет ствол в руках", _me.weapon_id == rifle and not _me.grenade_equipped, _me.weapon_id)
	print("light_keys_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails else 0)


## ВЕРАС в первом слоте, ракетница (если with_launcher) — в своём; в рюкзаке 2 химсвета, 2 фальшфейера, 2 гранаты.
func _arm(with_launcher: bool) -> void:
	var rng := RandomNumberGenerator.new()
	var rifle: Dictionary = WeaponDb.bare_weapon("wpn_ar_01", rng, [100, 100])
	rifle["mag"] = {"id": WeaponDb.default_mag("wpn_ar_01"), "ammo": WeaponDb.default_ammo("545x39"), "rounds": 30}
	var eq: Dictionary = {"primary": rifle}
	if with_launcher:
		eq["launcher"] = WeaponDb.bare_weapon("signal_launcher", rng, [100, 100])
	_me.loadout_mode = true
	_me.cancel_weapon_action()
	_me.inventory.equipment = eq
	_me.inventory.items = []
	for id: String in ["chemlight", "flare", "grenade"]:
		_me.inventory.add(id, 2)
	_me.grenade_equipped = false
	_me.weapon_slot = ""
	_me._ws.clear()
	_me._switch("primary", false)
	await get_tree().create_timer(0.6).timeout


## Бросок: ЛКМ держать hold секунд и отпустить.
func _throw(hold: float) -> void:
	Input.action_press("fire")
	var t: float = 0.0
	while t < hold:
		await get_tree().physics_frame
		t += get_physics_process_delta_time()
	Input.action_release("fire")
	await get_tree().create_timer(float(Balance.GRENADE_HAND.recover_sec) + 0.3).timeout


func _tap(action: String) -> void:
	Input.action_press(action)
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_release(action)
	await get_tree().physics_frame


func _lights(kind: String) -> int:
	var n: int = 0
	for node: Node in get_tree().get_nodes_in_group("thrown_lights"):
		if node is ThrownLight and (node as ThrownLight).kind == kind and not node.is_queued_for_deletion():
			n += 1
	return n


func _key(action: String) -> int:
	for ev: InputEvent in InputMap.action_get_events(action):
		if ev is InputEventKey:
			return int((ev as InputEventKey).physical_keycode)
	return -1


func _check(label: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_fails += 1
	print("%s %s%s" % ["[ok]  " if ok else "[FAIL]", label, "  (" + detail + ")" if detail != "" and not ok else ""])
