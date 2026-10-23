class_name PerceptionLab
extends DevelopmentLab
## Наблюдение за настоящим Marauder: стенд не передаёт ему позицию цели в обход зрения/шума.

var enemy: Marauder
var barrier: StaticBody3D
var cone: MeshInstance3D
var distance: float = 12.0
var target_angle: float = 0.0
var enemy_yaw: float = 0.0
var fixed_observer: bool = true
var allow_fire: bool = false
var _wall: bool = false
var _view: Dictionary = {}
var _heard: String = "Шума ещё не было. Можно отправить событие кнопкой или пройтись с F6."
var _mesh: ImmediateMesh
var _draw_timer: float = 0.0
var _notice_time: float = 0.0
var _acquired_after: float = -1.0
var target_angle_control: SpinBox


func _ready() -> void:
	super._ready()
	start_atmosphere(16.0)
	var nav: NavigationMesh = NavigationMesh.new()
	nav.set_vertices(PackedVector3Array([Vector3(-90,0,-90), Vector3(-90,0,110), Vector3(90,0,110), Vector3(90,0,-90)]))
	nav.add_polygon(PackedInt32Array([0,1,2,3]))
	var region: NavigationRegion3D = NavigationRegion3D.new()
	region.name = "NavigationRegion"
	region.navigation_mesh = nav
	add_child(region)
	enemy = (load("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	enemy.name = "Observer"
	enemy.archetype = "gunner"
	enemy.watch_dir = Vector3.FORWARD
	enemy.watch_sector_deg = 0.0
	enemy.hold_radius = 0.0
	enemy.position = Vector3(0, 0.03, 18)
	add_child(enemy)
	enemy._health.invulnerable = true
	enemy._grenades = 0
	barrier = box($Samples, "SightBarrier", Vector3(0, 1.3, 12), Vector3(5, 2.6, 0.35), Color(0.45, 0.49, 0.52))
	_set_barrier(false)
	cone = MeshInstance3D.new()
	cone.name = "VisionAndHearingOverlay"
	_mesh = ImmediateMesh.new()
	cone.mesh = _mesh
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.vertex_color_use_as_albedo = true
	material.no_depth_test = true
	cone.material_override = material
	add_child(cone)
	text_3d(enemy, "НАБЛЮДАТЕЛЬ", Vector3(0, 2.3, 0))
	panel.number("Расстояние до цели · м", distance, 3.0, 100.0, 0.5, func(value: float) -> void:
		distance = value
		_position_target())
	target_angle_control = panel.number("Цель вокруг наблюдателя · °", target_angle, -180.0, 180.0, 1.0, func(value: float) -> void:
		target_angle = value
		_position_target())
	panel.number("Куда смотрит наблюдатель · °", enemy_yaw, -180.0, 180.0, 1.0, func(value: float) -> void:
		enemy_yaw = value
		reset_observer())
	panel.option("Стойка цели", ["Стоя", "Сидя", "Лёжа"], _set_stance)
	panel.toggle("Стена между наблюдателем и целью", false, _set_barrier)
	panel.toggle("Наблюдатель закреплён на месте", true, func(enabled: bool) -> void: fixed_observer = enabled)
	panel.toggle("Разрешить стрельбу наблюдателя", false, func(enabled: bool) -> void: allow_fire = enabled)
	panel.action("Шум: шаг", func() -> void: emit_noise("step", float(Balance.NOISE_STEP.stand)))
	panel.action("Шум: бег", func() -> void: emit_noise("step", float(Balance.NOISE_STEP.sprint)))
	panel.action("Шум: выстрел текущего оружия", emit_shot_noise)
	panel.action("Сбросить обнаружение и память", reset_observer)
	panel.option("Погода", ["Ясно", "Пасмурно", "Дождь", "Туман", "Жара"], set_weather)
	panel.number("Часы · условия видимости", 16.0, 0.0, 23.95, 0.1, set_hour)
	panel.label(panel.context, "Зрение проверяет угол, игровую дальность и преграду. Слух сейчас определяется радиусом события; стена сама по себе радиус не уменьшает.", 14)
	NoiseBus.noise.connect(_record_noise)
	observer.position = Vector3(45, 65, -35)
	observer.look_at(Vector3(0, 0, 15), Vector3.UP)
	_position_target()


func _position_target() -> void:
	if not is_instance_valid(enemy):
		return
	var angle: float = deg_to_rad(target_angle)
	player.position = enemy.position + Vector3(sin(angle), 0.0, -cos(angle)) * distance
	player.velocity = Vector3.ZERO
	player._eye_tick_ready = false
	var direction: Vector3 = enemy.position - player.position
	rig._look_yaw = atan2(direction.x, direction.z)
	rig._look_pitch = 0.0
	if is_instance_valid(barrier):
		barrier.position = (enemy.position + player.position) * 0.5 + Vector3(0, 1.3, 0)
		barrier.rotation.y = -angle
	reset_observer()


func _set_stance(index: int) -> void:
	match index:
		1: player.stance = Player.Stance.CROUCH
		2: player.stance = Player.Stance.PRONE
		_: player.stance = Player.Stance.STAND
	player._apply_stance()
	player._eye_tick_ready = false
	reset_observer()


func _set_barrier(enabled: bool) -> void:
	_wall = enabled
	barrier.visible = enabled
	barrier.collision_layer = Hitscan.LAYER_WORLD if enabled else 0
	reset_observer()


func reset_observer() -> void:
	if not is_instance_valid(enemy):
		return
	enemy.state = Marauder.State.PATROL
	enemy.notice_timer = 0.0
	enemy.memory_timer = 0.0
	enemy._target_player = null
	enemy._foe = null
	enemy._seen_now = false
	enemy.last_known = Vector3.ZERO
	enemy._facing = PI + deg_to_rad(enemy_yaw)
	enemy.velocity = Vector3.ZERO
	_notice_time = 0.0
	_acquired_after = -1.0


func _settings_changed() -> void:
	if DayCycle.current:
		DayCycle.current.set_hour(DayCycle.current.hour)
	reset_observer()


func emit_noise(kind: String, radius: float) -> void:
	NoiseBus.emit(player.global_position, radius, kind)


func emit_shot_noise() -> void:
	emit_noise("shot", float(player.spec().noise_m))


func _record_noise(position: Vector3, radius: float, kind: String) -> void:
	if not is_instance_valid(enemy) or position.distance_to(player.global_position) > 2.0:
		return
	var range_m: float = radius * Balance.lab_number("perception", "hearing")
	var distance_m: float = enemy.global_position.distance_to(position)
	_heard = "%s · шум «%s»: %.1f м до источника, слышно до %.1f м" % [
		"Шум дошёл" if distance_m <= range_m else "Шум не дошёл", kind, distance_m, range_m]


func diagnose() -> Dictionary:
	var eye: Vector3 = enemy._eye()
	var point: Vector3 = player.global_position + Vector3.UP * float(Perception.TARGET_HEIGHT[player.stance_key()]) + player.lean_vector()
	var to: Vector3 = point - eye
	var forward: Vector3 = Vector3(sin(enemy._facing), 0, cos(enemy._facing))
	var flat: Vector3 = Vector3(to.x, 0, to.z).normalized()
	var angle: float = rad_to_deg(acos(clampf(forward.dot(flat), -1, 1)))
	var range_m: float = Perception._view_range(player, player.has_light_on(), player.light_view(), player.laser_on)
	range_m *= float(enemy._arch.get("view", 1.0)) * float(Balance.AI_VIEW_STANCE_SCALE[player.stance_key()]) * Balance.lab_number("perception", "view")
	var visible: bool = Perception.can_see(get_world_3d(), eye, forward, player, [enemy.get_rid()], float(enemy._arch.get("view", 1.0)))
	var reason: String = "Есть линия видимости"
	if not visible:
		if to.length() > 2.0 and angle > Balance.lab_number("perception", "half_angle"):
			reason = "Цель вне угла обзора"
		elif to.length() > range_m:
			reason = "Цель дальше игровой дальности зрения"
		else:
			reason = "Линию зрения перекрывает преграда"
	return {"visible": visible, "range": range_m, "distance": to.length(), "angle": angle, "reason": reason, "point": point}


func _physics_process(delta: float) -> void:
	if not is_instance_valid(enemy):
		return
	if fixed_observer:
		enemy.position = Vector3(0, 0.03, 18)
		enemy._facing = PI + deg_to_rad(enemy_yaw)
		enemy.velocity = Vector3.ZERO
	if not allow_fire:
		enemy._shot_t = 10.0
	_notice_time += delta
	if enemy._seen_now and _acquired_after < 0.0:
		_acquired_after = _notice_time
	_view = diagnose()


func _lab_tick(delta: float) -> void:
	if not is_instance_valid(enemy) or _view.is_empty():
		return
	_draw_timer -= delta
	if _draw_timer <= 0.0:
		_draw_timer = 0.1
		_draw_overlay()
	var state: String = ["Патруль", "Проверяет шум", "Бой", "Ищет цель", "Отступает", "Мёртв", "Ранен", "Спасает"][enemy.state]
	telemetry.text = "ЗРЕНИЕ И СЛУХ\n%s\nДистанция: %.1f м · предел: %.1f м\nОтклонение: %.1f° · половина обзора: %.1f°\nОбнаружение: %.0f%% · состояние: %s\nЦель замечена за: %s · память: %.1f с\n%s\nПоследняя известная точка: %s\nF8 — увидеть конус сверху; зелёный луч — видно, красный — нет." % [
		String(_view.reason), float(_view.distance), float(_view.range), float(_view.angle), Balance.lab_number("perception", "half_angle"),
		clampf(enemy.notice_timer, 0, 1) * 100.0, state, "%.2f с" % _acquired_after if _acquired_after >= 0.0 else "ещё не замечена", enemy.memory_timer,
		_heard, str(enemy.last_known)]


func _draw_overlay() -> void:
	_mesh.clear_surfaces()
	_mesh.surface_begin(Mesh.PRIMITIVE_LINES)
	var center: Vector3 = enemy.position + Vector3(0, 0.07, 0)
	var radius: float = float(_view.range)
	var half: float = deg_to_rad(Balance.lab_number("perception", "half_angle"))
	var yaw: float = enemy._facing
	_mesh.surface_set_color(Color(1.0, 0.75, 0.2))
	for index: int in range(32):
		var a: float = yaw - half + 2.0 * half * float(index) / 32.0
		var b: float = yaw - half + 2.0 * half * float(index + 1) / 32.0
		_mesh.surface_add_vertex(center + Vector3(sin(a), 0, cos(a)) * radius)
		_mesh.surface_add_vertex(center + Vector3(sin(b), 0, cos(b)) * radius)
	for a: float in [yaw - half, yaw + half]:
		_mesh.surface_add_vertex(center)
		_mesh.surface_add_vertex(center + Vector3(sin(a), 0, cos(a)) * radius)
	_mesh.surface_set_color(Color(0.2, 1.0, 0.35) if bool(_view.visible) else Color(1.0, 0.2, 0.15))
	_mesh.surface_add_vertex(enemy._eye())
	_mesh.surface_add_vertex(_view.point as Vector3)
	_mesh.surface_end()
