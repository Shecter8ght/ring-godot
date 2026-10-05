extends Node
## Штатный профиль на zone02: снаряжение на кону, лут через Raid, эвакуация и смерть.
## Каждый исход использует собственный файл; итог проверяется до ручного сохранения.

const EVAC_PROFILE: String = "user://profile_zone02_evac_test.json"
const DEATH_PROFILE: String = "user://profile_zone02_death_test.json"
const LEVEL_SCENE: String = "res://scenes/levels/zone02_urban_belt.tscn"
const LEVEL_DEFINITION: String = "res://data/sectors/zone02_urban_belt.json"
const READY_TIMEOUT_MS: int = 20000
const OUTCOME_TIMEOUT_MS: int = 20000
const WATCHDOG_SEC: float = 90.0

var _fails: int = 0
var _checks: int = 0
var _level: Node3D
var _raid: Raid
var _player: Player
var _prepared: Dictionary = {}
var _loot_id: String = ""
var _loot_count: int = 0


func _ready() -> void:
	# Тест остаётся в корне дерева при удалении сцен между двумя независимыми рейдами.
	get_tree().current_scene = null
	get_tree().create_timer(WATCHDOG_SEC).timeout.connect(_timeout)
	if not _check("проверка без сетевой сессии", not Net.is_networked()):
		_finish()
		return
	RaidEvents.enabled = false
	if not _cached_navigation_ready():
		_finish()
		return
	await get_tree().process_frame
	await _run_case(EVAC_PROFILE, false)
	await _run_case(DEATH_PROFILE, true)
	_finish()


func _run_case(profile_path: String, death: bool) -> void:
	print("\nzone02_profile: %s, %s" % ["смерть" if death else "эвакуация", profile_path])
	if not _prepare_profile(profile_path):
		return
	if not await _enter_raid():
		await _close_level()
		return
	if not await _take_loot():
		await _close_level()
		return
	var expected_equipment: Dictionary = _player.equipment_state().duplicate(true)
	var expected_backpack: Array = _player.inventory.items.duplicate(true)
	var expected_pocket: Array = _player.inventory.pocket.duplicate(true)
	var finished: bool = await _die() if death else await _evacuate()
	if finished:
		_check("штатная хроника соответствует исходу", _raid.chronicle != null
			and _raid.analytics.outcome == ("death" if death else "extract"))
		# Дать системе ещё несколько кадров: повторная запись не должна удвоить возврат.
		await _frames(5)
		if death:
			_check("снаряжение и добыча остались в теле", _corpse_has_loadout(expected_equipment, expected_backpack))
			expected_equipment = {}
			expected_backpack = []
		_check_result(expected_equipment, expected_backpack, expected_pocket, death)
		var saved: Dictionary = _read_saved(profile_path)
		_check("автосохранение Raid: снаряжение и рюкзак", _same(saved.get("equipment"), expected_equipment)
			and _same(saved.get("backpack"), expected_backpack))
		_check("автосохранение Raid: маршрут и число выходов", String(saved.get("floor", "")) == "zone02"
			and int(saved.get("extractions", -1)) == (0 if death else 1))
	await _close_level()
	if finished:
		# Перезагрузка именно через публичный API; save() после исхода тест не вызывает.
		Profile.use_file(profile_path, false)
		_check("перечитан собственный файл", Profile.path == profile_path)
		_check_result(expected_equipment, expected_backpack, expected_pocket, death, "после чтения: ")
		_check("перечитанный маршрут zone02 доступен", Profile.floor == "zone02"
			and "zone02" in Profile.floors_open and Floors.start_block(Profile.floor) == "")


func _prepare_profile(profile_path: String) -> bool:
	Profile.pending_raid = false
	Profile.use_file(profile_path, true)
	if not _check("собственный чистый тестовый профиль", Profile.path == profile_path
		and profile_path.ends_with("_test.json") and Profile.extractions == 0):
		return false
	if not _check("маршрут выбран через Floors.select", Floors.select("zone02")
		and Profile.floor == "zone02" and Floors.scene(Profile.floor) == LEVEL_SCENE
		and Floors.start_block(Profile.floor) == ""):
		return false
	for id: String in ["w_rifle", "w_pistol", "vest_light", "helmet"]:
		if not _check("снаряжение из тайника: " + id, Profile.equip_from_stash(_stash_index(id))):
			return false
	# Количества — входные данные теста, а ёмкости и правила снаряжения берёт игра.
	for pair: Array in [["ammo_545", 60], ["ammo_9x19", 34], ["bandage", 2], ["grenade", 1]]:
		var id: String = String(pair[0])
		if not _check("рюкзак из тайника: " + id, Profile.stash_to_backpack(_stash_index(id), int(pair[1]))):
			return false
	_prepared = {"equipment": Profile.equipment.duplicate(true), "backpack": Profile.backpack.duplicate(true),
		"stash": Profile.stash.duplicate(true), "money": Profile.money, "trust": Profile.trust}
	Profile.use_file(profile_path, false)
	return _check("снаряжение и маршрут сохранены перед рейдом", Profile.floor == "zone02"
		and _same(Profile.equipment, _prepared.equipment) and _same(Profile.backpack, _prepared.backpack))


func _cached_navigation_ready() -> bool:
	var definition: Dictionary = SectorBuilder.load_def(LEVEL_DEFINITION)
	var bounds: Array = definition.get("bounds", [])
	if not _check("данные нового уровня доступны", bounds.size() == 4):
		return false
	var tile: float = float(Balance.URBAN_WORLD.nav_tile)
	var columns: int = int(ceil((float(bounds[2]) - float(bounds[0])) / tile))
	var rows: int = int(ceil((float(bounds[3]) - float(bounds[1])) / tile))
	for x: int in range(columns):
		for z: int in range(rows):
			var path: String = "%s/tile_%d_%d.res" % [UrbanNavigation.CACHE_DIR, x, z]
			if not ResourceLoader.exists(path):
				_check("готовый кэш навигации; rebake запрещён", false, path)
				return false
	return _check("все тайлы кэша доступны; запуск без rebake", true, "%d тайлов" % (columns * rows))


func _enter_raid() -> bool:
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	Profile.pending_raid = true
	var scene: PackedScene = load(Floors.scene(Profile.floor)) as PackedScene
	if not _check("выбранная сцена загружена", scene != null):
		return false
	_level = scene.instantiate() as Node3D
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	_raid = Raid.current
	_player = _raid.local_player() if _raid != null else null
	if not _check("игрок и Raid созданы на новом уровне", _raid != null and _player != null
		and _level.scene_file_path == LEVEL_SCENE):
		return false
	_player.health.invulnerable = true
	var start_ms: int = Time.get_ticks_msec()
	while not bool(_level.get("_nav_baked")) or not _player.inventory.loadout_ready or _player.weapon_id == "":
		if Time.get_ticks_msec() - start_ms > READY_TIMEOUT_MS:
			_check("штатный рейд готов в пределах таймаута", false)
			return false
		await get_tree().physics_frame
	# Проверяется профиль, поэтому AI и перемещение не вносят случайный урон и столкновения.
	for enemy: Node in _level.get_node("Marauders").get_children():
		enemy.set_physics_process(false)
	_player.set_physics_process(false)
	_check("настоящий pending_raid и loadout_mode", Profile.pending_raid and _player.loadout_mode
		and _player.inventory.loadout_ready)
	_check("take_loadout снял снаряжение и рюкзак с профиля", Profile.equipment.is_empty() and Profile.backpack.is_empty())
	var saved: Dictionary = _read_saved(Profile.path)
	_check("изъятие снаряжения сохранено на диске", saved.has("equipment") and saved.has("backpack")
		and (saved.equipment as Dictionary).is_empty() and (saved.backpack as Array).is_empty())
	_check("в Inventory выданы слоты из профиля", _equipment_ids(_player.inventory.equipment) == _equipment_ids(_prepared.equipment))
	for pair: Array in [["primary", "ammo_545_std"], ["secondary", "ammo_919_fmj"]]:
		var slot: String = String(pair[0])
		var ammo_id: String = String(pair[1])
		var before: int = _count(_prepared.backpack, ammo_id) + Gear.total_rounds((_prepared.equipment as Dictionary).get(slot, {}))
		var after: int = _player.inventory.count(ammo_id) + Gear.total_rounds(_player.inventory.equipment.get(slot, {}))
		_check("патроны перенесены без потерь: " + slot, before == after, "%d -> %d" % [before, after])
	return true


func _take_loot() -> bool:
	var containers: Array[Node] = get_tree().get_nodes_in_group("loot_containers")
	if not _check("штатные контейнеры нового уровня существуют", not containers.is_empty()):
		return false
	for node: Node in containers:
		var container: LootContainer = node as LootContainer
		if container == null or not _level.is_ancestor_of(container):
			continue
		container.roll()
		for raw_entry: Variant in container.items:
			var entry: Dictionary = (raw_entry as Dictionary).duplicate(true)
			entry["n"] = 1
			if ItemDb.room_in(_player.inventory.items, entry, Balance.BACKPACK_GRID) < 1:
				continue
			_loot_id = String(entry.id)
			var before: int = _player.inventory.count(_loot_id)
			var left: int = _count(container.items, _loot_id)
			await _put_player(container.global_position + Vector3.RIGHT * (Balance.INTERACT_RADIUS * 0.5))
			_raid.request_take(container, _loot_id, 1)
			_loot_count = before + 1
			return _check("лут перенесён через Raid.request_take в Inventory", _player.inventory.count(_loot_id) == _loot_count
				and _count(container.items, _loot_id) == left - 1 and ItemDb.grid_ok(_player.inventory.items, Balance.BACKPACK_GRID),
				"%s: %d -> %d; %s" % [_loot_id, before, _player.inventory.count(_loot_id), str(container.get_path())])
	return _check("в контейнерах есть добыча, которая помещается в рюкзак", false)


func _evacuate() -> bool:
	var point: ExtractionPoint = null
	for node: Node in get_tree().get_nodes_in_group("extractions"):
		var candidate: ExtractionPoint = node as ExtractionPoint
		if candidate != null and _level.is_ancestor_of(candidate) and _raid.extraction_block_reason(candidate) == "":
			point = candidate
			break
	if not _check("штатная открытая точка эвакуации существует", point != null):
		return false
	await _put_player(point.global_position)
	_check("игрок внутри штатной зоны", point.contains(_player.global_position))
	await _frames(2)
	var channel: Array = _raid.channel.get(_player.peer_id, [])
	_check("начался обычный короткий отсчёт", channel.size() == 2 and float(channel[1]) > 0.0
		and _raid.evac_wait.is_empty() and not _raid.is_extracted(_player.peer_id), str(channel))
	var start_ms: int = Time.get_ticks_msec()
	while not (_raid.is_extracted(_player.peer_id) and _raid.over and _raid.chronicle != null):
		if Time.get_ticks_msec() - start_ms > OUTCOME_TIMEOUT_MS:
			return _check("штатная эвакуация завершилась в пределах таймаута", false)
		await get_tree().process_frame
	return _check("эвакуирован штатным Raid после отсчёта", String(_raid.extracted.get(_player.peer_id, "")) == point.display_name
		and not _raid.dead.has(_player.peer_id) and not _player.is_in_group("players"),
		"%s, %.1f с" % [point.display_name, point.channel_s])


func _die() -> bool:
	_check("до смерти игрок не эвакуирован", not _raid.has_left(_player.peer_id))
	_player.health.invulnerable = false
	# Штатное тяжёлое ранение, затем добивание; состояние Raid и профиль меняет сама игра.
	_player.health.take_damage(_player.health.max_hp + Balance.DOWN_HP, Vector3.ZERO, "blast_close")
	if _player.health.downed:
		_player.health.take_damage(Balance.DOWN_HP, Vector3.ZERO, "blast_close")
	var start_ms: int = Time.get_ticks_msec()
	while not (_raid.dead.has(_player.peer_id) and _raid.over and _raid.chronicle != null):
		if Time.get_ticks_msec() - start_ms > OUTCOME_TIMEOUT_MS:
			return _check("штатная смерть завершилась в пределах таймаута", false)
		await get_tree().process_frame
	return _check("смерть засчитана без эвакуации", not _player.is_alive() and not _raid.has_left(_player.peer_id))


func _check_result(equipment: Dictionary, backpack: Array, pocket: Array, death: bool, prefix: String = "") -> void:
	_check(prefix + "снаряжение потеряно" if death else prefix + "снаряжение вернулось с состоянием оружия",
		_same(Profile.equipment, equipment))
	_check(prefix + "рюкзак и добыча потеряны" if death else prefix + "рюкзак и добыча вернулись",
		_same(Profile.backpack, backpack) and _count(Profile.backpack, _loot_id) == (0 if death else _loot_count))
	_check(prefix + "карман соответствует Inventory", _same(Profile.pocket, pocket))
	_check(prefix + "счётчик эвакуаций не дублируется", Profile.extractions == (0 if death else 1))
	_check(prefix + "тайник и деньги сохранились", _same(Profile.stash, _prepared.stash) and Profile.money == int(_prepared.money))
	_check(prefix + "доверие соответствует исходу", Profile.trust == int(_prepared.trust) if death
		else Profile.trust >= int(_prepared.trust) + Balance.TRUST_PER_EXTRACTION)


func _corpse_has_loadout(equipment: Dictionary, backpack: Array) -> bool:
	var expected: Array = backpack.duplicate(true) + equipment.values()
	for node: Node in _raid.get_node("Drops").get_children():
		var container: LootContainer = node as LootContainer
		if container != null and container.display_name.begins_with("Тело:") and _counts(container.items) == _counts(expected):
			return true
	return false


func _put_player(position: Vector3) -> void:
	_player.global_position = position + Vector3.UP * 0.1
	_player.velocity = Vector3.ZERO
	await get_tree().physics_frame
	await get_tree().physics_frame


func _close_level() -> void:
	if is_instance_valid(_level):
		get_tree().current_scene = null
		_level.queue_free()
		await _frames(2)
	_level = null
	_raid = null
	_player = null
	Profile.pending_raid = false


func _read_saved(profile_path: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(profile_path))
	_check("собственный JSON читается с диска", parsed is Dictionary, profile_path)
	return parsed as Dictionary if parsed is Dictionary else {}


func _equipment_ids(equipment: Dictionary) -> Dictionary:
	var ids: Dictionary = {}
	for slot: String in equipment:
		ids[slot] = String((equipment[slot] as Dictionary).get("id", ""))
	return ids


func _counts(items: Array) -> Dictionary:
	var counts: Dictionary = {}
	for raw_entry: Variant in items:
		var entry: Dictionary = raw_entry as Dictionary
		var id: String = String(entry.id)
		counts[id] = int(counts.get(id, 0)) + int(entry.n)
	return counts


func _count(items: Array, id: String) -> int:
	return int(_counts(items).get(id, 0))


func _stash_index(id: String) -> int:
	var canonical: String = WeaponDb.canonical(id)
	for index: int in range(Profile.stash.size()):
		if String(Profile.stash[index].id) == canonical:
			return index
	return -1


func _same(actual: Variant, expected: Variant) -> bool:
	# JSON нормализует int/float при сравнении снимка Inventory с перечитанным профилем.
	return JSON.parse_string(JSON.stringify(actual)) == JSON.parse_string(JSON.stringify(expected))


func _frames(count: int) -> void:
	for index: int in range(count):
		await get_tree().process_frame


func _check(title: String, ok: bool, info: String = "") -> bool:
	_checks += 1
	if not ok:
		_fails += 1
	print("  [%s] %s%s" % ["ok" if ok else "FAIL", title, "  " + info if info != "" else ""])
	return ok


func _timeout() -> void:
	_check("общий таймаут теста", false)
	_finish()


func _finish() -> void:
	print("zone02_profile_test: проверок %d, провалено %d" % [_checks, _fails])
	get_tree().quit(1 if _fails > 0 else 0)
