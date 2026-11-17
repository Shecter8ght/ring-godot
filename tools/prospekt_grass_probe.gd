extends Node3D
## Сравнительный стенд земли и травы «Проспекта» (docs/tasks/prospekt_grass_upgrade.md).
## Свет и камеры одинаковые; полная карта здесь не изменяется. F5…F8 — варианты, F9 — ряд моделей.
## -- shots: docs/screens/prospekt_grass/probe; -- check: ассеты, LOD, покров и приминание.

const PG = preload("res://src/world/prospekt_grass.gd")
const PLAYER_SCENE: String = "res://scenes/player/player.tscn"
const RIG_SCENE: String = "res://scenes/player/camera_rig.tscn"
const OUT_DEFAULT: String = "res://docs/screens/prospekt_grass/probe"
const PLOT_SIZE: float = 12.0
const PLOT_STEP: float = 16.0
const GROUND_Y: float = 0.08
const VARIANTS: Array = [
	{"id": "current", "title": "0 · Текущий газон", "ground": "current", "mixed": false},
	{"id": "leafy", "title": "A · Leafy Grass + Bermuda / Medium / Weed", "ground": "leafy", "mixed": false},
	{"id": "grass001", "title": "B · Grass 001 + тот же покров", "ground": "grass001", "mixed": false},
	{"id": "mixed", "title": "C · Leafy Grass + Grass Ground, проплешины", "ground": "leafy", "mixed": true},
]
const MODEL_LINEUP: PackedStringArray = ["grass_bermuda_01_a", "grass_medium_01_a", "grass_medium_01_tall", "weed_plant_02_a"]

var _roots: Array[Node3D] = []
var _scatters: Array = []
var _active: int = -1
var _player: Player
var _rig: CameraRig
var _camera: Camera3D
var _atmo: RaidAtmosphere
var _weather: RaidWeather
var _hud: Label
var _lineup: Node3D
var _report: Dictionary = {}
var _relief_on: bool = true


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.current = {"time": "day", "weather": "clear", "power": "on"}
	var quality: String = OS.get_environment("GRASS_PROBE_QUALITY")
	if quality in Settings.QUALITY:
		Settings.quality = quality
		Settings.apply_graphics()
		Settings.changed.emit()
	var environment_node := WorldEnvironment.new()
	environment_node.name = "WorldEnvironment"
	environment_node.environment = Environment.new()
	add_child(environment_node)
	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.shadow_enabled = true
	add_child(sun)
	var ground := ProbeGround.new()
	ground.name = "ProbeGround"
	add_child(ground)
	_build_floor()
	_build_variants()
	_build_lineup()
	_atmo = RaidAtmosphere.new()
	_atmo.name = "Atmosphere"
	add_child(_atmo)
	_atmo.apply()
	_weather = RaidWeather.new()
	_weather.name = "Weather"
	add_child(_weather)
	_spawn_player()
	_build_hud()
	if DayCycle.current:
		DayCycle.current.set_hour(13.0)
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if "check" in args or "shots" in args:
		_camera = Camera3D.new()
		_camera.name = "ShotCamera"
		_camera.fov = Settings.fps_fov_v()
		_camera.far = 400.0
		add_child(_camera)
		_camera.make_current()
		_player.set_physics_process(false)
		_player.set_process(false)
		_player.set_process_input(false)
		_player.hide()
		_rig.set_process(false)
		_rig.set_physics_process(false)
		_rig.set_process_input(false)
		_rig.set_process_unhandled_input(false)
		for item: Node in _rig.find_children("*", "CanvasItem", true, false):
			(item as CanvasItem).hide()
		for item: Node in _player.find_children("*", "CanvasItem", true, false):
			(item as CanvasItem).hide()
		_camera.make_current()
	if "check" in args:
		await _check()
		return
	if "shots" in args:
		await _shots()
		return
	_activate(0)
	_goto(0)


func _build_floor() -> void:
	var outside := MeshInstance3D.new()
	outside.name = "Outside"
	outside.mesh = StreetPaving.surface_mesh(Rect2(-40, -30, 160, 100), -0.02, Color(0, 0, 0, 0))
	outside.material_override = StreetPaving.material("lawn", false)
	add_child(outside)
	_collider(self, Vector3(30, -0.27, 15), Vector3(150, 0.5, 100))


func _build_variants() -> void:
	for i: int in range(VARIANTS.size()):
		var spec: Dictionary = VARIANTS[i]
		var x: float = float(i) * PLOT_STEP
		var root := Node3D.new()
		root.name = "Variant_" + String(spec.id)
		add_child(root)
		_roots.append(root)
		var surface := MeshInstance3D.new()
		surface.name = "Ground"
		surface.mesh = StreetPaving.surface_mesh(Rect2(x - PLOT_SIZE * 0.5, -PLOT_SIZE * 0.5, PLOT_SIZE, PLOT_SIZE), GROUND_Y, Color(0, 0, 0, 0))
		surface.material_override = PG.ground_material(String(spec.ground), bool(spec.mixed))
		root.add_child(surface)
		_collider(root, Vector3(x, GROUND_Y - 0.25, 0), Vector3(PLOT_SIZE, 0.5, PLOT_SIZE))
		_label(root, Vector3(x, 1.25, 4.8), String(spec.title), 48)
		var scatters: Array[Node] = []
		if String(spec.id) == "current":
			var grass: DistrictGrass = PG.make_scatter("CurrentGrass", _density(x, 1.0, 0.0), _origin(x), "current")
			root.add_child(grass)
			scatters.append(grass)
		else:
			var base: DistrictGrass = PG.make_scatter("BaseGrass", _density(x, 1.0, 0.0), _origin(x), "base")
			root.add_child(base)
			scatters.append(base)
			var accents: DistrictGrass = PG.make_scatter("AccentGrass", _density(x, 0.75, 1.0), _origin(x), "accents")
			root.add_child(accents)
			scatters.append(accents)
		_scatters.append(scatters)


func _density(x: float, red: float, green: float) -> ImageTexture:
	var image := Image.create(int(PLOT_SIZE), int(PLOT_SIZE), false, Image.FORMAT_RGBA8)
	image.fill(Color(red, green, 0, 1))
	return ImageTexture.create_from_image(image)


func _origin(x: float) -> Vector2:
	return Vector2(x - PLOT_SIZE * 0.5, -PLOT_SIZE * 0.5)


func _build_lineup() -> void:
	_lineup = Node3D.new()
	_lineup.name = "ModelLineup"
	add_child(_lineup)
	_label(_lineup, Vector3(2.5, 1.15, 31.0), "Модели · одинаковая нормировка высоты 0,35 м", 48)
	var x: float = 0.0
	for asset: String in MODEL_LINEUP:
		var path: String = PG.model_path(asset, 0)
		if not ResourceLoader.exists(path):
			continue
		var inst: Node3D = (load(path) as PackedScene).instantiate() as Node3D
		_lineup.add_child(inst)
		var mesh_instance: MeshInstance3D = _first_mesh(inst)
		if mesh_instance == null:
			continue
		var height: float = maxf(mesh_instance.mesh.get_aabb().size.y, 0.01)
		inst.scale = Vector3.ONE * (0.35 / height)
		inst.position = Vector3(x, GROUND_Y, 30.0)
		_label(_lineup, Vector3(x, 0.48, 30.15), asset.replace("grass_", "").replace("weed_plant_02", "Weed 02"), 30)
		x += 1.5
	_label(_lineup, Vector3(6.4, 0.5, 30.0), "Fab Grass Clumps / Wild Grass\nожидают штатной загрузки", 30)


func _first_mesh(root: Node) -> MeshInstance3D:
	if root is MeshInstance3D:
		return root as MeshInstance3D
	var found: Array[Node] = root.find_children("*", "MeshInstance3D", true, false)
	return found[0] as MeshInstance3D if not found.is_empty() else null


func _label(parent: Node3D, at: Vector3, text: String, font_size: int) -> void:
	var label := Label3D.new()
	label.text = text
	label.font_size = font_size
	label.pixel_size = 0.006
	label.outline_size = 8
	label.modulate = Color(0.95, 0.96, 0.9)
	label.outline_modulate = Color(0.03, 0.035, 0.025)
	label.no_depth_test = false
	label.rotation.y = PI
	label.position = at
	parent.add_child(label)


func _collider(parent: Node3D, at: Vector3, size: Vector3) -> void:
	var body := StaticBody3D.new()
	body.collision_layer = Hitscan.LAYER_WORLD
	body.collision_mask = 0
	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	collision.shape = shape
	body.add_child(collision)
	body.position = at
	parent.add_child(body)


func _spawn_player() -> void:
	_player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	_player.name = "Player_1"
	_player.position = Vector3(0, GROUND_Y + 0.1, -4)
	add_child(_player)
	_rig = (load(RIG_SCENE) as PackedScene).instantiate() as CameraRig
	_rig.name = "CameraRig"
	_rig.target_path = NodePath("../Player_1")
	add_child(_rig)
	CameraRig.first_person_mode = true


func _build_hud() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 5
	add_child(layer)
	_hud = Label.new()
	_hud.position = Vector2(16, 12)
	_hud.add_theme_font_size_override("font_size", 16)
	_hud.add_theme_color_override("font_color", Color(1, 1, 1))
	_hud.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_hud.add_theme_constant_override("outline_size", 5)
	layer.add_child(_hud)
	_update_hud()


func _update_hud() -> void:
	if _hud:
		_hud.text = "Трава «Проспекта» · день 13:00, ясно · %s\nF5…F8 — варианты · F9 — модели · F4 — рельеф: %s · WASD и мышь — прогулка" % [VARIANTS[maxi(_active, 0)].title, "вкл" if _relief_on else "выкл"]


func _set_relief(enabled: bool) -> void:
	_relief_on = enabled
	for spec: Dictionary in VARIANTS:
		if String(spec.ground) == "current":
			continue
		var material: ShaderMaterial = PG.ground_material(String(spec.ground), bool(spec.mixed)) as ShaderMaterial
		material.set_shader_parameter("parallax_scale", (0.035 if String(spec.ground) == "leafy" else 0.022) if enabled else 0.0)
	_update_hud()


func _activate(index: int) -> void:
	_active = index
	for i: int in range(_roots.size()):
		_roots[i].visible = i == index
		for grass: Node in _scatters[i]:
			grass.set_process(i == index)
	_lineup.visible = index == -1
	if index >= 0:
		_update_hud()


func _goto(index: int) -> void:
	_activate(index)
	var x: float = float(index) * PLOT_SIZE + float(index) * (PLOT_STEP - PLOT_SIZE)
	_player.position = Vector3(x, GROUND_Y + 0.1, -4.5)
	_player.velocity = Vector3.ZERO
	_player.face(0.0)
	_rig.set("_look_yaw", 0.0)
	_rig.set("_look_pitch", -0.18)


func _unhandled_input(event: InputEvent) -> void:
	var key := event as InputEventKey
	if key == null or not key.pressed or key.echo:
		return
	if key.keycode >= KEY_F5 and key.keycode <= KEY_F8:
		_goto(int(key.keycode - KEY_F5))
	elif key.keycode == KEY_F9:
		_activate(-1)
		_player.position = Vector3(2.2, GROUND_Y + 0.1, 26.8)
		_player.face(0.0)
		_rig.set("_look_yaw", 0.0)
		_rig.set("_look_pitch", -0.12)
	elif key.keycode == KEY_F4:
		_set_relief(not _relief_on)
	else:
		return
	get_viewport().set_input_as_handled()


func _shots() -> void:
	_hud.hide()
	var out: String = OS.get_environment("GRASS_PROBE_OUT")
	if out == "":
		out = ProjectSettings.globalize_path(OUT_DEFAULT)
	DirAccess.make_dir_recursive_absolute(out)
	var only: PackedStringArray = OS.get_environment("GRASS_PROBE_ONLY").split(",", false)
	var vp: RID = get_viewport().get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(vp, true)
	for i: int in range(VARIANTS.size()):
		var id: String = String(VARIANTS[i].id)
		if not only.is_empty() and not id in only:
			continue
		_activate(i)
		var x: float = float(i) * PLOT_STEP
		var views: Array = [
			["eye", Vector3(x, GROUND_Y + 1.62, -7.0), Vector3(x, 0.28, 2.0)],
			["close", Vector3(x - 1.2, GROUND_Y + 0.5, -1.8), Vector3(x, GROUND_Y + 0.03, 0.4)],
			["far", Vector3(x, GROUND_Y + 1.62, -17.0), Vector3(x, 0.22, 2.0)],
		]
		for view: Array in views:
			_camera.global_position = view[1]
			_camera.look_at(view[2], Vector3.UP)
			_camera.make_current()
			await _frames(180 if String(view[0]) == "eye" else 30)
			await RenderingServer.frame_post_draw
			var path: String = out.path_join("%s_%s.png" % [id, String(view[0])])
			get_viewport().get_texture().get_image().save_png(path)
			print("grass_probe: ", path)
			if String(view[0]) == "eye":
				_report[id] = await _measure(vp)
	if only.is_empty() or "mixed" in only or "relief" in only:
		_activate(3)
		var x: float = 3.0 * PLOT_STEP
		_camera.global_position = Vector3(x - 0.6, GROUND_Y + 0.35, -0.8)
		_camera.look_at(Vector3(x, GROUND_Y, 0.4), Vector3.UP)
		_camera.make_current()
		for grass: DistrictGrass in _scatters[3]:
			grass.hide()
		await _frames(30)
		for enabled: bool in [false, true]:
			_set_relief(enabled)
			await _frames(12)
			await RenderingServer.frame_post_draw
			var name: String = "relief_pom" if enabled else "relief_flat"
			get_viewport().get_texture().get_image().save_png(out.path_join(name + ".png"))
		_set_relief(true)
		for grass: DistrictGrass in _scatters[3]:
			grass.show()
	_activate(-1)
	_camera.global_position = Vector3(2.2, 1.05, 25.7)
	_camera.look_at(Vector3(2.2, 0.22, 30.0), Vector3.UP)
	_camera.make_current()
	await _frames(30)
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(out.path_join("models.png"))
	var file: FileAccess = FileAccess.open(out.path_join("performance.json"), FileAccess.WRITE)
	file.store_string(JSON.stringify(_report, "\t"))
	file.close()
	print("grass_probe: снимки и замеры — ", out)
	get_tree().quit(0)


func _measure(vp: RID) -> Dictionary:
	await _frames(60)
	var frames0: int = Engine.get_frames_drawn()
	var time0: int = Time.get_ticks_usec()
	var gpu: float = 0.0
	for _i: int in range(90):
		await get_tree().process_frame
		gpu += RenderingServer.viewport_get_measured_render_time_gpu(vp)
	var seconds: float = float(Time.get_ticks_usec() - time0) / 1e6
	return {"fps": float(Engine.get_frames_drawn() - frames0) / seconds, "gpu_ms": gpu / 90.0,
		"triangles": int(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME))}


func _check() -> void:
	var fails: int = 0
	if not PG.map_files_ready():
		print("ПРОВАЛ: не все игровые файлы импортированы")
		fails += 1
	for assets: PackedStringArray in [PG.BASE_ASSETS, PG.CLUMP_ASSETS, PG.WEED_ASSETS]:
		for asset: String in assets:
			var previous: int = 0
			for lod: int in range(2):
				var mesh: Mesh = _mesh_at(PG.model_path(asset, lod))
				if mesh == null:
					print("ПРОВАЛ: нет сетки ", asset, " LOD", lod)
					fails += 1
					continue
				var arrays: Array = mesh.surface_get_arrays(0)
				var tris: int = (arrays[Mesh.ARRAY_INDEX] as PackedInt32Array).size() / 3
				if tris <= 0 or tris > 3200 or (lod == 1 and tris >= previous):
					print("ПРОВАЛ: бюджет/переход ", asset, " LOD", lod, " = ", tris)
					fails += 1
				previous = tris
	_activate(1)
	_camera.global_position = Vector3(PLOT_STEP, 1.7, -4)
	await _frames(300)
	for grass: DistrictGrass in _scatters[1]:
		var stats: Dictionary = grass.stats()
		if int(stats.scan_instances) <= 0:
			print("ПРОВАЛ: пустой покров ", grass.name)
			fails += 1
		print("ПОКРОВ ", grass.name, ": ", JSON.stringify(stats))
	GrassTrample.hit(Vector3(PLOT_STEP, GROUND_Y, 0), 0.4)
	await get_tree().create_timer(0.15).timeout
	if GrassTrample.current == null or GrassTrample.current.pressed_at(Vector3(PLOT_STEP, GROUND_Y, 0)) < 0.5:
		print("ПРОВАЛ: приминание не записано")
		fails += 1
	print("grass_probe: проверок завершено, провалов ", fails)
	get_tree().quit(fails)


func _mesh_at(path: String) -> Mesh:
	if not ResourceLoader.exists(path):
		return null
	var inst: Node = (load(path) as PackedScene).instantiate()
	var found: Array[Node] = inst.find_children("*", "MeshInstance3D", true, false)
	var mesh: Mesh = (found[0] as MeshInstance3D).mesh if not found.is_empty() else null
	inst.free()
	return mesh


func _frames(count: int) -> void:
	for _i: int in range(count):
		await get_tree().process_frame


class ProbeGround:
	extends Node3D

	func _enter_tree() -> void:
		add_to_group("district_terrain")

	func height_at(_x: float, _z: float) -> float:
		return GROUND_Y
