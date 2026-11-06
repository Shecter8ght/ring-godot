class_name OsokaMissile
extends Node3D
## Ракета ЗР-36 «Осоки» в полёте (Balance.OSOKA). Пуск рассылает Player (_rpc_osoka_launch): у всех peer та же точка,
## направление и цель; урон считает только peer стрелка (как у гранаты — Health.apply_or_request_damage, в сети — хост).
## Полёт: вышибной заряд выталкивает ракету из трубы (eject_mps), за трубой раскрываются стабилизаторы и рули
## (fins_sec), на ignite_m включается маршевый двигатель — разгон до speed_mps за boost_sec, дымный след и пламя
## burn_sec. С двигателем ракета наводится на тепловую цель пропорциональным методом (nav_k) с пределом перегрузки
## max_g; цель — узел группы "heat_targets" (heat_point(), heat_velocity(), heat_alive(), missile_hit()). Взрыватель —
## ближе fuse_m к цели (с проверкой всего отрезка за кадр: ракета пролетает ~10 м за кадр) или удар; взвод — после
## arm_m (удар раньше — ракета разбивается без взрыва). Через life_sec — самоликвидация в воздухе.
## Модель — assets/models/weapons/osoka/osoka_missile.gltf (узлы Fin0…3, RudderTop/Bottom на шарнирах; повороты
## раскрытия — osoka.json, missile_deploy); нет файла — процедурный цилиндр.

const MODEL := "res://assets/models/weapons/osoka/osoka_missile.gltf"
## Раскрытие (отчёт экспорта osoka.json, missile_deploy): стабилизаторы −90° вокруг своей продольной оси, рули ±90°.
const DEPLOY := {"Fin0_Missile": [Vector3(0, 0, 1), -90.0], "Fin1_Missile": [Vector3(0, 0, 1), -90.0],
	"Fin2_Missile": [Vector3(0, 0, 1), -90.0], "Fin3_Missile": [Vector3(0, 0, 1), -90.0],
	"RudderTop_Missile": [Vector3(1, 0, 0), 90.0], "RudderBottom_Missile": [Vector3(1, 0, 0), -90.0]}
## Длина трубы от сопла ракеты в ней до среза раструба, м — дальше ракета «на воле» (раскрытие, след виден).
const TUBE_M := 1.62
## Взвод взрывателя, м: удар ближе — ракета разбивается без взрыва (стрелка не накрывает).
const ARM_M := 15.0

var src: Dictionary = {"kind": "missile"}
var _vel: Vector3
var _speed: float = 0.0
var _t: float = 0.0
var _motor_t: float = -1.0
var _flown: float = 0.0
var _target: Node3D
var _target_prev: Vector3 = Vector3.INF
var _damage: bool = true
var _attacker: int = -1
var _shooter: RID
var _model: Node3D
var _fins: Array = []
var _deploy_k: float = 0.0
var _roll: float = 0.0
var _flame: MeshInstance3D
var _light: OmniLight3D
var _trail: GPUParticles3D
var _motor_sound: ProcSound
var _done: bool = false
var _hit_cb: Callable


## Пуск: from — сопло ракеты в трубе (метка MissileMount), dir — ось трубы, target — захваченная тепловая цель или
## null. on_hit(цель) — у стрелка: ракета попала (отметка попадания).
static func launch(parent: Node, from: Vector3, dir: Vector3, target: Node3D, shooter: RID, deal_damage: bool,
		attacker: int = -1, on_hit: Callable = Callable()) -> OsokaMissile:
	var m := OsokaMissile.new()
	m.name = "OsokaMissile"
	m._target = target
	m._shooter = shooter
	m._damage = deal_damage
	m._attacker = attacker
	m._hit_cb = on_hit
	m.src = {"kind": "missile", "by": "player"}
	var d: Vector3 = dir.normalized() if dir.length_squared() > 0.0001 else Vector3.FORWARD
	m._speed = float(Balance.OSOKA.eject_mps)
	m._vel = d * m._speed
	parent.add_child(m)
	m.global_position = from
	m._face(d)
	m._launch_fx(from, d)
	return m


func _ready() -> void:
	add_to_group("missiles")
	_build_model()
	_flame = _glow_quad(1.3, Color(1.0, 0.72, 0.38, 1.0))
	_flame.visible = false
	_light = OmniLight3D.new()
	_light.light_color = Color(1.0, 0.68, 0.35)
	_light.light_energy = 0.0
	_light.omni_range = 30.0
	_light.shadow_enabled = false
	_light.set_meta("soft", true)
	add_child(_light)
	_light.position = Vector3(0, 0, -0.4)


func _build_model() -> void:
	if ResourceLoader.exists(MODEL, "PackedScene"):
		_model = (ResourceLoader.load(MODEL, "PackedScene") as PackedScene).instantiate() as Node3D
	if _model == null:
		# без ассетов — серый цилиндр той же длины
		_model = Node3D.new()
		var mi := MeshInstance3D.new()
		var cyl := CylinderMesh.new()
		cyl.top_radius = 0.036
		cyl.bottom_radius = 0.036
		cyl.height = 1.6
		mi.mesh = cyl
		mi.rotation.x = PI * 0.5
		mi.position.z = 0.8
		_model.add_child(mi)
	_model.name = "Model"
	add_child(_model)
	for node_name: String in DEPLOY:
		var n: Node3D = _model.find_child(node_name, true, false) as Node3D
		if n:
			_fins.append([n, n.transform, DEPLOY[node_name][0], float(DEPLOY[node_name][1])])
	for raw: Node in _model.find_children("*", "GeometryInstance3D", true, false):
		(raw as GeometryInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON


## Корпус — по скорости (+Z модели — к носу), с вращением вокруг оси.
func _face(d: Vector3) -> void:
	var up: Vector3 = Vector3.UP if absf(d.dot(Vector3.UP)) < 0.98 else Vector3.RIGHT
	basis = Basis.looking_at(-d, up) * Basis(Vector3(0, 0, 1), _roll)


func _physics_process(delta: float) -> void:
	if _done:
		return
	var cfg: Dictionary = Balance.OSOKA
	_t += delta
	var from: Vector3 = global_position
	if _motor_t < 0.0 and _flown >= float(cfg.ignite_m):
		_ignite()
	if _motor_t >= 0.0:
		_motor_t += delta
		var accel: float = (float(cfg.speed_mps) - float(cfg.eject_mps)) / maxf(float(cfg.boost_sec), 0.01)
		if _motor_t < float(cfg.burn_sec):
			_speed = minf(_speed + accel * delta, float(cfg.speed_mps))
		else:
			# двигатель догорел — тормозит воздух
			_speed = maxf(60.0, _speed * (1.0 - 0.06 * delta))
			if _motor_t - delta < float(cfg.burn_sec):
				_burn_out()
		_guide(delta)
	else:
		# до двигателя — по инерции, чуть проседает
		_vel += Vector3.DOWN * 9.8 * delta * 0.5
	if _motor_t >= float(cfg.burn_sec) or _target == null:
		_vel += Vector3.DOWN * 9.8 * delta * 0.3
	_vel = _vel.normalized() * _speed
	var to: Vector3 = from + _vel * delta
	_flown += from.distance_to(to)
	# взрыватель: цель ближе fuse_m от отрезка за этот кадр
	var tgt: Vector3 = _target_point()
	if tgt != Vector3.INF:
		var closest: Vector3 = Geometry3D.get_closest_point_to_segment(tgt, from, to)
		if closest.distance_to(tgt) <= float(cfg.fuse_m):
			global_position = closest
			_explode(closest, true)
			return
	# удар о мир, людей, мишени
	var mask: int = Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_GLASS | Hitscan.LAYER_MARAUDER | Hitscan.LAYER_PLAYER
	var exclude: Array[RID] = []
	if _t < 1.5:
		exclude.append(_shooter)
	var q := PhysicsRayQueryParameters3D.create(from, to, mask, exclude)
	var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(q)
	if not hit.is_empty():
		global_position = hit.position
		if _flown < ARM_M:
			_dud(hit.position)
		else:
			_explode(hit.position, false)
		return
	global_position = to
	_roll += TAU * float(cfg.roll_hz) * delta
	_face(_vel.normalized())
	# раскрытие рулей и стабилизаторов — как только вышла из трубы
	if _flown > TUBE_M and _deploy_k < 1.0:
		_deploy_k = minf(1.0, _deploy_k + delta / maxf(float(cfg.fins_sec), 0.01))
		for f: Array in _fins:
			var rest: Transform3D = f[1]
			var k: float = ease(_deploy_k, 0.5)
			(f[0] as Node3D).transform = Transform3D(Basis((f[2] as Vector3), deg_to_rad(float(f[3]) * k)) * rest.basis, rest.origin)
	if _motor_t >= 0.0 and _motor_t < float(cfg.burn_sec):
		_flame.visible = true
		var flick: float = 0.85 + 0.3 * sin(_t * 61.0) * sin(_t * 23.0)
		_flame.scale = Vector3.ONE * flick
		_light.light_energy = 7.0 * flick
	if _t >= float(cfg.life_sec):
		_explode(global_position, false)


## Точка цели (сопла двигателей вертолёта, звезда ракеты) — или INF, если цели нет / она уже не горит.
func _target_point() -> Vector3:
	if _target == null or not is_instance_valid(_target):
		_target = null
		return Vector3.INF
	if _target.has_method("heat_alive") and not bool(_target.call("heat_alive")):
		_target = null
		return Vector3.INF
	return _target.call("heat_point") if _target.has_method("heat_point") else _target.global_position


## Пропорциональное наведение: ускорение поперёк скорости, пропорционально повороту линии визирования.
func _guide(delta: float) -> void:
	var tp: Vector3 = _target_point()
	if tp == Vector3.INF:
		_target_prev = Vector3.INF
		return
	var tv: Vector3 = Vector3.ZERO
	if _target.has_method("heat_velocity"):
		tv = _target.call("heat_velocity")
	elif _target_prev != Vector3.INF:
		tv = (tp - _target_prev) / maxf(delta, 0.001)
	_target_prev = tp
	var r: Vector3 = tp - global_position
	var dist2: float = maxf(r.length_squared(), 1.0)
	var v_rel: Vector3 = tv - _vel
	var omega: Vector3 = r.cross(v_rel) / dist2
	var closing: float = maxf(-r.normalized().dot(v_rel), 50.0)
	var a: Vector3 = float(Balance.OSOKA.nav_k) * closing * omega.cross(r.normalized())
	# в начале полёта линия визирования ещё не «устоялась» — довернуть на цель напрямую (ракета на старте смотрит
	# по оси трубы, выше линии прицела)
	var lead: Vector3 = (r.normalized() - _vel.normalized()) * _speed * 2.5
	a += lead
	var v_dir: Vector3 = _vel.normalized()
	a -= v_dir * a.dot(v_dir)
	var limit: float = float(Balance.OSOKA.max_g) * 9.81
	if a.length() > limit:
		a = a.normalized() * limit
	_vel += a * delta


func _ignite() -> void:
	_motor_t = 0.0
	_flame.visible = true
	_motor_sound = null
	if Audio.has_sound("osoka_motor"):
		Audio.play("osoka_motor", global_position)
	else:
		_motor_sound = ProcSound.make_3d(self, ProcSound.Kind.MOTOR, 35.0, 4000.0, 6.0, &"Shots")
	_trail = _make_trail()
	add_child(_trail)
	_trail.emitting = true


func _burn_out() -> void:
	_flame.visible = false
	_light.light_energy = 0.0
	if _trail:
		_trail.emitting = false
	if is_instance_valid(_motor_sound):
		_motor_sound.level = 0.0


## Дымный след: частицы в мире (не за ракетой), выпуск растянут по пути ракеты за кадр (interpolate) — сплошной
## шлейф и на 570 м/с; дым — тот же лист кадров, что у разрывов (ImpactBurst «dust_puff_b»), растёт и тает.
func _make_trail() -> GPUParticles3D:
	var cfg: Dictionary = Balance.OSOKA
	var p := GPUParticles3D.new()
	p.name = "Trail"
	p.local_coords = false
	p.interpolate = true
	p.fract_delta = true
	p.lifetime = float(cfg.trail_life_sec)
	# частота выпуска у GPUParticles3D — amount / lifetime: частица на step_m при полной скорости
	var per_sec: float = float(cfg.speed_mps) / float(cfg.trail_step_m)
	p.amount = int(per_sec * float(cfg.trail_life_sec))
	p.preprocess = 0.0
	p.visibility_aabb = AABB(Vector3(-3000, -3000, -3000), Vector3(6000, 6000, 6000))
	var pm := ParticleProcessMaterial.new()
	pm.direction = Vector3.UP
	pm.spread = 180.0
	pm.initial_velocity_min = 0.2
	pm.initial_velocity_max = 1.2
	pm.gravity = Vector3(0, 0.25, 0)
	pm.damping_min = 0.4
	pm.damping_max = 0.8
	var size: Array = cfg.trail_size
	pm.scale_min = float(size[0])
	pm.scale_max = float(size[0]) * 1.4
	var sc := Curve.new()
	sc.max_value = float(size[1]) / float(size[0])
	sc.add_point(Vector2(0.0, 1.0))
	sc.add_point(Vector2(0.15, sc.max_value * 0.35))
	sc.add_point(Vector2(1.0, sc.max_value))
	var sct := CurveTexture.new()
	sct.curve = sc
	pm.scale_curve = sct
	pm.angle_min = -180.0
	pm.angle_max = 180.0
	var grad := Gradient.new()
	grad.offsets = PackedFloat32Array([0.0, 0.03, 0.4, 1.0])
	grad.colors = PackedColorArray([Color(1.0, 0.85, 0.6, 0.9), Color(0.82, 0.8, 0.77, 0.85),
		Color(0.78, 0.77, 0.75, 0.45), Color(0.8, 0.8, 0.8, 0.0)])
	var gt := GradientTexture1D.new()
	gt.gradient = grad
	pm.color_ramp = gt
	p.process_material = pm
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE
	p.draw_pass_1 = quad
	p.material_override = smoke_material()
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	p.position = Vector3(0, 0, -0.05)
	return p


static var _smoke_mat: StandardMaterial3D


## Дым ракеты: мягкое белёсое пятно, освещается солнцем (пылевой лист кадров разрывов — бурый, для следа не годится).
static func smoke_material() -> StandardMaterial3D:
	if _smoke_mat:
		return _smoke_mat
	var mat := StandardMaterial3D.new()
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.vertex_color_use_as_albedo = true
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	mat.albedo_texture = _soft_texture()
	mat.roughness = 1.0
	mat.specular_mode = BaseMaterial3D.SPECULAR_DISABLED
	mat.disable_receive_shadows = true
	_smoke_mat = mat
	return mat


## Облако дыма в точке pos: amount клубов, живут life с, разлетаются со скоростью speed, растут от size[0] до size[1] м.
func _smoke_burst(parent: Node, pos: Vector3, dir: Vector3, amount: int, life: float, speed: Vector2, size: Vector2, alpha: float) -> void:
	var p := GPUParticles3D.new()
	p.one_shot = true
	p.explosiveness = 0.95
	p.amount = amount
	p.lifetime = life
	var pm := ParticleProcessMaterial.new()
	pm.direction = dir
	pm.spread = 35.0
	pm.initial_velocity_min = speed.x
	pm.initial_velocity_max = speed.y
	pm.gravity = Vector3(0, 0.3, 0)
	pm.damping_min = 4.0
	pm.damping_max = 7.0
	pm.scale_min = size.x
	pm.scale_max = size.x * 1.3
	var sc := Curve.new()
	sc.max_value = size.y / size.x
	sc.add_point(Vector2(0.0, 1.0))
	sc.add_point(Vector2(1.0, sc.max_value))
	var sct := CurveTexture.new()
	sct.curve = sc
	pm.scale_curve = sct
	var grad := Gradient.new()
	grad.offsets = PackedFloat32Array([0.0, 0.15, 1.0])
	grad.colors = PackedColorArray([Color(0.92, 0.91, 0.88, alpha), Color(0.86, 0.85, 0.83, alpha * 0.8), Color(0.88, 0.88, 0.87, 0.0)])
	var gt := GradientTexture1D.new()
	gt.gradient = grad
	pm.color_ramp = gt
	p.process_material = pm
	var quad := QuadMesh.new()
	p.draw_pass_1 = quad
	p.material_override = smoke_material()
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(p)
	p.global_position = pos
	p.emitting = true
	get_tree().create_timer(life + 0.5).timeout.connect(p.queue_free)


## Пуск у трубы: хлопок вышибного заряда, облако у раструба и выброс назад из казённой части.
func _launch_fx(from: Vector3, d: Vector3) -> void:
	var parent: Node = get_parent()
	if Audio.has_sound("osoka_launch"):
		Audio.play("osoka_launch", from)
	else:
		var holder := Node3D.new()
		parent.add_child(holder)
		holder.global_position = from + d * TUBE_M * 0.5
		var s := ProcSound.make_3d(holder, ProcSound.Kind.THUMP, 18.0, 1500.0, 8.0, &"Shots")
		s.life = 0.9
		get_tree().create_timer(1.0).timeout.connect(holder.queue_free)
	NoiseBus.emit(from, float(Balance.OSOKA.noise_m), "shot")
	# у раструба — небольшой белёсый клуб вперёд, сзади — выброс газов назад из казённой части
	_smoke_burst(parent, from + d * (TUBE_M + 0.2), d, 8, 1.6, Vector2(1.0, 3.0), Vector2(0.3, 1.4), 0.45)
	_smoke_burst(parent, from - d * 0.3, -d, 12, 2.2, Vector2(3.0, 8.0), Vector2(0.35, 1.8), 0.4)


## Взрыв боевой части: урон и толчок в радиусе (с прямой видимостью), цель — подбита.
func _explode(pos: Vector3, proximity: bool) -> void:
	_done = true
	var cfg: Dictionary = Balance.OSOKA
	var radius: float = float(cfg.radius_m)
	var hit_target: bool = false
	if _target != null and is_instance_valid(_target) and _target.has_method("missile_hit"):
		var tp: Vector3 = _target_point()
		if proximity or (tp != Vector3.INF and tp.distance_to(pos) <= radius):
			hit_target = bool(_target.call("missile_hit", pos))
	if hit_target and _hit_cb.is_valid():
		_hit_cb.call(_target)
	var space := get_world_3d().direct_space_state
	for group in ["players", "marauders", "shootable"]:
		for n in get_tree().get_nodes_in_group(group):
			var body := n as Node3D
			if body == null:
				continue
			var point := body.global_position + Vector3.UP * 1.0
			var d := pos.distance_to(point)
			if d > radius:
				continue
			var q := PhysicsRayQueryParameters3D.create(pos, point, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR)
			if not space.intersect_ray(q).is_empty():
				continue
			var dmg := float(cfg.damage) * pow(1.0 - d / radius, 1.3)
			if body is Target and _damage:
				(body as Target).on_hit(point, (point - pos).normalized(), dmg)
			var h := body.get_node_or_null("Health") as Health
			if h and _damage:
				h.apply_or_request_damage(dmg, pos, "blast_close" if d < 2.0 else "blast", _attacker, Vector3.INF, {"src": src})
	for rd in get_tree().get_nodes_in_group("ragdolls"):
		var r: Variant = rd
		var c: Node3D = r.chest()
		if c and c.global_position.distance_to(pos) < radius:
			var k := 1.0 - c.global_position.distance_to(pos) / radius
			r.push(((c.global_position - pos).normalized() + Vector3.UP * 0.6) * float(cfg.push) * k, c.global_position)
	if _damage:
		for gp in get_tree().get_nodes_in_group("glass_panes"):
			(gp as GlassPanes).blast(pos, radius * 1.3)
	NoiseBus.emit(pos, 400.0, "shot")
	# у земли — обычный взрыв с подпалиной, в воздухе — без неё
	var floor_q := PhysicsRayQueryParameters3D.create(pos + Vector3.UP * 0.5, pos + Vector3.DOWN * 2.0, Hitscan.LAYER_WORLD)
	if space.intersect_ray(floor_q).is_empty():
		ImpactFx._explosion_fx(get_tree().current_scene, pos, false)
	else:
		ImpactFx.explosion(pos)
	Audio.play("explosion", pos)
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	if rig:
		var cam_d := pos.distance_to(rig.focus_point())
		rig.add_shake(clampf(1.0 - cam_d / 40.0, 0.0, 1.0) * 0.9)
	_finish()


## Удар раньше взвода — без взрыва: искры, звук удара, ракета пропадает.
func _dud(pos: Vector3) -> void:
	_done = true
	Audio.play("debris", pos, -4.0)
	_finish()


## След остаётся дотлевать в мире; звук двигателя стихает; сама ракета пропадает.
func _finish() -> void:
	set_physics_process(false)
	if _trail:
		_trail.emitting = false
		var keep: GPUParticles3D = _trail
		var at: Transform3D = keep.global_transform
		remove_child(keep)
		get_tree().current_scene.add_child(keep)
		keep.global_transform = at
		get_tree().create_timer(keep.lifetime + 0.5).timeout.connect(keep.queue_free)
	if is_instance_valid(_motor_sound):
		_motor_sound.queue_free()
	queue_free()


func _glow_quad(size: float, color: Color) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = Vector2.ONE * size
	mi.mesh = q
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.albedo_color = color
	m.albedo_texture = _soft_texture()
	m.no_depth_test = false
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)
	mi.position = Vector3(0, 0, -0.45)
	return mi


static var _soft: Texture2D


static func _soft_texture() -> Texture2D:
	if _soft:
		return _soft
	var grad := Gradient.new()
	grad.set_color(0, Color(1, 1, 1, 1))
	grad.set_color(1, Color(1, 1, 1, 0))
	var tex := GradientTexture2D.new()
	tex.gradient = grad
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(1.0, 0.5)
	_soft = tex
	return tex
