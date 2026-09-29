class_name ImpactBurst
extends Node3D
## Один короткий выброс: крошка/щепки, пыль, отдельно горячие частицы металла.
## Частицы — только изображение: не наносят урон и не создают шум для ИИ.

@onready var debris: CPUParticles3D = $Debris
@onready var dust: CPUParticles3D = $Dust
@onready var sparks: CPUParticles3D = $Sparks

static var _meshes: Dictionary[String, Mesh] = {}
static var _materials: Dictionary[String, StandardMaterial3D] = {}
static var _dust_texture: Texture2D


func setup(kind: String, normal: Vector3, direction: Vector3, seed_value: int) -> void:
	var spec: Dictionary = Balance.IMPACT_SURFACES.get(kind, Balance.IMPACT_SURFACES.concrete)
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = seed_value
	var reflected: Vector3 = direction.bounce(normal).normalized()
	var outward: Vector3 = (normal + reflected * 0.45).normalized()
	if kind == "flesh":
		outward = direction
	_emit(debris, spec, outward, rng)
	var lifetime: float = float(spec.life)
	if int(spec.dust) > 0:
		_emit_dust(spec, normal, rng)
		lifetime = maxf(lifetime, float(spec.dust_life))
	if kind == "metal":
		_emit_sparks(normal, reflected, rng)
		lifetime = maxf(lifetime, float(Balance.IMPACT_SPARKS.life))
	get_tree().create_timer(lifetime + Balance.IMPACT_CLEANUP_MARGIN).timeout.connect(queue_free)


func _base(particles: CPUParticles3D, amount: int, life: float, direction: Vector3) -> void:
	particles.emitting = false
	particles.one_shot = true
	particles.explosiveness = 1.0
	particles.local_coords = false
	particles.amount = amount
	particles.lifetime = life
	particles.direction = direction
	particles.gravity = Vector3.DOWN * Balance.IMPACT_GRAVITY
	particles.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF


func _emit(particles: CPUParticles3D, spec: Dictionary, direction: Vector3, rng: RandomNumberGenerator) -> void:
	var count: Vector2i = spec.count
	_base(particles, rng.randi_range(count.x, count.y), float(spec.life), direction)
	var speed: Vector2 = spec.speed
	var size_range: Vector2 = spec.size
	particles.initial_velocity_min = speed.x
	particles.initial_velocity_max = speed.y
	particles.scale_amount_min = size_range.x
	particles.scale_amount_max = size_range.y
	particles.spread = float(spec.spread)
	particles.damping_min = float(spec.drag)
	particles.damping_max = float(spec.drag) * 1.4
	particles.angular_velocity_min = -Balance.IMPACT_SPIN
	particles.angular_velocity_max = Balance.IMPACT_SPIN
	particles.angle_min = -180.0
	particles.angle_max = 180.0
	particles.color = spec.color
	particles.color_ramp = _fade()
	var variation: Gradient = Gradient.new()
	variation.set_color(0, Color(0.68, 0.68, 0.68))
	variation.set_color(1, Color.WHITE)
	particles.color_initial_ramp = variation
	particles.mesh = _mesh(String(spec.mesh))
	particles.material_override = _material(String(spec.mesh))
	particles.restart()
	particles.emitting = true


func _emit_dust(spec: Dictionary, normal: Vector3, _rng: RandomNumberGenerator) -> void:
	var cfg: Dictionary = Balance.IMPACT_DUST
	_base(dust, int(spec.dust), float(spec.dust_life), normal)
	var speed: Vector2 = cfg.speed
	var size_range: Vector2 = spec.dust_size
	var drag: Vector2 = cfg.drag
	dust.initial_velocity_min = speed.x
	dust.initial_velocity_max = speed.y
	dust.scale_amount_min = size_range.x
	dust.scale_amount_max = size_range.y
	dust.damping_min = drag.x
	dust.damping_max = drag.y
	dust.spread = float(cfg.spread)
	dust.gravity = Vector3(0, float(cfg.gravity), 0)
	dust.angle_min = -180.0
	dust.angle_max = 180.0
	dust.color = Color(spec.color, float(spec.opacity))
	dust.color_ramp = _fade(0.0, 0.12)
	var grow: Curve = Curve.new()
	grow.add_point(Vector2(0, 0.25))
	grow.add_point(Vector2(1, 1.0))
	dust.scale_amount_curve = grow
	dust.mesh = _mesh("dust")
	dust.material_override = _material("dust")
	dust.restart()
	dust.emitting = true


func _emit_sparks(normal: Vector3, reflected: Vector3, rng: RandomNumberGenerator) -> void:
	var cfg: Dictionary = Balance.IMPACT_SPARKS
	var count: Vector2i = cfg.count
	_base(sparks, rng.randi_range(count.x, count.y), float(cfg.life), (reflected + normal * 0.2).normalized())
	var speed: Vector2 = cfg.speed
	var size_range: Vector2 = cfg.size
	sparks.spread = float(cfg.spread)
	sparks.initial_velocity_min = speed.x
	sparks.initial_velocity_max = speed.y
	sparks.scale_amount_min = size_range.x
	sparks.scale_amount_max = size_range.y
	sparks.particle_flag_align_y = true
	var cooling: Gradient = Gradient.new()
	cooling.offsets = PackedFloat32Array([0.0, 0.25, 0.7, 1.0])
	cooling.colors = PackedColorArray([Color(1, 0.86, 0.53), Color(1, 0.51, 0.13), Color(0.46, 0.1, 0.01, 0.5), Color(0.08, 0.01, 0, 0)])
	sparks.color_ramp = cooling
	sparks.mesh = _mesh("spark")
	sparks.material_override = _material("spark")
	sparks.restart()
	sparks.emitting = true


static func _fade(start_alpha: float = 1.0, peak_at: float = 0.65) -> Gradient:
	var fade: Gradient = Gradient.new()
	fade.offsets = PackedFloat32Array([0.0, peak_at, 1.0])
	fade.colors = PackedColorArray([Color(1, 1, 1, start_alpha), Color.WHITE, Color(1, 1, 1, 0)])
	return fade


static func _material(kind: String) -> StandardMaterial3D:
	if _materials.has(kind):
		return _materials[kind]
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.vertex_color_use_as_albedo = true
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	material.roughness = 0.88
	if kind == "spark":
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		material.emission_enabled = true
		material.emission = Color.WHITE
		material.emission_operator = BaseMaterial3D.EMISSION_OP_MULTIPLY
		material.emission_energy_multiplier = float(Balance.IMPACT_SPARKS.emission)
	elif kind == "dust":
		material.albedo_texture = _cloud()
		material.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
		material.billboard_keep_scale = true
		material.diffuse_mode = BaseMaterial3D.DIFFUSE_BURLEY
	elif kind == "shard":
		material.roughness = 0.12
		material.metallic_specular = 0.85
	_materials[kind] = material
	return material


## Неровный освещаемый тетраэдр: у сколов есть грани, а не одинаковые кубики.
static func _mesh(kind: String) -> Mesh:
	if _meshes.has(kind):
		return _meshes[kind]
	if kind == "dust":
		var quad: QuadMesh = QuadMesh.new()
		quad.size = Vector2.ONE
		_meshes[kind] = quad
		return quad
	if kind == "spark" or kind == "fiber":
		var streak: BoxMesh = BoxMesh.new()
		streak.size = Vector3(0.035, 1.0, 0.035) if kind == "spark" else Vector3(0.07, 1.0, 0.07)
		_meshes[kind] = streak
		return streak
	if kind == "drop":
		var drop: SphereMesh = SphereMesh.new()
		drop.radius = 0.35
		drop.height = 1.0
		drop.radial_segments = 6
		drop.rings = 4
		_meshes[kind] = drop
		return drop
	var scale_vec: Vector3 = Vector3.ONE
	if kind in ["flake", "shard", "paper"]:
		scale_vec = Vector3(1.0, 0.7, 0.08)
	elif kind == "splinter":
		scale_vec = Vector3(0.14, 1.0, 0.12)
	var vertices: Array[Vector3] = [Vector3(-0.48, -0.4, -0.22), Vector3(0.52, -0.25, -0.12), Vector3(-0.15, 0.6, -0.15), Vector3(0.02, -0.05, 0.55)]
	var faces: Array[Vector3i] = [Vector3i(0, 2, 1), Vector3i(0, 1, 3), Vector3i(1, 2, 3), Vector3i(2, 0, 3)]
	var surface: SurfaceTool = SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	for face: Vector3i in faces:
		var a: Vector3 = vertices[face.x] * scale_vec
		var b: Vector3 = vertices[face.y] * scale_vec
		var c: Vector3 = vertices[face.z] * scale_vec
		surface.set_normal((b - a).cross(c - a).normalized())
		surface.add_vertex(a)
		surface.add_vertex(b)
		surface.add_vertex(c)
	var result: ArrayMesh = surface.commit()
	_meshes[kind] = result
	return result


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
