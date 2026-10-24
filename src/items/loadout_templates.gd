class_name LoadoutTemplates
extends RefCounted
## Шаблоны снаряжения (свои у каждого профиля, Profile.loadout_templates): что надето — по слотам,
## с обвесом на оружии и плитами в жилете, — и что лежит в рюкзаке (id и сколько). Собрать по
## шаблону: сначала из тайника, недостающее — купить у Михалыча (если каталог открыт и хватает
## денег). Перед сборкой — план: что возьмётся, что купится и за сколько, чего нет и почему.
## Магазины снаряжаются сами на входе в рейд (Inventory.prepare_mags) — шаблон их только кладёт.
##
## Шаблон: {name, slots: {слот: {id, mods: {точка: id}, plates: {сторона: id}}}, backpack: [[id, n]]}.

const MAX := 6


static func all() -> Array:
	Profile.ensure()
	return Profile.loadout_templates


## Сохранить текущее (надето + рюкзак) под именем; такое имя уже есть — заменить.
static func capture(name: String) -> Dictionary:
	var slots := {}
	for slot in Profile.equipment:
		var e: Dictionary = Profile.equipment[slot]
		var rec := {"id": String(e.id)}
		var mods := {}
		# место на планке (паз, сторона кронштейна, угол) — отдельно: старые шаблоны читают mods как id
		var place := {}
		for m in e.get("mods", {}):
			mods[String(m)] = WeaponDb.mod_id(e.mods[m])
			var md: Dictionary = e.mods[m] if e.mods[m] is Dictionary else {}
			var p := {}
			for k in ["slot", "flip", "angle", "remote"]:
				if md.has(k):
					p[k] = md[k]
			if not p.is_empty():
				place[String(m)] = p
		if not mods.is_empty():
			rec["mods"] = mods
		if not place.is_empty():
			rec["place"] = place
		var plates := {}
		for side in e.get("plates", {}):
			plates[String(side)] = String((e.plates[side] as Dictionary).id)
		if not plates.is_empty():
			rec["plates"] = plates
		if not ItemDb.pouch_list(e).is_empty():
			rec["pouches"] = ItemDb.pouch_list(e).duplicate(true)
		slots[String(slot)] = rec
	var counts := {}
	var order: Array = []
	for e in Profile.backpack:
		var id := String(e.id)
		if not counts.has(id):
			order.append(id)
		counts[id] = int(counts.get(id, 0)) + int(e.get("n", 1))
	var bp: Array = []
	for id in order:
		bp.append([id, int(counts[id])])
	var t := {"name": name.strip_edges() if name.strip_edges() != "" else "Шаблон %d" % (all().size() + 1), "slots": slots, "backpack": bp}
	for i in range(all().size()):
		if String(all()[i].name) == String(t.name):
			all()[i] = t
			Profile.save()
			return t
	if all().size() >= MAX:
		all().remove_at(0)
	all().append(t)
	Profile.save()
	return t


static func remove(i: int) -> void:
	if i >= 0 and i < all().size():
		all().remove_at(i)
		Profile.save()


## Можно ли купить у Михалыча ("" — можно, иначе почему нет).
static func _buy_block(id: String) -> String:
	if Profile.buy_price(id) <= 0:
		return "у предмета нет цены Михалыча"
	var n := TraderStock.catalog_of(id)
	if n <= 0:
		return "у Михалыча нет"
	if Profile.trust_level() < n and not id in Profile.unlocked_stock:
		return "нужна ступень доверия %d" % TraderStock.step_of(n)
	return ""


## План сборки: [{what, how: "есть" / "тайник" / "купить" / "нет", price, why}], итог — cost, missing.
static func plan(t: Dictionary) -> Dictionary:
	var rows: Array = []
	# сколько чего в тайнике (одно и то же не берём дважды)
	var stock := {}
	for e in Profile.stash:
		stock[String(e.id)] = int(stock.get(String(e.id), 0)) + int(e.get("n", 1))
	var add := func(what: String, id: String, n: int) -> void:
		var have := mini(int(stock.get(id, 0)), n)
		if have > 0:
			stock[id] = int(stock[id]) - have
			rows.append({"what": what, "id": id, "n": have, "how": "тайник", "price": 0, "why": ""})
		var need := n - have
		if need <= 0:
			return
		var why := _buy_block(id)
		if why == "":
			rows.append({"what": what, "id": id, "n": need, "how": "купить", "price": Profile.buy_price(id) * need, "why": ""})
		else:
			rows.append({"what": what, "id": id, "n": need, "how": "нет", "price": 0, "why": why})
	var slots: Dictionary = t.get("slots", {})
	for slot in slots:
		var rec: Dictionary = slots[slot]
		var id := String(rec.id)
		var cur: Dictionary = Profile.equipment.get(String(slot), {})
		if String(cur.get("id", "")) == id:
			rows.append({"what": ItemDb.item_name(id), "id": id, "n": 1, "how": "есть", "price": 0, "why": ""})
		else:
			add.call(ItemDb.item_name(id), id, 1)
		var cur_mods: Dictionary = cur.get("mods", {}) if String(cur.get("id", "")) == id else {}
		var mods: Dictionary = rec.get("mods", {})
		for m in mods:
			var mid := String(mods[m])
			if cur_mods.has(m) and WeaponDb.mod_id(cur_mods[m]) == mid:
				continue
			var wb := Profile.mod_block(mid, String(m))
			if wb != "":
				rows.append({"what": "  " + ItemDb.item_name(mid), "id": mid, "n": 1, "how": "нет", "price": 0, "why": wb})
				continue
			add.call("  " + ItemDb.item_name(mid), mid, 1)
		var cur_pl: Dictionary = cur.get("plates", {}) if String(cur.get("id", "")) == id else {}
		var plates: Dictionary = rec.get("plates", {})
		for side in plates:
			var pid := String(plates[side])
			if cur_pl.has(side) and String((cur_pl[side] as Dictionary).id) == pid:
				continue
			add.call("  " + ItemDb.item_name(pid), pid, 1)
		# подсумки на броне: что уже висит — засчитано
		var have_p: Array = ItemDb.pouch_ids(cur) if String(cur.get("id", "")) == id else []
		for p_v: Variant in rec.get("pouches", []):
			var pid := String((p_v as Dictionary).id) if p_v is Dictionary else String(p_v)
			var k := have_p.find(pid)
			if k >= 0:
				have_p.remove_at(k)
				continue
			add.call("  " + ItemDb.item_name(String(pid)), String(pid), 1)
	# рюкзак: что уже лежит — засчитано
	var in_bp := {}
	for e in Profile.backpack:
		in_bp[String(e.id)] = int(in_bp.get(String(e.id), 0)) + int(e.get("n", 1))
	for pair in t.get("backpack", []):
		var id := String(pair[0])
		var need := int(pair[1]) - int(in_bp.get(id, 0))
		if need > 0:
			add.call(ItemDb.item_name(id) + (" ×%d" % need if need > 1 else ""), id, need)
	# итог — по строкам (лямбда выше чисел снаружи не меняет)
	var cost := 0
	var missing := 0
	for r in rows:
		cost += int(r.price)
		if String(r.how) == "нет":
			missing += 1
	return {"rows": rows, "cost": cost, "missing": missing}


## Вернуть детали её место из шаблона (паз, сторона, угол), если оно сейчас допустимо.
static func _place(slot: String, key: String, p: Dictionary) -> void:
	if p.is_empty():
		return
	var e: Dictionary = Profile.equipment.get(slot, {})
	var mods: Dictionary = e.get("mods", {})
	if not mods.has(key) or not mods[key] is Dictionary:
		return
	if WeaponBuild.block(e, key, WeaponDb.mod_id(mods[key]), int(p.get("slot", -1))) != "":
		return
	for k in p:
		(mods[key] as Dictionary)[k] = p[k]
	e["rev"] = int(e.get("rev", 0)) + 1
	Profile.save()


## Собрать: берёт из тайника, докупает, надевает, ставит обвес и плиты, кладёт в рюкзак.
## Возвращает, что не получилось (пусто — всё собрано).
static func apply(t: Dictionary) -> Array[String]:
	var fails: Array[String] = []
	var p := plan(t)
	if int(p.cost) > Profile.money:
		fails.append("не хватает денег: нужно %s ₽" % InventoryUI.money(int(p.cost)))
		return fails
	var slots: Dictionary = t.get("slots", {})
	for slot in slots:
		var rec: Dictionary = slots[slot]
		var id := String(rec.id)
		if String((Profile.equipment.get(String(slot), {}) as Dictionary).get("id", "")) != id:
			if not _equip(id):
				fails.append(ItemDb.item_name(id))
				continue
		var mods: Dictionary = rec.get("mods", {})
		var place: Dictionary = rec.get("place", {})
		# от родителей к детям: прицел на кронштейне — после кронштейна
		for m: String in WeaponBuild.sorted_keys(mods):
			var mid := String(mods[m])
			var cur: Dictionary = Profile.weapon_mods(String(slot))
			if cur.has(m) and WeaponDb.mod_id(cur[m]) == mid:
				_place(String(slot), m, place.get(m, {}))
				continue
			var i := _from_stash(mid)
			if i < 0 or not Profile.install_mod(String(slot), i, false, m):
				fails.append(ItemDb.item_name(mid))
				continue
			_place(String(slot), m, place.get(m, {}))
		var plates: Dictionary = rec.get("plates", {})
		for side in plates:
			var pid := String(plates[side])
			var e: Dictionary = Profile.equipment.get(String(slot), {})
			if (e.get("plates", {}) as Dictionary).has(side) and String((e.plates[side] as Dictionary).id) == pid:
				continue
			var i := _from_stash(pid)
			if i < 0 or not Profile.fit_part("equip:" + String(slot), -1, "stash", i, String(side)):
				fails.append(ItemDb.item_name(pid))
		# подсумки — на надетую броню: из тайника, нет — купить
		var have_p: Array = ItemDb.pouch_ids(Profile.equipment.get(String(slot), {}) as Dictionary)
		for pid_v: Variant in rec.get("pouches", []):
			var pid := String((pid_v as Dictionary).id) if pid_v is Dictionary else String(pid_v)
			# место из шаблона (полуслот), занято — первое свободное
			var at := int((pid_v as Dictionary).get("at", -1)) if pid_v is Dictionary else -1
			var k := have_p.find(pid)
			if k >= 0:
				have_p.remove_at(k)
				continue
			var i := _from_stash(pid)
			if i < 0:
				if _buy_block(pid) != "" or not Profile.buy(pid, 1, "stash", false):
					fails.append(ItemDb.item_name(pid))
					continue
				i = _from_stash(pid)
			if i < 0 or not (Profile.equip_from("stash", i, "pouch:%d" % at) or Profile.equip_from("stash", i)):
				fails.append(ItemDb.item_name(pid))
	var in_bp := {}
	for e in Profile.backpack:
		in_bp[String(e.id)] = int(in_bp.get(String(e.id), 0)) + int(e.get("n", 1))
	for pair in t.get("backpack", []):
		var id := String(pair[0])
		var need := int(pair[1]) - int(in_bp.get(id, 0))
		while need > 0:
			var i := -1
			for j in range(Profile.stash.size()):
				if String(Profile.stash[j].id) == id:
					i = j
					break
			if i >= 0:
				var k := mini(need, int(Profile.stash[i].n))
				if not Profile.stash_to_backpack(i, k):
					fails.append("%s — нет места в рюкзаке" % ItemDb.item_name(id))
					break
				need -= k
				continue
			# вещи с состоянием (магазины) не складываются — покупаются по одной
			var per := need if ItemDb.stack(id) > 1 else 1
			if _buy_block(id) != "" or not Profile.buy(id, per, "backpack", false):
				fails.append(ItemDb.item_name(id))
				break
			need -= per
	Profile.save()
	return fails


## Надеть id: из тайника, нет — купить в тайник и надеть.
static func _equip(id: String) -> bool:
	var i := _from_stash(id)
	return i >= 0 and Profile.equip_from("stash", i)


## Индекс записи id в тайнике; нет — купить одну (если можно) и вернуть её индекс.
static func _from_stash(id: String) -> int:
	for i in range(Profile.stash.size()):
		if String(Profile.stash[i].id) == id:
			return i
	if _buy_block(id) != "" or not Profile.buy(id, 1, "stash", false):
		return -1
	for i in range(Profile.stash.size() - 1, -1, -1):
		if String(Profile.stash[i].id) == id:
			return i
	return -1
