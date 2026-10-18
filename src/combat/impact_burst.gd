class_name ImpactBurst
extends Node3D
## Одно попадание слоями: вспышка (металл) → веер мелкого материала полосами → искры → куски с весом
## (отскакивают от поверхности и пола под точкой) → мелочь (травинки, крошка) → медленное облако.
## Числа слоёв — Balance.IMPACT_SURFACES, движение частиц — impact_particles.gdshader.
## Частицы — только изображение: не наносят урон и не создают шум для ИИ.

const PARTICLES_SHADER: Shader = preload("res://src/combat/impact_particles.gdshader")
const SPARK_SHADER: Shader = preload("res://src/combat/impact_spark.gdshader")
## Лоупольные куски из Blender (tools/build_impact_debris.py): объекты <вид>_<N>.
const DEBRIS_PATH := "res://assets/models/props/impact_debris/impact_debris.glb"
const SPRAY_SHADER: Shader = preload("res://src/combat/impact_spray.gdshader")
const FLASH_SHADER: Shader = preload("res://src/combat/impact_flash.gdshader")
## Плоскость «нигде»: пол не нашли.
const NO_PLANE := Vector4(0.0, 1.0, 0.0, -100000.0)
const NO_RADIUS: float = 100000.0
## Слои кусков и веера, в порядке появления.
const LAYERS: Array[String] = ["spray", "debris", "bits"]

@onready var debris: GPUParticles3D = $Debris
@onready var bits: GPUParticles3D = $Bits
@onready var spray: GPUParticles3D = $Spray
@onready var sparks: GPUParticles3D = $Sparks
@onready var dust: CPUParticles3D = $Dust
@onready var flash: MeshInstance3D = $Flash

## Куда полетел каждый слой (для проверок): слой → ось конуса.
var aims: Dictionary[String, Vector3] = {}

static var _meshes: Dictionary[String, Mesh] = {}
static var _materials: Dictionary[String, Material] = {}
static var _ramps: Dictionary[String, Texture2D] = {}
static var _dust_texture: Texture2D
static var _grain_texture: Texture2D
static var _lights: int = 0
## вид куска → варианты сеток из DEBRIS_PATH (пусто — процедурные _mesh)
static var _debris: Dictionary = {}
static var _debris_loaded: bool = false


## floor_plane — пол под точкой (нормаль и высота вдоль неё, NO_PLANE — нет); surface_radius — дальше
## от точки удара поверхности, в которую попали, нет (маленькая верхняя грань); far — далеко от камеры.
func setup(kind: String, normal: Vector3, direction: Vector3, seed_value: int, floor_plane: Vector4 = NO_PLANE, surface_radius: float = NO_RADIUS, far: bool = false) -> void:
	var spec: Dictionary = Balance.IMPACT_SURFACES.get(kind, Balance.IMPACT_SURFACES.concrete)
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = seed_value
	var reflected: Vector3 = direction.bounce(normal).normalized()
	# плоскость поверхности — в самой точке удара (узел вынесен от неё на IMPACT_OFFSET)
	var planes: Dictionary = {
		"a": Vector4(normal.x, normal.y, normal.z, normal.dot(global_position) - Balance.IMPACT_OFFSET),
		"radius": surface_radius,
		"b": floor_plane,
	}
	if kind == "flesh":
		planes = {"a": NO_PLANE, "radius": NO_RADIUS, "b": NO_PLANE}
	var lifetime: float = 0.0
	for layer: String in LAYERS:
		if not spec.has(layer) or (far and layer == "bits"):
			continue
		var cfg: Dictionary = spec[layer]
		var aim: Vector3 = direction if kind == "flesh" else _aim(cfg.get("aim", Vector2(1.0, 0.45)), normal, reflected)
		var count: int = _count(cfg.count, rng, far)
		lifetime = maxf(lifetime, _emit(_layer_node(layer), layer, cfg, count, aim, planes, rng.randi()))
	if spec.has("sparks") and rng.randf() < float(spec.sparks.get("chance", 1.0)):
		lifetime = maxf(lifetime, _emit_sparks(spec.sparks.count, normal, reflected, planes, rng, far))
	if spec.has("dust"):
		lifetime = maxf(lifetime, _emit_dust(spec.dust, normal))
	if spec.has("flash"):
		lifetime = maxf(lifetime, _flash(spec.flash, far))
	get_tree().create_timer(lifetime + Balance.IMPACT_CLEANUP_MARGIN).timeout.connect(queue_free)


## Общие сетки, материалы и текстуры всех слоёв — заранее (ImpactFx при запуске): первое попадание
## в новую поверхность иначе стоит десятки миллисекунд кадра.
static func prepare() -> void:
	for layer: String in ["debris", "bits", "spray", "sparks"]:
		_ramp(layer)
	for look: String in ["sparks", "spray", "flash", "dust"]:
		_material(look)
	_mesh("streak")
	_mesh("flash")
	_mesh("dust")
	_debris_shapes()
	for kind: String in Balance.IMPACT_SURFACES:
		var spec: Dictionary = Balance.IMPACT_SURFACES[kind]
		for layer: String in ["debris", "bits"]:
			if spec.has(layer):
				_mesh(String(spec[layer].mesh))
				_material(String(spec[layer].mesh))


func _layer_node(layer: String) -> GPUParticles3D:
	match layer:
		"spray":
			return spray
		"bits":
			return bits
	return debris


func _aim(weights: Vector2, normal: Vector3, reflected: Vector3) -> Vector3:
	var aim: Vector3 = normal * weights.x + reflected * weights.y
	return aim.normalized() if aim.length_squared() > 0.0001 else normal


func _count(range_value: Vector2i, rng: RandomNumberGenerator, far: bool) -> int:
	var count: int = rng.randi_range(range_value.x, range_value.y)
	return int(ceil(count * 0.5)) if far else count


## Слой на видеокарте: свой материал движения (направление, плоскости — у каждого попадания свои).
func _emit(particles: GPUParticles3D, layer: String, cfg: Dictionary, count: int, aim: Vector3, planes: Dictionary, variant: int = 0) -> float:
	if count <= 0:
		return 0.0
	var life: Vector2 = cfg.life
	var color: Color = cfg.color
	var streak: bool = layer == "spray" or layer == "sparks"
	var material: ShaderMaterial = ShaderMaterial.new()
	material.shader = PARTICLES_SHADER
	material.set_shader_parameter("origin", global_position)
	material.set_shader_parameter("direction", aim)
	material.set_shader_parameter("spread", float(cfg.spread))
	material.set_shader_parameter("speed", cfg.speed)
	material.set_shader_parameter("speed_bias", float(cfg.get("bias", 1.6)))
	material.set_shader_parameter("life", life)
	material.set_shader_parameter("size", cfg.size)
	material.set_shader_parameter("gravity", Balance.IMPACT_GRAVITY * float(cfg.get("gravity", 1.0)))
	material.set_shader_parameter("drag", float(cfg.drag))
	material.set_shader_parameter("spin", 0.0 if streak else deg_to_rad(Balance.IMPACT_SPIN))
	material.set_shader_parameter("flutter", float(cfg.get("flutter", 0.0)))
	material.set_shader_parameter("stretch", float(cfg.get("stretch", 0.0)))
	material.set_shader_parameter("stretch_max", float(cfg.get("stretch_max", 0.4)))
	material.set_shader_parameter("size_end", float(cfg.get("size_end", 2.0 if layer == "spray" else 1.0)))
	material.set_shader_parameter("bounce", float(cfg.get("bounce", 0.0)))
	material.set_shader_parameter("friction", float(cfg.get("friction", 0.6)))
	material.set_shader_parameter("plane_a", planes.a)
	material.set_shader_parameter("plane_a_radius", float(planes.radius))
	material.set_shader_parameter("plane_b", planes.b)
	material.set_shader_parameter("color_ramp", _ramp(layer))
	material.set_shader_parameter("tint", color)
	material.set_shader_parameter("tint_alt", cfg.get("alt", color))
	material.set_shader_parameter("alt_share", float(cfg.get("alt_share", 0.0)))
	material.set_shader_parameter("shade_var", 0.0 if streak else 0.32)
	material.set_shader_parameter("shape_var", 0.0 if streak else Balance.IMPACT_SHAPE_VAR)
	particles.process_material = material
	particles.amount = count
	particles.lifetime = life.y
	particles.one_shot = true
	particles.explosiveness = 1.0
	particles.local_coords = false
	particles.fixed_fps = 0
	particles.visibility_aabb = AABB(Vector3(-6.0, -6.0, -6.0), Vector3(12.0, 12.0, 12.0))
	particles.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var look: String = layer if streak else String(cfg.mesh)
	particles.draw_pass_1 = _mesh("streak") if streak else _shape(look, variant)
	particles.material_override = _material(look)
	particles.restart()
	particles.emitting = true
	aims[layer] = aim
	return life.y


func _emit_sparks(count_range: Vector2i, normal: Vector3, reflected: Vector3, planes: Dictionary, rng: RandomNumberGenerator, far: bool) -> float:
	var cfg: Dictionary = Balance.IMPACT_SPARKS
	var layer: Dictionary = {
		"spread": cfg.spread, "speed": cfg.speed, "life": cfg.life, "size": cfg.width, "drag": cfg.drag,
		"bounce": cfg.bounce, "friction": cfg.friction, "stretch": cfg.stretch, "stretch_max": cfg.stretch_max,
		"color": Color.WHITE, "size_end": 0.6, "bias": 1.3,
	}
	return _emit(sparks, "sparks", layer, _count(count_range, rng, far), _aim(cfg.aim, normal, reflected), planes)


func _emit_dust(cfg: Dictionary, normal: Vector3) -> float:
	var common: Dictionary = Balance.IMPACT_DUST
	var life: Vector2 = cfg.life
	dust.emitting = false
	dust.one_shot = true
	dust.explosiveness = 1.0
	dust.local_coords = false
	dust.amount = int(cfg.count)
	dust.lifetime = life.y
	dust.lifetime_randomness = clampf(1.0 - life.x / life.y, 0.0, 1.0)
	dust.direction = normal
	dust.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var speed: Vector2 = common.speed
	var size_range: Vector2 = cfg.size
	var drag: Vector2 = common.drag
	dust.initial_velocity_min = speed.x
	dust.initial_velocity_max = speed.y
	dust.scale_amount_min = size_range.x
	dust.scale_amount_max = size_range.y
	dust.damping_min = drag.x
	dust.damping_max = drag.y
	dust.spread = float(common.spread)
	dust.gravity = Vector3(0.0, float(cfg.get("rise", 0.0)), 0.0)
	dust.angle_min = -180.0
	dust.angle_max = 180.0
	dust.color = Color(cfg.color as Color, float(cfg.opacity))
	dust.color_ramp = _fade(0.0, 0.12)
	var grow: Curve = Curve.new()
	grow.add_point(Vector2(0, 0.25))
	grow.add_point(Vector2(1, 1.0))
	dust.scale_amount_curve = grow
	dust.mesh = _mesh("dust")
	dust.material_override = _material("dust")
	dust.restart()
	dust.emitting = true
	return life.y


## Вспышка на пару кадров и свет на миг (не больше IMPACT_FLASH.light_max сразу, вдали — без света).
func _flash(cfg: Dictionary, far: bool) -> float:
	var common: Dictionary = Balance.IMPACT_FLASH
	var life: float = float(common.life)
	var size: float = float(cfg.size)
	flash.mesh = _mesh("flash")
	flash.material_override = _material("flash")
	flash.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	flash.scale = Vector3.ONE * size * 0.6
	flash.set_instance_shader_parameter("fade", 1.0)
	flash.visible = true
	var tween: Tween = create_tween().set_parallel()
	tween.tween_property(flash, "scale", Vector3.ONE * size, life * 0.5)
	tween.tween_method(_set_flash_fade, 1.0, 0.0, life)
	tween.chain().tween_callback(flash.hide)
	if bool(cfg.get("light", false)) and not far and _lights < int(common.light_max):
		var light: OmniLight3D = OmniLight3D.new()
		light.name = "FlashLight"
		light.light_color = common.color
		light.light_energy = float(common.light_energy)
		light.omni_range = float(common.light_range)
		light.shadow_enabled = false
		ImpactBurst._lights += 1
		light.tree_exiting.connect(_light_gone)
		add_child(light)
		var fade: Tween = light.create_tween()
		fade.tween_property(light, "light_energy", 0.0, life * 1.3)
		fade.tween_callback(light.queue_free)
	return life * 1.3


func _set_flash_fade(value: float) -> void:
	flash.set_instance_shader_parameter("fade", value)


func _light_gone() -> void:
	ImpactBurst._lights = maxi(0, ImpactBurst._lights - 1)


static func _fade(start_alpha: float = 1.0, peak_at: float = 0.65) -> Gradient:
	var fade: Gradient = Gradient.new()
	fade.offsets = PackedFloat32Array([0.0, peak_at, 1.0])
	fade.colors = PackedColorArray([Color(1, 1, 1, start_alpha), Color.WHITE, Color(1, 1, 1, 0)])
	return fade


## Цвет и прозрачность по доле жизни: искры остывают, веер тает, куски не меняются (уходят в точку).
static func _ramp(layer: String) -> Texture2D:
	if _ramps.has(layer):
		return _ramps[layer]
	var gradient: Gradient = Gradient.new()
	if layer == "sparks":
		gradient.offsets = PackedFloat32Array([0.0, 0.18, 0.55, 0.85, 1.0])
		gradient.colors = PackedColorArray([Color(1.0, 0.93, 0.72), Color(1.0, 0.68, 0.24), Color(1.0, 0.38, 0.06),
			Color(0.6, 0.12, 0.02, 0.6), Color(0.25, 0.04, 0.0, 0.0)])
	elif layer == "spray":
		gradient.offsets = PackedFloat32Array([0.0, 0.12, 0.5, 1.0])
		gradient.colors = PackedColorArray([Color(1, 1, 1, 0.7), Color(1, 1, 1, 1.0), Color(1, 1, 1, 0.55), Color(1, 1, 1, 0.0)])
	else:
		gradient.offsets = PackedFloat32Array([0.0, 1.0])
		gradient.colors = PackedColorArray([Color.WHITE, Color.WHITE])
	var texture: GradientTexture1D = GradientTexture1D.new()
	texture.gradient = gradient
	texture.width = 64
	_ramps[layer] = texture
	return texture


static func _material(kind: String) -> Material:
	if _materials.has(kind):
		return _materials[kind]
	var result: Material
	if kind == "sparks":
		var spark: ShaderMaterial = ShaderMaterial.new()
		spark.shader = SPARK_SHADER
		spark.set_shader_parameter("energy", float(Balance.IMPACT_SPARKS.energy))
		result = spark
	elif kind == "spray":
		var cloud: ShaderMaterial = ShaderMaterial.new()
		cloud.shader = SPRAY_SHADER
		cloud.set_shader_parameter("mask", _grain())
		result = cloud
	elif kind == "flash":
		var glow: ShaderMaterial = ShaderMaterial.new()
		glow.shader = FLASH_SHADER
		glow.set_shader_parameter("color", Balance.IMPACT_FLASH.color)
		glow.set_shader_parameter("energy", float(Balance.IMPACT_FLASH.energy))
		result = glow
	else:
		var material: StandardMaterial3D = StandardMaterial3D.new()
		material.vertex_color_use_as_albedo = true
		material.cull_mode = BaseMaterial3D.CULL_DISABLED
		material.roughness = 0.88
		match kind:
			"dust":
				material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
				material.albedo_texture = _cloud()
				material.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
				material.billboard_keep_scale = true
				material.diffuse_mode = BaseMaterial3D.DIFFUSE_BURLEY
				# мягкий стык облака с полом и стеной
				material.proximity_fade_enabled = true
				material.proximity_fade_distance = 0.15
			"shard":
				material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
				material.roughness = 0.12
				material.metallic_specular = 0.85
			"drop":
				material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
				material.roughness = 0.3
			"clod":
				material.roughness = 0.96
			"pebble":
				material.roughness = 0.8
			"blade":
				material.roughness = 0.7
				# травинка на просвет зеленее
				material.backlight_enabled = true
				material.backlight = Color(0.22, 0.28, 0.08)
			"flake":
				material.roughness = 0.55
				material.metallic = 0.35
		result = material
	_materials[kind] = result
	return result


## Сетка куска: вариант из Blender, если есть, иначе процедурная.
static func _shape(kind: String, variant: int) -> Mesh:
	var variants: Array = _debris_shapes().get(kind, [])
	if variants.is_empty():
		return _mesh(kind)
	return variants[absi(variant) % variants.size()] as Mesh


## Куски из GLB (tools/build_impact_debris.py): вид → сетки вариантов; нет файла — пусто.
static func _debris_shapes() -> Dictionary:
	if _debris_loaded:
		return _debris
	_debris_loaded = true
	if not ResourceLoader.exists(DEBRIS_PATH):
		return _debris
	var scene: PackedScene = load(DEBRIS_PATH) as PackedScene
	if scene == null:
		return _debris
	var root: Node = scene.instantiate()
	for node: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mesh_node: MeshInstance3D = node as MeshInstance3D
		var kind: String = String(mesh_node.name).rsplit("_", true, 1)[0]
		if not _debris.has(kind):
			_debris[kind] = []
		(_debris[kind] as Array).append(mesh_node.mesh)
	root.free()
	return _debris


static func _mesh(kind: String) -> Mesh:
	if _meshes.has(kind):
		return _meshes[kind]
	var result: Mesh
	match kind:
		"dust", "streak", "flash":
			var quad: QuadMesh = QuadMesh.new()
			quad.size = Vector2.ONE
			result = quad
		"fiber":
			var streak: BoxMesh = BoxMesh.new()
			streak.size = Vector3(0.07, 1.0, 0.07)
			result = streak
		"drop":
			var drop: SphereMesh = SphereMesh.new()
			drop.radius = 0.35
			drop.height = 1.0
			drop.radial_segments = 6
			drop.rings = 4
			result = drop
		"clod", "pebble":
			result = _lump(kind == "pebble")
		"blade":
			result = _blade()
		_:
			result = _tetra(kind)
	_meshes[kind] = result
	return result


## Неровный освещаемый тетраэдр: у сколов есть грани, а не одинаковые кубики.
static func _tetra(kind: String) -> Mesh:
	var scale_vec: Vector3 = Vector3.ONE
	if kind in ["flake", "shard", "paper"]:
		scale_vec = Vector3(1.0, 0.7, 0.08)
	elif kind == "splinter":
		scale_vec = Vector3(0.14, 1.0, 0.12)
	var vertices: Array[Vector3] = [Vector3(-0.48, -0.4, -0.22), Vector3(0.52, -0.25, -0.12), Vector3(-0.15, 0.6, -0.15), Vector3(0.02, -0.05, 0.55)]
	var faces: Array[Vector3i] = [Vector3i(0, 2, 1), Vector3i(0, 1, 3), Vector3i(1, 2, 3), Vector3i(2, 0, 3)]
	var points: Array[Vector3] = []
	for vertex: Vector3 in vertices:
		points.append(vertex * scale_vec)
	return _faceted(points, faces)


## Ком земли или камешек: октаэдр с неровными вершинами (камешек — площе и ровнее).
static func _lump(flat: bool) -> Mesh:
	var squash: float = 0.62 if flat else 0.86
	var points: Array[Vector3] = [
		Vector3(0.5, 0.04, -0.05), Vector3(-0.46, -0.03, 0.06),
		Vector3(0.03, 0.42 * squash, 0.02), Vector3(-0.05, -0.4 * squash, -0.03),
		Vector3(0.06, 0.02, 0.47), Vector3(-0.02, -0.05, -0.44),
	]
	if not flat:
		points[0] += Vector3(0.0, 0.12, 0.08)
		points[4] += Vector3(-0.1, -0.08, 0.0)
	var faces: Array[Vector3i] = [
		Vector3i(0, 2, 4), Vector3i(4, 2, 1), Vector3i(1, 2, 5), Vector3i(5, 2, 0),
		Vector3i(4, 3, 0), Vector3i(1, 3, 4), Vector3i(5, 3, 1), Vector3i(0, 3, 5),
	]
	return _faceted(points, faces)


## Травинка: узкая полоска с изгибом к кончику, видна и с ребра.
static func _blade() -> Mesh:
	var rows: Array[Vector3] = [Vector3(0.06, -0.5, 0.0), Vector3(0.045, 0.0, 0.06), Vector3(0.0, 0.5, 0.18)]
	var points: Array[Vector3] = []
	for row: Vector3 in rows:
		points.append(Vector3(-row.x, row.y, row.z))
		points.append(Vector3(row.x, row.y, row.z + row.x * 0.6))
	var faces: Array[Vector3i] = [Vector3i(0, 1, 2), Vector3i(1, 3, 2), Vector3i(2, 3, 4), Vector3i(3, 5, 4)]
	return _faceted(points, faces)


## Грани с нормалью наружу (от середины куска) и обходом по часовой стрелке снаружи — лицевая
## сторона у Godot; иначе свет считается с изнанки и кусок выходит тёмным.
static func _faceted(points: Array[Vector3], faces: Array[Vector3i]) -> Mesh:
	var middle: Vector3 = Vector3.ZERO
	for point: Vector3 in points:
		middle += point
	middle /= float(points.size())
	var surface: SurfaceTool = SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	for face: Vector3i in faces:
		var a: Vector3 = points[face.x]
		var b: Vector3 = points[face.y]
		var c: Vector3 = points[face.z]
		var normal: Vector3 = (b - a).cross(c - a).normalized()
		if normal.dot((a + b + c) / 3.0 - middle) < 0.0:
			normal = -normal
		if (b - a).cross(c - a).dot(normal) > 0.0:
			var swap: Vector3 = b
			b = c
			c = swap
		surface.set_normal(normal)
		surface.add_vertex(a)
		surface.add_vertex(b)
		surface.add_vertex(c)
	return surface.commit()


## Зерно веера: бесшовный шум (R), без круглого края — форму клуба задаёт шейдер.
static func _grain() -> Texture2D:
	if _grain_texture != null:
		return _grain_texture
	var noise: FastNoiseLite = FastNoiseLite.new()
	noise.seed = 811
	noise.frequency = 0.09
	var image: Image = noise.get_seamless_image(64, 64)
	image.convert(Image.FORMAT_RGBA8)
	image.generate_mipmaps()
	_grain_texture = ImageTexture.create_from_image(image)
	return _grain_texture


## Неповторяющаяся мягкая маска пыли: шум внутри облака и прозрачный край.
static func _cloud() -> Texture2D:
	if _dust_texture != null:
		return _dust_texture
	var noise: FastNoiseLite = FastNoiseLite.new()
	noise.seed = 5179
	noise.frequency = 0.085
	var image: Image = Image.create(64, 64, false, Image.FORMAT_RGBA8)
	for y: int in range(64):
		for x: int in range(64):
			var radius: float = Vector2(x - 31.5, y - 31.5).length() / 31.5
			var cloud: float = clampf(0.65 + noise.get_noise_2d(x, y) * 0.8, 0.0, 1.0)
			var alpha: float = (1.0 - smoothstep(0.12, 0.98, radius)) * cloud
			image.set_pixel(x, y, Color(1, 1, 1, alpha))
	image.generate_mipmaps()
	_dust_texture = ImageTexture.create_from_image(image)
	return _dust_texture
