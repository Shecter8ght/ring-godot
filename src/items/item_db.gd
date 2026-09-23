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


static func _ensure() -> void:
	if not _items.is_empty():
		return
	_items = (JSON.parse_string(FileAccess.get_file_as_string(ITEMS_PATH)) as Dictionary).get("items", {})
	_loot = JSON.parse_string(FileAccess.get_file_as_string(LOOT_PATH)) as Dictionary


static func item(id: String) -> Dictionary:
	_ensure()
	return _items.get(id, {"name": id, "cat": "misc", "cells": 1, "value": 0, "stack": 1})


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
				if id != "nothing":
					var n := rng.randi_range(int(e[2][0]), int(e[2][1]))
					if equip(id).has("durability"):
						# броня из лута — отдельными экземплярами, с изношенной прочностью
						for k in range(n):
							var one := make(id, 1)
							one.dur = roundf(float(one.dur) * rng.randf_range(0.4, 1.0))
							out.append(one)
					else:
						_merge(out, id, n)
				break
	return out


static func _merge(list: Array, id: String, n: int) -> void:
	for it in list:
		if String(it.id) == id and not it.has("dur"):
			it.n = int(it.n) + n
			return
	list.append({"id": id, "n": n})


static func equip(id: String) -> Dictionary:
	return item(id).get("equip", {})


## Новый экземпляр предмета: у брони — полная прочность ("dur").
static func make(id: String, n: int) -> Dictionary:
	var e := {"id": id, "n": n}
	var eq := equip(id)
	if eq.has("durability"):
		e["dur"] = float(eq.durability)
	return e


## Предмет с состоянием (прочность, обвесы) не складывается с другими такими же.
static func can_merge(a: Dictionary, b: Dictionary) -> bool:
	return String(a.id) == String(b.id) and not a.has("dur") and not b.has("dur") and not a.has("mods") and not b.has("mods")


## Экземпляр со своим состоянием — всегда поштучно.
static func _stateful(e: Dictionary) -> bool:
	return e.has("dur") or e.has("mods")


static func mod_spec(id: String) -> Dictionary:
	return item(id).get("mod", {})


## Обвес mod подходит на оружие weapon_item (id предмета) в свой слот.
static func mod_fits(mod: String, weapon_item: String) -> bool:
	var ms := mod_spec(mod)
	var eq := equip(weapon_item)
	return not ms.is_empty() and String(eq.get("weapon", "")) in ms.get("fits", []) and String(ms.slot) in eq.get("slots", [])


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
		for key in ["x", "y", "r"]:
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


## Название с состоянием: «Бронежилет лёгкий (кл. 2) · 32/50».
static func label(entry: Dictionary) -> String:
	var t := item_name(String(entry.id))
	if entry.has("dur"):
		t += " · %d/%d" % [int(entry.dur), int(equip(String(entry.id)).get("durability", 0))]
	if entry.has("mods") and not (entry.mods as Dictionary).is_empty():
		t += " · обвесов: %d" % (entry.mods as Dictionary).size()
	return t


## Цена с учётом износа брони.
static func entry_value(entry: Dictionary) -> int:
	var v := float(value(String(entry.id))) * int(entry.n)
	if entry.has("dur"):
		v *= clampf(float(entry.dur) / maxf(1.0, float(equip(String(entry.id)).get("durability", 1))), 0.2, 1.0)
	for slot in entry.get("mods", {}):
		v += float(value(String(entry.mods[slot])))
	return int(v)


static func value_of(list: Array) -> int:
	var v := 0
	for it in list:
		v += entry_value(it)
	return v
