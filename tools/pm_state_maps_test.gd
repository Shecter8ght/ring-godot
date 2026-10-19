extends Node
## Вид один (решение владельца 2026-10-19): при любой прочности карты как есть — шейдер получает прочность 1,
## выстрел её не меняет. Ниже — прежний вид по прочности (WeaponCondition.visual_wear, выключен в игре;
## остался для инструментов сравнения), проверяется с включённым флагом.
## ПМ v11: вид по прочности. Сталь и щёчка — шейдер износа по маске pm_pm_<поверхность>_100_wear.png
## (решение владельца 2026-10-17) при любой прочности, плавно; выстрел меняет прочность в шейдере без
## пересборки модели. Ручные карты 60 и 20 (states/pm_<поверхность>_<состояние>_*) остаются и подставляются
## прежним путём (для сравнения). Магазин, патроны и глушитель — одно состояние 60 и не меняются.
## ВЕРАС-54 v13 (2026-10-19) — тоже на шейдере: маски _wear и жировая плёнка _coat (слой Clearcoat).

const PM: String = "wpn_hg_01"
const VERAS: String = "wpn_ar_01"

var _fails: int = 0


func _check(label: String, ok: bool) -> void:
	print("  [%s] %s" % ["ok" if ok else "FAIL", label])
	if not ok:
		_fails += 1


## Первая поверхность модели с исходным материалом «GAME • <поверхность> • …»: [узел, номер поверхности].
func _surface(model: Node3D, surface_name: String) -> Array:
	for n: Node in model.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = n as MeshInstance3D
		if mi.mesh == null:
			continue
		for s: int in range(mi.mesh.get_surface_count()):
			var src: StandardMaterial3D = mi.mesh.surface_get_material(s) as StandardMaterial3D
			if src and src.resource_name.begins_with("GAME • %s •" % surface_name):
				return [mi, s]
	return []


## Что видно на поверхности: «shader:<маска>» или имя карты цвета StandardMaterial3D.
func _look(model: Node3D, surface_name: String) -> String:
	var found: Array = _surface(model, surface_name)
	if found.is_empty():
		return ""
	var mat: Material = (found[0] as MeshInstance3D).get_active_material(int(found[1]))
	if mat is ShaderMaterial:
		var mask: Texture2D = (mat as ShaderMaterial).get_shader_parameter("wear_tex") as Texture2D
		return "shader:" + (mask.resource_path.get_file() if mask else "-")
	if mat is StandardMaterial3D and (mat as StandardMaterial3D).albedo_texture:
		return (mat as StandardMaterial3D).albedo_texture.resource_path.get_file()
	return "-"


func _condition(model: Node3D, surface_name: String) -> float:
	var found: Array = _surface(model, surface_name)
	if found.is_empty():
		return -1.0
	return float((found[0] as MeshInstance3D).get_instance_shader_parameter("condition"))


func _ready() -> void:
	await get_tree().process_frame
	WeaponCondition.visual_wear = false
	for dur: float in [100.0, 47.0, 0.0]:
		var one: Node3D = WeaponModels.build(PM, {}, 0, dur)
		add_child(one)
		_check("один вид (%d): сталь и щёчка — карты как есть, прочность в шейдере 1" % int(dur), _look(one, "Steel") == "shader:pm_pm_Steel_100_wear.png"
				and is_equal_approx(_condition(one, "Steel"), 1.0) and is_equal_approx(_condition(one, "Grip"), 1.0))
		WeaponCondition.update_wear(one, 12.0)
		_check("один вид (%d): выстрел вид не меняет" % int(dur), is_equal_approx(_condition(one, "Steel"), 1.0))
		one.queue_free()
	# дальше — прежний вид по прочности
	WeaponCondition.visual_wear = true
	for dur: float in [100.0, 60.0, 47.0, 20.0, 0.0]:
		var model: Node3D = WeaponModels.build(PM, {}, 0, dur)
		add_child(model)
		var steel: String = _look(model, "Steel")
		var grip: String = _look(model, "Grip")
		var mag: String = _look(model, "Magazine")
		print("PM ", dur, " steel=", steel, " grip=", grip, " mag=", mag, " condition=", _condition(model, "Steel"))
		_check("сталь — шейдер по маске (%d)" % int(dur), steel == "shader:pm_pm_Steel_100_wear.png")
		_check("щёчка — шейдер по маске (%d)" % int(dur), grip == "shader:pm_pm_Grip_100_wear.png")
		_check("прочность в шейдере = %d %%" % int(dur), is_equal_approx(_condition(model, "Steel"), dur / 100.0) and is_equal_approx(_condition(model, "Grip"), dur / 100.0))
		_check("магазин не меняется с прочностью (%d)" % int(dur), mag.find("Magazine_60") >= 0)
		model.queue_free()
	# выстрел: ресурс меняется, модель та же (ключ модели держит только ступень вида)
	var model: Node3D = WeaponModels.build(PM, {}, 0, 58.0)
	add_child(model)
	var before: Material = (_surface(model, "Steel")[0] as MeshInstance3D).get_active_material(int(_surface(model, "Steel")[1]))
	WeaponCondition.update_wear(model, 41.5)
	_check("update_wear: прочность 41.5 % без пересборки", is_equal_approx(_condition(model, "Steel"), 0.415))
	WeaponCondition.apply_visual(model, {"id": PM, "dur": 33.0})
	_check("apply_visual на готовой модели — только прочность", is_equal_approx(_condition(model, "Grip"), 0.33))
	var after: Material = (_surface(model, "Steel")[0] as MeshInstance3D).get_active_material(int(_surface(model, "Steel")[1]))
	_check("материал общий и не пересоздаётся", before == after)
	model.queue_free()
	# ручные карты ПМ — прежним путём, для сравнения
	var maps: String = String(WeaponDb.weapon(PM).get("state_maps", ""))
	for visual: int in [60, 20]:
		var hand: Node3D = WeaponModels.build(PM, {}, 0, 100.0)
		add_child(hand)
		_check("ручные карты %d подставляются" % visual, WeaponCondition._apply_state_maps(hand, maps, visual))
		_check("сталь %d — своя карта" % visual, _look(hand, "Steel") == "pm_Steel_%d_albedo.png" % visual)
		_check("щёчка %d — своя карта" % visual, _look(hand, "Grip") == "pm_Grip_%d_albedo.png" % visual)
		hand.queue_free()
	# ВЕРАС-54 v13: сталь, полимер и магазин — шейдер износа по своим маскам, у стали и полимера — жировая плёнка
	var veras: Node3D = WeaponModels.build(VERAS, {}, 0, 60.0)
	add_child(veras)
	var shaded: int = 0
	var coated: int = 0
	for n: Node in veras.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = n as MeshInstance3D
		for s: int in range(mi.mesh.get_surface_count() if mi.mesh else 0):
			var sm: ShaderMaterial = mi.get_active_material(s) as ShaderMaterial
			if sm and sm.shader.resource_path == WeaponCondition.WEAR_SHADER:
				shaded += 1
				if sm.get_shader_parameter("coat_tex") != null:
					coated += 1
	_check("ВЕРАС-54 v13 — шейдер износа (%d поверхн.)" % shaded, shaded >= 3 and veras.get_meta("wear_shader", false))
	_check("ВЕРАС-54 v13 — жировая плёнка у %d поверхн." % coated, coated >= 2)
	veras.queue_free()
	print("PM_STATE_MAPS ", "PASS" if _fails == 0 else "FAIL %d" % _fails)
	get_tree().quit(_fails)
