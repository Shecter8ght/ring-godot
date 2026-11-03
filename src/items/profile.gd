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
## Вещи, вынутые в буфер обмена с напарником (Trade): пока обмен не состоялся — здесь; игра закрылась
## посреди обмена — при загрузке возвращаются в тайник.
static var trade_hold: Array = []
## Путь к файлу (тесты подменяют, чтобы не портить настоящий профиль).
static var path: String = PATH

## Имя сохранения (главное меню).
static var profile_name: String = ""
static var money: int = 0
static var stash: Array = []
static var equipment: Dictionary = {}
static var backpack: Array = []
## Доверие торговца (Михалыча): растёт за удачные эвакуации, открывает маршруты на этажи (Floors).
static var trust: int = 0
## Сколько раз выбрался из рейда живым.
static var extractions: int = 0
## Открытые маршруты (id этажей из data/floors.json) и выбранный для следующего рейда.
static var floors_open: Array = ["mall"]
static var floor: String = "mall"
## Модули убежища: id -> уровень (см. Upgrades, data/hideout.json).
static var modules: Dictionary = {}
## Сохранённые каналы досуга; старые профили без ключа остаются совместимыми.
static var hideout_media: Dictionary = {}
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
## Сюжетная кампания этого сохранения (id): в группе все идут по кампании хоста. Чужие кампании,
## в которых участвовал гостем, — отдельно (campaign id -> {quests, flags}): не смешиваются со своей.
static var campaign_id: String = ""
## Постоянный владелец и журнал оружия мира хоста, независимо от временного peer_id.
static var profile_id: String = ""
static var weapon_world: Dictionary = {}
## Шаблоны снаряжения (LoadoutTemplates): что надето и что в рюкзаке — собрать одной кнопкой.
static var loadout_templates: Array = []
static var guest_campaigns: Dictionary = {}
## Контракты терминала (Contracts): доска {board: [{id, tpl, giver, seed, born}], seq, raids} и
## репутация у заказчиков (rep: giver -> очки).
static var contracts: Dictionary = {}
## Хроника рейдов: последние рейды (новее первым) — для повторов и серий (RaidHistory); и фразы,
## что уже звучали, — чтобы не повторяться.
static var raid_history: Array = []
static var story_recent: Array = []
## Условия следующего рейда (RaidConditions), выбранные у лестницы.
static var next_conditions: Dictionary = {"time": "dusk", "weather": "clear", "power": "on"}
static var _loaded: bool = false


## Id своей сюжетной кампании (создаётся при первом обращении и сохраняется).
static func own_campaign() -> String:
	ensure()
	if campaign_id == "":
		campaign_id = "%08x%08x" % [randi(), Time.get_ticks_usec() & 0x7fffffff]
		save()
	return campaign_id


static func ensure() -> void:
	if _loaded:
		return
	_loaded = true
	var text := FileAccess.get_file_as_string(path) if FileAccess.file_exists(path) else ""
	var d: Variant = JSON.parse_string(text) if text != "" else null
	if not d is Dictionary and FileAccess.file_exists(path + ".bak"):
		d = JSON.parse_string(FileAccess.get_file_as_string(path + ".bak"))
	if d is Dictionary:
		money = int(d.get("money", 0))
		profile_name = String(d.get("name", ""))
		stash = d.get("stash", [])
		# пометки поштучных операций (MagOps) — не из сохранения: вышли посреди снаряжения
		for l in [stash, d.get("backpack", []), d.get("pocket", [])]:
			MagOps.clean(l)
		equipment = d.get("equipment", {})
		backpack = d.get("backpack", [])
		pocket = d.get("pocket", [])
		# старые id брони и шлемов (до сведения к трём, 2026-10-24) и прежние псевдонимы — в нынешние
		for l in [stash, backpack, pocket]:
			ItemDb.canon_list(l)
		for slot in equipment:
			if equipment[slot] is Dictionary:
				ItemDb.canon_entry(equipment[slot] as Dictionary)
		_migrate_rigs()
		trust = int(d.get("trust", 0))
		extractions = int(d.get("extractions", 0))
		floors_open = d.get("floors_open", ["mall"])
		if not "mall" in floors_open:
			floors_open.append("mall")
		floor = String(d.get("floor", "mall"))
		# выбранного маршрута больше нет в data/floors.json (так убрали зону 2 и кольцо f1) — территория ТЦ
		if not floor in floors_open or Floors.find(floor).is_empty():
			floor = "mall"
		modules = d.get("modules", {})
		hideout_media = d.get("hideout_media", {})
		for k in modules:
			modules[k] = int(modules[k])
		missions_active = d.get("missions_active", {})
		for k in missions_active:
			missions_active[k] = int(missions_active[k])
		missions_done = d.get("missions_done", [])
		quests = d.get("quests", {})
		flags = d.get("flags", {})
		unlocked_stock = d.get("unlocked_stock", [])
		campaign_id = String(d.get("campaign_id", ""))
		profile_id = String(d.get("profile_id", ""))
		weapon_world = d.get("weapon_world", {})
		if profile_id == "":
			profile_id = WeaponMark.new_id()
		loadout_templates = d.get("loadout_templates", [])
		for t: Variant in loadout_templates:
			if t is Dictionary:
				ItemDb.canon_template(t as Dictionary)
		# обмен оборвался (вылет, выход) — вещи из буфера обмена обратно в тайник
		trade_hold = []
		for held: Variant in d.get("trade_hold", []):
			if held is Dictionary:
				for key in ["x", "y", "r"]:
					(held as Dictionary).erase(key)
				ItemDb.add_to(stash, held, Vector2i.ZERO)
		guest_campaigns = d.get("guest_campaigns", {})
		contracts = d.get("contracts", {})
		raid_history = d.get("raid_history", [])
		# хэши фраз: из JSON приходят дробными, а Array.has сравнивает по типу
		story_recent = (d.get("story_recent", []) as Array).map(func(h: Variant) -> int: return int(h))
		next_conditions = d.get("next_conditions", next_conditions)
		for i in range(unlocked_stock.size()):
			unlocked_stock[i] = WeaponDb.canonical(String(unlocked_stock[i]))
		_migrate()
		# до слота «Рюкзак» у всех был рюкзак на 30 ячеек — выдать его надетым, вещи на местах
		if not flags.get("bp_slot", false):
			flags["bp_slot"] = true
			if not equipment.has("backpack"):
				equipment["backpack"] = ItemDb.make(Balance.BACKPACK_START, 1)
		_fix_numbers()
		_fit_grids()
		save()
	else:
		_starter()
		save()
	grow_unlocked()


## Первый запуск: немного денег и базовый набор в тайнике.
static func _starter() -> void:
	profile_name = ""
	money = Balance.START_MONEY
	stash = []
	equipment = {}
	backpack = []
	pocket = []
	trust = 0
	extractions = 0
	floors_open = ["mall"]
	floor = "mall"
	modules = {}
	hideout_media = {}
	missions_active = {}
	missions_done = []
	quests = {}
	flags = {}
	unlocked_stock = []
	campaign_id = ""
	profile_id = WeaponMark.new_id()
	weapon_world = {}
	guest_campaigns = {}
	contracts = {}
	loadout_templates = []
	raid_history = []
	story_recent = []
	for e in start_kit():
		ItemDb.add_to(stash, e, stash_grid())
	equipment["backpack"] = ItemDb.make(Balance.BACKPACK_START, 1)
	flags["bp_slot"] = true


## Стартовый набор записями (Balance.START_STASH; у ствола — обвес по точкам). without — [id, штук], что
## из него вычесть (пролог: это игрок несёт с собой, остальное — в закладке).
static func start_kit(without: Array = []) -> Array:
	var less: Dictionary = {}
	for pair in without:
		less[String(pair[0])] = int(less.get(String(pair[0]), 0)) + int(pair[1])
	var out: Array = []
	for pair: Array in Balance.START_STASH:
		var n := int(pair[1]) - int(less.get(String(pair[0]), 0))
		if n <= 0:
			continue
		var e: Dictionary = ItemDb.make(String(pair[0]), n)
		if pair.size() > 2 and e.has("mods"):
			for mount: String in (pair[2] as Dictionary):
				e.mods[mount] = {"id": String(pair[2][mount]), "dur": float(Balance.CONDITION.full)}
		out.append(e)
	return out


## Новая игра с прологом (docs/design/prologue.md §2, §7): тайник пуст — набор ждёт в закладке у кордона;
## с собой — рюкзак и немного медицины (Balance.PROLOGUE.carry).
static func prologue_start() -> void:
	ensure()
	stash = []
	backpack = []
	for pair in Balance.PROLOGUE.carry:
		ItemDb.add_to(backpack, ItemDb.make(String(pair[0]), int(pair[1])), grid_of("backpack"))
	flags["prologue"] = true


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


static func save() -> bool:
	# Сначала полный временный файл. Ошибка записи не списывает ресурс гравировки.
	var f := FileAccess.open(path + ".tmp", FileAccess.WRITE)
	if f == null:
		push_error("Profile: не удалось записать " + path)
		return false
	f.store_string(JSON.stringify({"name": profile_name, "money": money, "stash": stash, "equipment": equipment, "backpack": backpack,
		"pocket": pocket, "trust": trust, "extractions": extractions, "floors_open": floors_open, "floor": floor,
		"modules": modules, "hideout_media": hideout_media, "missions_active": missions_active, "missions_done": missions_done,
		"quests": quests, "flags": flags, "unlocked_stock": unlocked_stock, "campaign_id": campaign_id, "profile_id": profile_id, "weapon_world": weapon_world, "guest_campaigns": guest_campaigns, "contracts": contracts, "loadout_templates": loadout_templates, "next_conditions": next_conditions,
		"raid_history": raid_history, "story_recent": story_recent, "trade_hold": trade_hold}, "  "))
	f.flush()
	var error: Error = f.get_error()
	f.close()
	if error != OK:
		return false
	var absolute: String = ProjectSettings.globalize_path(path)
	if FileAccess.file_exists(path):
		if DirAccess.copy_absolute(absolute, absolute + ".bak") != OK:
			return false
	return DirAccess.rename_absolute(absolute + ".tmp", absolute) == OK


## Тесты: свой файл и чистый старт.
static func use_file(p: String, fresh: bool) -> void:
	path = p
	_loaded = false
	if fresh:
		for suffix: String in ["", ".bak", ".tmp"]:
			if FileAccess.file_exists(p + suffix):
				DirAccess.remove_absolute(ProjectSettings.globalize_path(p + suffix))
	ensure()


## Оружие в руках для вида в убежище: основное, иначе пистолет, иначе "".
static func equipped_weapon() -> String:
	return String(equipped_entry().get("id", ""))


## Оружие в снаряжении (основное, иначе пистолет) — запись; {} — нет.
static func equipped_entry() -> Dictionary:
	ensure()
	for slot in ItemDb.WEAPON_SLOTS:
		if equipment.has(slot) and WeaponDb.is_weapon(String(equipment[slot].id)):
			return equipment[slot]
	return {}


## Перед рейдом: чего из основного нет с собой — оружия, патронов к нему (россыпью, в магазинах,
## в самом оружии), магазина (у оружия со съёмным), медицины. С собой — надетое, рюкзак и карман.
## Строки для предупреждения; пусто — всё есть.
static func raid_kit_gaps() -> Array[String]:
	ensure()
	var out: Array[String] = []
	var carried: Array = backpack + pocket
	var weapons: Array = []
	for slot in ["primary", "secondary", "sidearm"]:
		var e: Dictionary = equipment.get(slot, {})
		if WeaponDb.is_weapon(String(e.get("id", ""))):
			weapons.append(e)
	if weapons.is_empty():
		out.append("оружие — надень его в тайнике")
	for e in weapons:
		var wid := String(e.id)
		var w := WeaponDb.weapon(wid)
		var name := ItemDb.item_name(wid)
		var mag: Dictionary = e.get("mag", {}) if e.get("mag") is Dictionary else {}
		var rounds := int(mag.get("rounds", 0))
		var mags := 1 if String(mag.get("id", "")) != "" else 0
		for it in carried:
			var iid := String(it.id)
			if (it as Dictionary).has("rounds"):
				if WeaponDb.mag_fits(wid, iid):
					mags += 1
					rounds += int(it.rounds)
			elif not WeaponDb.ammo(iid).is_empty() and WeaponDb.ammo_fits(wid, iid):
				rounds += int(it.n)
		if rounds <= 0:
			out.append("патроны к «%s» (%s)" % [name, WeaponDb.caliber_name(String(w.get("caliber", "")))])
		if not w.has("internal_mag") and mags == 0:
			out.append("магазин к «%s»" % name)
	var med := false
	for it in carried:
		if String(ItemDb.item(String(it.id)).get("cat", "")) == "med":
			med = true
	if not med:
		out.append("медицина — бинт или аптечка")
	return out


## Ступень доверия Михалыча: очки + 1, до Balance.TRUST_STEPS.max.
static func trust_step() -> int:
	if Settings.unlocked():
		return int(Balance.TRUST_STEPS.max)
	return clampi(trust + 1, 1, int(Balance.TRUST_STEPS.max))


## Уровень доверия = сколько каталогов открыто (1–5): каталог n — со ступени TraderStock.step_of(n).
## Им же проверяются задания, модули убежища и сюжет.
static func trust_level() -> int:
	var lv := 1
	for c in TraderStock.catalogs():
		if trust_step() >= int(c.step):
			lv = maxi(lv, int(c.n))
	return lv


## Чит «открыть всё» (Settings.unlocked): тайник и карман вырастают до предела в самом сохранении
## и остаются такими после выключения — в добавленных рядах лежат вещи, отнять ряды значит их
## потерять. Остальные модули чит открывает на лету (Upgrades.level), сохранение их не помнит.
static func grow_unlocked() -> void:
	if not _loaded or not Settings.unlocked():
		return
	var grown := false
	for id: String in ["stash", "pocket"]:
		var top := Upgrades.max_level(id)
		if int(modules.get(id, 0)) < top:
			modules[id] = top
			grown = true
	if grown:
		save()


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
		"rig", "dump":
			# подсумки и сумка сброса надетой разгрузки — внутри её записи
			return ItemDb.rig_list(equipment, name)
	return stash


static func grid_of(name: String) -> Vector2i:
	match name:
		"backpack":
			return ItemDb.bag_grid(equipment)
		"pocket":
			return pocket_grid()
		"rig", "dump":
			return ItemDb.rig_grid(equipment, name)
	return stash_grid()


static func stash_cells() -> int:
	return ItemDb.cells_of(stash)


static func backpack_cells() -> int:
	return ItemDb.cells_of(backpack)


## Ячеек в рюкзаке (без рюкзака — в карманах).
static func backpack_capacity() -> int:
	var g := grid_of("backpack")
	return g.x * g.y


## Сколько штук id в тайнике (все стопки).
## Сколько id в тайнике; fir_only — только найденного в рейде (задания Михалыча).
static func stash_count(id: String, fir_only: bool = false) -> int:
	var c := 0
	for e in stash:
		if String(e.id) == id and (not fir_only or bool(e.get("fir", false))):
			c += int(e.n)
	return c


## Забрать из тайника n штук id (детали на модули, сдача заданий); сколько забрал.
static func take_from_stash(id: String, n: int, fir_only: bool = false) -> int:
	var left := n
	var i := stash.size() - 1
	while i >= 0 and left > 0:
		if String(stash[i].id) == id and (not fir_only or bool(stash[i].get("fir", false))):
			left -= int(ItemDb.remove_at(stash, i, left).n)
		i -= 1
	save()
	return n - left


# ---------------------------------------------------------------- убежище

## Разложить сетку name по порядку (крупное в начало, стопки добраны). false — не вышло.
static func sort_grid(name: String) -> bool:
	var out := ItemDb.arranged(list_of(name), grid_of(name))
	if out.is_empty() and not list_of(name).is_empty():
		return false
	var list := list_of(name)
	list.clear()
	list.append_array(out)
	save()
	return true


## Передвинуть запись внутри сетки name ("stash" / "backpack" / "pocket").
static func move_in(name: String, idx: int, x: int, y: int, r: bool) -> bool:
	if name == "rig" and idx >= 0 and idx < list_of(name).size() and not ItemDb.rig_accepts_at(equipment, list_of(name)[idx], x, y, r):
		return false
	var ok := ItemDb.move_in(list_of(name), grid_of(name), idx, x, y, r)
	if ok:
		save()
	return ok


## Перенести запись idx из сетки from в сетку to прямо в место (x, y); false — не влезло.
static func transfer(from: String, idx: int, to: String, x: int, y: int, r: bool) -> bool:
	var src := list_of(from)
	if idx < 0 or idx >= src.size() or grid_of(to) == Vector2i.ZERO or not ItemDb.grid_accepts(to, src[idx]):
		return false
	if to == "rig" and not ItemDb.rig_accepts_at(equipment, src[idx], x, y, r):
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
	if from in ["rig", "dump"]:
		# из разгрузки — в рюкзак, нет места — в тайник
		return _move(src, backpack, idx, 1, grid_of("backpack")) or _move(src, stash, idx, 1, stash_grid())
	return _move(src, list_of(to), idx, int(src[idx].n), grid_of(to))


## Из тайника в рюкзак (n штук записи idx); false — не влезло.
static func stash_to_backpack(idx: int, n: int) -> bool:
	return _move(stash, backpack, idx, n, ItemDb.bag_grid(equipment))


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


## Разгрузки (rig_*) из старых сохранений — в подсумки (gear_v2, 2026-10-24): надетая — автоматные подсумки на
## надетую броню, сколько влезет, и её магазины в них; остальное и разгрузки из сеток — подсумками, магазинами
## и сбросом в тайник.
static func _migrate_rigs() -> void:
	var loose: Array = []
	if equipment.has("rig"):
		var rig: Dictionary = equipment.rig if equipment.rig is Dictionary else {}
		equipment.erase("rig")
		var n := int((ItemDb.item(String(rig.get("id", ""))).get("rig", {}) as Dictionary).get("pouches", 0))
		var armor: Dictionary = equipment.get("armor", {})
		for i in range(n):
			if armor.is_empty() or not ItemDb.attach_pouch(armor, "pouch_rifle"):
				loose.append(ItemDb.make("pouch_rifle", 1))
		for part: String in ["mags", "dump"]:
			for inner: Variant in rig.get(part, []):
				if not inner is Dictionary:
					continue
				var m := (inner as Dictionary).duplicate(true)
				for key in ["x", "y", "r"]:
					m.erase(key)
				var put := ItemDb.add_to_rig(equipment, m) if part == "mags" else ItemDb.add_to(ItemDb.rig_list(equipment, part), m, ItemDb.rig_grid(equipment, part))
				if armor.is_empty() or put == 0:
					loose.append(m)
	for l: Array in [stash, backpack, pocket]:
		var i := 0
		while i < l.size():
			var e: Dictionary = l[i]
			if ItemDb.item(String(e.get("id", ""))).has("rig"):
				var n := int((ItemDb.item(String(e.id)).get("rig", {}) as Dictionary).get("pouches", 0))
				for k in range(n):
					loose.append(ItemDb.make("pouch_rifle", 1))
				loose.append_array(ItemDb.detach_pouches(e))
				l.remove_at(i)
				continue
			i += 1
	for e: Dictionary in loose:
		if ItemDb.add_to(stash, e, stash_grid()) == 0:
			ItemDb.add_to(stash, e, Vector2i.ZERO)


## Надеть предмет из тайника или рюкзака; то, что было в слоте, — туда же (не влезло — в тайник).
static func equip_from(from: String, idx: int, want: String = "") -> bool:
	var src := list_of(from)
	var grid := grid_of(from)
	if idx < 0 or idx >= src.size():
		return false
	var id := String(src[idx].id)
	# подсумок — на надетую броню или пояс (пока есть места), своего слота у него нет
	if ItemDb.pouch_cost(id) > 0.0:
		var at := int(want.trim_prefix("pouch:")) if want.begins_with("pouch:") else -1
		if not equipment.has("armor") or not ItemDb.attach_pouch(equipment.armor as Dictionary, id, at):
			return false
		ItemDb.remove_at(src, idx, 1)
		save()
		return true
	var slot := ItemDb.pick_slot(id, equipment, want)
	if slot == "":
		return false
	var entry := ItemDb.remove_at(src, idx, 1)
	for key in ["x", "y", "r"]:
		entry.erase(key)
	if not entry.has("dur") and ItemDb.equip(id).has("durability"):
		entry.dur = float(ItemDb.equip(id).durability)
	var old: Dictionary = equipment.get(slot, {})
	equipment[slot] = entry
	if slot == "backpack":
		_refit_backpack()
		grid = grid_of(from)
	if not old.is_empty() and ItemDb.add_to(src, old, grid) == 0:
		ItemDb.add_to(stash, old, stash_grid())
	save()
	return true


## Сменили рюкзак (или сняли): вещи — в его сетку (без рюкзака — по карманам), что не влезло — в тайник.
static func _refit_backpack() -> void:
	var r := ItemDb.refit(backpack, grid_of("backpack"))
	backpack = r[0]
	for e in r[1]:
		ItemDb.add_to(stash, e, stash_grid())


## Выбросить насовсем: запись idx списка (тайник, рюкзак, карман) или из слота ("equip:<слот>").
static func discard(where: String, idx: int) -> bool:
	if where.begins_with("equip:"):
		if not equipment.erase(where.trim_prefix("equip:")):
			return false
		if where == "equip:backpack":
			_refit_backpack()
	else:
		var list := list_of(where)
		if idx < 0 or idx >= list.size():
			return false
		list.remove_at(idx)
	save()
	return true


static func unequip(slot: String) -> bool:
	if slot.begins_with("pouch:"):
		return _pouch_off(int(slot.trim_prefix("pouch:")), "stash", -1, -1, false)
	if not equipment.has(slot):
		return false
	var probe: Dictionary = equipment[slot]
	if ItemDb.room_in(stash, probe, stash_grid()) <= 0:
		return false
	ItemDb.add_to(stash, probe, stash_grid())
	equipment.erase(slot)
	if slot == "backpack":
		_refit_backpack()
	save()
	return true


## Снять прямо в место (x, y) тайника или рюкзака (перетащили из слота в сетку).
static func unequip_to(slot: String, to_name: String, x: int, y: int, r: bool) -> bool:
	if slot.begins_with("pouch:"):
		return _pouch_off(int(slot.trim_prefix("pouch:")), to_name, x, y, r)
	if not equipment.has(slot) or grid_of(to_name) == Vector2i.ZERO or not ItemDb.grid_accepts(to_name, equipment[slot]):
		return false
	# рюкзак сам в себя не кладётся
	if slot == "backpack" and to_name == "backpack":
		return false
	var to := list_of(to_name)
	var grid := grid_of(to_name)
	if ItemDb.put_at(to, equipment[slot], grid, x, y, r) <= 0:
		return false
	equipment.erase(slot)
	if slot == "backpack":
		_refit_backpack()
	save()
	return true


# ---------------------------------------------------------------- верстак

## Ремонт тела оружия или конкретного обвеса; деньги и изменение сохраняются вместе.
static func repair_part(where: String, idx: int, mount: String = "") -> bool:
	ensure()
	var entry: Dictionary = _entry_at(where, idx).duplicate(true)
	if entry.is_empty():
		return false
	var part: Dictionary = entry
	if mount != "":
		var mods: Dictionary = entry.get("mods", {})
		if not mods.has(mount):
			return false
		part = WeaponCondition.mod_entry(mods[mount])
	var cost: int = WeaponCondition.repair_price(part)
	if cost <= 0 or money < cost:
		return false
	part["dur"] = float(Balance.CONDITION.full)
	if mount != "":
		(entry.mods as Dictionary)[mount] = part
	else:
		entry = part
	entry["rev"] = int(entry.get("rev", 0)) + 1
	_set_entry(where, idx, entry)
	money -= cost
	save()
	return true

## Обвес на оружии в слоте снаряжения (primary/secondary): точка → {id, …}.
static func weapon_mods(weapon_slot: String) -> Dictionary:
	if not equipment.has(weapon_slot):
		return {}
	return (equipment[weapon_slot] as Dictionary).get("mods", {})


## Поставить обвес (запись idx тайника или рюкзака) на надетое оружие в точку mount ("" — первая
## подходящая); снятый оттуда ложится туда, откуда взят новый.
static func install_mod(weapon_slot: String, idx: int, from_backpack: bool = false, mount: String = "") -> bool:
	var src: Array = backpack if from_backpack else stash
	if not equipment.has(weapon_slot) or idx < 0 or idx >= src.size():
		return false
	var mod := String(src[idx].id)
	var target := mount
	if target == "":
		target = WeaponDb.free_mount_for(equipment[weapon_slot], mod)
		if target == "":
			var all := WeaponDb.mounts_for(equipment[weapon_slot], mod)
			target = String(all[0]) if not all.is_empty() else ""
	if target == "" or mod_block(mod, target) != "":
		return false
	return fit_part("equip:" + weapon_slot, -1, "backpack" if from_backpack else "stash", idx, target)


## Почему обвес нельзя поставить на верстаке этого уровня в точку mount ("" — можно).
static func mod_block(_mod: String, mount: String = "") -> String:
	var need := int(Balance.WORKBENCH_SLOT_LEVEL.get(WeaponBuild.top_mount(mount), 1))
	if Upgrades.level("workbench") < need:
		return "нужен верстак %d" % need
	return ""


## Сборка из конструктора (BuildPlan — черновик с пометкой, откуда каждая деталь): взять детали из
## тайника и рюкзака, купить недостающее у Михалыча, снятое — в тайник. Всё или ничего; точки,
## которым нужен верстак выше, — по Balance.WORKBENCH_SLOT_LEVEL. "" — готово, иначе причина.
static func apply_build(where: String, idx: int, draft: Dictionary, draft_mag: Dictionary = {}) -> String:
	ensure()
	var weapon := _entry_at(where, idx)
	if weapon.is_empty():
		return "оружия нет"
	var r: Dictionary = BuildPlan.resolve(weapon, draft, draft_mag, {"stash": stash, "backpack": backpack},
		{"shop": true, "lists": BuildPlan.HIDEOUT_LISTS})
	if String(r.why) != "":
		return String(r.why)
	for mount: Variant in WeaponDb.mounts_of(String(weapon.id)):
		if BuildPlan._branch(weapon.get("mods", {}), String(mount)) != BuildPlan._branch((r.entry as Dictionary).mods, String(mount)):
			var why := mod_block("", String(mount))
			if why != "":
				return "%s: %s" % [String(WeaponDb.MOUNT_NAMES.get(String(mount), mount)), why]
	var cost: int = BuildPlan.cost(r.buy)
	if cost > money:
		return "не хватает денег"
	var lists: Dictionary = {"stash": stash.duplicate(true), "backpack": backpack.duplicate(true)}
	# взятое — по убыванию индекса (индексы впереди не сдвигаются); оружие в том же списке — сдвинется
	var by_list: Dictionary = {}
	for t: Variant in r.take:
		var taken: Array = by_list.get(String(t[0]), [])
		taken.append(int(t[1]))
		by_list[String(t[0])] = taken
	var target := idx
	for list_name: Variant in by_list:
		var taken2: Array = by_list[list_name]
		taken2.sort()
		taken2.reverse()
		for i: Variant in taken2:
			ItemDb.remove_at(lists[list_name], int(i), 1)
			if String(list_name) == where and int(i) < idx:
				target -= 1
	for item: Variant in r.returned:
		var got: Dictionary = item
		if ItemDb.add_to(lists.stash, got, stash_grid()) < int(got.get("n", 1)):
			return "в тайнике нет места для снятого"
	stash.clear()
	stash.append_array(lists.stash)
	backpack.clear()
	backpack.append_array(lists.backpack)
	money -= cost
	_set_entry(where, target, r.entry)
	_refit_backpack()
	save()
	return ""


static func remove_mod(weapon_slot: String, mount: String) -> bool:
	return strip_part("equip:" + weapon_slot, -1, "mod:" + mount)


## Запись по месту: "equip:<слот>" или список ("stash" / "backpack" / "pocket") и индекс.
static func _entry_at(where: String, idx: int) -> Dictionary:
	if where.begins_with("equip:"):
		return equipment.get(where.trim_prefix("equip:"), {})
	var list := list_of(where)
	return list[idx] if idx >= 0 and idx < list.size() else {}


static func _set_entry(where: String, idx: int, e: Dictionary) -> void:
	if where.begins_with("equip:"):
		equipment[where.trim_prefix("equip:")] = e
		return
	var list := list_of(where)
	var old: Dictionary = list[idx]
	for k in ["x", "y", "r"]:
		if old.has(k):
			e[k] = old[k]
	list[idx] = e


## Снять подсумок с полуслота at надетой брони в сетку to (x < 0 — куда влезет); магазины, которым не
## осталось подсумка своего вида, — в рюкзак, не влезло — в тайник.
static func _pouch_off(at: int, to: String, x: int, y: int, r: bool) -> bool:
	var armor: Dictionary = equipment.get("armor", {})
	var i := ItemDb.pouch_index_at(armor, at)
	if i < 0 or not to in ["stash", "backpack"]:
		return false
	var pid := String((ItemDb.pouch_list(armor)[i] as Dictionary).id)
	var probe := ItemDb.make(pid, 1)
	var fits := false
	if x >= 0:
		fits = ItemDb.put_at(list_of(to).duplicate(true), probe, grid_of(to), x, y, r) > 0
	else:
		fits = ItemDb.room_in(list_of(to), probe, grid_of(to)) > 0
	if not fits:
		return false
	var out := ItemDb.detach_pouch(equipment, i)
	var pouch: Dictionary = out.pop_front()
	if x >= 0:
		ItemDb.put_at(list_of(to), pouch, grid_of(to), x, y, r)
	else:
		ItemDb.add_to(list_of(to), pouch, grid_of(to))
	for m: Dictionary in out:
		if ItemDb.add_to(backpack, m, grid_of("backpack")) == 0 and ItemDb.add_to(stash, m, stash_grid()) == 0:
			ItemDb.add_to(stash, m, Vector2i.ZERO)
	save()
	return true


## Переставить подсумок на броне с полуслота from_at на to_at.
static func move_pouch(from_at: int, to_at: int) -> bool:
	if not equipment.has("armor"):
		return false
	var res := ItemDb.move_pouch(equipment, from_at, to_at)
	if not bool(res[0]):
		return false
	for m: Dictionary in res[1]:
		if ItemDb.add_to(backpack, m, grid_of("backpack")) == 0 and ItemDb.add_to(stash, m, stash_grid()) == 0:
			ItemDb.add_to(stash, m, Vector2i.ZERO)
	save()
	return true


## Снять часть с предмета (обвес "mod:<точка>", плиту "plate:<сторона>", магазин "mag"): с надетого
## и из рюкзака — в рюкзак (не влезло — в тайник), из тайника — в тайник.
## Снять с брони все подсумки (и магазины в них): из тайника — в тайник, иначе в рюкзак, не влезло — в тайник.
static func strip_pouches(where: String, idx: int) -> bool:
	var e := _entry_at(where, idx)
	if e.is_empty() or ItemDb.pouch_list(e).is_empty():
		return false
	var to_stash := where == "stash"
	for part: Dictionary in ItemDb.detach_pouches(e):
		if to_stash or ItemDb.add_to(backpack, part, grid_of("backpack")) == 0:
			if ItemDb.add_to(stash, part, stash_grid()) == 0:
				ItemDb.add_to(stash, part, Vector2i.ZERO)
	save()
	return true


static func strip_part(where: String, idx: int, part: String) -> bool:
	var e := _entry_at(where, idx)
	if e.is_empty():
		return false
	var r := Gear.strip(e, part)
	var got: Dictionary = r[1]
	if got.is_empty():
		return false
	var to := "stash"
	if where != "stash" and ItemDb.room_in(backpack, got, grid_of("backpack")) >= int(got.n):
		to = "backpack"
	if ItemDb.room_in(list_of(to), got, grid_of(to)) < int(got.n):
		return false
	_set_entry(where, idx, r[0])
	ItemDb.add_to(list_of(to), got, grid_of(to))
	save()
	return true


## Поставить предмет из списка src (запись src_idx) в предмет where/idx (обвес, плиту, магазин);
## вытесненное — туда же, откуда взят новый.
static func fit_part(where: String, idx: int, src: String, src_idx: int, hint: String = "") -> bool:
	var e := _entry_at(where, idx)
	var from := list_of(src)
	if e.is_empty() or src_idx < 0 or src_idx >= from.size() or (where == src and idx == src_idx):
		return false
	var r := Gear.fit(e, from[src_idx], hint)
	if String(r[2]) != "":
		return false
	var probe := from.duplicate(true)
	ItemDb.remove_at(probe, src_idx, 1)
	if not (r[1] as Dictionary).is_empty() and ItemDb.add_to(probe, r[1], grid_of(src)) == 0:
		return false
	# цель в том же списке, что источник, — её индекс мог сдвинуться
	var ti := idx
	if where == src and src_idx < idx and int(from[src_idx].n) <= 1:
		ti -= 1
	from.clear()
	from.append_array(probe)
	_set_entry(where, ti, r[0])
	save()
	return true


## Проверили магазин (тайник / рюкзак / карман, запись idx): сетка запомнит, сколько было, —
## пока столько же, видна оценка (Gear.mag_state).
static func check_mag(name: String, idx: int) -> void:
	var list := list_of(name)
	if idx < 0 or idx >= list.size() or not (list[idx] as Dictionary).has("rounds"):
		return
	list[idx]["checked"] = int(list[idx].rounds)
	save()


## Старые сохранения (до арсенала): id по алиасам, обвес по точкам, магазины, прочность. Что не
## встало — в тайник.
static func _migrate() -> void:
	Prologue.repair_saved_completion(quests, flags)
	var spill: Array = []
	for list in [stash, backpack, pocket]:
		for i in range(list.size()):
			var r := WeaponDb.migrate(list[i])
			list[i] = r[0]
			WeaponMark.identify(list[i])
			if String(list[i].get("id", "")) == "laser_head":
				list[i]["uid"] = list[i].get("uid", WeaponMark.new_id())
				list[i]["charges"] = int(list[i].get("charges", Balance.ENGRAVING.charges))
			spill.append_array(r[1])
	for slot in equipment.keys():
		var r := WeaponDb.migrate(equipment[slot])
		equipment[slot] = r[0]
		WeaponMark.identify(equipment[slot])
		spill.append_array(r[1])
	# слоты оружия 2026-10-19: пистолет и ракетница из «Оружие 1 / 2» — в свои слоты (и в шаблонах снаряжения)
	ItemDb.remap_weapon_slots(equipment)
	for t: Variant in loadout_templates:
		if t is Dictionary and (t as Dictionary).get("slots") is Dictionary:
			ItemDb.remap_weapon_slots((t as Dictionary).slots)
	# старая броня в слоте — может не встать своим слотом (плитоносец надевается в armor)
	for e in spill:
		ItemDb.add_to(stash, e, stash_grid())


# ---------------------------------------------------------------- торговец

## Покупка — явная цена за преимущество; оценка находки и ремонт от неё не зависят.
static func buy_price(id: String) -> int:
	return int(Balance.TRADER_BUY_PRICES.get(WeaponDb.canonical(id), 0))


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
	return maxi(0, floori(float(ItemDb.entry_value(entry)) * Balance.TRADER_SELL_MULT + _sale_adjustment(entry)))


## Общая выручка списка для окна убежища; рейдовая ценность ItemDb остаётся отдельной оценкой.
static func sell_value_of(items: Array) -> int:
	var total: int = 0
	for entry: Dictionary in items:
		total += sell_price(entry)
	return total


## Дешёвые магазины и медицина переоценены и внутри сборки. Исходную оценку ItemDb оставляем
## для ремонта и рейдовой аналитики; поправка продажи обходит всё содержимое экземпляра.
static func _sale_adjustment(entry: Dictionary) -> float:
	var id: String = WeaponDb.canonical(String(entry.get("id", "")))
	var delta: float = _sale_unit_adjustment(id) * int(entry.get("n", 1))
	var mx: float = ItemDb.max_dur(id)
	if entry.has("dur") and mx > 0.0:
		delta *= clampf(float(entry.dur) / mx, 0.2, 1.0)
	for slot: String in entry.get("mods", {}):
		delta += _sale_adjustment(WeaponCondition.mod_entry(entry.mods[slot]))
	var mag: Dictionary = entry.get("mag", {}) if entry.get("mag") is Dictionary else {}
	if not mag.is_empty():
		delta += _sale_adjustment(Gear.mag_item(mag))
	if entry.has("rounds"):
		for layer: Variant in Gear.mag_layers(entry):
			delta += _sale_unit_adjustment(String(layer[0])) * int(layer[1])
	if int(entry.get("chamber", 0)) > 0:
		delta += _sale_unit_adjustment(String(entry.get("chamber_ammo", mag.get("ammo", "")))) * int(entry.chamber)
	for side: String in entry.get("plates", {}):
		delta += _sale_adjustment(entry.plates[side])
	for part: String in ["mags", "dump"]:
		for inner: Variant in entry.get(part, []):
			delta += _sale_adjustment(inner)
	return delta


static func _sale_unit_adjustment(id: String) -> float:
	var canonical: String = WeaponDb.canonical(id)
	if not Balance.TRADER_SELL_PRICES.has(canonical):
		return 0.0
	return float(Balance.TRADER_SELL_PRICES[canonical]) - ItemDb.value(canonical) * Balance.TRADER_SELL_MULT


## Купить: надеть в свободные совместимые слоты; остальное — в выбранную сетку.
## Если вся оставшаяся покупка не помещается в рюкзак, она целиком уходит в тайник.
## wear=false используется сборщиком шаблонов: он сам распределяет купленные вещи.
static func buy(id: String, n: int, to: String = "stash", wear: bool = true) -> bool:
	ensure()
	id = WeaponDb.canonical(id)
	if ItemDb.loot_only(id) and not Settings.shop_loot:
		return false
	var unit: int = buy_price(id)
	if unit <= 0 or n <= 0 or unit * n > money:
		return false
	var cost: int = unit * n
	# Сначала проверяем покупку на копиях: отказ не меняет ни деньги, ни экипировку.
	var next_equipment: Dictionary = equipment.duplicate(true)
	var remaining: Array[Dictionary] = []
	var left: int = n
	while left > 0:
		var bought: Dictionary = ItemDb.make(id, left if ItemDb.stack(id) > 1 else 1)
		var count: int = int(bought.n)
		if WeaponDb.is_weapon(id) and bought.get("mag") is Dictionary:
			(bought.mag as Dictionary)["rounds"] = WeaponDb.capacity(bought)
		if wear and _buy_wear(bought, next_equipment):
			bought.n = count - 1
		if int(bought.n) > 0:
			remaining.append(bought)
		left -= count
	var destination: String = to
	var dst: Array = list_of(destination).duplicate(true)
	var grid: Vector2i = ItemDb.bag_grid(next_equipment) if destination == "backpack" else grid_of(destination)
	var fits: bool = _buy_place(dst, remaining, grid)
	if not fits and destination == "backpack":
		destination = "stash"
		dst = stash.duplicate(true)
		fits = _buy_place(dst, remaining, stash_grid())
	if not fits:
		return false
	var new_backpack: bool = next_equipment.get("backpack") != equipment.get("backpack")
	equipment = next_equipment
	var actual_dst: Array = list_of(destination)
	actual_dst.clear()
	actual_dst.append_array(dst)
	if new_backpack:
		_refit_backpack()
	money -= cost
	save()
	Audio.play_ui("cash")
	return true


## Купленная вещь надевается без замены занятого слота; подсумок — на свободное место брони.
static func _buy_wear(entry: Dictionary, eq: Dictionary) -> bool:
	var id: String = String(entry.id)
	if ItemDb.pouch_cost(id) > 0.0 and eq.get("armor") is Dictionary and not (eq.armor as Dictionary).is_empty():
		return ItemDb.attach_pouch(eq.armor as Dictionary, id)
	var slot: String = ItemDb.pick_slot(id, eq)
	if slot == "" or (eq.get(slot) is Dictionary and not (eq[slot] as Dictionary).is_empty()):
		return false
	var worn: Dictionary = entry.duplicate(true)
	worn.n = 1
	if not worn.has("dur") and ItemDb.equip(id).has("durability"):
		worn.dur = float(ItemDb.equip(id).durability)
	for key: String in ["x", "y", "r"]:
		worn.erase(key)
	eq[slot] = worn
	return true


## Проверка всей оставшейся покупки в копии сетки; частичный результат при отказе отбрасывается.
static func _buy_place(dst: Array, items: Array[Dictionary], grid: Vector2i) -> bool:
	for entry: Dictionary in items:
		if ItemDb.add_to(dst, entry, grid) < int(entry.n):
			return false
	return true


## Продать n штук записи idx из тайника, рюкзака или кармана (from — "stash" / "backpack" / "pocket").
static func sell(idx: int, n: int, from: String = "stash") -> bool:
	var list := list_of(from)
	if idx < 0 or idx >= list.size():
		return false
	var out := ItemDb.remove_at(list, idx, n)
	if out.is_empty():
		return false
	money += sell_price(out)
	save()
	Audio.play_ui("cash")
	return true


## Продать несколько записей разом (вкладка «Продать»): picks — [[откуда, индекс], …]. Один звук,
## одно сохранение. Возвращает выручку.
static func sell_many(picks: Array) -> int:
	var by: Dictionary = {}
	for p: Variant in picks:
		var from: String = String((p as Array)[0])
		if not by.has(from):
			by[from] = []
		(by[from] as Array).append(int((p as Array)[1]))
	var total: int = 0
	for from: Variant in by:
		var list := list_of(String(from))
		# с конца списка: продажа записи сдвигает индексы тех, что после неё
		var order: Array = by[from]
		order.sort()
		order.reverse()
		var last: int = -1
		for i: int in order:
			if i == last or i < 0 or i >= list.size():
				continue
			last = i
			var out := ItemDb.remove_at(list, i, int(list[i].n))
			if not out.is_empty():
				total += sell_price(out)
	if total > 0:
		money += total
		save()
		Audio.play_ui("cash")
	return total


static func unpack(from: String, idx: int, expected_id: String) -> bool:
	var result: Array = ItemDb.unpack(list_of(from), grid_of(from), idx, expected_id)
	if result.is_empty():
		return false
	match from:
		"backpack":
			backpack = result
		"pocket":
			pocket = result
		_:
			stash = result
	return save()


# ---------------------------------------------------------------- рейд

## Вход в рейд: снаряжение и рюкзак уходят с профиля (на кону), возвращаются при эвакуации.
static func take_loadout() -> Dictionary:
	ensure()
	var out := {"equipment": equipment.duplicate(true), "backpack": backpack.duplicate(true),
		"pocket": pocket.duplicate(true), "pocket_grid": pocket_grid(), "profile_id": profile_id}
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
	# наклейка «Счёт» на вынесенном в руках стволе — зарубка за эвакуацию
	for slot: String in ItemDb.WEAPON_SLOTS:
		if equipment.get(slot) is Dictionary:
			Stickers.tally_extract(equipment[slot])
	_fix_numbers()
	_fit_grids()
	save()
