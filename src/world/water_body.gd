class_name WaterBody
extends MeshInstance3D
## Гладь воды (болото и ручей в овраге зоны 1): по ней известна глубина над любой точкой — для ходьбы
## вброд (скорость, бег, стойка), шагов по воде и брызг. Гладь — плоскость PlaneMesh узла (поворот только
## вокруг вертикали); дно — рельеф под ней, поэтому кочки и острова сухие сами собой.
## Владелец 2026-10-18: болото переходят вброд по пояс; физика воды без тяжёлых эффектов.

static var _bodies: Array[WaterBody] = []

## Брызги и круг на воде у ног — общие ресурсы на всю игру.
static var _splash_mesh: QuadMesh
static var _splash_mat: StandardMaterial3D
static var _ring_mesh: QuadMesh
static var _ring_shader: Shader
## Сила дождя на глади сейчас (set_rain).
static var _rain: float = 0.0


func _enter_tree() -> void:
	_bodies.append(self)
	_apply_rain(self)


func _exit_tree() -> void:
	_bodies.erase(self)


## Дождь на глади (круги от капель, шейдер district_water): сила 0..1 от RaidWeather — материалы
## воды трогаются, только когда она меняется.
static func set_rain(k: float) -> void:
	k = snappedf(k, 0.01)
	if is_equal_approx(k, _rain):
		return
	_rain = k
	for b: WaterBody in _bodies:
		_apply_rain(b)


static func _apply_rain(b: WaterBody) -> void:
	var m: ShaderMaterial = b.mesh.surface_get_material(0) as ShaderMaterial if b.mesh else null
	if m:
		m.set_shader_parameter("rain", _rain)


## Высота глади над точкой или NAN, если воды над ней нет.
static func surface_at(pos: Vector3) -> float:
	var best: float = NAN
	for body: WaterBody in _bodies:
		var plane := body.mesh as PlaneMesh
		if plane == null or not body.is_inside_tree():
			continue
		var local: Vector3 = body.global_transform.affine_inverse() * pos
		if absf(local.x) > plane.size.x * 0.5 or absf(local.z) > plane.size.y * 0.5:
			continue
		var y: float = body.global_position.y
		if is_nan(best) or y > best:
			best = y
	return best


## Глубина воды над точкой (обычно — над ступнями), м; сухо — 0.
static func depth_at(pos: Vector3) -> float:
	var y: float = surface_at(pos)
	return 0.0 if is_nan(y) else maxf(0.0, y - pos.y)


## Множитель по глубине из таблицы Balance.WATER: [по щиколотку, по колено, по пояс], между — плавно.
static func depth_k(depth: float, table: Array) -> float:
	var w: Dictionary = Balance.WATER
	var ankle: float = float(w.ankle)
	var knee: float = float(w.knee)
	var waist: float = float(w.waist)
	if depth <= ankle:
		return float(table[0])
	if depth <= knee:
		return lerpf(float(table[0]), float(table[1]), (depth - ankle) / (knee - ankle))
	return lerpf(float(table[1]), float(table[2]), clampf((depth - knee) / (waist - knee), 0.0, 1.0))


## Брызги у ног и расходящийся круг на глади. Только рядом с камерой — дальше их не видно.
static func splash(tree: SceneTree, pos: Vector3, strength: float) -> void:
	var surface: float = surface_at(pos)
	if is_nan(surface) or tree == null or tree.current_scene == null:
		return
	var cam: Camera3D = tree.root.get_viewport().get_camera_3d()
	if cam and cam.global_position.distance_to(pos) > float(Balance.WATER.fx_distance):
		return
	_ensure_resources()
	var at := Vector3(pos.x, surface + 0.02, pos.z)
	var p := CPUParticles3D.new()
	p.one_shot = true
	p.emitting = true
	p.amount = int(lerpf(6.0, 16.0, clampf(strength, 0.0, 1.0)))
	p.lifetime = 0.55
	p.explosiveness = 0.9
	p.mesh = _splash_mesh
	p.material_override = _splash_mat
	p.direction = Vector3.UP
	p.spread = 38.0
	p.initial_velocity_min = 1.2 + 1.2 * strength
	p.initial_velocity_max = 2.2 + 1.6 * strength
	p.gravity = Vector3(0, -9.8, 0)
	p.scale_amount_min = 0.5
	p.scale_amount_max = 1.2
	p.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	p.emission_sphere_radius = 0.18
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var ring := MeshInstance3D.new()
	ring.mesh = _ring_mesh
	ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var mat := ShaderMaterial.new()
	mat.shader = _ring_shader
	mat.set_shader_parameter("t", 0.0)
	ring.material_override = mat
	tree.current_scene.add_child(p)
	tree.current_scene.add_child(ring)
	p.global_position = at
	ring.global_position = at
	ring.rotation_degrees = Vector3(-90, 0, 0)
	ring.create_tween().tween_property(mat, "shader_parameter/t", 1.0, 0.9)
	var t := tree.create_timer(1.2)
	t.timeout.connect(func() -> void:
		if is_instance_valid(p):
			p.queue_free()
		if is_instance_valid(ring):
			ring.queue_free())


static func _ensure_resources() -> void:
	if _splash_mesh:
		return
	_splash_mesh = QuadMesh.new()
	_splash_mesh.size = Vector2(0.07, 0.07)
	_splash_mat = StandardMaterial3D.new()
	_splash_mat.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	_splash_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_splash_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_splash_mat.albedo_color = Color(0.7, 0.72, 0.66, 0.55)
	_ring_mesh = QuadMesh.new()
	_ring_mesh.size = Vector2(2.6, 2.6)
	_ring_shader = Shader.new()
	# круг расходится за ~0,9 с и тает; без текстур — дёшево
	_ring_shader.code = """shader_type spatial;
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never, shadows_disabled;
uniform float t = 0.0;
void fragment() {
	float r = length(UV - vec2(0.5)) * 2.0;
	float ring = smoothstep(0.07, 0.0, abs(r - mix(0.15, 0.95, t)));
	ALBEDO = vec3(0.78, 0.8, 0.76);
	ALPHA = ring * (1.0 - t) * 0.45;
}
"""
