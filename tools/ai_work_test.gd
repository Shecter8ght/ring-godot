extends Node3D
## Повторные цели не сбрасывают путь; снимок освещения общий, луч у каждого наблюдателя свой.

class NavigationProbe extends Marauder:
	var snaps: int = 0
	var covers: int = 0
	var fire_checks: int = 0
	var shots: int = 0

	func _ready() -> void:
		set_process(false)
		set_physics_process(false)

	func _snap(point: Vector3) -> Vector3:
		snaps += 1
		return Vector3(point.x, 0.0, point.z)

	func _cover_point(_radius: float, _far: bool) -> Vector3:
		covers += 1
		return Vector3.INF

	func _line_of_fire() -> bool:
		fire_checks += 1
		return super._line_of_fire()

	func _shoot(_suppress: bool) -> void:
		shots += 1


class AtmosphereProbe extends RaidAtmosphere:
	var calls: int = 0

	func view_distance(_position: Vector3, _light: bool, _strength: float = 1.0, _laser: bool = false) -> float:
		calls += 1
		return 30.0


var _fails: int = 0
var _vision_phase: int = 0
var _vision_done: bool = false
var _target: StaticBody3D
var _atmosphere: AtmosphereProbe
var _first_calls: int = 0


func _ready() -> void:
	Profile.use_file("user://ai_work_test.json", true)
	RaidConditions.current = {"time": "day", "weather": "clear", "power": "on"}
	var probe: NavigationProbe = NavigationProbe.new()
	var agent: NavigationAgent3D = NavigationAgent3D.new()
	agent.name = "NavigationAgent3D"
	probe.add_child(agent)
	var health: Health = Health.new()
	health.name = "Health"
	probe.add_child(health)
	var body: Node3D = Node3D.new()
	body.name = "Body"
	probe.add_child(body)
	var muzzle: OmniLight3D = OmniLight3D.new()
	muzzle.name = "Muzzle"
	body.add_child(muzzle)
	add_child(probe)
	var region: NavigationRegion3D = NavigationRegion3D.new()
	var mesh: NavigationMesh = NavigationMesh.new()
	mesh.vertices = PackedVector3Array([Vector3(-10, 0, -10), Vector3(-10, 0, 10), Vector3(10, 0, 10), Vector3(10, 0, -10)])
	mesh.add_polygon(PackedInt32Array([0, 1, 2, 3]))
	region.navigation_mesh = mesh
	add_child(region)
	for frame: int in range(4):
		await get_tree().physics_frame
	Marauder.work_profile_enabled = true
	Marauder.work_profile.clear()
	for index: int in range(100):
		probe._set_move_target(Vector3(4, 0, 0), true)
	_check("сто одинаковых целей — одна проекция и одна команда пути", probe.snaps == 1 and int(Marauder.work_profile.target_set.count) == 1)
	probe._set_move_target(Vector3(5, 0, 0), true)
	_check("движение цели обновляет путь", probe.snaps == 2 and agent.target_position == Vector3(5, 0, 0))
	agent.target_position = Vector3(-4, 0, 0)
	probe._set_move_target(Vector3(5, 0, 0), true)
	_check("чужая команда не оставляет старый результат", probe.snaps == 3 and agent.target_position == Vector3(5, 0, 0))
	var iteration: int = NavigationServer3D.map_get_iteration_id(get_world_3d().navigation_map)
	region.position.x = 0.5
	while NavigationServer3D.map_get_iteration_id(get_world_3d().navigation_map) == iteration:
		await get_tree().physics_frame
	probe._set_move_target(Vector3(5, 0, 0), true)
	_check("изменение навигации отменяет проекцию", probe.snaps == 4)
	Marauder.work_profile.clear()
	for index: int in range(100):
		probe._set_move_target(Vector3.ZERO)
	_check("остановка не сбрасывает путь каждый кадр", int(Marauder.work_profile.target_set.count) == 1)
	Marauder.work_profile_enabled = false
	# Смена геометрии может дать несколько асинхронных итераций карты.
	for frame: int in range(8):
		await get_tree().physics_frame
	probe.last_known = Vector3(0, 0, 8)
	for frame: int in range(5):
		probe._try_cover(10.0, false)
		await get_tree().physics_frame
	_check("нет укрытия — короткий повтор использует прежний результат", probe.covers == 1)
	probe.last_known.x += 2.0
	probe._try_cover(10.0, false)
	_check("новая угроза сразу повторяет поиск укрытия", probe.covers == 2)
	probe._try_cover(10.0, true)
	_check("отступление сразу ищет укрытие", probe.covers == 3)
	await get_tree().create_timer(float(Balance.AI_WORK.cover_retry_sec) + 0.05).timeout
	probe._try_cover(10.0, false)
	_check("неудачный поиск укрытия возобновляется", probe.covers == 4)
	probe.position.x += 1.0
	probe._try_cover(10.0, false)
	_check("сдвинулся сам — поиск укрытия сразу обновляется", probe.covers == 5)
	probe._try_cover(11.0, false)
	_check("другой радиус — отдельный поиск укрытия", probe.covers == 6)
	probe.position = Vector3.ZERO
	var phases: Dictionary = {}
	for slot: int in range(int(Balance.AI_WORK.phase_slots)):
		var delay: float = probe._next_work_delay(-float(slot) / float(Balance.AI_WORK.phase_slots) * 0.5, 0.5)
		phases[roundi(delay * 1000000.0)] = true
	_check("периодические проверки занимают разные моменты", phases.size() == int(Balance.AI_WORK.phase_slots))
	_atmosphere = AtmosphereProbe.new()
	add_child(_atmosphere)
	_target = _obstacle(Vector3(0, 1.3, -5), Vector3(0.5, 2.6, 0.5), Hitscan.LAYER_MARAUDER)
	# Для второго наблюдателя есть стена, первый смотрит на цель сбоку от неё.
	_obstacle(Vector3(1.5, 1.3, -2.5), Vector3(0.4, 3.0, 0.8), Hitscan.LAYER_WORLD)
	for frame: int in range(3):
		await get_tree().physics_frame
	_vision_phase = 1
	while not _vision_done:
		await get_tree().process_frame
	Perception.work_profile_enabled = false
	# Стрельба проверяет реальную стену заново даже после общего снимка зрения.
	var fire_wall: StaticBody3D = _obstacle(Vector3(0, 1.3, -2.5), Vector3(1.0, 3.0, 0.4), Hitscan.LAYER_WORLD)
	probe.last_known = Vector3(0, 0, -5)
	probe._spec = {"class": "PISTOL", "burst": 1, "interval": 0.2, "burst_pause": 0.1}
	probe._mag = 3
	probe._shot_t = 1.0
	await get_tree().physics_frame
	probe._try_fire()
	_check("оружие ещё не готово — лишний луч не нужен", probe.fire_checks == 0 and probe.shots == 0)
	probe._shot_t = 0.0
	probe._try_fire()
	_check("готовое оружие не стреляет сквозь стену", probe.fire_checks == 1 and probe.shots == 0)
	fire_wall.collision_layer = 0
	await get_tree().physics_frame
	probe._try_fire()
	_check("проход открылся — выстрел разрешён сразу", probe.fire_checks == 2 and probe.shots == 1 and probe._mag == 2)
	fire_wall.collision_layer = Hitscan.LAYER_WORLD
	probe._shot_t = 0.0
	await get_tree().physics_frame
	probe._try_fire()
	_check("проход закрылся — прежнее разрешение не используется", probe.fire_checks == 3 and probe.shots == 1)
	print("ai_work_test: провалов ", _fails)
	get_tree().quit(_fails)


func _physics_process(_delta: float) -> void:
	if _vision_phase == 1:
		Perception.work_profile_enabled = true
		Perception.work_profile.clear()
		var all_seen: bool = true
		for index: int in range(24):
			all_seen = all_seen and Perception.can_see_body(get_world_3d(), Vector3(0, 2.6, 0), Vector3.FORWARD, _target, [])
		_check("видимая цель действительно видна", all_seen)
		_check("24 наблюдателя — один расчёт освещения", _atmosphere.calls == 1 and int(Perception.work_profile.range_calculations) == 1)
		var blocked: bool = Perception.can_see_body(get_world_3d(), Vector3(3, 2.6, 0), Vector3(-3, 0, -5).normalized(), _target, [])
		_check("общий снимок не даёт видеть через стену другого наблюдателя", not blocked and int(Perception.work_profile.rays) == 25)
		RaidConditions.current.power = "off"
		Perception._view_range(_target, false)
		_check("смена условий отменяет общий результат сразу", _atmosphere.calls == 2)
		_target.position.x = -0.5
		Perception._view_range(_target, false)
		_check("движение цели обновляет общие условия", _atmosphere.calls == 3)
		_first_calls = _atmosphere.calls
		_vision_phase = 2
	elif _vision_phase == 2:
		Perception._view_range(_target, false)
		_check("следующий физический шаг получает свежие условия", _atmosphere.calls == _first_calls + 1)
		_vision_phase = 0
		_vision_done = true


func _obstacle(at: Vector3, size: Vector3, collision: int) -> StaticBody3D:
	var body: StaticBody3D = StaticBody3D.new()
	body.collision_layer = collision
	body.position = at
	var shape: CollisionShape3D = CollisionShape3D.new()
	var box: BoxShape3D = BoxShape3D.new()
	box.size = size
	shape.shape = box
	body.add_child(shape)
	add_child(body)
	return body


func _check(label: String, okay: bool) -> void:
	if not okay:
		_fails += 1
	print("%s ai work: %s" % ["OK" if okay else "FAIL", label])
