extends Node3D
## Машина Ильи в движке: scenes/props/coupe_ilya.tscn (модель — tools/coupe_ilya/game_*.py).
##   tools/godot.cmd --headless res://tools/coupe_ilya_shots.tscn -- check
##       узлы состояний и их LOD, габариты, коллизия, треугольники по LOD, переключение состояний;
##   tools/godot.cmd --windowed --resolution 1280x800 res://tools/coupe_ilya_shots.tscn [-- only=front34,bay]
##       снимки docs/screens/coupe_ilya_*.png — те же ракурсы, что у рендеров отделки в Blender (камера и точка
##       взгляда — в осях Blender, фокус — мм при кадре 36 мм), плюс LOD с трёх расстояний одним кадром.

const SCENE: String = "res://scenes/props/coupe_ilya.tscn"
const OUTPUT_DIR: String = "res://docs/screens"
const SKY: String = "res://assets/sky/kloppenheim_03_puresky.hdr"
const SIZE: Vector2i = Vector2i(1280, 800)
## Габарит (ширина без зеркал, высота, длина), м — asset-state.md; допуск — 3 см.
const DIMENSIONS: Vector3 = Vector3(1.935, 1.431, 4.857)
const NODES: Array[String] = ["Body", "Hood", "Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR", "WheelOff_FL",
	"Battery_Installed", "Battery_Missing"]
## ракурс: глаз, точка взгляда (оси Blender: перёд −Y, левый борт +X), фокус мм; состояние машины
const VIEWS: Dictionary = {
	"front34": {"eye": [4.4, -5.2, 1.55], "at": [0.1, -0.5, 0.62], "mm": 40.0, "state": "found"},
	"front34_fixed": {"eye": [4.4, -5.2, 1.55], "at": [0.1, -0.5, 0.62], "mm": 40.0, "state": "ready"},
	"rear34": {"eye": [-4.6, 5.4, 1.6], "at": [0.0, 0.5, 0.6], "mm": 40.0, "state": "ready"},
	"bay": {"eye": [0.9, -3.0, 1.75], "at": [0.0, -1.5, 0.65], "mm": 30.0, "state": "found"},
	"bay_battery": {"eye": [0.9, -3.0, 1.75], "at": [0.0, -1.5, 0.65], "mm": 30.0, "state": "battery"},
	"wheel_well": {"eye": [1.9, -1.9, 0.45], "at": [0.9, -1.4355, 0.34], "mm": 40.0, "state": "found"},
	"wheel": {"eye": [1.9, -1.9, 0.45], "at": [0.9, -1.4355, 0.34], "mm": 50.0, "state": "ready"},
	"hood_dust": {"eye": [0.7, -3.0, 1.15], "at": [0.0, -2.05, 0.86], "mm": 50.0, "state": "ready"},
	"handle": {"eye": [1.55, 0.15, 1.0], "at": [0.88, 0.39, 0.88], "mm": 50.0, "state": "ready"},
	"interior": {"eye": [1.75, 0.55, 1.2], "at": [0.0, -0.5, 0.8], "mm": 22.0, "state": "battery"},
}

var _camera: Camera3D
var _label: Label
var _car: IlyaCar
var _only: PackedStringArray = []
var _failures: int = 0
var _written: Array[String] = []


func _ready() -> void:
	var check: bool = "check" in OS.get_cmdline_user_args()
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("only="):
			_only = argument.trim_prefix("only=").split(",", false)
	if not ResourceLoader.exists(SCENE, "PackedScene"):
		push_error("coupe_ilya_shots: нет сцены " + SCENE)
		get_tree().quit(1)
		return
	_car = (load(SCENE) as PackedScene).instantiate() as IlyaCar
	add_child(_car)
	_run_checks()
	if check:
		print("coupe_ilya_shots: проверка, ошибок %d" % _failures)
		get_tree().quit(1 if _failures > 0 else 0)
		return
	if DisplayServer.get_name() == "headless":
		push_error("coupe_ilya_shots: снимки требуют окна (или -- check без окна)")
		get_tree().quit(1)
		return
	Engine.max_fps = 60
	get_window().content_scale_size = SIZE
	get_window().size = SIZE
	RenderingServer.global_shader_parameter_set("rain_wet", 0.0)
	_build_stage()
	for view: String in VIEWS:
		if _wanted(view):
			_save(view, await _shot(view))
	if _wanted("lod"):
		var cells: Array[Image] = []
		for distance: float in [10.0, 25.0, 60.0]:
			cells.append(await _shot_far(distance))
		_save_grid("lod", cells, 3)
	print("coupe_ilya_shots: снимков %d, ошибок %d" % [_written.size(), _failures])
	get_tree().quit(1 if _failures > 0 else 0)


func _fail(text: String) -> void:
	_failures += 1
	push_error("coupe_ilya_shots: " + text)


func _run_checks() -> void:
	for node_name: String in NODES:
		var node: Node3D = _car.find_child(node_name, true, false) as Node3D
		if node == null:
			_fail("нет узла " + node_name)
			continue
		for lod: int in range(3):
			if node.find_child("%s_LOD%d" % [node_name, lod], false, false) == null:
				_fail("у %s нет сетки LOD%d" % [node_name, lod])
	# габарит по ближней модели кузова с колёсами: высота — от земли (начало модели), колёса стоят на земле
	var box: AABB = AABB()
	var measured: int = 0
	for part: String in ["Body", "Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR"]:
		var mesh_instance: MeshInstance3D = _car.find_child(part + "_LOD0", true, false) as MeshInstance3D
		if mesh_instance == null:
			continue
		var part_box: AABB = mesh_instance.global_transform * mesh_instance.mesh.get_aabb()
		box = part_box if measured == 0 else box.merge(part_box)
		measured += 1
	if measured == 5:
		var size: Vector3 = box.size
		print("coupe_ilya_shots: габарит %.3f × %.3f × %.3f м, низ колёс %.3f м" % [size.x, box.end.y, size.z, box.position.y])
		if absf(box.end.y - DIMENSIONS.y) > 0.03 or absf(size.z - DIMENSIONS.z) > 0.03 or size.x < DIMENSIONS.x - 0.03 \
				or absf(box.position.y) > 0.03:
			_fail("габарит не сходится с моделью: ждали %s, колёса на земле" % str(DIMENSIONS))
	# коллизия от импорта машин (tools/editor/vehicle_import.gd)
	var shapes: Array[Node] = _car.find_children("*", "CollisionShape3D", true, false)
	if shapes.is_empty():
		_fail("нет коллизии (импорт машин)")
	var lod_tris: Array[int] = [0, 0, 0]
	for node: Node in _car.find_children("*_LOD?", "MeshInstance3D", true, false):
		var mesh_instance: MeshInstance3D = node as MeshInstance3D
		var lod: int = int(String(mesh_instance.name).right(1))
		for surface: int in range(mesh_instance.mesh.get_surface_count()):
			var arrays: Array = mesh_instance.mesh.surface_get_arrays(surface)
			var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX] as PackedInt32Array
			lod_tris[lod] += indices.size() / 3
	print("coupe_ilya_shots: треугольники LOD0/1/2 (все узлы, оба состояния) — %d / %d / %d" % lod_tris)
	if lod_tris[0] < 120000 or lod_tris[0] > 175000 or lod_tris[1] > 60000 or lod_tris[2] > 16000:
		_fail("треугольники вне бюджета владельца (150 / 50 / 12 тыс.)")
	_set_state("ready")
	var wheel: Node3D = _car.find_child("Wheel_FL", true, false) as Node3D
	var bricks: Node3D = _car.find_child("WheelOff_FL", true, false) as Node3D
	var hood: Node3D = _car.find_child("Hood", true, false) as Node3D
	if wheel == null or bricks == null or hood == null or not wheel.visible or bricks.visible or absf(hood.rotation.x) > 0.001:
		_fail("состояние «готова» не включилось")
	_set_state("found")
	if wheel == null or hood == null or wheel.visible or not bricks.visible or absf(hood.rotation.x) < 0.5:
		_fail("состояние «найдена» не включилось")


func _set_state(state: String) -> void:
	_car.wheel_fitted = state == "ready"
	_car.battery_installed = state in ["ready", "battery"]
	_car.hood_open = state != "ready"


func _build_stage() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUTPUT_DIR))
	var sky_material: PanoramaSkyMaterial = PanoramaSkyMaterial.new()
	sky_material.panorama = load(SKY) as Texture2D
	var sky: Sky = Sky.new()
	sky.sky_material = sky_material
	var environment: Environment = Environment.new()
	environment.background_mode = Environment.BG_SKY
	environment.sky = sky
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	environment.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	environment.tonemap_mode = Environment.TONE_MAPPER_AGX
	environment.ssao_enabled = true
	environment.ssr_enabled = true
	var world: WorldEnvironment = WorldEnvironment.new()
	world.environment = environment
	add_child(world)
	var sun: DirectionalLight3D = DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-42, 140, 0)
	sun.light_energy = 2.2
	sun.light_color = Color(1.0, 0.95, 0.88)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 80.0
	add_child(sun)
	# тёмная брусчатка, как во дворе проверочных рендеров
	var floor_mesh: MeshInstance3D = MeshInstance3D.new()
	var plane: PlaneMesh = PlaneMesh.new()
	plane.size = Vector2(200, 200)
	floor_mesh.mesh = plane
	var floor_material: StandardMaterial3D = StandardMaterial3D.new()
	floor_material.albedo_color = Color(0.19, 0.19, 0.185)
	floor_material.roughness = 0.85
	floor_mesh.material_override = floor_material
	add_child(floor_mesh)
	_camera = Camera3D.new()
	_camera.near = 0.02
	_camera.far = 400.0
	_camera.keep_aspect = Camera3D.KEEP_WIDTH
	add_child(_camera)
	_camera.current = true
	var layer: CanvasLayer = CanvasLayer.new()
	add_child(layer)
	_label = Label.new()
	_label.position = Vector2(20, 14)
	_label.add_theme_font_size_override("font_size", 26)
	_label.add_theme_color_override("font_color", Color(1, 1, 1))
	_label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_label.add_theme_constant_override("outline_size", 7)
	layer.add_child(_label)


## Точка в осях Blender → оси модели в Godot (экспорт glTF, Y вверх): x ← x, y ← z, z ← −y.
func _g(b: Array) -> Vector3:
	return Vector3(float(b[0]), float(b[2]), -float(b[1]))


func _fov(mm: float) -> float:
	return rad_to_deg(2.0 * atan(18.0 / mm))


func _shot(view: String) -> Image:
	var spec: Dictionary = VIEWS[view]
	_set_state(String(spec.state))
	_camera.fov = _fov(float(spec.mm))
	_camera.position = _g(spec.eye as Array)
	_camera.look_at(_g(spec.at as Array))
	_label.text = view
	await _frames(12)
	await RenderingServer.frame_post_draw
	return get_viewport().get_texture().get_image()


## Тот же кадр машины с расстояния distance: фокус растёт с расстоянием, включается свой LOD.
func _shot_far(distance: float) -> Image:
	_set_state("ready")
	var at: Vector3 = _g([0.0, -0.3, 0.6])
	var direction: Vector3 = (_g([4.4, -5.2, 1.55]) - at).normalized()
	_camera.position = at + direction * distance
	_camera.look_at(at)
	_camera.fov = rad_to_deg(2.0 * atan(3.4 / distance))
	var lod: int = 0 if distance < float(Balance.VEHICLE_LOD.lod1_m) else (1 if distance < float(Balance.VEHICLE_LOD.lod2_m) else 2)
	_label.text = "%d м — LOD%d" % [int(distance), lod]
	await _frames(12)
	await RenderingServer.frame_post_draw
	return get_viewport().get_texture().get_image()


func _save(name: String, image: Image) -> void:
	var path: String = OUTPUT_DIR + "/coupe_ilya_" + name + ".png"
	if image == null or image.save_png(ProjectSettings.globalize_path(path)) != OK:
		_fail("не сохранился " + path)
		return
	_written.append(path)
	print("coupe_ilya_shots: ", path)


func _save_grid(name: String, cells: Array[Image], columns: int) -> void:
	var cell_size: Vector2i = SIZE / 2
	var rows: int = ceili(float(cells.size()) / float(columns))
	var grid: Image = Image.create(cell_size.x * columns, cell_size.y * rows, false, Image.FORMAT_RGB8)
	for index: int in range(cells.size()):
		var cell: Image = cells[index]
		cell.convert(Image.FORMAT_RGB8)
		cell.resize(cell_size.x, cell_size.y, Image.INTERPOLATE_LANCZOS)
		grid.blit_rect(cell, Rect2i(Vector2i.ZERO, cell_size), Vector2i(index % columns * cell_size.x, index / columns * cell_size.y))
	_save(name, grid)


func _wanted(view: String) -> bool:
	return _only.is_empty() or view in _only


func _frames(count: int) -> void:
	for index: int in range(count):
		await get_tree().process_frame
