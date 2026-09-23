class_name Profile
extends RefCounted
## Профиль игрока между рейдами — у каждого свой, на его компьютере (user://profile.json):
## деньги, тайник (Balance.STASH_CELLS ячеек), снаряжение и рюкзак, с которыми он пойдёт в рейд.
## Правило жанра: уходя в рейд, снаряжение и рюкзак рискуешь потерять — при входе в рейд они
## снимаются с профиля (take_loadout) и возвращаются только при эвакуации (return_loadout).
## Тесты и запуск уровня напрямую профиль не трогают: pending_raid = false — «песочница».

const PATH := "user://profile.json"

## Следующий рейд — из убежища (со снаряжением профиля). Ставит убежище/лобби, снимает рейд.
static var pending_raid: bool = false
## Пришёл в лобби из убежища — рейд, который начнёт хост, будет со снаряжением профиля.
## Тесты сети сюда не заходят и остаются в песочнице.
static var from_hideout: bool = false
## Путь к файлу (тесты подменяют, чтобы не портить настоящий профиль).
static var path: String = PATH

static var money: int = 0
static var stash: Array = []
static var equipment: Dictionary = {}
static var backpack: Array = []
## Доверие торговца (Михалыча): растёт за удачные эвакуации, открывает маршруты на этажи (Floors).
static var trust: int = 0
## Сколько раз выбрался из рейда живым.
static var extractions: int = 0
## Открытые маршруты (id этажей из data/floors.json) и выбранный для следующего рейда.
static var floors_open: Array = ["f1"]
static var floor: String = "f1"
static var _loaded: bool = false


static func ensure() -> void:
	if _loaded:
		return
	_loaded = true
	var text := FileAccess.get_file_as_string(path) if FileAccess.file_exists(path) else ""
	var d: Variant = JSON.parse_string(text) if text != "" else null
	if d is Dictionary:
		money = int(d.get("money", 0))
		stash = d.get("stash", [])
		equipment = d.get("equipment", {})
		backpack = d.get("backpack", [])
		trust = int(d.get("trust", 0))
		extractions = int(d.get("extractions", 0))
		floors_open = d.get("floors_open", ["f1"])
		if not "f1" in floors_open:
			floors_open.append("f1")
		floor = String(d.get("floor", "f1"))
		if not floor in floors_open:
			floor = "f1"
		_fix_numbers()
		_fit_grids()
	else:
		_starter()
		save()


## Первый запуск: немного денег и базовый набор в тайнике.
static func _starter() -> void:
	money = Balance.START_MONEY
	stash = []
	equipment = {}
	backpack = []
	trust = 0
	extractions = 0
	floors_open = ["f1"]
	floor = "f1"
	for pair in Balance.START_STASH:
		ItemDb.add_to(stash, ItemDb.make(String(pair[0]), int(pair[1])), Balance.STASH_GRID)


## JSON отдаёт числа как float — количества делаем целыми.
static func _fix_numbers() -> void:
	for list in [stash, backpack]:
		for it in list:
			it.n = int(it.n)
	for slot in equipment:
		equipment[slot].n = 1


## Тайник и рюкзак — сетки: записи без мест (старый профиль, вернувшиеся патроны) раскладываются
## заново; что не влезло в рюкзак — в тайник, что не влезло в тайник — теряется (с предупреждением).
static func _fit_grids() -> void:
	if not ItemDb.grid_ok(backpack, Balance.BACKPACK_GRID):
		for e in ItemDb.pack(backpack, Balance.BACKPACK_GRID):
			ItemDb.add_to(stash, e, Balance.STASH_GRID)
	if not ItemDb.grid_ok(stash, Balance.STASH_GRID):
		var lost := ItemDb.pack(stash, Balance.STASH_GRID)
		if not lost.is_empty():
			push_warning("Profile: тайник переполнен, не поместилось: %s" % str(lost))


static func save() -> void:
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		push_error("Profile: не удалось записать " + path)
		return
	f.store_string(JSON.stringify({"money": money, "stash": stash, "equipment": equipment, "backpack": backpack,
		"trust": trust, "extractions": extractions, "floors_open": floors_open, "floor": floor}, "  "))


## Тесты: свой файл и чистый старт.
static func use_file(p: String, fresh: bool) -> void:
	path = p
	_loaded = false
	if fresh and FileAccess.file_exists(p):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(p))
	ensure()


## Оружие в руках для вида в убежище: основное, иначе пистолет, иначе "".
static func equipped_weapon() -> String:
	ensure()
	for slot in ["primary", "secondary"]:
		if equipment.has(slot):
			return String(ItemDb.equip(String(equipment[slot].id)).get("weapon", ""))
	return ""


static func stash_cells() -> int:
	return ItemDb.cells_of(stash)


static func backpack_cells() -> int:
	return ItemDb.cells_of(backpack)


# ---------------------------------------------------------------- убежище

## Передвинуть запись внутри тайника или рюкзака (перетащили мышью).
static func move_in(in_backpack: bool, idx: int, x: int, y: int, r: bool) -> bool:
	var ok := ItemDb.move_in(backpack if in_backpack else stash, Balance.BACKPACK_GRID if in_backpack else Balance.STASH_GRID, idx, x, y, r)
	if ok:
		save()
	return ok


## Перенести запись idx между тайником и рюкзаком прямо в место (x, y); false — не влезло.
static func transfer_to(from_backpack: bool, idx: int, x: int, y: int, r: bool) -> bool:
	var from: Array = backpack if from_backpack else stash
	var to: Array = stash if from_backpack else backpack
	var grid := Balance.STASH_GRID if from_backpack else Balance.BACKPACK_GRID
	if idx < 0 or idx >= from.size():
		return false
	var e: Dictionary = (from[idx] as Dictionary).duplicate(true)
	var k := ItemDb.put_at(to, e, grid, x, y, r)
	if k <= 0:
		return false
	ItemDb.remove_at(from, idx, k)
	save()
	return true


## Из тайника в рюкзак (n штук записи idx); false — не влезло.
static func stash_to_backpack(idx: int, n: int) -> bool:
	return _move(stash, backpack, idx, n, Balance.BACKPACK_GRID)


static func backpack_to_stash(idx: int, n: int) -> bool:
	return _move(backpack, stash, idx, n, Balance.STASH_GRID)


static func _move(from: Array, to: Array, idx: int, n: int, cap: Vector2i) -> bool:
	if idx < 0 or idx >= from.size():
		return false
	var probe: Dictionary = (from[idx] as Dictionary).duplicate(true)
	probe.n = mini(n, int(probe.n))
	var k := ItemDb.room_in(to, probe, cap)
	if k <= 0:
		return false
	var out := ItemDb.remove_at(from, idx, mini(k, int(probe.n)))
	ItemDb.add_to(to, out, cap)
	save()
	return true


## Надеть из тайника; то, что было в слоте, — в тайник.
static func equip_from_stash(idx: int) -> bool:
	return equip_from(false, idx)


## Надеть предмет из тайника или рюкзака; то, что было в слоте, — туда же (не влезло — в тайник).
static func equip_from(in_backpack: bool, idx: int) -> bool:
	var src: Array = backpack if in_backpack else stash
	var grid := Balance.BACKPACK_GRID if in_backpack else Balance.STASH_GRID
	if idx < 0 or idx >= src.size():
		return false
	var id := String(src[idx].id)
	var slot := String(ItemDb.equip(id).get("slot", ""))
	if slot == "":
		return false
	var entry := ItemDb.remove_at(src, idx, 1)
	for key in ["x", "y", "r"]:
		entry.erase(key)
	if not entry.has("dur") and ItemDb.equip(id).has("durability"):
		entry.dur = float(ItemDb.equip(id).durability)
	if equipment.has(slot):
		var old: Dictionary = equipment[slot]
		if ItemDb.add_to(src, old, grid) == 0:
			ItemDb.add_to(stash, old, Balance.STASH_GRID)
	equipment[slot] = entry
	save()
	return true


static func unequip(slot: String) -> bool:
	if not equipment.has(slot):
		return false
	var probe: Dictionary = equipment[slot]
	if ItemDb.room_in(stash, probe, Balance.STASH_GRID) <= 0:
		return false
	ItemDb.add_to(stash, probe, Balance.STASH_GRID)
	equipment.erase(slot)
	save()
	return true


## Снять прямо в место (x, y) тайника или рюкзака (перетащили из слота в сетку).
static func unequip_to(slot: String, to_backpack: bool, x: int, y: int, r: bool) -> bool:
	if not equipment.has(slot):
		return false
	var to: Array = backpack if to_backpack else stash
	var grid := Balance.BACKPACK_GRID if to_backpack else Balance.STASH_GRID
	if ItemDb.put_at(to, equipment[slot], grid, x, y, r) <= 0:
		return false
	equipment.erase(slot)
	save()
	return true


# ---------------------------------------------------------------- верстак

## Обвесы на оружии в слоте снаряжения (primary/secondary): слот обвеса -> id.
static func weapon_mods(weapon_slot: String) -> Dictionary:
	if not equipment.has(weapon_slot):
		return {}
	return (equipment[weapon_slot] as Dictionary).get("mods", {})


## Поставить обвес (запись idx тайника или рюкзака) на надетое оружие; старый из того же слота
## ложится туда, откуда взят новый (место освободилось — обмен один на один).
static func install_mod(weapon_slot: String, idx: int, from_backpack: bool = false) -> bool:
	var src: Array = backpack if from_backpack else stash
	if not equipment.has(weapon_slot) or idx < 0 or idx >= src.size():
		return false
	var mod := String(src[idx].id)
	var weapon: Dictionary = equipment[weapon_slot]
	if not ItemDb.mod_fits(mod, String(weapon.id)):
		return false
	var slot := String(ItemDb.mod_spec(mod).slot)
	ItemDb.remove_at(src, idx, 1)
	var mods: Dictionary = weapon.get("mods", {}).duplicate()
	if mods.has(slot):
		ItemDb.add_to(src, ItemDb.make(String(mods[slot]), 1), Balance.BACKPACK_GRID if from_backpack else Balance.STASH_GRID)
	mods[slot] = mod
	weapon["mods"] = mods
	save()
	return true


static func remove_mod(weapon_slot: String, mod_slot: String) -> bool:
	var mods := weapon_mods(weapon_slot).duplicate()
	if not mods.has(mod_slot):
		return false
	var e := ItemDb.make(String(mods[mod_slot]), 1)
	if ItemDb.room_in(stash, e, Balance.STASH_GRID) <= 0:
		return false
	ItemDb.add_to(stash, e, Balance.STASH_GRID)
	mods.erase(mod_slot)
	(equipment[weapon_slot] as Dictionary)["mods"] = mods
	save()
	return true


# ---------------------------------------------------------------- торговец

static func buy_price(id: String) -> int:
	return int(ceil(float(ItemDb.value(id)) * Balance.TRADER_BUY_MULT))


static func sell_price(entry: Dictionary) -> int:
	return int(floor(float(ItemDb.entry_value(entry)) * Balance.TRADER_SELL_MULT))


static func buy(id: String, n: int) -> bool:
	var cost := buy_price(id) * n
	if cost > money or ItemDb.room_in(stash, ItemDb.make(id, n), Balance.STASH_GRID) < n:
		return false
	money -= cost
	ItemDb.add_to(stash, ItemDb.make(id, n), Balance.STASH_GRID)
	save()
	return true


static func sell(idx: int, n: int) -> bool:
	if idx < 0 or idx >= stash.size():
		return false
	var out := ItemDb.remove_at(stash, idx, n)
	if out.is_empty():
		return false
	money += sell_price(out)
	save()
	return true


# ---------------------------------------------------------------- рейд

## Вход в рейд: снаряжение и рюкзак уходят с профиля (на кону), возвращаются при эвакуации.
static func take_loadout() -> Dictionary:
	ensure()
	var out := {"equipment": equipment.duplicate(true), "backpack": backpack.duplicate(true)}
	equipment = {}
	backpack = []
	save()
	return out


## Эвакуировался: снаряжение надето, вынесенное — в рюкзаке (разложить по тайнику — в убежище).
## Удачный выход добавляет доверия торговца; вынес много — ещё больше.
static func return_loadout(eq: Dictionary, items: Array, loot_value: int = 0) -> void:
	ensure()
	extractions += 1
	trust += Balance.TRUST_PER_EXTRACTION
	if loot_value >= Balance.TRUST_BONUS_VALUE:
		trust += Balance.TRUST_BONUS
	equipment = eq.duplicate(true)
	backpack = items.duplicate(true)
	_fix_numbers()
	_fit_grids()
	save()
