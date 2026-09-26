extends Node
## Магазины и буфер: сколько патронов — не видно (только вместимость), проверка — держать R (у
## пистолетов и болтовок точно, у остальных словами); разрядить магазин (в рюкзак, в буфер),
## патроны на магазин — снарядить, «Снарядить магазины» берёт и из буфера; буфер 3×3 в окне ящика,
## закрыл окно — всё в рюкзак, не влезло — мешком рядом.
## godot --headless res://tools/mags_test.tscn

var _fails: int = 0


func _ready() -> void:
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
	var me := Raid.current.local_player()
	me.health.hp = 1e9
	await get_tree().create_timer(0.3).timeout
	var inv := me.inventory
	# --- разрядить в рюкзак
	inv.items = []
	inv.buffer = []
	var mag := WeaponDb.make_mag("mag_545_30", "ammo_545_std", 17)
	inv.add_entry(mag)
	var got := inv.unload_mag("backpack", 0, "backpack")
	_check("разрядить в рюкзак: 17 патронов стопкой, магазин пуст", got == 17 and inv.count("ammo_545_std") == 17 and int(_mag(inv.items).rounds) == 0, "вынуто %d" % got)
	# --- патроны на магазин
	var mi := inv.items.find(_mag(inv.items))
	var ai := _index_of(inv.items, "ammo_545_std")
	var put := inv.fill_mag("backpack", ai, "backpack", mi)
	_check("патроны на магазин — снарядил", put == 17 and int(_mag(inv.items).rounds) == 17 and inv.count("ammo_545_std") == 0, "заряжено %d" % put)
	# --- разрядить в буфер, из буфера — обратно на магазин
	mi = inv.items.find(_mag(inv.items))
	got = inv.unload_mag("backpack", mi, "buffer")
	_check("разрядить в буфер", got == 17 and _count(inv.buffer, "ammo_545_std") == 17, str(inv.buffer))
	put = inv.fill_mag("buffer", _index_of(inv.buffer, "ammo_545_std"), "backpack", inv.items.find(_mag(inv.items)))
	_check("из буфера — на магазин", put == 17 and inv.buffer.is_empty(), "заряжено %d" % put)
	# --- другой калибр не лезет
	inv.buffer = []
	inv.put_at(ItemDb.make("ammo_919_fmj", 10), 0, 0, false, "buffer")
	put = inv.fill_mag("buffer", 0, "backpack", inv.items.find(_mag(inv.items)))
	_check("9 мм в магазин 5.45 — нет", put == 0, "")
	# --- «Снарядить магазины» берёт и из буфера
	inv.buffer = []
	mi = inv.items.find(_mag(inv.items))
	inv.unload_mag("backpack", mi, "buffer")
	var used := inv.load_all_mags()
	_check("«Снарядить магазины» — из буфера", used == 17 and inv.buffer.is_empty() and int(_mag(inv.items).rounds) == 17, "ушло %d" % used)
	# --- переложить в буфер и обратно (куда влезет)
	mi = inv.items.find(_mag(inv.items))
	var moved := inv.move_between("backpack", mi, "buffer", -1, -1, false)
	_check("рюкзак → буфер", moved and inv.buffer.size() == 1 and _mag(inv.items).is_empty(), "")
	moved = inv.move_between("buffer", 0, "backpack", -1, -1, false)
	_check("буфер → рюкзак", moved and inv.buffer.is_empty() and not _mag(inv.items).is_empty(), "")
	# --- подписи: вместимость есть, сколько внутри — нет
	var lbl := ItemDb.label(_mag(inv.items))
	_check("у магазина видна вместимость, не остаток", lbl.contains("на 30") and not lbl.contains("17"), lbl)
	# --- окно ящика: буфер посередине; закрыл — буфер в рюкзак, лишнее — мешком
	var c := LootContainer.new()
	c.display_name = "Ящик теста"
	c.rolled = true
	level.add_child(c)
	c.global_position = me.global_position + Vector3(0.8, 0, 0)
	await get_tree().process_frame
	var ui := Raid.current.ui
	ui._open_loot(c)
	await get_tree().process_frame
	_check("открыт ящик — буфер посередине", ui._buf_panel.visible, "")
	inv.put_at(ItemDb.make("bandage", 3), 1, 1, false, "buffer")
	await get_tree().process_frame
	ui.close_all()
	await get_tree().create_timer(0.2).timeout
	_check("закрыл окно — буфер в рюкзаке", inv.buffer.is_empty() and inv.count("bandage") == 3 and not ui._buf_panel.visible, str(inv.buffer))
	# рюкзак забит — не влезшее ложится рядом
	var bags0 := _bags()
	var full: Array = []
	for i in range(Balance.BACKPACK_GRID.x * Balance.BACKPACK_GRID.y):
		full.append({"id": "lighter", "n": 1, "x": i % Balance.BACKPACK_GRID.x, "y": i / Balance.BACKPACK_GRID.x, "r": false})
	inv.items = full
	inv.buffer = [{"id": "gold_chain", "n": 1, "x": 0, "y": 0, "r": false}]
	Raid.current.request_flush_buffer()
	await get_tree().create_timer(0.3).timeout
	_check("рюкзак полон — из буфера мешком рядом", inv.buffer.is_empty() and _bags() > bags0, "мешков %d → %d" % [bags0, _bags()])
	# --- держать R — проверка (без перезарядки), коротко — перезарядка
	inv.items = []
	me._switch(String(me.weapon_keys()[1]), false)
	await get_tree().physics_frame
	me.ammo = 17
	var spec := me.spec()
	await _hold_reload(0.7)
	_check("держать R — проверка словами, без перезарядки", me.ammo_check_text == Gear.ammo_estimate(17, int(spec.mag), false) and me.reload_timer <= 0.0, "«%s», перезарядка %.2f" % [me.ammo_check_text, me.reload_timer])
	await _hold_reload(0.05)
	_check("коротко R — перезарядка", me.reload_timer > 0.0, "%.2f" % me.reload_timer)
	await get_tree().create_timer(4.0).timeout
	me._switch(String(me.weapon_keys()[0]), false)
	await get_tree().physics_frame
	me.ammo = 7
	await _hold_reload(0.7)
	_check("пистолет — точно", me.ammo_check_text == "7 из %d" % int(me.spec().mag), me.ammo_check_text)
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


func _index_of(list: Array, id: String) -> int:
	for i in range(list.size()):
		if String(list[i].id) == id:
			return i
	return -1


func _count(list: Array, id: String) -> int:
	var n := 0
	for it in list:
		if String(it.id) == id:
			n += int(it.n)
	return n


func _bags() -> int:
	var n := 0
	for c in get_tree().get_nodes_in_group("loot_containers"):
		if (c as LootContainer).display_name == "Выложено":
			n += 1
	return n


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
