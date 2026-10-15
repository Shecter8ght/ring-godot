extends Node3D
## Открытое окно выше головы. Десять реальных бросков снаружи, без подсказки траектории.
## -- manual оставляет управляемого игрока с гранатами для ручной пробы стенда.

const CASES: Array[Dictionary] = [
	{"x": 0.0, "distance": 1.2, "ground": 0.0, "power": 0.26},
	{"x": -0.45, "distance": 1.6, "ground": 0.0, "power": 0.30},
	{"x": 0.45, "distance": 2.0, "ground": 0.0, "power": 0.40},
	{"x": 0.0, "distance": 2.6, "ground": 0.0, "power": 0.50},
	{"x": -0.6, "distance": 3.2, "ground": 0.0, "power": 0.60},
	{"x": 0.6, "distance": 4.0, "ground": 0.0, "power": 0.72},
	{"x": 0.0, "distance": 4.8, "ground": 0.0, "power": 0.82},
	{"x": -0.35, "distance": 1.8, "ground": -0.30, "power": 0.40},
	{"x": 0.35, "distance": 2.8, "ground": 0.20, "power": 0.50},
	{"x": 0.0, "distance": 3.8, "ground": -0.20, "power": 0.72},
]
var _player: Player
var _camera: CameraRig
var _fails: int = 0
var _results: Array[Dictionary] = []


func _ready() -> void:
	Engine.max_fps = 60
	Profile.use_file("user://profile_grenade_window_test.json", true)
	Profile.ensure()
	Profile.pending_raid = false
	RaidEvents.enabled = false
	_camera = (load("res://scenes/player/camera_rig.tscn") as PackedScene).instantiate() as CameraRig
	add_child(_camera)
	_player = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	_player.name = "Player_1"
	_player.position = Vector3(0, 0.02, 2.6)
	add_child(_player)
	_player.health.invulnerable = true
	_player.grenades = 100
	_player._equip_grenade()
	_camera.set_target(_player)
	# Первый вход в FPS берёт курс тела. После него ставим заданный взгляд на окно.
	for frame: int in range(3):
		await get_tree().process_frame
	_look_at_window()
	if "manual" in OS.get_cmdline_user_args():
		print("grenade_window_test: ручная проба; 4 — граната, ПКМ — нижний подброс; низ окна 2,10 м")
		return
	_player.set_physics_process(false)
	get_tree().create_timer(55.0).timeout.connect(func() -> void: get_tree().quit(99))
	for index: int in range(CASES.size()):
		await _case(index, CASES[index])
	var report: Dictionary = {"opening_bottom": ($Window/SillTop as Marker3D).global_position.y,
		"opening_top": ($Window/OpeningTop as Marker3D).global_position.y,
		"opening_width": 1.6, "wall_thickness": 0.24, "failures": _fails, "cases": _results}
	var file: FileAccess = FileAccess.open("res://docs/screens/grenade_window_report.json", FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(report, "\t"))
		file.close()
	print("grenade_window_test: бросков %d, прошли в окно %d, провалено %d" % [CASES.size(), CASES.size() - _fails, _fails])
	for child: Node in get_children():
		child.queue_free()
	for frame: int in range(4):
		await get_tree().process_frame
	get_tree().quit(1 if _fails else 0)


func _look_at_window() -> void:
	var direction: Vector3 = (($Window/Aim as Marker3D).global_position - _player.eye_position()).normalized()
	_player.ads = true
	_player.look_yaw = atan2(direction.x, direction.z)
	_player.look_pitch = asin(direction.y)
	_camera._look_yaw = _player.look_yaw
	_camera._look_pitch = _player.look_pitch


func _case(index: int, setup: Dictionary) -> void:
	($Floor as StaticBody3D).position.y = float(setup.ground) - 0.1
	_player.position = Vector3(float(setup.x), float(setup.ground) + 0.02, float(setup.distance))
	_look_at_window()
	_player.grenade_in_hand = true
	_player.grenade_underhand = true
	_player.grenade_pin = 1.0
	_player.grenade_charge = float(setup.power)
	for frame: int in range(3):
		await get_tree().physics_frame
	if index == 0:
		await _shot("grenade_window_ready")
	var start_count: int = _player.grenade_count()
	_player._throw_grenade()
	var nodes: Array[Node] = get_tree().get_nodes_in_group("thrown_grenades")
	if nodes.size() != 1:
		_fails += 1
		push_error("grenade_window_test: не создан один снаряд")
		return
	var grenade: Grenade = nodes[0] as Grenade
	grenade._damage = false
	grenade.body_entered.connect(func(body: Node) -> void:
		if body.is_in_group("grenade_window_frame"):
			grenade.set_meta("hit_frame", true))
	var launch_speed: float = grenade.linear_velocity.length()
	var peak: float = grenade.global_position.y
	var previous: Vector3 = grenade.global_position
	var front: Vector3 = Vector3.INF
	var back: Vector3 = Vector3.INF
	for frame: int in range(115):
		await get_tree().physics_frame
		if not is_instance_valid(grenade):
			break
		var point: Vector3 = grenade.global_position
		peak = maxf(peak, point.y)
		if front == Vector3.INF and previous.z > 0.12 and point.z <= 0.12:
			front = previous.lerp(point, (previous.z - 0.12) / (previous.z - point.z))
		if previous.z > -0.12 and point.z <= -0.12:
			back = previous.lerp(point, (previous.z + 0.12) / (previous.z - point.z))
			break
		previous = point
	var hit_frame: bool = bool(grenade.get_meta("hit_frame", false)) if is_instance_valid(grenade) else true
	var passed: bool = _inside_opening(front) and _inside_opening(back) and not hit_frame and _player.grenade_count() == start_count - 1
	if not passed:
		_fails += 1
	var result: Dictionary = setup.duplicate()
	result.merge({"shot": index + 1, "eye_y": _player.eye_position().y, "pitch_degrees": rad_to_deg(_player.look_pitch),
		"speed": launch_speed, "front": _point(front), "back": _point(back), "peak": peak,
		"hit_frame": hit_frame, "passed": passed})
	_results.append(result)
	print("[%s] окно %02d: дистанция %.1f, грунт %+.2f, сила %.0f%%, фронт %s, выход %s" % [
		"ok" if passed else "ПРОВАЛ", index + 1, float(setup.distance), float(setup.ground), float(setup.power) * 100.0,
		str(front), str(back)])
	if index == 3 and passed and is_instance_valid(grenade):
		var observer: Camera3D = $Observer as Camera3D
		grenade.freeze = true
		observer.look_at(Vector3(0, 2.55, 0), Vector3.UP)
		observer.current = true
		await _shot("grenade_window_inside")
		_camera._ads_cam.current = true
	if is_instance_valid(grenade):
		grenade.queue_free()
	await get_tree().create_timer(0.7).timeout


func _inside_opening(point: Vector3) -> bool:
	var radius: float = float(Balance.GRENADE_HAND.spawn_radius)
	return point.is_finite() and absf(point.x) < 0.8 - radius and point.y > ($Window/SillTop as Marker3D).global_position.y + radius \
		and point.y < ($Window/OpeningTop as Marker3D).global_position.y - radius


func _point(point: Vector3) -> Array:
	return [point.x, point.y, point.z] if point.is_finite() else []


func _shot(label: String) -> void:
	if DisplayServer.get_name() == "headless":
		return
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png("res://docs/screens/" + label + ".png")
