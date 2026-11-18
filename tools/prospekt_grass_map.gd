extends Node3D
## Снимки и замер одного газона «Проспекта» на настоящей карте.
## -- before | after: docs/screens/prospekt_grass/map_<режим>; PROSPEKT_GRASS_TEST=0 отключает пробу.

const LEVEL: String = "res://scenes/levels/prospekt_study.tscn"
const VIEWS: Array = [
	["lawn", Vector3(-10, 3.0, 200), Vector3(-10, 0.1, 200.1)],
	["eye", Vector3(-10, 1.74, 194), Vector3(-10, 0.22, 202)],
	["close", Vector3(-11, 0.62, 197), Vector3(-10, 0.14, 199)],
	["far", Vector3(-10, 1.74, 184), Vector3(-10, 0.22, 198)],
]

var _camera: Camera3D


func _ready() -> void:
	Engine.max_fps = 0
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Settings.quality = "high"
	Settings.apply_graphics()
	Settings.changed.emit()
	var world: Node3D = (load(LEVEL) as PackedScene).instantiate() as Node3D
	add_child(world)
	_camera = Camera3D.new()
	_camera.fov = Settings.fps_fov_v()
	_camera.far = 2000.0
	add_child(_camera)
	_camera.make_current()
	if OS.get_cmdline_user_args().has("check"):
		await _check(world)
		return
	var mode: String = "after" if OS.get_cmdline_user_args().has("after") else "before"
	var out: String = OS.get_environment("GRASS_MAP_OUT")
	if out == "":
		out = ProjectSettings.globalize_path("res://docs/screens/prospekt_grass/map_" + mode)
	DirAccess.make_dir_recursive_absolute(out)
	var vp: RID = get_viewport().get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(vp, true)
	var report: Dictionary = {}
	for view: Array in VIEWS:
		_camera.global_position = view[1]
		_camera.look_at(view[2], Vector3.UP)
		await _frames(360)
		await RenderingServer.frame_post_draw
		var path: String = out.path_join(String(view[0]) + ".png")
		get_viewport().get_texture().get_image().save_png(path)
		report[String(view[0])] = await _measure(vp)
		print("grass_map ", mode, " ", String(view[0]), ": ", JSON.stringify(report[String(view[0])]))
	var file: FileAccess = FileAccess.open(out.path_join("performance.json"), FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "\t"))
	file.close()
	get_tree().quit(0)


func _measure(vp: RID) -> Dictionary:
	await _frames(90)
	var frames0: int = Engine.get_frames_drawn()
	var time0: int = Time.get_ticks_usec()
	var gpu: float = 0.0
	for _i: int in range(180):
		await get_tree().process_frame
		gpu += RenderingServer.viewport_get_measured_render_time_gpu(vp)
	var seconds: float = float(Time.get_ticks_usec() - time0) / 1e6
	return {"fps": float(Engine.get_frames_drawn() - frames0) / seconds, "gpu_ms": gpu / 180.0,
		"triangles": int(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME))}


func _check(world: Node3D) -> void:
	var want_on: bool = OS.get_environment("PROSPEKT_GRASS_TEST") != "0"
	var fails: int = 0
	var found: Array[Node] = world.find_children("GrassUpgrade_Grove", "Node3D", true, false)
	var original: DistrictGrass = world.find_child("LawnGrass", true, false) as DistrictGrass
	if original == null:
		print("ПРОВАЛ: прежний покров не найден")
		fails += 1
	else:
		var inside: Color = _density_at(original, Vector2(-10, 199))
		var outside: Color = _density_at(original, Vector2(-100, -15.6))
		if want_on and inside.r > 0.001:
			print("ПРОВАЛ: прежний покров остался внутри пробы")
			fails += 1
		if not want_on and inside.r < 0.99:
			print("ПРОВАЛ: отключение пробы не вернуло прежний покров")
			fails += 1
		if outside.r < 0.99:
			print("ПРОВАЛ: изменился другой газон")
			fails += 1
	if not want_on:
		if not found.is_empty():
			print("ПРОВАЛ: узел пробы существует при отключении")
			fails += 1
		print("grass_map check: отключение, провалов ", fails)
		get_tree().quit(fails)
		return
	if found.size() != 1:
		print("ПРОВАЛ: пробных участков ", found.size(), ", ожидался один")
		fails += 1
		get_tree().quit(fails)
		return
	var root := found[0] as Node3D
	if String(root.get_meta("site", "")) != "grove_lawn_n" or String(root.get_meta("candidate", "")) != "D":
		print("ПРОВАЛ: неверный участок или кандидат")
		fails += 1
	var ground: MeshInstance3D = root.find_child("Ground", true, false) as MeshInstance3D
	var material: ShaderMaterial = ground.material_override as ShaderMaterial if ground else null
	if material == null or not bool(material.get_shader_parameter("use_soil")):
		print("ПРОВАЛ: земля пробы не использует проплешины")
		fails += 1
	elif absf(float(material.get_shader_parameter("parallax_scale"))) > 0.0001 or not is_equal_approx(float(material.get_shader_parameter("normal_strength")), 2.0):
		print("ПРОВАЛ: у D должны быть нормаль ×2 и нулевой параллакс")
		fails += 1
	_camera.global_position = Vector3(-10, 1.74, 194)
	_camera.look_at(Vector3(-10, 0.22, 202), Vector3.UP)
	await _frames(360)
	for name: String in ["UpgradeBase", "UpgradeAccents"]:
		var grass: DistrictGrass = root.find_child(name, true, false) as DistrictGrass
		if grass == null or int(grass.stats().scan_instances) <= 0:
			print("ПРОВАЛ: пустой слой ", name)
			fails += 1
		else:
			print("СЛОЙ ", name, ": ", JSON.stringify(grass.stats()))
	var broad_base: DistrictGrass = root.find_child("UpgradeBase", true, false) as DistrictGrass
	if broad_base != null and (not broad_base.dynamic_alpha or broad_base.override_scan_radius < 70.0):
		print("ПРОВАЛ: на газоне не включены возможности D")
		fails += 1
	print("grass_map check: один участок D, провалов ", fails)
	get_tree().quit(fails)


func _density_at(grass: DistrictGrass, point: Vector2) -> Color:
	var image: Image = grass.get("_density") as Image
	var origin: Vector2 = grass.origin
	if image == null:
		return Color(0, 0, 0)
	return image.get_pixel(int(point.x - origin.x), int(point.y - origin.y))


func _frames(count: int) -> void:
	for _i: int in range(count):
		await get_tree().process_frame
