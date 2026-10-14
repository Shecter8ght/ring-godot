extends Node
## ПМ v11: карты износа по прочности. 100 — карты, встроенные в pm.glb; 60 и 20 — states/pm_<поверхность>_<состояние>_*;
## магазин, патроны и глушитель — одно состояние 60 (решение владельца 2026-10-14) и не меняются.

var _fails: int = 0


func _check(label: String, ok: bool) -> void:
	print("  [%s] %s" % ["ok" if ok else "FAIL", label])
	if not ok:
		_fails += 1


func _albedo(model: Node3D, surface_name: String) -> String:
	for n: Node in model.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = n as MeshInstance3D
		if mi.mesh == null:
			continue
		for s: int in range(mi.mesh.get_surface_count()):
			var src: StandardMaterial3D = mi.mesh.surface_get_material(s) as StandardMaterial3D
			if src == null or not src.resource_name.begins_with("GAME • %s •" % surface_name):
				continue
			var mat: StandardMaterial3D = mi.get_active_material(s) as StandardMaterial3D
			if mat and mat.albedo_texture:
				return mat.albedo_texture.resource_path.get_file()
			return "-"
	return ""


func _ready() -> void:
	await get_tree().process_frame
	for dur: float in [100.0, 60.0, 20.0]:
		var model: Node3D = WeaponModels.build("wpn_hg_01", {}, 0, dur)
		add_child(model)
		WeaponCondition.apply_visual(model, {"id": "wpn_hg_01", "dur": dur})
		var steel: String = _albedo(model, "Steel")
		var grip: String = _albedo(model, "Grip")
		var mag: String = _albedo(model, "Magazine")
		print("PM ", dur, " steel=", steel, " grip=", grip, " mag=", mag)
		_check("сталь и щёчка найдены (%d)" % int(dur), steel != "" and grip != "")
		if dur < 100.0:
			_check("сталь %d — своя карта" % int(dur), steel == "pm_Steel_%d_albedo.png" % int(dur))
			_check("щёчка %d — своя карта" % int(dur), grip == "pm_Grip_%d_albedo.png" % int(dur))
		else:
			_check("100 — встроенные карты модели", steel.find("Steel_100") >= 0 and grip.find("Grip_100") >= 0)
		_check("магазин не меняется с прочностью (%d)" % int(dur), mag.find("Magazine_60") >= 0)
		model.queue_free()
	print("PM_STATE_MAPS ", "PASS" if _fails == 0 else "FAIL %d" % _fails)
	get_tree().quit(_fails)
