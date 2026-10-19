extends Node3D
## Визуальная проверка попаданий по всем видам поверхности. Нужен рендер — только с окном.
## tools/godot.cmd --windowed --resolution 1600x900 res://tools/impact_gallery.tscn → docs/screens/impact_*.png
## Стены 3×3 (impact_gallery_*, impact_<вид>_close), ряд грунтов — трава кочками, земля, грязь, гравий:
## выстрелы из глаза под углом, как в игре (impact_ground_*), стальной лист на полу — вспышка, веер
## искр, искры скачут по полу (impact_metal_*), грунты крупно (impact_<вид>_air / _close), стёкла —
## одна пуля, три пули, закалённое (сетка кубиков, осыпается волной), ослабленное (трещины ползут,
## рассыпается на куски, «зубья» в раме) — impact_glass_*.
## Взрыв гранаты на полу — огонь, дым листами кадров (impact_boom_*).
## IMPACT_ONLY=walls,ground,metal,close,glass,boom — выборочно; IMPACT_GLOW=1 — со свечением (блумом), как
## в помещениях игры: NaN и пересветы в шейдерах видны ореолами.

const SURFACES: Array[String] = [
	"concrete", "tile", "asphalt",
	"metal", "wood", "cardboard",
	"plastic", "fabric", "glass",
]
const GROUNDS: Array[String] = ["grass", "dirt", "mud", "gravel"]
const COLORS := {
	"concrete": Color(0.52, 0.5, 0.46),
	"tile": Color(0.8, 0.79, 0.75),
	"asphalt": Color(0.18, 0.18, 0.17),
	"metal": Color(0.32, 0.36, 0.39),
	"wood": Color(0.42, 0.24, 0.11),
	"cardboard": Color(0.5, 0.36, 0.2),
	"plastic": Color(0.2, 0.25, 0.31),
	"fabric": Color(0.2, 0.16, 0.25),
	"grass": Color(0.24, 0.27, 0.15),
	"dirt": Color(0.36, 0.29, 0.21),
	"mud": Color(0.17, 0.14, 0.1),
	"gravel": Color(0.46, 0.45, 0.42),
	"floor": Color(0.42, 0.41, 0.39),
}
## Ряд грунтов и стальной лист — в стороне от стен, чтобы следы не мешали друг другу.
const GROUND_AT := Vector3(30.0, 0.0, 0.0)
const GLASS_AT := Vector3(30.0, 0.0, -9.0)
const FLOOR_Y: float = -0.3

var _only: PackedStringArray = PackedStringArray()
var _camera: Camera3D


func _ready() -> void:
	if OS.get_environment("IMPACT_ONLY") != "":
		_only = OS.get_environment("IMPACT_ONLY").split(",")
	_world()
	await get_tree().physics_frame
	await _warm_up()
	if _want("walls"):
		await _walls()
	var grounds: Dictionary = _grounds()
	var plate: StaticBody3D = _box("metal", GROUND_AT + Vector3(0.0, FLOOR_Y + 0.6, -4.0), Vector3(1.6, 1.2, 0.08), "metal")
	await get_tree().physics_frame
	# трава строит кочки и карту примятия за пару кадров
	await get_tree().create_timer(0.3).timeout
	if _want("ground"):
		await _ground_row(grounds)
	if _want("metal"):
		await _metal(plate)
	if _want("close"):
		for kind: String in GROUNDS:
			await _ground_close(kind, grounds[kind])
	if _want("glass"):
		await _glass()
	if _want("boom"):
		await _boom()
	print("impact_gallery: декалей %d" % _count_decals())
	get_tree().quit(0)


## Первое попадание в новый материал собирает шейдеры — длинный кадр сбил бы время снимков.
## Все виды один раз на виду, в стороне от мест съёмки.
func _warm_up() -> void:
	var spot := Vector3(-20.0, FLOOR_Y, 6.0)
	var dummy: StaticBody3D = _box("floor", spot + Vector3(0.0, -0.1, 0.0), Vector3(3.0, 0.2, 3.0), "concrete")
	_camera.look_at_from_position(spot + Vector3(0.0, 1.6, 3.0), spot, Vector3.UP)
	await get_tree().physics_frame
	for kind: String in Balance.IMPACT_SURFACES:
		dummy.set_meta("surface", kind)
		ImpactFx.spawn_hit({"position": spot, "normal": Vector3.UP, "collider": dummy}, Vector3(0.0, -0.6, -0.8).normalized())
	await get_tree().create_timer(1.0).timeout
	dummy.set_meta("surface", "concrete")


func _want(part: String) -> bool:
	return _only.is_empty() or _only.has(part)


func _walls() -> void:
	var bodies: Array[StaticBody3D] = []
	for index: int in range(SURFACES.size() - 1):
		bodies.append(_panel(SURFACES[index], _cell_position(index)))
	var glass := GlassPanes.new()
	var glass_pos := _cell_position(SURFACES.size() - 1)
	glass.setup([{
		"xf": Transform3D(Basis.IDENTITY, glass_pos),
		"size": Vector2(1.55, 1.55),
		"floor_y": glass_pos.y - 0.9,
		"sill": Vector3(1.65, 0.12, 0.18),
		"broken": false,
		"tempered": false,
	}])
	add_child(glass)
	_label("glass", glass_pos)
	await get_tree().physics_frame
	_camera.look_at_from_position(Vector3(0, 2.65, 10.5), Vector3(0, 2.65, 0), Vector3.UP)
	for index: int in range(bodies.size()):
		var center := _cell_position(index) + Vector3(0, 0, 0.07)
		for offset: Vector2 in [Vector2(-0.34, 0.18), Vector2(0.05, -0.2), Vector2(0.34, 0.22)]:
			ImpactFx.spawn_hit({
				"position": center + Vector3(offset.x, offset.y, 0),
				"normal": Vector3.BACK,
				"collider": bodies[index],
			}, Vector3.FORWARD)
	glass.bullet(0, 18.0, glass_pos + Vector3(0.08, -0.04, 0.07))
	ImpactFx.spawn_hit({
		"position": glass_pos + Vector3(0.08, -0.04, 0.07),
		"normal": Vector3.BACK,
		"collider": glass.get_node("Glass"),
		"shape": 0,
	}, Vector3.FORWARD)
	await get_tree().create_timer(0.1).timeout
	_save("impact_gallery_particles.png")
	await get_tree().process_frame
	await get_tree().create_timer(2.2).timeout
	_save("impact_gallery_decals.png")
	for index: int in [0, 3, 4]:
		var point: Vector3 = _cell_position(index) + Vector3(0, 0, 0.065)
		_camera.look_at_from_position(point + Vector3(0.45, 0.2, 2.0), point, Vector3.UP)
		await get_tree().create_timer(0.25).timeout
		var hit: Dictionary = {"position": point, "normal": Vector3.BACK, "collider": bodies[index]}
		await _capture(ImpactFx.spawn_hit.bind(hit, Vector3.FORWARD), 0.07, "impact_%s_close.png" % SURFACES[index])
		if index == 0:
			await get_tree().create_timer(2.0).timeout
			hit.position = point + Vector3(0.12, -0.1, 0.0)
			await _capture(ImpactFx.spawn_hit.bind(hit, Vector3.FORWARD), 0.4, "impact_concrete_dust.png")
		await get_tree().create_timer(1.6).timeout


## Ряд грунтов: стрелок стоит в 4 м, пули ложатся под углом, как в игре.
func _ground_row(grounds: Dictionary) -> void:
	var eye: Vector3 = GROUND_AT + Vector3(0.0, 1.65, 4.6)
	_camera.look_at_from_position(eye, GROUND_AT + Vector3(0.0, 0.1, 0.0), Vector3.UP)
	await get_tree().create_timer(0.3).timeout
	await _capture(_fire_row.bind(eye, grounds, [Vector2(-0.3, 0.25), Vector2(0.25, -0.2)]), 0.1, "impact_ground_burst.png")
	await get_tree().create_timer(2.5).timeout
	await _capture(_fire_row.bind(eye, grounds, [Vector2(0.1, 0.4), Vector2(-0.2, -0.35)]), 0.45, "impact_ground_air.png")
	await get_tree().create_timer(2.6).timeout
	_save("impact_ground_after.png")


func _fire_row(eye: Vector3, grounds: Dictionary, offsets: Array) -> void:
	for index: int in range(GROUNDS.size()):
		var center: Vector3 = _ground_position(index)
		for offset: Vector2 in offsets:
			_shoot(eye, center + Vector3(offset.x, 0.0, offset.y), grounds[GROUNDS[index]])


## Стальной лист на полу: вспышка, веер искр, искры скачут по полу.
func _metal(plate: StaticBody3D) -> void:
	var point: Vector3 = GROUND_AT + Vector3(0.1, FLOOR_Y + 0.75, -3.96)
	# камера у стрелка: искры летят по отражению пули — вправо и к полу, видно сбоку
	_camera.look_at_from_position(point + Vector3(-1.6, 0.45, 2.6), point + Vector3(0.7, -0.35, 0.5), Vector3.UP)
	await get_tree().create_timer(0.3).timeout
	var from: Vector3 = point + Vector3(-1.2, 0.3, 3.0)
	await _capture(_shoot.bind(from, point, plate), 0.03, "impact_metal_flash.png")
	await get_tree().create_timer(1.5).timeout
	await _capture(_shoot.bind(from, point + Vector3(0.1, 0.05, 0.0), plate), 0.1, "impact_metal_sparks.png")
	await get_tree().create_timer(1.5).timeout
	await _capture(_shoot.bind(from, point + Vector3(-0.1, -0.05, 0.0), plate), 0.35, "impact_metal_bounce.png")
	await get_tree().create_timer(1.5).timeout
	# очередь из трёх — как держит автомат
	for index: int in range(3):
		_shoot(from, point + Vector3(0.12 * index - 0.1, 0.08 * index, 0.0), plate)
		await get_tree().create_timer(0.09).timeout
	await get_tree().create_timer(0.05).timeout
	_save("impact_metal_burst.png")
	await get_tree().create_timer(1.5).timeout


func _ground_close(kind: String, body: StaticBody3D) -> void:
	var index: int = GROUNDS.find(kind)
	var point: Vector3 = _ground_position(index) + Vector3(0.35, 0.0, -0.4)
	_camera.look_at_from_position(point + Vector3(0.9, 0.55, 1.5), point + Vector3(0.0, 0.25, 0.0), Vector3.UP)
	await get_tree().create_timer(0.3).timeout
	var from: Vector3 = point + Vector3(-0.8, 1.5, 3.0)
	await _capture(_shoot.bind(from, point, body), 0.12, "impact_%s_close.png" % kind)
	await get_tree().create_timer(2.2).timeout
	await _capture(_shoot.bind(from, point + Vector3(0.15, 0.0, 0.1), body), 0.45, "impact_%s_air.png" % kind)
	await get_tree().create_timer(1.6).timeout


## Снимок через seconds после выстрела fire — время по кадрам и у каждого снимка свой выстрел:
## запись PNG занимает длинный кадр и сбила бы время следующего снимка той же очереди.
func _capture(fire: Callable, seconds: float, file_name: String) -> void:
	await get_tree().process_frame
	fire.call()
	var start: int = Time.get_ticks_usec()
	while float(Time.get_ticks_usec() - start) / 1000000.0 < seconds:
		await get_tree().process_frame
	_save(file_name)
	await get_tree().process_frame


## Стёкла перед стеной: обычное — одна пуля и три пули, закалённое, ослабленное до распада.
func _glass() -> void:
	var base: Vector3 = GLASS_AT
	_box("concrete", base + Vector3(0.0, 1.2, -2.0), Vector3(9.0, 3.0, 0.3), "concrete")
	var specs: Array = []
	var size := Vector2(1.4, 2.1)
	var sill := Vector3(1.5, 0.12, 0.16)
	for index: int in range(4):
		var center: Vector3 = base + Vector3((float(index) - 1.5) * 1.8, FLOOR_Y + sill.y + size.y * 0.5, 0.0)
		specs.append({"xf": Transform3D(Basis.IDENTITY, center), "size": size, "floor_y": FLOOR_Y, "sill": sill,
			"broken": false, "tempered": index == 2})
	var glass := GlassPanes.new()
	glass.setup(specs)
	add_child(glass)
	await get_tree().physics_frame
	var body: StaticBody3D = glass.get_node("Glass")
	var eye_y: float = FLOOR_Y + 1.6
	# одна пуля
	var c0: Vector3 = (specs[0].xf as Transform3D).origin
	_camera.look_at_from_position(c0 + Vector3(0.35, eye_y - c0.y, 1.7), c0 + Vector3(0.0, 0.1, 0.0), Vector3.UP)
	await get_tree().create_timer(0.3).timeout
	_glass_shot(glass, body, 0, c0 + Vector3(0.12, 0.25, 0.0), 30.0)
	await get_tree().create_timer(0.3).timeout
	_save("impact_glass_hit.png")
	# три пули — трещины второй и третьей упираются в первую
	var c1: Vector3 = (specs[1].xf as Transform3D).origin
	_camera.look_at_from_position(c1 + Vector3(-0.3, eye_y - c1.y, 1.8), c1 + Vector3(0.0, 0.1, 0.0), Vector3.UP)
	for offset: Vector3 in [Vector3(-0.25, 0.35, 0.0), Vector3(0.2, 0.05, 0.0), Vector3(-0.05, -0.45, 0.0)]:
		_glass_shot(glass, body, 1, c1 + offset, 12.0)
		await get_tree().create_timer(0.25).timeout
	await get_tree().create_timer(0.3).timeout
	_save("impact_glass_cracks.png")
	# закалённое: сетка кубиков, осыпается волной
	var c2: Vector3 = (specs[2].xf as Transform3D).origin
	_camera.look_at_from_position(c2 + Vector3(0.6, eye_y - c2.y, 2.2), c2 + Vector3(0.0, -0.2, 0.0), Vector3.UP)
	await get_tree().create_timer(0.3).timeout
	await _capture(_glass_shot.bind(glass, body, 2, c2 + Vector3(-0.15, 0.3, 0.0), 30.0), 0.08, "impact_glass_crazed.png")
	await _until_broken(glass, 2)
	await _wait_frames_for(0.15)
	_save("impact_glass_tempered_fall.png")
	await get_tree().create_timer(2.0).timeout
	_save("impact_glass_tempered_after.png")
	# ослабленное: трещины ползут, потом рассыпается на куски
	var c3: Vector3 = (specs[3].xf as Transform3D).origin
	_camera.look_at_from_position(c3 + Vector3(-0.7, eye_y - c3.y, 2.3), c3 + Vector3(0.1, -0.25, 0.0), Vector3.UP)
	await get_tree().create_timer(0.3).timeout
	_glass_shot(glass, body, 3, c3 + Vector3(0.15, 0.2, 0.0), 25.0)
	await get_tree().create_timer(0.15).timeout
	_glass_shot(glass, body, 3, c3 + Vector3(-0.25, -0.3, 0.0), 25.0)
	await get_tree().create_timer(0.9).timeout
	_save("impact_glass_creep.png")
	await _until_broken(glass, 3)
	await _wait_frames_for(0.12)
	_save("impact_glass_shatter.png")
	await _wait_frames_for(0.35)
	_save("impact_glass_fall.png")
	await get_tree().create_timer(2.5).timeout
	_save("impact_glass_after.png")
	_camera.look_at_from_position(base + Vector3(0.0, eye_y + 0.4, 5.5), base + Vector3(0.0, 0.6, 0.0), Vector3.UP)
	await get_tree().create_timer(0.3).timeout
	_save("impact_glass_row.png")


## Взрыв гранаты на полу: огненный шар, клубы дыма (листы кадров) расползаются и тают.
func _boom() -> void:
	var at: Vector3 = Vector3(-8.0, FLOOR_Y, -6.0)
	_camera.look_at_from_position(at + Vector3(0.0, 2.2, 7.5), at + Vector3(0.0, 1.0, 0.0), Vector3.UP)
	await get_tree().create_timer(0.3).timeout
	await _capture(ImpactFx.explosion.bind(at), 0.35, "impact_boom_fire.png")
	await _wait_frames_for(0.9)
	_save("impact_boom_smoke.png")
	await _wait_frames_for(1.6)
	_save("impact_boom_late.png")


func _glass_shot(glass: GlassPanes, body: StaticBody3D, index: int, at: Vector3, damage: float) -> void:
	glass.bullet(index, damage, at, Vector3.FORWARD)
	ImpactFx.spawn_hit({"position": at, "normal": Vector3.BACK, "collider": body, "shape": index}, Vector3.FORWARD)


func _until_broken(glass: GlassPanes, index: int) -> void:
	var start: int = Time.get_ticks_msec()
	while not bool(glass.panes[index].broken) and Time.get_ticks_msec() - start < 6000:
		await get_tree().process_frame


func _wait_frames_for(seconds: float) -> void:
	var start: int = Time.get_ticks_usec()
	while float(Time.get_ticks_usec() - start) / 1000000.0 < seconds:
		await get_tree().process_frame


## Выстрел лучом, как у оружия: попадание туда, куда смотрит ствол (со своей нормалью).
func _shoot(from: Vector3, to: Vector3, fallback: StaticBody3D) -> void:
	var dir: Vector3 = (to - from).normalized()
	var query := PhysicsRayQueryParameters3D.create(from, to + dir * 0.5, Hitscan.LAYER_WORLD)
	var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(query)
	if hit.is_empty():
		hit = {"position": to, "normal": Vector3.UP, "collider": fallback}
	ImpactFx.spawn_hit(hit, dir)


func _world() -> void:
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.055, 0.06, 0.07)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(0.42, 0.48, 0.58)
	environment.ambient_light_energy = 0.65
	environment.tonemap_mode = Environment.TONE_MAPPER_AGX
	if OS.get_environment("IMPACT_GLOW") == "1":
		environment.glow_enabled = true
		environment.glow_intensity = 0.8
		environment.glow_bloom = 0.1
		environment.glow_hdr_threshold = 1.0
	var world_environment := WorldEnvironment.new()
	world_environment.environment = environment
	add_child(world_environment)
	var light := DirectionalLight3D.new()
	light.light_color = Color(1.0, 0.82, 0.65)
	light.light_energy = 1.6
	light.rotation_degrees = Vector3(-32, -28, 0)
	light.shadow_enabled = true
	add_child(light)
	_camera = Camera3D.new()
	_camera.name = "Camera"
	_camera.fov = 46.0
	add_child(_camera)
	_camera.look_at_from_position(Vector3(0, 2.65, 10.5), Vector3(0, 2.65, 0), Vector3.UP)
	# пол под стенами и рядом грунтов — искры и куски падают на него
	_box("floor", Vector3(15.0, FLOOR_Y - 0.1, 0.0), Vector3(60.0, 0.2, 24.0), "concrete")
	var trample := GrassTrample.new()
	trample.name = "GrassTrample"
	add_child(trample)


func _grounds() -> Dictionary:
	var bodies: Dictionary = {}
	for index: int in range(GROUNDS.size()):
		var kind: String = GROUNDS[index]
		var center: Vector3 = _ground_position(index)
		bodies[kind] = _box(kind, center + Vector3(0.0, -0.1, 0.0), Vector3(1.9, 0.2, 1.9), kind)
		_label(kind, center + Vector3(0.0, -0.7, -1.1))
		if kind == "grass":
			_lawn(center)
	return bodies


## Кочки травы, как у DistrictGrass: те же куртины GrassBlades и шейдер, мнутся по GrassTrample.
func _lawn(center: Vector3) -> void:
	var cfg: Dictionary = Balance.GRASS
	var patch: float = float(cfg.patch)
	var material := ShaderMaterial.new()
	material.shader = preload("res://src/world/grass_blades.gdshader")
	var noise := NoiseTexture2D.new()
	noise.seamless = true
	noise.noise = FastNoiseLite.new()
	material.set_shader_parameter("wind_noise", noise)
	material.set_shader_parameter("dryness", 0.3)
	material.set_shader_parameter("fade_start", 80.0)
	material.set_shader_parameter("fade_end", 90.0)
	var steps: int = int(floor(1.8 / patch))
	for iz: int in range(steps):
		for ix: int in range(steps):
			var mesh := MeshInstance3D.new()
			mesh.mesh = GrassBlades.patch_mesh(4021 + ix * 31 + iz * 7, int(cfg.blades_near), int(cfg.segments_near), patch, 1.0, cfg.height, float(cfg.thatch))
			mesh.material_override = material
			add_child(mesh)
			mesh.global_position = center + Vector3((float(ix) - float(steps - 1) * 0.5) * patch, 0.0, (float(iz) - float(steps - 1) * 0.5) * patch)


func _ground_position(index: int) -> Vector3:
	return GROUND_AT + Vector3((float(index) - 1.5) * 2.2, FLOOR_Y + 0.2, 0.0)


func _cell_position(index: int) -> Vector3:
	var column := index % 3
	var row := index / 3
	return Vector3((column - 1) * 2.05, 4.72 - row * 2.05, 0)


func _panel(kind: String, pos: Vector3) -> StaticBody3D:
	var body: StaticBody3D = _box(kind, pos, Vector3(1.55, 1.55, 0.12), kind)
	_label(kind, pos)
	return body


func _box(kind: String, pos: Vector3, size: Vector3, surface: String) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.name = kind.capitalize()
	body.set_meta("surface", surface)
	body.position = pos
	var shape := BoxShape3D.new()
	shape.size = size
	var collision := CollisionShape3D.new()
	collision.shape = shape
	body.add_child(collision)
	var box := BoxMesh.new()
	box.size = size
	var mesh := MeshInstance3D.new()
	mesh.mesh = box
	var material := StandardMaterial3D.new()
	material.albedo_color = COLORS[kind]
	material.roughness = 0.72 if kind != "metal" else 0.34
	material.metallic = 0.0 if kind != "metal" else 0.65
	if kind == "mud":
		material.roughness = 0.35
	mesh.material_override = material
	body.add_child(mesh)
	add_child(body)
	return body


func _label(text: String, pos: Vector3) -> void:
	var label := Label3D.new()
	label.text = text.to_upper()
	label.font_size = 34
	label.outline_size = 8
	label.position = pos + Vector3(0, 0.98, 0.12)
	add_child(label)


func _save(file_name: String) -> void:
	var path := ProjectSettings.globalize_path("res://docs/screens/%s" % file_name)
	get_viewport().get_texture().get_image().save_png(path)


func _count_decals() -> int:
	var count := 0
	for child: Node in get_children():
		if child is Decal:
			count += 1
	return count
