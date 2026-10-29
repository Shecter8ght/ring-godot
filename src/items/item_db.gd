@tool
class_name ItemDb
extends RefCounted
## Справочник предметов (data/items.json) и лута (data/loot.json). Читается один раз.
## Предмет в инвентаре/контейнере — словарь {"id": String, "n": int}.
##
## Ячеистые хранилища (рюкзак, тайник) — сетка Ш×В (grid: Vector2i). Предмет занимает прямоугольник
## size (items.json → "size" [ш, в]), запись в сетке — одна стопка (не больше stack) с позицией
## "x","y" (левый верхний угол) и "r" (повёрнут на 90°). Списки без сетки (лут, тела, выброшенное) —
## grid = Vector2i.ZERO: без позиций, одинаковое складывается в одну запись.

const ITEMS_PATH := "res://data/items.json"
const LOOT_PATH := "res://data/loot.json"

static var _items: Dictionary = {}
static var _loot: Dictionary = {}

## Вес предмета без поля weight — по категории, кг.
const DEFAULT_WEIGHT := {"med": 0.15, "food": 0.4, "tech": 0.6, "value": 0.1, "barter": 0.2, "tools": 0.5, "intel": 0.2,
	"key": 0.05, "throw": 0.4, "misc": 0.3}


static func _ensure() -> void:
	if not _items.is_empty():
		return
	_items = (JSON.parse_string(FileAccess.get_file_as_string(ITEMS_PATH)) as Dictionary).get("items", {})
	# арсенал: оружие, патроны, магазины, обвес, броня — свои файлы данных (WeaponDb)
	_items.merge(WeaponDb.items())
	if _items.has("laser_head"):
		_items.laser_head["value"] = int(Balance.ENGRAVING.head_value)
	for id: String in Balance.ENGRAVING.parts_loot:
		_items[id]["value"] = int(Balance.ENGRAVING.parts_loot[id].value)
	for id: String in Balance.CIVILIAN_LOOT_VALUES:
		_items[id]["value"] = int(Balance.CIVILIAN_LOOT_VALUES[id])
	for id: String in Balance.VALUABLE_LOOT_VALUES:
		_items[id]["value"] = int(Balance.VALUABLE_LOOT_VALUES[id])
	# у оружия слот надевания — из его определения
	for id in WeaponDb.ids("weapons"):
		var it: Dictionary = _items[id]
		if not it.has("equip"):
			it["equip"] = {"slot": String((it.weapon as Dictionary).slot), "weapon": String(id)}
	# мелочь 1×1 складывается стопками (Balance.STACK_*): расходники и ценное — побольше
	for id in _items:
		var it: Dictionary = _items[id]
		var sz: Array = it.get("size", [1, 1])
		var cat := String(it.get("cat", "misc"))
		if int(sz[0]) != 1 or int(sz[1]) != 1 or it.has("equip") or cat in ["weapon", "mag", "armor", "plate"]:
			continue
		it["stack"] = maxi(int(it.get("stack", 1)), Balance.STACK_BIG if cat in Balance.STACK_BIG_CATS else Balance.STACK_SMALL)
	_loot = JSON.parse_string(FileAccess.get_file_as_string(LOOT_PATH)) as Dictionary


static func item(id: String) -> Dictionary:
	_ensure()
	return _items.get(WeaponDb.canonical(id), {"name": id, "cat": "misc", "cells": 1, "value": 0, "stack": 1})


## Есть ли такой предмет (item() на незнакомый id отдаёт заглушку, не пустоту).
## Только из рейда: Михалыч такое не продаёт (нет в его каталогах) и это не оружейное (стволы, магазины,
## патроны, обвес, броня вне каталогов — снаряжение ЧВК, его показывает «всё у Михалыча»). Головка
## станка, сигнал вызова самолёта, ценности, детали, пайки — купить можно только с читом «лут в продаже».
const ARSENAL_CATS := ["weapon", "mag", "ammo", "mod", "armor", "plate"]

static func loot_only(id: String) -> bool:
	# плёнку для наклеек Михалыч держит на продажу после задания «Фирменный знак»
	if id == String(Balance.STICKERS.film) and Stickers.printer_ready():
		return false
	var it := item(id)
	if bool(it.get("raid_only", false)):
		return true
	return TraderStock.catalog_of(id) <= 0 and not String(it.get("cat", "misc")) in ARSENAL_CATS


## Все id предметов (данные предметов и арсенала).
static func all_ids() -> Array:
	_ensure()
	return _items.keys()


static func exists(id: String) -> bool:
	_ensure()
	return _items.has(WeaponDb.canonical(id))


## Вес одной штуки, кг.
static func weight(id: String) -> float:
	var it := item(id)
	return float(it.get("weight", DEFAULT_WEIGHT.get(String(it.cat), 0.3)))


## Вес записи: штуки + всё, что в ней (обвес, магазин с патронами, плиты).
static func entry_weight(e: Dictionary) -> float:
	var w := weight(String(e.id)) * int(e.get("n", 1))
	for m in e.get("mods", {}):
		w += weight(WeaponDb.mod_id(e.mods[m]))
	var mag: Dictionary = e.get("mag", {}) if e.get("mag") is Dictionary else {}
	if not mag.is_empty():
		if String(mag.get("id", "")) != "":
			w += weight(String(mag.id))
		for layer: Variant in Gear.mag_layers(mag):
			w += weight(String(layer[0])) * int(layer[1])
	if e.has("rounds"):
		for layer: Variant in Gear.mag_layers(e):
			w += weight(String(layer[0])) * int(layer[1])
	if int(e.get("chamber", 0)) > 0:
		w += weight(String(e.get("chamber_ammo", mag.get("ammo", "")))) * int(e.chamber)
	for s in e.get("plates", {}):
		w += weight(String(e.plates[s].id))
	# подсумки на броне, магазины в них и в сбросе
	for p: Dictionary in pouch_list(e):
		w += weight(String(p.id))
	for part: String in ["mags", "dump"]:
		for inner: Variant in e.get(part, []):
			w += entry_weight(inner)
	return w


static func weight_of(list: Array) -> float:
	var w := 0.0
	for it in list:
		w += entry_weight(it)
	return w


static func item_name(id: String) -> String:
	return String(item(id).name)


static func cells(id: String) -> int:
	var s := size(id)
	return s.x * s.y


## Размер предмета в ячейках (ш × в); нет "size" — по старому числу ячеек.
static func size(id: String) -> Vector2i:
	var it := item(id)
	if it.has("size"):
		return Vector2i(int(it.size[0]), int(it.size[1]))
	match int(it.get("cells", 1)):
		1:
			return Vector2i(1, 1)
		2:
			return Vector2i(2, 1)
		3:
			return Vector2i(3, 1)
		4:
			return Vector2i(2, 2)
		6:
			return Vector2i(3, 2)
		_:
			return Vector2i(int(it.cells), 1)


## Размер записи в сетке с учётом поворота.
static func entry_size(e: Dictionary) -> Vector2i:
	var s := size(String(e.id))
	return Vector2i(s.y, s.x) if bool(e.get("r", false)) else s


static func stack(id: String) -> int:
	return int(item(id).stack)


static func value(id: String) -> int:
	return int(item(id).value)


## Описание контейнера по типу пропа ({} — такой проп не обыскивается).
static func container(kind: String) -> Dictionary:
	_ensure()
	return (_loot.get("containers", {}) as Dictionary).get(kind, {})


## Таблица по теме помещения (id комнаты) или "".
static func room_table(room_id: String) -> String:
	_ensure()
	return String((_loot.get("rooms", {}) as Dictionary).get(room_id, ""))


## Бросок таблицы: список {"id", "n"}; одинаковые предметы складываются.
static func roll(table_id: String, rng: RandomNumberGenerator) -> Array:
	_ensure()
	var table: Dictionary = (_loot.get("tables", {}) as Dictionary).get(table_id, {})
	if String(table.get("balance", "")) == "civilian":
		table = Balance.CIVILIAN_LOOT.get(table_id, {})
	var out: Array = []
	if table.is_empty():
		return out
	var entries: Array = table.entries
	var total := 0.0
	for e in entries:
		total += float(e[1])
	var rolls := rng.randi_range(int(table.rolls[0]), int(table.rolls[1]))
	for i in range(rolls):
		var pick := rng.randf() * total
		for e in entries:
			pick -= float(e[1])
			if pick <= 0.0:
				var id := String(e[0])
				# по тегам и тиру: случайный предмет арсенала (см. WeaponDb.pick)
				if id.begins_with("pick:"):
					id = WeaponDb.pick(id.trim_prefix("pick:"), rng)
					if id == "":
						break
				if id != "nothing":
					var n := rng.randi_range(int(e[2][0]), int(e[2][1]))
					var opts: Dictionary = e[3] if e.size() > 3 and e[3] is Dictionary else {}
					if id.begins_with("table:"):
						for k in range(n):
							out.append_array(roll(id.trim_prefix("table:"), rng))
					elif id.begins_with("preset:"):
						# готовая сборка: обвес, магазин (патронов — часть), износ (dur — в процентах)
						for k in range(n):
							var w := WeaponDb.make_weapon(id.trim_prefix("preset:"), rng, opts.get("dur", []))
							if not w.is_empty():
								_partial_mag(w, rng, opts)
								out.append(w)
					elif _stateful(make(id, 1)):
						# со своим состоянием — поштучно, изношенное: wear — доля [мин, макс]
						for k in range(n):
							out.append(_worn(make(id, 1), rng, opts.get("wear", [0.4, 1.0])))
					else:
						_merge(out, WeaponDb.canonical(id), n)
				break
	# добавки поверх бросков: [id, шанс, [от, до]] — ключи у главаря, ключ-карта в сейфе директора
	for e in table.get("extra", []):
		if rng.randf() < float(e[1]):
			_merge(out, WeaponDb.canonical(String(e[0])), rng.randi_range(int(e[2][0]), int(e[2][1])))
	# найдено в рейде: сдать Михалычу по заданию можно только такое (купленное — нет)
	if rng.randf() < float(Balance.VALUABLE_LOOT_CHANCE.get(table_id, 0.0)):
		var valuable: String = valuable_item(table_id, rng)
		if valuable != "":
			out.append(make(valuable, 1))
	if table_id in Balance.ENGRAVING.head_tables and rng.randf() < float(Balance.ENGRAVING.head_chance):
		out.append(make("laser_head", 1))
	for id: String in Balance.ENGRAVING.parts_loot:
		var spec: Dictionary = Balance.ENGRAVING.parts_loot[id]
		if table_id in spec.tables and rng.randf() < float(spec.chance):
			out.append(make(id, 1))
	for e in out:
		e["fir"] = true
	return out


## Одна видимая находка из темы: только переносимые гражданские модели, без вложенных бросков.
## Редкие лазерные головки и сюжетные грузы по-прежнему получают свой отдельный бросок в ящиках.
static func loose_item(table_id: String, rng: RandomNumberGenerator) -> String:
	var entries: Array = ((Balance.CIVILIAN_LOOT.get(table_id, {}) as Dictionary).get("entries", []) as Array).duplicate(true)
	entries.append_array(Balance.VALUABLE_LOOT.get(table_id, []))
	# снаряжение темы, которое может лежать на виду (разгрузки) — отдельным списком, вложенные в тему
	# броски ящиков сюда не попадают
	var gear: Array = Balance.LOOSE_GEAR.get(table_id, [])
	var gear_ids: Array = gear.map(func(g: Array) -> String: return String(g[0]))
	entries = entries.filter(func(e: Array) -> bool: return not String(e[0]) in gear_ids)
	entries.append_array(gear)
	var total: float = 0.0
	for entry: Array in entries:
		if Balance.CIVILIAN_LOOT_VALUES.has(String(entry[0])) or Balance.VALUABLE_LOOT_VALUES.has(String(entry[0])) or String(entry[0]) in gear_ids:
			total += float(entry[1])
	if total <= 0.0:
		return ""
	var pick: float = rng.randf() * total
	for entry: Array in entries:
		if not Balance.CIVILIAN_LOOT_VALUES.has(String(entry[0])) and not Balance.VALUABLE_LOOT_VALUES.has(String(entry[0])) and not String(entry[0]) in gear_ids:
			continue
		pick -= float(entry[1])
		if pick <= 0.0:
			return String(entry[0])
	return ""


## Взвешенная ценная находка из темы, без переброса остальных предметов контейнера.
static func valuable_item(table_id: String, rng: RandomNumberGenerator) -> String:
	var entries: Array = Balance.VALUABLE_LOOT.get(table_id, [])
	var total: float = 0.0
	for entry: Array in entries:
		total += float(entry[1])
	var pick: float = rng.randf() * total
	for entry: Array in entries:
		pick -= float(entry[1])
		if pick <= 0.0:
			return String(entry[0])
	return ""


## Вскрытие одной партии на копии сетки. При отказе исходная сетка не меняется.
static func unpack(list: Array, grid: Vector2i, idx: int, expected_id: String) -> Array:
	if idx < 0 or idx >= list.size() or String(list[idx].id) != expected_id or not Balance.LOOT_PACKS.has(expected_id):
		return []
	var copy: Array = list.duplicate(true)
	var found: bool = bool(copy[idx].get("fir", false))
	copy[idx].n = int(copy[idx].n) - 1
	if int(copy[idx].n) <= 0:
		copy.remove_at(idx)
	for content: Array in Balance.LOOT_PACKS[expected_id]:
		var item_entry: Dictionary = make(String(content[0]), int(content[1]))
		item_entry["fir"] = found
		if add_to(copy, item_entry, grid) != int(content[1]):
			return []
	return copy


## Износ найденного: прочность × случайная доля; плиты — отдельно.
static func _worn(one: Dictionary, rng: RandomNumberGenerator, wear: Array) -> Dictionary:
	if one.has("dur"):
		one.dur = roundf(float(one.dur) * rng.randf_range(float(wear[0]), float(wear[1])))
	for s in one.get("plates", {}):
		one.plates[s].dur = roundf(float(one.plates[s].dur) * rng.randf_range(float(wear[0]), float(wear[1])))
	return one


## Лут: в магазине найденного оружия — не полный боекомплект (rounds — доля [мин, макс]).
static func _partial_mag(w: Dictionary, rng: RandomNumberGenerator, opts: Dictionary) -> void:
	var mag: Dictionary = w.get("mag", {})
	if mag.is_empty():
		return
	var r: Array = opts.get("rounds", [0.0, 1.0])
	mag.rounds = int(round(float(mag.rounds) * rng.randf_range(float(r[0]), float(r[1]))))
	# найденный ствол не пристрелян под тебя: ноль сбит (Balance.ZEROING); случайность общая — броски
	# таблицы лута (rng) не сдвигаются
	Gear.knock_zero(w, Balance.ZEROING.found_moa)


static func _merge(list: Array, id: String, n: int) -> void:
	if WeaponCondition.supported(id):
		for i: int in range(n):
			list.append(make(id, 1))
		return
	for it in list:
		if String(it.id) == id and not it.has("dur"):
			it.n = int(it.n) + n
			return
	list.append({"id": id, "n": n})


static func equip(id: String) -> Dictionary:
	return item(id).get("equip", {})


## Слоты оружия (владелец 2026-10-19): клавиши 1 и 2 — крупное оружие (primary, secondary — любое, кроме пистолета и
## ракетницы), 3 — пистолет (sidearm), 5 — ракетница (launcher); клавиша 4 — граната. Вид ствола — "slot" в data/weapons.json.
const WEAPON_SLOTS := ["primary", "secondary", "sidearm", "launcher"]


## В какие слоты оружия встаёт ствол id: крупное — в первый и второй, пистолет — в свой, ракетница — в свой.
static func weapon_slots_for(id: String) -> Array:
	match String(equip(id).get("slot", "")):
		"sidearm":
			return ["sidearm"]
		"launcher":
			return ["launcher"]
	return ["primary", "secondary"]


## Подходит ли предмет в слот снаряжения.
static func slot_ok(id: String, slot: String) -> bool:
	var s := String(equip(id).get("slot", ""))
	if s == "":
		return false
	if equip(id).has("weapon"):
		return slot in weapon_slots_for(id)
	return s == slot


## Оружие из старых слотов (до 2026-10-19 любое оружие стояло в primary / secondary) — в свои: пистолет в sidearm, ракетница
## в launcher, если там свободно. eq — слот → запись (или запись шаблона с "id"); меняет и возвращает его же.
static func remap_weapon_slots(eq: Dictionary) -> Dictionary:
	for slot: String in ["primary", "secondary"]:
		if not eq.get(slot) is Dictionary:
			continue
		var id := String((eq[slot] as Dictionary).get("id", ""))
		if not equip(id).has("weapon") or slot_ok(id, slot):
			continue
		for to: String in weapon_slots_for(id):
			if not eq.has(to):
				eq[to] = eq[slot]
				eq.erase(slot)
				break
	return eq


## Подсумки живут на броне или поясе в слоте брони (gear_v2, 2026-10-24): в записи — pouches (id подсумков
## по порядку мест), mags (магазины в них, сетка "rig") и dump (сброс пустых — только логика, модели нет).
## Запись снаряжения, которая несёт подсумки; {} — брони с местами нет.
static func rig_entry(eq: Dictionary) -> Dictionary:
	var e: Dictionary = eq.get("armor", {})
	if e.is_empty() or int(WeaponDb.vest(String(e.get("id", ""))).get("places", 0)) <= 0:
		return {}
	return e


## Сетки подсумков по надетой броне: part — "rig" (магазины: колонка на подсумок, у большого две — под барабан)
## или "dump" (сброс пустых — половина от числа подсумков). ZERO — нет.
static func rig_grid(eq: Dictionary, part: String = "rig") -> Vector2i:
	var e := rig_entry(eq)
	if e.is_empty():
		return Vector2i.ZERO
	var n := 0
	if part == "dump":
		n = ceili(float(pouch_list(e).size()) / 2.0)
	else:
		for col: Dictionary in rig_columns(e):
			n += int(col.w)
	return Vector2i(n, int(Balance.RIG.rows)) if n > 0 else Vector2i.ZERO


## Подсумки на броне по порядку мест (места считаются половинками: at — номер полуслота с 1; пистолетный
## занимает 1, автоматный 2, большой 4). Старый формат (список id) переводится: подряд с первого полуслота.
static func pouch_list(e: Dictionary) -> Array:
	var raw: Variant = e.get("pouches", [])
	if not raw is Array or (raw as Array).is_empty():
		return []
	var list := raw as Array
	if list[0] is String:
		# по порядку на первое подходящее место; не встал по правилам (большой не на свою пару) — на первые
		# свободные полуслоты подряд, чтобы подсумок не пропал
		var ids := list.duplicate()
		var out: Array = []
		e["pouches"] = out
		for pid: Variant in ids:
			var at := pouch_free_at(e, String(pid))
			if at < 0:
				at = _free_run(out, pouch_half(String(pid)))
			out.append({"id": String(pid), "at": at})
		list = out
	list.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a.at) < int(b.at))
	return list


## Первый полуслот, с которого свободны half полуслотов подряд (без правил вида; для перевода старых записей).
static func _free_run(list: Array, half: int) -> int:
	var at := 1
	while true:
		var clash := false
		for q: Dictionary in list:
			var qa := int(q.at)
			var qb := qa + pouch_half(String(q.id)) - 1
			if at <= qb and at + half - 1 >= qa:
				clash = true
				at = qb + 1
				break
		if not clash:
			return at
	return at


static func pouch_ids(e: Dictionary) -> Array:
	var out: Array = []
	for p: Dictionary in pouch_list(e):
		out.append(String(p.id))
	return out


## Сколько полуслотов занимает подсумок (пистолетный 1, автоматный 2, большой 4); 0 — не подсумок.
static func pouch_half(id: String) -> int:
	return roundi(pouch_cost(id) * 2.0)


## Вид подсумка: pistol / rifle / big.
static func pouch_kind(id: String) -> String:
	return String((item(id).get("pouch", {}) as Dictionary).get("mags", ""))


## Встанет ли подсумок pid на полуслот at брони e: в пределах мест, автоматный — с целого места, большой —
## только на пару мест из данных брони (pairs_big), и полуслоты свободны. skip — не считать подсумок с этим номером.
static func pouch_fits(e: Dictionary, pid: String, at: int, skip: int = -1) -> bool:
	var v := WeaponDb.vest(String(e.get("id", "")))
	var places := int(v.get("places", 0))
	var half := pouch_half(pid)
	if half <= 0 or at < 1 or at + half - 1 > places * 2:
		return false
	var kind := pouch_kind(pid)
	if kind in ["rifle", "big"] and at % 2 == 0:
		return false
	if kind == "big":
		var p := (at + 1) / 2
		var ok := false
		for pair: Variant in v.get("pairs_big", []):
			if int((pair as Array)[0]) == p and int((pair as Array)[1]) == p + 1:
				ok = true
		if not ok:
			return false
	var i := 0
	for q: Dictionary in pouch_list(e):
		if i != skip:
			var qa := int(q.at)
			var qb := qa + pouch_half(String(q.id)) - 1
			if at <= qb and at + half - 1 >= qa:
				return false
		i += 1
	return true


## Первый полуслот, куда встанет подсумок; -1 — некуда.
static func pouch_free_at(e: Dictionary, pid: String) -> int:
	var places := int(WeaponDb.vest(String(e.get("id", ""))).get("places", 0))
	for at in range(1, places * 2 + 1):
		if pouch_fits(e, pid, at):
			return at
	return -1


## Колонки сетки магазинов по подсумкам: {kind, w (у большого 2), x0, pouch (номер в pouch_list)}.
static func rig_columns(e: Dictionary) -> Array:
	var out: Array = []
	var x := 0
	var i := 0
	for p: Dictionary in pouch_list(e):
		var kind := pouch_kind(String(p.id))
		var w := 2 if kind == "big" else 1
		out.append({"kind": kind, "w": w, "x0": x, "pouch": i})
		x += w
		i += 1
	return out


## Подписи колонок сетки магазинов для окна (GridView.column_groups): [[x0, ширина, «пист» / «авт» / «большой»], …].
static func rig_column_groups(eq: Dictionary) -> Array:
	var out: Array = []
	for col: Dictionary in rig_columns(rig_entry(eq)):
		out.append([int(col.x0), int(col.w), {"pistol": "пист", "rifle": "авт", "big": "большой"}.get(String(col.kind), "")])
	return out


## Вид подсумка под колонкой x сетки магазинов ("" — нет).
static func rig_kind_at(eq: Dictionary, x: int) -> String:
	var e := rig_entry(eq)
	for col: Dictionary in rig_columns(e):
		if x >= int(col.x0) and x < int(col.x0) + int(col.w):
			return String(col.kind)
	return ""


## Какой магазин в какой подсумок: пистолетный — только пистолетные (до 20 патронов, 1×1); автоматный — всё,
## кроме крупных (от 50); большой — любой.
static func mag_fits_kind(kind: String, id: String) -> bool:
	var mag := WeaponDb.magazine(id)
	if mag.is_empty():
		return false
	var cap := int(mag.get("capacity", 0))
	match kind:
		"pistol":
			return cap <= 20 and size(id) == Vector2i(1, 1)
		"rifle":
			return cap < 50
		"big":
			return true
	return false


## Примет ли сетка подсумков запись в клетку (x, y, r): только магазин, и каждая колонка под ним — своего вида.
static func rig_accepts_at(eq: Dictionary, entry: Dictionary, x: int, y: int, r: bool) -> bool:
	if not grid_accepts("rig", entry):
		return false
	return rig_id_fits_at(eq, String(entry.id), x, r)


## То же по id (для подсветки при перетаскивании): каждая колонка под магазином — подсумок его вида.
static func rig_id_fits_at(eq: Dictionary, id: String, x: int, r: bool) -> bool:
	var s := size(id)
	if r:
		s = Vector2i(s.y, s.x)
	for dx in range(s.x):
		if not mag_fits_kind(rig_kind_at(eq, x + dx), id):
			return false
	return true


## Номер подсумка в pouch_list, который занимает полуслот at; -1 — пусто.
static func pouch_index_at(e: Dictionary, at: int) -> int:
	var i := 0
	for p: Dictionary in pouch_list(e):
		if at >= int(p.at) and at < int(p.at) + pouch_half(String(p.id)):
			return i
		i += 1
	return -1


## Переставить подсумок с полуслота from_at на to_at (магазины переезжают по новым колонкам; не влезшие
## возвращаются). [] и false в первом — не встаёт.
static func move_pouch(eq: Dictionary, from_at: int, to_at: int) -> Array:
	var e := rig_entry(eq)
	var i := pouch_index_at(e, from_at)
	if i < 0:
		return [false, []]
	var p: Dictionary = pouch_list(e)[i]
	if not pouch_fits(e, String(p.id), to_at, i):
		return [false, []]
	p["at"] = to_at
	pouch_list(e)
	return [true, rig_relayout(eq)]


## Положить магазин в подсумки брони куда влезет по виду; сколько положил (0 — некуда).
static func add_to_rig(eq: Dictionary, entry: Dictionary) -> int:
	return rig_add(eq, rig_list(eq, "rig"), entry)


## То же в список list (копию сетки подсумков брони eq — так работает Inventory).
static func rig_add(eq: Dictionary, list: Array, entry: Dictionary) -> int:
	var grid := rig_grid(eq, "rig")
	if grid == Vector2i.ZERO or not grid_accepts("rig", entry):
		return 0
	var one := entry.duplicate(true)
	for key in ["x", "y", "r"]:
		one.erase(key)
	for x in range(grid.x):
		for y in range(grid.y):
			if rig_accepts_at(eq, one, x, y, false):
				var k := put_at(list, one, grid, x, y, false)
				if k > 0:
					return k
	return 0


## Магазины в подсумках — заново по колонкам (после снятия подсумка колонки сдвинулись); что не влезло — вернуть.
static func rig_relayout(eq: Dictionary) -> Array:
	var e := rig_entry(eq)
	if e.is_empty():
		return []
	var mags: Array = (e.get("mags", []) as Array).duplicate(true)
	e["mags"] = []
	var out: Array = []
	for m: Dictionary in mags:
		for key in ["x", "y", "r"]:
			m.erase(key)
		if add_to_rig(eq, m) <= 0:
			out.append(m)
	return out


## Что лежит в подсумках надетой брони: part — "rig" (поле mags) или "dump".
static func rig_list(eq: Dictionary, part: String = "rig") -> Array:
	var e := rig_entry(eq)
	if e.is_empty():
		return []
	var key := "dump" if part == "dump" else "mags"
	if not e.get(key) is Array:
		e[key] = []
	return e[key]


## Сколько мест на броне занимает подсумок (автоматный 1, пистолетный 0,5, большой 2); 0 — не подсумок.
static func pouch_cost(id: String) -> float:
	return float((item(id).get("pouch", {}) as Dictionary).get("places", 0.0))


## Свободные места на броне записи e (places из данных брони минус надетые подсумки).
static func places_free(e: Dictionary) -> float:
	var total := float(WeaponDb.vest(String(e.get("id", ""))).get("places", 0))
	for p: Dictionary in pouch_list(e):
		total -= pouch_cost(String(p.id))
	return total


## Повесить подсумок pid на броню e в полуслот at (at < 0 — первый подходящий); false — не встаёт.
static func attach_pouch(e: Dictionary, pid: String, at: int = -1) -> bool:
	if at < 0:
		at = pouch_free_at(e, pid)
	if at < 0 or not pouch_fits(e, pid, at):
		return false
	pouch_list(e)
	if not e.get("pouches") is Array:
		e["pouches"] = []
	(e.pouches as Array).append({"id": pid, "at": at})
	pouch_list(e)
	return true


## Снять один подсумок (номер в pouch_list): возвращает записи — сам подсумок и магазины, которым не
## осталось подсумка своего вида; остальные магазины переложены по новым колонкам.
static func detach_pouch(eq: Dictionary, i: int) -> Array:
	var e := rig_entry(eq)
	var list := pouch_list(e)
	if i < 0 or i >= list.size():
		return []
	var out: Array = [make(String((list[i] as Dictionary).id), 1)]
	list.remove_at(i)
	e["pouches"] = list
	out.append_array(rig_relayout(eq))
	if list.is_empty():
		for part: String in ["mags", "dump"]:
			for inner: Variant in e.get(part, []):
				if inner is Dictionary:
					var m := (inner as Dictionary).duplicate(true)
					for key in ["x", "y", "r"]:
						m.erase(key)
					out.append(m)
		e.erase("pouches")
		e.erase("mags")
		e.erase("dump")
	return out


## Снять с брони все подсумки: возвращает записи подсумков, магазинов и сброса — их кладут в сетку.
static func detach_pouches(e: Dictionary) -> Array:
	var out: Array = []
	for p: Dictionary in pouch_list(e):
		out.append(make(String(p.id), 1))
	for part: String in ["mags", "dump"]:
		for inner: Variant in e.get(part, []):
			if inner is Dictionary:
				var m := (inner as Dictionary).duplicate(true)
				for key in ["x", "y", "r"]:
					m.erase(key)
				out.append(m)
	e.erase("pouches")
	e.erase("mags")
	e.erase("dump")
	return out


## Можно ли положить запись в сетку role: в подсумки и сумку сброса — только магазины, в защищённый
## карман — всё, кроме груза с no_pocket.
static func grid_accepts(role: String, entry: Dictionary) -> bool:
	if role in ["rig", "dump"]:
		return entry.has("rounds") and not WeaponDb.magazine(String(entry.get("id", ""))).is_empty()
	# крупный груз заказа (колесо, радиатор) в защищённый карман не кладут — его несут в рюкзаке
	if role == "pocket":
		return not bool(item(String(entry.get("id", ""))).get("no_pocket", false))
	return true


## Крепления надетого шлема (данные helmet.mounts: NVG, HEADSET, LIGHT, VISOR); без шлема — пусто.
static func helmet_mounts(eq: Dictionary) -> Array:
	var h: Variant = eq.get("helmet", null)
	if not h is Dictionary:
		return []
	return WeaponDb.helmet(String((h as Dictionary).get("id", ""))).get("mounts", []) as Array


## Почему предмет id нельзя надеть в слот при надетом eq ("" — можно; docs/design/equip_doll_v2.md, п. 3):
## ПНВ носят и без шлема, но под шлем без площадки он не встаёт; и шлем без площадки поверх ПНВ не надеть.
static func slot_block(id: String, slot: String, eq: Dictionary) -> String:
	var helmet: Variant = eq.get("helmet")
	if slot == "eyes" and bool(equip(id).get("nvg", false)) and helmet is Dictionary and not (helmet as Dictionary).is_empty() and not "NVG" in helmet_mounts(eq):
		return "шлем без крепления ПНВ"
	if slot == "helmet":
		var eyes: Variant = eq.get("eyes", null)
		var nvg_on := eyes is Dictionary and bool(equip(String((eyes as Dictionary).get("id", ""))).get("nvg", false))
		if nvg_on and not "NVG" in (WeaponDb.helmet(id).get("mounts", []) as Array):
			return "у шлема нет крепления ПНВ — сначала сними ПНВ"
	return ""


## Куда надеть предмет: want — слот, на который бросили (если подходит); оружие без указания —
## в свой слот по данным, если он занят, а другой свободен — в другой. Слот, закрытый правилом
## (slot_block), — "".
static func pick_slot(id: String, eq: Dictionary, want: String = "") -> String:
	var s0 := _pick_slot(id, eq, want)
	return s0 if s0 == "" or slot_block(id, s0, eq) == "" else ""


static func _pick_slot(id: String, eq: Dictionary, want: String = "") -> String:
	if want != "" and slot_ok(id, want):
		return want
	var s := String(equip(id).get("slot", ""))
	if s != "" and equip(id).has("weapon"):
		var fits: Array = weapon_slots_for(id)
		for o in fits:
			if not eq.get(o) is Dictionary or (eq[o] as Dictionary).is_empty():
				return String(o)
		return String(fits[0])
	return s


## Новый экземпляр предмета (id по алиасам): оружие — новое, с пустым штатным магазином;
## магазин — пустой; броня, шлем, плита — полная прочность.
static func make(id: String, n: int) -> Dictionary:
	id = WeaponDb.canonical(id)
	var e := {"id": id, "n": n}
	if WeaponDb.is_weapon(id):
		WeaponMark.identify(e)
		e.n = 1
		var w := WeaponDb.weapon(id)
		e["dur"] = 100.0
		e["mods"] = {}
		e["mag"] = {"id": "" if w.has("internal_mag") else WeaponDb.default_mag(id), "ammo": WeaponDb.default_ammo(String(w.caliber)), "rounds": 0}
		e["sight"] = "primary"
	elif item(id).has("rig"):
		# разгрузка: что в подсумках и в сумке сброса — внутри самой записи (ездит вместе с ней)
		e.n = 1
		e["mags"] = []
		e["dump"] = []
	elif id == "laser_head":
		e.n = 1
		e["uid"] = WeaponMark.new_id()
		e["charges"] = int(Balance.ENGRAVING.charges)
	elif not WeaponDb.attachment(id).is_empty():
		e.n = 1
		e["dur"] = float(Balance.CONDITION.full)
	elif not WeaponDb.magazine(id).is_empty():
		e.n = 1
		e["ammo"] = WeaponDb.default_ammo(WeaponDb.mag_caliber(id))
		e["rounds"] = 0
	elif not WeaponDb.vest(id).is_empty():
		var v := WeaponDb.make_vest(id)
		v.n = 1
		return v
	elif not WeaponDb.helmet(id).is_empty():
		e["dur"] = float(WeaponDb.helmet(id).durability)
	elif not WeaponDb.plate(id).is_empty():
		e["dur"] = float(WeaponDb.plate(id).durability)
	return e


## Предмет с состоянием (прочность, обвес, магазин, патроны в магазине, плиты) не складывается.
static func can_merge(a: Dictionary, b: Dictionary) -> bool:
	if String(a.id) != String(b.id) or _stateful(a) or _stateful(b):
		return false
	# найденное в рейде с купленным в одну стопку не ложится (сдают «из рейда»); патроны — ложатся:
	# их не сдают, а россыпь одного калибра по клеткам только съедает рюкзак
	return String(item(String(a.id)).get("cat", "")) == "ammo" or bool(a.get("fir", false)) == bool(b.get("fir", false))


## В стопку dst добавили из src: смешали «из рейда» с купленным — пометка снимается.
static func _merged_fir(dst: Dictionary, src: Dictionary) -> void:
	if bool(dst.get("fir", false)) != bool(src.get("fir", false)):
		dst.erase("fir")


## Экземпляр со своим состоянием — всегда поштучно.
static func _stateful(e: Dictionary) -> bool:
	return e.has("dur") or e.has("mods") or e.has("mag") or e.has("rounds") or e.has("plates") or e.has("charges") or e.has("mags")


## Определение обвеса (data/weapons.json → attach).
static func mod_spec(id: String) -> Dictionary:
	return WeaponDb.attachment(id)


## Обвес mod встаёт на оружие-запись weapon_entry хоть в какую-то точку (свободную или на замену).
static func mod_fits(mod: String, weapon_entry: Dictionary) -> bool:
	return not WeaponDb.mounts_for(weapon_entry, mod).is_empty()


## Сколько ячеек занято (стопки по stack).
static func cells_of(list: Array) -> int:
	var c := 0
	for it in list:
		c += cells(String(it.id)) * int(ceil(float(it.n) / float(stack(String(it.id)))))
	return c


# ---------------------------------------------------------------- сетка

## Карта занятости сетки: 1 — занято. skip — запись, которую не учитываем (её двигают).
static func occupancy(list: Array, grid: Vector2i, skip: int = -1) -> PackedByteArray:
	var occ := PackedByteArray()
	occ.resize(grid.x * grid.y)
	for i in range(list.size()):
		if i == skip or not list[i].has("x"):
			continue
		var s := entry_size(list[i])
		var x0 := int(list[i].x)
		var y0 := int(list[i].y)
		for y in range(y0, mini(y0 + s.y, grid.y)):
			for x in range(x0, mini(x0 + s.x, grid.x)):
				if x >= 0 and y >= 0:
					occ[y * grid.x + x] = 1
	return occ


static func fits_at(occ: PackedByteArray, grid: Vector2i, x: int, y: int, s: Vector2i) -> bool:
	if x < 0 or y < 0 or x + s.x > grid.x or y + s.y > grid.y:
		return false
	for yy in range(y, y + s.y):
		for xx in range(x, x + s.x):
			if occ[yy * grid.x + xx] != 0:
				return false
	return true


## Сетка того, что несёшь, по надетому: рюкзак — его equip.grid, без рюкзака — карманы.
static func bag_grid(eq: Dictionary) -> Vector2i:
	var bp: Dictionary = eq.get("backpack", {})
	if bp.is_empty():
		return Balance.CARRY_GRID
	var g: Array = equip(String(bp.id)).get("grid", [Balance.CARRY_GRID.x, Balance.CARRY_GRID.y])
	return Vector2i(int(g[0]), int(g[1]))


## Во сколько раз быстрее тратится выносливость в спринте с надетым рюкзаком.
static func bag_sprint_k(eq: Dictionary) -> float:
	var bp: Dictionary = eq.get("backpack", {})
	return 1.0 if bp.is_empty() else float(equip(String(bp.id)).get("sprint_k", 1.0))


static func _mark(occ: PackedByteArray, grid: Vector2i, x: int, y: int, s: Vector2i) -> void:
	for yy in range(y, y + s.y):
		for xx in range(x, x + s.x):
			occ[yy * grid.x + xx] = 1


## Первое свободное место под предмет id: сначала как есть, потом повёрнутым. (x, y, r) или (-1,…).
static func find_spot(occ: PackedByteArray, grid: Vector2i, id: String) -> Vector3i:
	var s := size(id)
	for rot in ([0, 1] if s.x != s.y else [0]):
		var ss := Vector2i(s.y, s.x) if rot == 1 else s
		for y in range(grid.y - ss.y + 1):
			for x in range(grid.x - ss.x + 1):
				if fits_at(occ, grid, x, y, ss):
					return Vector3i(x, y, rot)
	return Vector3i(-1, -1, 0)


## Сколько штук entry влезет (grid = ZERO — без предела): добор неполных стопок + новые стопки
## в свободные места.
static func room_in(list: Array, entry: Dictionary, grid: Vector2i) -> int:
	var id := String(entry.id)
	if grid == Vector2i.ZERO:
		return int(entry.n)
	var occ := occupancy(list, grid)
	if _stateful(entry):
		return 1 if find_spot(occ, grid, id).x >= 0 else 0
	var st := stack(id)
	var room := 0
	for it in list:
		if can_merge(it, entry):
			room += maxi(0, st - int(it.n))
	var want := int(entry.n)
	while room < want:
		var spot := find_spot(occ, grid, id)
		if spot.x < 0:
			break
		var s := size(id)
		_mark(occ, grid, spot.x, spot.y, Vector2i(s.y, s.x) if spot.z == 1 else s)
		room += st
	return room


## Кладёт в list сколько влезет из entry; возвращает, сколько положил (list меняется).
## В сетке: добирает неполные стопки, остальное — новыми стопками в первые свободные места.
static func add_to(list: Array, entry: Dictionary, grid: Vector2i) -> int:
	var id := String(entry.id)
	if grid == Vector2i.ZERO:
		var k0 := int(entry.n)
		if k0 <= 0:
			return 0
		for it in list:
			if can_merge(it, entry):
				it.n = int(it.n) + k0
				_merged_fir(it, entry)
				return k0
		var e0 := entry.duplicate(true)
		# пометка поштучной операции (MagOps) не переезжает с предметом
		for key in ["x", "y", "r", "op"]:
			e0.erase(key)
		list.append(e0)
		return k0
	var left := int(entry.n)
	var st := 1 if _stateful(entry) else stack(id)
	if not _stateful(entry):
		for it in list:
			if left <= 0:
				break
			if can_merge(it, entry) and int(it.n) < st:
				var k := mini(left, st - int(it.n))
				it.n = int(it.n) + k
				_merged_fir(it, entry)
				left -= k
	var occ := occupancy(list, grid)
	while left > 0:
		var spot := find_spot(occ, grid, id)
		if spot.x < 0:
			break
		var e := entry.duplicate(true)
		e.erase("op")
		e.n = mini(left, st)
		e.x = spot.x
		e.y = spot.y
		e.r = spot.z == 1
		_mark(occ, grid, spot.x, spot.y, entry_size(e))
		list.append(e)
		left -= int(e.n)
	return int(entry.n) - left


## Положить entry ровно в (x, y) с поворотом r (перетаскивание мышью). На такую же неполную
## стопку — добирает её. Возвращает, сколько положил.
static func put_at(list: Array, entry: Dictionary, grid: Vector2i, x: int, y: int, r: bool) -> int:
	var id := String(entry.id)
	var st := 1 if _stateful(entry) else stack(id)
	# на стопку того же — добор
	for it in list:
		if it.has("x") and int(it.x) == x and int(it.y) == y and can_merge(it, entry):
			var k := mini(int(entry.n), st - int(it.n))
			if k > 0:
				it.n = int(it.n) + k
				_merged_fir(it, entry)
			return maxi(k, 0)
	var e := entry.duplicate(true)
	e.erase("op")
	e.r = r
	e.x = x
	e.y = y
	e.n = mini(int(entry.n), st)
	if not fits_at(occupancy(list, grid), grid, x, y, entry_size(e)):
		return 0
	list.append(e)
	return int(e.n)


## Передвинуть запись idx внутри той же сетки. false — место занято.
static func move_in(list: Array, grid: Vector2i, idx: int, x: int, y: int, r: bool) -> bool:
	if idx < 0 or idx >= list.size():
		return false
	var e: Dictionary = list[idx]
	var probe := e.duplicate()
	probe.r = r
	if not fits_at(occupancy(list, grid, idx), grid, x, y, entry_size(probe)):
		# на такую же неполную стопку — слить
		for i in range(list.size()):
			var it: Dictionary = list[i]
			if i != idx and it.has("x") and int(it.x) == x and int(it.y) == y and can_merge(it, e):
				var k := mini(int(e.n), stack(String(e.id)) - int(it.n))
				if k <= 0:
					return false
				it.n = int(it.n) + k
				_merged_fir(it, e)
				e.n = int(e.n) - k
				if int(e.n) <= 0:
					list.remove_at(idx)
				return true
		return false
	e.x = x
	e.y = y
	e.r = r
	return true


## Разложить список по сетке заново (старые профили без позиций, стопки больше stack):
## крупное — первым. Возвращает то, что не влезло (list меняется).
static func pack(list: Array, grid: Vector2i) -> Array:
	var flat: Array = []
	for it in list:
		var st := 1 if _stateful(it) else stack(String(it.id))
		var n := int(it.n)
		while n > 0:
			var one: Dictionary = (it as Dictionary).duplicate(true)
			one.n = mini(n, st)
			for key in ["x", "y", "r"]:
				one.erase(key)
			flat.append(one)
			n -= int(one.n)
	flat.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return cells(String(a.id)) > cells(String(b.id)))
	list.clear()
	var over: Array = []
	for it in flat:
		if add_to(list, it, grid) < int(it.n):
			over.append(it)
	return over


## Сортировка сетки: стопки одного добираются до полных, крупное — в начало, дальше по категории
## и названию. Новая раскладка или [] — не влезла бы (тогда оставить как есть).
static func arranged(list: Array, grid: Vector2i) -> Array:
	var order := ["weapon", "armor", "plate", "mag", "ammo", "mod", "med", "food", "throw", "tools", "tech", "value", "barter", "intel", "key", "misc"]
	var flat: Array = []
	for it in list:
		var e: Dictionary = (it as Dictionary).duplicate(true)
		for key in ["x", "y", "r"]:
			e.erase(key)
		flat.append(e)
	flat.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		var sa := size(String(a.id))
		var sb := size(String(b.id))
		if sa.x * sa.y != sb.x * sb.y:
			return sa.x * sa.y > sb.x * sb.y
		if maxi(sa.x, sa.y) != maxi(sb.x, sb.y):
			return maxi(sa.x, sa.y) > maxi(sb.x, sb.y)
		var ca := order.find(String(item(String(a.id)).get("cat", "misc")))
		var cb := order.find(String(item(String(b.id)).get("cat", "misc")))
		if ca != cb:
			return ca < cb
		if String(a.id) != String(b.id):
			return item_name(String(a.id)) < item_name(String(b.id))
		return int(a.n) > int(b.n))
	var out: Array = []
	for e in flat:
		if add_to(out, e, grid) < int(e.n):
			return []
	return out


## Переложить список в сетку grid (сменили рюкзак): [что встало, что не влезло]. Уже стоящее
## без наложений — как есть, иначе — как arranged (крупное раньше), не вышло — по одному.
static func refit(list: Array, grid: Vector2i) -> Array:
	if grid_ok(list, grid):
		return [list.duplicate(true), []]
	var out := arranged(list, grid)
	if not out.is_empty() or list.is_empty():
		return [out, []]
	var fitted: Array = []
	var spill: Array = []
	for e in list:
		var one: Dictionary = (e as Dictionary).duplicate(true)
		for k in ["x", "y", "r"]:
			one.erase(k)
		var n := int(one.n)
		var got := add_to(fitted, one.duplicate(true), grid)
		if got < n:
			var rest := one.duplicate(true)
			rest.n = n - got
			spill.append(rest)
	return [fitted, spill]


## Все ли записи сетки стоят на местах без наложений (для проверок и миграции).
static func grid_ok(list: Array, grid: Vector2i) -> bool:
	var occ := PackedByteArray()
	occ.resize(grid.x * grid.y)
	for it in list:
		if not it.has("x") or int(it.n) > (1 if _stateful(it) else stack(String(it.id))):
			return false
		var s := entry_size(it)
		if not fits_at(occ, grid, int(it.x), int(it.y), s):
			return false
		_mark(occ, grid, int(it.x), int(it.y), s)
	return true


## Вынимает из list[idx] до n штук; возвращает вынутое ({} — нечего).
static func remove_at(list: Array, idx: int, n: int) -> Dictionary:
	if idx < 0 or idx >= list.size():
		return {}
	var e: Dictionary = list[idx]
	var k := mini(n, int(e.n))
	var out := e.duplicate(true)
	out.n = k
	e.n = int(e.n) - k
	if int(e.n) <= 0:
		list.remove_at(idx)
	return out


## Наибольшая прочность предмета (оружие — 100; броня, шлем, плита — из данных; 0 — без износа).
static func max_dur(id: String) -> float:
	if WeaponCondition.supported(id):
		return 100.0
	var v := WeaponDb.vest(id)
	if not v.is_empty():
		return float((v.soft as Dictionary).durability) if v.get("soft") != null else 0.0
	if not WeaponDb.helmet(id).is_empty():
		return float(WeaponDb.helmet(id).durability)
	if not WeaponDb.plate(id).is_empty():
		return float(WeaponDb.plate(id).durability)
	return 0.0


## Название с состоянием: «Автомат 5.45×39 · 91% · маг. 30», «Магазин … · на 30 патр.» — сколько
## патронов внутри, не видно (проверить: зажать R с оружием, у магазина — «Проверить патроны»),
## «Плитоносец … · перед 21/72 · зад 70/72», «Шлем … · 32/50».
static func label(entry: Dictionary) -> String:
	return _label(entry) + ("  · из рейда" if bool(entry.get("fir", false)) else "")


static func _label(entry: Dictionary) -> String:
	var id := String(entry.id)
	var t := item_name(id)
	if WeaponCondition.supported(id) and WeaponCondition.broken(entry):
		t += " · СЛОМАНО"
	if WeaponDb.is_weapon(id):
		t += " · %d%%" % int(entry.get("dur", 100))
		var mag: Dictionary = entry.get("mag", {}) if entry.get("mag") is Dictionary else {}
		if not mag.is_empty():
			t += " · маг. %d" % WeaponDb.capacity(entry)
		if not (entry.get("mods", {}) as Dictionary).is_empty():
			t += " · обвес: %d" % (entry.mods as Dictionary).size()
		return t
	if not WeaponDb.attachment(id).is_empty():
		return t + " · %d%%" % int(WeaponCondition.percent(entry))
	if entry.has("rounds"):
		var cap := int(WeaponDb.magazine(id).get("capacity", 0))
		# вместимость — в названии («… на 30»); нет — дописать
		if not t.contains("на %d" % cap):
			t += " · на %d патр." % cap
		# сколько внутри — не видно: только «полный» / «пустой», после проверки — оценка
		var st := Gear.mag_state(entry)
		return t + (" · " + st if st != "" else "")
	if entry.has("plates"):
		var pl: Dictionary = entry.plates
		for s in ["front", "back"]:
			if s in WeaponDb.vest(id).get("plates", []):
				t += " · %s %s" % ["перед" if s == "front" else "зад", ("%d/%d" % [int(pl[s].dur), int(max_dur(String(pl[s].id)))]) if pl.has(s) else "—"]
		return t
	if entry.has("dur") and max_dur(id) > 0.0:
		t += " · %d/%d" % [int(entry.dur), int(max_dur(id))]
	return t


## Цена с учётом износа и того, что внутри (обвес, магазин с патронами, плиты).
static func entry_value(entry: Dictionary) -> int:
	var id := String(entry.id)
	var v := float(value(id)) * int(entry.get("n", 1))
	if id == "laser_head":
		v = lerpf(float(Balance.ENGRAVING.spent_value), float(Balance.ENGRAVING.head_value), float(entry.get("charges", 0)) / float(Balance.ENGRAVING.charges))
	var mx := max_dur(id)
	if entry.has("dur") and mx > 0.0:
		v *= clampf(float(entry.dur) / mx, 0.2, 1.0)
	for slot in entry.get("mods", {}):
		v += entry_value(WeaponCondition.mod_entry(entry.mods[slot]))
	var mag: Dictionary = entry.get("mag", {}) if entry.get("mag") is Dictionary else {}
	if not mag.is_empty():
		if String(mag.get("id", "")) != "":
			v += float(value(String(mag.id)))
		for layer: Variant in Gear.mag_layers(mag):
			v += float(value(String(layer[0]))) * int(layer[1])
	if entry.has("rounds"):
		for layer: Variant in Gear.mag_layers(entry):
			v += float(value(String(layer[0]))) * int(layer[1])
	if int(entry.get("chamber", 0)) > 0:
		v += float(value(String(entry.get("chamber_ammo", mag.get("ammo", ""))))) * int(entry.chamber)
	for s in entry.get("plates", {}):
		var p: Dictionary = entry.plates[s]
		v += float(value(String(p.id))) * clampf(float(p.dur) / maxf(1.0, max_dur(String(p.id))), 0.2, 1.0)
	for part: String in ["mags", "dump"]:
		for inner: Variant in entry.get(part, []):
			v += float(entry_value(inner))
	return int(v)


static func value_of(list: Array) -> int:
	var v := 0
	for it in list:
		v += entry_value(it)
	return v


## Старые id из сохранений (псевдонимы data/weapons.json → aliases: vest_*, carrier_*, helmet_* и прежние) — в нынешние:
## сам предмет, плиты, магазин в стволе, магазины в подсумках и сумке сброса разгрузки.
static func canon_entry(e: Dictionary) -> void:
	if e.has("id"):
		e.id = WeaponDb.canonical(String(e.id))
	for mount: String in e.get("mods", {}):
		var mod: Variant = e.mods[mount]
		if mod is Dictionary:
			canon_entry(mod as Dictionary)
		elif mod is String:
			e.mods[mount] = WeaponDb.canonical(String(mod))
	for s in e.get("plates", {}):
		var pl: Variant = (e.plates as Dictionary)[s]
		if pl is Dictionary and (pl as Dictionary).has("id"):
			(pl as Dictionary).id = WeaponDb.canonical(String((pl as Dictionary).id))
	if e.get("mag", null) is Dictionary and (e.mag as Dictionary).has("id"):
		(e.mag as Dictionary).id = WeaponDb.canonical(String((e.mag as Dictionary).id))
	for part: String in ["mags", "dump"]:
		for inner: Variant in e.get(part, []):
			if inner is Dictionary:
				canon_entry(inner as Dictionary)


static func canon_list(list: Array) -> void:
	for e: Variant in list:
		if e is Dictionary:
			canon_entry(e as Dictionary)


## Шаблон снаряжения (LoadoutTemplates / Balance.TRADER_KITS): slots — {слот: {id, plates: {гнездо: id},
## pouches: [id]}}, backpack — [[id, штук]]. Прежний слот "rig" — подсумки на броне (автоматные по числу
## подсумков разгрузки).
static func canon_template(t: Dictionary) -> void:
	var slots_d: Dictionary = t.get("slots", {})
	if slots_d.has("rig"):
		var rig: Dictionary = slots_d.rig if slots_d.rig is Dictionary else {}
		var n := int((item(String(rig.get("id", ""))).get("rig", {}) as Dictionary).get("pouches", 0))
		slots_d.erase("rig")
		if n > 0 and slots_d.get("armor") is Dictionary and not (slots_d.armor as Dictionary).has("pouches"):
			var pouches: Array = []
			for i in range(n):
				pouches.append("pouch_rifle")
			(slots_d.armor as Dictionary)["pouches"] = pouches
	for slot in t.get("slots", {}):
		var e: Variant = (t.slots as Dictionary)[slot]
		if not e is Dictionary:
			continue
		canon_entry(e as Dictionary)
		var plates: Variant = (e as Dictionary).get("plates", null)
		if plates is Dictionary:
			for g in plates:
				if (plates as Dictionary)[g] is String:
					(plates as Dictionary)[g] = WeaponDb.canonical(String((plates as Dictionary)[g]))
	for pair: Variant in t.get("backpack", []):
		if pair is Array and (pair as Array).size() > 0 and (pair as Array)[0] is String:
			(pair as Array)[0] = WeaponDb.canonical(String((pair as Array)[0]))

