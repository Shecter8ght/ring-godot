extends Node
## Магазины, ящики и буфер: сколько патронов — не видно (только ПОЛН / ПУСТ, после проверки — оценка);
## «Снарядить» — только этот магазин, любыми подходящими патронами, поштучно, с пометкой для круга;
## нет патронов — «Требуются… В наличии…»; разрядить из ящика — в ящик, потом в буфер, места нет —
## стоп; плиты из жилета — по одной; патроны из ящика на магазин в рюкзаке — сколько влезет; прервали —
## что сделано, осталось; положить в ящик — в клетку; из ящика — сразу в пустой слот; закрыть ящик с
## вещами в буфере — спросить, согласился — буфер пуст. Держать R — проверка (точно / словами).
## godot --headless res://tools/mags_test.tscn

var _fails: int = 0
var _raid: Raid
var _me: Player


func _ready() -> void:
	Profile.use_file("user://mags_test_profile.json", true)
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	_check_words()
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
	var inv := _me.inventory
	var per := float(Balance.MAG_OPS.load_sec)

	# --- видно только полный / пустой; после проверки — оценка, изменилось — снова не видно
	inv.items = []
	inv.add_entry(WeaponDb.make_mag("mag_545_30", "ammo_545_std", 17))
	var lbl := ItemDb.label(_mag(inv.items))
	_check("неполный: видна вместимость, не остаток", lbl.contains("на 30") and not lbl.contains("17") and Gear.mag_tag(_mag(inv.items)) == "", lbl)
	_raid.request_check_mag("backpack", _mag_idx(inv.items))
	await get_tree().physics_frame
	var est := Gear.ammo_estimate(17, 30, false)
	_check("проверил — видна оценка", Gear.mag_tag(_mag(inv.items)) == String(Balance.AMMO_CHECK.short[est]) and ItemDb.label(_mag(inv.items)).ends_with(est), ItemDb.label(_mag(inv.items)))
	var chk: Dictionary = _mag(inv.items)
	chk.rounds = 16
	_check("патронов стало другое — оценки снова не видно", Gear.mag_tag(chk) == "", "")
	inv.items = []
	inv.add_entry(WeaponDb.make_mag("mag_545_30", "ammo_545_std", 30))
	inv.add_entry(WeaponDb.make_mag("mag_545_30", "", 0))
	_check("полный и пустой видно всегда", ItemDb.label(inv.items[0]).contains("полный") and Gear.mag_tag(inv.items[1]) == "ПУСТ", ItemDb.label(inv.items[0]))

	# --- «Снарядить» — только этот магазин, поштучно, круг знает, что магазин был пуст
	inv.items = []
	inv.add_entry(WeaponDb.make_mag("mag_545_30", "", 0))
	inv.add_entry(WeaponDb.make_mag("mag_545_30", "", 0))
	inv.add("ammo_545_std", 50)
	_raid.request_item_op("load", "backpack", 0)
	await _wait(per * 5.5)
	var m0: Dictionary = inv.items[0]
	var op: Dictionary = m0.get("op", {})
	_check("идёт поштучно: несколько патронов, пометка «заведомо пустой»", int(m0.rounds) >= 3 and int(m0.rounds) < 30 and bool(op.get("known", false)), "%d, %s" % [int(m0.rounds), str(op)])
	await _wait(per * 30.0)
	_check("снарядил один: полный, второй пустой, патронов 20", int(inv.items[0].rounds) == 30 and int(inv.items[1].rounds) == 0 and inv.count("ammo_545_std") == 20 and not (inv.items[0] as Dictionary).has("op"),
		"%d / %d, россыпь %d" % [int(inv.items[0].rounds), int(inv.items[1].rounds), inv.count("ammo_545_std")])

	# --- нет подходящих — сказать какие нужны и какие есть
	inv.items = []
	inv.add_entry(WeaponDb.make_mag("mag_545_30", "", 0))
	inv.add("ammo_919_fmj", 40)
	var txt := MagOps.no_ammo_text(inv.items[0], inv.items)
	_check("нет патронов: «Требуются… В наличии…»", txt.begins_with("Нет подходящих патронов. Требуются: патроны 5.45×39") and txt.contains("В наличии:") and txt.contains("— 40"), txt)

	# --- ящик: разрядить из ящика — в тот же ящик
	var c := LootContainer.new()
	c.display_name = "Ящик теста"
	c.look = LootContainer.Look.CRATE
	c.items = [WeaponDb.make_mag("mag_545_30", "ammo_545_std", 30)]
	c.place_all()
	c.rolled = true
	level.add_child(c)
	c.global_position = _me.global_position + Vector3(0.8, 0, 0)
	await get_tree().process_frame
	_check("у ящика сетка", c.grid == Vector2i(Balance.LOOT_GRID_W, int(Balance.LOOT_ROWS.CRATE)) and c.items[0].has("x"), str(c.grid))
	var ui := _raid.ui
	ui._open_loot(c)
	await get_tree().process_frame
	var unload_per := float(Balance.MAG_OPS.unload_sec)
	_raid.request_item_op("unload", "loot", 0, c)
	await _wait(unload_per * 33.0)
	_check("разрядил из ящика — патроны в том же ящике", int(_mag(c.items).rounds) == 0 and _count(c.items, "ammo_545_std") == 30 and inv.buffer.is_empty(), "в ящике %d" % _count(c.items, "ammo_545_std"))
	# ящик забит; в буфере — неполная стопка, куда влезет 5: вынет 5 и встанет
	var full: Array = [WeaponDb.make_mag("mag_545_30", "ammo_545_std", 30)]
	var probe: Array = []
	ItemDb.add_to(probe, full[0], c.grid)
	while ItemDb.add_to(probe, {"id": "lighter", "n": 1}, c.grid) > 0:
		pass
	c.items = probe
	inv.buffer = []
	ItemDb.add_to(inv.buffer, {"id": "ammo_545_std", "n": ItemDb.stack("ammo_545_std") - 5}, Balance.BUFFER_GRID)
	while ItemDb.add_to(inv.buffer, {"id": "lighter", "n": 1}, Balance.BUFFER_GRID) > 0:
		pass
	_raid.request_item_op("unload", "loot", _mag_idx(c.items), c)
	await _wait(unload_per * 12.0)
	var cm := _mag(c.items)
	_check("ящик полон — в буфер; и там нет места — стоп, остальное в магазине", int(cm.rounds) == 25 and _count(inv.buffer, "ammo_545_std") == ItemDb.stack("ammo_545_std") and not cm.has("op"),
		"в магазине %d, в буфере %d" % [int(cm.rounds), _count(inv.buffer, "ammo_545_std")])
	var before := int(cm.rounds)
	_raid.request_item_op("unload", "loot", _mag_idx(c.items), c)
	await get_tree().physics_frame
	_check("места нет — не начинается", int(_mag(c.items).rounds) == before and not _mag(c.items).has("op"), "")

	# --- плиты из плитоносца в ящике — по одной, в ящик
	inv.buffer = []
	var vest := ItemDb.make("carrier_simple", 1)
	var pl_id := "plate_steel"
	vest["plates"] = {"front": {"id": pl_id, "dur": 40.0}, "back": {"id": pl_id, "dur": 35.0}}
	c.items = [vest]
	c.place_all()
	_raid.request_item_op("plates", "loot", 0, c)
	await _wait(float(Balance.MAG_OPS.plate_sec) * 1.4)
	var v1: Dictionary = _find(c.items, "carrier_simple")
	_check("плиты — по одной", (v1.plates as Dictionary).size() == 1 and _count(c.items, pl_id) == 1, "осталось %d, в ящике %d" % [(v1.plates as Dictionary).size(), _count(c.items, pl_id)])
	await _wait(float(Balance.MAG_OPS.plate_sec) * 1.2)
	# вторая в ящик не влезла (плитоносец большой) — в буфер
	_check("обе плиты вынуты: в ящик, не влезло — в буфер", (_find(c.items, "carrier_simple").plates as Dictionary).is_empty() and _count(c.items, pl_id) + _count(inv.buffer, pl_id) == 2,
		"в ящике %d, в буфере %d" % [_count(c.items, pl_id), _count(inv.buffer, pl_id)])
	# плиту из ящика — перетащить на плитоносец: встаёт
	_raid.request_fit_grid("loot", c.items.find(_find(c.items, pl_id)), "loot", c.items.find(_find(c.items, "carrier_simple")), c)
	await get_tree().physics_frame
	_check("плиту — на плитоносец (перетащил)", (_find(c.items, "carrier_simple").plates as Dictionary).size() == 1 and _count(c.items, pl_id) == 0, str(c.items))

	# --- патроны из ящика — на магазин в рюкзаке: сколько влезет, остаток — в ящике
	inv.items = []
	inv.buffer = []
	inv.add_entry(WeaponDb.make_mag("mag_545_30", "", 0))
	c.items = [ItemDb.make("ammo_545_std", 45)]
	c.place_all()
	_raid.request_fill("loot", 0, "backpack", 0, c)
	await _wait(per * 34.0)
	_check("из ящика на магазин: 30 внутри, 15 остались в ящике", int(inv.items[0].rounds) == 30 and _count(c.items, "ammo_545_std") == 15, "%d / %d" % [int(inv.items[0].rounds), _count(c.items, "ammo_545_std")])

	# --- прервали — что вынуто, то вынуто
	_raid.request_item_op("unload", "backpack", 0)
	await _wait(float(Balance.MAG_OPS.unload_sec) * 6.5)
	_raid.request_cancel_op()
	await get_tree().physics_frame
	var left := int(inv.items[_mag_idx(inv.items)].rounds)
	_check("прервал разрядку: часть вынута, пометки нет", left > 20 and left < 30 and inv.count("ammo_545_std") == 30 - left and not (_mag(inv.items) as Dictionary).has("op"), "в магазине %d" % left)

	# --- положить в ящик — в выбранную клетку; из ящика — сразу в пустой слот
	inv.items = [{"id": "bandage", "n": 2, "x": 0, "y": 0, "r": false}]
	c.items = []
	c.place_all()
	_raid.request_put(c, 0, "backpack", 3, 1, false)
	await get_tree().physics_frame
	_check("в ящик — в клетку (3, 1)", c.items.size() == 1 and int(c.items[0].x) == 3 and int(c.items[0].y) == 1 and inv.items.is_empty(), str(c.items))
	var eq := inv.equipment.duplicate(true)
	eq.erase("primary")
	inv.equipment = eq
	var gun := ItemDb.make("wpn_ar_03", 1)
	c.items = [gun]
	c.place_all()
	_raid.request_equip_from("loot", 0, c)
	await get_tree().physics_frame
	_check("из ящика — сразу в пустой слот", String((inv.equipment.get("primary", {}) as Dictionary).get("id", "")) == "wpn_ar_03" and c.items.is_empty(), str(inv.equipment.get("primary", {}).get("id", "")))

	# --- закрыть ящик с вещами в буфере: спросить; «остаться» — окно открыто; «закрыть» — буфер пуст
	c.items = [ItemDb.make("gold_chain", 1)]
	c.place_all()
	ui._open_loot(c)
	inv.buffer = [{"id": "bandage", "n": 3, "x": 0, "y": 0, "r": false}]
	await get_tree().process_frame
	_check("открыт ящик — буфер посередине, окно во весь экран", ui._buf_panel.visible and ui._loot_panel.visible and ui._bp_panel.visible and ui._dim.visible, "")
	ui.request_close()
	await get_tree().process_frame
	var dlg := ui.get_node_or_null("BufferLoss") as ConfirmationDialog
	_check("в буфере вещи — вопрос «будут потеряны»", dlg != null and dlg.dialog_text.contains("будут потеряны"), "")
	if dlg:
		dlg.get_cancel_button().pressed.emit()
	await get_tree().process_frame
	await get_tree().process_frame
	_check("«Остаться» — окно открыто, буфер цел", ui._looting == c and inv.buffer.size() == 1, "")
	ui.request_close()
	await get_tree().process_frame
	dlg = ui.get_node_or_null("BufferLoss") as ConfirmationDialog
	if dlg:
		dlg.get_ok_button().pressed.emit()
	await get_tree().create_timer(0.2).timeout
	_check("«Закрыть» — окно закрыто, буфер пуст", ui._looting == null and inv.buffer.is_empty() and inv.count("bandage") == 0, str(inv.buffer))

	# --- держать R — проверка (без перезарядки), коротко — перезарядка
	inv.items = []
	_me._switch(String(_me.weapon_keys()[0]), false)
	await get_tree().physics_frame
	_set_weapon_rounds(17)
	var spec := _me.spec()
	await _hold_reload(0.7)
	_check("держать R — проверка словами, без перезарядки", _me.ammo_check_text == Gear.ammo_estimate(17, int(spec.mag), false) and _me.reload_timer <= 0.0, "«%s», перезарядка %.2f" % [_me.ammo_check_text, _me.reload_timer])
	await _hold_reload(0.05)
	_check("коротко R — перезарядка", _me.reload_timer > 0.0, "%.2f" % _me.reload_timer)
	await get_tree().create_timer(4.0).timeout
	_me._switch(String(_me.weapon_keys()[1]), false)
	await get_tree().physics_frame
	_set_weapon_rounds(7)
	await _hold_reload(0.7)
	_check("пистолет — точно", _me.ammo_check_text == "7 из %d" % int(_me.spec().mag), _me.ammo_check_text)
	# --- ускоритель снаряжения в рюкзаке: пачками по 10 за полсекунды, 30 — за полторы секунды; разрядка так же
	_raid.request_cancel_op()
	inv.items = []
	inv.add_entry(WeaponDb.make_mag("mag_545_30", "", 0))
	inv.add("ammo_545_std", 60)
	inv.add("mag_loader", 1)
	_raid.request_item_op("load", "backpack", 0)
	await _wait(float(Balance.MAG_OPS.loader_sec) * 1.3)
	var fast_n := int(_mag(inv.items).rounds)
	_check("с ускорителем — пачка в 10 патронов за полсекунды", fast_n == int(Balance.MAG_OPS.loader_batch), "%d" % fast_n)
	await _wait(float(Balance.MAG_OPS.loader_sec) * 2.2)
	_check("магазин на 30 снаряжён за полторы секунды, ускоритель не потрачен", int(_mag(inv.items).rounds) == 30 and inv.has("mag_loader"), "%d" % int(_mag(inv.items).rounds))
	await _wait(0.3)
	_raid.request_item_op("unload", "backpack", _mag_idx(inv.items))
	await _wait(float(Balance.MAG_OPS.loader_sec) * 1.3)
	_check("разрядка с ускорителем — тоже пачкой в 10", int(_mag(inv.items).rounds) == 20, "%d" % int(_mag(inv.items).rounds))
	await _wait(float(Balance.MAG_OPS.loader_sec) * 2.4)
	_check("магазин разряжен за полторы секунды, патроны вернулись в рюкзак", int(_mag(inv.items).rounds) == 0 and inv.count("ammo_545_std") == 60, "%d / %d" % [int(_mag(inv.items).rounds), inv.count("ammo_545_std")])
	inv.remove("mag_loader", 1)
	_raid.request_item_op("load", "backpack", _mag_idx(inv.items))
	await _wait(float(Balance.MAG_OPS.load_sec) * 4.5)
	_check("без ускорителя — по одному, как раньше", int(_mag(inv.items).rounds) == 4, "%d" % int(_mag(inv.items).rounds))
	_raid.request_cancel_op()
	_check("ускоритель продаёт Михалыч (каталог 2), находится у охраны и ЧВК", TraderStock.catalog_of("mag_loader") == 2 and not ItemDb.loot_only("mag_loader"), "")
	print("mags_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _check_words() -> void:
	var cases := [[0, 30, "пустой"], [30, 30, "полный"], [27, 30, "почти полный"], [21, 30, "больше половины"], [15, 30, "половина"], [8, 30, "меньше половины"], [2, 30, "почти пустой"]]
	var bad: Array = []
	for c in cases:
		var got := Gear.ammo_estimate(int(c[0]), int(c[1]), false)
		if got != String(c[2]):
			bad.append("%d/%d: %s" % [int(c[0]), int(c[1]), got])
	_check("словами: пустой … полный", bad.is_empty(), str(bad))
	_check("точно: «7 из 17»", Gear.ammo_estimate(7, 17, true) == "7 из 17", "")
	_check("точно — пистолет и болтовка, словами — автомат и дробовик",
		Gear.exact_count("wpn_hg_03") and Gear.exact_count("wpn_sr_01") and not Gear.exact_count("wpn_ar_03") and not Gear.exact_count("wpn_sg_02"), "")


func _wait(sec: float) -> void:
	await get_tree().create_timer(sec).timeout


## ammo — отображение, пересчитываемое Player. Сценарий задаёт реальный боезапас оружия.
func _set_weapon_rounds(count: int) -> void:
	_me.entry_of(_me.weapon_slot)
	var state: Dictionary = _me._ws[_me.weapon_slot]
	var chamber: int = mini(count, int(WeaponDb.weapon(_me.weapon_id).get("chamber_capacity", 0)))
	state["rounds"] = maxi(0, count - chamber)
	state["chamber"] = chamber
	state["chamber_ammo"] = String(state.get("ammo", "")) if chamber > 0 else ""
	_me.ammo = count
	_me.weapon_rounds = count
	_me._ws_dirty = true


func _hold_reload(sec: float) -> void:
	await get_tree().physics_frame
	Input.action_press("reload")
	var t := 0.0
	while t < sec:
		await get_tree().physics_frame
		t += get_physics_process_delta_time()
	Input.action_release("reload")
	await get_tree().physics_frame
	await get_tree().physics_frame


func _mag(list: Array) -> Dictionary:
	for it in list:
		if (it as Dictionary).has("rounds"):
			return it
	return {}


func _mag_idx(list: Array) -> int:
	for i in range(list.size()):
		if (list[i] as Dictionary).has("rounds"):
			return i
	return -1


func _find(list: Array, id: String) -> Dictionary:
	for it in list:
		if String(it.id) == id:
			return it
	return {}


func _count(list: Array, id: String) -> int:
	var n := 0
	for it in list:
		if String(it.id) == id:
			n += int(it.n)
	return n


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
