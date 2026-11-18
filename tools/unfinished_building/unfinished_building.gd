extends Node3D

const MODEL_PATH := "res://assets/models/unfinished_building/%s.gltf"
const SURFACE_PATH := "res://assets/textures/unfinished_building/%s/%s_4K_%s.jpg"
const PLAYER_SCENE := preload("res://scenes/player/player.tscn")
const CAMERA_SCENE := preload("res://scenes/player/camera_rig.tscn")
const PUDDLE_SHADER := preload("res://tools/unfinished_building/puddle.gdshader")
const PUDDLE_WATER_SHADER := preload("res://tools/unfinished_building/puddle_water.gdshader")
const COLUMN_IDS := ["ujjleixga", "ujikdbrva", "ujjmecwba", "ukigcctfa"]
const BEAM_IDS := ["ujymbbdba", "ujlkbd1ga", "ujoqec3ga", "uknlcbaqx"]
const DEBRIS_IDS := ["tl0kcdmiw", "tl0mbbihw", "tl1gdgyhw", "tmclbcpiw", "tmclcaeiw", "tmjgderjw", "uc1iccejw", "uc1jagbjw", "uc1jagnjw"]

var _materials: Dictionary = {}
var _models: Dictionary = {}
var _solid: StaticBody3D
var _failures := 0
var _player: Player
var _random := RandomNumberGenerator.new()


func _ready() -> void:
	RaidEvents.enabled = false
	var sun := $Sun as DirectionalLight3D
	var toward_sun := Vector3(-0.82, 0.03, 0.55).normalized()
	sun.global_basis = Basis.looking_at(-toward_sun, Vector3.UP)
	_random.seed = 25042024
	_solid = StaticBody3D.new()
	_solid.name = "ArchitectureCollision"
	_solid.collision_layer = Hitscan.LAYER_WORLD
	_solid.collision_mask = 0
	add_child(_solid)
	_build_shell()
	_build_structure()
	_build_props()
	_build_puddles()
	var args := OS.get_cmdline_user_args()
	if args.has("--shots"):
		await _shots()
		return
	_spawn_player()
	if args.has("--check"):
		await _run_checks()


func _texture(id: String, channel: String) -> Texture2D:
	var path := SURFACE_PATH % [id, id, channel]
	if not ResourceLoader.exists(path):
		return null
	return load(path) as Texture2D


func _surface(id: String, tile_m: float, relief_m: float) -> StandardMaterial3D:
	if _materials.has(id):
		return _materials[id] as StandardMaterial3D
	var material := StandardMaterial3D.new()
	material.resource_name = "UB_" + id
	material.albedo_texture = _texture(id, "Albedo")
	material.normal_enabled = true
	material.normal_texture = _texture(id, "Normal")
	material.roughness = 1.0
	material.roughness_texture = _texture(id, "Roughness")
	material.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	material.ao_enabled = true
	material.ao_texture = _texture(id, "AO")
	material.ao_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	material.heightmap_enabled = false
	material.heightmap_texture = _texture(id, "Displacement")
	material.heightmap_scale = relief_m
	material.heightmap_deep_parallax = true
	material.uv1_triplanar = true
	material.uv1_world_triplanar = true
	material.uv1_scale = Vector3.ONE / tile_m
	material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	_materials[id] = material
	return material


func _box(label: String, at: Vector3, size: Vector3, material: Material, solid := true) -> MeshInstance3D:
	var box := BoxMesh.new()
	box.size = size
	var visual := MeshInstance3D.new()
	visual.name = label
	visual.mesh = box
	visual.material_override = material
	visual.position = at
	visual.gi_mode = GeometryInstance3D.GI_MODE_STATIC
	add_child(visual)
	if solid:
		_box_collision(at, size)
	return visual


func _box_collision(at: Vector3, size: Vector3, rotation := Vector3.ZERO) -> CollisionShape3D:
	var shape := BoxShape3D.new()
	shape.size = size
	var collision := CollisionShape3D.new()
	collision.shape = shape
	collision.position = at
	collision.rotation = rotation
	collision.set_meta("surface", "concrete")
	_solid.add_child(collision)
	return collision


func _model(id: String, at: Vector3, yaw := 0.0, scale_factor := 1.0) -> Node3D:
	if not _models.has(id):
		_models[id] = load(MODEL_PATH % id) as PackedScene
	var packed := _models[id] as PackedScene
	if packed == null:
		_failures += 1
		push_error("Не загружена модель " + id)
		return null
	var model := packed.instantiate() as Node3D
	model.name = "UB_" + id
	model.position = at
	model.rotation.y = yaw
	model.scale = Vector3.ONE * scale_factor
	add_child(model)
	for node: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		node.gi_mode = GeometryInstance3D.GI_MODE_STATIC
	return model


func _build_shell() -> void:
	var floor_material := _surface("ugtkadmg", 3.0, 0.018)
	floor_material.albedo_color = Color(0.46, 0.48, 0.45)
	var wall_material := _surface("uflnbcofw", 3.2, 0.012)
	var stained_material := _surface("ug3sbcady", 3.4, 0.015)
	stained_material.albedo_color = Color(0.68, 0.69, 0.63)
	var ceiling_material := _surface("ugkjec3ew", 3.6, 0.024)
	ceiling_material.albedo_color = Color(0.48, 0.50, 0.47)
	_box("Floor", Vector3(0, -0.16, 0.5), Vector3(19, 0.32, 18), floor_material)
	_box("Ceiling", Vector3(0, 3.04, 0.5), Vector3(19, 0.34, 18), ceiling_material)
	_box("RightWall", Vector3(9.15, 1.52, 0.5), Vector3(0.30, 3.36, 18), stained_material)
	_box("RearRightWall", Vector3(5.0, 1.52, -8.15), Vector3(8.0, 3.36, 0.30), stained_material)
	_box("RearLeftWall", Vector3(-8.0, 1.52, -8.15), Vector3(2.0, 3.36, 0.30), wall_material)
	_box("RearLintel", Vector3(-3.0, 2.87, -8.15), Vector3(8.0, 0.66, 0.30), wall_material)
	_box("RearKneeWall", Vector3(-3.0, 0.40, -8.15), Vector3(8.0, 0.80, 0.30), wall_material)
	_box("FrontWall", Vector3(0, 1.52, 9.15), Vector3(18.6, 3.36, 0.30), wall_material)
	_box("LeftRearWall", Vector3(-9.15, 1.52, -6.5), Vector3(0.30, 3.36, 3.0), wall_material)
	_box("LeftFrontWall", Vector3(-9.15, 1.52, 6.0), Vector3(0.30, 3.36, 6.0), wall_material)
	_box("LeftLintel", Vector3(-9.15, 2.87, -1.0), Vector3(0.30, 0.66, 8.0), wall_material)
	_box("ExteriorGround", Vector3(0, -0.20, 0), Vector3(80, 0.20, 80), _surface("ugtmehro", 4.0, 0.0))


func _build_structure() -> void:
	var index := 0
	for z in [3.0, -2.5]:
		for x in [-4.5, 0.0, 4.5]:
			_model(COLUMN_IDS[index % COLUMN_IDS.size()], Vector3(x, 0.0, z))
			var shape := CylinderShape3D.new()
			shape.radius = 0.23
			shape.height = 2.50
			var collision := CollisionShape3D.new()
			collision.shape = shape
			collision.position = Vector3(x, 1.25, z)
			_solid.add_child(collision)
			index += 1
	for z in [3.0, -2.5]:
		for i in range(5):
			_model(BEAM_IDS[i % BEAM_IDS.size()], Vector3(-7.0 + i * 3.5, 2.83, z))
		_box_collision(Vector3(0, 2.67, z), Vector3(18.0, 0.34, 0.36))
	for x in [-4.5, 0.0, 4.5]:
		for i in range(5):
			_model(BEAM_IDS[(i + 1) % BEAM_IDS.size()], Vector3(x, 2.80, -6.5 + i * 3.5), PI * 0.5)
		_box_collision(Vector3(x, 2.65, 0.5), Vector3(0.36, 0.32, 17.5))
	_model("uiznce1ga", Vector3(-3.3, 0.0, -4.8))
	_box_collision(Vector3(-3.3, 0.60, -6.28), Vector3(1.68, 0.18, 3.20), Vector3(deg_to_rad(22.8), 0, 0))


func _exterior_mounds() -> void:
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	var columns := 40
	var rows := 22
	for z in range(rows):
		for x in range(columns):
			var a := Vector3(-32.0 + x * 1.6, 0, -44.0 + z * 1.6)
			var b := a + Vector3(1.6, 0, 0)
			var c := a + Vector3(0, 0, 1.6)
			var d := a + Vector3(1.6, 0, 1.6)
			for point in [a, c, b, b, c, d]:
				point.y = -0.10 + maxf(0.0, sin(point.x * 0.13 + point.z * 0.09)) * 1.25
				surface.set_uv(Vector2(point.x, point.z) * 0.25)
				surface.add_vertex(point)
	surface.generate_normals()
	var terrain := MeshInstance3D.new()
	terrain.name = "ExteriorMounds"
	terrain.mesh = surface.commit()
	terrain.material_override = _surface("ugtmehro", 4.0, 0.0)
	terrain.gi_mode = GeometryInstance3D.GI_MODE_STATIC
	add_child(terrain)


func _build_props() -> void:
	_model("tfxteboda", Vector3(-6.4, 0.02, -5.8), 0.35)
	_model("tgdtfg0da", Vector3(6.4, 0.02, -5.9), -0.6)
	_model("riuvL", Vector3(-5.8, 0.0, 1.2), 0.8)
	_model("rjgmQ", Vector3(4.7, 0.0, 1.7), -0.4)
	_model("uizhacnga", Vector3(-6.2, 0.31, -1.7), 0.3).rotation.z = PI * 0.5
	_model("ukxkbesqa", Vector3(6.8, 0.0, -0.8), -0.5)
	_model("vh1icei", Vector3(5.9, 0.0, 4.5), 0.25)
	_model("vidkbho", Vector3(6.7, 0.02, 3.9), -0.25)
	_model("vjwnfiz", Vector3(-6.4, 0.02, 4.6), 0.6)
	_model("vjwtbd1", Vector3(-5.8, 0.025, 4.2), -0.2)
	_exterior_mounds()
	for i in range(95):
		var id: String = DEBRIS_IDS[i % DEBRIS_IDS.size()]
		var at := Vector3(_random.randf_range(-8.3, 8.3), 0.035, _random.randf_range(-7.3, 7.8))
		if Vector2(at.x, at.z - 5.5).length() < 1.6:
			continue
		var model := _model(id, at, _random.randf_range(-PI, PI), _random.randf_range(0.65, 1.3))
		if model:
			model.rotation.x = _random.randf_range(-0.08, 0.08)
			model.rotation.z = _random.randf_range(-0.08, 0.08)
	for i in range(8):
		var id := "vk2sdis" if i % 2 == 0 else "vk2vcdl"
		_model(id, Vector3(5.3 + (i % 3) * 0.42, 0.20 * (i / 3), 5.8 + (i % 2) * 0.24), _random.randf_range(-0.2, 0.2))


func _puddle_mesh(at: Vector3, radius: Vector2, seed_value: int, material: Material) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	var points: Array[Vector3] = []
	var phase := rng.randf_range(0.0, TAU)
	for i in range(64):
		var angle := TAU * float(i) / 64.0
		var variation := 1.0 + 0.13 * sin(angle * 3.0 + phase) + 0.07 * sin(angle * 5.0 - phase * 0.7) + 0.035 * sin(angle * 9.0 + phase * 1.3)
		points.append(Vector3(cos(angle) * radius.x * variation, 0, sin(angle) * radius.y * variation))
	for i in range(64):
		var a := points[i]
		var b := points[(i + 1) % 64]
		for point in [Vector3.ZERO, b, a]:
			surface.set_normal(Vector3.UP)
			surface.set_uv(Vector2(point.x / radius.x, point.z / radius.y) * 0.5)
			surface.add_vertex(point + at)
	var visual := MeshInstance3D.new()
	visual.name = "Puddle"
	visual.mesh = surface.commit()
	visual.material_override = material
	visual.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(visual)


func _build_puddles() -> void:
	var edge := ShaderMaterial.new()
	edge.shader = PUDDLE_SHADER
	var water := ShaderMaterial.new()
	water.shader = PUDDLE_WATER_SHADER
	var puddles := [
		[Vector3(-2.8, 0.008, 2.0), Vector2(2.2, 0.85)],
		[Vector3(0.4, 0.008, 0.8), Vector2(1.4, 0.72)],
		[Vector3(-4.8, 0.008, -2.0), Vector2(1.35, 0.65)],
		[Vector3(3.5, 0.008, -3.8), Vector2(1.1, 0.48)],
		[Vector3(1.4, 0.008, 5.5), Vector2(0.8, 0.42)],
	]
	for i in range(puddles.size()):
		var entry: Array = puddles[i]
		var at: Vector3 = entry[0]
		var radius: Vector2 = entry[1]
		_puddle_mesh(at, radius, 900 + i, water)
		at.y += 0.001
		_puddle_mesh(at, radius * 1.14, 900 + i, edge)


func _spawn_player() -> void:
	Profile.use_file("user://profile_unfinished_building.json", true)
	_player = PLAYER_SCENE.instantiate() as Player
	_player.name = "Player_1"
	add_child(_player)
	_player.position = Vector3(0, 0.05, 7.4)
	_player.cursor_ground = Vector3(0, 0, -3.0)
	var rig := CAMERA_SCENE.instantiate() as CameraRig
	add_child(rig)
	rig.set_target(_player)
	rig._look_yaw = PI


func _run_checks() -> void:
	for i in range(30):
		await get_tree().physics_frame
	_check("Игрок стоит на бетонном полу", _player.is_on_floor())
	_check("Колонна имеет физическое тело", _ray(Vector3(0, 1.2, 3.8), Vector3(0, 1.2, 2.2)).size() > 0)
	_check("Проём за лестницей свободен", _ray(Vector3(-3.3, 1.4, -7.6), Vector3(-3.3, 1.4, -8.8)).is_empty())
	_check("Задняя стена справа сохранила коллизию", _ray(Vector3(5, 1.4, -7.6), Vector3(5, 1.4, -8.8)).size() > 0)
	print("UNFINISHED_BUILDING: %d failures" % _failures)
	get_tree().quit(1 if _failures else 0)


func _ray(from: Vector3, to: Vector3) -> Dictionary:
	var query := PhysicsRayQueryParameters3D.create(from, to, Hitscan.LAYER_WORLD)
	return get_world_3d().direct_space_state.intersect_ray(query)


func _check(label: String, ok: bool) -> void:
	print(("OK " if ok else "FAIL ") + label)
	if not ok:
		_failures += 1


func _shots() -> void:
	var path := "res://docs/screens/unfinished_building"
	DirAccess.make_dir_recursive_absolute(path)
	var camera := Camera3D.new()
	camera.name = "ReferenceCamera"
	camera.near = 0.05
	camera.fov = 58.0
	add_child(camera)
	camera.make_current()
	var views := [
		["main", Vector3(0.0, 1.58, 7.4), Vector3(-3.2, 1.25, -3.5)],
		["stairs", Vector3(-0.6, 1.45, 1.8), Vector3(-3.3, 0.85, -5.7)],
		["floor", Vector3(-1.0, 0.82, 4.5), Vector3(-2.8, 0.05, 1.8)],
	]
	RenderingServer.viewport_set_measure_render_time(get_viewport().get_viewport_rid(), true)
	var only := OS.get_environment("UB_ONLY")
	for view: Array in views:
		if not only.is_empty() and view[0] != only:
			continue
		camera.position = view[1]
		camera.look_at(view[2], Vector3.UP)
		for i in range(100):
			await get_tree().process_frame
		var gpu_times := PackedFloat32Array()
		for i in range(30):
			await RenderingServer.frame_post_draw
			gpu_times.append(RenderingServer.viewport_get_measured_render_time_gpu(get_viewport().get_viewport_rid()))
		gpu_times.sort()
		print("GPU %s: %.2f ms" % [view[0], gpu_times[15]])
		var file := path.path_join(view[0] + ".png")
		var error := get_viewport().get_texture().get_image().save_png(file)
		_check("Сохранён " + file, error == OK)
	get_tree().quit(1 if _failures else 0)
