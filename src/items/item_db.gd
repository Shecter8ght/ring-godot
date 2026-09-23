@tool
class_name ItemDb
extends RefCounted
## Справочник предметов (data/items.json) и лута (data/loot.json). Читается один раз.
## Предмет в инвентаре/контейнере — словарь {"id": String, "n": int}.

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
	return int(item(id).cells)


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


## Предмет с состоянием (прочность) не складывается с другими такими же.
static func can_merge(a: Dictionary, b: Dictionary) -> bool:
	return String(a.id) == String(b.id) and not a.has("dur") and not b.has("dur")


## Сколько ячеек займёт список предметов (стопки по stack).
static func cells_of(list: Array) -> int:
	var c := 0
	for it in list:
		c += cells(String(it.id)) * int(ceil(float(it.n) / float(stack(String(it.id)))))
	return c


## Сколько штук entry влезет в список при вместимости cap ячеек (cap < 0 — без предела).
static func room_in(list: Array, entry: Dictionary, cap: int) -> int:
	var id := String(entry.id)
	if cap < 0:
		return int(entry.n)
	var free_cells := cap - cells_of(list)
	if entry.has("dur"):
		return 1 if free_cells >= cells(id) else 0
	var st := stack(id)
	var have := 0
	for it in list:
		if can_merge(it, entry):
			have = int(it.n)
	var free_in_stack := (st - have % st) % st if have > 0 else 0
	return free_in_stack + int(floor(float(free_cells) / float(cells(id)))) * st


## Кладёт в list сколько влезет из entry; возвращает, сколько положил (list меняется).
static func add_to(list: Array, entry: Dictionary, cap: int) -> int:
	var k := mini(int(entry.n), room_in(list, entry, cap))
	if k <= 0:
		return 0
	for it in list:
		if can_merge(it, entry):
			it.n = int(it.n) + k
			return k
	var e := entry.duplicate(true)
	e.n = k
	list.append(e)
	return k


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
	return t


## Цена с учётом износа брони.
static func entry_value(entry: Dictionary) -> int:
	var v := float(value(String(entry.id))) * int(entry.n)
	if entry.has("dur"):
		v *= clampf(float(entry.dur) / maxf(1.0, float(equip(String(entry.id)).get("durability", 1))), 0.2, 1.0)
	return int(v)


static func value_of(list: Array) -> int:
	var v := 0
	for it in list:
		v += entry_value(it)
	return v
