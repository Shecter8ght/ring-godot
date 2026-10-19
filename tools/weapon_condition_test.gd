extends Node
## Состояние не теряется в предметных операциях, хост считает износ, нулевой ресурс/ремонт.

var _fails: int = 0


func _check(label: String, ok: bool) -> void:
	print("%s: %s" % ["PASS" if ok else "FAIL", label])
	if not ok:
		_fails += 1


func _ready() -> void:
	Profile.use_file("user://weapon_condition_test.json", true)
	var weapon: Dictionary = ItemDb.make("wpn_ar_02", 1)
	var optic: Dictionary = ItemDb.make("optic_holo_01", 1)
	optic["dur"] = 20.0
	optic["fir"] = true
	weapon = Gear.fit(weapon, optic, "optic_primary")[0]
	_check("установка сохраняет ресурс и происхождение", float(weapon.mods.optic_primary.dur) == 20.0 and bool(weapon.mods.optic_primary.fir))
	var stripped: Array = Gear.strip(weapon, "mod:optic_primary")
	_check("снятие сохраняет ресурс", float(stripped[1].dur) == 20.0)
	var replaced: Array = Gear.fit(weapon, ItemDb.make("optic_holo_01", 1), "optic_primary")
	_check("замена возвращает изношенный экземпляр", float(replaced[1].dur) == 20.0 and float(replaced[0].mods.optic_primary.dur) == 100.0)
	_check("разные состояния не сливаются", not ItemDb.can_merge(optic, ItemDb.make("optic_holo_01", 1)))
	var old: Dictionary = WeaponDb.migrate({"id": "wpn_ar_02", "n": 1, "mods": {"optic_primary": "optic_holo_01"}})[0]
	_check("старые сохранения получают полный ресурс обвеса", float(old.mods.optic_primary.dur) == 100.0)
	_check("пороги 60/20 и ноль", WeaponCondition.stage({"dur": 60.01}) == 100 and WeaponCondition.stage({"dur": 60.0}) == 60 and WeaponCondition.stage({"dur": 20.0}) == 20 and WeaponCondition.broken({"dur": 0}))
	var full: Dictionary = replaced[0]
	var worn: Dictionary = full.duplicate(true)
	worn["dur"] = 20.0
	var new_stats: Dictionary = WeaponStats.compute(full)
	var worn_stats: Dictionary = WeaponStats.compute(worn)
	_check("износ ухудшает кучность и надёжность", float(worn_stats.spread_deg) > float(new_stats.spread_deg) and float(worn_stats.jam) > float(new_stats.jam))
	worn.mods.optic_primary.dur = 0.0
	_check("сломанный прицел теряет бонус", float(WeaponStats.compute(worn).ads_spread) == float(WeaponStats.compute({"id": worn.id, "dur": 20.0, "mods": {}}).ads_spread))
	_check("цена зависит от состояния обвеса", ItemDb.entry_value(worn) < ItemDb.entry_value(full))
	var inv: Inventory = Inventory.new()
	add_child(inv)
	full.mag.rounds = 30
	inv.equipment = {"primary": full}
	var before: Dictionary = inv.equipment.primary.duplicate(true)
	var state: Dictionary = {"id": full.id, "rev": int(before.rev), "rounds": 27, "shots": 3, "dur": 0.0}
	inv.apply_weapon_state("primary", state)
	var after: Dictionary = inv.equipment.primary
	_check("хост считает три выстрела, не принимает чужой процент", is_equal_approx(float(after.dur), 100.0 - float(WeaponDb.weapon(String(full.id)).stats.wear) * 3))
	_check("обвес изнашивается отдельно", float(after.mods.optic_primary.dur) < 100.0 and float(after.mods.optic_primary.dur) > float(after.dur))
	inv.apply_weapon_state("primary", state)
	_check("повтор пакета не удваивает износ", is_equal_approx(float(inv.equipment.primary.dur), float(after.dur)))
	state["shots"] = 999
	inv.apply_weapon_state("primary", state)
	_check("неподтверждённые выстрелы отклоняются", int(inv.equipment.primary._condition_shots) == 3)
	var broken: Dictionary = full.duplicate(true)
	broken["dur"] = 0.0
	Profile.equipment = {"primary": broken}
	Profile.money = 0
	_check("ремонт без денег невозможен", not Profile.repair_part("equip:primary", -1) and float(Profile.equipment.primary.dur) == 0.0)
	Profile.money = 1000000
	var repair_price: int = WeaponCondition.repair_price(broken)
	_check("ремонт сломанного оружия", Profile.repair_part("equip:primary", -1) and float(Profile.equipment.primary.dur) == 100.0 and Profile.money == 1000000 - repair_price)
	Profile.equipment.primary.mods.optic_primary.dur = 0.0
	_check("ремонт отдельного прицела", Profile.repair_part("equip:primary", -1, "optic_primary") and float(Profile.equipment.primary.mods.optic_primary.dur) == 100.0)
	Profile.save()
	Profile._loaded = false
	Profile.ensure()
	_check("сохранение после ремонта", float(Profile.equipment.primary.mods.optic_primary.dur) == 100.0)
	var actor: Player = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	actor.name = "BrokenWeaponActor"
	actor.process_mode = Node.PROCESS_MODE_DISABLED
	add_child(actor)
	actor.loadout_mode = true
	broken.mag.rounds = 10
	actor.inventory.equipment = {"primary": broken}
	actor.weapon_slot = ""
	actor._ws.clear()
	actor._switch("primary", false)
	actor._fire(actor.spec())
	_check("сломанное оружие не расходует патроны", actor.ammo == 10 and int(actor.weapon_entry().mag.rounds) == 10)
	actor.queue_free()
	var model: Node3D = WeaponModels.build("wpn_ar_02", {"optic_primary": {"id": "optic_holo_01", "dur": 0.0}})
	add_child(model)
	var markers: Array[Node] = model.find_children("Reticle", "MeshInstance3D", true, false)
	_check("ЛУМАР загружен, марка на нуле погашена", model.find_child("LUMAR_H1", true, false) != null and not markers.is_empty() and not (markers[0] as MeshInstance3D).visible)
	# вид один (решение владельца 2026-10-19): карты 100 и целое стекло при любой прочности; прежние 60/20 и
	# трещины — только при WeaponCondition.visual_wear
	for visual_wear: bool in [false, true]:
		WeaponCondition.visual_wear = visual_wear
		for state_value: int in [100, 60, 20]:
			var sample: Node3D = WeaponModels.build("wpn_ar_02", {"optic_primary": {"id": "optic_holo_01", "dur": state_value}})
			var sample_body: MeshInstance3D = sample.find_child("Body", true, false) as MeshInstance3D
			var sample_lens: MeshInstance3D = sample.find_child("Lens", true, false) as MeshInstance3D
			var body_material: StandardMaterial3D = sample_body.material_override as StandardMaterial3D
			var glass_material: ShaderMaterial = sample_lens.material_override as ShaderMaterial
			var shown: int = state_value if visual_wear else 100
			_check("%s: состояние %d%% — карты %d и %s стекло" % ["прежний вид" if visual_wear else "один вид", state_value, shown, "треснувшее" if shown == 20 else "целое"],
					body_material.albedo_texture.resource_path.ends_with("lumar_%d_base_color.png" % shown) and bool(glass_material.get_shader_parameter("cracked")) == (shown == 20))
			sample.free()
	WeaponCondition.visual_wear = false
	var compatible: int = 0
	for raw_id: Variant in WeaponDb.items():
		var id: String = String(raw_id)
		if not WeaponDb.is_weapon(id) or WeaponDb.attach_block({"id": id, "mods": {}}, "optic_primary", "optic_holo_01") != "":
			continue
		var mounted: Node3D = WeaponModels.build(id, {"optic_primary": {"id": "optic_holo_01", "dur": 60.0}})
		_check("ЛУМАР на совместимом оружии " + id, mounted.find_child("LUMAR_H1", true, false) != null and float(mounted.get_meta("sight_h", 0.0)) > 0.0)
		compatible += 1
		mounted.free()
	_check("совместимость ограничена креплением", compatible > 0 and WeaponDb.attach_block({"id": "wpn_hg_01", "mods": {}}, "optic_primary", "optic_holo_01") != "")
	var world_model: Node3D = WeaponModels.build("wpn_ar_02", {"optic_primary": {"id": "optic_holo_01", "dur": 100.0}}, 1)
	var lod: MeshInstance3D = world_model.find_child("Body_LOD1", true, false) as MeshInstance3D
	var body: MeshInstance3D = world_model.find_child("Body", true, false) as MeshInstance3D
	_check("мировая модель выбирает облегчённую сетку", lod != null and lod.visible and body != null and not body.visible and lod.mesh.get_faces().size() < body.mesh.get_faces().size())
	world_model.free()
	print("weapon_condition_test: ошибок %d" % _fails)
	get_tree().quit(_fails)
