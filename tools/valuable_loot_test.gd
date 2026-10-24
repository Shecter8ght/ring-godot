extends Node
## Проверка каталога, вскрытия пачек, отказов сигнала и единственного общего груза.
var fails: int = 0


func _ready() -> void:
	if name != "ValuableLootRunner":
		var runner: Node = Node.new()
		runner.name = "ValuableLootRunner"
		runner.set_script(get_script())
		get_tree().root.add_child.call_deferred(runner)
		return
	await _run()


func _run() -> void:
	Profile.use_file("user://valuable_loot_test.json", true)
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/items/models/valuable/manifest.json"))
	check("ровно 100 новых предметов и моделей", Balance.VALUABLE_LOOT_VALUES.size() == 100 and manifest.size() == 100)
	for id: String in Balance.VALUABLE_LOOT_VALUES:
		var item: Dictionary = ItemDb.item(id)
		check(id, ItemDb.value(id) > 0 and String(item.desc).length() > 50 and ItemDb.weight(id) > 0 and ResourceLoader.exists(String(item.model)) and ResourceLoader.exists("res://assets/icons/%s.png" % id))
		check(id + " текстуры внутри модели", FileAccess.get_file_as_string(String(item.model) + ".import").contains("gltf/embedded_image_handling=2"))
		var model: Node3D = ItemModels.build(id)
		var bounds: AABB = ItemModels.bounds(model)
		check(id + " сетка/метры", int(manifest[id].triangles) < 6600 and bounds.size.length() > 0.01 and bounds.size.length() < 1.8)
		model.free()
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = 81725
	var reached: Dictionary = {}
	for table: String in Balance.VALUABLE_LOOT:
		for i: int in range(6000):
			for entry: Dictionary in ItemDb.roll(table, rng):
				if Balance.VALUABLE_LOOT_VALUES.has(String(entry.id)):
					reached[entry.id] = true
	check("все 100 предметов достижимы в обычном луте", reached.size() == 100)
	for pack: String in Balance.LOOT_PACKS:
		var list: Array = [ItemDb.make(pack, 1)]
		list[0]["fir"] = true
		var result: Array = ItemDb.unpack(list, Vector2i(10, 10), 0, pack)
		check(pack + " выдаёт боеприпасы/расходники", not result.is_empty() and count_item(result, pack) == 0)
		for content: Array in Balance.LOOT_PACKS[pack]:
			check(pack + " количество", count_item(result, String(content[0])) == int(content[1]))
		check(pack + " FIR", not result.is_empty() and bool(result[0].fir))
	var tight: Array = [ItemDb.make("pack_frag", 1)]
	check("вскрытие использует место коробки и не меняет исходную копию", not ItemDb.unpack(tight, Vector2i(2, 2), 0, "pack_frag").is_empty() and count_item(tight, "pack_frag") == 1)
	check("подмена id/индекса отклоняется", ItemDb.unpack(tight, Vector2i(10, 10), 0, "pack_flares").is_empty() and ItemDb.unpack(tight, Vector2i(10, 10), -1, "pack_frag").is_empty())
	Profile.equipment = {"backpack": ItemDb.make(Balance.BACKPACK_START, 1)}
	Profile.backpack = [ItemDb.make("pack_919_fmj", 1)]
	check("вскрытие в убежище", Profile.unpack("backpack", 0, "pack_919_fmj") and count_item(Profile.backpack, "ammo_919_fmj") == 50)
	Profile.backpack = []
	Profile.pending_raid = true
	Profile.from_hideout = true
	Profile.save()
	RaidEvents.enabled = false
	get_tree().change_scene_to_file("res://scenes/levels/mall_map.tscn")
	for i: int in range(35):
		await get_tree().process_frame
	var pl: Player = Raid.current.local_player()
	pl.set_physics_process(false)
	pl.health.hp = 1e9
	# Далеко от существующей карты: физическая площадка и временная крыша теста.
	var floor_body: StaticBody3D = StaticBody3D.new()
	var shape: CollisionShape3D = CollisionShape3D.new()
	var box: BoxShape3D = BoxShape3D.new()
	box.size = Vector3(20, 0.2, 20)
	shape.shape = box
	floor_body.add_child(shape)
	get_tree().current_scene.add_child(floor_body)
	floor_body.global_position = Vector3(500, -0.1, 500)
	pl.global_position = Vector3(500, 0.1, 500)
	await get_tree().physics_frame
	Raid.current.request_supply_signal()
	check("без снаряжения вызова нет", Raid.current.supply_state.is_empty())
	pl.inventory.items = [ItemDb.make("signal_launcher", 1), ItemDb.make("supply_signal", 2)]
	var roof: StaticBody3D = floor_body.duplicate() as StaticBody3D
	get_tree().current_scene.add_child(roof)
	roof.global_position = Vector3(500, 3, 500)
	await get_tree().physics_frame
	Raid.current.request_supply_signal()
	check("крыша сохраняет патрон", Raid.current.supply_state.is_empty() and pl.inventory.count("supply_signal") == 2)
	roof.queue_free()
	await get_tree().physics_frame
	await get_tree().physics_frame
	var site: Vector3 = Raid.current._supply_site(pl)
	var obstacle: StaticBody3D = StaticBody3D.new()
	var obstacle_collision: CollisionShape3D = CollisionShape3D.new()
	var obstacle_shape: BoxShape3D = BoxShape3D.new()
	obstacle_shape.size = Vector3(0.2, 0.8, 0.2)
	obstacle_collision.shape = obstacle_shape
	obstacle.add_child(obstacle_collision)
	get_tree().current_scene.add_child(obstacle)
	obstacle.global_position = site + Vector3(0.8, 0.4, 0.8)
	await get_tree().physics_frame
	Raid.current.request_supply_signal()
	check("препятствие у угла ящика сохраняет патрон", Raid.current.supply_state.is_empty() and pl.inventory.count("supply_signal") == 2)
	obstacle.queue_free()
	await get_tree().physics_frame
	await get_tree().physics_frame
	Raid.current.request_supply_signal()
	Raid.current.request_supply_signal()
	check("один вызов, один патрон, пистолет остаётся", not Raid.current.supply_state.is_empty() and pl.inventory.count("supply_signal") == 1 and pl.inventory.count("signal_launcher") == 1)
	if not Raid.current.supply_state.is_empty():
		Raid.current.supply_state.elapsed = float(Balance.SUPPLY_SIGNAL.delay) - 0.01
		Raid.current._tick_supply(0.02)
		Raid.current._tick_supply(0.02)
		var crates: Array = Raid.current._drops.get_children().filter(func(n: Node) -> bool: return n is LootContainer and n.display_name == "Редкий груз снабжения")
		check("ровно один общий груз", crates.size() == 1 and bool(Raid.current.supply_state.dropped))
		if not crates.is_empty():
			var crate: LootContainer = crates[0] as LootContainer
			# груз — боевое (Balance.SUPPLY_LOOT): ствол высокого тира, магазины и обвес к нему, броня
			var guns: int = 0
			var mags: int = 0
			var mods: int = 0
			var armor: int = 0
			for e: Dictionary in crate.items:
				var id: String = String(e.id)
				if WeaponDb.is_weapon(id):
					guns += 1
					check("ствол из груза — высокого тира, в хорошем состоянии, с полным магазином", int(ItemDb.item(id).get("tier", 1)) >= int(Balance.SUPPLY_LOOT.weapon_tier)
						and float(e.dur) >= float(Balance.SUPPLY_LOOT.dur[0]) and int((e.mag as Dictionary).rounds) > 0)
				elif not WeaponDb.magazine(id).is_empty():
					mags += 1
				elif not WeaponDb.attachment(id).is_empty():
					mods += 1
				elif not WeaponDb.vest(id).is_empty() or not WeaponDb.helmet(id).is_empty():
					armor += 1
				check("всё найдено в рейде, без патрона вызова и без ценностей на продажу", bool(e.fir) and id != "supply_signal" and not Balance.VALUABLE_LOOT_VALUES.has(id))
			check("в грузе ствол, обвес к нему и броня", guns >= 1 and mods >= 1 and armor >= 1)
			print("  груз: стволов %d, магазинов %d, обвеса %d, брони %d, всего %d" % [guns, mags, mods, armor, crate.items.size()])
	print("valuable_loot_test: failures=", fails)
	get_tree().quit(1 if fails else 0)


func count_item(list: Array, id: String) -> int:
	var n: int = 0
	for item: Dictionary in list:
		if String(item.id) == id:
			n += int(item.n)
	return n


func check(label: String, passed: bool) -> void:
	print("OK " if passed else "FAIL ", label)
	if not passed:
		fails += 1
