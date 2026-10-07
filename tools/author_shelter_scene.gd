extends Node
## Офлайн-авторинг: перевод GLB в законченные ArrayMesh-сцены и запись фиксированного уровня.
## Запускается вручную при производстве; финальный уровень не зависит от этого инструмента.

const BASE: String = "res://levels/shelter/"
const MODELS: String = "res://assets/shelter/models/"
const TEXTURES: String = "res://assets/shelter/textures/"
var _materials: Dictionary = {}
var _kit: Dictionary = {}
var _root: Node3D
var _props: int = 0
var _placements: Array[Dictionary] = []

func _ready() -> void:
	await get_tree().process_frame
	Profile.use_file("user://shelter_author_test.json", true)
	_make_materials()
	# только материалы (шейдер старения, настройки) — сцена и меши ссылаются на них по пути
	if OS.get_environment("SHELTER_MATERIALS_ONLY") != "":
		get_tree().quit()
		return
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(MODELS + "manifest.json")) as Dictionary
	for id: String in manifest:
		_convert_asset(id, manifest[id])
	_bake_display_weapon("wpn_ar_03")
	_bake_display_weapon("wpn_hg_01")
	_root = Node3D.new()
	_root.name = "Shelter_Interior"
	add_child(_root)
	for name: String in ["Architecture", "Props", "Lights", "Activities", "Stations", "ReflectionProbes", "Navigation", "Gameplay", "Signs", "Audio"]:
		_group(name, _root)
	_layout(manifest)
	_detail_pass()
	_floor_joints()
	_gameplay()
	_lighting()
	_environment()
	_signage()
	_boiler_hall()
	_navigation()
	await get_tree().physics_frame
	var region: NavigationRegion3D = _root.get_node("Navigation/Interior") as NavigationRegion3D
	region.bake_navigation_mesh(false)
	await get_tree().process_frame
	ShelterSave.save(region.navigation_mesh, BASE + "architecture/interior_nav.tres")
	var rig: Node = (load("res://scenes/player/camera_rig.tscn") as PackedScene).instantiate()
	_root.add_child(rig)
	rig.owner = _root
	var spawn: Marker3D = Marker3D.new()
	spawn.name = "Spawn"
	spawn.position = Vector3(0, 0.08, 9.55)
	_owned(_root, spawn)
	_root.set_script(load("res://src/hideout/hideout_level.gd"))
	var packed: PackedScene = PackedScene.new()
	var result: Error = packed.pack(_root)
	assert(result == OK)
	assert(ShelterSave.save(packed, BASE + "Shelter_Interior.tscn") == OK)
	var f: FileAccess = FileAccess.open(BASE + "placements.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(_placements, "\t"))
	var stats: Dictionary = {"authored_assets": manifest.size(), "prop_instances": _props, "lights": _root.get_node("Lights").get_child_count(), "reflection_probes": _root.get_node("ReflectionProbes").get_child_count(), "navigation_polygons": region.navigation_mesh.get_polygon_count(), "gi": "SDFGI + SSIL (existing Forward+ pipeline)", "procedural_level_generation": false}
	f = FileAccess.open("res://docs/shelter/scene_stats.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(stats, "\t"))
	print("SHELTER_AUTHORED " + JSON.stringify(stats))
	get_tree().quit()


func _owned(parent: Node, child: Node) -> void:
	parent.add_child(child)
	if _root.is_ancestor_of(child):
		child.owner = _root

func _group(label: String, parent: Node) -> Node3D:
	var n: Node3D = Node3D.new()
	n.name = label
	_owned(parent, n)
	return n

func _make_materials() -> void:
	var names: Array[String] = ["RawConcrete", "PaintedConcrete", "DampConcrete", "WetConcrete", "IndustrialConcreteFloor", "PaintedSteel", "OchreSteel", "BareSteel", "RustedSteel", "GalvanizedSteel", "DirtyAluminum", "OldWood", "RawWood", "Rubber", "OldPlastic", "Canvas", "MilitaryFabric", "Leatherette", "Glass", "Oil", "PuddleWater", "WornCarpet", "Paper", "Cardboard", "RedPaint", "IndustrialTrim", "Labels", "PlanningMap", "RoomSigns", "WarmEmitter", "CoolEmitter", "Screen",
		# котельная зоны 5 и тир (tools/shelter_boiler_materials.py)
		"Brick", "Whitewash", "PeelingPaint", "BoilerSteel", "FlueRust", "WiredGlass", "ButtonGreen", "ButtonRed", "ButtonYellow", "RangePaper"]
	for label: String in names:
		var m: StandardMaterial3D = StandardMaterial3D.new()
		m.resource_name = label
		m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
		var extension: String = ".png" if label in ["IndustrialTrim", "Labels", "PlanningMap", "RoomSigns", "RangePaper"] else ".jpg"
		if ResourceLoader.exists(TEXTURES + label + "_base" + extension):
			m.albedo_texture = load(TEXTURES + label + "_base" + extension)
		if ResourceLoader.exists(TEXTURES + label + "_normal" + extension):
			m.normal_enabled = true
			m.normal_texture = load(TEXTURES + label + "_normal" + extension)
			m.normal_scale = 0.4 if label in ["RawConcrete", "PaintedConcrete"] else 0.32
		if ResourceLoader.exists(TEXTURES + label + "_orm" + extension):
			var orm: Texture2D = load(TEXTURES + label + "_orm" + extension)
			m.roughness_texture = orm
			m.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
			m.metallic_texture = orm
			m.metallic_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_BLUE
			m.metallic = 1.0
			m.roughness = 1.0
			m.ao_enabled = true
			m.ao_texture = orm
		if label.ends_with("Emitter"):
			m.emission_enabled = true
			m.emission = Color(1, 0.9, 0.77) if label == "WarmEmitter" else Color(0.87, 0.92, 1.0)
			m.emission_energy_multiplier = 2.4
			m.albedo_color = m.emission
		if label == "Screen":
			m.albedo_color = Color(0.007, 0.009, 0.006)
		if label in ["Oil", "PuddleWater", "WetConcrete", "Glass"]:
			m.metallic_specular = 0.55
		if label in ["IndustrialConcreteFloor", "RawConcrete", "PaintedConcrete", "DampConcrete", "Brick", "Whitewash", "PeelingPaint"]:
			m.metallic_specular = 0.35
		if label == "Brick":
			m.normal_scale = 0.7
		if label == "WiredGlass":
			# матовое армированное стекло светится рассеянным дневным светом снаружи котельной
			m.emission_enabled = true
			m.emission_texture = m.albedo_texture
			m.emission = Color(0.80, 0.86, 0.92)
			m.emission_energy_multiplier = 0.16
			m.albedo_color = Color(0.62, 0.64, 0.64, 0.5)
			m.metallic_specular = 0.6
			# полупрозрачное — пропускает солнце (ShelterWeather): на полу пятна с тенью переплёта
			m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		if label == "RangePaper":
			# лист тира: пробоины рисуются в копию этой текстуры, поэтому без сжатия на видеокарте
			m.cull_mode = BaseMaterial3D.CULL_DISABLED
		# Стены, пол и потолок стареют в шейдере (AGED): пятна, грязь у пола, подтёки, копоть.
		var final: Material = _aged(m, AGED[label]) if AGED.has(label) else m
		# Материал cutaway отдельный от пола/декора с тем же физическим составом.
		ShelterSave.save(final, BASE + "materials/" + label + ".tres")
		_materials[label] = load(BASE + "materials/" + label + ".tres")
		if label in ["RawConcrete", "PaintedConcrete", "DampConcrete", "BareSteel", "Brick", "Whitewash", "PeelingPaint"]:
			var cut: Material = final.duplicate()
			cut.resource_name = label + "_cut"
			if cut is BaseMaterial3D:
				(cut as BaseMaterial3D).distance_fade_mode = BaseMaterial3D.DISTANCE_FADE_PIXEL_DITHER
			ShelterSave.save(cut, BASE + "materials/" + label + "_cut.tres")
			_materials[label + "_cut"] = load(BASE + "materials/" + label + "_cut.tres")
	# Манекены тира — матовый литой пластик без лица (RangeTarget перекрывает им все поверхности).
	var plastic: StandardMaterial3D = StandardMaterial3D.new()
	plastic.resource_name = "MannequinPlastic"
	plastic.albedo_color = Color(0.74, 0.70, 0.64)
	plastic.roughness = 0.58
	plastic.metallic_specular = 0.45
	plastic.rim_enabled = true
	plastic.rim = 0.12
	ShelterSave.save(plastic, BASE + "materials/MannequinPlastic.tres")


var _two_sided: StandardMaterial3D

## Материал «тень с обеих сторон» для тени потолков (видимой поверхности у него нет).
func _two_sided_shadow() -> StandardMaterial3D:
	if _two_sided == null:
		_two_sided = StandardMaterial3D.new()
		_two_sided.resource_name = "TwoSidedShadow"
		_two_sided.cull_mode = BaseMaterial3D.CULL_DISABLED
		_two_sided.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		ShelterSave.save(_two_sided, BASE + "materials/TwoSidedShadow.tres")
		_two_sided = load(BASE + "materials/TwoSidedShadow.tres")
	return _two_sided


## Старение по материалам (assets/shelter/shaders/aged_surface.gdshader): грязь у пола, подтёки,
## копоть стен и потолка, вытертость пола, сила пятен. Побелка показывает подтёки сильнее всех.
const AGED: Dictionary = {
	"Brick": {"base_grime": 0.65, "streaks": 0.5, "soot": 0.5, "soot_ceiling": 0.0},
	"Whitewash": {"base_grime": 0.75, "streaks": 0.75, "soot": 0.6, "soot_ceiling": 0.0, "macro_amount": 0.22},
	"PeelingPaint": {"base_grime": 0.6, "streaks": 0.5, "soot": 0.45, "soot_ceiling": 0.0},
	"PaintedConcrete": {"base_grime": 0.6, "streaks": 0.45, "soot": 0.45, "soot_ceiling": 0.3},
	"RawConcrete": {"base_grime": 0.5, "streaks": 0.35, "soot": 0.4, "soot_ceiling": 0.4},
	"DampConcrete": {"base_grime": 0.65, "streaks": 0.55, "soot": 0.35, "soot_ceiling": 0.35},
	"IndustrialConcreteFloor": {"base_grime": 0.0, "streaks": 0.0, "soot": 0.0, "soot_ceiling": 0.0, "floor_wear": 0.55, "macro_amount": 0.3},
}
const AGED_SHADER: String = "res://assets/shelter/shaders/aged_surface.gdshader"
const GRIME: String = "res://assets/shelter/textures/grime/"


## ShaderMaterial старения с текстурами и настройками исходного StandardMaterial3D.
func _aged(m: StandardMaterial3D, tune: Dictionary) -> ShaderMaterial:
	var sm: ShaderMaterial = ShaderMaterial.new()
	sm.resource_name = m.resource_name
	sm.shader = load(AGED_SHADER)
	sm.set_shader_parameter("has_albedo", m.albedo_texture != null)
	if m.albedo_texture:
		sm.set_shader_parameter("albedo_tex", m.albedo_texture)
	sm.set_shader_parameter("albedo_color", m.albedo_color)
	sm.set_shader_parameter("has_normal", m.normal_enabled and m.normal_texture != null)
	if m.normal_texture:
		sm.set_shader_parameter("normal_tex", m.normal_texture)
	sm.set_shader_parameter("normal_scale", m.normal_scale)
	sm.set_shader_parameter("has_orm", m.roughness_texture != null)
	if m.roughness_texture:
		sm.set_shader_parameter("orm_tex", m.roughness_texture)
	sm.set_shader_parameter("roughness", m.roughness)
	sm.set_shader_parameter("specular", m.metallic_specular)
	sm.set_shader_parameter("macro_tex", load(GRIME + "macro.png"))
	sm.set_shader_parameter("streak_tex", load(GRIME + "streaks.png"))
	for key: String in tune:
		sm.set_shader_parameter(key, tune[key])
	return sm


func _convert_asset(id: String, info: Dictionary) -> void:
	var original: Node3D = (load(MODELS + id + ".glb") as PackedScene).instantiate() as Node3D
	var root: Node3D = Node3D.new()
	root.name = id
	var cut: bool = id.begins_with("Wall_") or id == "TechnicalStructure"
	var index: int = 0
	for node: Node in original.find_children("*", "MeshInstance3D", true, false):
		var source: MeshInstance3D = node as MeshInstance3D
		var mi: MeshInstance3D = MeshInstance3D.new()
		mi.name = "Screen" if source.name == &"Screen" else "FinishedMesh_%02d" % index
		var mesh: ArrayMesh = source.mesh.duplicate() as ArrayMesh
		for surface: int in range(mesh.get_surface_count()):
			var material: Material = source.mesh.surface_get_material(surface)
			if bool(info.get("external", false)):
				var pbr: StandardMaterial3D = material.duplicate() as StandardMaterial3D
				pbr.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
				mesh.surface_set_material(surface, pbr)
				continue
			var label: String = material.resource_name
			if cut and _materials.has(label + "_cut"):
				label += "_cut"
			assert(_materials.has(label), id + ": " + label)
			mesh.surface_set_material(surface, _materials[label])
		var mesh_path: String = BASE + "props/" + id + "_%02d.res" % index
		var saved: Error = ShelterSave.save(mesh, mesh_path)
		# Windows может кратко удерживать ресурс во время импорта/индексации.
		for attempt: int in range(3):
			if saved == OK: break
			OS.delay_msec(100)
			saved = ShelterSave.save(mesh, mesh_path)
		assert(saved == OK, "Не сохранён mesh: " + mesh_path)
		mi.mesh = load(mesh_path)
		var t: Transform3D = source.transform
		var ancestor: Node3D = source.get_parent() as Node3D
		while ancestor and ancestor != original:
			t = ancestor.transform * t
			ancestor = ancestor.get_parent() as Node3D
		mi.transform = t
		mi.gi_mode = GeometryInstance3D.GI_MODE_STATIC
		if id.begins_with("Ceiling_") or id in ["Ventilation", "PipesAndElectrical", "PracticalLight", "PH_HangingLamp", "PH_Crane"]:
			mi.layers = SectorBuilder.CEILING_LAYER
		if cut:
			mi.set_meta("shelter_cut", true)
		# стены — тень с обеих сторон: солнце снаружи видит их изнанку
		if id.begins_with("Wall_"):
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_DOUBLE_SIDED
		if id.begins_with("RoomSign_"):
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		if id in ["Mug", "FoodCan", "Notebook", "WaterBottle", "Beer", "Boots", "PlanningMap", "Rug", "PH_Cans", "PH_Binoculars", "PH_Gloves", "PH_Clipboard", "PH_Multimeter", "PH_OilTin", "PH_PipeWrench", "PH_Thermos", "RangeConsole"]:
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(mi)
		mi.owner = root
		if id.begins_with("Ceiling_"):
			var shadow: MeshInstance3D = MeshInstance3D.new()
			shadow.name = "CeilingShadow"
			shadow.mesh = mi.mesh
			shadow.transform = mi.transform
			shadow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
			# потолок — плоскость лицом вниз; солнце сверху видит изнанку, а она без этого в тень не
			# попадает: свет шёл сквозь потолки во все комнаты (замечание владельца 2026-10-07)
			shadow.material_override = _two_sided_shadow()
			shadow.gi_mode = GeometryInstance3D.GI_MODE_STATIC
			root.add_child(shadow)
			shadow.owner = root
		index += 1
	if not (info.collisions as Array).is_empty():
		var body: StaticBody3D = StaticBody3D.new()
		body.name = "SimplifiedCollision"
		body.collision_layer = 1
		body.collision_mask = 0
		root.add_child(body)
		body.owner = root
		for entry: Dictionary in info.collisions:
			var cs: CollisionShape3D = CollisionShape3D.new()
			cs.name = "Hull_%02d" % body.get_child_count()
			var shape: BoxShape3D = BoxShape3D.new()
			shape.size = _v(entry.size)
			cs.shape = shape
			cs.position = _v(entry.pos)
			cs.rotation_degrees.y = float(entry.yaw)
			body.add_child(cs)
			cs.owner = root
	var packed: PackedScene = PackedScene.new()
	assert(packed.pack(root) == OK)
	var path: String = BASE + ("architecture/" if _is_architecture(id) else "props/") + id + ".tscn"
	assert(ShelterSave.save(packed, path) == OK)
	_kit[id] = load(path)
	root.free()
	original.free()


func _v(a: Array) -> Vector3:
	return Vector3(float(a[0]), float(a[1]), float(a[2]))

## Сборки, которые стоят в нуле уровня как часть здания (стены, перекрытия, инженерия, зал).
func _is_architecture(id: String) -> bool:
	return id.begins_with("Floor_") or id.begins_with("Wall_") or id.begins_with("Ceiling_") or id in ["Ventilation", "PipesAndElectrical", "StairsAndRailing", "TechnicalStructure", "DrainsAndThresholds", "HallStructure"]

## Самодельные предметы, вместо которых теперь стоят модели Poly Haven (CC0) того же назначения.
const REPLACE: Dictionary = {"Chair": "PH_Chair", "Boots": "PH_Boots", "FoodCan": "PH_Cans", "JerryCan": "PH_JerryCan",
	"MedicalCase": "PH_MedicalBox", "Radio": "PH_Radio", "DeskLamp": "PH_DeskLamp", "Case": "PH_MilitaryCrate",
	"CardboardBox": "PH_Carton", "Bench": "PH_Bench", "CoffeeTable": "PH_CoffeeTable", "Binoculars": "PH_Binoculars"}

func _put(id: String, label: String, parent: Node, at: Vector3, yaw: float = 0.0) -> Node3D:
	if REPLACE.has(id) and _kit.has(String(REPLACE[id])):
		id = String(REPLACE[id])
	var n: Node3D = (_kit[id] as PackedScene).instantiate() as Node3D
	n.name = label
	n.position = at
	n.rotation_degrees.y = yaw
	_owned(parent, n)
	_props += 1
	_placements.append({"name": label, "asset": id, "position": [at.x, at.y, at.z], "yaw": yaw})
	if n.has_node("SimplifiedCollision") and not id.begins_with("Ceiling_"):
		n.add_to_group("shelter_navigation_geometry", true)
	return n


func _layout(manifest: Dictionary) -> void:
	var arch: Node = _root.get_node("Architecture")
	for id: String in manifest:
		if _is_architecture(id):
			var n: Node3D = _put(id, "SH_Int_" + id, arch, Vector3.ZERO)
	var p: Node = _root.get_node("Props")
	var hub: Node3D = _group("SH_Int_MainHub", p)
	var planning_rug: Node3D = _put("Rug", "PlanningRug", hub, Vector3.ZERO)
	planning_rug.scale = Vector3(1.35,1,1.35)
	var planning_table: Node3D = _put("PlanningTable", "PlanningTable", hub, Vector3.ZERO)
	planning_table.scale = Vector3(1.5,1,2.0)
	var planning_map: Node3D = _put("PlanningMap", "PlanningMap", hub, Vector3(0, 0.755, 0))
	planning_map.scale = Vector3(1.5,1,2.0)
	for spec: Array in [[-2.35, 0, 90], [2.35, 0, -90], [-1.05, 1.7, 0], [1.05, -1.7, 180],[-1.05,-1.7,180],[1.05,1.7,0]]:
		_put("Chair", "PlanningChair_%02d" % hub.get_child_count(), hub, Vector3(float(spec[0]), 0, float(spec[1])), float(spec[2]))
	_put("Mug", "PlanningMug", hub, Vector3(0.91, 0.79, 0.32))
	_put("Notebook", "RouteNotebook", hub, Vector3(-0.85, 0.79, 0.28), 14)
	_put("Radio", "FieldRadio", hub, Vector3(-0.75, 0.79, -0.26), 8)
	_put("Case", "UnderTableCase", hub, Vector3(0.38, 0, 0.03))
	var living: Node3D = _group("SH_Int_Living", p)
	_put("Rug", "LivingRug", living, Vector3(-13.2, 0, -8.0))
	_put("PH_Sofa", "Couch", living, Vector3(-13.3, 0, -7.55), 180)
	_put("PH_Armchair", "LivingArmchair", living, Vector3(-15.65, 0, -8.65), 100)
	_put("CoffeeTable", "CoffeeTable", living, Vector3(-13.3, 0, -8.75))
	_put("Counter", "TVStand", living, Vector3(-13.3, 0, -10.1))
	_put("Mug", "TeaMug", living, Vector3(-13.6, .49, -8.8))
	_put("Notebook", "LivingMagazine", living, Vector3(-13.0, .49, -8.9), 18)
	_put("Shelf", "LivingPersonalShelf", living, Vector3(-17.4, 0, -8), 90)
	_put("Backpack", "PersonalBag", living, Vector3(-17.2, .69, -8.3), 90)
	var trader: Node3D = _group("SH_Int_Trader", p)
	_put("Counter", "TraderCounter", trader, Vector3(-12.4, 0, -2.0))
	_put("Chair", "TraderChair", trader, Vector3(-12.4, 0, -3.35))
	for x: float in [-16.6, -14.8, -13.0]:
		_put("Shelf", "TraderGoods_%02d" % trader.get_child_count(), trader, Vector3(x, 0, -4.45))
		_put("CardboardBox", "TradeCarton_%02d" % trader.get_child_count(), trader, Vector3(x, .66, -4.45))
		_put("MedicalCase", "TradeMedical_%02d" % trader.get_child_count(), trader, Vector3(x+.25, 1.13, -4.4))
	_put("Notebook", "TraderLedger", trader, Vector3(-11.65, .97, -2.1), 12)
	_put("Mug", "TraderMug", trader, Vector3(-13.15, .97, -2.12))
	_put("Case", "TradeCase", trader, Vector3(-16.9, 0, -1.3))
	var workshop: Node3D = _group("SH_Int_Workshop", p)
	_put("Workbench", "Workbench", workshop, Vector3(13.7, 0, -4.25))
	_put("Shelf", "WorkshopPartsShelf", workshop, Vector3(17.4, 0, -2.0), -90)
	_put("Case", "ToolCase", workshop, Vector3(17.4, .66, -2))
	_put("JerryCan", "WorkshopOilCan", workshop, Vector3(14.4, 0, -3.8))
	_put("Notebook", "WorkshopManual", workshop, Vector3(13.9, .95, -4.1))
	_put("Bench", "WorkshopBench", workshop, Vector3(11.0, 0, -4.35))
	var armory: Node3D = _group("SH_Int_Armory", p)
	_put("WeaponRack", "WeaponRack_01", armory, Vector3(-13.8, 0, 1.5))
	_put("WeaponRack", "WeaponRack_02", armory, Vector3(-16.5, 0, 1.5))
	_put("PlanningTable", "MaintenanceTable", armory, Vector3(-12.2, 0, 4.1))
	for x: float in [-16.5, -15.7]:
		_put("Locker", "ArmoryLocker_%02d" % armory.get_child_count(), armory, Vector3(x, 0, 6.35), 180)
	_put("Case", "AmmoCase", armory, Vector3(-11.6, .76, 4.1))
	_put("Backpack", "ArmoryGear", armory, Vector3(-16.1, 0, 5.5))
	var storage: Node3D = _group("SH_Int_Storage", p)
	for x: float in [10.2, 12.0, 13.8, 15.6]:
		_put("Shelf", "StorageShelf_%02d" % storage.get_child_count(), storage, Vector3(x, 0, 6.3), 180)
		_put("Case", "StorageCase_%02d" % storage.get_child_count(), storage, Vector3(x, .18, 6.3), 180)
		_put("CardboardBox", "StorageCarton_%02d" % storage.get_child_count(), storage, Vector3(x, 1.14, 6.3), 180)
	for x: float in [10.05, 10.4, 10.75]:
		_put("WaterBottle", "WaterSupply_%02d" % storage.get_child_count(), storage, Vector3(x, .69, 6.3))
		_put("FoodCan", "FoodSupply_%02d" % storage.get_child_count(), storage, Vector3(x+1.8, .69, 6.3))
	_put("MedicalCase", "MedicalSupplies", storage, Vector3(13.7, 1.63, 6.3), 180)
	_put("Bench", "StorageSortBench", storage, Vector3(10.6, 0, 2.4), 0)
	var generator: Node3D = _group("SH_Int_Generator", p)
	_put("Generator", "Generator", generator, Vector3(13.8, 0, -8.5))
	_put("ElectricalCabinet", "Switchboard", generator, Vector3(17.4, 0, -7.9), -90)
	_put("ElectricalCabinet", "DistributionPanel", generator, Vector3(17.4, 0, -6.5), -90)
	for at: Vector3 in [Vector3(15.9,0,-10.3),Vector3(16.4,0,-10.3),Vector3(16.9,0,-10.3)]:
		_put("JerryCan", "FuelReserve_%02d" % generator.get_child_count(), generator, at)
	_put("IndustrialFan", "GeneratorVent", generator, Vector3(13.5, 1.9, -10.75))
	var sleeping: Node3D = _group("SH_Int_Sleeping", p)
	for x: float in [-2.15, 0.0, 2.15]:
		_put("Bed", "SleepingPosition_%02d" % sleeping.get_child_count(), sleeping, Vector3(x, 2.6, -9.35))
		_put("Boots", "SleepingBoots_%02d" % sleeping.get_child_count(), sleeping, Vector3(x+.55, 2.6, -8.5))
		_put("Case", "PersonalCase_%02d" % sleeping.get_child_count(), sleeping, Vector3(x, 2.6, -10.65))
	var bays: Node3D = _group("SH_Int_EquipmentBays", p)
	for i: int in range(3):
		var x: float = [-5.1, 5.1, 7.4][i]
		_put("Locker", "Bay_%02d_Locker" % (i+1), bays, Vector3(x, 0, 7.65), 180)
		_put("Backpack", "Bay_%02d_Pack" % (i+1), bays, Vector3(x-.58, .65, 7.6), 180)
		_put("Boots", "Bay_%02d_Boots" % (i+1), bays, Vector3(x, 0, 6.9), 180)
	var entry: Node3D = _group("SH_Int_Entry", p)
	_put("BlastDoor", "EntryBlastDoor", entry, Vector3(0, 0, 11.72))
	_put("Bench", "UnloadingBench", entry, Vector3(-3.5, 0, 9.9), 90)
	_put("Locker", "ReturnLocker", entry, Vector3(3.5, 0, 10.75), -90)
	_put("Case", "UnloadingCase", entry, Vector3(-2.5, 0, 11.35))
	_put("ElectricalCabinet", "EntryFusebox", entry, Vector3(3.5, .25, 8.85), -90)
	# Недоступные технические двери показывают продолжение объекта без наружного уровня.
	for spec: Array in [[-15.1,-10.74,0],[-4.95,-10.74,0],[4.95,-10.74,0]]:
		_put("BlastDoor", "ServiceDoor_%02d" % p.get_child_count(), p, Vector3(float(spec[0]),0,float(spec[1])), float(spec[2]))
	# Плавный скрытый collider лестницы: ступени дают рисунок, физика не застревает на riser.
	var body: StaticBody3D = StaticBody3D.new()
	body.name = "StairRampCollision"
	_owned(arch, body)
	body.add_to_group("shelter_navigation_geometry", true)
	var shape: ConvexPolygonShape3D = ConvexPolygonShape3D.new()
	shape.points = PackedVector3Array([Vector3(4.4,0,-2.15),Vector3(6.2,0,-2.15),Vector3(4.4,2.6,-6.2),Vector3(6.2,2.6,-6.2),Vector3(4.4,2.6,-6.7),Vector3(6.2,2.6,-6.7),Vector3(4.4,0,-6.7),Vector3(6.2,0,-6.7)])
	var cs: CollisionShape3D = CollisionShape3D.new()
	cs.name = "Ramp"
	cs.shape = shape
	_owned(body, cs)
	var guards: StaticBody3D = StaticBody3D.new()
	guards.name = "StairAndMezzanineGuardrails"
	_owned(arch,guards)
	guards.add_to_group("shelter_navigation_geometry",true)
	for x: float in [4.35,6.25]:
		var barrier: ConvexPolygonShape3D = ConvexPolygonShape3D.new()
		var points: PackedVector3Array = PackedVector3Array()
		for side: float in [-.05,.05]:
			for endpoint: Vector2 in [Vector2(-2.15,0),Vector2(-6.7,2.6)]:
				for height: float in [0,1.1]:
					points.append(Vector3(x+side,endpoint.y+height,endpoint.x))
		barrier.points = points
		var guard: CollisionShape3D = CollisionShape3D.new()
		guard.name = "StairSide_%02d" % guards.get_child_count()
		guard.shape = barrier
		_owned(guards,guard)
	for spec: Array in [[Vector3(-2,3.15,-7),Vector3(2,1.1,.07)],[Vector3(1,3.15,-6.5),Vector3(4,1.1,.07)],[Vector3(0,3.15,-10.8),Vector3(6,1.1,.07)],[Vector3(3.7,3.15,-6.5),Vector3(1.3,1.1,.07)],[Vector3(4.7,3.15,-8.1),Vector3(3.4,1.1,.07)]]:
		var box: BoxShape3D = BoxShape3D.new()
		box.size = spec[1]
		var guard: CollisionShape3D = CollisionShape3D.new()
		guard.name = "UpperEdge_%02d" % guards.get_child_count()
		guard.position = spec[0]
		guard.shape = box
		_owned(guards,guard)


func _gameplay() -> void:
	var stations: Node = _root.get_node("Stations")
	for spec: Array in [["StashStation",0,"Тайник и снаряжение",Vector3(12,.75,5.35)],["WorkbenchStation",3,"Верстак — обвесы",Vector3(13.7,.85,-3.7)],["TraderStation",1,"Михалыч — торговля и задания",Vector3(-12.4,.80,-1.2)],["ExitStation",2,"Планирование рейда",Vector3(0,.65,1.3)],["UpgradeStation",4,"Модули убежища",Vector3(16.1,.80,-6.5)],["WeaponStorage",0,"Оружейная — тайник",Vector3(-13.8,.8,2.4)],["EntryLoadout",0,"Разгрузка и снаряжение",Vector3(-2.6,.5,9.8)]]:
		var n: HideoutStation = HideoutStation.new()
		n.name = String(spec[0])
		n.kind = int(spec[1]) as HideoutStation.Kind
		n.authored_visual = true
		n.display_name = String(spec[2])
		n.position = spec[3]
		_owned(stations, n)
	var activities: Node = _root.get_node("Activities")
	for spec: Array in [["Tv",0,Vector3(-13.3,1.41,-10.1)],["Radio",1,Vector3(-14.33,.97,-10.1)],["Beer",2,Vector3(-13.25,.485,-8.7)],["SeatL",3,Vector3(-13.93,.30,-7.55)],["SeatM",3,Vector3(-13.3,.30,-7.55)],["SeatR",3,Vector3(-12.67,.30,-7.55)]]:
		var act: HideoutActivity = HideoutActivity.new()
		act.name = String(spec[0])
		act.kind = int(spec[1]) as HideoutActivity.Kind
		act.authored_visual = true
		act.position = spec[2]
		act.seat_yaw = 180
		act.glow_light = NodePath("../../Lights/TvGlow")
		if act.kind == HideoutActivity.Kind.TV:
			act.screen_path = NodePath("TV_Visual/Screen")
			_put("Television", "TV_Visual", act, Vector3.ZERO)
		elif act.kind == HideoutActivity.Kind.RADIO:
			_put("Radio", "Radio_Visual", act, Vector3.ZERO)
		elif act.kind == HideoutActivity.Kind.BEER:
			_put("Beer", "Beer_Visual", act, Vector3.ZERO)
		_owned(activities, act)
		for visual: Node in act.get_children():
			if visual.name in [&"TV_Visual", &"Radio_Visual", &"Beer_Visual"]:
				visual.owner = _root
	var gameplay: Node = _root.get_node("Gameplay")
	var power: ShelterPower = ShelterPower.new()
	power.name = "GeneratorPower"
	power.position = Vector3(12.0,.95,-8.5)
	_owned(gameplay, power)
	var spawns: Node3D = _group("SpawnPoints", gameplay)
	for i: int in range(3):
		var marker: Marker3D = Marker3D.new()
		marker.name = "PlayerSpawn_%02d" % (i+1)
		marker.position = Vector3(-1.6 + i*1.6, .08, 9.55)
		_owned(spawns, marker)
	var anchor: QuestAnchor = QuestAnchor.new()
	anchor.name = "AntonExistingQuestAnchor"
	anchor.site_id = "anton_hideout"
	anchor.position = Vector3(-4.5, 0, -9.2)
	anchor.rotation_degrees.y = 90
	_owned(gameplay, anchor)
	# Старый TraderNpc был капсулой-декором; интерактивная сущность TraderStation не заменяется.
	var npc: CharacterBody3D = CharacterBody3D.new()
	npc.name = "TraderNpc"
	npc.position = Vector3(-12.4,0,-3.15)
	_owned(gameplay,npc)
	var body: Node3D = _group("Body",npc)
	var persona: Node = (load("res://assets/models/characters/persona_animated.glb") as PackedScene).instantiate()
	persona.name = "Persona"
	body.add_child(persona)
	persona.owner = _root
	var animator: Node = Node.new()
	animator.name = "CharacterAnimator"
	animator.set_script(load("res://src/player/character_animator.gd"))
	_owned(npc,animator)
	var sound: Node = Node.new()
	sound.name = "ExistingAudioBridge"
	for spec: Array in [["living",.35,.65,.13],["utility",.55,.45,.19]]:
		var reverb: AudioEffectReverb = AudioEffectReverb.new()
		reverb.room_size = float(spec[1])
		reverb.damping = float(spec[2])
		reverb.wet = float(spec[3])
		reverb.dry = 1.0
		ShelterSave.save(reverb,BASE+"materials/audio_"+String(spec[0])+".tres")
	for spec: Array in [["GeneratorHum",Vector3(13.8,1.1,-8.5),-16.0,2.0,14.0,1.0],["VentilationHum",Vector3(7.1,3.8,-1),-33.0,3.0,20.0,.76]]:
		var source: AudioStreamPlayer3D = AudioStreamPlayer3D.new()
		source.name = String(spec[0])
		source.position = spec[1]
		source.bus = &"Ambient"
		source.volume_db = float(spec[2])
		source.unit_size = float(spec[3])
		source.max_distance = float(spec[4])
		source.pitch_scale = float(spec[5])
		sound.add_child(source)
	sound.set_script(load("res://src/hideout/shelter_audio.gd"))
	_owned(_root.get_node("Audio"),sound)
	for source: Node in sound.get_children():
		source.owner = _root


func _detail_pass() -> void:
	var props: Node = _root.get_node("Props")
	var details: Node3D = _group("SH_Int_PersonalAndTechnical",props)
	for x: float in [-14.5,-13.8,-13.1]:
		# стволы в стойке стоят дулом вверх, боком к проходу (настоящие модели игры, не запечённые заглушки)
		_weapon(VSS_GLB, "RackRifle_%02d" % details.get_child_count(), details, Vector3(x, .2, 1.62), RIFLE_STANDING)
	_weapon(PM_GLB, "MaintenancePistol", details, Vector3(-12.2, .77, 4.25), PISTOL_LYING)
	# Резерв у стен, рабочие полки заполнены по назначению; основные проходы остаются свободны.
	for spec: Array in [["PH_Crate","HubRouteCrate",Vector3(-3.7,0,-2.9),12],["PH_Crate","HubRouteCrate2",Vector3(-3.7,.34,-2.9),12],["PH_AmmoBox","HubAmmo",Vector3(-3.25,0,-2.55),0],["PH_Crate","ArmoryReserve",Vector3(-16.4,0,4.0),90],["PH_Crate","StorageReserve1",Vector3(16.5,0,1.6),0],["PH_Crate","StorageReserve2",Vector3(16.5,.34,1.6),0],["PH_Crate","StorageReserve3",Vector3(15.55,0,1.6),0],["PH_Barrel","GeneratorDrum",Vector3(10.7,0,-10.25),0],["PH_Barrel","WorkshopDrum",Vector3(16.7,0,-4.35),0],["PH_Barrel","StorageWaterDrum",Vector3(17.0,0,5.95),0],["PH_AmmoBox","ArmoryAmmo1",Vector3(-11.7,.76,3.9),0],["PH_AmmoBox","ArmoryAmmo2",Vector3(-16.5,.26,6.0),90],["PH_AmmoBox","TraderAmmo",Vector3(-15.95,1.14,-4.4),0],["PH_Crate","TraderDelivery",Vector3(-17.2,0,-3.6),0],["PH_Crate","EntryShipment",Vector3(2.65,0,11.2),0],["Rug","UnloadingMat",Vector3(0,0,8.6),0],["Bench","HubRestBench",Vector3(-6.5,0,-.1),90],["Bench","BayBench1",Vector3(-5.1,0,6.5),0],["Bench","BayBench2",Vector3(5.1,0,6.5),0],["Bench","BayBench3",Vector3(7.25,0,6.5),0],["Shelf","WorkshopReserveShelf",Vector3(10.5,0,-4.4),0],["Shelf","ArmoryReserveShelf",Vector3(-17.4,0,3.4),90],["Shelf","LivingFoodShelf",Vector3(-10.2,0,-10.45),0],["Counter","StorageSortingDesk",Vector3(13.7,0,1.55),180],["MedicalCase","SortingFirstAid",Vector3(13.3,.97,1.55),180],["Notebook","SortingLedger",Vector3(14.3,.97,1.55),0],["PH_Crate","UnderSortingDesk",Vector3(13.5,0,1.55),0],["Case","HubMedicReserve",Vector3(-6.5,0,-5.65),0]]:
		_put(String(spec[0]),String(spec[1]),details,spec[2],float(spec[3]))
	for spec: Array in [[-10.2,-10.45],[-17.4,3.4],[10.5,-4.4]]:
		for i: int in range(3):
			_put("PH_AmmoBox","StockBox_%03d" % details.get_child_count(),details,Vector3(float(spec[0]),.68+i*.48,float(spec[1])),0)
	for x: float in [10.2,12.0,13.8,15.6,-16.6,-14.8,-13.0]:
		var z: float = 6.3 if x>0 else -4.45
		_put("Case","SupplyTop_%03d" % details.get_child_count(),details,Vector3(x,1.65,z))
		_put("PH_AmmoBox","SupplyTray_%03d" % details.get_child_count(),details,Vector3(x,.2,z))
	for i: int in range(6):
		_put("FoodCan","LivingTin_%02d" % i,details,Vector3(-10.5+(i%3)*.24,.67+(i/3)*.49,-10.42))
	for i: int in range(4):
		_put("WaterBottle","LivingWater_%02d" % i,details,Vector3(-10.5+i*.19,1.16,-10.4))
	for spec: Array in [["DeskLamp","PlanningLamp",Vector3(1.02,.79,-.36),0],["Binoculars","PlanningOptics",Vector3(.32,.78,.32),14],["Pencil","PlanningPencil",Vector3(-.63,.79,.38),-23],["DeskLamp","LivingLamp",Vector3(-12.22,.97,-10.1),0],["DeskLamp","TraderTaskLamp",Vector3(-13.3,.97,-1.87),0],["DeskLamp","WorkbenchTaskLamp",Vector3(14.6,.95,-4.2),0],["WallMap","HubRouteBoard",Vector3(-7.73,1.85,.95),90],["Shelf","HubSuppliesShelf",Vector3(-7.35,0,-3.5),90],["ElectricalCabinet","HubCommunicationsPanel",Vector3(7.48,0,1.75),-90],["Counter","CommunicationsDesk",Vector3(-5.3,0,-9.1),0],["Radio","CommunicationsReceiver",Vector3(-5.8,.97,-9.1),0],["Notebook","CommunicationsLog",Vector3(-4.7,.97,-9.1),16],["Bench","NorthWaitingBench",Vector3(0,0,-10.5),0],["Locker","PersonalLocker",Vector3(-3.8,0,-10.5),0],["CableReel","MaintenanceReel",Vector3(7.2,0,-4.0),0],["Case","MaintenanceCase",Vector3(-7.1,0,1.0),90],["Case","HubSuppliesCase",Vector3(-7.3,.66,-3.5),90],["Backpack","HubSparePack",Vector3(-7.3,1.13,-3.1),90],["HookRail","EntryHooks",Vector3(-3.71,1.64,9.4),90],["HookRail","BayHooks1",Vector3(-5.1,1.62,7.81),180],["HookRail","BayHooks2",Vector3(5.1,1.62,7.81),180],["HookRail","BayHooks3",Vector3(7.4,1.62,7.81),180],["TacticalVest","BayVest1",Vector3(-4.7,1.05,7.65),180],["TacticalVest","BayVest2",Vector3(5.5,1.05,7.65),180],["TacticalVest","BayVest3",Vector3(7.65,1.05,7.65),180],["Helmet","ArmoryHelmet",Vector3(-12.5,.78,4.1),0],["Helmet","BayHelmet",Vector3(5.45,.49,6.48),0],["Helmet","TraderHelmet",Vector3(-14.8,1.65,-4.4),0],["TacticalVest","ArmoryVest",Vector3(-16.8,1.2,6.35),180],["JerryCan","EntryWaterCan",Vector3(2.9,0,11.3),0],["MedicalCase","HubFirstAid",Vector3(-7.4,1.63,-3.5),90],["CardboardBox","LivingPersonalCarton",Vector3(-17.4,.18,-8.3),90],["FoodCan","LivingFood",Vector3(-17.4,1.13,-8),0],["WaterBottle","LivingWater",Vector3(-17.4,.69,-7.7),0],["Mug","SleepingCup",Vector3(-2.14,3.14,-10.6),0]]:
		_put(String(spec[0]),String(spec[1]),details,spec[2],float(spec[3]))
	for spec: Array in [["PlanningTask",Vector3(1.02,1.15,-.36),.38,2.0],["LivingTask",Vector3(-12.2,1.36,-10.1),.45,2.8],["WorkshopTask",Vector3(14.6,1.34,-4.2),.45,2.5],["GalleryTask",Vector3(-5.4,1.55,-9.1),.6,3.5]]:
		var task: OmniLight3D = OmniLight3D.new()
		task.name = String(spec[0])
		task.position = spec[1]
		task.light_energy = float(spec[2])
		task.omni_range = float(spec[3])
		task.light_color = Color(1,.78,.48)
		task.light_size = .06
		task.light_bake_mode = Light3D.BAKE_DYNAMIC
		_owned(_root.get_node("Lights"),task)
	# Шесть practicals центрального хаба; только два основных источника дают realtime shadows.
	for position: Vector3 in [Vector3(-4.1,3.65,4.8),Vector3(4.1,3.65,4.8),Vector3(-4.1,3.65,-4.8),Vector3(4.1,3.65,-4.8)]:
		var lamp: OmniLight3D = OmniLight3D.new()
		lamp.name = "HubPractical_%02d" % _root.get_node("Lights").get_child_count()
		lamp.position = position
		lamp.light_color = Color(1,.94,.85)
		lamp.light_energy = 1.15
		lamp.omni_range = 4.7
		lamp.light_bake_mode = Light3D.BAKE_DYNAMIC
		_owned(_root.get_node("Lights"),lamp)
		_put("PracticalLight","Fixture_"+lamp.name,details,position+Vector3(0,.12,0))


const VSS_GLB: String = "res://assets/models/weapons/vss_textured/VSS_Vintorez_Picatinny.glb"
const PM_GLB: String = "res://assets/models/weapons/pm/pm.glb"
const GLOCK_GLB: String = "res://assets/models/weapons/glock17/glock17.glb"
## Модели оружия: +Z — дуло, +Y — верх, -X — правый бок. Стоя в стойке: дуло вверх, левый бок к зрителю (+Z).
const RIFLE_STANDING: Basis = Basis(Vector3(0, 0, 1), Vector3(1, 0, 0), Vector3(0, 1, 0))
## Лёжа на столе на правом боку: дуло вдоль +X, левый бок вверх.
const PISTOL_LYING: Basis = Basis(Vector3(0, 1, 0), Vector3(0, 0, 1), Vector3(1, 0, 0))

## Декоративный экземпляр готовой модели оружия игры (тот же GLB, что в руках).
func _weapon(path: String, label: String, parent: Node, at: Vector3, basis: Basis) -> Node3D:
	var n: Node3D = (load(path) as PackedScene).instantiate() as Node3D
	n.name = label
	n.transform = Transform3D(basis, at)
	# экземпляр GLB-сцены: в .tscn остаётся ссылкой на модель, внутренности не копируются
	_owned(parent, n)
	_placements.append({"name": label, "asset": path.get_file().get_basename(), "position": [at.x, at.y, at.z], "yaw": 0.0})
	return n


func _bake_display_weapon(id: String) -> void:
	# Прежние модели игры, запечённые как static decoration; функциональный тайник прежний.
	var original: Node3D = WeaponModels.build(id,{},1)
	var root: Node3D = Node3D.new()
	root.name = "Display_"+id
	var index: int = 0
	for n: Node in original.find_children("*","MeshInstance3D",true,false):
		var source: MeshInstance3D = n as MeshInstance3D
		if not source.visible or source.mesh == null:
			continue
		var mesh: ArrayMesh = ArrayMesh.new()
		for surface: int in range(source.mesh.get_surface_count()):
			mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,source.mesh.surface_get_arrays(surface))
			var material: Material = source.material_override if source.material_override else source.mesh.surface_get_material(surface)
			if material is StandardMaterial3D and (material as StandardMaterial3D).albedo_texture == null:
				var color: Color = (material as StandardMaterial3D).albedo_color
				material = _materials["OldWood"] if color.r>color.b*1.5 and color.r>.18 else _materials["BareSteel"]
			mesh.surface_set_material(surface,material)
		var path: String = BASE+"props/Display_"+id+"_%02d.res" % index
		ShelterSave.save(mesh,path)
		var mi: MeshInstance3D = MeshInstance3D.new()
		mi.name = "FinishedWeaponPart_%02d" % index
		mi.mesh = load(path)
		var t: Transform3D = source.transform
		var parent: Node3D = source.get_parent() as Node3D
		while parent:
			t = parent.transform*t
			if parent == original:break
			parent = parent.get_parent() as Node3D
		mi.transform = t
		root.add_child(mi)
		mi.owner = root
		index+=1
	var packed: PackedScene = PackedScene.new()
	packed.pack(root)
	var target: String = BASE+"props/Display_"+id+".tscn"
	ShelterSave.save(packed,target)
	_kit["Display_"+id] = load(target)
	root.free()
	original.free()


func _floor_joints() -> void:
	# Швы заливки бетона — тонкие authored strips, общий ArrayMesh, без коллизий.
	var surface: SurfaceTool = SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	surface.set_material(_materials["Rubber"])
	var runs: Array[Array] = []
	for x: float in [-4,0,4]:
		runs.append([Vector3(x,.008,-8),Vector3(x,.008,8)])
	for z: float in [-4,0,4]:
		runs.append([Vector3(-8,.008,z),Vector3(8,.008,z)])
	for x: float in [-14,-10,10,14]:
		runs.append([Vector3(x,.008,-11),Vector3(x,.008,7)])
	for z: float in [-9,-7,-3,-1,3,5]:
		runs.append([Vector3(-18,.008,z),Vector3(-8,.008,z)])
		runs.append([Vector3(8,.008,z),Vector3(18,.008,z)])
	for run: Array in runs:
		var offset: Vector3 = (run[1]-run[0]).normalized().cross(Vector3.UP)*.004
		var vertices: Array[Vector3] = [run[0]-offset,run[0]+offset,run[1]+offset,run[0]-offset,run[1]+offset,run[1]-offset]
		for vertex: Vector3 in vertices:
			surface.set_normal(Vector3.UP)
			surface.set_uv(Vector2(vertex.x,vertex.z))
			surface.add_vertex(vertex)
	var mesh: ArrayMesh = surface.commit()
	ShelterSave.save(mesh,BASE+"architecture/floor_joints.res")
	var node: MeshInstance3D = MeshInstance3D.new()
	node.name = "SH_Int_ConcreteConstructionJoints"
	node.mesh = load(BASE+"architecture/floor_joints.res")
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_owned(_root.get_node("Architecture"),node)


## Пара потолочных ламп вместо одной: на сколько разнести (м, вдоль длинной оси помещения) и сила
## каждой от прежней одиночной (две по 0.7 — в помещении светлее в 1.4 раза).
const LAMP_PAIR: Dictionary = {"HubWest": Vector3(0, 0, 4.0), "HubEast": Vector3(0, 0, 4.0), "NorthGallery": Vector3(4.0, 0, 0),
	"Entry": Vector3(2.4, 0, 0), "Living": Vector3(3.6, 0, 0), "Trader": Vector3(3.6, 0, 0), "Armory": Vector3(3.6, 0, 0),
	"Workshop": Vector3(3.6, 0, 0), "Storage": Vector3(3.6, 0, 0), "Generator": Vector3(3.6, 0, 0), "Sleeping": Vector3(4.0, 0, 0),
	"Bays": Vector3(0, 0, 1.6), "BaysWest": Vector3(0, 0, 1.6)}
const LAMP_PAIR_ENERGY: float = 0.7

func _lighting() -> void:
	var lights: Node = _root.get_node("Lights")
	for spec: Array in [["HubWest",Vector3(-3.9,3.6,0),Color(1,.82,.58),3.8,8.0,true],["HubEast",Vector3(3.9,3.6,0),Color(1,.82,.58),3.8,8.0,true],["NorthGallery",Vector3(0,2.0,-6),Color(1,.78,.50),2.4,5.0,false],["Entry",Vector3(0,2.7,9.7),Color(1,.78,.48),2.8,5.0,true],["Living",Vector3(-13.0,2.65,-8.0),Color(1,.66,.34),2.9,5.5,true],["Trader",Vector3(-12.8,2.65,-2.0),Color(1,.78,.52),3.1,5.0,false],["Armory",Vector3(-12.8,2.65,4.0),Color(1,.86,.66),3.0,5.3,false],["Workshop",Vector3(13.0,2.65,-2.5),Color(1,.88,.73),3.8,5.5,true],["Storage",Vector3(13.0,2.65,4),Color(1,.83,.61),2.9,5.5,false],["Generator",Vector3(13.0,2.65,-8.0),Color(.90,.95,1),3.5,5.5,true],["Sleeping",Vector3(0,4.65,-9.2),Color(1,.73,.45),1.8,4.5,false],["Bays",Vector3(5.3,2.9,6.6),Color(1,.8,.54),1.9,3.8,false],["BaysWest",Vector3(-5.3,2.9,6.6),Color(1,.8,.54),1.9,3.8,false]]:
		# по две лампы на помещение (решение владельца 2026-10-07): пара вдоль длинной оси комнаты,
		# каждая — LAMP_PAIR_ENERGY от прежней одиночной
		var pair: Vector3 = LAMP_PAIR[String(spec[0])]
		for twin: int in range(2):
			var light: OmniLight3D = OmniLight3D.new()
			light.name = String(spec[0]) + ("2" if twin == 1 else "")
			light.position = (spec[1] as Vector3) + pair * (0.5 if twin == 1 else -0.5)
			light.light_color = spec[2]
			if String(spec[0]) in ["HubWest","HubEast","Trader","Workshop","Armory","Storage"]:
				light.light_color = Color(1,.94,.85)
			elif String(spec[0]) in ["Entry","NorthGallery","Sleeping","Bays","BaysWest","Living"]:
				light.light_color = Color(1,.86,.70)
			light.light_energy = float(spec[3]) * LAMP_PAIR_ENERGY
			light.omni_range = float(spec[4])
			light.omni_attenuation = 1.5
			light.shadow_enabled = bool(spec[5]) or String(spec[0]) in ["Trader","Armory","Storage","Sleeping"]
			light.light_size = .35
			light.shadow_blur = 1.0
			light.shadow_bias = .025
			light.shadow_normal_bias = .35
			light.light_bake_mode = Light3D.BAKE_DYNAMIC
			light.light_volumetric_fog_energy = .10
			_owned(lights, light)
			_put("PracticalLight", "Fixture_"+light.name, _root.get_node("Props"), light.position + Vector3(0,.10,0))
	for spec: Array in [["EmergencyEntry",Vector3(0,2.0,8.45),.65,6.0],["EmergencyHub",Vector3(0,2.7,-6),.65,9.0]]:
		var light: OmniLight3D = OmniLight3D.new()
		light.name = String(spec[0])
		light.position = spec[1]
		light.light_energy = float(spec[2])
		light.omni_range = float(spec[3])
		light.light_color = Color(.78,.74,.65)
		light.light_bake_mode = Light3D.BAKE_DYNAMIC
		_owned(lights,light)
	for spec: Array in [["LivingWall",Vector3(-17.65,2.05,-8.2),90],["TraderWall",Vector3(-17.65,2.05,-3.4),90],["ArmoryWall",Vector3(-17.65,2.05,3.4),90],["StorageWall",Vector3(17.65,2.05,1.9),-90],["WorkshopWall",Vector3(17.65,2.05,-1.7),-90],["GeneratorWall",Vector3(10.8,2.05,-10.7),0],["HubWallLeft",Vector3(-7.65,2.05,1.15),90],["HubWallRight",Vector3(7.65,2.05,1.15),-90]]:
		# настенные лампы — тоже парами вдоль стены
		var along: Vector3 = Vector3(1.6, 0, 0) if is_zero_approx(float(spec[2])) else Vector3(0, 0, 1.6)
		for twin: int in range(2):
			var light: OmniLight3D = OmniLight3D.new()
			light.name = String(spec[0]) + ("2" if twin == 1 else "")
			light.position = spec[1]
			if String(spec[0]) == "HubWallLeft":
				light.position.z = 2.55
			light.position += along * (0.5 if twin == 1 else -0.5)
			light.light_color = Color(1,.90,.76)
			light.light_energy = 1.25 * LAMP_PAIR_ENERGY
			light.omni_range = 3.8
			light.light_bake_mode = Light3D.BAKE_DYNAMIC
			_owned(lights,light)
			_put("CageLamp","Fixture_"+light.name,_root.get_node("Props"),light.position,float(spec[2]))
	var tv: OmniLight3D = OmniLight3D.new()
	tv.name = "TvGlow"
	tv.position = Vector3(-13.3,1.35,-9.7)
	tv.omni_range = 2.6
	tv.light_energy = .28
	tv.light_bake_mode = Light3D.BAKE_DYNAMIC
	_owned(lights,tv)
	for spec: Array in [["Entry",Vector3(0,1.6,10),Vector3(7.7,3.1,4.0)],["MainHub",Vector3(0,2.0,0),Vector3(15.5,4,15.5)],["Living",Vector3(-13,1.6,-8),Vector3(9.6,3.1,5.6)],["Workshop",Vector3(13,1.6,-2),Vector3(9.6,3.1,5.6)],["Storage",Vector3(13,1.6,4),Vector3(9.6,3.1,5.6)],["Generator",Vector3(13,1.6,-8),Vector3(9.6,3.1,5.6)]]:
		var probe: ReflectionProbe = ReflectionProbe.new()
		probe.name = "Probe_"+String(spec[0])
		probe.position = spec[1]
		probe.size = spec[2]
		probe.interior = true
		probe.box_projection = true
		probe.enable_shadows = true
		probe.max_distance = 18
		probe.mesh_lod_threshold = 2.0
		probe.update_mode = ReflectionProbe.UPDATE_ONCE
		probe.intensity = .65
		_owned(_root.get_node("ReflectionProbes"),probe)


func _environment() -> void:
	var e: Environment = Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(.01,.012,.013)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(.55,.62,.70)
	e.ambient_light_energy = .35
	e.tonemap_mode = Environment.TONE_MAPPER_ACES
	e.tonemap_exposure = 1.10
	e.ssao_enabled = true
	e.ssao_radius = .45
	e.ssao_intensity = .85
	e.ssil_enabled = true
	e.sdfgi_enabled = true
	e.sdfgi_use_occlusion = true
	e.sdfgi_cascades = 3
	e.sdfgi_min_cell_size = .15
	e.sdfgi_energy = 1.0
	e.sdfgi_bounce_feedback = .55
	e.sdfgi_read_sky_light = false
	e.glow_enabled = true
	e.glow_intensity = .18
	e.glow_bloom = .015
	e.volumetric_fog_enabled = true
	e.volumetric_fog_density = .0012
	e.volumetric_fog_length = 40.0
	e.volumetric_fog_albedo = Color(.76,.77,.72)
	e.set_meta("ssr_allowed", false)
	e.set_meta("authored_lighting", true)
	var world: WorldEnvironment = WorldEnvironment.new()
	world.name = "WorldEnvironment"
	world.environment = e
	_owned(_root, world)
	for spec: Array in [["EntryWet",Vector3(0,.025,10),Vector3(3,.1,2),"wet_patch"],["ReturnBootMarks",Vector3(.8,.025,8.8),Vector3(1.8,.1,2),"shoe_marks"],["GeneratorOil",Vector3(13.8,.025,-8.1),Vector3(3.7,.1,2.0),"oil_stain"],["WorkshopOil",Vector3(13.7,.025,-3.7),Vector3(2.6,.1,1.4),"oil_stain"],["EntryDirt",Vector3(-2.9,.025,9.2),Vector3(1.3,.1,1.4),"dirt"]]:
		var decal: Decal = Decal.new()
		decal.name = String(spec[0])
		decal.position = spec[1]
		decal.size = spec[2]
		decal.texture_albedo = load(TEXTURES+String(spec[3])+".png")
		if ResourceLoader.exists(TEXTURES+String(spec[3])+"_orm.png"):
			decal.texture_orm = load(TEXTURES+String(spec[3])+"_orm.png")
		decal.upper_fade = .02
		decal.lower_fade = .02
		_owned(_root.get_node("Props"),decal)
	for spec: Array in [["LivingDamp",Vector3(-16.5,1.5,-10.76),Vector3(2.4,.12,2.0),"water_streak"],["GeneratorRust",Vector3(16.8,1.6,-10.76),Vector3(1.7,.12,2.2),"rust_streak"],["WorkshopScratches",Vector3(14,1.25,-4.76),Vector3(3,.12,1.8),"paint_damage"],["HubDamp",Vector3(-6,1.7,-10.76),Vector3(2.4,.12,2.4),"water_streak"]]:
		var decal: Decal = Decal.new()
		decal.name = String(spec[0])
		decal.position = spec[1]
		decal.rotation_degrees.x = 90
		decal.size = spec[2]
		decal.texture_albedo = load(TEXTURES+String(spec[3])+".png")
		_owned(_root.get_node("Props"),decal)


func _signage() -> void:
	# Физические таблички с эмалью и винтами, лицевая сторона обращена к хабу.
	var index: int = 0
	for spec: Array in [[Vector3(-7.78,2.65,-2),90],[Vector3(-7.78,2.65,4),90],[Vector3(-7.78,2.65,-6.8),90],[Vector3(7.78,2.65,-2),-90],[Vector3(7.78,2.65,4),-90],[Vector3(7.78,2.65,-6.8),-90],[Vector3(0,2.7,11.77),180],[Vector3(0,3.4,-6.46),0],[Vector3(4.95,2.68,-10.55),0],[Vector3(-4.95,2.68,-10.55),0]]:
		_put("RoomSign_%02d" % index,"WallSign_%02d" % index,_root.get_node("Signs"),spec[0],float(spec[1]))
		index += 1
	for i: int in range(3):
		var sign: Node3D = _put("RoomSign_%02d" % (i+10),"EquipmentBaySign_%02d" % (i+1),_root.get_node("Signs"),Vector3([-5.1,5.1,7.4][i],2.24,7.79),180)
		sign.scale = Vector3(.65,.85,1)


func _navigation() -> void:
	var mesh: NavigationMesh = NavigationMesh.new()
	mesh.agent_radius = .5
	mesh.agent_height = 2.0
	mesh.agent_max_climb = .5
	mesh.agent_max_slope = 40.0
	mesh.cell_size = .25
	mesh.cell_height = .25
	mesh.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	mesh.geometry_source_geometry_mode = NavigationMesh.SOURCE_GEOMETRY_GROUPS_WITH_CHILDREN
	mesh.geometry_source_group_name = &"shelter_navigation_geometry"
	# котельный зал с тиром — восточнее основного здания, до x 62.4
	mesh.filter_baking_aabb = AABB(Vector3(-19,-.25,-12),Vector3(82,3.3,25))
	var region: NavigationRegion3D = NavigationRegion3D.new()
	region.name = "Interior"
	region.navigation_mesh = mesh
	_owned(_root.get_node("Navigation"),region)


## Нижняя точка мешей узла по Y в его собственной системе — чтобы поставить модель на опору.
func _lowest(n: Node3D) -> float:
	var lowest: float = INF
	for child: Node in n.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = child as MeshInstance3D
		var t: Transform3D = mi.transform
		var p: Node = mi.get_parent()
		while p and p != n:
			t = (p as Node3D).transform * t
			p = p.get_parent()
		lowest = minf(lowest, (n.transform * t * mi.get_aabb()).position.y)
	return lowest


## Модель оружия стоит или лежит на опоре на высоте floor_y.
func _weapon_on(path: String, label: String, parent: Node, at: Vector3, basis: Basis, floor_y: float) -> Node3D:
	var n: Node3D = _weapon(path, label, parent, at, basis)
	n.position.y += floor_y - _lowest(n)
	return n


## Лист мишени: квадрат 0.6 × 1.0 м с UV на всю картинку «мишени № 4», низ листа — y 0.
func _paper_sheet() -> ArrayMesh:
	var path: String = BASE + "range/paper_sheet.res"
	DirAccess.make_dir_recursive_absolute(BASE + "range")
	var st: SurfaceTool = SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	st.set_material(_materials["RangePaper"])
	var corners: Array[Vector3] = [Vector3(-.3, 0, 0), Vector3(.3, 0, 0), Vector3(.3, 1, 0), Vector3(-.3, 1, 0)]
	var uvs: Array[Vector2] = [Vector2(0, 1), Vector2(1, 1), Vector2(1, 0), Vector2(0, 0)]
	for i: int in [0, 1, 2, 0, 2, 3]:
		st.set_normal(Vector3(0, 0, 1))
		st.set_uv(uvs[i])
		st.add_vertex(corners[i])
	st.generate_tangents()
	ShelterSave.save(st.commit(), path)
	return load(path) as ArrayMesh


func _boiler_hall() -> void:
	# Бывший котельный зал (раскладка — boiler_layout.json от tools/build_shelter_boiler.py):
	# два остановленных котла, насосы, щит КИП и кран-балка вдоль северной стены, тир на пять дорожек.
	var layout: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(MODELS + "boiler_layout.json")) as Dictionary
	var fx: float = float(layout.firing_x)
	var hall: Node3D = _group("SH_Int_BoilerHall", _root.get_node("Props"))
	var index: int = 1
	for b: Dictionary in layout.boilers:
		_put("Boiler", "Boiler_%d" % index, hall, Vector3(float(b.x), 0, float(b.z)))
		index += 1
	index = 1
	for pump: Dictionary in layout.pumps:
		_put("CirculationPump", "CirculationPump_%d" % index, hall, Vector3(float(pump.x), 0, float(pump.z)))
		index += 1
	_put("KipPanel", "KipPanel", hall, Vector3(18.47, 0, -7.2), 90)
	var crane: Node3D = _put("PH_Crane", "BridgeCrane", hall, Vector3(41.0, .69, -8.4))
	crane.scale = Vector3.ONE * 1.2
	var cabinet: Vector3 = _v(layout.gun_cabinet)
	_put("RangeGunCabinet", "RangeGunCabinet", hall, cabinet, 90)
	# В шкафу стойки — настоящие модели игры: три ВСС в ложементах и пистолеты на полке.
	var facing_hall: Basis = Basis(Vector3(1, 0, 0), Vector3(0, 0, -1), Vector3(0, 1, 0))
	for k: int in range(3):
		_weapon_on(VSS_GLB, "CabinetVss_%d" % (k + 1), hall, Vector3(cabinet.x + .1, 0, cabinet.z + [.85, .45, .05][k]), facing_hall, .37)
	var along_shelf: Basis = Basis(Vector3(0, 1, 0), Vector3(1, 0, 0), Vector3(0, 0, -1))
	_weapon_on(PM_GLB, "CabinetPm", hall, Vector3(cabinet.x + .12, 0, cabinet.z - .3), along_shelf, 1.965)
	_weapon_on(GLOCK_GLB, "CabinetGlock", hall, Vector3(cabinet.x + .12, 0, cabinet.z - .72), along_shelf, 1.965)
	for spec: Array in [
		["PH_Bench", "WaitingBench_1", Vector3(20.6, 0, -3.6), 90], ["PH_Bench", "WaitingBench_2", Vector3(20.6, 0, 5.6), 90],
		["PH_FoldingStool", "LaneStool_1", Vector3(22.6, 0, -1.2), 0], ["PH_FoldingStool", "LaneStool_2", Vector3(22.6, 0, 3.6), 0],
		["PH_TrashCan", "HallTrash", Vector3(19.0, 0, 6.3), 0], ["PH_UtilityBox", "PumpStarter", Vector3(24.6, 0, -10.5), 0],
		["PH_PowerBox", "HallBreakers", Vector3(18.24, 1.25, -4.6), 90], ["PH_PropaneTank", "BurnerGas_1", Vector3(28.4, 0, -10.35), 0],
		["PH_PropaneTank", "BurnerGas_2", Vector3(28.9, 0, -10.4), 30], ["PH_ToolCart", "BoilerToolCart", Vector3(42.0, 0, -7.0), 90],
		["PH_Compressor", "HallCompressor", Vector3(55.6, 0, -9.9), 0], ["PH_PlasticCrate", "HallCrate_1", Vector3(57.6, 0, -10.4), 0],
		["PH_PlasticCrate", "HallCrate_2", Vector3(57.6, .264, -10.4), 8], ["PH_LpgTank", "HallLpg", Vector3(56.6, 0, -6.6), 0],
		["PH_PipeWrench", "PumpWrench", Vector3(21.0, .205, -9.6), 70], ["PH_OilTin", "PumpOil", Vector3(23.75, 0, -9.3), 0],
		["PH_GasMask", "HallGasMask_1", Vector3(18.24, .95, -2.2), 90], ["PH_GasMask", "HallGasMask_2", Vector3(18.24, .95, -2.7), 90],
		["PH_Stool", "KipStool", Vector3(19.4, 0, -7.2), 0], ["PH_Clipboard", "KipLog", Vector3(18.62, 1.0, -6.7), 0],
	]:
		_put(String(spec[0]), String(spec[1]), hall, spec[2], float(spec[3]))
	# --- тир: дорожки, мишени на тележках, пульты, стойка оружия ---
	var gameplay: Node = _root.get_node("Gameplay")
	var range_node: ShootingRange = ShootingRange.new()
	range_node.name = "ShootingRange"
	range_node.position = Vector3(fx, 0, 0)
	var hx: Dictionary = layout.hall
	range_node.zone = AABB(Vector3(float(hx.x0) + .2 - fx, -.5, float(hx.z0) + .2), Vector3(float(hx.x1) - float(hx.x0) - .4, 9.0, float(hx.z1) - float(hx.z0) - .4))
	_owned(gameplay, range_node)
	var sheet: ArrayMesh = _paper_sheet()
	index = 1
	for lane_spec: Dictionary in layout.lanes:
		var paper: bool = String(lane_spec.kind) == "paper"
		var lane: RangeLane = RangeLane.new()
		lane.name = "Lane_%d" % index
		lane.display_name = "Дорожка %d" % index
		lane.max_distance_m = float(layout.rail_x1) - fx - .6
		lane.position = Vector3(0, 0, float(lane_spec.z))
		# -Z дорожки — к мишени (на восток, +X мира), +Z — к стрелку
		lane.rotation_degrees.y = -90
		_owned(range_node, lane)
		var carriage: Node3D = Node3D.new()
		carriage.name = "Carriage"
		_owned(lane, carriage)
		_put("RangeCarrierPaper" if paper else "RangeCarrierFloor", "CarrierModel", carriage, Vector3.ZERO)
		var target: RangeTarget = RangeTarget.new()
		target.name = "Target"
		target.kind = RangeTarget.Kind.PAPER if paper else RangeTarget.Kind.MANNEQUIN
		_owned(lane, target)
		var shape: CollisionShape3D = CollisionShape3D.new()
		shape.name = "Hitbox"
		var box: BoxShape3D = BoxShape3D.new()
		if paper:
			box.size = Vector3(.62, 1.02, .05)
			shape.position = Vector3(0, 1.47, 0)
			var sway: Node3D = Node3D.new()
			sway.name = "Sway"
			sway.position = Vector3(0, 1.97, 0)
			_owned(target, sway)
			var sheet_node: MeshInstance3D = MeshInstance3D.new()
			sheet_node.name = "Paper"
			sheet_node.mesh = sheet
			sheet_node.position = Vector3(0, -1.0, .012)
			_owned(sway, sheet_node)
		else:
			box.size = Vector3(.52, 1.8, .34)
			shape.position = Vector3(0, 1.07, 0)
			var persona: Node3D = (load("res://assets/models/characters/persona_animated.glb") as PackedScene).instantiate() as Node3D
			persona.name = "Persona"
			persona.position = Vector3(0, .175, 0)
			_owned(target, persona)
		shape.shape = box
		_owned(target, shape)
		# пульт на стойке рубежа: за линией огня, лицом к стрелку
		_put("RangeConsole", "Console", lane, Vector3(0, float(layout.counter_top), fx - float(layout.counter_x)))
		var display: Label3D = Label3D.new()
		display.name = "Display"
		# табло между кнопками пульта, на наклонной панели, читается стрелку
		display.position = Vector3(0, float(layout.counter_top) + .168, fx - float(layout.counter_x) - .07)
		display.rotation_degrees.x = -62
		display.pixel_size = .0006
		display.font_size = 64
		display.outline_size = 4
		display.modulate = Color(.55, 1.0, .55)
		display.shaded = false
		_owned(lane, display)
		for spec: Array in [["ButtonCloser", "closer", -.36], ["ButtonReset", "reset", 0.0], ["ButtonFarther", "farther", .36]]:
			var button: RangeButton = RangeButton.new()
			button.name = String(spec[0])
			button.action = String(spec[1])
			button.lane_path = NodePath("..")
			button.position = Vector3(float(spec[2]), float(layout.counter_top) + .21, fx - float(layout.counter_x) + .05)
			_owned(lane, button)
		index += 1
	var rack: RangeWeaponRack = RangeWeaponRack.new()
	rack.name = "RangeWeaponRack"
	rack.position = Vector3(cabinet.x + .45, 1.1, cabinet.z)
	_owned(gameplay, rack)
	# дистанции трафаретом на южной стене зала
	for d: int in [5, 10, 15, 20, 25, 30]:
		var mark: Label3D = Label3D.new()
		mark.name = "DistanceMark_%02d" % d
		mark.text = "%d м" % d
		mark.position = Vector3(fx + d, 2.25, float(hx.z1) - .22)
		mark.rotation_degrees.y = 180
		mark.pixel_size = .006
		mark.font_size = 96
		mark.modulate = Color(.86, .82, .68)
		# трафарет на кирпиче, не металлическая табличка — живёт с залом, а не в Signs
		_owned(hall, mark)
	_put("RoomSign_13", "HallSign_Storage", _root.get_node("Signs"), Vector3(17.78, 2.65, float(layout.storage_door_z)), -90)
	_put("RoomSign_14", "HallSign_FiringLine", _root.get_node("Signs"), Vector3(float(layout.counter_x), 3.35, .6), -90)
	_put("RoomSign_15", "HallSign_Caution", _root.get_node("Signs"), Vector3(18.22, 2.65, float(layout.storage_door_z)), 90)
	# --- свет зала: подвесные цеховые светильники, прожектор вдоль дорожек, дневной свет окон ---
	var lights: Node = _root.get_node("Lights")
	# подвесные — вдвое больше: между прежними (в ряду над дорожками и над котлами) ещё по одному
	for spec: Array in [[28.5, .6, true], [32.25, .6, false], [36.0, .6, false], [39.75, .6, false], [43.5, .6, true], [47.25, .6, false], [51.0, .6, false], [54.75, .6, false],
			[27.5, -8.4, false], [34.0, -8.4, false], [40.75, -8.4, false], [47.5, -8.4, false]]:
		var at: Vector3 = Vector3(float(spec[0]), 5.46, float(spec[1]))
		_put("PH_HangingLamp", "Fixture_HallPendant_%02d" % lights.get_child_count(), hall, at)
		var lamp: OmniLight3D = OmniLight3D.new()
		lamp.name = "HallPendant_%02d" % lights.get_child_count()
		lamp.position = at + Vector3(0, .05, 0)
		lamp.light_color = Color(1, .92, .8)
		lamp.light_energy = (2.4 if float(spec[1]) > 0 else 1.3) * LAMP_PAIR_ENERGY
		lamp.omni_range = 13.0
		lamp.omni_attenuation = 1.2
		lamp.shadow_enabled = bool(spec[2])
		lamp.light_size = .3
		lamp.light_bake_mode = Light3D.BAKE_DYNAMIC
		_owned(lights, lamp)
	var flood: SpotLight3D = SpotLight3D.new()
	flood.name = "RangeFloodlight"
	flood.position = Vector3(fx - 1.0, 4.8, .6)
	flood.basis = Basis.looking_at(Vector3(fx + 32.0, 1.4, .6) - flood.position, Vector3.UP)
	flood.spot_range = 42.0
	flood.spot_angle = 21.0
	flood.light_energy = 8.0
	flood.light_color = Color(1, .95, .86)
	flood.shadow_enabled = true
	flood.light_bake_mode = Light3D.BAKE_DYNAMIC
	_owned(lights, flood)
	var fill: OmniLight3D = OmniLight3D.new()
	fill.name = "HallFiringArea"
	fill.position = Vector3(21.0, 3.2, .6)
	fill.light_energy = 1.6
	fill.omni_range = 8.0
	fill.light_color = Color(1, .9, .76)
	fill.light_bake_mode = Light3D.BAKE_DYNAMIC
	_owned(lights, fill)
	for z: float in [-0.2, -3.4, -6.6, -9.8]:
		var wall_lamp: OmniLight3D = OmniLight3D.new()
		wall_lamp.name = "HallWestWall_%02d" % lights.get_child_count()
		wall_lamp.position = Vector3(18.3, 2.6, z)
		wall_lamp.light_color = Color(1, .9, .76)
		wall_lamp.light_energy = 1.2 * LAMP_PAIR_ENERGY
		wall_lamp.omni_range = 4.5
		wall_lamp.light_bake_mode = Light3D.BAKE_DYNAMIC
		_owned(lights, wall_lamp)
		_put("CageLamp", "Fixture_" + wall_lamp.name, hall, wall_lamp.position, 90)
	# солнце снаружи: светит в южные окна; направление, сила и видимость — ShelterWeather по погоде
	var sun: DirectionalLight3D = DirectionalLight3D.new()
	sun.name = "Sun"
	sun.visible = false
	sun.shadow_enabled = true
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
	sun.directional_shadow_max_distance = 70.0
	sun.shadow_blur = 1.5
	sun.light_bake_mode = Light3D.BAKE_DYNAMIC
	sun.sky_mode = DirectionalLight3D.SKY_MODE_LIGHT_ONLY
	_owned(lights, sun)
	var weather: ShelterWeather = ShelterWeather.new()
	weather.name = "Weather"
	_owned(_root, weather)
	# рассеянный дневной свет через армированное стекло — холодный и слабый
	for x: float in [27.0, 39.0, 51.0]:
		var day: OmniLight3D = OmniLight3D.new()
		day.name = "HallDaylight_%02d" % lights.get_child_count()
		day.position = Vector3(x, 4.6, float(hx.z1) - 1.0)
		day.light_color = Color(.78, .85, .95)
		day.light_energy = .45
		day.omni_range = 8.0
		day.light_bake_mode = Light3D.BAKE_DYNAMIC
		_owned(lights, day)
	var probe: ReflectionProbe = ReflectionProbe.new()
	probe.name = "Probe_BoilerHall"
	probe.position = Vector3((float(hx.x0) + float(hx.x1)) * .5, 4.0, (float(hx.z0) + float(hx.z1)) * .5)
	probe.size = Vector3(float(hx.x1) - float(hx.x0), 8.0, float(hx.z1) - float(hx.z0))
	probe.interior = true
	probe.box_projection = true
	probe.max_distance = 50
	probe.update_mode = ReflectionProbe.UPDATE_ONCE
	probe.intensity = .6
	_owned(_root.get_node("ReflectionProbes"), probe)
	for spec: Array in [["BoilerOil_1", Vector3(29.4, .025, -8.4)], ["BoilerOil_2", Vector3(42.9, .025, -8.4)], ["PumpOil", Vector3(21.7, .025, -9.6)]]:
		var decal: Decal = Decal.new()
		decal.name = String(spec[0])
		decal.position = spec[1]
		decal.size = Vector3(2.6, .1, 1.8)
		decal.texture_albedo = load(TEXTURES + "oil_stain.png")
		decal.texture_orm = load(TEXTURES + "oil_stain_orm.png")
		decal.upper_fade = .02
		decal.lower_fade = .02
		_owned(hall, decal)
