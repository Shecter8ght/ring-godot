class_name HeliTarget
extends Node3D
## Учебная цель для ПЗРК (стенд tools/osoka_range.tscn; владелец 2026-11-06: «процедурный вертолёт максимально
## простых форм, чтобы он летел, добавить ему процедурный звук»). Не модель для игры — серые примитивы оливкового цвета:
## фюзеляж-капсула, остекление кабины, капот двигателей с двумя соплами, хвостовая балка, киль, стабилизатор,
## несущий винт (4 лопасти и полупрозрачный диск) и рулевой, полозья. Кружит над точкой center (Balance.HELI_TARGET):
## радиус, высота над землёй с плавной волной, скорость, крен в вираже. Звук винтов — ProcSound.ROTOR, слышен издалека.
## Тепловая цель (группа "heat_targets"): сопла двигателей. Ракета попала (missile_hit) — горит, дымит, винт
## останавливается, вертолёт крутится и падает; на земле — взрыв и догорающий остов; через respawn_sec — новый заход
## с другой стороны круга.

enum State { FLY, FALL, WRECK }

## Маршрут (карта «Плотина»: plan.heli стенда tools/heli_study) — летит по нему туда и обратно со скоростью route_speed,
## на концах ждёт route_wait с; пусто — кружит над center.
var route: PackedVector3Array = PackedVector3Array()
var route_speed: float = 42.0
var route_wait: float = 6.0
var center: Vector3 = Vector3.ZERO
var state: int = State.FLY
var kills: int = 0
var _phi: float = 0.0
var _route_len: PackedFloat32Array = PackedFloat32Array()
var _route_s: float = 0.0
var _route_dir: float = 1.0
var _route_pause: float = 0.0
var _ground_y: float = 0.0
var _vel: Vector3 = Vector3.ZERO
var _t: float = 0.0
var _fall_t: float = 0.0
var _wreck_t: float = 0.0
var _spin: float = 0.0
var _yaw: float = 0.0
var _rotor_k: float = 1.0
var _body: Node3D
var _rotor: Node3D
var _tail_rotor: Node3D
var _disc: MeshInstance3D
var _heat: Node3D
var _sound: ProcSound
var _smoke: GPUParticles3D
var _fire: OmniLight3D
var _fire_glow: MeshInstance3D
var _paint: StandardMaterial3D


func _ready() -> void:
	add_to_group("heat_targets")
	_build()
	_sound = ProcSound.make_3d(self, ProcSound.Kind.ROTOR, float(Balance.HELI_TARGET.unit_m), float(Balance.HELI_TARGET.max_m),
		float(Balance.HELI_TARGET.db))
	_sound.blades = int(Balance.HELI_TARGET.blades)
	_sound.tail_hz = float(Balance.HELI_TARGET.tail_hz)
	var total: float = 0.0
	for k in range(route.size()):
		if k > 0:
			total += route[k - 1].distance_to(route[k])
		_route_len.append(total)
	_find_ground()
	_place(0.0)


## Земля под центром круга — высота полёта от неё.
func _find_ground() -> void:
	var q := PhysicsRayQueryParameters3D.create(center + Vector3.UP * 600.0, center + Vector3.DOWN * 600.0, Hitscan.LAYER_WORLD)
	var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(q)
	_ground_y = float((hit.position as Vector3).y) if not hit.is_empty() else center.y


func heat_point() -> Vector3:
	return _heat.global_position


func heat_velocity() -> Vector3:
	return _vel


func heat_alive() -> bool:
	return state == State.FLY


## Попадание ракеты ПЗРК: загорелся и падает.
func missile_hit(_pos: Vector3) -> bool:
	if state != State.FLY:
		return false
	state = State.FALL
	_fall_t = 0.0
	kills += 1
	# земля под местом попадания — запасная высота падения (по маршруту под вертолётом озеро, ущелье, горы)
	var down := PhysicsRayQueryParameters3D.create(global_position, global_position + Vector3.DOWN * 3000.0, Hitscan.LAYER_WORLD)
	var under: Dictionary = get_world_3d().direct_space_state.intersect_ray(down)
	if not under.is_empty():
		_ground_y = float((under.position as Vector3).y)
	remove_from_group("heat_targets")
	_smoke.emitting = true
	_fire.visible = true
	_fire_glow.visible = true
	_paint.albedo_color = _paint.albedo_color.darkened(0.35)
	return true


func _physics_process(delta: float) -> void:
	var cfg: Dictionary = Balance.HELI_TARGET
	_t += delta
	match state:
		State.FLY:
			_place(delta)
		State.FALL:
			_fall(delta)
		State.WRECK:
			_wreck_t += delta
			_fire.light_energy = 4.0 * (0.8 + 0.2 * sin(_t * 17.0)) * clampf(1.0 - _wreck_t / float(cfg.respawn_sec), 0.2, 1.0)
			if _wreck_t >= float(cfg.respawn_sec):
				_respawn()
	_rotor.rotate_y(TAU * float(cfg.rotor_hz) * _rotor_k * delta)
	_tail_rotor.rotate_x(TAU * float(cfg.tail_hz) * _rotor_k * delta)
	_disc.visible = _rotor_k > 0.4
	_sound.rotor_hz = float(cfg.rotor_hz) * maxf(_rotor_k, 0.05)
	_sound.level = clampf(_rotor_k * 1.2, 0.0, 1.0)


## Полёт по маршруту: туда и обратно, на концах пауза (разворот на месте); курс — по ходу, нос чуть опущен.
func _place_route(delta: float) -> void:
	var end: float = _route_len[_route_len.size() - 1]
	var prev: Vector3 = global_position
	if _route_pause > 0.0:
		_route_pause -= delta
	else:
		_route_s += _route_dir * route_speed * delta
		if _route_s >= end or _route_s <= 0.0:
			_route_s = clampf(_route_s, 0.0, end)
			_route_dir = -_route_dir
			_route_pause = route_wait
	var p: Vector3 = route[route.size() - 1]
	for k in range(route.size() - 1):
		if _route_s <= _route_len[k + 1]:
			var t: float = (_route_s - _route_len[k]) / maxf(_route_len[k + 1] - _route_len[k], 0.001)
			p = route[k].lerp(route[k + 1], t)
			break
	global_position = p
	_vel = (p - prev) / delta if delta > 0.0 else Vector3.ZERO
	var flat := Vector3(_vel.x, 0.0, _vel.z)
	if flat.length() > 0.5:
		_yaw = lerp_angle(_yaw, atan2(flat.x, flat.z), minf(1.0, delta * 1.5))
	var tilt: float = deg_to_rad(4.0) if flat.length() > 0.5 else 0.0
	basis = Basis(Vector3.UP, _yaw) * Basis(Vector3.RIGHT, tilt)


## Полёт по кругу: курс — по касательной, крен внутрь виража, высота — плавной волной.
func _place(delta: float) -> void:
	if route.size() >= 2:
		_place_route(delta)
		return
	var cfg: Dictionary = Balance.HELI_TARGET
	var r: float = float(cfg.radius_m)
	var w: float = float(cfg.speed_mps) / r
	_phi += w * delta
	var alt: float = _ground_y + float(cfg.alt_m) + float(cfg.alt_wave_m) * sin(_phi * 2.0 + 0.7)
	var p := Vector3(center.x + cos(_phi) * r, alt, center.z + sin(_phi) * r)
	var tangent := Vector3(-sin(_phi), 0.0, cos(_phi))
	var prev: Vector3 = global_position
	global_position = p
	if delta > 0.0:
		_vel = (p - prev) / delta
	else:
		_vel = tangent * float(cfg.speed_mps)
	_yaw = atan2(tangent.x, tangent.z)
	var bank: float = deg_to_rad(float(cfg.bank_deg))
	# центр круга слева по ходу (обход против часовой, если смотреть сверху) — крен влево; нос чуть опущен
	basis = Basis(Vector3.UP, _yaw) * Basis(Vector3.FORWARD, -bank) * Basis(Vector3.RIGHT, deg_to_rad(4.0))


## Подбит: скорость гаснет, вертолёт крутится вокруг винта и падает; винт останавливается; земля — взрыв.
func _fall(delta: float) -> void:
	var cfg: Dictionary = Balance.HELI_TARGET
	_fall_t += delta
	_rotor_k = maxf(0.15, _rotor_k - delta * 0.25)
	var flat := Vector3(_vel.x, 0.0, _vel.z) * (1.0 - 0.35 * delta)
	var vy: float = _vel.y - 9.8 * delta * 0.85
	_vel = Vector3(flat.x, vy, flat.z)
	_spin += TAU * float(cfg.fall_spin) * minf(1.0, _fall_t / 2.0) * delta
	var from: Vector3 = global_position
	var to: Vector3 = from + _vel * delta
	var q := PhysicsRayQueryParameters3D.create(from, to + Vector3.DOWN * 1.8, Hitscan.LAYER_WORLD)
	var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(q)
	if not hit.is_empty():
		global_position = (hit.position as Vector3) + Vector3.UP * 1.8
		_crash()
		return
	# под вертолётом нет коллизии (край карты, дыра) — не падать бесконечно: земля — высота под центром круга
	if to.y < _ground_y + 1.8:
		global_position = Vector3(to.x, _ground_y + 1.8, to.z)
		_crash()
		return
	global_position = to
	basis = Basis(Vector3.UP, _yaw + _spin) * Basis(Vector3.FORWARD, deg_to_rad(18.0) * sin(_fall_t * 1.3)) \
		* Basis(Vector3.RIGHT, deg_to_rad(12.0 + 6.0 * sin(_fall_t * 0.9)))


func _crash() -> void:
	state = State.WRECK
	_wreck_t = 0.0
	_rotor_k = 0.0
	_vel = Vector3.ZERO
	var pos: Vector3 = global_position
	ImpactFx.explosion(pos)
	ImpactFx._explosion_fx(get_tree().current_scene, pos + Vector3(1.5, 1.0, -2.0), false)
	ImpactFx._explosion_fx(get_tree().current_scene, pos + Vector3(-2.0, 0.5, 2.5), false)
	Audio.play("explosion", pos, 4.0)
	Audio.play("debris", pos)
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	if rig:
		rig.add_shake(clampf(1.0 - pos.distance_to(rig.focus_point()) / 120.0, 0.0, 1.0) * 0.6)
	# остов: тёмный, винт сорван (лопасти прячутся), горит
	_rotor.visible = false
	_paint.albedo_color = Color(0.09, 0.085, 0.08)
	_fire.light_energy = 4.0
	basis = Basis(Vector3.UP, _yaw + _spin) * Basis(Vector3.FORWARD, deg_to_rad(28.0))


## Новый заход — с другой стороны круга, целый.
func _respawn() -> void:
	state = State.FLY
	_rotor_k = 1.0
	_spin = 0.0
	_phi += PI
	_route_s = 0.0
	_route_dir = 1.0
	_route_pause = route_wait
	_rotor.visible = true
	_paint.albedo_color = Color(0.27, 0.3, 0.2)
	_smoke.emitting = false
	_fire.visible = false
	_fire_glow.visible = false
	add_to_group("heat_targets")
	_place(0.0)


# ---------------------------------------------------------------- сборка из примитивов

func _build() -> void:
	_paint = _mat(Color(0.27, 0.3, 0.2), 0.62, 0.15)
	var dark: StandardMaterial3D = _mat(Color(0.08, 0.08, 0.08), 0.5, 0.4)
	var glass: StandardMaterial3D = _mat(Color(0.05, 0.08, 0.1), 0.08, 0.2)
	var soot: StandardMaterial3D = _mat(Color(0.05, 0.045, 0.04), 0.85, 0.3)
	_body = Node3D.new()
	_body.name = "Body"
	add_child(_body)
	# фюзеляж и остекление
	var fus := CapsuleMesh.new()
	fus.radius = 1.25
	fus.height = 7.0
	_part(fus, _paint, Vector3(0, 0, 0.6), Vector3(90, 0, 0))
	var cab := SphereMesh.new()
	cab.radius = 1.12
	cab.height = 2.0
	_part(cab, glass, Vector3(0, 0.3, 3.35), Vector3.ZERO, Vector3(1.0, 0.95, 1.2))
	# капот двигателей и сопла (тепловая точка — между ними, чуть позади)
	var hood := BoxMesh.new()
	hood.size = Vector3(1.5, 0.75, 3.2)
	_part(hood, _paint, Vector3(0, 1.35, 0.2))
	for side: float in [-1.0, 1.0]:
		var ex := CylinderMesh.new()
		ex.top_radius = 0.2
		ex.bottom_radius = 0.26
		ex.height = 0.7
		_part(ex, soot, Vector3(0.62 * side, 1.38, -1.45), Vector3(-75, 0, -20 * side))
	_heat = Node3D.new()
	_heat.name = "Heat"
	_body.add_child(_heat)
	_heat.position = Vector3(0, 1.45, -1.9)
	# хвостовая балка, киль, стабилизатор
	var boom := CylinderMesh.new()
	boom.top_radius = 0.24
	boom.bottom_radius = 0.6
	boom.height = 6.6
	_part(boom, _paint, Vector3(0, 0.55, -5.3), Vector3(-90, 0, 0))
	var fin := BoxMesh.new()
	fin.size = Vector3(0.14, 1.9, 1.1)
	_part(fin, _paint, Vector3(0, 1.45, -8.45), Vector3(-22, 0, 0))
	var stab := BoxMesh.new()
	stab.size = Vector3(2.6, 0.08, 0.65)
	_part(stab, _paint, Vector3(0, 0.6, -7.3))
	# несущий винт: вал, втулка, лопасти и диск
	var mast := CylinderMesh.new()
	mast.top_radius = 0.12
	mast.bottom_radius = 0.16
	mast.height = 0.7
	_part(mast, dark, Vector3(0, 2.0, 0.55))
	_rotor = Node3D.new()
	_rotor.name = "Rotor"
	_body.add_child(_rotor)
	_rotor.position = Vector3(0, 2.38, 0.55)
	var blades: int = int(Balance.HELI_TARGET.blades)
	for i in range(blades):
		var arm := Node3D.new()
		_rotor.add_child(arm)
		arm.rotation.y = TAU * float(i) / float(blades)
		var bl := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3(0.48, 0.05, 7.3)
		bl.mesh = bm
		bl.material_override = dark
		arm.add_child(bl)
		bl.position = Vector3(0, 0, 3.9)
		bl.rotation.z = deg_to_rad(6.0)
	var hub := SphereMesh.new()
	hub.radius = 0.32
	hub.height = 0.4
	var hub_i := MeshInstance3D.new()
	hub_i.mesh = hub
	hub_i.material_override = dark
	_rotor.add_child(hub_i)
	_disc = MeshInstance3D.new()
	var dm := CylinderMesh.new()
	dm.top_radius = 7.6
	dm.bottom_radius = 7.6
	dm.height = 0.02
	dm.radial_segments = 48
	_disc.mesh = dm
	var disc_mat := StandardMaterial3D.new()
	disc_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	disc_mat.albedo_color = Color(0.1, 0.1, 0.1, 0.16)
	disc_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	_disc.material_override = disc_mat
	_disc.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_body.add_child(_disc)
	_disc.position = Vector3(0, 2.4, 0.55)
	# рулевой винт — сбоку на киле
	_tail_rotor = Node3D.new()
	_tail_rotor.name = "TailRotor"
	_body.add_child(_tail_rotor)
	_tail_rotor.position = Vector3(0.28, 1.75, -8.7)
	for j in range(3):
		var tb := MeshInstance3D.new()
		var tm := BoxMesh.new()
		tm.size = Vector3(0.04, 1.45, 0.2)
		tb.mesh = tm
		tb.material_override = dark
		var tarm := Node3D.new()
		_tail_rotor.add_child(tarm)
		tarm.rotation.x = TAU * float(j) / 3.0
		tarm.add_child(tb)
		tb.position = Vector3(0, 0.7, 0)
	# полозья на стойках
	for side2: float in [-1.0, 1.0]:
		var skid := CylinderMesh.new()
		skid.top_radius = 0.07
		skid.bottom_radius = 0.07
		skid.height = 4.4
		_part(skid, dark, Vector3(1.15 * side2, -1.75, 0.7), Vector3(90, 0, 0))
		for z: float in [-0.6, 2.0]:
			var strut := CylinderMesh.new()
			strut.top_radius = 0.06
			strut.bottom_radius = 0.06
			strut.height = 1.1
			_part(strut, dark, Vector3(1.0 * side2, -1.25, z), Vector3(0, 0, 18 * side2))
	# огонь и дым — включаются при попадании
	_fire = OmniLight3D.new()
	_fire.light_color = Color(1.0, 0.55, 0.2)
	_fire.light_energy = 5.0
	_fire.omni_range = 22.0
	_fire.visible = false
	_fire.set_meta("soft", true)
	_body.add_child(_fire)
	_fire.position = Vector3(0, 1.6, -1.2)
	_fire_glow = MeshInstance3D.new()
	var fq := QuadMesh.new()
	fq.size = Vector2(3.5, 3.5)
	_fire_glow.mesh = fq
	var fm := StandardMaterial3D.new()
	fm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	fm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	fm.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	fm.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	fm.albedo_color = Color(1.0, 0.5, 0.15, 0.9)
	fm.albedo_texture = OsokaMissile._soft_texture()
	_fire_glow.material_override = fm
	_fire_glow.visible = false
	_body.add_child(_fire_glow)
	_fire_glow.position = Vector3(0, 1.7, -1.3)
	_smoke = _make_smoke()
	_body.add_child(_smoke)
	_smoke.position = Vector3(0, 1.6, -1.6)


func _make_smoke() -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.name = "Smoke"
	p.local_coords = false
	p.interpolate = true
	p.amount = 600
	p.lifetime = 9.0
	p.emitting = false
	p.visibility_aabb = AABB(Vector3(-600, -600, -600), Vector3(1200, 1200, 1200))
	var pm := ParticleProcessMaterial.new()
	pm.direction = Vector3.UP
	pm.spread = 40.0
	pm.initial_velocity_min = 1.0
	pm.initial_velocity_max = 3.0
	pm.gravity = Vector3(0, 1.2, 0)
	pm.damping_min = 0.3
	pm.damping_max = 0.6
	pm.scale_min = 1.4
	pm.scale_max = 2.2
	var sc := Curve.new()
	sc.max_value = 5.0
	sc.add_point(Vector2(0.0, 1.0))
	sc.add_point(Vector2(1.0, 5.0))
	var sct := CurveTexture.new()
	sct.curve = sc
	pm.scale_curve = sct
	var grad := Gradient.new()
	grad.offsets = PackedFloat32Array([0.0, 0.08, 0.5, 1.0])
	grad.colors = PackedColorArray([Color(1.0, 0.5, 0.2, 0.9), Color(0.12, 0.11, 0.1, 0.85), Color(0.18, 0.17, 0.16, 0.5),
		Color(0.25, 0.25, 0.25, 0.0)])
	var gt := GradientTexture1D.new()
	gt.gradient = grad
	pm.color_ramp = gt
	p.process_material = pm
	var quad := QuadMesh.new()
	p.draw_pass_1 = quad
	if not ImpactBurst._flipbook("puff_b").is_empty():
		pm.anim_speed_min = 0.3
		pm.anim_speed_max = 0.5
		pm.anim_offset_max = 1.0
		p.material_override = ImpactBurst._material("dust_puff_b")
	else:
		var mat := StandardMaterial3D.new()
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		mat.vertex_color_use_as_albedo = true
		mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
		mat.albedo_texture = OsokaMissile._soft_texture()
		p.material_override = mat
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return p


func _part(mesh: Mesh, mat: Material, pos: Vector3, rot_deg: Vector3 = Vector3.ZERO, scl: Vector3 = Vector3.ONE) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = mat
	_body.add_child(mi)
	mi.position = pos
	mi.rotation_degrees = rot_deg
	mi.scale = scl
	return mi


func _mat(color: Color, rough: float, metal: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = rough
	m.metallic = metal
	return m
