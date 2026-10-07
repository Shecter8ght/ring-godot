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
	_navigation()
	await get_tree().physics_frame
	var region: NavigationRegion3D = _root.get_node("Navigation/Interior") as NavigationRegion3D
	region.bake_navigation_mesh(false)
	await get_tree().process_frame
	ResourceSaver.save(region.navigation_mesh, BASE + "architecture/interior_nav.tres")
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
	assert(ResourceSaver.save(packed, BASE + "Shelter_Interior.tscn") == OK)
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
	var names: Array[String] = ["RawConcrete", "PaintedConcrete", "DampConcrete", "WetConcrete", "IndustrialConcreteFloor", "PaintedSteel", "OchreSteel", "BareSteel", "RustedSteel", "GalvanizedSteel", "DirtyAluminum", "OldWood", "RawWood", "Rubber", "OldPlastic", "Canvas", "MilitaryFabric", "Leatherette", "Glass", "Oil", "PuddleWater", "WornCarpet", "Paper", "Cardboard", "RedPaint", "IndustrialTrim", "Labels", "PlanningMap", "RoomSigns", "WarmEmitter", "CoolEmitter", "Screen"]
	for label: String in names:
		var m: StandardMaterial3D = StandardMaterial3D.new()
		m.resource_name = label
		m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
		var extension: String = ".png" if label in ["IndustrialTrim", "Labels", "PlanningMap", "RoomSigns"] else ".jpg"
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
		if label in ["IndustrialConcreteFloor", "RawConcrete", "PaintedConcrete", "DampConcrete"]:
			m.metallic_specular = 0.35
		# Материал cutaway отдельный от пола/декора с тем же физическим составом.
		ResourceSaver.save(m, BASE + "materials/" + label + ".tres")
		_materials[label] = load(BASE + "materials/" + label + ".tres")
		if label in ["RawConcrete", "PaintedConcrete", "DampConcrete", "BareSteel"]:
			var cut: StandardMaterial3D = m.duplicate() as StandardMaterial3D
			cut.resource_name = label + "_cut"
			cut.distance_fade_mode = BaseMaterial3D.DISTANCE_FADE_PIXEL_DITHER
			ResourceSaver.save(cut, BASE + "materials/" + label + "_cut.tres")
			_materials[label + "_cut"] = load(BASE + "materials/" + label + "_cut.tres")


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
		var saved: Error = ResourceSaver.save(mesh, mesh_path)
		# Windows может кратко удерживать ресурс во время импорта/индексации.
		for attempt: int in range(3):
			if saved == OK: break
			OS.delay_msec(100)
			saved = ResourceSaver.save(mesh, mesh_path)
		assert(saved == OK, "Не сохранён mesh: " + mesh_path)
		mi.mesh = load(mesh_path)
		var t: Transform3D = source.transform
		var ancestor: Node3D = source.get_parent() as Node3D
		while ancestor and ancestor != original:
			t = ancestor.transform * t
			ancestor = ancestor.get_parent() as Node3D
		mi.transform = t
		mi.gi_mode = GeometryInstance3D.GI_MODE_STATIC
		if id.begins_with("Ceiling_") or id in ["Ventilation", "PipesAndElectrical", "PracticalLight"]:
			mi.layers = SectorBuilder.CEILING_LAYER
		if cut:
			mi.set_meta("shelter_cut", true)
		if id.begins_with("RoomSign_"):
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		if id in ["Mug", "FoodCan", "Notebook", "WaterBottle", "Beer", "Boots", "PlanningMap", "Rug"]:
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(mi)
		mi.owner = root
		if id.begins_with("Ceiling_"):
			var shadow: MeshInstance3D = MeshInstance3D.new()
			shadow.name = "CeilingShadow"
			shadow.mesh = mi.mesh
			shadow.transform = mi.transform
			shadow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
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
	var path: String = BASE + ("architecture/" if id.begins_with("Floor_") or id.begins_with("Wall_") or id.begins_with("Ceiling_") or id in ["Ventilation", "PipesAndElectrical", "StairsAndRailing", "TechnicalStructure", "DrainsAndThresholds"] else "props/") + id + ".tscn"
	assert(ResourceSaver.save(packed, path) == OK)
	_kit[id] = load(path)
	root.free()
	original.free()


func _v(a: Array) -> Vector3:
	return Vector3(float(a[0]), float(a[1]), float(a[2]))

func _put(id: String, label: String, parent: Node, at: Vector3, yaw: float = 0.0) -> Node3D:
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
		if id.begins_with("Floor_") or id.begins_with("Wall_") or id.begins_with("Ceiling_") or id in ["Ventilation", "PipesAndElectrical", "StairsAndRailing", "TechnicalStructure", "DrainsAndThresholds"]:
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
	_put("Bench", "StorageSortBench", storage, Vector3(17.2, 0, 4.0), -90)
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
		ResourceSaver.save(reverb,BASE+"materials/audio_"+String(spec[0])+".tres")
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
		var rifle: Node3D = _put("Display_wpn_ar_03","RackRifle_%02d" % details.get_child_count(),details,Vector3(x,.59,1.65))
		rifle.rotation_degrees.x = -90
	_put("Display_wpn_hg_01","MaintenancePistol",details,Vector3(-12.2,.77,4.25),90)
	# Резерв у стен, рабочие полки заполнены по назначению; основные проходы остаются свободны.
	for spec: Array in [["PH_Crate","HubRouteCrate",Vector3(-3.7,0,-2.9),12],["PH_Crate","HubRouteCrate2",Vector3(-3.7,.34,-2.9),12],["PH_AmmoBox","HubAmmo",Vector3(-3.25,0,-2.55),0],["PH_Crate","ArmoryReserve",Vector3(-16.4,0,4.0),90],["PH_Crate","StorageReserve1",Vector3(16.4,0,3.0),0],["PH_Crate","StorageReserve2",Vector3(16.4,.34,3.0),0],["PH_Crate","StorageReserve3",Vector3(16.4,0,4.1),0],["PH_Barrel","GeneratorDrum",Vector3(10.7,0,-10.25),0],["PH_Barrel","WorkshopDrum",Vector3(16.7,0,-4.35),0],["PH_Barrel","StorageWaterDrum",Vector3(17.0,0,5.95),0],["PH_AmmoBox","ArmoryAmmo1",Vector3(-11.7,.76,3.9),0],["PH_AmmoBox","ArmoryAmmo2",Vector3(-16.5,.26,6.0),90],["PH_AmmoBox","TraderAmmo",Vector3(-15.95,1.14,-4.4),0],["PH_Crate","TraderDelivery",Vector3(-17.2,0,-3.6),0],["PH_Crate","EntryShipment",Vector3(2.65,0,11.2),0],["Rug","UnloadingMat",Vector3(0,0,8.6),0],["Bench","HubRestBench",Vector3(-6.5,0,-.1),90],["Bench","BayBench1",Vector3(-5.1,0,6.5),0],["Bench","BayBench2",Vector3(5.1,0,6.5),0],["Bench","BayBench3",Vector3(7.25,0,6.5),0],["Shelf","WorkshopReserveShelf",Vector3(10.5,0,-4.4),0],["Shelf","ArmoryReserveShelf",Vector3(-17.4,0,3.4),90],["Shelf","LivingFoodShelf",Vector3(-10.2,0,-10.45),0],["Counter","StorageSortingDesk",Vector3(13.7,0,1.55),180],["MedicalCase","SortingFirstAid",Vector3(13.3,.97,1.55),180],["Notebook","SortingLedger",Vector3(14.3,.97,1.55),0],["PH_Crate","UnderSortingDesk",Vector3(13.5,0,1.55),0],["Case","HubMedicReserve",Vector3(-6.5,0,-5.65),0]]:
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
		ResourceSaver.save(mesh,path)
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
	ResourceSaver.save(packed,target)
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
	ResourceSaver.save(mesh,BASE+"architecture/floor_joints.res")
	var node: MeshInstance3D = MeshInstance3D.new()
	node.name = "SH_Int_ConcreteConstructionJoints"
	node.mesh = load(BASE+"architecture/floor_joints.res")
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_owned(_root.get_node("Architecture"),node)


func _lighting() -> void:
	var lights: Node = _root.get_node("Lights")
	for spec: Array in [["HubWest",Vector3(-3.9,3.6,0),Color(1,.82,.58),3.8,8.0,true],["HubEast",Vector3(3.9,3.6,0),Color(1,.82,.58),3.8,8.0,true],["NorthGallery",Vector3(0,2.0,-6),Color(1,.78,.50),2.4,5.0,false],["Entry",Vector3(0,2.7,9.7),Color(1,.78,.48),2.8,5.0,true],["Living",Vector3(-13.0,2.65,-8.0),Color(1,.66,.34),2.9,5.5,true],["Trader",Vector3(-12.8,2.65,-2.0),Color(1,.78,.52),3.1,5.0,false],["Armory",Vector3(-12.8,2.65,4.0),Color(1,.86,.66),3.0,5.3,false],["Workshop",Vector3(13.0,2.65,-2.5),Color(1,.88,.73),3.8,5.5,true],["Storage",Vector3(13.0,2.65,4),Color(1,.83,.61),2.9,5.5,false],["Generator",Vector3(13.0,2.65,-8.0),Color(.90,.95,1),3.5,5.5,true],["Sleeping",Vector3(0,4.65,-9.2),Color(1,.73,.45),1.8,4.5,false],["Bays",Vector3(5.3,2.9,6.6),Color(1,.8,.54),1.9,3.8,false],["BaysWest",Vector3(-5.3,2.9,6.6),Color(1,.8,.54),1.9,3.8,false]]:
		var light: OmniLight3D = OmniLight3D.new()
		light.name = String(spec[0])
		light.position = spec[1]
		light.light_color = spec[2]
		if light.name in [&"HubWest",&"HubEast",&"Trader",&"Workshop",&"Armory",&"Storage"]:
			light.light_color = Color(1,.94,.85)
		elif light.name in [&"Entry",&"NorthGallery",&"Sleeping",&"Bays",&"BaysWest",&"Living"]:
			light.light_color = Color(1,.86,.70)
		light.light_energy = float(spec[3])
		light.omni_range = float(spec[4])
		light.omni_attenuation = 1.5
		light.shadow_enabled = bool(spec[5]) or light.name in [&"Trader",&"Armory",&"Storage",&"Sleeping"]
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
	for spec: Array in [["LivingWall",Vector3(-17.65,2.05,-8.2),90],["TraderWall",Vector3(-17.65,2.05,-3.4),90],["ArmoryWall",Vector3(-17.65,2.05,3.4),90],["StorageWall",Vector3(17.65,2.05,4.6),-90],["WorkshopWall",Vector3(17.65,2.05,-1.7),-90],["GeneratorWall",Vector3(10.8,2.05,-10.7),0],["HubWallLeft",Vector3(-7.65,2.05,1.15),90],["HubWallRight",Vector3(7.65,2.05,1.15),-90]]:
		var light: OmniLight3D = OmniLight3D.new()
		light.name = String(spec[0])
		light.position = spec[1]
		if light.name == &"HubWallLeft":
			light.position.z = 2.55
		light.light_color = Color(1,.90,.76)
		light.light_energy = 1.25
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
	mesh.filter_baking_aabb = AABB(Vector3(-19,-.25,-12),Vector3(38,3.3,25))
	var region: NavigationRegion3D = NavigationRegion3D.new()
	region.name = "Interior"
	region.navigation_mesh = mesh
	_owned(_root.get_node("Navigation"),region)
