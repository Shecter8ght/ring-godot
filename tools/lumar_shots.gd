extends Node3D
## Проверка игровых карт (вид один при прочности 100/60/20 — решение владельца 2026-10-19; на 20 и 0 % тускнеет
## только марка), посадки и вида из глаза; снимки реального Forward+.

var _camera: Camera3D


func _ready() -> void:
	Profile.use_file("user://lumar_shots_test.json", true)
	var world: WorldEnvironment = WorldEnvironment.new()
	var env: Environment = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.12, 0.135, 0.15)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.7, 0.75, 0.8)
	env.ambient_light_energy = 0.7
	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	env.ssao_enabled = true
	env.ssao_radius = 0.025
	env.glow_enabled = true
	world.environment = env
	add_child(world)
	var key: DirectionalLight3D = DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-35, 40, 0)
	key.light_energy = 3.0
	add_child(key)
	var rim: DirectionalLight3D = DirectionalLight3D.new()
	rim.rotation_degrees = Vector3(-20, -140, 0)
	rim.light_color = Color(0.7, 0.8, 1.0)
	rim.light_energy = 1.5
	add_child(rim)
	_camera = Camera3D.new()
	_camera.near = 0.002
	_camera.current = true
	add_child(_camera)
	var row: Node3D = Node3D.new()
	add_child(row)
	for i: int in range(3):
		var state: int = [100, 60, 20][i]
		var holder: Node3D = Node3D.new()
		row.add_child(holder)
		WeaponMods.fit(holder, String(WeaponDb.weapon("wpn_ar_02").model), {"optic_primary": {"id": "optic_holo_01", "dur": state}})
		holder.position.x = (i - 1) * 0.15
		holder.rotation.y = 0.55
	_camera.fov = 28.0
	_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	_camera.size = 0.32
	_camera.position = Vector3(0, 0.24, -0.56)
	_camera.look_at(Vector3(0, 0.12, 0))
	var labels: CanvasLayer = CanvasLayer.new()
	add_child(labels)
	for i: int in range(3):
		var label: Label = Label.new()
		label.text = ["прочность 20 %", "прочность 60 %", "прочность 100 %"][i]
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.add_theme_font_size_override("font_size", 22)
		label.position = Vector2(get_viewport().get_visible_rect().size.x * i / 3.0, get_viewport().get_visible_rect().size.y * 0.68)
		label.size.x = get_viewport().get_visible_rect().size.x / 3.0
		labels.add_child(label)
	await _capture("lumar_states_verified")
	row.queue_free()
	labels.queue_free()
	await get_tree().process_frame
	for state: int in [100, 60, 20, 0]:
		var model: Node3D = WeaponModels.build("wpn_ar_02", {"optic_primary": {"id": "optic_holo_01", "dur": state}}, 0, state)
		add_child(model)
		var height: float = float(model.get_meta("sight_h"))
		_camera.fov = 45.0
		_camera.projection = Camera3D.PROJECTION_PERSPECTIVE
		_camera.position = Vector3(0, height, -0.23)
		_camera.look_at(Vector3(0, height, 1.0))
		await _capture("lumar_eye_%d" % state)
		if state in [100, 20]:
			var check: MeshInstance3D = MeshInstance3D.new()
			var quad: QuadMesh = QuadMesh.new()
			quad.size = Vector2(0.3, 0.3)
			check.mesh = quad
			check.position = Vector3(0, height, 0.45)
			var shader: Shader = Shader.new()
			shader.code = "shader_type spatial; render_mode unshaded, cull_disabled; void fragment() { float c = mod(floor(UV.x*8.0)+floor(UV.y*8.0),2.0); ALBEDO = mix(vec3(0.03),vec3(0.8),c); }"
			var mat: ShaderMaterial = ShaderMaterial.new()
			mat.shader = shader
			check.material_override = mat
			add_child(check)
			await _capture("lumar_glass_%d" % state)
			check.queue_free()
			await get_tree().process_frame
		if state == 100:
			_camera.fov = 30.0
			_camera.position = Vector3(-0.8, 0.35, -0.55)
			_camera.look_at(Vector3(0, 0.05, 0.18))
			await _capture("lumar_rifle")
		model.queue_free()
		await get_tree().process_frame
	var entry: Dictionary = ItemDb.make("wpn_ar_02", 1)
	entry.dur = 20.0
	entry.mods = {"optic_primary": {"id": "optic_holo_01", "dur": 0.0}}
	Profile.equipment = {"primary": entry}
	Profile.money = 50000
	var ui: HideoutUI = HideoutUI.new()
	add_child(ui)
	ui.open(HideoutStation.Kind.WORKBENCH)
	await _capture("weapon_condition_workbench")
	get_tree().quit(0)


func _capture(file: String) -> void:
	for frame: int in range(10):
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % file))
	print("lumar_shots: ", file)
