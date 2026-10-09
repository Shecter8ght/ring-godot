class_name BuildPlan
extends RefCounted
## Черновик сборки из конструктора (WeaponBuilder) → одна проверенная операция. Черновик — обвес
## mods, где у каждой записи есть "src" — откуда деталь:
##   {"from": "weapon", "key": <ключ на этом оружии до правки>}   — уже стояла (могла переехать);
##   {"from": <список>, "idx": <запись>, "sub": <ключ внутри неё>} — из тайника/рюкзака (sub — деталь,
##                                                                   стоявшая на взятом переходнике);
##   {"from": "shop"}                                              — купить у торговца.
## Магазин — mag: {"from": "weapon"} (тот же), {"from": <список>, "idx"} (другой), {"from": "none"}.
## resolve() проверяет всё разом (точки, пазы, соседи, наличие, повторы, правила места) и считает,
## что взять, что купить и что вернуть. Применяют Profile.apply_build (убежище) и Raid (хост).

## Списки, из которых конструктор берёт детали в убежище и в рейде.
const HIDEOUT_LISTS := ["stash", "backpack"]
const RAID_LISTS := ["backpack"]


## Итог: {entry: новая запись оружия, take: [[список, индекс]], buy: [id], returned: [предмет],
## why: "" — можно, иначе причина}. lists — {имя: Array записей}; rules — {shop: bool, lists: [],
## locked: [точки оружия, которые здесь менять нельзя, — приклад в рейде]}.
static func resolve(weapon: Dictionary, draft: Dictionary, draft_mag: Dictionary, lists: Dictionary, rules: Dictionary) -> Dictionary:
	var out: Dictionary = {"entry": {}, "take": [], "buy": [], "returned": [], "why": ""}
	var wid: String = String(weapon.get("id", ""))
	var old_mods: Dictionary = weapon.get("mods", {})
	var used_weapon: Dictionary = {}
	var used_take: Dictionary = {}
	var final_mods: Dictionary = {}
	var allowed: Array = rules.get("lists", HIDEOUT_LISTS)
	# 1. откуда каждая деталь и что в ней на самом деле
	for key: String in WeaponBuild.sorted_keys(draft):
		var rec: Dictionary = draft[key] if draft[key] is Dictionary else {"id": String(draft[key])}
		var src: Dictionary = rec.get("src", {"from": "weapon", "key": key})
		var att: String = WeaponDb.mod_id(rec)
		var real: Dictionary = {}
		match String(src.get("from", "")):
			"weapon":
				var ok: String = String(src.get("key", key))
				if not old_mods.has(ok) or WeaponDb.mod_id(old_mods[ok]) != att or used_weapon.has(ok):
					return _fail(out, "деталь уже не на оружии")
				used_weapon[ok] = true
				real = WeaponCondition.mod_entry(old_mods[ok])
			"shop":
				if not bool(rules.get("shop", false)):
					return _fail(out, "торговца здесь нет")
				(out.buy as Array).append(att)
				real = {"id": att, "dur": float(Balance.CONDITION.full)}
			_:
				var list_name: String = String(src.from)
				var idx: int = int(src.get("idx", -1))
				var sub: String = String(src.get("sub", ""))
				var list: Array = lists.get(list_name, [])
				if not list_name in allowed or idx < 0 or idx >= list.size():
					return _fail(out, "детали нет в вещах")
				var item: Dictionary = list[idx]
				if sub == "":
					if WeaponDb.canonical(String(item.get("id", ""))) != att:
						return _fail(out, "детали нет в вещах")
					real = WeaponCondition.mod_entry(item)
				else:
					var carried: Dictionary = item.get("mods", {})
					if not carried.has(sub) or WeaponDb.mod_id(carried[sub]) != att:
						return _fail(out, "детали нет в вещах")
					real = WeaponCondition.mod_entry(carried[sub])
				var tk: String = "%s:%d:%s" % [list_name, idx, sub]
				if used_take.has(tk):
					return _fail(out, "одна деталь — в двух местах")
				used_take[tk] = true
				var whole: String = "%s:%d" % [list_name, idx]
				if not used_take.has(whole):
					used_take[whole] = true
					(out.take as Array).append([list_name, idx])
		# ресурс и включённость фонаря/лазера — от самой детали; место — из черновика
		for drop: String in ["x", "y", "r", "n", "rev", "mods", "uid", "src", "slot", "flip", "angle"]:
			real.erase(drop)
		for place: String in ["slot", "flip", "angle", "light", "laser"]:
			if rec.has(place):
				real[place] = rec[place]
		final_mods[key] = real
	# 2. точки, которые здесь менять нельзя
	for locked: Variant in rules.get("locked", []):
		var before: Array = _branch(old_mods, String(locked))
		var after: Array = _branch(final_mods, String(locked))
		if before != after:
			return _fail(out, "%s — только на верстаке в убежище" % String(WeaponDb.MOUNT_NAMES.get(String(locked), locked)).to_lower())
	# 3. сборка целиком: каждая деталь — по порядку, от родителей к детям
	var probe: Dictionary = weapon.duplicate(true)
	probe["mods"] = {}
	for key: String in WeaponBuild.sorted_keys(final_mods):
		var why: String = WeaponBuild.block(probe, key, WeaponDb.mod_id(final_mods[key]), int((final_mods[key] as Dictionary).get("slot", -1)))
		if why != "":
			return _fail(out, "%s: %s" % [ItemDb.item_name(WeaponDb.mod_id(final_mods[key])), why])
		(probe.mods as Dictionary)[key] = final_mods[key]
	# 4. что вернётся: снятое с оружия (переходник — со всем снятым, что было на нём) и остатки взятых
	var returned: Array = _leftovers(old_mods, func(k: String) -> bool: return used_weapon.has(k))
	for t: Variant in out.take:
		var item2: Dictionary = (lists[String(t[0])] as Array)[int(t[1])]
		var prefix: String = "%s:%d:" % [String(t[0]), int(t[1])]
		returned.append_array(_leftovers(item2.get("mods", {}), func(k: String) -> bool: return used_take.has(prefix + k)))
	# 5. магазин
	var entry: Dictionary = probe
	var mag_from: String = String(draft_mag.get("from", "weapon"))
	var old_mag: Dictionary = weapon.get("mag", {}) if weapon.get("mag") is Dictionary else {}
	if mag_from != "weapon":
		var w: Dictionary = WeaponDb.weapon(wid)
		if w.has("internal_mag"):
			return _fail(out, "магазин встроенный")
		if String(old_mag.get("id", "")) != "":
			returned.append(WeaponDb.make_mag(String(old_mag.id), String(old_mag.get("ammo", "")), int(old_mag.get("rounds", 0))))
		if mag_from == "none":
			entry["mag"] = {"id": "", "ammo": String(old_mag.get("ammo", "")), "rounds": 0}
		else:
			var mlist: Array = lists.get(mag_from, [])
			var mi: int = int(draft_mag.get("idx", -1))
			if not mag_from in allowed or mi < 0 or mi >= mlist.size():
				return _fail(out, "магазина нет в вещах")
			var mag_item: Dictionary = mlist[mi]
			if not WeaponDb.mag_fits(wid, String(mag_item.get("id", ""))):
				return _fail(out, "магазин не подходит")
			if used_take.has("%s:%d" % [mag_from, mi]):
				return _fail(out, "одна вещь — в двух местах")
			(out.take as Array).append([mag_from, mi])
			entry["mag"] = {"id": WeaponDb.canonical(String(mag_item.id)), "ammo": String(mag_item.get("ammo", "")), "rounds": int(mag_item.get("rounds", 0))}
	# выбранный прицел остался на месте?
	if not String(entry.get("sight", "primary")) in WeaponStats.sights_of(entry):
		entry["sight"] = "primary"
	entry["rev"] = int(entry.get("rev", 0)) + 1
	out.entry = entry
	out.returned = returned
	return out


## Детали дерева mods, которые не пошли в сборку (used — пошла ли), — предметами: верхняя из
## неиспользованных уносит с собой неиспользованных потомков (кронштейн с прицелом).
static func _leftovers(mods: Dictionary, used: Callable) -> Array:
	var out: Array = []
	for k: String in WeaponBuild.sorted_keys(mods):
		if used.call(k):
			continue
		var parent: String = WeaponBuild.parent_key(k)
		if parent != "" and mods.has(parent) and not used.call(parent):
			continue
		var item: Dictionary = WeaponCondition.mod_entry(mods[k])
		for drop: String in ["slot", "flip", "angle"]:
			item.erase(drop)
		var carried: Dictionary = {}
		for d: String in WeaponBuild.subtree(mods, k):
			if d != k and _free_chain(mods, used, k, d):
				carried[d.substr(k.length() + 1)] = (mods[d] as Dictionary).duplicate(true) if mods[d] is Dictionary else {"id": String(mods[d])}
		if not carried.is_empty():
			item["mods"] = carried
		out.append(item)
	return out


## Сама деталь d и все её предки до top не пошли в сборку (тогда d уезжает вместе с top).
static func _free_chain(mods: Dictionary, used: Callable, top: String, d: String) -> bool:
	var k: String = d
	while k != top and k != "":
		if used.call(k) or not mods.has(k):
			return false
		k = WeaponBuild.parent_key(k)
	return true


## Ветка точки оружия для сравнения: [[ключ, id], …] по порядку.
static func _branch(mods: Dictionary, mount: String) -> Array:
	var out: Array = []
	for k: String in WeaponBuild.sorted_keys(mods):
		if WeaponBuild.top_mount(k) == mount:
			out.append([k, WeaponDb.mod_id(mods[k])])
	return out


static func _fail(out: Dictionary, why: String) -> Dictionary:
	out.why = why
	return out


## Черновик из записи оружия: каждая деталь помечена «стоит на этом оружии».
static func draft_of(weapon: Dictionary) -> Dictionary:
	var out: Dictionary = {}
	var mods: Dictionary = weapon.get("mods", {})
	for k: Variant in mods:
		var rec: Dictionary = (mods[k] as Dictionary).duplicate(true) if mods[k] is Dictionary else {"id": String(mods[k])}
		rec["src"] = {"from": "weapon", "key": String(k)}
		out[String(k)] = rec
	return out


## Сумма покупки у торговца.
static func cost(buy: Array) -> int:
	var total: int = 0
	for id: Variant in buy:
		total += Profile.buy_price(String(id))
	return total


## Черновик без пометок — для модели и характеристик.
static func clean(draft: Dictionary) -> Dictionary:
	var out: Dictionary = {}
	for k: Variant in draft:
		var rec: Dictionary = (draft[k] as Dictionary).duplicate()
		rec.erase("src")
		out[k] = rec
	return out
