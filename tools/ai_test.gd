extends Node
## Мародёр без рук на рейдовой карте ТЦ (mall_map): дверь открывается по F; мародёр спиной к игроку не видит, но слышит
## бег — идёт проверять, видит, бой, стреляет; игрок стреляет в ответ (вид из глаз — взгляд на мародёра).
## Печатает [ok]/[FAIL] и состояния; код выхода — число провалов. С окном — ещё снимок docs/screens/ai_combat.png.
## tools/godot.cmd --headless res://tools/ai_test.tscn

const LEVEL := "res://scenes/levels/mall_map.tscn"
## Площадь к югу от ТЦ: ровная земля, вдоль ±X свободно 80 м (днём видно 100 м).
const OPEN := Vector2(90.0, 150.0)
## Мародёр стоит в стольких метрах от игрока спиной к нему (бег слышно на Balance.NOISE_STEP.sprint).
const LISTEN_M := 9.0
## Створка уже — обрезок (у черновика ТЦ есть двери по 8–11 см), такую не берём.
const DOOR_MIN_W := 0.8

var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node = load(LEVEL).instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	# своих мародёров карты убираем: проверяем одного, без помощников
	for n in level.get_node("Marauders").get_children():
		n.queue_free()
	await get_tree().physics_frame
	var player := get_tree().get_first_node_in_group("players") as Player
	player.health.hp = 100000.0  # чтобы дожить до проверки своих выстрелов
	player.health.head_protected = func() -> bool: return true
	# дверь: встать в зону, нажать F, проверить, что открылась
	var door := _door()
	_check("на карте есть дверь без замка", door != null, "")
	if door:
		player.global_position = _door_stand(door) + Vector3.UP * 0.05
		await get_tree().physics_frame
		await get_tree().physics_frame
		Input.action_press("interact")
		await get_tree().process_frame
		Input.action_release("interact")
		await _wait(0.5)
		_check("дверь открывается по F", door.is_open, "%s, угол створки %.0f°" % [door.get_path(), rad_to_deg(door.get_node("Leaf").rotation.y)])
	# мародёр в LISTEN_M м от игрока на открытой площади, спиной к нему — увидеть не может, но услышит бег
	var spot := _ground(OPEN)
	player.global_position = spot + Vector3(0, 0.1, 0)
	player.velocity = Vector3.ZERO
	var m := (preload("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	m.name = "Listener"
	m.archetype = "gunner"
	m.weapon = "rifle"
	level.get_node("Marauders").add_child(m)
	m.global_position = spot + Vector3(LISTEN_M, 0.1, 0)
	m.patrol_point_provider = func() -> Vector3: return m.global_position
	m._facing = atan2(1.0, 0.0)
	m.state = Marauder.State.PATROL
	for i in range(3):
		await get_tree().physics_frame
	_check("мародёр спиной к игроку — не видит", not _sees(m, player), "%s, %.1f м" % [_state(m), m.global_position.distance_to(player.global_position)])
	# бег от мародёра 1.5 с — шум шагов
	_face(Vector3.LEFT)
	Input.action_press("move_forward")
	Input.action_press("sprint")
	await _wait(1.5)
	Input.action_release("move_forward")
	Input.action_release("sprint")
	_check("услышал бег — идёт проверять (или уже бой)", m.state in [Marauder.State.INVESTIGATE, Marauder.State.COMBAT],
		"%s, до игрока по памяти %.1f м" % [_state(m), m.last_known.distance_to(player.global_position)])
	# повернулся, увидел — бой и стрельба
	var t := 0.0
	while t < 10.0 and not (m.state == Marauder.State.COMBAT and player.health.hp < 100000.0):
		await _wait(0.25)
		t += 0.25
	_check("увидел — бой, стреляет", m.state == Marauder.State.COMBAT and player.health.hp < 100000.0,
		"%s через %.1f с, у игрока %d, до игрока %.1f м" % [_state(m), t, int(player.health.hp), m.global_position.distance_to(player.global_position)])
	if DisplayServer.get_name() != "headless":
		await get_tree().process_frame
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/ai_combat.png"))
	# игрок стреляет: взгляд — на грудь мародёра
	var health := m.get_node("Health") as Health
	var hp0 := health.hp
	var ammo0 := player.ammo
	for i in range(8):
		if m.state in [Marauder.State.DEAD, Marauder.State.DOWNED]:
			break
		_aim(player, m.global_position + Vector3.UP * (0.8 if m.crouched else 1.2))
		await get_tree().physics_frame
		await get_tree().physics_frame
		Input.action_press("fire")
		await _wait(0.3)
		Input.action_release("fire")
		await get_tree().process_frame
	_check("игрок стреляет и попадает", health.hp < hp0 or m.state in [Marauder.State.DEAD, Marauder.State.DOWNED],
		"здоровье мародёра %d → %d, патронов %d → %d, %s; прямой луч: %s" % [int(hp0), int(health.hp), ammo0, player.ammo, _state(m), _probe(player, m)])
	print("ai_test: провалено %d" % _fails)
	get_tree().quit(_fails)


## Дверь без ключа и питания в человеческий рост, перед которой можно встать (место у двери — на навигации; сетка
## путей лежит на полметра выше пола).
func _door() -> Door:
	var map: RID = get_viewport().get_world_3d().navigation_map
	for n in get_tree().get_nodes_in_group("doors"):
		var d := n as Door
		if d == null or d.is_open or d.required_key != "" or d.required_switch != "" or d.width < DOOR_MIN_W:
			continue
		var at := _door_stand(d)
		var nav := NavigationServer3D.map_get_closest_point(map, at)
		if Vector2(nav.x - at.x, nav.z - at.z).length() < 0.3 and absf(nav.y - at.y) < 1.0:
			return d
	return null


## Где встать, чтобы открыть дверь: напротив середины створки, в 0,9 м от неё.
func _door_stand(d: Door) -> Vector3:
	return d.global_position + d.global_basis.x * (d.width * 0.5) + d.global_basis.z * 0.9


## Повернуть взгляд игрока по направлению dir (вид из глаз: CameraRig._look_yaw → Player.look_yaw; сверху — камера).
func _face(dir: Vector3) -> void:
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	rig.rotation.y = atan2(-dir.x, -dir.z)
	rig._look_yaw = atan2(dir.x, dir.z)
	rig._look_pitch = 0.0


## Взгляд из глаз игрока — на точку (курс и наклон камеры: вперёд = (cos н · sin к, sin н, cos н · cos к)).
func _aim(p: Player, at: Vector3) -> void:
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	var dir := (at - p.view_eye()).normalized()
	rig._look_yaw = atan2(dir.x, dir.z)
	rig._look_pitch = asin(clampf(dir.y, -1.0, 1.0))
	rig.rotation.y = atan2(-dir.x, -dir.z)


## Точка карты по углу и радиусу (SectorBuilder.polar) — на земле: рельеф территории не на нуле.
func _ground(ar: Vector2) -> Vector3:
	var p := SectorBuilder.polar(ar.x, ar.y)
	var hit := get_viewport().get_world_3d().direct_space_state.intersect_ray(
		PhysicsRayQueryParameters3D.create(p + Vector3.UP * 60.0, p + Vector3.DOWN * 60.0, 1))
	return hit.position as Vector3 if not hit.is_empty() else p


func _probe(p: Player, m: Marauder) -> String:
	var from := p.view_eye()
	var to := m.global_position + Vector3.UP * 1.2
	var ex: Array[RID] = [p.get_rid()]
	var rng := RandomNumberGenerator.new()
	var hit := Hitscan.fire(p.get_world_3d(), from, (to - from).normalized(), 0.0, 60.0, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_MARAUDER, 0.0, ex, rng)
	if hit.has("collider"):
		return "%s на %.1f м" % [hit.collider.name, from.distance_to(hit.position)]
	return "промах"


func _sees(m: Marauder, p: Player) -> bool:
	var eye := m.global_position + Vector3.UP * Marauder.EYE_HEIGHT
	var fwd := Vector3(sin(m._facing), 0.0, cos(m._facing))
	var ex: Array[RID] = [m.get_rid()]
	return Perception.can_see(m.get_world_3d(), eye, fwd, p, ex)


func _state(m: Marauder) -> String:
	return Marauder.State.keys()[m.state] if is_instance_valid(m) else "нет"


func _wait(sec: float) -> void:
	await get_tree().create_timer(sec).timeout


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
