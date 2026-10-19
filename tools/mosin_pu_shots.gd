extends Node3D
## Мосин 1891/30 ПУ в движке: игровая модель assets/models/weapons/mosin_pu (tools/mosin_pu/game_*.py) при пасмурной
## дневной панораме и солнце. Ракурсы те же, что у сверки формы в Blender (камера и точка взгляда — в осях винтовки, мм), поэтому
## кадры можно класть рядом с рендером исходника. Снимки docs/screens/mosin_pu_*.png:
##   mosin_pu_<ракурс>.png — вид от первого лица, затвор, направляющие обоймы, шейка, прицел, дуло, приклад, целиком
##   слева, окуляр;
##   mosin_pu_bolt_open.png — затвор открыт и отведён (узлы Bolt / Bolt_Rotor / Bolt_Cocking двигает код);
##   mosin_pu_lod.png — вид от первого лица и мировая модель (LOD1) с 3 м.
## Вид один при любой прочности (решение владельца 2026-10-19) — прежние кадры износа шейдером убраны.
## Запуск с окном: tools/godot.cmd --windowed --resolution 1100x760 res://tools/mosin_pu_shots.tscn [-- only=fp_hip,lod]

const MODEL: String = "res://assets/models/weapons/mosin_pu/mosin_pu.glb"
const INFO: String = "res://assets/models/weapons/mosin_pu/mosin_pu.json"
const OUTPUT_DIR: String = "res://docs/screens"
const SKY: String = "res://assets/sky/kloofendal_overcast_puresky.hdr"
const SIZE: Vector2i = Vector2i(1100, 760)
## Камера (eye) и точка взгляда (at) в осях винтовки, мм: дуло +X, верх +Z, правая сторона стрелка −Y;
## fov — по ширине кадра, как у камеры Blender.
const VIEWS: Dictionary = {
	"fp_hip": {"eye": [-430, 85, 120], "at": [60, 0, 0], "fov": 48.0},
	"bolt_right": {"eye": [-130, -250, 70], "at": [-110, 0, -10], "fov": 40.0},
	"clip_guides": {"eye": [-20, -110, 160], "at": [-106, 0, 6], "fov": 26.0},
	"wrist_right": {"eye": [-360, -240, -10], "at": [-240, 0, -55], "fov": 40.0},
	"scope_left": {"eye": [-260, 230, 140], "at": [-100, 8, 40], "fov": 40.0},
	"muzzle": {"eye": [560, 160, 90], "at": [690, 0, 0], "fov": 45.0},
	"butt": {"eye": [-650, -260, -40], "at": [-450, 0, -90], "fov": 45.0},
	"full_left": {"eye": [100, 1500, 150], "at": [100, 0, -40], "fov": 50.0},
	"ads": {"eye": [-262, 8, 51.2], "at": [0, 8, 51.2], "fov": 50.0},
}
const BOLT_BACK: float = 0.110  # ход затвора до упора (форма v08; mosin_pu.json, rig.Bolt)
const COCK_TRAVEL: float = 0.0095

var _camera: Camera3D
var _label: Label
var _grip: Vector3 = Vector3.ZERO
var _only: PackedStringArray = []
var _failures: int = 0
var _written: Array[String] = []


func _ready() -> void:
	Engine.max_fps = 60
	if DisplayServer.get_name() == "headless":
		push_error("mosin_pu_shots: снимки требуют окна и настоящего GPU, без --headless")
		get_tree().quit(1)
		return
	get_window().content_scale_size = SIZE
	get_window().size = SIZE
	RenderingServer.global_shader_parameter_set("rain_wet", 0.0)
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("only="):
			_only = argument.trim_prefix("only=").split(",", false)
	if not ResourceLoader.exists(MODEL, "PackedScene"):
		push_error("mosin_pu_shots: нет импортированной модели " + MODEL)
		get_tree().quit(1)
		return
	var info: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(INFO)) as Dictionary
	var grip: Array = info.get("grip_origin_rifle_mm", [0, 0, 0]) as Array
	_grip = Vector3(float(grip[0]), float(grip[1]), float(grip[2]))
	_build_stage()
	for view: String in VIEWS:
		if _wanted(view):
			_save(view, await _shot(view, 0, false, view))
	if _wanted("bolt_open"):
		_save("bolt_open", await _shot("bolt_right", 0, true, "затвор открыт и отведён"))
	if _wanted("lod"):
		var lods: Array[Image] = [await _shot("full_left", 0, false, "LOD0"), await _shot("world", 1, false, "LOD1, 3 м")]
		_save_grid("lod", lods, 2)
	print("mosin_pu_shots: снимков %d, ошибок %d" % [_written.size(), _failures])
	for child: Node in get_children():
		child.queue_free()
	await _frames(3)
	get_tree().quit(1 if _failures > 0 else 0)


func _build_stage() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUTPUT_DIR))
	# дневная панорама (Poly Haven, assets/sky): лак ложи и полированный затвор отражают настоящее небо, как в игре на улице
	var sky_material: PanoramaSkyMaterial = PanoramaSkyMaterial.new()
	sky_material.panorama = load(SKY) as Texture2D
	sky_material.energy_multiplier = 1.2
	var sky: Sky = Sky.new()
	sky.sky_material = sky_material
	var environment: Environment = Environment.new()
	environment.background_mode = Environment.BG_SKY
	environment.sky = sky
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	environment.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	environment.tonemap_mode = Environment.TONE_MAPPER_AGX
	environment.ssao_enabled = true
	environment.ssao_radius = 0.035
	var world: WorldEnvironment = WorldEnvironment.new()
	world.environment = environment
	add_child(world)
	var sun: DirectionalLight3D = DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-38, 35, 0)
	sun.light_energy = 2.0
	sun.light_color = Color(1.0, 0.94, 0.86)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 8.0
	add_child(sun)
	var fill: DirectionalLight3D = DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-20, -140, 0)
	fill.light_energy = 0.5
	fill.light_color = Color(0.7, 0.8, 1.0)
	add_child(fill)
	_camera = Camera3D.new()
	_camera.near = 0.005
	_camera.far = 100.0
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


## Точка в осях винтовки (мм) → оси модели: x ← y, y ← z, z ← x от середины шейки (game_export.py).
func _game(mm: Array) -> Vector3:
	var p: Vector3 = Vector3(float(mm[0]), float(mm[1]), float(mm[2])) - _grip
	return Vector3(p.y, p.z, p.x) * 0.001


func _shot(view: String, lod: int, open: bool, text: String) -> Image:
	var model: Node3D = (load(MODEL) as PackedScene).instantiate() as Node3D
	WeaponModels._select_lod(model, lod)
	add_child(model)
	WeaponCondition.apply_visual(model)
	if open:
		# как в Blender: стебель повёрнут рукоятью вверх (−90° вокруг оси канала), затвор назад, курок взведён
		(model.find_child("Bolt_Rotor", true, false) as Node3D).rotation.z = deg_to_rad(-90.0)
		(model.find_child("Bolt", true, false) as Node3D).position.z -= BOLT_BACK
		(model.find_child("Bolt_Cocking", true, false) as Node3D).position.z -= COCK_TRAVEL
	if view == "world":
		_camera.fov = 30.0
		_camera.position = Vector3(2.6, 0.9, 1.2)
		_camera.look_at(Vector3(0.0, 0.0, 0.3))
	else:
		var spec: Dictionary = VIEWS[view]
		_camera.fov = float(spec.fov)
		_camera.position = _game(spec.eye as Array)
		_camera.look_at(_game(spec.at as Array))
	_label.text = text
	await _frames(10)
	await RenderingServer.frame_post_draw
	var image: Image = get_viewport().get_texture().get_image()
	model.queue_free()
	await _frames(2)
	return image


func _save(name: String, image: Image) -> void:
	var path: String = OUTPUT_DIR + "/mosin_pu_" + name + ".png"
	if image == null or image.save_png(ProjectSettings.globalize_path(path)) != OK:
		_failures += 1
		push_error("mosin_pu_shots: не сохранился " + path)
		return
	_written.append(path)
	print("mosin_pu_shots: ", path)


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
