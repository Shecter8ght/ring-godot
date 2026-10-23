extends Node
## Вид оружия один (решение владельца 2026-10-19): при любой прочности модель показывает карты, принятые
## в Blender; износ по виду (маски _wear, ручные карты 60/20, налёт) удалён.
## ПМ «пошарпанный» v01 (2026-10-20): сталь, щёчка, магазин, патроны и глушитель — карты pm_<Атлас>_100_* с маской
## плёнки _coat — шейдер жировых следов. ВЕРАС-54 v13: то же на стали, полимере и магазине. Прежних файлов износа нет.

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


## Что видно на поверхности: «shader» или имя карты цвета StandardMaterial3D.
func _look(model: Node3D, surface_name: String) -> String:
	var found: Array = _surface(model, surface_name)
	if found.is_empty():
		return ""
	var mat: Material = (found[0] as MeshInstance3D).get_active_material(int(found[1]))
	if mat is ShaderMaterial:
		return "shader"
	if mat is StandardMaterial3D and (mat as StandardMaterial3D).albedo_texture:
		return (mat as StandardMaterial3D).albedo_texture.resource_path.get_file()
	return "-"


func _ready() -> void:
	await get_tree().process_frame
	for dur: float in [100.0, 47.0, 0.0]:
		var model: Node3D = WeaponModels.build(PM, {}, 0, dur)
		add_child(model)
		var steel: String = _look(model, "Steel")
		var grip: String = _look(model, "Grip")
		var mag: String = _look(model, "Magazine")
		print("PM ", dur, " steel=", steel, " grip=", grip, " mag=", mag)
		_check("ПМ %d %%: сталь — шейдер следов на картах 100" % int(dur), steel == "shader")
		_check("ПМ %d %%: щёчка — шейдер следов" % int(dur), grip == "shader")
		_check("ПМ %d %%: магазин — шейдер следов" % int(dur), mag == "shader")
		_check("ПМ %d %%: шейдер следов включён" % int(dur), model.get_meta("wear_shader", false))
		var coated: int = 0
		for n: Node in model.find_children("*", "MeshInstance3D", true, false):
			var mi: MeshInstance3D = n as MeshInstance3D
			for s: int in range(mi.mesh.get_surface_count() if mi.mesh else 0):
				var sm: ShaderMaterial = mi.get_active_material(s) as ShaderMaterial
				if sm and sm.shader.resource_path == WeaponCondition.WEAR_SHADER and sm.get_shader_parameter("coat_tex") != null:
					coated += 1
		_check("ПМ %d %%: карта следов у шейдерных поверхностей (%d)" % [int(dur), coated], coated >= 4)
		model.queue_free()
	for atlas: String in ["Steel", "Grip", "Magazine", "Ammo", "Suppressor"]:
		for kind: String in ["albedo", "normal", "orm", "coat"]:
			var path: String = "res://assets/models/weapons/pm/pm_%s_100_%s.png" % [atlas, kind]
			_check("карта ПМ есть: " + path.get_file(), ResourceLoader.exists(path))
	_check("ключ модели ПМ не зависит от прочности", WeaponCondition.model_key(PM, {}, 100.0) == WeaponCondition.model_key(PM, {}, 3.0))
	_check("у ПМ нет ручных карт состояний", not WeaponDb.weapon(PM).has("state_maps"))
	for path: String in ["res://assets/models/weapons/pm/states/pm_Steel_60_albedo.png", "res://assets/models/weapons/pm/pm.glb",
			"res://assets/models/weapons/pm/pm_pm_Steel_100_wear.png", "res://assets/textures/weapon_wear/wear_detail.png",
			"res://assets/models/weapons/veras54/veras54_Steel_100_wear.png", "res://assets/models/attachments/lumar_h1/lumar_20_base_color.png"]:
		_check("файла износа нет: " + path.get_file(), not ResourceLoader.exists(path))
	# ВЕРАС-54 v13: шейдер жировых следов на всех трёх атласах — при любой прочности одинаково
	for dur: float in [100.0, 20.0]:
		var veras: Node3D = WeaponModels.build(VERAS, {}, 0, dur)
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
		_check("ВЕРАС-54 %d %%: шейдер следов (%d поверхн.)" % [int(dur), shaded], shaded >= 3 and veras.get_meta("wear_shader", false))
		_check("ВЕРАС-54 %d %%: у всех шейдерных поверхностей — карта следов" % int(dur), coated == shaded)
		veras.queue_free()
	print("PM_STATE_MAPS ", "PASS" if _fails == 0 else "FAIL %d" % _fails)
	get_tree().quit(_fails)
