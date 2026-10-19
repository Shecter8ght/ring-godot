extends Node
## Режимы огня (решение владельца 2026-10-19): у ВЕРАС-54 X переводит по кругу АВ → 2 → ОД → АВ, по умолчанию АВ;
## пока переводчик щёлкает (Balance.FIRE_MODES.switch_sec) — не стреляет. АВ — очередь, пока держат спуск; «2» — нажатие
## даёт ровно Balance.FIRE_MODES.burst выстрела (и при коротком щелчке, и при долгом удержании); ОД — один выстрел.
## Режим хранится на экземпляре ствола: уходит хосту с состоянием оружия, переживает перезарядку и смену ствола.
## У стволов без "fire_modes" в данных — один режим по stats.auto, X ничего не делает.
## tools/godot.cmd --headless res://tools/fire_mode_test.tscn

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
	_me._rng.seed = 54
	await get_tree().create_timer(0.3).timeout

	# --- данные
	_check("ВЕРАС-54: режимы АВ → 2 → ОД", WeaponDb.fire_modes(ID) == ["auto", "burst", "semi"], str(WeaponDb.fire_modes(ID)))
	_check("пистолет без переводчика — один режим «одиночный»", WeaponDb.fire_modes("wpn_hg_01") == ["semi"], str(WeaponDb.fire_modes("wpn_hg_01")))
	_check("автомат без fire_modes в данных — один режим «АВ»", WeaponDb.fire_modes("wpn_smg_01") == ["auto"], str(WeaponDb.fire_modes("wpn_smg_01")))
	_check("клавиша режима огня — X", _key_of("fire_mode") == KEY_X, str(_key_of("fire_mode")))
	_check("тащить раненого — B", _key_of("drag") == KEY_B, str(_key_of("drag")))

	await _arm(30)
	_check("по умолчанию — АВ", _me.fire_mode() == "auto", _me.fire_mode())
	var auto_n: int = await _shots(0.6)
	_check("АВ: держать спуск — очередь (%d)" % auto_n, auto_n >= 5)

	# --- X: следующий режим, пока щёлкает — не стреляет
	await _arm(30)
	await _press_x()
	_check("X — «2»", _me.fire_mode() == "burst", _me.fire_mode())
	_check("переводчик щёлкает — таймер идёт", _me.fire_mode_switch_t > 0.0, "%.2f" % _me.fire_mode_switch_t)
	var during: int = await _shots(0.05, false)
	_check("пока переводчик щёлкает — выстрела нет", during == 0, str(during))
	await get_tree().create_timer(float(Balance.FIRE_MODES.switch_sec)).timeout
	var burst: int = int(Balance.FIRE_MODES.burst)
	var tap_n: int = await _shots(0.03)
	_check("«2»: короткий щелчок — очередь из %d" % burst, tap_n == burst, str(tap_n))
	var hold_n: int = await _shots(0.8)
	_check("«2»: держать спуск — всё равно %d" % burst, hold_n == burst, str(hold_n))
	var second: int = await _shots(0.03)
	_check("«2»: следующее нажатие — ещё очередь", second == burst, str(second))

	await _press_x()
	await get_tree().create_timer(float(Balance.FIRE_MODES.switch_sec)).timeout
	_check("X — ОД", _me.fire_mode() == "semi", _me.fire_mode())
	var semi_n: int = await _shots(0.8)
	_check("ОД: держать спуск — один выстрел", semi_n == 1, str(semi_n))

	await _press_x()
	await get_tree().create_timer(float(Balance.FIRE_MODES.switch_sec)).timeout
	_check("X — снова АВ (по кругу)", _me.fire_mode() == "auto", _me.fire_mode())

	# --- режим на экземпляре: хосту, перезарядка, смена ствола
	await _press_x()
	await get_tree().create_timer(float(Balance.FIRE_MODES.switch_sec) + 0.5).timeout
	var stored: String = String((_me.inventory.equipment.get("primary", {}) as Dictionary).get("fire_mode", ""))
	_check("режим ушёл в запись ствола (хост)", stored == "burst", stored)
	_me.cancel_weapon_action()
	await _tap_reload()
	var guard: float = 0.0
	while _me.reload_timer > 0.0 and guard < 8.0:
		await get_tree().physics_frame
		guard += get_physics_process_delta_time()
	await get_tree().create_timer(0.3).timeout
	_check("после перезарядки — тот же режим «2»", _me.fire_mode() == "burst", _me.fire_mode())
	_me._holster()
	await get_tree().create_timer(0.3).timeout
	_me._switch("primary", false)
	await get_tree().create_timer(0.5).timeout
	_check("убрал и достал — тот же режим «2»", _me.fire_mode() == "burst", _me.fire_mode())
	var text: String = ItemInfo._weapon_text(ID, WeaponDb.weapon(ID))
	_check("в описании ствола — переводчик АВ, 2, ОД", text.contains("переводчик") and text.contains("ОД"), text)

	# --- ствол с одним режимом: X ничего не делает
	var rng := RandomNumberGenerator.new()
	var pistol: Dictionary = WeaponDb.bare_weapon("wpn_hg_01", rng, [100, 100])
	pistol["mag"] = {"id": WeaponDb.default_mag("wpn_hg_01"), "ammo": WeaponDb.default_ammo(String(WeaponDb.weapon("wpn_hg_01").caliber)), "rounds": 8}
	var eq: Dictionary = _me.inventory.equipment.duplicate(true)
	eq["secondary"] = pistol
	_me.inventory.equipment = eq
	_me._switch("secondary", false)
	await get_tree().create_timer(0.5).timeout
	await _press_x()
	_check("пистолет: X не переключает", _me.fire_mode() == "semi" and _me.fire_mode_switch_t <= 0.0, _me.fire_mode())
	print("fire_mode_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails else 0)


## ВЕРАС с магазином на rounds патронов, ствол поднят (не «наискосок»), режим по умолчанию.
func _arm(rounds: int) -> void:
	var rng := RandomNumberGenerator.new()
	var entry: Dictionary = WeaponDb.bare_weapon(ID, rng, [100, 100])
	entry["mag"] = {"id": WeaponDb.default_mag(ID), "ammo": WeaponDb.default_ammo("545x39"), "rounds": rounds}
	_me.loadout_mode = true
	_me.cancel_weapon_action()
	_me.inventory.equipment = {"primary": entry}
	_me.inventory.items = [WeaponDb.make_mag(WeaponDb.default_mag(ID), WeaponDb.default_ammo("545x39"), 30)]
	_me.weapon_slot = ""
	_me._ws.clear()
	_me._switch("primary", false)
	_me.carry_low = false
	_me.raise_weapon()
	await get_tree().create_timer(0.6).timeout


## Сколько выстрелов за нажатие спуска на hold секунд (и ещё полсекунды после — очередь «2» доходит сама).
## Задержка посреди замера (редко) — снять и замерить заново.
func _shots(hold: float, wait_after: bool = true) -> int:
	for attempt: int in range(3):
		(_me._ws[_me.weapon_slot] as Dictionary)["jam"] = false
		var before: int = _me.ammo
		Input.action_press("fire")
		var t: float = 0.0
		await get_tree().physics_frame
		while t < hold:
			await get_tree().physics_frame
			t += get_physics_process_delta_time()
		Input.action_release("fire")
		if wait_after:
			await get_tree().create_timer(0.5).timeout
		else:
			await get_tree().physics_frame
		if not _me.is_jammed():
			return before - _me.ammo
		print("  (задержка во время замера — заново)")
	return -1


func _press_x() -> void:
	Input.action_press("fire_mode")
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_release("fire_mode")
	await get_tree().physics_frame


func _tap_reload() -> void:
	Input.action_press("reload")
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_release("reload")


func _key_of(action: String) -> int:
	for ev: InputEvent in InputMap.action_get_events(action):
		if ev is InputEventKey:
			return int((ev as InputEventKey).physical_keycode)
	return -1


func _check(label: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_fails += 1
	print("%s %s%s" % ["[ok]  " if ok else "[FAIL]", label, "  (" + detail + ")" if detail != "" and not ok else ""])
