extends Node3D
## Снимки и замер газонов «Проспекта» на настоящей карте.
## -- before | after: docs/screens/prospekt_grass/map_<режим>; PROSPEKT_GRASS_TEST=0 возвращает прежний покров.
## GRASS_MAP_VIEW=имя:x:y:z:куда_x:куда_y:куда_z;… — свои камеры.

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
	var views: Array = VIEWS.duplicate()
	if OS.get_environment("GRASS_MAP_VIEW") != "":
		views.clear()
		for spec: String in OS.get_environment("GRASS_MAP_VIEW").split(";", false):
			var p: PackedStringArray = spec.split(":")
			if p.size() == 7:
				views.append([p[0], Vector3(p[1].to_float(), p[2].to_float(), p[3].to_float()),
					Vector3(p[4].to_float(), p[5].to_float(), p[6].to_float())])
	for view: Array in views:
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
	var found: Array[Node] = world.find_children("GrassUpgrade_All", "Node3D", true, false)
	var original: DistrictGrass = world.find_child("LawnGrass", true, false) as DistrictGrass
	var landscape: Node3D = world.find_child("Landscape", true, false) as Node3D
	var lawns: Array = landscape.get("_lawns") as Array if landscape else []
	if original == null or lawns.is_empty():
		print("ПРОВАЛ: прежний покров или список газонов не найден")
		fails += 1
	for lawn: Array in lawns:
		var c: Vector2 = lawn[0]
		if original != null:
			var density: Color = _density_at(original, c)
			if want_on and density.r > 0.001:
				print("ПРОВАЛ: прежний покров остался в ", c)
				fails += 1
			if not want_on and density.r < 0.99:
				print("ПРОВАЛ: при отключении прежний покров не на месте в ", c)
				fails += 1
	if not want_on:
		if not found.is_empty():
			print("ПРОВАЛ: новый покров существует при отключении")
			fails += 1
		print("grass_map check: прежние газоны, участков ", lawns.size(), ", провалов ", fails)
		get_tree().quit(fails)
		return
	if found.size() != 1:
		print("ПРОВАЛ: узлов полного покрова ", found.size(), ", ожидался один")
		fails += 1
		get_tree().quit(fails)
		return
	var root := found[0] as Node3D
	if String(root.get_meta("candidate", "")) != "D" or String(root.get_meta("scope", "")) != "all_lawns":
		print("ПРОВАЛ: неверный кандидат или охват")
		fails += 1
	var grounds: Array[Node] = root.find_children("Ground_*", "MeshInstance3D", true, false)
	if grounds.size() != lawns.size() or int(root.get_meta("lawn_count", 0)) != lawns.size():
		print("ПРОВАЛ: земля покрывает ", grounds.size(), " из ", lawns.size())
		fails += 1
	var base: DistrictGrass = root.find_child("UpgradeBase", true, false) as DistrictGrass
	var accents: DistrictGrass = root.find_child("UpgradeAccents", true, false) as DistrictGrass
	for lawn: Array in lawns:
		var c: Vector2 = lawn[0]
		var top: float = float(lawn[3])
		var expected := Vector3(c.x, top + 0.004, c.y)
		var matched: bool = false
		for ground_node: Node in grounds:
			var ground := ground_node as MeshInstance3D
			if ground.position.distance_to(expected) < 0.001 and absf(wrapf(ground.rotation.y - float(lawn[2]), -PI, PI)) < 0.001:
				matched = true
				break
		if not matched:
			print("ПРОВАЛ: нет земли с нужной высотой/поворотом в ", c)
			fails += 1
		if base != null and _density_at(base, c).r < 0.99:
			print("ПРОВАЛ: нет основы D в ", c)
			fails += 1
		if accents != null and _density_at(accents, c).r < 0.5:
			print("ПРОВАЛ: нет акцентов D в ", c)
			fails += 1
	if not grounds.is_empty():
		var material: ShaderMaterial = (grounds[0] as MeshInstance3D).material_override as ShaderMaterial
		if material == null or not bool(material.get_shader_parameter("use_soil")):
			print("ПРОВАЛ: земля D не использует проплешины")
			fails += 1
		elif absf(float(material.get_shader_parameter("parallax_scale"))) > 0.0001 or not is_equal_approx(float(material.get_shader_parameter("normal_strength")), 2.0) or not is_equal_approx(float(material.get_shader_parameter("albedo_contrast")), 0.5):
			print("ПРОВАЛ: у D должны быть нормаль ×2, контраст альбедо 0,5 и нулевой параллакс")
			fails += 1
	_camera.global_position = Vector3(-10, 1.74, 194)
	_camera.look_at(Vector3(-10, 0.22, 202), Vector3.UP)
	await _frames(360)
	for grass: DistrictGrass in [base, accents]:
		if grass == null or int(grass.stats().scan_instances) <= 0:
			print("ПРОВАЛ: пустой слой")
			fails += 1
		else:
			print("СЛОЙ ", grass.name, ": ", JSON.stringify(grass.stats()))
	if base != null and (not base.dynamic_alpha or base.override_scan_radius < 50.0):
		print("ПРОВАЛ: на газонах не включены возможности D")
		fails += 1
	print("grass_map check: все газоны D, участков ", lawns.size(), ", провалов ", fails)
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
