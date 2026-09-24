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
## Модули убежища: id -> уровень (см. Upgrades, data/hideout.json).
static var modules: Dictionary = {}
## Задания: взятые (id -> счётчик) и сданные (см. Missions).
static var missions_active: Dictionary = {}
static var missions_done: Array = []
## Защищённый карман: что в нём — не теряется при смерти (сетка — по модулю «карман»).
static var pocket: Array = []
## Сюжетные квесты (см. Quests, data/quests): id -> {state, stage, obj, clues, count}.
static var quests: Dictionary = {}
## Сюжетные флаги мира (anton_rescued, sergey_secret_revealed…) — их читают будущие квесты.
static var flags: Dictionary = {}
## Товары торговца, открытые сюжетом (без проверки доверия).
static var unlocked_stock: Array = []
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
		pocket = d.get("pocket", [])
		trust = int(d.get("trust", 0))
		extractions = int(d.get("extractions", 0))
		floors_open = d.get("floors_open", ["f1"])
		if not "f1" in floors_open:
			floors_open.append("f1")
		floor = String(d.get("floor", "f1"))
		if not floor in floors_open:
			floor = "f1"
		modules = d.get("modules", {})
		for k in modules:
			modules[k] = int(modules[k])
		missions_active = d.get("missions_active", {})
		for k in missions_active:
			missions_active[k] = int(missions_active[k])
		missions_done = d.get("missions_done", [])
		quests = d.get("quests", {})
		flags = d.get("flags", {})
		unlocked_stock = d.get("unlocked_stock", [])
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
	pocket = []
	trust = 0
	extractions = 0
	floors_open = ["f1"]
	floor = "f1"
	modules = {}
	missions_active = {}
	missions_done = []
	quests = {}
	flags = {}
	unlocked_stock = []
	for pair in Balance.START_STASH:
		ItemDb.add_to(stash, ItemDb.make(String(pair[0]), int(pair[1])), stash_grid())


## JSON отдаёт числа как float — количества делаем целыми.
static func _fix_numbers() -> void:
	for list in [stash, backpack, pocket]:
		for it in list:
			it.n = int(it.n)
	for slot in equipment:
		equipment[slot].n = 1


## Тайник, рюкзак и карман — сетки: записи без мест (старый профиль, вернувшиеся патроны)
## раскладываются заново; что не влезло в рюкзак или карман — в тайник, что не влезло в тайник —
## теряется (с предупреждением).
static func _fit_grids() -> void:
	for name in ["backpack", "pocket"]:
		var list := list_of(name)
		if not ItemDb.grid_ok(list, grid_of(name)):
			for e in ItemDb.pack(list, grid_of(name)):
				ItemDb.add_to(stash, e, stash_grid())
	if not ItemDb.grid_ok(stash, stash_grid()):
		var lost := ItemDb.pack(stash, stash_grid())
		if not lost.is_empty():
			push_warning("Profile: тайник переполнен, не поместилось: %s" % str(lost))


static func save() -> void:
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		push_error("Profile: не удалось записать " + path)
		return
	f.store_string(JSON.stringify({"money": money, "stash": stash, "equipment": equipment, "backpack": backpack,
		"pocket": pocket, "trust": trust, "extractions": extractions, "floors_open": floors_open, "floor": floor,
		"modules": modules, "missions_active": missions_active, "missions_done": missions_done,
		"quests": quests, "flags": flags, "unlocked_stock": unlocked_stock}, "  "))


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


## Уровень доверия Михалыча (1–4) по очкам (Balance.TRUST_LEVELS).
static func trust_level() -> int:
	var lv := 0
	for t in Balance.TRUST_LEVELS:
		if trust >= int(t):
			lv += 1
	return maxi(lv, 1)


## Сетка тайника — растёт с модулем «тайник».
static func stash_grid() -> Vector2i:
	var lv := clampi(int(modules.get("stash", 1)), 1, Balance.STASH_ROWS.size())
	return Vector2i(Balance.STASH_GRID.x, int(Balance.STASH_ROWS[lv - 1]))


## Сетка защищённого кармана (ZERO — кармана ещё нет).
static func pocket_grid() -> Vector2i:
	var lv := clampi(int(modules.get("pocket", 0)), 0, Balance.POCKET_GRIDS.size() - 1)
	return Balance.POCKET_GRIDS[lv]


static func list_of(name: String) -> Array:
	match name:
		"backpack":
			return backpack
		"pocket":
			return pocket
	return stash


static func grid_of(name: String) -> Vector2i:
	match name:
		"backpack":
			return Balance.BACKPACK_GRID
		"pocket":
			return pocket_grid()
	return stash_grid()


static func stash_cells() -> int:
	return ItemDb.cells_of(stash)


static func backpack_cells() -> int:
	return ItemDb.cells_of(backpack)


## Сколько штук id в тайнике (все стопки).
static func stash_count(id: String) -> int:
	var c := 0
	for e in stash:
		if String(e.id) == id:
			c += int(e.n)
	return c


## Забрать из тайника n штук id (детали на модули, сдача заданий); сколько забрал.
static func take_from_stash(id: String, n: int) -> int:
	var left := n
	var i := stash.size() - 1
	while i >= 0 and left > 0:
		if String(stash[i].id) == id:
			left -= int(ItemDb.remove_at(stash, i, left).n)
		i -= 1
	save()
	return n - left


# ---------------------------------------------------------------- убежище

## Передвинуть запись внутри сетки name ("stash" / "backpack" / "pocket").
static func move_in(name: String, idx: int, x: int, y: int, r: bool) -> bool:
	var ok := ItemDb.move_in(list_of(name), grid_of(name), idx, x, y, r)
	if ok:
		save()
	return ok


## Перенести запись idx из сетки from в сетку to прямо в место (x, y); false — не влезло.
static func transfer(from: String, idx: int, to: String, x: int, y: int, r: bool) -> bool:
	var src := list_of(from)
	if idx < 0 or idx >= src.size() or grid_of(to) == Vector2i.ZERO:
		return false
	var e: Dictionary = (src[idx] as Dictionary).duplicate(true)
	var k := ItemDb.put_at(list_of(to), e, grid_of(to), x, y, r)
	if k <= 0:
		return false
	ItemDb.remove_at(src, idx, k)
	save()
	return true


## Быстрый перенос (двойной клик / Ctrl): тайник → рюкзак, рюкзак и карман → тайник.
static func quick_move(from: String, idx: int) -> bool:
	var src := list_of(from)
	if idx < 0 or idx >= src.size():
		return false
	var to := "backpack" if from == "stash" else "stash"
	return _move(src, list_of(to), idx, int(src[idx].n), grid_of(to))


## Из тайника в рюкзак (n штук записи idx); false — не влезло.
static func stash_to_backpack(idx: int, n: int) -> bool:
	return _move(stash, backpack, idx, n, Balance.BACKPACK_GRID)


static func backpack_to_stash(idx: int, n: int) -> bool:
	return _move(backpack, stash, idx, n, stash_grid())


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
	return equip_from("stash", idx)


## Надеть предмет из тайника или рюкзака; то, что было в слоте, — туда же (не влезло — в тайник).
static func equip_from(from: String, idx: int) -> bool:
	var src := list_of(from)
	var grid := grid_of(from)
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
			ItemDb.add_to(stash, old, stash_grid())
	equipment[slot] = entry
	save()
	return true


static func unequip(slot: String) -> bool:
	if not equipment.has(slot):
		return false
	var probe: Dictionary = equipment[slot]
	if ItemDb.room_in(stash, probe, stash_grid()) <= 0:
		return false
	ItemDb.add_to(stash, probe, stash_grid())
	equipment.erase(slot)
	save()
	return true


## Снять прямо в место (x, y) тайника или рюкзака (перетащили из слота в сетку).
static func unequip_to(slot: String, to_name: String, x: int, y: int, r: bool) -> bool:
	if not equipment.has(slot) or grid_of(to_name) == Vector2i.ZERO:
		return false
	var to := list_of(to_name)
	var grid := grid_of(to_name)
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
	if mod_block(mod) != "":
		return false
	ItemDb.remove_at(src, idx, 1)
	var mods: Dictionary = weapon.get("mods", {}).duplicate()
	if mods.has(slot):
		ItemDb.add_to(src, ItemDb.make(String(mods[slot]), 1), Balance.BACKPACK_GRID if from_backpack else stash_grid())
	mods[slot] = mod
	weapon["mods"] = mods
	save()
	return true


## Почему обвес нельзя поставить на верстаке этого уровня ("" — можно).
static func mod_block(mod: String) -> String:
	var need := int(Balance.WORKBENCH_SLOT_LEVEL.get(String(ItemDb.mod_spec(mod).get("slot", "")), 1))
	if Upgrades.level("workbench") < need:
		return "нужен верстак %d" % need
	return ""


static func remove_mod(weapon_slot: String, mod_slot: String) -> bool:
	var mods := weapon_mods(weapon_slot).duplicate()
	if not mods.has(mod_slot):
		return false
	var e := ItemDb.make(String(mods[mod_slot]), 1)
	if ItemDb.room_in(stash, e, stash_grid()) <= 0:
		return false
	ItemDb.add_to(stash, e, stash_grid())
	mods.erase(mod_slot)
	(equipment[weapon_slot] as Dictionary)["mods"] = mods
	save()
	return true


# ---------------------------------------------------------------- торговец

static func buy_price(id: String) -> int:
	var mult := Balance.TRADER_BUY_MULT
	if String(ItemDb.item(id).get("cat", "")) == "mod":
		mult *= Balance.TRADER_MOD_BUY_MULT
	return int(ceil(float(ItemDb.value(id)) * mult))


## Нет ни одного огнестрела (надето, рюкзак, карман, тайник) и не на что купить самый дешёвый.
static func needs_rescue() -> bool:
	ensure()
	for list in [stash, backpack, pocket, equipment.values()]:
		for e in list:
			if String(ItemDb.equip(String(e.id)).get("weapon", "")) != "":
				return false
	return money < buy_price(String(Balance.RESCUE_KIT[0][0]))


## Выручка Михалыча: набор из Balance.RESCUE_KIT в тайник. false — не положено или тайник полон.
static func take_rescue() -> bool:
	if not needs_rescue():
		return false
	for pair in Balance.RESCUE_KIT:
		ItemDb.add_to(stash, ItemDb.make(String(pair[0]), int(pair[1])), stash_grid())
	save()
	return true


static func sell_price(entry: Dictionary) -> int:
	return int(floor(float(ItemDb.entry_value(entry)) * Balance.TRADER_SELL_MULT))


static func buy(id: String, n: int) -> bool:
	var cost := buy_price(id) * n
	if cost > money or ItemDb.room_in(stash, ItemDb.make(id, n), stash_grid()) < n:
		return false
	money -= cost
	ItemDb.add_to(stash, ItemDb.make(id, n), stash_grid())
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
	var out := {"equipment": equipment.duplicate(true), "backpack": backpack.duplicate(true),
		"pocket": pocket.duplicate(true), "pocket_grid": pocket_grid()}
	equipment = {}
	backpack = []
	save()
	return out


## Карман после рейда — и после эвакуации, и после смерти (он не теряется).
static func set_pocket(items: Array) -> void:
	ensure()
	pocket = items.duplicate(true)
	_fix_numbers()
	_fit_grids()
	save()


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
