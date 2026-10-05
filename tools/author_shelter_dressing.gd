extends Node
## Добавляет законченный художественный слой к существующей сцене, сохраняя её правки.

const BASE: String = "res://levels/shelter/"
const INPUT: String = "res://assets/shelter/dressing/"
const FX: String = "res://assets/shelter/atmosphere/"
var _level: Node3D
var _group: Node3D
var _placements: Array[Dictionary] = []
var _material: StandardMaterial3D

func _ready() -> void:
	Profile.use_file("user://dressing_author_test.json", true)
	DirAccess.make_dir_recursive_absolute(BASE + "dressing")
	DirAccess.make_dir_recursive_absolute(BASE + "atmosphere")
	_make_material()
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(INPUT + "manifest.json")) as Dictionary
	for id: String in manifest:
		_convert(id, manifest[id])
	_effect("DustMotes", "DustSoft", Color(.74,.69,.58), .85)
	_effect("KettleVapor", "VaporSoft", Color(.82,.81,.75), .65)
	_level = (load(BASE + "Shelter_Interior.tscn") as PackedScene).instantiate() as Node3D
	# Сохранённая копия до добавления слоя остаётся в сырье, не в runtime.
	DirAccess.make_dir_recursive_absolute("res://_asset_src/shelter/dressing")
	if not FileAccess.file_exists("res://_asset_src/shelter/dressing/Shelter_before_dressing.tscn"):
		DirAccess.copy_absolute(BASE + "Shelter_Interior.tscn", "res://_asset_src/shelter/dressing/Shelter_before_dressing.tscn")
	var previous: Node = _level.get_node_or_null("Dressing")
	if previous: previous.free()
	previous = _level.get_node_or_null("Atmosphere")
	if previous: previous.free()
	_group = Node3D.new()
	_group.name = "Dressing"
	_level.add_child(_group)
	_group.owner = _level
	_layout()
	_atmosphere()
	# Новые напольные предметы включены в сохранённую навигацию.
	var original_script: Script = _level.get_script() as Script
	_level.set_script(null)
	add_child(_level)
	await get_tree().physics_frame
	var region: NavigationRegion3D = _level.get_node("Navigation/Interior") as NavigationRegion3D
	region.navigation_mesh = region.navigation_mesh.duplicate() as NavigationMesh
	# Сохранить высоту шага сетки для связности лестницы и антресоли.
	region.navigation_mesh.cell_size = .25
	region.navigation_mesh.cell_height = .25
	region.navigation_mesh.agent_max_climb = .5
	region.bake_navigation_mesh(false)
	assert(ResourceSaver.save(region.navigation_mesh, BASE + "architecture/interior_nav.tres") == OK)
	_level.set_script(original_script)
	var packed: PackedScene = PackedScene.new()
	assert(packed.pack(_level) == OK)
	assert(ResourceSaver.save(packed, BASE + "Shelter_Interior.tscn") == OK)
	var file: FileAccess = FileAccess.open(BASE + "dressing/placements.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(_placements, "\t"))
	_sync_metadata(manifest, region.navigation_mesh.get_polygon_count())
	print("DRESSING_AUTHORED " + JSON.stringify({"assets":manifest.size(),"placements":_placements.size(),"effects":_level.get_node("Atmosphere").get_child_count(),"nav_polygons":region.navigation_mesh.get_polygon_count(),"runtime_generation":false}))
	get_tree().quit()

func _sync_metadata(manifest: Dictionary, polygons: int) -> void:
	var original: Array = JSON.parse_string(FileAccess.get_file_as_string(BASE+"placements.json")) as Array
	var combined: Array[Dictionary] = []
	for entry: Dictionary in original:
		if manifest.has(String(entry.asset)): continue
		var found: Array[Node] = _level.find_children(String(entry.name),"Node3D",true,false)
		if found.is_empty(): continue
		var node: Node3D = found[0] as Node3D
		entry.position = [node.position.x,node.position.y,node.position.z]
		entry.yaw = rad_to_deg(node.rotation.y)
		entry["rotation_degrees"] = [node.rotation_degrees.x,node.rotation_degrees.y,node.rotation_degrees.z]
		combined.append(entry)
	for entry: Dictionary in _placements:
		var node: Node3D = _group.get_node(String(entry.name)) as Node3D
		entry["rotation_degrees"] = [node.rotation_degrees.x,node.rotation_degrees.y,node.rotation_degrees.z]
		combined.append(entry)
	var file: FileAccess = FileAccess.open(BASE+"placements.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(combined,"\t"))
	file = FileAccess.open(BASE+"dressing/placements.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(_placements,"\t"))
	var stats: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://docs/shelter/scene_stats.json")) as Dictionary
	var base_manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/shelter/models/manifest.json")) as Dictionary
	stats.authored_assets = base_manifest.size()+manifest.size()
	stats.prop_instances = combined.size()
	stats.navigation_polygons = polygons
	stats["dressing"] = {"assets":manifest.size(),"placements":_placements.size(),"ucupaint_layers":4,"baked_effect_assets":2,"effect_instances":5,"runtime_particle_simulation":false}
	file = FileAccess.open("res://docs/shelter/scene_stats.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(stats,"\t"))

func _make_material() -> void:
	_material = StandardMaterial3D.new()
	_material.resource_name = "DressingAtlas"
	_material.albedo_texture = load(INPUT + "Dressing_base.png") as Texture2D
	_material.roughness_texture = load(INPUT + "Dressing_roughness.png") as Texture2D
	_material.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	_material.metallic_texture = load(INPUT + "Dressing_metallic.png") as Texture2D
	_material.metallic_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	_material.metallic = 1.0
	_material.roughness = 1.0
	_material.metallic_specular = .35
	_material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	assert(ResourceSaver.save(_material, BASE + "dressing/DressingAtlas.tres") == OK)
	_material = load(BASE + "dressing/DressingAtlas.tres") as StandardMaterial3D

func _convert(id: String, info: Dictionary) -> void:
	var source: Node3D = (load(INPUT + id + ".glb") as PackedScene).instantiate() as Node3D
	var root: Node3D = Node3D.new()
	root.name = id
	var index: int = 0
	for child: Node in source.find_children("*", "MeshInstance3D", true, false):
		var original: MeshInstance3D = child as MeshInstance3D
		var mesh: ArrayMesh = original.mesh.duplicate() as ArrayMesh
		for surface: int in range(mesh.get_surface_count()): mesh.surface_set_material(surface, _material)
		var path: String = BASE + "dressing/" + id + "_%02d.res" % index
		assert(ResourceSaver.save(mesh, path) == OK)
		var instance: MeshInstance3D = MeshInstance3D.new()
		instance.name = "FinishedMesh_%02d" % index
		instance.mesh = load(path) as ArrayMesh
		var transform: Transform3D = original.transform
		var ancestor: Node3D = original.get_parent() as Node3D
		while ancestor and ancestor != source:
			transform = ancestor.transform * transform
			ancestor = ancestor.get_parent() as Node3D
		instance.transform = transform
		instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF if float(info.bounds_m[1]) < .4 else GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		root.add_child(instance)
		instance.owner = root
		index += 1
	if info.collision != null:
		var body: StaticBody3D = StaticBody3D.new()
		body.name = "SimplifiedCollision"
		body.collision_layer = 1
		root.add_child(body)
		body.owner = root
		var shape: BoxShape3D = BoxShape3D.new()
		shape.size = _v(info.collision.size)
		var collider: CollisionShape3D = CollisionShape3D.new()
		collider.name = "Shape"
		collider.shape = shape
		collider.position = _v(info.collision.center)
		body.add_child(collider)
		collider.owner = root
	var packed: PackedScene = PackedScene.new()
	assert(packed.pack(root) == OK)
	assert(ResourceSaver.save(packed, BASE + "dressing/" + id + ".tscn") == OK)
	root.free()
	source.free()

func _effect(id: String, mask: String, tint: Color, opacity: float) -> void:
	var root: Node3D = Node3D.new()
	root.name = id
	root.set_script(load("res://src/hideout/shelter_effect.gd"))
	var visual: Node3D = (load(FX + id + ".glb") as PackedScene).instantiate() as Node3D
	visual.name = "Visual"
	root.add_child(visual)
	visual.owner = root
	var material: ShaderMaterial = ShaderMaterial.new()
	material.shader = load(FX + "soft_density.gdshader") as Shader
	material.set_shader_parameter("density_texture", load(FX + mask + ".png"))
	material.set_shader_parameter("tint", tint)
	material.set_shader_parameter("opacity", opacity)
	assert(ResourceSaver.save(material, BASE + "atmosphere/" + id + ".tres") == OK)
	for node: Node in visual.find_children("*", "MeshInstance3D", true, false):
		var mesh: MeshInstance3D = node as MeshInstance3D
		assert(ResourceSaver.save(mesh.mesh, BASE + "atmosphere/" + id + "_mesh.res") == OK)
		mesh.mesh = load(BASE + "atmosphere/" + id + "_mesh.res") as ArrayMesh
		mesh.material_override = load(BASE + "atmosphere/" + id + ".tres") as ShaderMaterial
		mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mesh.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
	var players: Array[Node] = visual.find_children("*", "AnimationPlayer", true, false)
	assert(players.size() == 1, id + " has no baked animation")
	var player: AnimationPlayer = players[0] as AnimationPlayer
	root.set("animation_path", root.get_path_to(player))
	for label: String in player.get_animation_list():
		if label == "RESET": continue
		player.get_animation(label).loop_mode = Animation.LOOP_LINEAR
		player.autoplay = label
	# Сохранить правки импортированных потомков как явные узлы готового ассета.
	visual.scene_file_path = ""
	_own_subtree(visual, root)
	print("BAKED_EFFECT ", id, " ", player.get_animation_list())
	var packed: PackedScene = PackedScene.new()
	assert(packed.pack(root) == OK)
	assert(ResourceSaver.save(packed, BASE + "atmosphere/" + id + ".tscn") == OK)
	root.free()

func _own_subtree(node: Node, owner_root: Node) -> void:
	for child: Node in node.get_children():
		child.owner = owner_root
		_own_subtree(child, owner_root)

func _v(values: Array) -> Vector3:
	return Vector3(float(values[0]),float(values[1]),float(values[2]))

func _put(id: String, label: String, position: Vector3, yaw: float = 0.0) -> Node3D:
	var node: Node3D = (load(BASE + "dressing/" + id + ".tscn") as PackedScene).instantiate() as Node3D
	node.name = label
	_group.add_child(node)
	node.owner = _level
	node.position = position
	node.rotation.y = deg_to_rad(yaw)
	if node.has_node("SimplifiedCollision"): node.add_to_group("shelter_navigation_geometry", true)
	_placements.append({"asset":id,"name":label,"position":[position.x,position.y,position.z],"yaw":yaw})
	return node

func _layout() -> void:
	# Рабочие поверхности: опора на столешницу и расстояния до старых предметов.
	for spec: Array in [
		["InventoryClipboard","RouteClipboard",Vector3(1.42,.79,.46),-8],
		["BooksStack","RouteFolders",Vector3(-1.43,.79,-.62),4],
		["NoticeBoard","HubNoticeBoard",Vector3(7.70,1.65,-.1),-90],
		["CableJunction","CommunicationsWiring",Vector3(7.67,.88,2.30),-90],
		["WorkGloves","UnloadGloves",Vector3(-3.48,.49,9.65),90],
		["HangingJacket","ReturnJacket",Vector3(-3.70,.52,10.50),90],
		["CleaningBucket","ReturnCleaning",Vector3(-3.38,0,11.24),0],
		["FireExtinguisher","EntryFireSafety",Vector3(3.68,.35,9.70),-90],
		["DrapedBlanket","SofaBlanket",Vector3(-13.90,.46,-7.52),180],
		["Cushion","SofaCushion",Vector3(-12.65,.43,-7.52),0],
		["BooksStack","LivingBooks",Vector3(-13.78,.496,-8.90),-12],
		["TeaStation","TeaCorner",Vector3(-16.35,0,-10.35),0],
		["TeaSet","KettleAndCups",Vector3(-16.35,.944,-10.35),0],
		["WallClock","LivingClock",Vector3(-17.73,2.25,-6.85),90],
		["FoldedTowel","TeaTowel",Vector3(-16.66,.225,-10.35),0],
		["BooksStack","PersonalBooks",Vector3(-17.4,1.62,-8.0),90],
		["CounterScales","TraderScales",Vector3(-12.90,.975,-2.01),0],
		["Calculator","TraderCalculator",Vector3(-12.36,.975,-2.04),12],
		["InventoryClipboard","TradeInventory",Vector3(-12.0,.975,-2.04),-7],
		["RepairTools","WorkshopCurrentRepair",Vector3(13.15,.945,-4.16),0],
		["OpenToolbox","WorkshopToolbox",Vector3(14.12,.945,-4.43),0],
		["PartsOrganizer","WorkshopDrawerBins",Vector3(13.95,1.12,-4.55),0],
		["CleaningRag","WorkshopRag",Vector3(14.50,.951,-4.00),20],
		["WeaponCleaningSet","WeaponService",Vector3(-13.55,.765,4.21),0],
		["AmmoAndMagazines","WeaponAmmo",Vector3(-12.78,.768,4.48),12],
		["HearingProtection","ArmoryHeadset",Vector3(-13.62,.765,3.75),10],
		["WorkGloves","ArmoryGloves",Vector3(-12.91,.765,3.79),-20],
		["MeterPanel","GeneratorMeters",Vector3(15.42,.97,-10.74),0],
		["CableJunction","GeneratorCableDrop",Vector3(15.95,.20,-10.73),0],
		["GeneratorServiceDetails","GeneratorFittings",Vector3(13.8,0,-8.33),0],
		["ExhaustConnection","GeneratorExhaustRoute",Vector3(12.75,2.60,-8.82),0],
		["FireExtinguisher","GeneratorFireSafety",Vector3(10.04,.40,-10.73),0],
		["InventoryClipboard","GeneratorServiceLog",Vector3(15.03,.88,-10.73),0],
		["HandTruck","StorageHandTruck",Vector3(17.08,0,2.03),-90],
		["MixedCartons","SortingDelivery",Vector3(12.86,.975,1.60),180],
		["InventoryClipboard","WarehouseInventory",Vector3(13.85,.975,1.58),12],
		["WorkGloves","WarehouseGloves",Vector3(14.58,.975,1.53),-7]
	]: _put(String(spec[0]),String(spec[1]),spec[2],float(spec[3]))
	(_group.get_node("GeneratorServiceLog") as Node3D).rotation_degrees.x = 90
	# Выкладка заранее задана для каждой полки, без случайного заполнения.
	for spec: Array in [
		["FoodStock",-16.6,1.15,-4.39,0],["WaterStock",-14.8,.665,-4.43,0],["BatteryStock",-13.0,1.62,-4.4,0],
		["MedicalStock",-16.7,1.62,-4.4,0],["MixedCartons",-14.8,1.62,-4.4,0],["FoodStock",-13,.665,-4.39,0],
		["FoodStock",10.2,1.62,6.25,180],["WaterStock",12,1.62,6.25,180],["MixedCartons",13.8,1.62,6.3,180],
		["BatteryStock",15.6,1.62,6.3,180],["MedicalStock",15.6,.665,6.3,180],["FoodStock",13.8,.665,6.3,180],
		["MixedCartons",12,.665,6.3,180],["SupplySack",15.6,1.14,6.30,180],["SupplySack",10.2,.665,6.3,180],
		["MixedCartons",10.2,1.14,6.3,180],["MedicalStock",12,1.14,6.3,180],["FoodStock",13.8,1.14,6.3,180],
		["PartsOrganizer",17.40,1.15,-2.0,-90],["MixedCartons",10.50,1.15,-4.40,0],["BatteryStock",10.5,1.62,-4.4,0],
		["AmmoAndMagazines",-17.40,.665,3.25,90],["MedicalStock",-17.4,1.15,3.3,90],["MixedCartons",-17.4,1.62,3.3,90],
		["BooksStack",-10.2,1.62,-10.45,0],["SupplySack",-10.2,.18,-10.45,0]
	]:
		_put(String(spec[0]),"Stock_%02d" % _group.get_child_count(),Vector3(float(spec[1]),float(spec[2]),float(spec[3])),float(spec[4]))
	# Заменить повторённые ящики на выделенных заполненных полках, оставив нижний запас.
	for label: String in ["SupplyTop_*","TradeMedical_04","TradeMedical_07","TradeCarton_06","TradeCarton_09","StorageCarton_*","MedicalSupplies"]:
		var nodes: Array[Node] = _level.find_children(label,"Node3D",true,false)
		for node: Node in nodes: node.free()
	for spec: Array in [["MaintenanceTable",Vector3(-13.0,0,4.1)],["MaintenancePistol",Vector3(-13.0,.77,4.25)],["AmmoCase",Vector3(-16.5,0,5.3)],["ArmoryAmmo1",Vector3(-16.6,0,4.8)],["ArmoryHelmet",Vector3(-12.22,.78,4.1)],["TraderHelmet",Vector3(-13.47,1.65,-4.38)],["BayHelmet",Vector3(-5.75,.49,6.50)]]:
		var nodes: Array[Node] = _level.find_children(String(spec[0]),"Node3D",true,false)
		for node: Node in nodes: (node as Node3D).position = spec[1]
	# Пистолет лежит боком; высота учитывает фактическую толщину сохранённого меша.
	var pistol: Node3D = _level.find_children("MaintenancePistol", "Node3D", true, false)[0] as Node3D
	pistol.rotation.z = PI / 2.0
	pistol.position.y = 0.0
	var lowest: float = INF
	for node: Node in pistol.find_children("*", "MeshInstance3D", true, false):
		var mesh: MeshInstance3D = node as MeshInstance3D
		var bounds: AABB = pistol.transform * mesh.transform * mesh.get_aabb()
		lowest = minf(lowest, bounds.position.y)
	pistol.position.y = .767 - lowest
	# Боксы и антресоль: предметы на существующих лавках и тумбах.
	for i: int in range(3):
		var x: float = [-5.1,5.1,7.4][i]
		_put("WorkGloves","BayGloves_%d"%i,Vector3(x-.32,.491,6.49),float(i*13-12))
		_put("HearingProtection","BayHeadset_%d"%i,Vector3(x+.10,.491,6.52),float(i*10))
		_put("FoldedTowel","BayCloth_%d"%i,Vector3(x+.58,.525,6.47),0)
		var bed_x: float = [-2.15,0.0,2.15][i]
		_put("BedBlanket","SleepingBlanket_%d"%i,Vector3(bed_x,3.29,-9.02),0)
		_put("BooksStack","BedsideBooks_%d"%i,Vector3(bed_x-.25,3.135,-10.65),float(i*6))
		_put("FoldedTowel","SleepingTowel_%d"%i,Vector3(bed_x+.13,3.156,-10.67),0)

func _atmosphere() -> void:
	var group: Node3D = Node3D.new()
	group.name = "Atmosphere"
	_level.add_child(group)
	group.owner = _level
	for spec: Array in [["DustMotes","HubDustWest",Vector3(-3.9,1.6,0),0],["DustMotes","HubDustEast",Vector3(3.9,1.6,0),180],["DustMotes","LivingDust",Vector3(-13.3,1.2,-8.0),0],["DustMotes","ArmoryDust",Vector3(-12.8,1.3,4.0),180],["KettleVapor","TeaVapor",Vector3(-16.35,1.16,-10.35),0]]:
		var node: Node3D = (load(BASE + "atmosphere/" + String(spec[0]) + ".tscn") as PackedScene).instantiate() as Node3D
		node.name = String(spec[1])
		node.position = spec[2]
		node.rotation.y = deg_to_rad(float(spec[3]))
		group.add_child(node)
		node.owner = _level
