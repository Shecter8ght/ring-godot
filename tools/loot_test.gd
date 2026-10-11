extends Node
## Каталог, тематические броски, настоящая модель, отказ полного рюкзака и вынос/продажа.
var fails: int = 0


func _ready() -> void:
	if name != "LootTestRunner":
		var runner: Node = Node.new()
		runner.name = "LootTestRunner"
		runner.set_script(get_script())
		get_tree().root.add_child.call_deferred(runner)
		return
	await _run()


func _run() -> void:
	Profile.use_file("user://loot_test.json", true)
	var reached: Dictionary = {}
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = 97141
	var manifests: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/items/models/loot/manifest.json"))
	for id: String in Balance.CIVILIAN_LOOT_VALUES:
		var item: Dictionary = ItemDb.item(id)
		check(id + ": описание, цена, вес", String(item.desc).length() > 50 and ItemDb.value(id) > 0 and ItemDb.weight(id) > 0)
		check(id + ": модель и иконка", ResourceLoader.exists(String(item.model)) and ResourceLoader.exists("res://assets/icons/%s.png" % id))
		var model: Node3D = ItemModels.build(id)
		var bounds: AABB = ItemModels.bounds(model)
		check(id + ": размер в метрах и сетка в бюджете", bounds.size.length() > 0.05 and bounds.size.length() < 1.6 and int(manifests[id].triangles) <= 6600)
		model.free()
	for table: String in Balance.CIVILIAN_LOOT:
		for attempt: int in range(3000):
			for entry: Dictionary in ItemDb.roll(table, rng):
				if not ItemDb.exists(String(entry.id)):
					check("неизвестный предмет " + String(entry.id), false)
				if Balance.CIVILIAN_LOOT_VALUES.has(String(entry.id)):
					reached[entry.id] = true
			var visible_id: String = ItemDb.loose_item(table, rng)
			check_silent("видимая вещь соответствует теме " + table, visible_id != "" and (_loose_gear(table, visible_id) or Balance.CIVILIAN_LOOT_VALUES.has(visible_id) or Balance.VALUABLE_LOOT_VALUES.has(visible_id)))
	check("все 24 предмета достижимы в тематическом луте", reached.size() == 24)
	Profile.equipment = {"backpack": ItemDb.make(Balance.BACKPACK_START, 1)}
	Profile.backpack = []
	Profile.pending_raid = true
	Profile.from_hideout = true
	Profile.save()
	RaidEvents.enabled = false
	get_tree().change_scene_to_file("res://scenes/levels/f1_market.tscn")
	for frame: int in range(25):
		await get_tree().process_frame
	var player: Player = Raid.current.local_player()
	player.set_physics_process(false)
	player.health.hp = 1e9
	var point: LooseLoot = (load("res://scenes/world/loose_loot.tscn") as PackedScene).instantiate() as LooseLoot
	point.item_id = "multimeter"
	point.spawn_chance = 1.0
	get_tree().current_scene.add_child(point)
	point.global_position = player.global_position
	check("в мире настоящая модель и опора снизу", point._vis.get_child_count() == 1 and absf(ItemModels.bounds(point._vis).position.y - float(Balance.LOOSE_LOOT.surface_gap)) < 0.005)
	# Заполнить все клетки предметами 1×1; даже при выключенном рюкзаке есть карманы.
	var full: Array = []
	var grid: Vector2i = player.inventory.backpack_grid()
	for y: int in range(grid.y):
		for x: int in range(grid.x):
			full.append({"id": "watch", "n": ItemDb.stack("watch"), "x": x, "y": y})
	player.inventory.items = full
	point._use(1)
	check("полный рюкзак сохраняет вещь в мире", point.items.size() == 1 and point.can_use() and point._vis.get_child_count() == 1)
	player.inventory.items = []
	player.global_position = point.global_position + Vector3(20, 0, 0)
	point._use(1)
	check("подбор издалека отклонён", point.items.size() == 1)
	player.global_position = point.global_position
	point._use(1)
	point._use(1)
	check("подбор без копии, найдено в рейде", player.inventory.count("multimeter") == 1 and bool(player.inventory.items[0].fir))
	check("из мира исчезла модель и подсказка", point.items.is_empty() and not point.can_use() and point._vis.get_child_count() == 0)
	var ext: ExtractionPoint = ExtractionPoint.new()
	get_tree().current_scene.add_child(ext)
	Raid.current._extract(player, ext)
	for frame: int in range(12):
		await get_tree().process_frame
	check("реальная эвакуация сохраняет находку", count_item(Profile.backpack, "multimeter") == 1)
	Profile._loaded = false
	Profile.ensure()
	check("сохранение содержит вынесенную вещь", count_item(Profile.backpack, "multimeter") == 1)
	var before: int = Profile.money
	check("продажа Михалычу проходит", Profile.sell(0, 1, "backpack"))
	check("деньги зачислены и вещь удалена", Profile.money - before == Profile.sell_price(ItemDb.make("multimeter", 1)) and count_item(Profile.backpack, "multimeter") == 0)
	print("loot_test: failures=", fails)
	get_tree().quit(1 if fails else 0)


func check(label: String, passed: bool) -> void:
	print("OK " if passed else "FAIL ", label)
	if not passed:
		fails += 1


func check_silent(label: String, passed: bool) -> void:
	if not passed:
		check(label, passed)


func count_item(list: Array, id: String) -> int:
	var count: int = 0
	for entry: Dictionary in list:
		if String(entry.id) == id:
			count += int(entry.n)
	return count


## Снаряжение, которому в этой теме можно лежать на виду (Balance.LOOSE_GEAR).
func _loose_gear(table: String, id: String) -> bool:
	for pair: Array in Balance.LOOSE_GEAR.get(table, []):
		if String(pair[0]) == id:
			return true
	return false
