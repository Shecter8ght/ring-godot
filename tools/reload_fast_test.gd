extends Node
## Перезарядка и проверка магазина со снаряжением (ВЕРАС-54): одно R — обычная смена, старый магазин в
## рюкзаке; два быстрых R — быстрая: короче в Balance.RELOAD_FAST.time_k раз, старый магазин лежит на
## земле в мешке «Выброшено»; второе R позже окна — обычная; держать R — проверка: магазин остаётся в
## руке, пока держат (Player.mag_inspect), перезарядка не начинается; отпустили — убран.
## tools/godot.cmd --headless res://tools/reload_fast_test.tscn

const ID := "wpn_ar_01"

var _fails: int = 0
var _raid: Raid
var _me: Player


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/f1_market.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in level.get_node("Marauders").get_children():
		m.queue_free()
	_raid = Raid.current
	_me = _raid.local_player()
	_me.health.invulnerable = true
	await get_tree().create_timer(0.3).timeout
	var spec_reload: float = float(WeaponDb.weapon(ID).stats.reload)
	var k: float = float(Balance.RELOAD_FAST.time_k)
	_check("быстрая перезарядка на 25–30 %% быстрее обычной (%.0f %%)" % ((1.0 - k) * 100.0), k >= 0.70 and k <= 0.75)

	# --- одно R: обычная, старый магазин — в рюкзак
	_arm(12, [30])
	await _tap()
	_check("одно R — обычная перезарядка", _me.reload_timer > 0.0 and not _me._reload_fast and absf(_me.reload_timer - spec_reload) < 0.25, "%.2f" % _me.reload_timer)
	await _until_done()
	_check("обычная: в оружии полный магазин", _me.ammo == 30, str(_me.ammo))
	_check("обычная: старый магазин (12) в рюкзаке", _mag_rounds().has(12), str(_mag_rounds()))
	_check("обычная: на земле ничего", _dropped().is_empty(), str(_dropped()))

	# --- два быстрых R: быстрая, старый магазин — на землю
	_arm(12, [30])
	await _tap()
	await _tap()
	_check("два быстрых R — быстрая перезарядка", _me._reload_fast and _me.reload_timer > 0.0)
	var left: float = _me.reload_timer + _me._reload_age
	_check("быстрая: короче в %.2f раза" % k, absf(left - spec_reload * k) < 0.2, "%.2f с при обычной %.2f" % [left, spec_reload])
	await _until_done()
	await get_tree().create_timer(0.3).timeout
	_check("быстрая: в оружии полный магазин", _me.ammo == 30, str(_me.ammo))
	_check("быстрая: старого магазина в рюкзаке нет", not _mag_rounds().has(12), str(_mag_rounds()))
	_check("быстрая: старый магазин лежит на земле", _dropped().has(12), str(_dropped()))

	# --- второе R позже окна — перезарядка остаётся обычной
	_arm(12, [30])
	await _tap()
	await get_tree().create_timer(float(Balance.RELOAD_FAST.tap_sec) + 0.25).timeout
	await _tap()
	_check("второе R с опозданием — обычная", _me.reload_timer > 0.0 and not _me._reload_fast)
	await _until_done()
	_check("опоздал: магазин в рюкзаке, не на земле", _mag_rounds().has(12))

	# --- нет запасного магазина: двойное R не выбрасывает единственный
	_arm(12, [])
	await _tap()
	await _tap()
	_check("без запасного магазина быстрой нет", not _me._reload_fast)
	await _until_done()

	# --- держать R: проверка, магазин в руке, пока держат
	_arm(17, [30])
	Input.action_press("reload")
	await get_tree().create_timer(float(Balance.AMMO_CHECK.hold_sec) + 0.3).timeout
	_check("держать R — проверка, магазин остаётся в руке", _me.mag_inspect and _me.reload_timer <= 0.0 and _me.ammo_check_text != "")
	await get_tree().create_timer(2.0).timeout
	_check("держат дальше — всё ещё в руке, ответ на экране", _me.mag_inspect and _me.ammo_check_t > 0.0)
	Input.action_release("reload")
	await get_tree().create_timer(0.2).timeout
	_check("отпустили — магазин убран, перезарядки нет", not _me.mag_inspect and _me.reload_timer <= 0.0 and _me.ammo == 17)

	# --- магазин вынут: R (по нажатию) вставляет новый; двойное R и удержание — ничего особенного
	var insert_sec: float = float(WeaponDb.weapon(ID).stats.reload_empty) * float(Balance.RELOAD_INSERT.time_k)
	_arm(-1, [30])
	await get_tree().create_timer(0.4).timeout
	_check("магазин вынут: в руках оружие без магазина", _me.mag_out() and _me.ammo == 0, _me.weapon_mag)
	Input.action_press("reload")
	await get_tree().physics_frame
	await get_tree().physics_frame
	_check("без магазина: R сразу вставляет новый (не ждёт отпускания)", _me.reload_timer > 0.0 and _me._reload_insert, "%.2f" % _me.reload_timer)
	_check("без магазина: вставка короче полной перезарядки", absf(_me.reload_timer + _me._reload_age - insert_sec) < 0.25, "%.2f при %.2f" % [_me.reload_timer, insert_sec])
	Input.action_release("reload")
	await get_tree().physics_frame
	await _tap()
	_check("без магазина: двойное R — быстрой нет", not _me._reload_fast and _me.reload_timer > 0.0)
	await _until_done()
	_check("без магазина: вставлен полный магазин", _me.ammo == 30 and not _me.mag_out() and _dropped().is_empty(), "%d %s" % [_me.ammo, _me.weapon_mag])
	_arm(-1, [])
	await get_tree().create_timer(0.4).timeout
	_me.ammo_check_text = ""
	Input.action_press("reload")
	await get_tree().create_timer(float(Balance.AMMO_CHECK.hold_sec) + 0.4).timeout
	_check("без магазина: держать R — ни проверки, ни перезарядки", not _me.mag_inspect and _me.ammo_check_text == "" and _me.reload_timer <= 0.0)
	Input.action_release("reload")
	await get_tree().physics_frame
	# только пустой магазин в рюкзаке — вставляется и он (дальше можно досыпать россыпью)
	_arm(-1, [0])
	await get_tree().create_timer(0.4).timeout
	await _tap()
	await _until_done()
	_check("без магазина: вставляется и пустой магазин", not _me.mag_out() and _me.ammo == 0 and _mag_rounds().is_empty(), "%s %s" % [_me.weapon_mag, str(_mag_rounds())])
	print("reload_fast_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails else 0)


## Игрок со снаряжением: ВЕРАС с магазином на rounds патронов (−1 — магазин вынут), в рюкзаке — магазины spare.
func _arm(rounds: int, spare: Array) -> void:
	for n: Node in get_tree().get_nodes_in_group("loot_containers"):
		var c := n as LootContainer
		if c and c.display_name == Raid.DROP_NAME:
			c.queue_free()
	var rng := RandomNumberGenerator.new()
	var entry: Dictionary = WeaponDb.bare_weapon(ID, rng, [100, 100])
	var ammo_id: String = WeaponDb.default_ammo("545x39")
	entry["mag"] = {"id": WeaponDb.default_mag(ID), "ammo": ammo_id, "rounds": rounds}
	if rounds < 0:
		# магазин вынут
		entry["mag"] = {"id": "", "ammo": ammo_id, "rounds": 0}
	_me.loadout_mode = true
	_me.cancel_weapon_action()
	_me.inventory.equipment = {"primary": entry}
	_me.inventory.items = []
	for n: int in spare:
		_me.inventory.add_entry(WeaponDb.make_mag(WeaponDb.default_mag(ID), ammo_id, n))
	_me.weapon_slot = ""
	_me._ws.clear()
	_me._switch("primary", false)
	await get_tree().create_timer(0.3).timeout


## Короткое нажатие R (перезарядка начинается по отпусканию).
func _tap() -> void:
	Input.action_press("reload")
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_release("reload")
	await get_tree().physics_frame
	await get_tree().physics_frame


func _until_done() -> void:
	var guard := 0.0
	while _me.reload_timer > 0.0 and guard < 8.0:
		await get_tree().physics_frame
		guard += get_physics_process_delta_time()
	await get_tree().create_timer(0.2).timeout


## Остатки во всех магазинах рюкзака.
func _mag_rounds() -> Array:
	var out: Array = []
	for it: Dictionary in _me.inventory.items:
		if it.has("rounds"):
			out.append(int(it.rounds))
	return out


## Остатки в магазинах, лежащих на земле в мешках «Выброшено».
func _dropped() -> Array:
	var out: Array = []
	for n: Node in get_tree().get_nodes_in_group("loot_containers"):
		var c := n as LootContainer
		if c == null or c.is_queued_for_deletion() or c.display_name != Raid.DROP_NAME:
			continue
		for it: Dictionary in c.items:
			if it.has("rounds"):
				out.append(int(it.rounds))
	return out


func _check(label: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_fails += 1
	print("%s %s%s" % ["[ok]  " if ok else "[FAIL]", label, "  (" + detail + ")" if detail != "" and not ok else ""])
