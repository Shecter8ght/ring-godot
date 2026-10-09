class_name ArsenalDev
extends RefCounted
## Команды консоли разработчика (`, и в проекте, и в собранной игре) для арсенала: выдать предмет или
## сборку, поставить обвес в точку, переключить прицел / фонарь / ЛЦУ, заспавнить ИИ с выкладкой,
## повредить плиту, выставить износ, показать характеристики. Только хост или соло: состояние
## оружия и снаряжения ведёт хост (Gear._bump — владелец перечитает).

const HELP := "give <id|код|preset:ID> [n] · mount <точка> <обвес> · unmount <точка> · sight · light · laser · spawn <выкладка|тип> [n] · plate front|back <урон> · dur <0–100> · stats · list weapons|ammo|magazines|attachments|presets|vests|plates|helmets|headsets|loadouts. Пример: give weapon VERAS54 · give ammo 545_AP 120 · give optic LPVO_01 · equip primaryOptic LPVO_01 · equip offsetOptic OFFSET_RED_DOT_01 · equip sideLeft FLASHLIGHT_01 · toggle sight|flashlight|laser · spawn loadout perimeter_marksman · damage plate front 50 · set weapon durability 25"
## Точки в записи ТЗ (camelCase) → точки арсенала.
const MOUNT_ALIAS := {"primaryOptic": "optic_primary", "offsetOptic": "optic_offset", "sideLeft": "side_left", "sideRight": "side_right",
	"underbarrel": "underbarrel", "muzzle": "muzzle", "stock": "stock"}
const GIVE_KINDS := ["weapon", "ammo", "optic", "flashlight", "laser", "combo", "armor", "carrier", "vest", "plate", "helmet", "headset", "mag", "magazine",
	"muzzle", "grip", "stock", "mod", "item"]


static func run(tree: SceneTree, a: PackedStringArray) -> String:
	a = _normalize(a)
	if a.is_empty():
		return HELP
	if Net.is_networked() and not tree.get_multiplayer().is_server():
		return "только на хосте"
	var pl := _me(tree)
	match a[0]:
		"give":
			return _give(pl, a[1] if a.size() > 1 else "", int(a[2]) if a.size() > 2 else 1)
		"list":
			return _list(a[1] if a.size() > 1 else "")
		"spawn":
			return _spawn(tree, pl, a[1] if a.size() > 1 else "", int(a[2]) if a.size() > 2 else 1)
	if pl == null:
		return "нет своего игрока (команда — в рейде или на полигоне)"
	match a[0]:
		"mount":
			return _mount(pl, a[1] if a.size() > 1 else "", a[2] if a.size() > 2 else "")
		"unmount":
			return _unmount(pl, a[1] if a.size() > 1 else "")
		"sight":
			pl._toggle_sight()
			return "прицел: " + String(pl._ws.get(pl.weapon_slot, {}).get("sight", "primary"))
		"light":
			pl._toggle_tac("light")
			return "фонарь переключён"
		"laser":
			pl._toggle_tac("laser")
			return "ЛЦУ переключён"
		"plate":
			return _plate(pl, a[1] if a.size() > 1 else "front", float(a[2]) if a.size() > 2 else 20.0)
		"dur":
			return _dur(pl, float(a[1]) if a.size() > 1 else 100.0)
		"stats":
			var s := WeaponStats.compute(pl.weapon_entry())
			return "%s: урон %d, пробитие %d, магазин %d, темп %.2f с, разброс %.2f°, отдача %.3f, эрго %d, износ %d%%, задержка %.1f%%" % [
				String(s.name), int(s.damage), int(s.pen), int(s.mag), float(s.interval), float(s.spread_deg), float(s.kick), int(s.ergo), int(s.dur), float(s.jam) * 100.0]
	return HELP


## Запись команд из ТЗ → свои: give <вид> <код> [n], equip <точка> <код>, toggle …, spawn loadout …,
## damage plate …, set weapon durability ….
static func _normalize(a: PackedStringArray) -> PackedStringArray:
	if a.size() >= 3 and a[0] == "give" and a[1] in GIVE_KINDS:
		var out := PackedStringArray(["give", resolve(a[2])])
		if a.size() > 3:
			out.append(a[3])
		return out
	if a.size() == 2 and a[0] == "give":
		return PackedStringArray(["give", resolve(a[1])])
	if a.size() >= 3 and a[0] == "equip":
		return PackedStringArray(["mount", String(MOUNT_ALIAS.get(a[1], a[1])), resolve(a[2])])
	if a.size() >= 2 and a[0] == "toggle":
		return PackedStringArray(["light" if a[1] == "flashlight" else a[1]])
	if a.size() >= 3 and a[0] == "spawn" and a[1] == "loadout":
		return PackedStringArray(["spawn"] + Array(a.slice(2)))
	if a.size() >= 4 and a[0] == "damage" and a[1] == "plate":
		return PackedStringArray(["plate", a[2], a[3]])
	if a.size() >= 4 and a[0] == "set" and a[1] == "weapon" and a[2] == "durability":
		return PackedStringArray(["dur", a[3]])
	return a


## Код из данных (VERAS54, 545_AP, LPVO_01, OFFSET_RED_DOT_01, CAR_03, PLATE_06…) или id → id предмета;
## сборка (AK12_BASE) → "preset:…". Не нашлось — как есть.
static func resolve(code: String) -> String:
	if code.begins_with("preset:") or ItemDb.exists(code):
		return code
	var up := code.to_upper()
	if not WeaponDb.preset(up).is_empty():
		return "preset:" + up
	var items := WeaponDb.items()
	for id in items:
		# прежний код (old_code) — синоним: АК-12 стал ВЕРАС-54, а AK12 в старых заметках и командах остался
		if _code_of(items[id]) == up or String((items[id] as Dictionary).get("old_code", "")) == up:
			return String(id)
	var low := code.to_lower().replace("red_dot", "rd")
	var best := ""
	for id in items:
		var s := String(id)
		if s.ends_with("_" + low) or s.contains("_" + low + "_") or s == low:
			if best == "" or s.length() < best.length():
				best = s
	return best if best != "" else code


## Код предмета из данных: у оружия — сверху, у брони — во вложенном описании.
static func _code_of(it: Dictionary) -> String:
	if it.has("code"):
		return String(it.code).to_upper()
	for k in it:
		if it[k] is Dictionary and (it[k] as Dictionary).has("code"):
			return String(it[k].code).to_upper()
	return ""


static func _me(tree: SceneTree) -> Player:
	for n in tree.get_nodes_in_group("players"):
		if (n as Player).is_local():
			return n as Player
	return null


## В рюкзак своего игрока в рейде, иначе — в тайник.
static func _give(pl: Player, id: String, n: int) -> String:
	if id == "":
		return "give <id|preset:ID> [n]"
	var e: Dictionary
	if id.begins_with("preset:"):
		var rng := RandomNumberGenerator.new()
		rng.randomize()
		e = WeaponDb.make_weapon(id.trim_prefix("preset:"), rng, [100, 100])
	elif not ItemDb.exists(id):
		return "нет такого предмета: " + id
	else:
		e = ItemDb.make(WeaponDb.canonical(id), maxi(1, n))
	if e.is_empty():
		return "нет такой сборки: " + id
	if pl and pl.loadout_mode:
		var k := pl.inventory.add_entry(e)
		return "в рюкзак: %s × %d" % [ItemDb.label(e), k] if k > 0 else "в рюкзаке нет места"
	Profile.ensure()
	var got := ItemDb.add_to(Profile.stash, e, Profile.stash_grid())
	Profile.save()
	return "в тайник: %s × %d" % [ItemDb.label(e), got] if got > 0 else "в тайнике нет места"


static func _list(section: String) -> String:
	match section:
		"presets":
			return ", ".join(WeaponDb.presets().keys())
		"loadouts":
			return ", ".join(WeaponDb.loadouts().keys())
		"":
			return HELP
	return ", ".join(WeaponDb.ids(section))


## Запись оружия в руках (снаряжение в рейде или ствол песочницы) и как её записать обратно.
static func _held(pl: Player) -> Dictionary:
	if pl.weapon_slot == "":
		return {}
	if pl.loadout_mode:
		return pl.inventory.equipment.get(pl.weapon_slot, {})
	return pl.sandbox_weapons.get(pl.weapon_slot, {})


static func _store(pl: Player, e: Dictionary) -> void:
	Gear._bump(e)
	if pl.loadout_mode:
		var eq := pl.inventory.equipment.duplicate(true)
		eq[pl.weapon_slot] = e
		pl.inventory.equipment = eq
	else:
		pl.sandbox_weapons[pl.weapon_slot] = e


static func _mount(pl: Player, mount: String, att: String) -> String:
	var e := _held(pl)
	if e.is_empty():
		return "в руках нет оружия"
	if att == "" or WeaponDb.attachment(att).is_empty():
		return "mount <точка> <обвес>; точки: " + ", ".join(WeaponDb.mounts_of(String(e.id)).keys())
	if mount == "optic_offset":
		# прежняя команда «угловой»: кронштейн 45° на верхнюю планку, прицел — на него
		var probe := e.duplicate(true)
		(probe.mods as Dictionary)["optic_offset"] = {"id": WeaponDb.canonical(att), "dur": 100.0}
		var up: Array = WeaponBuild.upgrade(probe)
		if not (up[1] as Array).is_empty():
			return "не встаёт: на планке нет места под кронштейн"
		_store(pl, up[0])
		return "%s → кронштейн 45° на верхней планке" % ItemDb.item_name(att)
	var r := Gear.fit(e, ItemDb.make(WeaponDb.canonical(att), 1), mount)
	if String(r[2]) != "":
		return "не встаёт: " + String(r[2])
	_store(pl, r[0])
	return "%s → %s" % [ItemDb.item_name(att), String(WeaponDb.MOUNT_NAMES.get(mount, mount)) if mount != "" else "первая подходящая точка"]


static func _unmount(pl: Player, mount: String) -> String:
	var e := _held(pl)
	if e.is_empty() or not (e.get("mods", {}) as Dictionary).has(mount):
		return "на точке «%s» ничего нет" % mount
	var r := Gear.strip(e, "mod:" + mount)
	_store(pl, r[0])
	return "снято: " + ItemDb.item_name(String((r[1] as Dictionary).get("id", "")))


static func _plate(pl: Player, side: String, dmg: float) -> String:
	var eq := pl.inventory.equipment.duplicate(true)
	var v: Dictionary = eq.get("armor", {})
	var plates: Dictionary = v.get("plates", {})
	if not plates.has(side):
		return "плиты «%s» нет (надет %s)" % [side, ItemDb.item_name(String(v.get("id", "")))]
	var p: Dictionary = plates[side]
	p.dur = maxf(0.0, float(p.dur) - dmg)
	pl.inventory.equipment = eq
	return "плита %s: %d / %d" % [side, int(p.dur), int(ItemDb.max_dur(String(p.id)))]


static func _dur(pl: Player, v: float) -> String:
	var e := _held(pl)
	if e.is_empty():
		return "в руках нет оружия"
	e = e.duplicate(true)
	e.dur = clampf(v, 0.0, 100.0)
	if pl._ws.has(pl.weapon_slot):
		pl._ws[pl.weapon_slot].dur = e.dur
	_store(pl, e)
	return "износ оружия: %d%%" % int(e.dur)


## ИИ с выкладкой (data/loadouts.json) или типом (Balance.AI_ARCHETYPES) в 8 м перед собой.
static func _spawn(tree: SceneTree, pl: Player, what: String, n: int) -> String:
	var level := tree.current_scene
	if level == null or not level.has_method("spawn_squad"):
		return "не в рейде"
	var arch := what
	var opts := {}
	if not Balance.AI_ARCHETYPES.has(what):
		if WeaponDb.loadout(what).is_empty():
			return "spawn <выкладка|тип>; выкладки: " + ", ".join(WeaponDb.loadouts().keys())
		opts["loadout"] = what
		arch = "pmc" if what.begins_with("perimeter") else ("resident" if what == "civilian" else "gunner")
		for k in Balance.AI_ARCHETYPES:
			if String(Balance.AI_ARCHETYPES[k].get("loadout", "")) == what:
				arch = String(k)
	var at := Vector3.ZERO
	if pl:
		at = pl.global_position + Vector3(sin(pl.body_yaw()), 0.0, cos(pl.body_yaw())) * 8.0
	var archs: Array = []
	for i in range(clampi(n, 1, 6)):
		archs.append(arch)
	level.call("spawn_squad", at, archs, opts)
	return "заспавнено: %d × %s" % [archs.size(), what]
