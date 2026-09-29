extends Node
## Регрессия: зарядка съедает первую пачку, мышь держит вторую над другим магазином.

var _fails: int = 0
var _signals: int = 0


func _ready() -> void:
	Profile.use_file("user://profile_inventory_drag_test.json", true)
	Profile.ensure()
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	await _stale_source()
	await _hideout()
	await _raid()
	print("inventory_drag_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _entries() -> Array:
	var first: Dictionary = WeaponDb.make_mag("mag_545_30", "", 0)
	first.merge({"x": 2, "y": 0})
	var second: Dictionary = WeaponDb.make_mag("mag_545_30", "", 0)
	second.merge({"x": 4, "y": 0})
	return [{"id": "ammo_545_std", "n": 1, "x": 0, "y": 0}, {"id": "ammo_545_std", "n": 20, "x": 1, "y": 0}, first, second]


func _payload(view: GridView) -> Dictionary:
	return {"view": view, "idx": 1, "id": "ammo_545_std", "origin": Vector2i(1, 0), "base_r": false, "grab": Vector2i.ZERO}


func _target() -> Vector2:
	return Vector2(4.5, 0.5) * GridView.CELL


func _stale_source() -> void:
	var source: GridView = GridView.new()
	var target: GridView = GridView.new()
	var slot: SlotView = SlotView.new("primary")
	add_child(source)
	add_child(target)
	add_child(slot)
	source.set_items(_entries())
	target.set_items(_entries())
	var data: Dictionary = _payload(source)
	target.dropped.connect(func(_s: GridView, _i: int, _x: int, _y: int, _r: bool) -> void: _signals += 1)
	target.dropped_on.connect(func(_s: GridView, _i: int, _j: int) -> void: _signals += 1)
	slot.equip_from.connect(func(_s: GridView, _i: int) -> void: _signals += 1)
	slot.mod_from.connect(func(_s: GridView, _i: int) -> void: _signals += 1)
	source.queue_free()
	_check(not target._can_drop_data(_target(), data), "сетка отвергает источник в очереди удаления")
	target._drop_data(_target(), data)
	slot._drop_data(Vector2.ZERO, data)
	await get_tree().process_frame
	_check(not target._can_drop_data(_target(), data), "наведение с удалённой сеткой безопасно")
	_check(not slot._can_drop_data(Vector2.ZERO, data), "слот отвергает удалённую сетку")
	_check(not target._fits_into(data, 3), "проверка магазина с удалённой сеткой безопасна")
	target._drop_data(_target(), data)
	slot._drop_data(Vector2.ZERO, data)
	_check(_signals == 0, "удалённая сетка не передаётся типизированным сигналам")
	target.free()
	slot.free()


func _hideout() -> void:
	Profile.stash = _entries()
	Profile.backpack = []
	var ui: HideoutUI = HideoutUI.new()
	add_child(ui)
	ui.set_process(false)
	ui.open(HideoutStation.Kind.STASH)
	ui._process(0.0)
	await get_tree().process_frame
	var source: GridView = ui._stash_views[0]
	var data: Dictionary = _payload(source)
	ui._start_op("load", "stash", 2, "ammo_545_std", "stash")
	ui._process(float(Balance.MAG_OPS.load_sec) * 1.1)
	await get_tree().process_frame
	_check(is_instance_valid(source) and source == ui._stash_views[0], "убежище: зарядка не пересоздала сетку")
	_check(source.drag_index(data) == 0, "убежище: вторая пачка найдена после удаления первой")
	_check(source._can_drop_data(_target(), data), "убежище: наведение второй пачки на второй магазин")
	source._drop_data(_target(), data)
	ui._process(float(Balance.MAG_OPS.load_sec) * 1.1)
	_check(int(Profile.stash[1].rounds) == 1 and int(Profile.stash[2].rounds) == 1, "убежище: зарядка перешла на второй магазин")
	_check(int(Profile.stash[0].n) == 19, "убежище: патроны не потеряны и не удвоены")
	ui._cancel_op()
	Profile.stash.remove_at(0)
	ui._process(0.0)
	_check(not source._can_drop_data(_target(), data), "израсходованную/убранную пачку нельзя бросить вместо другого предмета")
	ui.free()


func _raid() -> void:
	var level: Node = load("res://scenes/levels/f1_market.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for enemy: Node in level.get_node("Marauders").get_children():
		enemy.queue_free()
	var raid: Raid = Raid.current
	var me: Player = raid.local_player()
	me.health.invulnerable = true
	await get_tree().create_timer(0.3).timeout
	# Шаги зарядки считаем явно, чтобы число патронов не зависело от скорости headless-кадров.
	raid.set_physics_process(false)
	me.inventory.items = _entries()
	var ui: InventoryUI = raid.ui
	ui.set_process(false)
	ui._backpack_open = true
	ui._refresh_visibility()
	ui._refresh_lists(me)
	await get_tree().process_frame
	var source: GridView = ui._bp_grid
	var data: Dictionary = _payload(source)
	raid.request_item_op("load", "backpack", 2, null, "ammo_545_std", "backpack")
	_check(not raid._ops.is_empty(), "рейд: операция началась")
	raid._tick_ops(float(Balance.MAG_OPS.load_sec) * 1.1)
	ui._refresh_lists(me)
	await get_tree().process_frame
	_check(is_instance_valid(source) and source == ui._bp_grid, "рейд: зарядка не пересоздала сетку")
	_check(source.drag_index(data) == 0, "рейд: индекс пачки обновлён")
	_check(source._can_drop_data(_target(), data), "рейд: наведение второй пачки")
	source._drop_data(_target(), data)
	raid._tick_ops(float(Balance.MAG_OPS.load_sec) * 1.1)
	ui._refresh_lists(me)
	_check(int(me.inventory.items[1].rounds) == 1 and int(me.inventory.items[2].rounds) == 1, "рейд: зарядка перешла на второй магазин")
	_check(int(me.inventory.items[0].n) == 19, "рейд: патроны сохранены")
	raid.request_cancel_op()
	# Перестройка содержимого буфера и ящика также сохраняет узлы и их обработчики.
	me.inventory.buffer = [{"id": "ammo_545_std", "n": 10, "x": 0, "y": 0}]
	ui._refresh_buffer(me)
	var buffer: GridView = ui._existing_grid(ui._buf_list, "buffer")
	me.inventory.buffer[0].n = 9
	ui._refresh_buffer(me)
	_check(buffer == ui._existing_grid(ui._buf_list, "buffer") and int(buffer.items[0].n) == 9, "буфер обновляется без удаления сетки")
	var loot: LootContainer = LootContainer.new()
	loot.items = _entries()
	loot.rolled = true
	level.add_child(loot)
	ui._looting = loot
	ui._build_loot(me)
	var loot_grid: GridView = ui._existing_grid(ui._loot_list, "loot")
	loot.items[1].n = 19
	ui._build_loot(me)
	_check(loot_grid == ui._existing_grid(ui._loot_list, "loot") and int(loot_grid.items[1].n) == 19, "ящик обновляется без удаления сетки")


func _check(ok: bool, label: String) -> void:
	if not ok:
		_fails += 1
		push_error(label)
	print("  [%s] %s" % ["ok" if ok else "FAIL", label])
