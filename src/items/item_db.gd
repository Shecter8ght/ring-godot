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
		w += weight(String(mag.get("ammo", ""))) * int(mag.get("rounds", 0))
	if e.has("rounds"):
		w += weight(String(e.get("ammo", ""))) * int(e.rounds)
	if int(e.get("chamber", 0)) > 0:
		w += weight(String(e.get("chamber_ammo", mag.get("ammo", "")))) * int(e.chamber)
	for s in e.get("plates", {}):
		w += weight(String(e.plates[s].id))
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
	# найдено в рейде: сдать Михалычу по заданию можно только такое (купленное — нет)
	for e in out:
		e["fir"] = true
	return out


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


static func _merge(list: Array, id: String, n: int) -> void:
	for it in list:
		if String(it.id) == id and not it.has("dur"):
			it.n = int(it.n) + n
			return
	list.append({"id": id, "n": n})


static func equip(id: String) -> Dictionary:
	return item(id).get("equip", {})


## Слоты оружия: любое оружие встаёт в любой из них (два пистолета, винтовка и дробовик — как угодно).
const WEAPON_SLOTS := ["primary", "secondary"]


## Подходит ли предмет в слот снаряжения.
static func slot_ok(id: String, slot: String) -> bool:
	var s := String(equip(id).get("slot", ""))
	if s == "":
		return false
	if equip(id).has("weapon"):
		return slot in WEAPON_SLOTS
	return s == slot


## Куда надеть предмет: want — слот, на который бросили (если подходит); оружие без указания —
## в свой слот по данным, если он занят, а другой свободен — в другой.
static func pick_slot(id: String, eq: Dictionary, want: String = "") -> String:
	if want != "" and slot_ok(id, want):
		return want
	var s := String(equip(id).get("slot", ""))
	if s != "" and equip(id).has("weapon") and eq.has(s):
		for o in WEAPON_SLOTS:
			if not eq.has(o):
				return String(o)
	return s


## Новый экземпляр предмета (id по алиасам): оружие — новое, с пустым штатным магазином;
## магазин — пустой; броня, шлем, плита — полная прочность.
static func make(id: String, n: int) -> Dictionary:
	id = WeaponDb.canonical(id)
	var e := {"id": id, "n": n}
	if WeaponDb.is_weapon(id):
		e.n = 1
		var w := WeaponDb.weapon(id)
		e["dur"] = 100.0
		e["mods"] = {}
		e["mag"] = {"id": "" if w.has("internal_mag") else WeaponDb.default_mag(id), "ammo": WeaponDb.default_ammo(String(w.caliber)), "rounds": 0}
		e["sight"] = "primary"
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
	# найденное в рейде с купленным в одну стопку не ложится
	return String(a.id) == String(b.id) and not _stateful(a) and not _stateful(b) and bool(a.get("fir", false)) == bool(b.get("fir", false))


## Экземпляр со своим состоянием — всегда поштучно.
static func _stateful(e: Dictionary) -> bool:
	return e.has("dur") or e.has("mods") or e.has("mag") or e.has("rounds") or e.has("plates")


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
	if WeaponDb.is_weapon(id):
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
	if WeaponDb.is_weapon(id):
		t += " · %d%%" % int(entry.get("dur", 100))
		var mag: Dictionary = entry.get("mag", {}) if entry.get("mag") is Dictionary else {}
		if not mag.is_empty():
			t += " · маг. %d" % WeaponDb.capacity(entry)
		if not (entry.get("mods", {}) as Dictionary).is_empty():
			t += " · обвес: %d" % (entry.mods as Dictionary).size()
		return t
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
	var mx := max_dur(id)
	if entry.has("dur") and mx > 0.0:
		v *= clampf(float(entry.dur) / mx, 0.2, 1.0)
	for slot in entry.get("mods", {}):
		v += float(value(WeaponDb.mod_id(entry.mods[slot])))
	var mag: Dictionary = entry.get("mag", {}) if entry.get("mag") is Dictionary else {}
	if not mag.is_empty():
		if String(mag.get("id", "")) != "":
			v += float(value(String(mag.id)))
		v += float(value(String(mag.get("ammo", "")))) * int(mag.get("rounds", 0))
	if entry.has("rounds"):
		v += float(value(String(entry.get("ammo", "")))) * int(entry.rounds)
	if int(entry.get("chamber", 0)) > 0:
		v += float(value(String(entry.get("chamber_ammo", mag.get("ammo", ""))))) * int(entry.chamber)
	for s in entry.get("plates", {}):
		var p: Dictionary = entry.plates[s]
		v += float(value(String(p.id))) * clampf(float(p.dur) / maxf(1.0, max_dur(String(p.id))), 0.2, 1.0)
	return int(v)


static func value_of(list: Array) -> int:
	var v := 0
	for it in list:
		v += entry_value(it)
	return v
