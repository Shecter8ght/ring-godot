extends Node3D
## Фриз первых попаданий: по каждому виду поверхности — первое попадание и самый длинный кадр за ним
## (на чистом кэше шейдеров первое попадание нового вида собирало шейдеры до секунды кадра).
## С окном (шейдеры собираются только при отрисовке):
##   tools/godot.cmd --windowed --resolution 1280x720 res://tools/first_hit_test.tscn
## FIRST_HIT_WARM=1 — сначала разогрев, как под экраном загрузки рейда (ImpactFx.warm_up).
## Чистый кэш, как у друга при первом запуске, не трогая общий: APPDATA и LOCALAPPDATA — на пустую
## папку (Godot берёт из APPDATA папку данных, в ней кэш шейдеров и конвейеров).
## Провал — кадр длиннее FIRST_HIT_LIMIT_MS (по умолчанию 100) при включённом разогреве.

const KINDS: Array[String] = ["concrete", "tile", "asphalt", "metal", "wood", "cardboard", "plastic", "fabric",
	"grass", "dirt", "mud", "gravel", "snow", "flesh"]

var _camera: Camera3D
var _worst: float = 0.0
var _worst_what: String = ""


func _ready() -> void:
	var warm: bool = OS.get_environment("FIRST_HIT_WARM") == "1"
	var limit: float = float(OS.get_environment("FIRST_HIT_LIMIT_MS")) if OS.get_environment("FIRST_HIT_LIMIT_MS") != "" else 100.0
	_world()
	var wall: StaticBody3D = _box(Vector3(0.0, 1.5, -3.0), Vector3(6.0, 3.0, 0.2))
	var floor_body: StaticBody3D = _box(Vector3(0.0, -0.1, 0.0), Vector3(20.0, 0.2, 20.0))
	var glass: GlassPanes = GlassPanes.new()
	var panes: Array = []
	for index: int in range(2):
		panes.append({"xf": Transform3D(Basis.IDENTITY, Vector3(-1.2 + index * 2.4, 1.2, -1.6)), "size": Vector2(1.2, 1.8),
			"floor_y": 0.0, "sill": Vector3(1.3, 0.1, 0.15), "broken": false, "tempered": index == 1})
	glass.setup(panes)
	add_child(glass)
	await get_tree().physics_frame
	# пустые кадры: сцена, тени, небо собрались до замеров
	for i: int in range(30):
		await get_tree().process_frame
	if warm:
		var t0: int = Time.get_ticks_msec()
		await ImpactFx.warm_up()
		print("first_hit: разогрев %d мс" % (Time.get_ticks_msec() - t0))
		for i: int in range(10):
			await get_tree().process_frame
	for kind: String in KINDS:
		var on_floor: bool = kind in ["grass", "dirt", "mud", "gravel", "snow"]
		var body: StaticBody3D = floor_body if on_floor else wall
		body.set_meta("surface", kind)
		var pos: Vector3 = Vector3(randf_range(-1.0, 1.0), 0.0, -1.0) if on_floor else Vector3(randf_range(-1.5, 1.5), 1.4, -2.9)
		var normal: Vector3 = Vector3.UP if on_floor else Vector3.BACK
		await _measure(kind, func() -> void: ImpactFx.spawn_hit({"position": pos, "normal": normal, "collider": body}, (pos - _camera.global_position).normalized()))
	var glass_body: StaticBody3D = glass.get_node("Glass")
	await _measure("стекло: трещины", func() -> void: glass.bullet(0, 20.0, Vector3(-1.2, 1.4, -1.6), Vector3.FORWARD))
	await _measure("стекло: распад", func() -> void: glass._apply(0, 1000.0, Vector2(-1, -1), -1.0))
	await _measure("стекло закалённое", func() -> void: glass.bullet(1, 30.0, Vector3(1.2, 1.4, -1.6), Vector3.FORWARD); glass._apply(1, 1000.0, Vector2(-1, -1), -1.0))
	await _measure("граната", func() -> void: ImpactFx.explosion(Vector3(0.0, 0.0, -2.0)))
	var fails: int = 1 if warm and _worst > limit else 0
	print("first_hit: худший кадр %.0f мс (%s), разогрев %s, предел %.0f мс — провалено %d" % [_worst, _worst_what, "да" if warm else "нет", limit, fails])
	get_tree().quit(fails)


## Самый длинный кадр за 12 кадров после действия.
func _measure(what: String, action: Callable) -> void:
	await get_tree().process_frame
	var last: int = Time.get_ticks_usec()
	action.call()
	var worst: float = 0.0
	for i: int in range(12):
		await get_tree().process_frame
		var now: int = Time.get_ticks_usec()
		worst = maxf(worst, float(now - last) / 1000.0)
		last = now
	print("first_hit: %-18s %6.1f мс" % [what, worst])
	if worst > _worst:
		_worst = worst
		_worst_what = what
	# эффекты — дожить и уйти, чтобы не мешали следующему замеру
	for i: int in range(20):
		await get_tree().process_frame


func _world() -> void:
	var environment: Environment = Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.3, 0.33, 0.38)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(0.5, 0.52, 0.56)
	environment.tonemap_mode = Environment.TONE_MAPPER_AGX
	var world_environment: WorldEnvironment = WorldEnvironment.new()
	world_environment.environment = environment
	add_child(world_environment)
	var light: DirectionalLight3D = DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-40, -30, 0)
	light.shadow_enabled = true
	add_child(light)
	_camera = Camera3D.new()
	add_child(_camera)
	_camera.look_at_from_position(Vector3(0.0, 1.6, 2.5), Vector3(0.0, 1.0, -2.0), Vector3.UP)


func _box(pos: Vector3, size: Vector3) -> StaticBody3D:
	var body: StaticBody3D = StaticBody3D.new()
	var shape: BoxShape3D = BoxShape3D.new()
	shape.size = size
	var collision: CollisionShape3D = CollisionShape3D.new()
	collision.shape = shape
	body.add_child(collision)
	var mesh: MeshInstance3D = MeshInstance3D.new()
	var box: BoxMesh = BoxMesh.new()
	box.size = size
	mesh.mesh = box
	body.add_child(mesh)
	body.position = pos
	add_child(body)
	return body
