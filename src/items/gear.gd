class_name Gear
extends RefCounted
## Операции над экземплярами снаряжения — чистые функции над записями (см. WeaponDb): снять /
## поставить обвес, плиту, магазин; перезарядка (смена магазина или досыпка россыпью); снарядить
## магазины из россыпи. Где лежит запись (слот, рюкзак, ящик, тело) — решает вызывающий (Raid —
## на хосте, Profile — в убежище). Часть: "mod:<точка>", "plate:<front|back>", "mag".

## Вынуть часть из записи: [новая запись, вынутое] (вынутое пустое — нечего).
static func strip(entry: Dictionary, part: String) -> Array:
	var e := entry.duplicate(true)
	if part.begins_with("mod:"):
		var mount := part.trim_prefix("mod:")
		var mods: Dictionary = e.get("mods", {})
		if not mods.has(mount):
			return [entry, {}]
		var got := {"id": WeaponDb.mod_id(mods[mount]), "n": 1}
		mods.erase(mount)
		e["mods"] = mods
		_bump(e)
		return [e, got]
	if part.begins_with("plate:"):
		var side := part.trim_prefix("plate:")
		var plates: Dictionary = e.get("plates", {})
		if not plates.has(side):
			return [entry, {}]
		var p: Dictionary = plates[side]
		plates.erase(side)
		e["plates"] = plates
		return [e, {"id": String(p.id), "n": 1, "dur": float(p.dur)}]
	if part == "mag":
		var mag: Dictionary = e.get("mag", {}) if e.get("mag") is Dictionary else {}
		if mag.is_empty():
			return [entry, {}]
		var w := WeaponDb.weapon(String(e.id))
		if w.has("internal_mag") or String(mag.get("id", "")) == "":
			# встроенный магазин: вынимаются только патроны
			if int(mag.get("rounds", 0)) <= 0:
				return [entry, {}]
			var ammo := {"id": String(mag.ammo), "n": int(mag.rounds)}
			mag.rounds = 0
			_bump(e)
			return [e, ammo]
		var out := WeaponDb.make_mag(String(mag.id), String(mag.get("ammo", "")), int(mag.get("rounds", 0)))
		e["mag"] = {"id": "", "ammo": String(mag.get("ammo", "")), "rounds": 0}
		_bump(e)
		return [e, out]
	return [entry, {}]


## Поставить предмет item в запись: обвес (в точку hint или первую подходящую), плиту (в сторону
## hint или первую свободную), магазин (вместо вставленного). [новая запись, вытесненное, ошибка].
static func fit(entry: Dictionary, item: Dictionary, hint: String = "") -> Array:
	var e := entry.duplicate(true)
	var iid := WeaponDb.canonical(String(item.id))
	if not WeaponDb.attachment(iid).is_empty() and WeaponDb.is_weapon(String(e.id)):
		var mount := hint
		if mount == "":
			mount = WeaponDb.free_mount_for(e, iid)
			if mount == "":
				var all := WeaponDb.mounts_for(e, iid)
				mount = String(all[0]) if not all.is_empty() else ""
		if mount == "":
			return [entry, {}, "на это оружие не встаёт"]
		var probe := e.duplicate(true)
		var mods: Dictionary = probe.get("mods", {})
		var old := {}
		if mods.has(mount):
			old = {"id": WeaponDb.mod_id(mods[mount]), "n": 1}
			mods.erase(mount)
		probe["mods"] = mods
		var why := WeaponDb.attach_block(probe, mount, iid)
		if why != "":
			return [entry, {}, why]
		mods[mount] = {"id": iid}
		probe["mods"] = mods
		_bump(probe)
		return [probe, old, ""]
	if not WeaponDb.plate(iid).is_empty() and e.has("plates"):
		var slots: Array = WeaponDb.vest(String(e.id)).get("plates", [])
		var side := hint
		if side == "":
			for s in slots:
				if not (e.plates as Dictionary).has(s):
					side = String(s)
					break
		if side == "" or not side in slots:
			return [entry, {}, "нет свободного гнезда под плиту"]
		var old := {}
		if (e.plates as Dictionary).has(side):
			var op: Dictionary = e.plates[side]
			old = {"id": String(op.id), "n": 1, "dur": float(op.dur)}
		e.plates[side] = {"id": iid, "dur": float(item.get("dur", WeaponDb.plate(iid).durability))}
		return [e, old, ""]
	if not WeaponDb.magazine(iid).is_empty() and WeaponDb.is_weapon(String(e.id)):
		if not WeaponDb.mag_fits(String(e.id), iid):
			return [entry, {}, "магазин не подходит"]
		var r := strip(e, "mag")
		e = r[0]
		e["mag"] = {"id": iid, "ammo": String(item.get("ammo", "")), "rounds": int(item.get("rounds", 0))}
		_bump(e)
		return [e, r[1], ""]
	return [entry, {}, "сюда не ставится"]


## Что можно снять с записи: [[подпись, часть], …] — обвес по точкам, магазин (или патроны из
## встроенного), плиты.
static func parts(e: Dictionary) -> Array:
	var out: Array = []
	var id := String(e.get("id", ""))
	var mods: Dictionary = e.get("mods", {})
	for m in WeaponDb.MOUNTS:
		if mods.has(m):
			out.append(["Снять: %s (%s)" % [ItemDb.item_name(WeaponDb.mod_id(mods[m])), String(WeaponDb.MOUNT_NAMES.get(m, m))], "mod:" + String(m)])
	var mag: Dictionary = e.get("mag", {}) if e.get("mag") is Dictionary else {}
	if WeaponDb.is_weapon(id) and not mag.is_empty():
		if String(mag.get("id", "")) != "":
			out.append(["Вынуть магазин (%d)" % int(mag.get("rounds", 0)), "mag"])
		elif int(mag.get("rounds", 0)) > 0:
			out.append(["Разрядить (%d)" % int(mag.rounds), "mag"])
	var plates: Dictionary = e.get("plates", {})
	for side in ["front", "back"]:
		if plates.has(side):
			var p: Dictionary = plates[side]
			out.append(["Вынуть плиту %s (%d/%d)" % ["спереди" if side == "front" else "сзади", int(p.dur), int(ItemDb.max_dur(String(p.id)))], "plate:" + side])
	return out


## Хозяин поменял оружие (магазин, обвес) — счётчик ревизии: у владельца состояние перечитается.
static func _bump(e: Dictionary) -> void:
	e["rev"] = int(e.get("rev", 0)) + 1


## Перезарядка (хост): weapon — запись оружия (уже с состоянием владельца), list — рюкзак (меняется).
## Отстёгиваемый магазин: самый полный подходящий из рюкзака (тем же патроном — лучше), старый —
## в рюкзак с остатком; снаряжённых нет — досыпать россыпь в текущий. Встроенный — россыпью.
## Возвращает [оружие, выпавшее (старый магазин без места), вид: "swap" / "topup" / ""].
static func reload_weapon(weapon: Dictionary, list: Array, grid: Vector2i) -> Array:
	var e := weapon.duplicate(true)
	var wid := String(e.id)
	var w := WeaponDb.weapon(wid)
	var mag: Dictionary = e.get("mag", {}) if e.get("mag") is Dictionary else {}
	if not w.has("internal_mag"):
		var best := -1
		var best_n := 0
		for i in range(list.size()):
			var it: Dictionary = list[i]
			if not WeaponDb.mag_fits(wid, String(it.id)) or int(it.get("rounds", 0)) <= 0:
				continue
			var n := int(it.rounds) + (1000 if String(it.get("ammo", "")) == String(mag.get("ammo", "")) else 0)
			if n > best_n:
				best_n = n
				best = i
		if best >= 0:
			var fresh: Dictionary = ItemDb.remove_at(list, best, 1)
			var old := {}
			if String(mag.get("id", "")) != "":
				old = WeaponDb.make_mag(String(mag.id), String(mag.get("ammo", "")), int(mag.get("rounds", 0)))
			e["mag"] = {"id": String(fresh.id), "ammo": String(fresh.get("ammo", "")), "rounds": int(fresh.get("rounds", 0))}
			_bump(e)
			var spill := {}
			if not old.is_empty() and ItemDb.add_to(list, old, grid) == 0:
				spill = old
			return [e, spill, "swap"]
		if String(mag.get("id", "")) == "":
			return [weapon, {}, ""]
	# россыпью: тем же патроном; магазин пуст — любым своего калибра
	var cap := WeaponDb.capacity(e)
	var need := cap - int(mag.get("rounds", 0))
	if need <= 0:
		return [weapon, {}, ""]
	var ammo_id := String(mag.get("ammo", ""))
	var have := _count(list, ammo_id)
	if have <= 0 and int(mag.get("rounds", 0)) == 0:
		for it in list:
			if WeaponDb.ammo_fits(wid, String(it.id)):
				ammo_id = String(it.id)
				have = _count(list, ammo_id)
				break
	if have <= 0:
		return [weapon, {}, ""]
	var take := mini(need, have)
	_remove(list, ammo_id, take)
	mag.ammo = ammo_id
	mag.rounds = int(mag.get("rounds", 0)) + take
	e["mag"] = mag
	_bump(e)
	return [e, {}, "topup"]


## Что будет при перезарядке (владелец, по своей копии рюкзака): "swap" / "topup" / "".
static func reload_kind(weapon: Dictionary, list: Array) -> String:
	var wid := String(weapon.id)
	var w := WeaponDb.weapon(wid)
	var mag: Dictionary = weapon.get("mag", {}) if weapon.get("mag") is Dictionary else {}
	if not w.has("internal_mag"):
		for it in list:
			if WeaponDb.mag_fits(wid, String(it.id)) and int(it.get("rounds", 0)) > 0:
				return "swap"
		if String(mag.get("id", "")) == "":
			return ""
	if int(mag.get("rounds", 0)) >= WeaponDb.capacity(weapon):
		return ""
	for it in list:
		if WeaponDb.ammo_fits(wid, String(it.id)) and (int(mag.get("rounds", 0)) == 0 or String(it.id) == String(mag.get("ammo", ""))):
			return "topup"
	return ""


## Снарядить пустые и неполные магазины (и оружие) из россыпи того же калибра: сначала тем же
## патроном, что уже в магазине. list — где лежат и магазины, и патроны; extra — ещё записи
## (оружие в слотах), их магазины тоже. Возвращает сколько патронов ушло.
static func load_mags(list: Array, extra: Array = []) -> int:
	var used := 0
	# ссылки на сами записи: удаление стопок патронов сдвигает индексы, записи — нет
	var targets: Array = []
	for it in list:
		if it.has("rounds"):
			targets.append(it)
	for e in extra:
		if e is Dictionary and WeaponDb.is_weapon(String(e.get("id", ""))) and e.get("mag") is Dictionary:
			targets.append(e)
	for rec in targets:
		var mag: Dictionary = rec if rec.has("rounds") else rec.mag
		var cal := WeaponDb.mag_caliber(String(rec.id)) if rec.has("rounds") else String(WeaponDb.weapon(String(rec.id)).caliber)
		var cap := int(WeaponDb.magazine(String(rec.id)).get("capacity", 0)) if rec.has("rounds") else WeaponDb.capacity(rec)
		var need := cap - int(mag.get("rounds", 0))
		if need <= 0 or cal == "":
			continue
		var ammo_id := String(mag.get("ammo", ""))
		if _count(list, ammo_id) <= 0 and int(mag.get("rounds", 0)) == 0:
			for it in list:
				if String(WeaponDb.ammo(String(it.id)).get("caliber", "")) == cal:
					ammo_id = String(it.id)
					break
		var take := mini(need, _count(list, ammo_id))
		if take <= 0:
			continue
		_remove(list, ammo_id, take)
		mag["ammo"] = ammo_id
		mag["rounds"] = int(mag.get("rounds", 0)) + take
		used += take
	return used


## Точно считает патроны только у пистолетов и болтовок (мало патронов, видно в окно) — у
## остальных при проверке — словами.
static func exact_count(weapon_id: String) -> bool:
	var w := WeaponDb.weapon(weapon_id)
	return String(w.get("class", "")) == "PISTOL" or String(w.get("cycle_sound", "")) == "bolt"


## Магазин от пистолета или болтовки — его проверка тоже точная.
static func mag_exact(mag_id: String) -> bool:
	for wid in WeaponDb.ids("weapons"):
		if WeaponDb.mag_fits(String(wid), mag_id) and exact_count(String(wid)):
			return true
	return false


## Что видно о магазине в сетке без проверки: «полный» / «пустой»; частично — ничего, пока не
## проверили (checked — сколько было при проверке; изменилось — снова не видно).
static func mag_state(mag: Dictionary) -> String:
	if not mag.has("rounds"):
		return ""
	var cap := int(WeaponDb.magazine(String(mag.id)).get("capacity", 0))
	var n := int(mag.rounds)
	if n <= 0:
		return "пустой"
	if n >= cap:
		return "полный"
	if int(mag.get("checked", -1)) == n:
		return ammo_estimate(n, cap, mag_exact(String(mag.id)))
	return ""


## Метка на магазине в сетке: ПОЛН / ПУСТ, после проверки — «>½», «7/17» (Balance.AMMO_CHECK.short).
static func mag_tag(mag: Dictionary) -> String:
	var st := mag_state(mag)
	if st.contains(" из "):
		return st.replace(" из ", "/")
	return String(Balance.AMMO_CHECK.short.get(st, ""))


## Сколько патронов «на глаз»: точно (exact) или словами (Balance.AMMO_CHECK.words).
static func ammo_estimate(rounds: int, capacity: int, exact: bool) -> String:
	if exact:
		return "%d из %d" % [rounds, capacity]
	if rounds <= 0:
		return "пустой"
	if rounds >= capacity:
		return "полный"
	var f := float(rounds) / float(maxi(capacity, 1))
	for w in Balance.AMMO_CHECK.words:
		if f >= float(w[0]):
			return String(w[1])
	return "почти пустой"


static func _count(list: Array, id: String) -> int:
	var c := 0
	for it in list:
		if String(it.id) == id and not it.has("rounds"):
			c += int(it.n)
	return c


static func _remove(list: Array, id: String, n: int) -> void:
	var left := n
	var i := list.size() - 1
	while i >= 0 and left > 0:
		if String(list[i].id) == id and not list[i].has("rounds"):
			left -= int(ItemDb.remove_at(list, i, left).n)
		i -= 1
