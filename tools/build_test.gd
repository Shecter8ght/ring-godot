extends Node
## Сборка оружия деревом (WeaponBuild): старые сборки, пазы планок, пересечения, «мешает прицелу»,
## кронштейн снимается вместе с прицелом и ставится обратно, модель и линии прицелов.
## tools/godot.cmd --headless res://tools/build_test.tscn

var _fails: int = 0
var _checks: int = 0


func _check(label: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	print("%s: %s %s" % ["PASS" if ok else "FAIL", label, detail])
	if not ok:
		_fails += 1


func _ready() -> void:
	_legacy()
	_rails()
	_adapters()
	_model()
	_stats()
	_plan()
	print("build_test: проверок %d, провалено %d" % [_checks, _fails])
	get_tree().quit(1 if _fails > 0 else 0)


func _veras(mods: Dictionary) -> Dictionary:
	return {"id": "wpn_ar_01", "n": 1, "dur": 100.0, "mods": mods.duplicate(true), "sight": "primary"}


## Старый «угловой прицел» становится кронштейном на верхней планке с прицелом на нём.
func _legacy() -> void:
	var old: Dictionary = _veras({"optic_primary": {"id": "optic_lpvo_01", "dur": 100.0}, "optic_offset": {"id": "optic_holo_01", "dur": 70.0}})
	old.sight = "offset"
	var r: Array = WeaponBuild.upgrade(old)
	var e: Dictionary = r[0]
	var mods: Dictionary = e.mods
	var bracket: String = ""
	for k: Variant in mods:
		if WeaponDb.mod_id(mods[k]) == WeaponBuild.LEGACY_BRACKET:
			bracket = String(k)
	_check("старый угловой → кронштейн на планке", bracket.begins_with("optic_primary#") and not mods.has("optic_offset"), JSON.stringify(mods))
	_check("прицел — на кронштейне, ресурс сохранён", mods.has(bracket + "/rail") and float((mods[bracket + "/rail"] as Dictionary).dur) == 70.0)
	_check("ничего не выпало", (r[1] as Array).is_empty(), str(r[1]))
	_check("выбранный «угловой» — прицел на кронштейне", String(e.sight) == bracket + "/rail", String(e.sight))
	_check("кронштейн не налезает на LPVO", WeaponBuild.block(e, bracket, WeaponBuild.LEGACY_BRACKET) == "")
	var preset: Dictionary = WeaponDb.make_weapon("AR_07_LEADER", RandomNumberGenerator.new())
	_check("пресет без убранного углового сохраняет основной прицел", not (preset.get("mods", {}) as Dictionary).has("optic_offset")
		and WeaponStats.sights_of(preset).size() == 1, JSON.stringify(preset.get("mods", {})))
	var mig: Array = WeaponDb.migrate(old)
	_check("миграция сохранения тоже переводит", not ((mig[0] as Dictionary).mods as Dictionary).has("optic_offset") and (mig[1] as Array).is_empty())
	var again: Array = WeaponDb.migrate(mig[0])
	_check("повторная миграция ничего не меняет", JSON.stringify(again[0].mods) == JSON.stringify(mig[0].mods))


## Пазы планки: шаг 20 мм, длина зажима, соседи, выход за край.
func _rails() -> void:
	var e: Dictionary = _veras({})
	var pt: Dictionary = WeaponBuild.point("wpn_ar_01", {}, "optic_primary")
	_check("верхняя планка ВЕРАСа — отрезок", WeaponBuild.is_rail(pt) and is_equal_approx(float(pt.rail[0]), 0.010), str(pt))
	var lpvo_slots: Array[int] = WeaponBuild.valid_slots(e, "optic_primary", "optic_lpvo_01")
	_check("LPVO (зажим 70 мм) — 5 пазов на 169 мм", lpvo_slots.size() == 5, str(lpvo_slots))
	var r: Array = WeaponBuild.insert(e, "optic_primary", {"id": "optic_lpvo_01", "n": 1, "dur": 100.0}, 2)
	e = r[0]
	_check("LPVO в пазу 2: середина на 0.085", is_equal_approx(WeaponBuild.placed_z("veras54", e.mods, "optic_primary"), 0.010 + 0.035 + 0.04))
	var front: Dictionary = WeaponBuild.insert(_veras({}), "optic_primary", {"id": "optic_lpvo_01"}, 4)[0]
	_check("LPVO впереди коллиматора — предупреждение без запрета", WeaponBuild.block(front, "optic_primary#2", "optic_rd_01", 0) == "" and WeaponBuild.sight_warning(front, "optic_primary#2", "optic_rd_01", 0) != "")
	_check("второй прицел на тот же участок — «занято»", WeaponBuild.block(e, "optic_primary#2", "optic_rd_01", 2).begins_with("занято"))
	_check("коллиматор перед LPVO — предупреждение без запрета", WeaponBuild.block(e, "optic_primary#2", "optic_rd_01", 6) == "" and WeaponBuild.sight_warning(e, "optic_primary#2", "optic_rd_01", 6) != "",
		WeaponBuild.block(e, "optic_primary#2", "optic_rd_01", 6))
	_check("за край планки — нельзя", WeaponBuild.block(e, "optic_primary#2", "mount_offset45_01", 9) != "")
	var place: Dictionary = WeaponBuild.free_place(e, "mount_offset45_01")
	_check("кронштейн сначала ищет свободную точку (цевьё сверху)", String(place.get("key", "")) == "top_front", str(place))
	var near: Dictionary = WeaponBuild.rail_place(e, "optic_primary", "mount_offset45_01", 0.16)
	_check("рядом с LPVO на той же планке — свободный паз", String(near.get("key", "")) == "optic_primary#2" and int(near.get("slot", -1)) >= 0, str(near))
	var top_front: Dictionary = WeaponBuild.free_place(_veras({}), "optic_rd_01")
	_check("коллиматор на голом ВЕРАСе — на верхнюю планку", String(top_front.get("key", "")) == "optic_primary", str(top_front))
	var grip: Array[int] = WeaponBuild.valid_slots(_veras({}), "underbarrel", "grip_vertical_01")
	_check("нижняя планка: рукоятка ездит по пазам", grip.size() >= 4, str(grip))
	_check("фонарь не встаёт на верхнюю планку", WeaponBuild.block(_veras({}), "optic_primary", "tac_flashlight_01") != "")


## Переходник: точка появляется от детали, снимается вместе с прицелом, ставится обратно.
func _adapters() -> void:
	var e: Dictionary = _veras({"optic_primary": {"id": "optic_lpvo_01", "dur": 100.0, "slot": 0}})
	var r: Array = WeaponBuild.insert(e, "optic_primary#2", {"id": "mount_offset45_01", "n": 1, "dur": 90.0}, 6, true)
	_check("кронштейн встал перевёрнутым", String(r[2]) == "" and bool(((r[0] as Dictionary).mods["optic_primary#2"] as Dictionary).get("flip", false)), String(r[2]))
	e = r[0]
	_check("кронштейн дал точку под мини-коллиматор", WeaponBuild.candidate_keys(e, "optic_holo_01").has("optic_primary#2/rail"))
	_check("крен перевёрнутого кронштейна −45°", is_equal_approx(WeaponBuild.point_roll("veras54", e.mods, "optic_primary#2/rail"), -45.0))
	r = WeaponBuild.insert(e, "optic_primary#2/rail", {"id": "optic_holo_01", "n": 1, "dur": 80.0})
	e = r[0]
	_check("коллиматор на кронштейне", String(r[2]) == "" and (e.mods as Dictionary).has("optic_primary#2/rail"))
	_check("прицелы: основной и угловой", WeaponStats.sights_of(e) == ["primary", "optic_primary#2/rail"], str(WeaponStats.sights_of(e)))
	_check("имя углового — слева", WeaponStats.sight_name("optic_primary#2/rail", e) == "Угловой слева", WeaponStats.sight_name("optic_primary#2/rail", e))
	e.sight = "optic_primary#2/rail"
	var weight_before: float = ItemDb.entry_weight(e)
	var out: Array = Gear.strip(e, "mod:optic_primary#2")
	var item: Dictionary = out[1]
	_check("кронштейн снимается вместе с прицелом", String(item.id) == "mount_offset45_01" and (item.get("mods", {}) as Dictionary).has("rail")
		and not ((out[0] as Dictionary).mods as Dictionary).has("optic_primary#2/rail"), JSON.stringify(item))
	_check("выбранный прицел вернулся на основной", String((out[0] as Dictionary).sight) == "primary")
	_check("вес сборки = оружие + снятый узел", is_equal_approx(weight_before, ItemDb.entry_weight(out[0]) + ItemDb.entry_weight(item)))
	var back: Array = Gear.fit(out[0], item, "optic_primary#2")
	_check("узел ставится обратно целиком", String(back[2]) == "" and ((back[0] as Dictionary).mods as Dictionary).has("optic_primary#2/rail"), String(back[2]))
	var riser: Array = WeaponBuild.insert(_veras({}), "optic_primary", {"id": "mount_riser_01", "n": 1}, 1)
	_check("длинная LPVO на короткую проставку не встаёт", WeaponBuild.block(riser[0], "optic_primary/rail", "optic_lpvo_01") != "")
	var on_riser: Array = WeaponBuild.insert(riser[0], "optic_primary/rail", {"id": "optic_4x_01", "n": 1})
	_check("4× на проставке — основной прицел", String(on_riser[2]) == "" and WeaponBuild.primary_key((on_riser[0] as Dictionary).mods) == "optic_primary/rail"
		and WeaponStats.sights_of(on_riser[0]) == ["primary"], String(on_riser[2]))
	var adj: Array = WeaponBuild.insert(_veras({}), "optic_primary", {"id": "mount_adjustable_01", "n": 1}, 3, false, 30.0)
	_check("поворотный кронштейн держит угол 30°", is_equal_approx(WeaponBuild.point_roll("veras54", (adj[0] as Dictionary).mods, "optic_primary/rail"), 30.0))
	var deep: Dictionary = _veras({"optic_primary": {"id": "mount_riser_01"}, "optic_primary/rail": {"id": "mount_riser_01"},
		"optic_primary/rail/rail": {"id": "mount_riser_01"}})
	_check("четвёртый переходник подряд — нельзя", WeaponBuild.block(deep, "optic_primary/rail/rail/rail", "mount_riser_01") != "")
	_check("прицел на третьем — можно", WeaponBuild.block(deep, "optic_primary/rail/rail/rail", "optic_rd_01") == "",
		WeaponBuild.block(deep, "optic_primary/rail/rail/rail", "optic_rd_01"))


## Модель: устройство стоит по пазу, линии прицелов от кронштейна — с креном.
func _model() -> void:
	var mods: Dictionary = {"optic_primary": {"id": "optic_lpvo_01", "dur": 100.0, "slot": 0},
		"optic_primary#2": {"id": "mount_offset45_01", "dur": 100.0, "slot": 6},
		"optic_primary#2/rail": {"id": "optic_holo_01", "dur": 100.0},
		"underbarrel": {"id": "grip_vertical_01", "dur": 100.0, "slot": 3}}
	var m0: Node3D = WeaponModels.build("wpn_ar_01", mods, 0, 100.0)
	add_child(m0)
	var sights: Dictionary = m0.get_meta("sights", {})
	var line: Dictionary = sights.get("optic_primary#2/rail", {})
	_check("линия углового прицела есть, крен 45°", not line.is_empty() and is_equal_approx(absf(float(line.roll)), deg_to_rad(45.0)), str(line))
	_check("угловой — справа от оси (−X)", float(line.get("x", 0.0)) < -0.01, str(line))
	var part: Node3D = m0.find_child("Attachment_optic_primary_n2__rail", true, false) as Node3D
	_check("узел прицела на кронштейне назван по пути", part != null)
	var ads0: float = float(m0.get_meta("ads_z", 0.0))
	mods.optic_primary.slot = 4
	mods.erase("optic_primary#2")
	mods.erase("optic_primary#2/rail")
	var m1: Node3D = WeaponModels.build("wpn_ar_01", mods, 0, 100.0)
	add_child(m1)
	var ads1: float = float(m1.get_meta("ads_z", 0.0))
	_check("LPVO вперёд на 4 паза — глаз ближе к окуляру не становится: прицел дальше на 80 мм", is_equal_approx(ads0 - ads1, 0.08), "%.3f → %.3f" % [ads0, ads1])
	m0.queue_free()
	m1.queue_free()
	# магазин: вынут — не виден, другой — свой вид, пустой штатный — на месте
	var veras: Dictionary = _veras({})
	veras["mag"] = {"id": "mag_545_30", "ammo": "ammo_545_std", "rounds": 0}
	_check("пустой штатный магазин — вид штатный", WeaponMods.mag_state(veras) == "*")
	veras.mag.id = ""
	_check("вынутый магазин — «нет»", WeaponMods.mag_state(veras) == "")
	veras.mag.id = "mag_545_60"
	_check("магазин на 60 — свой вид", WeaponMods.mag_state(veras) == "mag_545_60")
	for state: String in ["", "mag_545_60", "*"]:
		var mm: Node3D = WeaponModels.build("wpn_ar_01", {}, 0, 100.0, state)
		add_child(mm)
		var shown := 0
		for n: Node in mm.find_children("*", "MeshInstance3D", true, false):
			if String(n.get_meta("part", "")) == "mag" and (n as MeshInstance3D).visible:
				shown += 1
		var look: bool = mm.find_child("MagLook", false, false) != null
		var ok: bool = (state == "" and shown == 0 and not look) or (state == "mag_545_60" and shown == 0 and look) or (state == "*" and shown > 0 and not look)
		_check("модель с магазином «%s»" % state, ok, "штатных видно %d, свой вид %s" % [shown, look])
		mm.queue_free()
	_check("ключ вида различает магазин", WeaponCondition.model_key("wpn_ar_01", {}, 100.0, "") != WeaponCondition.model_key("wpn_ar_01", {}, 100.0, "*"))


## Характеристики: прицел на кронштейне работает только выбранным, вес переходника считается.
func _stats() -> void:
	var e: Dictionary = _veras({"optic_primary": {"id": "optic_lpvo_01", "dur": 100.0, "slot": 0},
		"optic_primary#2": {"id": "mount_offset45_01", "dur": 100.0, "slot": 6},
		"optic_primary#2/rail": {"id": "optic_holo_01", "dur": 100.0}})
	var main: Dictionary = WeaponStats.compute(e)
	e.sight = "optic_primary#2/rail"
	var side: Dictionary = WeaponStats.compute(e)
	_check("основной — оптика, угловой — без кратности", bool(main.scoped) and not bool(side.scoped) and String(side.sight) == "optic_primary#2/rail")
	var bare: Dictionary = WeaponStats.compute(_veras({"optic_primary": {"id": "optic_lpvo_01", "dur": 100.0}}))
	_check("кронштейн и коллиматор утяжеляют", float(main.weight) > float(bare.weight) + 0.08, "%.2f / %.2f" % [main.weight, bare.weight])


## Черновик конструктора → одна операция: взять из тайника (кронштейн с прицелом на нём), купить,
## снятое — в тайник; повтор детали и приклад в рейде — отказ.
func _plan() -> void:
	Profile.use_file("user://build_test_profile.json", true)
	Profile.money = 100000
	# верстак 2 — точки прицелов (Balance.WORKBENCH_SLOT_LEVEL)
	Profile.modules["workbench"] = 2
	Profile.stash.clear()
	Profile.backpack.clear()
	var bracket: Dictionary = {"id": "mount_offset45_01", "n": 1, "dur": 77.0, "mods": {"rail": {"id": "optic_holo_01", "dur": 66.0}}}
	ItemDb.add_to(Profile.stash, bracket, Profile.stash_grid())
	Profile.equipment["primary"] = {"id": "wpn_ar_01", "n": 1, "dur": 100.0, "sight": "primary",
		"mods": {"optic_primary": {"id": "optic_lpvo_01", "dur": 90.0, "slot": 0}, "stock": {"id": "stock_tele_ak_01", "dur": 100.0}},
		"mag": {"id": "mag_545_30", "ammo": "ammo_545_std", "rounds": 30}}
	var weapon: Dictionary = Profile.equipment.primary
	var draft: Dictionary = BuildPlan.draft_of(weapon)
	var bi: int = -1
	for i in range(Profile.stash.size()):
		if String(Profile.stash[i].id) == "mount_offset45_01":
			bi = i
	draft["optic_primary#2"] = {"id": "mount_offset45_01", "slot": 6, "src": {"from": "stash", "idx": bi, "sub": ""}}
	draft["optic_primary#2/rail"] = {"id": "optic_holo_01", "src": {"from": "stash", "idx": bi, "sub": "rail"}}
	draft["underbarrel"] = {"id": "grip_vertical_01", "slot": 2, "src": {"from": "shop"}}
	var money_before: int = Profile.money
	var r: Dictionary = BuildPlan.resolve(weapon, draft, {}, {"stash": Profile.stash, "backpack": Profile.backpack}, {"shop": true})
	_check("план: можно, покупка — рукоятка", String(r.why) == "" and r.buy == ["grip_vertical_01"], String(r.why))
	var why: String = Profile.apply_build("equip:primary", -1, draft, {})
	var mods: Dictionary = Profile.equipment.primary.mods
	_check("сборка применена: кронштейн, прицел на нём, рукоятка", why == "" and mods.has("optic_primary#2/rail") and mods.has("underbarrel"), why)
	_check("ресурс деталей из тайника сохранён", float(mods["optic_primary#2"].dur) == 77.0 and float(mods["optic_primary#2/rail"].dur) == 66.0)
	_check("деньги списаны по цене торговца", Profile.money == money_before - Profile.buy_price("grip_vertical_01"))
	_check("кронштейна в тайнике больше нет", Profile.stash.filter(func(e: Dictionary) -> bool: return String(e.id) == "mount_offset45_01").is_empty())
	# снять LPVO черновиком — он в тайнике
	var d2: Dictionary = BuildPlan.draft_of(Profile.equipment.primary)
	d2.erase("optic_primary")
	why = Profile.apply_build("equip:primary", -1, d2, {})
	_check("снятая LPVO — в тайнике с ресурсом", why == "" and not (Profile.equipment.primary.mods as Dictionary).has("optic_primary")
		and Profile.stash.any(func(e: Dictionary) -> bool: return String(e.id) == "optic_lpvo_01" and float(e.dur) == 90.0), why)
	# снять кронштейн — прицел уезжает вместе с ним одним предметом
	var d3: Dictionary = BuildPlan.draft_of(Profile.equipment.primary)
	d3.erase("optic_primary#2")
	d3.erase("optic_primary#2/rail")
	why = Profile.apply_build("equip:primary", -1, d3, {})
	_check("кронштейн вернулся в тайник с прицелом на нём", why == "" and Profile.stash.any(func(e: Dictionary) -> bool:
		return String(e.id) == "mount_offset45_01" and (e.get("mods", {}) as Dictionary).has("rail")), why)
	# одна деталь дважды
	var w2: Dictionary = Profile.equipment.primary
	var d4: Dictionary = BuildPlan.draft_of(w2)
	d4["side_left"] = {"id": "grip_vertical_01", "src": {"from": "weapon", "key": "underbarrel"}}
	_check("одна деталь в двух местах — отказ", String(BuildPlan.resolve(w2, d4, {}, {"stash": Profile.stash}, {"shop": true}).why) != "")
	# рейд: приклад не менять, торговца нет
	var d5: Dictionary = BuildPlan.draft_of(w2)
	d5.erase("stock")
	_check("в рейде приклад не снять", String(BuildPlan.resolve(w2, d5, {}, {"backpack": []}, {"shop": false, "lists": BuildPlan.RAID_LISTS, "locked": ["stock"]}).why) != "")
	var d6: Dictionary = BuildPlan.draft_of(w2)
	d6["side_left"] = {"id": "tac_flashlight_01", "src": {"from": "shop"}}
	_check("в рейде торговца нет", String(BuildPlan.resolve(w2, d6, {}, {"backpack": []}, {"shop": false, "lists": BuildPlan.RAID_LISTS}).why) != "")
	# магазин: вынуть — в тайник
	why = Profile.apply_build("equip:primary", -1, BuildPlan.draft_of(Profile.equipment.primary), {"from": "none"})
	_check("магазин вынут в тайник", why == "" and String(Profile.equipment.primary.mag.id) == ""
		and Profile.stash.any(func(e: Dictionary) -> bool: return String(e.id) == "mag_545_30" and int(e.get("rounds", 0)) == 30), why)
	_template()


## Шаблон снаряжения помнит пазы и сторону кронштейна: снял всё в тайник — собрал по шаблону — как было.
func _template() -> void:
	Profile.stash.clear()
	Profile.equipment["primary"] = {"id": "wpn_ar_01", "n": 1, "dur": 100.0, "sight": "primary",
		"mods": {"optic_primary": {"id": "optic_rd_01", "dur": 100.0, "slot": 0},
			"optic_primary#2": {"id": "mount_offset45_01", "dur": 100.0, "slot": 6, "flip": true},
			"optic_primary#2/rail": {"id": "optic_holo_01", "dur": 100.0},
			"underbarrel": {"id": "grip_vertical_01", "dur": 100.0, "slot": 3}},
		"mag": {"id": "mag_545_30", "ammo": "ammo_545_std", "rounds": 30}}
	var t: Dictionary = LoadoutTemplates.capture("тест сборки")
	var bare: Dictionary = BuildPlan.draft_of(Profile.equipment.primary)
	for k: String in bare.keys():
		bare.erase(k)
	var why: String = Profile.apply_build("equip:primary", -1, bare, {})
	_check("шаблон: всё снято в тайник", why == "" and (Profile.equipment.primary.mods as Dictionary).is_empty(), why)
	var fails: Array[String] = LoadoutTemplates.apply(t)
	var mods: Dictionary = Profile.equipment.primary.mods
	_check("шаблон собран без отказов", fails.is_empty(), str(fails))
	_check("шаблон вернул пазы и сторону кронштейна", int(mods.get("optic_primary#2", {}).get("slot", -1)) == 6 and bool(mods.get("optic_primary#2", {}).get("flip", false))
		and int(mods.get("underbarrel", {}).get("slot", -1)) == 3 and mods.has("optic_primary#2/rail"), JSON.stringify(mods))
