class_name Gear
extends RefCounted
## Операции над экземплярами снаряжения — чистые функции над записями (см. WeaponDb): снять /
## поставить обвес, плиту, магазин; перезарядка (смена магазина или досыпка россыпью); снарядить
## магазины из россыпи. Где лежит запись (слот, рюкзак, ящик, тело) — решает вызывающий (Raid —
## на хосте, Profile — в убежище). Часть: "mod:<точка>", "plate:<front|back>", "mag".

## Вынуть часть из записи: [новая запись, вынутое] (вынутое пустое — нечего).
## Старые записи ПМ считали весь боезапас в магазине. При миграции переносим один патрон,
## сохраняя общее число; остальные семейства продолжают прежнюю схему.
static func normalize_chamber(entry: Dictionary) -> Dictionary:
	var e: Dictionary = entry.duplicate(true)
	if int(WeaponDb.weapon(String(e.get("id", ""))).get("chamber_capacity", 0)) <= 0:
		return e
	var mag: Dictionary = e.get("mag", {}) if e.get("mag") is Dictionary else {}
	if not e.has("chamber"):
		e["chamber"] = 1 if int(mag.get("rounds", 0)) > 0 else 0
		e["chamber_ammo"] = mag_pop(mag) if int(e.chamber) > 0 else ""
		e["mag"] = mag
	return e


static func total_rounds(entry: Dictionary) -> int:
	var e: Dictionary = normalize_chamber(entry)
	var mag: Dictionary = e.get("mag", {}) if e.get("mag") is Dictionary else {}
	return int(mag.get("rounds", 0)) + int(e.get("chamber", 0))


## Досыл после полной перезарядки переносит патрон из магазина, а не создаёт девятый.
static func chamber_round(entry: Dictionary) -> void:
	if int(WeaponDb.weapon(String(entry.get("id", ""))).get("chamber_capacity", 0)) <= 0:
		return
	var mag: Dictionary = entry.get("mag", {}) if entry.get("mag") is Dictionary else {}
	if int(entry.get("chamber", 0)) <= 0 and int(mag.get("rounds", 0)) > 0:
		entry["chamber_ammo"] = mag_pop(mag)
		entry["mag"] = mag
		entry["chamber"] = 1


static func strip(entry: Dictionary, part: String) -> Array:
	var e := entry.duplicate(true)
	if part.begins_with("mod:"):
		# снимается со всем, что на нём стоит (кронштейн — вместе с прицелом)
		var r: Array = WeaponBuild.extract(e, part.trim_prefix("mod:"))
		if (r[1] as Dictionary).is_empty():
			return [entry, {}]
		if WeaponDb.is_optic(String((r[1] as Dictionary).get("id", ""))):
			# прицел сняли — открытые прицельные пристреливать заново
			knock_zero(r[0], Balance.ZEROING.sight_moa)
		_bump(r[0])
		return r
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
			# встроенный магазин: вынимаются только патроны (вперемешку — верхние одного типа, остальные следом)
			var layers: Array = mag_layers(mag)
			if layers.is_empty():
				return [entry, {}]
			var top: Array = layers.pop_back()
			var ammo := {"id": String(top[0]), "n": int(top[1])}
			mag_apply(mag, layers)
			e["mag"] = mag
			_bump(e)
			return [e, ammo]
		var out := mag_item(mag)
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
		var slot := -1
		if mount == "":
			var place: Dictionary = WeaponBuild.free_place(e, iid)
			if place.is_empty():
				var all := WeaponDb.mounts_for(e, iid)
				mount = String(all[0]) if not all.is_empty() else ""
			else:
				mount = String(place.key)
				slot = int(place.slot)
		elif not (e.get("mods", {}) as Dictionary).has(mount) and WeaponBuild.block(e, mount, iid) != "":
			# новое место на планке: ближайший свободный паз
			var slots: Array[int] = WeaponBuild.valid_slots(e, mount, iid)
			if not slots.is_empty():
				slot = slots[0]
		if mount == "":
			return [entry, {}, "на это оружие не встаёт"]
		var r: Array = WeaponBuild.insert(e, mount, item, slot)
		if String(r[2]) != "":
			return [entry, {}, String(r[2])]
		if not (r[3] as Dictionary).is_empty():
			return [entry, {}, "на переходнике не всё встанет"]
		if WeaponDb.is_optic(iid):
			# новый прицел — ноль сбит, пристреливать заново
			knock_zero(r[0], Balance.ZEROING.sight_moa)
		return [r[0], r[1], ""]
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
		e["mag"] = mag_record(item)
		_bump(e)
		return [e, r[1], ""]
	return [entry, {}, "сюда не ставится"]


## Что можно снять с записи: [[подпись, часть], …] — обвес по точкам, магазин (или патроны из
## встроенного), плиты.
static func parts(e: Dictionary) -> Array:
	var out: Array = []
	var id := String(e.get("id", ""))
	var mods: Dictionary = e.get("mods", {})
	for m: String in WeaponBuild.sorted_keys(mods):
		out.append(["Снять: %s (%s)" % [ItemDb.item_name(WeaponDb.mod_id(mods[m])), WeaponBuild.label(id, mods, m)], "mod:" + m])
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
## в рюкзак с остатком; снаряжённых нет — досыпать россыпь в текущий (того же типа нет — любым своего
## калибра, поверх: в магазине можно мешать). Магазин вынут — вставляется и пустой. Встроенный — россыпью.
## Возвращает [оружие, выпавшее (старый магазин без места), вид: "swap" / "topup" / ""].
static func reload_weapon(weapon: Dictionary, list: Array, grid: Vector2i, keep_old: bool = false) -> Array:
	var e: Dictionary = normalize_chamber(weapon)
	var wid := String(e.id)
	var w := WeaponDb.weapon(wid)
	var mag: Dictionary = e.get("mag", {}) if e.get("mag") is Dictionary else {}
	if not w.has("internal_mag"):
		var best := -1
		var best_n := -1
		var mag_out: bool = String(mag.get("id", "")) == ""
		for i in range(list.size()):
			var it: Dictionary = list[i]
			if not it.has("rounds") or not WeaponDb.mag_fits(wid, String(it.id)) or (int(it.get("rounds", 0)) <= 0 and not mag_out):
				continue
			var n := int(it.rounds) + (1000 if String(it.get("ammo", "")) == String(mag.get("ammo", "")) else 0)
			if n > best_n:
				best_n = n
				best = i
		if best >= 0:
			var fresh: Dictionary = ItemDb.remove_at(list, best, 1)
			var old := {}
			if String(mag.get("id", "")) != "":
				old = mag_item(mag)
			e["mag"] = mag_record(fresh)
			chamber_round(e)
			_bump(e)
			var spill := {}
			# keep_old: старый магазин вызывающий раскладывает сам (сумка сброса разгрузки, рюкзак)
			if not old.is_empty() and (keep_old or ItemDb.add_to(list, old, grid) == 0):
				spill = old
			return [e, spill, "swap"]
		if String(mag.get("id", "")) == "":
			return [weapon, {}, ""]
	# россыпью: тем же патроном, что сверху; его нет (или магазин пуст) — любым своего калибра
	var cap := WeaponDb.capacity(e)
	var need := cap - int(mag.get("rounds", 0))
	if need <= 0:
		return [weapon, {}, ""]
	var ammo_id := mag_top(mag)
	var have := _count(list, ammo_id)
	if have <= 0:
		for it in list:
			if WeaponDb.ammo_fits(wid, String(it.id)) and not it.has("rounds"):
				ammo_id = String(it.id)
				have = _count(list, ammo_id)
				break
	if have <= 0:
		return [weapon, {}, ""]
	var take := mini(need, have)
	_remove(list, ammo_id, take)
	mag_push(mag, ammo_id, take)
	e["mag"] = mag
	chamber_round(e)
	_bump(e)
	return [e, {}, "topup"]


## Что будет при перезарядке (владелец, по своей копии рюкзака): "swap" / "topup" / "".
static func reload_kind(weapon: Dictionary, list: Array) -> String:
	var wid := String(weapon.id)
	var w := WeaponDb.weapon(wid)
	var mag: Dictionary = weapon.get("mag", {}) if weapon.get("mag") is Dictionary else {}
	if not w.has("internal_mag"):
		var mag_out: bool = String(mag.get("id", "")) == ""
		for it in list:
			if it.has("rounds") and WeaponDb.mag_fits(wid, String(it.id)) and (int(it.get("rounds", 0)) > 0 or mag_out):
				return "swap"
		if mag_out:
			return ""
	if int(mag.get("rounds", 0)) >= WeaponDb.capacity(weapon):
		return ""
	for it in list:
		if WeaponDb.ammo_fits(wid, String(it.id)) and not it.has("rounds"):
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
		elif e is Dictionary and e.has("rounds"):
			# магазин вне сетки (в подсумке разгрузки)
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
		mag_push(mag, ammo_id, take)
		used += take
	return used


# ---------------------------------------------------------------- пристрелка

## "zero" экземпляра ствола: [ошибка вбок, ошибка вверх, щелчки вбок, щелчки вверх]. Ошибка — в
## угловых минутах, игроку не видна (сбитый ноль); щелчки — что он накрутил барабанчиками.
## Нет поля — ствол пристрелян. Balance.ZEROING.
static func _zero(entry: Dictionary) -> Array:
	var z: Variant = entry.get("zero")
	if z is Array and (z as Array).size() >= 4:
		return [float(z[0]), float(z[1]), int(z[2]), int(z[3])]
	return [0.0, 0.0, 0, 0]


## Куда уходят пули от точки прицеливания, угл. мин: x — вправо, y — вверх.
static func zero_offset(entry: Dictionary) -> Vector2:
	var z: Array = _zero(entry)
	var click: float = float(Balance.ZEROING.click_moa)
	return Vector2(float(z[0]) + float(z[2]) * click, float(z[1]) + float(z[3]) * click)


static func zero_clicks(entry: Dictionary) -> Vector2i:
	var z: Array = _zero(entry)
	return Vector2i(int(z[2]), int(z[3]))


static func set_zero_clicks(entry: Dictionary, clicks: Vector2i) -> void:
	var z: Array = _zero(entry)
	var lim: int = int(Balance.ZEROING.max_clicks)
	z[2] = clampi(clicks.x, -lim, lim)
	z[3] = clampi(clicks.y, -lim, lim)
	if is_zero_approx(float(z[0])) and is_zero_approx(float(z[1])) and int(z[2]) == 0 and int(z[3]) == 0:
		entry.erase("zero")
	else:
		entry["zero"] = z


## Сбить ноль: ошибка в случайную сторону на moa = [от, до] угл. мин; щелчки остаются как были.
static func knock_zero(entry: Dictionary, moa: Array, rng: RandomNumberGenerator = null) -> void:
	if not WeaponDb.is_weapon(String(entry.get("id", ""))):
		return
	var angle: float = rng.randf() * TAU if rng else randf() * TAU
	var size: float = rng.randf_range(float(moa[0]), float(moa[1])) if rng else randf_range(float(moa[0]), float(moa[1]))
	var z: Array = _zero(entry)
	z[0] = snappedf(cos(angle) * size, 0.1)
	z[1] = snappedf(sin(angle) * size, 0.1)
	entry["zero"] = z


## Что накручено: «вверх 3, вправо 2» ("" — барабанчики на нуле).
static func zero_text(clicks: Vector2i) -> String:
	var parts: Array[String] = []
	if clicks.y != 0:
		parts.append("%s %d" % ["вверх" if clicks.y > 0 else "вниз", absi(clicks.y)])
	if clicks.x != 0:
		parts.append("%s %d" % ["вправо" if clicks.x > 0 else "влево", absi(clicks.x)])
	return ", ".join(parts)


# ---------------------------------------------------------------- патроны в магазине вперемешку

## Слои патронов магазина снизу вверх: [[id патрона, сколько], …] — ровно на rounds патронов.
## Один тип — поля "mix" нет, тип — "ammo". Вперемешку — "mix" хранит слои, "ammo" — верхний патрон
## (он уходит в ствол первым). Выстрел уменьшает только rounds: лишнее сверху отбрасывается здесь.
## mag — предмет-магазин или запись магазина в оружии (поля одни и те же).
static func mag_layers(mag: Dictionary) -> Array:
	var out: Array = []
	var left: int = int(mag.get("rounds", 0))
	if left <= 0:
		return out
	var mix: Variant = mag.get("mix")
	if mix is Array:
		for layer: Variant in (mix as Array):
			if left <= 0:
				break
			var n: int = mini(int(layer[1]), left)
			if n <= 0:
				continue
			_layer_add(out, String(layer[0]), n)
			left -= n
	if left > 0:
		# слоёв нет (один тип) или меньше, чем патронов: остальное — типом "ammo"
		_layer_add(out, String(mag.get("ammo", "")), left)
	return out


static func _layer_add(layers: Array, ammo_id: String, n: int) -> void:
	if not layers.is_empty() and String(layers[-1][0]) == ammo_id:
		layers[-1][1] = int(layers[-1][1]) + n
	else:
		layers.append([ammo_id, n])


## Записать слои в магазин: счёт, верхний тип, "mix" — только если типов больше одного.
static func mag_apply(mag: Dictionary, layers: Array) -> void:
	var total: int = 0
	for layer: Variant in layers:
		total += int(layer[1])
	mag["rounds"] = total
	if not layers.is_empty():
		mag["ammo"] = String(layers[-1][0])
	if layers.size() > 1:
		mag["mix"] = layers
	else:
		mag.erase("mix")


## Тип верхнего патрона (следующий в ствол); пустой магазин — последний тип, что в нём был.
static func mag_top(mag: Dictionary) -> String:
	var layers: Array = mag_layers(mag)
	return String(layers[-1][0]) if not layers.is_empty() else String(mag.get("ammo", ""))


## Дослать сверху n патронов типа ammo_id.
static func mag_push(mag: Dictionary, ammo_id: String, n: int = 1) -> void:
	var layers: Array = mag_layers(mag)
	_layer_add(layers, ammo_id, n)
	mag_apply(mag, layers)


## Снять верхний патрон: его тип ("" — магазин пуст).
static func mag_pop(mag: Dictionary) -> String:
	var layers: Array = mag_layers(mag)
	if layers.is_empty():
		return ""
	var top: String = String(layers[-1][0])
	layers[-1][1] = int(layers[-1][1]) - 1
	if int(layers[-1][1]) <= 0:
		layers.pop_back()
	mag_apply(mag, layers)
	if layers.is_empty():
		mag["ammo"] = top
	return top


## Типов патронов в магазине больше одного.
static func mag_mixed(mag: Dictionary) -> bool:
	return mag_layers(mag).size() > 1


## Чем снаряжён, сверху вниз: «БП ×10, ПС ×20» ("" — пуст). Один тип — просто его имя.
static func mag_text(mag: Dictionary) -> String:
	var layers: Array = mag_layers(mag)
	if layers.is_empty():
		return ""
	if layers.size() == 1:
		return ItemDb.item_name(String(layers[0][0]))
	var parts: Array[String] = []
	for i: int in range(layers.size() - 1, -1, -1):
		var short: String = String(ItemDb.item(String(layers[i][0])).get("short", ""))
		parts.append("%s ×%d" % [short if short != "" else ItemDb.item_name(String(layers[i][0])), int(layers[i][1])])
	return ", ".join(parts)


## Какие типы лежат вперемешку, сверху вниз, без счёта (ответ проверки магазина): «сверху БП, ниже ПС».
## Один тип — "".
static func mag_types_text(mag: Dictionary) -> String:
	var layers: Array = mag_layers(mag)
	if layers.size() < 2:
		return ""
	var names: Array[String] = []
	for i: int in range(layers.size() - 1, -1, -1):
		var short: String = String(ItemDb.item(String(layers[i][0])).get("short", ""))
		names.append(short if short != "" else ItemDb.item_name(String(layers[i][0])))
	return "сверху %s, ниже %s" % [names[0], ", ".join(names.slice(1))]


## Предмет-магазин (в рюкзак) из записи магазина оружия — с тем же содержимым.
static func mag_item(mag: Dictionary) -> Dictionary:
	var out: Dictionary = WeaponDb.make_mag(String(mag.get("id", "")), String(mag.get("ammo", "")), int(mag.get("rounds", 0)))
	mag_apply(out, mag_layers(mag))
	return out


## Запись магазина в оружии из предмета-магазина.
static func mag_record(item: Dictionary) -> Dictionary:
	var out: Dictionary = {"id": WeaponDb.canonical(String(item.get("id", ""))), "ammo": String(item.get("ammo", "")), "rounds": int(item.get("rounds", 0))}
	mag_apply(out, mag_layers(item))
	return out


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
