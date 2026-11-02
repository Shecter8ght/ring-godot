extends Node3D
## Imported geometry, physical scale, separate movers, glass and Forward+ appearance.

var _camera: Camera3D
var _passed: int = 0
var _failed: int = 0
var _report: Dictionary = {}


func _ready() -> void:
	var flashlight: Node3D = DozorAsset.flashlight()
	var clamp: Node3D = DozorAsset.mount()
	add_child(flashlight)
	add_child(clamp)
	if OS.get_environment("DOZOR_DEBUG_ALBEDO") == "on":
		for model: Node3D in [flashlight, clamp]:
			for node: Node in model.find_children("*", "MeshInstance3D", true, false):
				var mat: Material = (node as MeshInstance3D).material_override
				if mat is StandardMaterial3D:
					(mat as StandardMaterial3D).shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
					(mat as StandardMaterial3D).albedo_color = Color(6, 6, 6)
	if OS.get_environment("DOZOR_DEBUG_LOD") == "off":
		for model: Node3D in [flashlight, clamp]:
			for node: Node in model.find_children("*", "MeshInstance3D", true, false):
				var instance: MeshInstance3D = node as MeshInstance3D
				var full: ArrayMesh = ArrayMesh.new()
				for si: int in range(instance.mesh.get_surface_count()):
					full.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, instance.mesh.surface_get_arrays(si))
				instance.mesh = full
	if OS.get_environment("DOZOR_DEBUG_NORMALS") == "off":
		for model: Node3D in [flashlight, clamp]:
			for node: Node in model.find_children("*", "MeshInstance3D", true, false):
				var mat: Material = (node as MeshInstance3D).material_override
				if mat is StandardMaterial3D:(mat as StandardMaterial3D).normal_enabled = false
	var ft: int = _triangles(flashlight)
	var mt: int = _triangles(clamp)
	_check(ft + mt <= DozorAsset.TRIANGLE_LIMIT, "LOD0 assembly <= 5000: %d + %d = %d" % [ft, mt, ft + mt])
	var bounds: AABB = ItemModels.bounds(flashlight)
	_check(absf(bounds.size.z - 0.143) < 0.0006, "length 143 mm")
	_check(absf(bounds.size.x - 0.034) < 0.002, "head diameter 34 mm")
	for part: String in ["Clip", "PrimaryButton", "ModeButton", "TailCap", "Bezel", "LightEmitter", "RingMountSocket"]:
		_check(_part(flashlight, part) != null, "independent flashlight node " + part)
	for part: String in ["CapHinge", "MovingJaw", "LockScrew", "ClampPadNegative", "ClampPadPositive", "FlashlightSocket"]:
		_check(_part(clamp, part) != null, "independent mount node " + part)
	var cap: Node3D = _part(clamp, "CapHinge")
	var before: Transform3D = cap.transform
	cap.rotation.z = deg_to_rad(65.0)
	_check(not cap.transform.is_equal_approx(before), "mount cap rotates on its hinge")
	cap.transform = before
	var socket: Node3D = _part(clamp, "FlashlightSocket")
	_check(socket.position.is_equal_approx(Vector3(0, 0.024, 0)), "mount socket +24 mm")
	_check(DozorAsset.collision() is ConvexPolygonShape3D, "simple flashlight convex collision")
	_check(DozorAsset.collision(true) is BoxShape3D, "simple mount collision")
	var collider: CollisionShape3D = DozorAsset.collision_node(true)
	_check(is_equal_approx(collider.position.y, 0.018), "mount collision centered above rail datum")
	collider.free()
	for variant: String in ["f1m", "f1s"]:
		var other: Node3D = DozorAsset.flashlight(variant, true)
		_check(_triangles(other) == ft, variant + " shares geometry budget")
		_check(not _part(other, "Clip").visible, "clip removed for mounted " + variant)
		other.free()
	for atlas: String in ["f1", "p"]:
		var normal: ConfigFile = ConfigFile.new()
		var orm: ConfigFile = ConfigFile.new()
		_check(normal.load(DozorAsset.DIRECTORY + "dozor_" + atlas + "_normal.png.import") == OK, "normal import metadata " + atlas)
		_check(orm.load(DozorAsset.DIRECTORY + "dozor_" + atlas + "_orm.png.import") == OK, "ORM import metadata " + atlas)
		_check(normal.get_value("params", "compress/normal_map") == 1, "normal VRAM compression " + atlas)
		_check(orm.get_value("params", "roughness/mode") == 3 and not String(orm.get_value("params", "roughness/src_normal")).is_empty(), "ORM G roughness filter " + atlas)
		_check(orm.get_value("params", "mipmaps/generate") == true, "ORM mipmaps " + atlas)
	_report = {"flashlight_triangles": ft, "mount_triangles": mt, "complete_assembly_triangles": ft + mt,
		"triangle_limit": 5000, "bounds_m": {"size": [bounds.size.x, bounds.size.y, bounds.size.z]},
		"passed": _passed, "failed": _failed, "renderer": RenderingServer.get_current_rendering_method(),
		"imported_lod_entries": _lod_entries(flashlight) + _lod_entries(clamp)}
	var path: String = "res://_asset_src/dozor/game/godot-checks.json"
	var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	file.store_string(JSON.stringify(_report, "\t"))
	print("DOZOR: ", _passed, " passed, ", _failed, " failed; ", ft + mt, " triangles")
	if DisplayServer.get_name() == "headless" or "check" in OS.get_cmdline_user_args():
		get_tree().quit(0 if _failed == 0 else 1)
		return
	_setup_studio()
	clamp.position = Vector3.ZERO
	flashlight.position = Vector3(0, 0.024, 0)
	_part(flashlight, "Clip").visible = false
	_camera.position = Vector3(0.20, 0.19, 0.25)
	_camera.look_at(Vector3(0, 0.018, 0.009))
	_camera.size = 0.16
	await _capture("game_assembly")
	clamp.visible = false
	flashlight.position = Vector3.ZERO
	_part(flashlight, "Clip").visible = true
	_camera.position = Vector3(0.16, 0.15, 0.24)
	_camera.look_at(Vector3(0, 0, 0.009))
	await _capture("game_flashlight")
	flashlight.visible = false
	clamp.visible = true
	cap.rotation.z = deg_to_rad(65.0)
	_camera.position = Vector3(0.12, 0.11, 0.13)
	_camera.look_at(Vector3(0, 0.018, 0))
	_camera.size = 0.09
	await _capture("game_mount_open")
	clamp.visible = false
	flashlight.visible = true
	_camera.position = Vector3(0, 0.11, -0.12)
	_camera.look_at(Vector3(0, 0, -0.048))
	_camera.size = 0.067
	await _capture("game_tail")
	get_viewport().mesh_lod_threshold = 1.0
	_camera.projection = Camera3D.PROJECTION_PERSPECTIVE
	_camera.fov = 54.0
	_camera.position = Vector3(0.6, 0.45, 0.8)
	_camera.look_at(Vector3(0, 0, 0.009))
	await _capture("game_world")
	get_tree().quit(0 if _failed == 0 else 1)


func _check(ok: bool, text: String) -> void:
	if ok:
		_passed += 1
	else:
		_failed += 1
		push_error("DOZOR: " + text)
	print("PASS " if ok else "FAIL ", text)


func _part(model: Node3D, prefix: String) -> Node3D:
	return model.find_child(prefix + "*", true, false) as Node3D


func _triangles(model: Node3D) -> int:
	var count: int = 0
	for raw: Node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh: Mesh = (raw as MeshInstance3D).mesh
		for surface: int in range(mesh.get_surface_count()):
			var arrays: Array = mesh.surface_get_arrays(surface)
			var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
			count += indices.size() / 3 if not indices.is_empty() else (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() / 3
	return count


func _lod_entries(model: Node3D) -> int:
	var count: int = 0
	for raw: Node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh: Mesh = (raw as MeshInstance3D).mesh
		var surfaces: Variant = mesh.get("_surfaces")
		if surfaces is Array:
			for surface: Dictionary in surfaces:
				var lods: Variant = surface.get("lods", [])
				count += lods.size()
	return count


func _setup_studio() -> void:
	var world: WorldEnvironment = WorldEnvironment.new()
	var env: Environment = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.21, 0.23, 0.25)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.7, 0.75, 0.8)
	env.ambient_light_energy = 0.65
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	var sky: Sky = Sky.new()
	var sky_mat: ProceduralSkyMaterial = ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.45, 0.52, 0.62)
	sky_mat.sky_horizon_color = Color(0.8, 0.82, 0.84)
	sky_mat.ground_horizon_color = Color(0.5, 0.52, 0.54)
	sky_mat.ground_bottom_color = Color(0.12, 0.14, 0.16)
	sky.sky_material = sky_mat
	env.sky = sky
	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	env.ssao_enabled = true
	env.ssao_radius = 0.02
	world.environment = env
	add_child(world)
	for angle: Vector3 in [Vector3(-38, -30, 0), Vector3(-20, 150, 0)]:
		var light: DirectionalLight3D = DirectionalLight3D.new()
		light.rotation_degrees = angle
		light.light_energy = 1.4
		add_child(light)
	_camera = Camera3D.new()
	_camera.current = true
	_camera.near = 0.001
	_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	get_viewport().mesh_lod_threshold = 0.0 # screenshot and triangle audit inspect LOD0
	add_child(_camera)


func _capture(name: String) -> void:
	for frame: int in range(20):
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var prefix: String = "albedo_" if OS.get_environment("DOZOR_DEBUG_ALBEDO") == "on" else "lod_off_" if OS.get_environment("DOZOR_DEBUG_LOD") == "off" else "normal_off_" if OS.get_environment("DOZOR_DEBUG_NORMALS") == "off" else ""
	get_viewport().get_texture().get_image().save_png("res://docs/screens/dozor/" + prefix + name + ".png")
	print("DOZOR screenshot: ", name)
