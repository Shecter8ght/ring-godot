extends "res://tools/perf_test.gd"
## Производительность Zone02: пять фиксированных точек, штатные ISO и ADS, 24 неподвижных AI.
## tools/godot.cmd --disable-vsync res://tools/zone02_perf_test.tscn

const LEVEL_PATH: String = "res://scenes/levels/zone02_urban_belt.tscn"
const REQUIRED_AI_COUNT: int = 24
const READY_TIMEOUT_MS: int = 120000
const AIM_TIMEOUT_MS: int = 5000
## Курс взгляда — в градусах от севера по часовой стрелке; Y определяется физическим полом.
const ZONE02_SPOTS: Array[Dictionary] = [
	{"name": "жилой двор", "xz": Vector2(-515, -365), "yaw": 180.0},
	{"name": "магазин", "xz": Vector2(20, -175), "yaw": 0.0},
	{"name": "администрация", "xz": Vector2(0, 245), "yaw": 180.0},
	{"name": "автостанция", "xz": Vector2(400, 240), "yaw": 0.0},
	{"name": "гаражи", "xz": Vector2(410, -377), "yaw": 90.0},
]

var _level: Node3D


func _ready() -> void:
	Profile.use_file("user://profile_zone02_perf_test.json", true)
	Profile.pending_raid = false
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	CameraRig.first_person_mode = false
	Input.action_release("aim")
	await _frames(1)
	_level = (load(LEVEL_PATH) as PackedScene).instantiate() as Node3D
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	var player: Player = Raid.current.local_player()
	var rig: CameraRig = _level.get_node("CameraRig") as CameraRig
	CameraRig.first_person_mode = false
	if player == null or rig == null:
		_fail("Player или CameraRig не созданы")
		return
	player.health.invulnerable = true
	if not await _wait_for_world():
		_fail("таймаут готовности: nav=%s, AI=%d/%d" % [str(_level.get("_nav_baked")), _level.get_node("Marauders").get_child_count(), REQUIRED_AI_COUNT])
		return
	for enemy: Node in _level.get_node("Marauders").get_children():
		var marauder: Marauder = enemy as Marauder
		marauder.set_physics_process(false)
		marauder.velocity = Vector3.ZERO
	# Мышь не меняет фиксированный курс во время замера; игровой процесс камеры остаётся включён.
	rig.set_process_unhandled_input(false)
	print("zone02_perf: %s | day clear power on | AI=%d (physics off)" % [LEVEL_PATH, REQUIRED_AI_COUNT])
	print("  %-18s %7s %7s %-4s %7s %8s %8s %10s" % ["точка", "X", "Z", "mode", "FPS", "draw", "objects", "prims"])
	for spot: Dictionary in ZONE02_SPOTS:
		var xz: Vector2 = spot.xz
		var hit: Dictionary = _floor_hit(xz)
		if hit.is_empty() or (hit.normal as Vector3).y < 0.7:
			_fail("не найден пол: %s %s" % [spot.name, str(xz)])
			return
		player.global_position = (hit.position as Vector3) + Vector3.UP * 0.05
		player.velocity = Vector3.ZERO
		var yaw: float = deg_to_rad(float(spot.yaw))
		rig.rotation.y = -yaw
		rig.global_position = player.global_position
		for mode: String in ["ISO", "ADS"]:
			var ads: bool = mode == "ADS"
			if not await _aim_mode(rig, ads):
				_fail("CameraRig не перешёл в %s" % mode)
				return
			if ads:
				# Штатный вход в ADS берёт курс корпуса, до этого следовавшего за курсором.
				rig._look_yaw = PI - yaw
				rig._look_pitch = 0.0
			else:
				Input.warp_mouse(get_viewport().get_visible_rect().size * 0.5)
			await _frames(WARM_FRAMES)
			var result: Dictionary = await _measure()
			print("  %-18s %7.1f %7.1f %-4s %7.1f %8d %8d %10d" % [spot.name, xz.x, xz.y, mode, result.fps, result.draw, result.objects, result.prims])
			Input.action_release("aim")
			await _frames(10)
	get_tree().quit(0)


func _wait_for_world() -> bool:
	var start_ms: int = Time.get_ticks_msec()
	while not bool(_level.get("_nav_baked")) or _level.get_node("Marauders").get_child_count() != REQUIRED_AI_COUNT:
		if Time.get_ticks_msec() - start_ms > READY_TIMEOUT_MS:
			return false
		await _frames(1)
	return true


func _aim_mode(rig: CameraRig, ads: bool) -> bool:
	if ads:
		Input.action_press("aim")
	else:
		Input.action_release("aim")
	var start_ms: int = Time.get_ticks_msec()
	while rig.ads_active != ads:
		if Time.get_ticks_msec() - start_ms > AIM_TIMEOUT_MS:
			return false
		await _frames(1)
	return true


func _floor_hit(xz: Vector2) -> Dictionary:
	# height_at задаёт общий уклон; луч под крышами уточняет площадку, пол здания или тротуар.
	var terrain_y: float = UrbanTerrain.height_at(xz.x, xz.y)
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(Vector3(xz.x, terrain_y + 3.0, xz.y), Vector3(xz.x, terrain_y - 8.0, xz.y), Hitscan.LAYER_WORLD)
	return _level.get_world_3d().direct_space_state.intersect_ray(query)


func _fail(message: String) -> void:
	Input.action_release("aim")
	push_error("zone02_perf: " + message)
	get_tree().quit(1)
