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
	print("build_test: проверок %d, провалено %d" % [_checks, _fails])
	get_tree().quit(1 if _fails > 0 else 0)


func _veras(mods: Dictionary) -> Dictionary:
	return {"id": "wpn_ar_01", "n": 1, "dur": 100.0, "mods": mods.duplicate(true), "sight": "primary"}


## Старый «угловой прицел» становится кронштейном на верхней планке с прицелом на нём.
func _legacy() -> void:
	var old: Dictionary = _veras({"optic_primary": {"id": "optic_lpvo_01", "dur": 100.0}, "optic_offset": {"id": "optic_offset_rd_01", "dur": 70.0}})
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
	_check("пресет со старым угловым собирается деревом", not (preset.get("mods", {}) as Dictionary).has("optic_offset")
		and WeaponStats.sights_of(preset).size() == 2, JSON.stringify(preset.get("mods", {})))
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
	_check("LPVO впереди коллиматора — «мешает прицелу»", WeaponBuild.block(WeaponBuild.insert(_veras({}), "optic_primary", {"id": "optic_lpvo_01"}, 4)[0], "optic_primary#2", "optic_rd_01", 0).begins_with("мешает прицелу"))
	_check("второй прицел на тот же участок — «занято»", WeaponBuild.block(e, "optic_primary#2", "optic_rd_01", 2).begins_with("занято"))
	_check("коллиматор перед LPVO — «закроет прицел»", WeaponBuild.block(e, "optic_primary#2", "optic_rd_01", 6).begins_with("закроет прицел"),
		WeaponBuild.block(e, "optic_primary#2", "optic_rd_01", 6))
	_check("за край планки — нельзя", WeaponBuild.block(e, "optic_primary#2", "mount_offset45_01", 9) != "")
	var place: Dictionary = WeaponBuild.free_place(e, "mount_offset45_01")
	_check("кронштейн находит свободный паз", String(place.get("key", "")) == "optic_primary#2" and int(place.get("slot", -1)) >= 0, str(place))
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
	_check("кронштейн дал точку под мини-коллиматор", WeaponBuild.candidate_keys(e, "optic_rmr_01").has("optic_primary#2/rail"))
	_check("крен перевёрнутого кронштейна −45°", is_equal_approx(WeaponBuild.point_roll("veras54", e.mods, "optic_primary#2/rail"), -45.0))
	r = WeaponBuild.insert(e, "optic_primary#2/rail", {"id": "optic_rmr_01", "n": 1, "dur": 80.0})
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
	var on_riser: Array = WeaponBuild.insert(riser[0], "optic_primary/rail", {"id": "optic_lpvo_01", "n": 1})
	_check("LPVO на проставке — основной прицел", String(on_riser[2]) == "" and WeaponBuild.primary_key((on_riser[0] as Dictionary).mods) == "optic_primary/rail"
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
		"optic_primary#2/rail": {"id": "optic_rmr_01", "dur": 100.0},
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


## Характеристики: прицел на кронштейне работает только выбранным, вес переходника считается.
func _stats() -> void:
	var e: Dictionary = _veras({"optic_primary": {"id": "optic_lpvo_01", "dur": 100.0, "slot": 0},
		"optic_primary#2": {"id": "mount_offset45_01", "dur": 100.0, "slot": 6},
		"optic_primary#2/rail": {"id": "optic_rmr_01", "dur": 100.0}})
	var main: Dictionary = WeaponStats.compute(e)
	e.sight = "optic_primary#2/rail"
	var side: Dictionary = WeaponStats.compute(e)
	_check("основной — оптика, угловой — без кратности", bool(main.scoped) and not bool(side.scoped) and String(side.sight) == "optic_primary#2/rail")
	var bare: Dictionary = WeaponStats.compute(_veras({"optic_primary": {"id": "optic_lpvo_01", "dur": 100.0}}))
	_check("кронштейн и коллиматор утяжеляют", float(main.weight) > float(bare.weight) + 0.08, "%.2f / %.2f" % [main.weight, bare.weight])
