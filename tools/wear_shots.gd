extends Node3D
## Честное сравнение износа ПМ: ручные карты 60 и 20 рядом с шейдером износа (weapon_wear) при той же
## прочности — один свет (как tools/pm_shots), одни ракурсы. Снимки docs/screens/wear_*.png:
##   wear_<ракурс>.png — сетка 2×2: строки 60 / 20, слева ручные карты, справа шейдер;
##   wear_base.png — материал GLB и шейдер при 100 % (должны совпасть); wear_steps.png — шейдер при 100 … 0; wear_wet.png — 20 %: сухо и в дождь;
##   wear_nvg.png — 20 % от первого лица ночью в ПНВ (ИК-подсветка и трубка — как в CameraRig).
## Запуск с окном: tools/godot.cmd --windowed --resolution 1280x720 res://tools/wear_shots.tscn
## Выбор: после -- передать only=right,fp,steps (ракурсы: right, left, front34, rear_close, fp, world, base, steps, wet, nvg).

const WEAPON_ID: String = "wpn_hg_01"
const OUTPUT_DIR: String = "res://docs/screens"
const CELL: Vector2i = Vector2i(960, 540)
## Ракурсы предметной съёмки: камера — центр модели + offset (оси модели: +Z дуло, +Y верх, −X — правая
## сторона стрелка); focus — сдвиг точки взгляда от центра; lod 1 — мировая модель (третье лицо).
const VIEWS: Dictionary = {
	"right": {"offset": Vector3(-0.40, 0.05, 0.02), "fov": 30.0},
	"left": {"offset": Vector3(0.40, 0.05, 0.02), "fov": 30.0},
	"front34": {"offset": Vector3(0.17, 0.12, 0.25), "fov": 30.0},
	"rear_close": {"offset": Vector3(0.17, 0.09, -0.17), "fov": 30.0, "focus": Vector3(0.0, 0.02, -0.02)},
	"world": {"offset": Vector3(-0.5, 0.2, 0.3), "fov": 30.0, "lod": 1},
}

var _camera: Camera3D
var _label: Label
var _environment: Environment
var _lights: Array[DirectionalLight3D] = []
var _nvg_rect: ColorRect
var _vm_space: Node3D
var _arms: FirstPersonArms
var _only: PackedStringArray = []
var _failures: int = 0
var _written: Array[String] = []


func _ready() -> void:
	Engine.max_fps = 60
	if DisplayServer.get_name() == "headless":
		push_error("wear_shots: снимки требуют окна и настоящего GPU, без --headless")
		get_tree().quit(1)
		return
	get_window().content_scale_size = Vector2i(1280, 720)
	get_window().size = Vector2i(1280, 720)
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	RenderingServer.global_shader_parameter_set("rain_wet", 0.0)
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("only="):
			_only = argument.trim_prefix("only=").split(",", false)
	_build_stage()
	if String(WeaponDb.weapon(WEAPON_ID).get("state_maps", "")) == "":
		push_error("wear_shots: у ПМ нет ручных карт состояний — сравнивать не с чем")
		get_tree().quit(1)
		return
	for view: String in VIEWS:
		if _wanted(view):
			await _pairs(view)
	if _wanted("fp"):
		await _pairs("fp")
	if _wanted("base"):
		var base: Array[Image] = [await _shot("rear_close", 100.0, "glb", "материал GLB 100"), await _shot("rear_close", 100.0, "shader", "шейдер 100")]
		_save_grid("wear_base", base, 2)
	if _wanted("steps"):
		await _steps()
	if _wanted("wet"):
		await _wet()
	if _wanted("nvg"):
		await _nvg()
	RenderingServer.global_shader_parameter_set("rain_wet", 0.0)
	print("wear_shots: снимков %d, ошибок %d" % [_written.size(), _failures])
	for child: Node in get_children():
		child.queue_free()
	await _frames(3)
	get_tree().quit(1 if _failures > 0 else 0)


func _build_stage() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUTPUT_DIR))
	# свет и фон — как в tools/pm_shots: сравнения ПМ между собой остаются сопоставимыми
	var world: WorldEnvironment = WorldEnvironment.new()
	var environment: Environment = Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.12, 0.15, 0.19)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(0.78, 0.85, 1.0)
	environment.ambient_light_energy = 0.55
	environment.tonemap_mode = Environment.TONE_MAPPER_ACES
	environment.ssao_enabled = true
	environment.ssao_radius = 0.035
	environment.glow_enabled = true
	world.environment = environment
	add_child(world)
	_environment = environment
	var key: DirectionalLight3D = DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-32, 42, 0)
	key.light_energy = 2.2
	key.light_color = Color(1.0, 0.92, 0.82)
	key.shadow_enabled = true
	add_child(key)
	_lights.append(key)
	var fill: DirectionalLight3D = DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-22, -115, 0)
	fill.light_energy = 1.2
	fill.light_color = Color(0.68, 0.80, 1.0)
	add_child(fill)
	_lights.append(fill)
	var plane: PlaneMesh = PlaneMesh.new()
	plane.size = Vector2(40.0, 40.0)
	var ground_material: StandardMaterial3D = StandardMaterial3D.new()
	ground_material.albedo_color = Color(0.20, 0.23, 0.26)
	ground_material.roughness = 0.88
	var ground: MeshInstance3D = MeshInstance3D.new()
	ground.mesh = plane
	ground.material_override = ground_material
	ground.position.y = -1.5
	add_child(ground)
	_camera = Camera3D.new()
	_camera.near = 0.005
	_camera.far = 100.0
	add_child(_camera)
	_camera.current = true
	_vm_space = Node3D.new()
	_vm_space.name = "ViewmodelSpace"
	add_child(_vm_space)
	# трубка ПНВ — тот же шейдер, что у CameraRig; подпись — поверх неё
	var tube: CanvasLayer = CanvasLayer.new()
	tube.layer = 1
	add_child(tube)
	_nvg_rect = ColorRect.new()
	_nvg_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	var tube_material: ShaderMaterial = ShaderMaterial.new()
	var tube_shader: Shader = Shader.new()
	tube_shader.code = CameraRig.NVG_SHADER
	tube_material.shader = tube_shader
	_nvg_rect.material = tube_material
	_nvg_rect.visible = false
	tube.add_child(_nvg_rect)
	var layer: CanvasLayer = CanvasLayer.new()
	layer.layer = 2
	add_child(layer)
	_label = Label.new()
	_label.position = Vector2(24, 18)
	_label.add_theme_font_size_override("font_size", 34)
	_label.add_theme_color_override("font_color", Color(1, 1, 1))
	_label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_label.add_theme_constant_override("outline_size", 8)
	layer.add_child(_label)


## ПМ при прочности dur: «shader» — шейдер износа (как в игре), «hand» — ручные карты состояния (прежний
## путь, для сравнения), «glb» — исходные материалы GLB (100 %): шейдер при 100 % должен их повторять.
func _make(dur: float, mode: String, lod: int) -> Node3D:
	if mode == "shader":
		return WeaponModels.build(WEAPON_ID, {}, lod, dur)
	var model: Node3D = WeaponModels.build(WEAPON_ID, {}, lod, 100.0)
	if mode == "glb":
		for node: Node in model.find_children("*", "MeshInstance3D", true, false):
			var mesh: MeshInstance3D = node as MeshInstance3D
			for surface: int in range(mesh.mesh.get_surface_count() if mesh.mesh else 0):
				mesh.set_surface_override_material(surface, null)
		return model
	var maps: String = String(WeaponDb.weapon(WEAPON_ID).get("state_maps", ""))
	var visual: int = WeaponCondition.stage({"dur": dur})
	if visual < int(Balance.CONDITION.full) and not WeaponCondition._apply_state_maps(model, maps, visual):
		_failures += 1
		push_error("wear_shots: ручные карты %d не нашлись" % visual)
	return model


## Модель в кадре ракурса view (предметная съёмка или от первого лица с руками Persona) и снимок.
func _shot(view: String, dur: float, mode: String, text: String) -> Image:
	var spec: Dictionary = VIEWS.get(view, {})
	var model: Node3D = _make(dur, mode, int(spec.get("lod", 0)))
	_vm_space.transform = Transform3D.IDENTITY
	_vm_space.add_child(model)
	var rig: WeaponRig = WeaponRig.find_on(model)
	if rig == null:
		_failures += 1
		push_error("wear_shots: нужен импортированный ПМ")
		model.queue_free()
		return null
	rig.set_ammo_state(8)
	if view == "fp":
		_first_person(model, rig)
	else:
		_camera.transform = Transform3D.IDENTITY
		_camera.near = 0.005
		_camera.fov = float(spec.get("fov", 30.0))
		await _frames(2)
		var center: Vector3 = _bounds(model).get_center()
		var focus: Vector3 = center + (spec.get("focus", Vector3.ZERO) as Vector3)
		_camera.position = focus + (spec.offset as Vector3)
		_camera.look_at(focus)
	_label.text = text
	# у кадра от первого лица в сетку идёт вырезка вокруг оружия — подпись внутри неё
	_label.position = Vector2(612, 386) if view == "fp" else Vector2(24, 18)
	_label.add_theme_font_size_override("font_size", 20 if view == "fp" else 34)
	await _frames(8)
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	var image: Image = get_viewport().get_texture().get_image()
	if view == "fp":
		# тот же игровой кадр от бедра, но крупнее: ПМ в нижней правой части экрана
		var scale: float = float(image.get_width()) / 1280.0
		image = image.get_region(Rect2i(Vector2i(Vector2(600, 380) * scale), Vector2i(Vector2(560, 315) * scale)))
	if _arms:
		_arms.visible = false
	model.queue_free()
	await _frames(2)
	return image


## Как CameraRig от бедра: модель развёрнута к камере, своё поле зрения у вьюмодели, руки держат ПМ.
func _first_person(model: Node3D, rig: WeaponRig) -> void:
	if _arms == null:
		_arms = (load("res://scenes/player/first_person_arms.tscn") as PackedScene).instantiate() as FirstPersonArms
		_vm_space.add_child(_arms)
	_arms.visible = true
	_arms.bind_weapon(model)
	rig.attach_arms(_arms)
	model.rotation.y = PI
	model.position = Balance.FPS_HIP_POSE + rig.view_offset()
	model.basis *= Basis.from_euler(rig.view_rotation_degrees() * (PI / 180.0))
	_camera.transform = Transform3D.IDENTITY
	_camera.near = 0.05
	_camera.fov = Settings.fps_fov_v()
	var vk: float = CameraRig.viewmodel_scale(_camera.fov)
	_vm_space.transform = Transform3D(Basis.from_scale(Vector3(vk, vk, 1.0)), Vector3.ZERO)
	_arms.set_hand_target("Left", rig.get_hand_target(), rig.get_hand_weight())
	_arms.update_pose()


func _pairs(view: String) -> void:
	var cells: Array[Image] = []
	for dur: float in [60.0, 20.0]:
		cells.append(await _shot(view, dur, "hand", "ручные карты %d" % int(dur)))
		cells.append(await _shot(view, dur, "shader", "шейдер %d" % int(dur)))
	_save_grid("wear_" + view, cells, 2)


func _steps() -> void:
	var cells: Array[Image] = []
	for dur: float in [100.0, 80.0, 60.0, 40.0, 20.0, 0.0]:
		cells.append(await _shot("right", dur, "shader", "шейдер %d" % int(dur)))
	_save_grid("wear_steps", cells, 3)


func _wet() -> void:
	var cells: Array[Image] = []
	RenderingServer.global_shader_parameter_set("rain_wet", 0.0)
	cells.append(await _shot("front34", 20.0, "shader", "шейдер 20, сухо"))
	RenderingServer.global_shader_parameter_set("rain_wet", 1.0)
	cells.append(await _shot("front34", 20.0, "shader", "шейдер 20, дождь"))
	RenderingServer.global_shader_parameter_set("rain_wet", 0.0)
	_save_grid("wear_wet", cells, 2)


## Ночь в ПНВ: солнца и подсветки стенда нет, ИК-фонарь от камеры, окружение и выдержка усилены, трубка —
## как в CameraRig (_tick_nvg_ir, _nvg_env, NVG_SHADER).
func _nvg() -> void:
	var ambient: float = _environment.ambient_light_energy
	var exposure: float = _environment.tonemap_exposure
	var background: Color = _environment.background_color
	for light: DirectionalLight3D in _lights:
		light.visible = false
	_environment.background_color = Color(0.008, 0.01, 0.014)
	_environment.ambient_light_energy = maxf(0.06, 0.5) * 3.0
	_environment.tonemap_exposure = exposure * 1.5
	var ir: SpotLight3D = SpotLight3D.new()
	ir.light_color = Color(0.9, 0.95, 1.0)
	ir.light_energy = 0.9
	ir.spot_range = 32.0
	ir.spot_angle = 48.0
	ir.spot_attenuation = 0.6
	ir.shadow_enabled = true
	ir.light_specular = 0.1
	_camera.add_child(ir)
	_nvg_rect.visible = true
	var cells: Array[Image] = []
	cells.append(await _shot("fp", 20.0, "hand", "ПНВ: ручные карты 20"))
	cells.append(await _shot("fp", 20.0, "shader", "ПНВ: шейдер 20"))
	_save_grid("wear_nvg", cells, 2)
	_nvg_rect.visible = false
	ir.queue_free()
	for light: DirectionalLight3D in _lights:
		light.visible = true
	_environment.background_color = background
	_environment.ambient_light_energy = ambient
	_environment.tonemap_exposure = exposure


func _save_grid(name: String, cells: Array[Image], columns: int) -> void:
	var rows: int = ceili(float(cells.size()) / float(columns))
	var grid: Image = Image.create(CELL.x * columns, CELL.y * rows, false, Image.FORMAT_RGB8)
	for index: int in range(cells.size()):
		var cell: Image = cells[index]
		if cell == null:
			continue
		cell.convert(Image.FORMAT_RGB8)
		cell.resize(CELL.x, CELL.y, Image.INTERPOLATE_LANCZOS)
		grid.blit_rect(cell, Rect2i(Vector2i.ZERO, CELL), Vector2i(index % columns * CELL.x, index / columns * CELL.y))
	var path: String = OUTPUT_DIR + "/" + name + ".png"
	var error: Error = grid.save_png(ProjectSettings.globalize_path(path))
	if error != OK:
		_failures += 1
		push_error("wear_shots: ошибка сохранения %s: %s" % [path, error_string(error)])
		return
	_written.append(path)
	print("wear_shots: ", path)


func _wanted(view: String) -> bool:
	return _only.is_empty() or view in _only


func _bounds(root: Node3D) -> AABB:
	var bounds: AABB = AABB()
	var started: bool = false
	for node: Node in root.find_children("*", "MeshInstance3D", true, false):
		var instance: MeshInstance3D = node as MeshInstance3D
		if instance.mesh == null or not instance.is_visible_in_tree():
			continue
		var at: AABB = instance.global_transform * instance.get_aabb()
		bounds = bounds.merge(at) if started else at
		started = true
	return bounds


func _frames(count: int) -> void:
	for index: int in range(count):
		await get_tree().process_frame
