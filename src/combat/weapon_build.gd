class_name WeaponBuild
extends RefCounted
## Сборка экземпляра оружия — дерево обвеса в плоском словаре entry.mods. Ключ — путь к точке:
##   "optic_primary"          — точка самого оружия (data/weapons.json → weapons.*.mounts);
##   "optic_primary#2"        — второе устройство на той же планке;
##   "optic_primary#2/rail"   — точка, которую дал установленный переходник (provides обвеса).
## Запись обвеса: {id, dur[, slot, flip, angle, light, laser]}. slot — паз: задний край зажима
## отстоит от заднего края планки на slot × SLOT_M; без slot устройство стоит там, где его ставили
## раньше (сокет данных). flip — кронштейн на другую сторону, angle — угол регулируемого крепления.
## Плоский словарь оставляет прежним всё, что перебирает обвес (вес, цена, ресурс, сеть), а снятый
## переходник уносит своё поддерево с собой: у предмета-кронштейна в рюкзаке есть свои mods.

## Шаг паза планки, м (решение владельца — 20 мм вместо 10 у настоящей Пикатинни).
const SLOT_M := 0.02
const SEP := "/"
const MULTI := "#"
## Больше трёх переходников подряд не собираем (проставка на проставке на кронштейне…):
## переходник — не глубже MAX_DEPTH − 1, устройство на последнем — на глубине MAX_DEPTH.
const MAX_DEPTH := 3
## Длина зажима, если у обвеса не задана (clamp_m), м.
const DEFAULT_CLAMP := 0.03
const POINT_NAMES := {"rail": "планка переходника", "light": "кольцо фонаря"}


# ---------------------------------------------------------------- ключи

static func parent_key(key: String) -> String:
	var i: int = key.rfind(SEP)
	return key.substr(0, i) if i >= 0 else ""


static func leaf(key: String) -> String:
	var i: int = key.rfind(SEP)
	return key.substr(i + 1) if i >= 0 else key


## Имя точки без номера устройства на планке: "optic_primary#2" → "optic_primary".
static func base_of(key: String) -> String:
	var l: String = leaf(key)
	var i: int = l.find(MULTI)
	return l.substr(0, i) if i >= 0 else l


## Точка оружия, от которой растёт ветка.
static func top_mount(key: String) -> String:
	var first: String = key.get_slice(SEP, 0)
	var i: int = first.find(MULTI)
	return first.substr(0, i) if i >= 0 else first


static func depth(key: String) -> int:
	return key.count(SEP)


## Ключ точки без номера: тот же родитель + имя точки.
static func point_key(key: String) -> String:
	var p: String = parent_key(key)
	return (p + SEP if p != "" else "") + base_of(key)


## Имя узла сцены по ключу (в именах узлов «/» и «#» нельзя).
static func node_name(key: String) -> String:
	return key.replace(SEP, "__").replace(MULTI, "_n")


## Ключ и все его потомки.
static func subtree(mods: Dictionary, key: String) -> Array[String]:
	var out: Array[String] = []
	for k: Variant in mods:
		var s: String = String(k)
		if s == key or s.begins_with(key + SEP):
			out.append(s)
	return out


## Сначала родители, потом дети (порядок установки на модель).
static func sorted_keys(mods: Dictionary) -> Array[String]:
	var out: Array[String] = []
	for k: Variant in mods:
		out.append(String(k))
	out.sort_custom(func(a: String, b: String) -> bool:
		return depth(a) < depth(b) if depth(a) != depth(b) else a < b)
	return out


## Устройства, стоящие на той же точке (та же планка), кроме самого key.
static func siblings(mods: Dictionary, key: String) -> Array[String]:
	var out: Array[String] = []
	var pk: String = point_key(key)
	for k: Variant in mods:
		var s: String = String(k)
		if s != key and point_key(s) == pk:
			out.append(s)
	return out


# ---------------------------------------------------------------- точки и планки

static func model_of(weapon_id: String) -> String:
	return String(WeaponDb.weapon(weapon_id).get("model", ""))


## Точка key на оружии entry_id при обвесе mods: геометрия (geo) + интерфейс iface.
## {} — такой точки нет (у оружия нет, нет родителя-переходника или он её не даёт).
static func point(entry_id: String, mods: Dictionary, key: String) -> Dictionary:
	var base: String = base_of(key)
	var parent: String = parent_key(key)
	var iface: String = ""
	if parent == "":
		var mounts: Dictionary = WeaponDb.mounts_of(entry_id)
		if not mounts.has(base):
			return {}
		iface = String(mounts[base])
	else:
		if not mods.has(parent):
			return {}
		var spec: Dictionary = (WeaponDb.attachment(WeaponDb.mod_id(mods[parent])).get("provides", {}) as Dictionary).get(base, {})
		iface = String(spec.get("if", ""))
		if iface == "SAME":
			iface = String(point(entry_id, mods, parent).get("iface", ""))
	var g: Dictionary = geo(model_of(entry_id), mods, key)
	if g.is_empty():
		return {}
	g["iface"] = iface
	return g


## Геометрия точки по модели: {rail: [от, до] вдоль оси точки (пусто — точка без планки), z — где
## стоит устройство без паза, pos, roll/flip/angle/step — у точек переходника}. Ось точки у точек
## оружия — оси модели (z — абсолютный); у точки переходника начало в pos его рамки после крена.
static func geo(model_key: String, mods: Dictionary, key: String) -> Dictionary:
	var base: String = base_of(key)
	var parent: String = parent_key(key)
	if parent == "":
		var sk: Dictionary = WeaponMods.socket(model_key, base)
		var out: Dictionary = {"rail": [], "z": 0.0, "pos": Vector3.ZERO}
		if sk.is_empty():
			return out
		out.pos = sk.pos
		out.z = (sk.pos as Vector3).z
		if sk.has("rail_z"):
			var r: Array = sk.rail_z
			out.rail = [float(r[0]), float(r[1])]
		elif sk.has("rail_len"):
			var half: float = float(sk.rail_len) * 0.5
			out.rail = [out.z - half, out.z + half]
		# короткая планка (overhang в сокете): третьим элементом — устройство длиннее неё встаёт посередине
		if bool(sk.get("overhang", false)) and not (out.rail as Array).is_empty():
			(out.rail as Array).append(true)
		return out
	if not mods.has(parent) or depth(key) > MAX_DEPTH:
		return {}
	var provides: Dictionary = WeaponDb.attachment(WeaponDb.mod_id(mods[parent])).get("provides", {})
	if not provides.has(base):
		return {}
	var spec: Dictionary = provides[base]
	var p: Array = spec.get("pos", [0, 0, 0])
	var out2: Dictionary = {"rail": [], "z": 0.0, "pos": Vector3(float(p[0]), float(p[1]), float(p[2])),
		"roll": float(spec.get("roll", 0.0)), "flip": bool(spec.get("flip", false))}
	if spec.has("rail_z"):
		var r2: Array = spec.rail_z
		out2.rail = [float(r2[0]), float(r2[1])]
	if spec.has("angle"):
		out2["angle"] = spec.angle
		out2["step"] = float(spec.get("step", 15.0))
	return out2


static func is_rail(pt: Dictionary) -> bool:
	return not (pt.get("rail", []) as Array).is_empty()


static func clamp_of(att_id: String) -> float:
	return float(WeaponDb.attachment(att_id).get("clamp_m", DEFAULT_CLAMP))


## Короткая планка, на которую ставят любое устройство (сокет с overhang, владелец 2026-11-01: боковые планки
## ГРАНЬ-15 по 30 мм): зажиму хватает пары пазов, корпус длиннее планки свисает с обоих концов — одно место посередине.
static func overhangs(rail: Array, clamp: float) -> bool:
	return rail.size() > 2 and bool(rail[2]) and float(rail[1]) - float(rail[0]) < clamp - 0.0001


## Середина зажима устройства в пазу slot планки rail.
static func slot_z(rail: Array, clamp: float, slot: int) -> float:
	if overhangs(rail, clamp):
		return (float(rail[0]) + float(rail[1])) * 0.5
	return float(rail[0]) + clamp * 0.5 + float(slot) * SLOT_M


## Сколько пазов у устройства длиной clamp на планке rail (0 — не помещается).
static func slot_count(rail: Array, clamp: float) -> int:
	if overhangs(rail, clamp):
		return 1
	var room: float = float(rail[1]) - float(rail[0]) - clamp
	return int(floor(room / SLOT_M + 0.0001)) + 1 if room >= -0.0001 else 0


## Ближайший к z паз.
static func nearest_slot(rail: Array, clamp: float, z: float) -> int:
	var n: int = slot_count(rail, clamp)
	if n <= 0:
		return 0
	return clampi(roundi((z - float(rail[0]) - clamp * 0.5) / SLOT_M), 0, n - 1)


## Где вдоль оси точки стоит середина зажима устройства key (по пазу или как раньше).
static func placed_z(model_key: String, mods: Dictionary, key: String) -> float:
	var pt: Dictionary = geo(model_key, mods, key)
	if pt.is_empty():
		return 0.0
	var rec: Variant = mods.get(key, {})
	if is_rail(pt) and rec is Dictionary and (rec as Dictionary).has("slot"):
		return slot_z(pt.rail, clamp_of(WeaponDb.mod_id(rec)), int((rec as Dictionary).slot))
	return float(pt.z)


## Отрезок, который зажим устройства занимает на планке.
static func span(model_key: String, mods: Dictionary, key: String) -> Vector2:
	var z: float = placed_z(model_key, mods, key)
	var att: String = WeaponDb.mod_id(mods.get(key, ""))
	var footprint: Array = WeaponDb.attachment(att).get("footprint_m", [])
	if footprint.size() == 2:
		return Vector2(z + float(footprint[0]), z + float(footprint[1]))
	var c: float = clamp_of(att)
	return Vector2(z - c * 0.5, z + c * 0.5)


## Крен точки переходника с учётом стороны и регулировки, град (у точек оружия — 0).
static func point_roll(model_key: String, mods: Dictionary, key: String) -> float:
	var pt: Dictionary = geo(model_key, mods, key)
	var parent: String = parent_key(key)
	if parent == "" or pt.is_empty():
		return 0.0
	var rec: Dictionary = WeaponCondition.mod_entry(mods.get(parent, {}))
	var roll: float = float(pt.get("roll", 0.0))
	if pt.has("angle"):
		var lim: Array = pt.angle
		roll = clampf(float(rec.get("angle", roll)), float(lim[0]), float(lim[1]))
	if bool(pt.get("flip", false)) and bool(rec.get("flip", false)):
		roll = -roll
	return roll


# ---------------------------------------------------------------- проверка

## Почему обвес att нельзя поставить в key ("" — можно). slot < 0 — паз записи (или как раньше).
## Проверки: точка есть, интерфейс подходит, зажим помещается на планке, не налезает на соседей,
## старые запреты blocks. Перекрытие линии прицеливания — отдельное предупреждение.
static func block(entry: Dictionary, key: String, att: String, slot: int = -1) -> String:
	var a: Dictionary = WeaponDb.attachment(att)
	if a.is_empty():
		return "это не обвес"
	var id: String = String(entry.get("id", ""))
	if String(WeaponDb.weapon(id).get("class", "")) == "PISTOL" and (att == DozorGear.MOUNT or DozorGear.is_flashlight(att)):
		return "с пистолетом фонарь держат в левой руке (T)"
	var model_key: String = model_of(id)
	slot = resolve_slot(entry, key, att, slot)
	# заменяемое устройство и всё, что на нём, в проверке не участвует
	var mods: Dictionary = without(entry.get("mods", {}), key)
	var rec: Dictionary = {"id": att}
	var old: Variant = (entry.get("mods", {}) as Dictionary).get(key, {})
	if old is Dictionary and WeaponDb.mod_id(old) == att:
		rec = (old as Dictionary).duplicate(true)
	if slot >= 0:
		rec["slot"] = slot
	mods[key] = rec
	var pt: Dictionary = point(id, mods, key)
	if pt.is_empty():
		return "на этом оружии нет такой точки" if parent_key(key) == "" else "переходник не даёт такой точки"
	if leaf(key).contains(MULTI) and not is_rail(pt):
		return "сюда помещается одно устройство"
	if not String(pt.iface) in a.get("fits", []):
		return "не подходит крепление (%s)" % String(pt.iface)
	if depth(key) >= MAX_DEPTH and not (a.get("provides", {}) as Dictionary).is_empty():
		return "слишком длинная цепочка переходников"
	if is_rail(pt):
		var c: float = clamp_of(att)
		if slot_count(pt.rail, c) <= 0:
			return "не хватает длины планки"
		var mine: Vector2 = span(model_key, mods, key)
		var z: float = placed_z(model_key, mods, key)
		if not overhangs(pt.rail, c) and (z - c * 0.5 < float(pt.rail[0]) - 0.0001 or z + c * 0.5 > float(pt.rail[1]) + 0.0001):
			return "не помещается на планке"
		for other: String in siblings(mods, key):
			var o: Vector2 = span(model_key, mods, other)
			if mine.x < o.y - 0.0001 and o.x < mine.y - 0.0001:
				return "занято: " + ItemDb.item_name(WeaponDb.mod_id(mods[other]))
	for other: Variant in mods:
		var ok: String = String(other)
		if ok == key:
			continue
		var oa: Dictionary = WeaponDb.attachment(WeaponDb.mod_id(mods[other]))
		if key in oa.get("blocks", []):
			return "мешает: " + ItemDb.item_name(WeaponDb.mod_id(mods[other]))
		if ok in a.get("blocks", []):
			return "закроет: " + ItemDb.item_name(WeaponDb.mod_id(mods[other]))
	# Пульт занимает планку, хотя второго предмета в mods нет.
	return String(AttachmentRemote.resolve(id, mods).why)


## Подсказка о возможном перекрытии, а не запрет установки (владелец, 2026-10-22).
## Окончательный обзор игрок проверяет из глаза; низкие кронштейны не учитываем.
static func view_block(id: String, mods: Dictionary, key: String) -> String:
	var pt: Dictionary = point(id, mods, key)
	if String(pt.get("iface", "")) != "RAIL_TOP":
		return ""
	var me: String = WeaponDb.mod_id(mods[key])
	var mine: Vector2 = span(model_of(id), mods, key)
	var others: Array[String] = siblings(mods, key)
	if depth(key) == 0:
		# соседняя верхняя планка оружия (коробка ↔ цевьё): оси общие, высота почти та же
		for k: Variant in mods:
			var ok: String = String(k)
			if depth(ok) == 0 and point_key(ok) != point_key(key) and String(point(id, mods, ok).get("iface", "")) == "RAIL_TOP":
				others.append(ok)
	for other: String in others:
		var oid: String = WeaponDb.mod_id(mods[other])
		var o: Vector2 = span(model_of(id), mods, other)
		if WeaponDb.is_optic(me) and o.x >= mine.y - 0.0001 and not bool(WeaponDb.attachment(oid).get("low", false)):
			return "мешает прицелу: " + ItemDb.item_name(oid)
		if WeaponDb.is_optic(oid) and mine.x >= o.y - 0.0001 and not bool(WeaponDb.attachment(me).get("low", false)):
			return "закроет прицел: " + ItemDb.item_name(oid)
	return ""


## Предупреждение об обзоре при примерке; установка от него не зависит.
static func sight_warning(entry: Dictionary, key: String, att: String, slot: int = -1) -> String:
	var mods: Dictionary = without(entry.get("mods", {}), key)
	var rec: Dictionary = {"id": att}
	slot = resolve_slot(entry, key, att, slot)
	if slot >= 0:
		rec["slot"] = slot
	mods[key] = rec
	var why: String = view_block(String(entry.get("id", "")), mods, key)
	return "Возможно перекрытие обзора: " + why + ". Установка разрешена — проверь вид из глаза." if why != "" else ""


static func sight_warnings(entry: Dictionary) -> Array[String]:
	var out: Array[String] = []
	var mods: Dictionary = entry.get("mods", {})
	for key: String in sorted_keys(mods):
		var warning: String = sight_warning(entry, key, WeaponDb.mod_id(mods[key]))
		if warning != "" and not warning in out:
			out.append(warning)
	return out


## Паз, если не задан: у заменяемой записи — её паз; иначе штатное место или ближайший паз.
static func resolve_slot(entry: Dictionary, key: String, att: String, slot: int) -> int:
	if slot >= 0:
		return slot
	var mods: Dictionary = entry.get("mods", {})
	var old: Variant = mods.get(key)
	if old is Dictionary and (old as Dictionary).has("slot"):
		return int((old as Dictionary).slot)
	var probe: Dictionary = without(mods, key)
	probe[key] = {"id": att}
	var g: Dictionary = geo(model_of(String(entry.get("id", ""))), probe, key)
	if g.is_empty() or not is_rail(g):
		return -1
	var c: float = clamp_of(att)
	var z: float = float(g.z)
	if z - c * 0.5 >= float(g.rail[0]) - 0.0001 and z + c * 0.5 <= float(g.rail[1]) + 0.0001:
		return -1
	return nearest_slot(g.rail, c, z)


## Копия mods без key и его поддерева.
static func without(mods: Dictionary, key: String) -> Dictionary:
	var out: Dictionary = mods.duplicate(true)
	for k: String in subtree(mods, key):
		out.erase(k)
	return out


## Все допустимые пазы обвеса att в точке key (у точки без планки — [-1], если встаёт).
static func valid_slots(entry: Dictionary, key: String, att: String) -> Array[int]:
	var out: Array[int] = []
	var pt: Dictionary = point(String(entry.id), without(entry.get("mods", {}), key).merged({key: {"id": att}}), key)
	if pt.is_empty():
		return out
	if not is_rail(pt):
		if block(entry, key, att) == "":
			out.append(-1)
		return out
	for s: int in range(slot_count(pt.rail, clamp_of(att))):
		if block(entry, key, att, s) == "":
			out.append(s)
	return out


# ---------------------------------------------------------------- куда ставить

## Точки, в которые обвес att может встать (свободные ключи и занятые — для замены), по порядку:
## точки оружия, затем точки переходников. На планке — ещё и следующий номер устройства.
static func candidate_keys(entry: Dictionary, att: String) -> Array[String]:
	var out: Array[String] = []
	var id: String = String(entry.get("id", ""))
	var mods: Dictionary = entry.get("mods", {})
	var a: Dictionary = WeaponDb.attachment(att)
	var points: Array[String] = []
	var mounts: Dictionary = WeaponDb.mounts_of(id)
	for m: String in WeaponDb.MOUNTS:
		if mounts.has(m):
			points.append(m)
	for m: Variant in mounts:
		if not String(m) in points:
			points.append(String(m))
	for k: String in sorted_keys(mods):
		var pa: Dictionary = WeaponDb.attachment(WeaponDb.mod_id(mods[k]))
		for p: Variant in pa.get("provides", {}):
			points.append(k + SEP + String(p))
	for pk: String in points:
		var pt: Dictionary = point(id, mods, pk)
		if pt.is_empty() or not String(pt.iface) in a.get("fits", []):
			continue
		out.append(pk)
		if is_rail(pt):
			for n: int in range(2, 6):
				var extra: String = pk + MULTI + str(n)
				if mods.has(extra):
					out.append(extra)
				else:
					out.append(extra)
					break
	return out


## Первая свободная точка с допустимым пазом: {key, slot} (slot -1 — без паза); {} — некуда.
static func free_place(entry: Dictionary, att: String, prefer_z: float = INF) -> Dictionary:
	var mods: Dictionary = entry.get("mods", {})
	# сначала свободные точки, потом — ещё одно устройство на занятую планку
	var keys: Array[String] = candidate_keys(entry, att)
	var ordered: Array[String] = []
	for k: String in keys:
		if not leaf(k).contains(MULTI):
			ordered.append(k)
	for k2: String in keys:
		if leaf(k2).contains(MULTI):
			ordered.append(k2)
	for key: String in ordered:
		if mods.has(key):
			continue
		var slots: Array[int] = valid_slots(entry, key, att)
		if slots.is_empty():
			continue
		if slots[0] < 0:
			return {"key": key, "slot": -1}
		var pt: Dictionary = point(String(entry.id), mods.merged({key: {"id": att}}), key)
		var want: float = prefer_z if is_finite(prefer_z) else float(pt.z)
		var best: int = slots[0]
		for s: int in slots:
			if absf(slot_z(pt.rail, clamp_of(att), s) - want) < absf(slot_z(pt.rail, clamp_of(att), best) - want):
				best = s
		# точка оружия без паза в записи — на прежнем месте, если оно допустимо
		if parent_key(key) == "" and not key.contains(MULTI) and block(entry, key, att) == "":
			return {"key": key, "slot": -1}
		return {"key": key, "slot": best}
	return {}


## Место на планке rail_key (её ключ без номера): свободный номер устройства и паз ближе к prefer_z.
## {} — места нет.
static func rail_place(entry: Dictionary, rail_key: String, att: String, prefer_z: float) -> Dictionary:
	var mods: Dictionary = entry.get("mods", {})
	for n: int in range(1, 8):
		var key: String = rail_key if n == 1 else rail_key + MULTI + str(n)
		if mods.has(key):
			continue
		var slots: Array[int] = valid_slots(entry, key, att)
		if slots.is_empty() or slots[0] < 0:
			return {}
		var pt: Dictionary = point(String(entry.id), mods.merged({key: {"id": att}}), key)
		var best: int = slots[0]
		for s: int in slots:
			if absf(slot_z(pt.rail, clamp_of(att), s) - prefer_z) < absf(slot_z(pt.rail, clamp_of(att), best) - prefer_z):
				best = s
		return {"key": key, "slot": best}
	return {}


# ---------------------------------------------------------------- снять / поставить

## Снять key со всем, что на нём стоит: [запись без него, предмет]. Предмет-переходник уносит
## поддерево в своих mods (ключи — от него самого), паз остаётся на планке.
static func extract(entry: Dictionary, key: String) -> Array:
	var mods: Dictionary = entry.get("mods", {})
	if not mods.has(key):
		return [entry, {}]
	var e: Dictionary = entry.duplicate(true)
	var item: Dictionary = WeaponCondition.mod_entry(mods[key])
	for placement: String in ["slot", "flip", "angle", "remote"]:
		item.erase(placement)
	var carried: Dictionary = {}
	for k: String in subtree(mods, key):
		if k != key:
			carried[k.substr(key.length() + 1)] = (mods[k] as Dictionary).duplicate(true) if mods[k] is Dictionary else {"id": String(mods[k])}
	if not carried.is_empty():
		item["mods"] = carried
	e["mods"] = without(mods, key)
	_fix_sight(e)
	return [e, item]


## Поставить предмет item в key (slot -1 — паз из предмета нет: прежнее место / ближайший к нему).
## Замена на том же месте сохраняет паз. [новая запись, вытесненный предмет ({} — ничего), причина
## отказа ("" — встал), {ключ от переходника: запись} — что из его поддерева не встало].
static func insert(entry: Dictionary, key: String, item: Dictionary, slot: int = -1, flip: bool = false, angle: float = NAN) -> Array:
	var att: String = WeaponDb.canonical(String(item.get("id", "")))
	slot = resolve_slot(entry, key, att, slot)
	var why: String = block(entry, key, att, slot)
	if why != "":
		return [entry, {}, why, {}]
	var r: Array = extract(entry, key)
	var e: Dictionary = r[0]
	var mods: Dictionary = e.get("mods", {})
	var installed: Dictionary = WeaponCondition.mod_entry(item)
	installed["id"] = att
	for drop: String in ["x", "y", "r", "n", "mods", "rev"]:
		installed.erase(drop)
	if slot >= 0:
		installed["slot"] = slot
	if flip:
		installed["flip"] = true
	if not is_nan(angle):
		installed["angle"] = angle
	mods[key] = installed
	# переходник со своим поддеревом: ставим то, что встаёт; не встало — возвращается вместе с ним
	var carried: Dictionary = item.get("mods", {})
	var spilled: Dictionary = {}
	for ck: String in sorted_keys(carried):
		var full: String = key + SEP + ck
		var crec: Dictionary = WeaponCondition.mod_entry(carried[ck])
		for drop: String in ["x", "y", "r", "n", "rev"]:
			crec.erase(drop)
		var probe: Dictionary = e.duplicate(true)
		probe["mods"] = mods
		if parent_key(full) == key or mods.has(parent_key(full)):
			if block(probe, full, WeaponDb.mod_id(crec), int(crec.get("slot", -1))) == "":
				mods[full] = crec
				continue
		spilled[ck] = crec
	e["mods"] = mods
	var resolved: Dictionary = AttachmentRemote.resolve(String(e.id), mods)
	if String(resolved.why) != "":
		return [entry, {}, String(resolved.why), {}]
	e["mods"] = resolved.mods
	_bump(e)
	return [e, r[1], "", spilled]


static func _bump(e: Dictionary) -> void:
	e["rev"] = int(e.get("rev", 0)) + 1


## Выбранный прицел исчез вместе с веткой — вернуть основной.
static func _fix_sight(e: Dictionary) -> void:
	var s: String = String(e.get("sight", "primary"))
	if s != "primary" and not (e.get("mods", {}) as Dictionary).has(s):
		e["sight"] = "primary"


# ---------------------------------------------------------------- прицелы

## Ключ основного прицела: на верхней планке или над ней на проставке/удлинителе (без крена).
## На верхней планке прицела нет — основным становится прицел на планке над цевьём (дальней): через
## него и целятся, оптика работает с кратностью (раньше он считался «угловым» — без увеличения, с
## красной линзой-заглушкой). "" — основного прицела нет.
static func primary_key(mods: Dictionary) -> String:
	for top: String in ["optic_primary", "top_front"]:
		var best: String = ""
		for k: String in sorted_keys(mods):
			if top_mount(k) != top or not WeaponDb.is_optic(WeaponDb.mod_id(mods[k])):
				continue
			if _straight(mods, k) and (best == "" or depth(k) < depth(best)):
				best = k
		if best != "":
			return best
	return ""


## Вся цепочка до точки оружия — без крена (проставки, удлинители), а не угловые кронштейны.
static func _straight(mods: Dictionary, key: String) -> bool:
	var k: String = key
	while parent_key(k) != "":
		var spec: Dictionary = (WeaponDb.attachment(WeaponDb.mod_id(mods.get(parent_key(k), ""))).get("provides", {}) as Dictionary).get(base_of(k), {})
		if not is_zero_approx(float(spec.get("roll", 0.0))) or spec.has("angle"):
			return false
		k = parent_key(k)
	# второй прицел прямо на планке (optic_primary#2) — дополнительный, не основной
	return depth(key) > 0 or key in ["optic_primary", "top_front"]


## Прицелы экземпляра по порядку: "primary" (основной, встроенная оптика или прицела нет вовсе)
## и ключи остальных прицелов. Фонарь/ЛЦУ на боковой точке прицелом не считается.
static func sights(entry: Dictionary) -> Array:
	var mods: Dictionary = entry.get("mods", {})
	var w: Dictionary = WeaponDb.weapon(String(entry.get("id", "")))
	var integral: bool = (w.get("integral", {}) as Dictionary).has("zoom")
	var main: String = primary_key(mods)
	var out: Array = []
	for k: String in sorted_keys(mods):
		if k != main and WeaponDb.is_optic(WeaponDb.mod_id(mods[k])):
			out.append(k)
	if main != "" or integral or out.is_empty():
		out.push_front("primary")
	return out


## Подпись точки для окон: «Сверху на коробке → Кронштейн 45° (справа)».
static func label(entry_id: String, mods: Dictionary, key: String) -> String:
	var parent: String = parent_key(key)
	var base: String = base_of(key)
	var name: String = String(WeaponDb.MOUNT_NAMES.get(base, POINT_NAMES.get(base, base)))
	var n: String = leaf(key).get_slice(MULTI, 1) if leaf(key).contains(MULTI) else ""
	if n != "":
		name += " · " + n
	if parent == "":
		return name
	return "%s → %s" % [label(entry_id, mods, parent), ItemDb.item_name(WeaponDb.mod_id(mods.get(parent, "")))]


# ---------------------------------------------------------------- старые сборки

## Привести обвес записи к дереву: старая точка «угловой прицел» (optic_offset) становится
## кронштейном 45° на верхней планке с прицелом на нём; выбранный «offset» — этим прицелом.
## Что не встало — [запись, выпавшее].
static func upgrade(entry: Dictionary) -> Array:
	var e: Dictionary = entry.duplicate(true)
	var spill: Array = []
	var mods: Dictionary = e.get("mods", {})
	if not mods.has("optic_offset"):
		return [e, spill]
	var optic: Dictionary = WeaponCondition.mod_entry(mods.optic_offset)
	mods.erase("optic_offset")
	e["mods"] = mods
	var model_key: String = String(WeaponDb.weapon(String(e.id)).get("model", ""))
	var legacy: Dictionary = WeaponMods.socket(model_key, "optic_offset")
	var bracket: Dictionary = {"id": LEGACY_BRACKET, "dur": float(optic.get("dur", 100.0)), "mods": {"rail": optic}}
	var want_z: float = (legacy.pos as Vector3).z if not legacy.is_empty() else INF
	# прежний угловой стоял у основного прицела — кронштейн туда же, на верхнюю планку коробки
	var place: Dictionary = rail_place(e, "optic_primary", LEGACY_BRACKET, want_z) if is_finite(want_z) else {}
	if place.is_empty() and mods.has("optic_primary"):
		# короткая планка: основной прицел сдвигается по пазам, пока рядом не встанет кронштейн
		var main_id: String = WeaponDb.mod_id(mods.optic_primary)
		for s: int in valid_slots(e, "optic_primary", main_id):
			var moved: Dictionary = e.duplicate(true)
			var main_rec: Dictionary = WeaponCondition.mod_entry(moved.mods.optic_primary)
			main_rec.erase("n")
			main_rec["slot"] = s
			moved.mods.optic_primary = main_rec
			place = rail_place(moved, "optic_primary", LEGACY_BRACKET, want_z)
			if not place.is_empty():
				e = moved
				break
	if place.is_empty():
		place = free_place(e, LEGACY_BRACKET, want_z)
	if place.is_empty():
		spill.append(bracket)
		return [e, spill]
	var r: Array = insert(e, String(place.key), bracket, int(place.slot))
	if String(r[2]) != "":
		spill.append(bracket)
		return [e, spill]
	e = r[0]
	var left: Dictionary = r[3]
	for k: Variant in left:
		spill.append(left[k])
	if String(e.get("sight", "primary")) == "offset":
		e["sight"] = String(place.key) + SEP + "rail" if (e.mods as Dictionary).has(String(place.key) + SEP + "rail") else "primary"
	return [e, spill]


## Кронштейн, которым заменяется старый встроенный угловой.
const LEGACY_BRACKET := "mount_offset45_01"
