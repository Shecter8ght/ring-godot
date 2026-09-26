extends Node
## Постановочная запись настоящего игрового цикла. Монтаж вырезает перестановку участников.
## Профиль отдельный; баланс и сцена уровня на диске не меняются.

const OUT: String = "res://export/trailer/"
var _level: Node3D
var _player: Player
var _rig: CameraRig
var _enemy: Marauder
var _track_enemy: bool = false
var _marks: Dictionary = {}
var _cinema: Camera3D


func _ready() -> void:
	seed(270926)
	Profile.use_file("user://trailer_capture_test.json", true)
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "dusk", "weather": "clear", "power": "on"}
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT))
	await get_tree().process_frame
	_level = (load("res://scenes/levels/f1_ring.tscn") as PackedScene).instantiate() as Node3D
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	while _level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	_player = get_tree().get_first_node_in_group("players") as Player
	_rig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	# Для повторяемого дубля оператор не погибает до обыска и выхода.
	_player.health.invulnerable = true
	for enemy: Node in get_tree().get_nodes_in_group("marauders"):
		enemy.queue_free()
	await _wait(0.5)
	await _teleport(Vector3(-5.0, 0.1, -145.0))
	await _press("weapon_2")
	_player.inventory.equipment["primary"] = _player._base_entry(_player.weapon_slot).duplicate(true)
	_cinema = Camera3D.new()
	_cinema.fov = 55.0
	_cinema.far = 1000.0
	_level.add_child(_cinema)
	_cinema.current = true
	_cinema.global_position = Vector3(35, 52, -192)
	_cinema.look_at(Vector3(0, 7, -75))
	await _wait(1.0)
	_mark("establish")
	for frame: int in range(150):
		var t: float = float(frame) / 149.0
		_cinema.global_position = Vector3(35, 52, -192).lerp(Vector3(18, 43, -169), t)
		_cinema.look_at(Vector3(0, 7, -75))
		await get_tree().process_frame
	await _shot("establish")
	_cinema.current = false
	_rig._camera.current = true
	await _teleport(SectorBuilder.polar(-108.0, 72.0) + Vector3.UP * 0.1)
	_rig._distance = 24.0
	_rig.rotation.y = 0.0
	await _wait(1.0)
	_mark("approach")
	Input.action_press("move_right")
	await _wait(2.0)
	Input.action_release("move_right")
	await _shot("approach")
	await _wait(1.0)
	# Противник замечает игрока обычным зрением; стрельба и урон настоящие.
	CameraRig.first_person_mode = true
	await _teleport(SectorBuilder.polar(-108.0, 72.0) + Vector3.UP * 0.1)
	await _wait(0.3)
	_enemy = (load("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	_enemy.weapon = "pistol"
	_enemy.archetype = "scout"
	_enemy.position = SectorBuilder.polar(-99.0, 72.0) + Vector3.UP * 0.1
	_level.add_child(_enemy)
	_enemy._facing = atan2(_player.global_position.x - _enemy.global_position.x, _player.global_position.z - _enemy.global_position.z)
	_track_enemy = true
	await _wait(0.7)
	_mark("combat")
	await _wait(1.2)
	Input.action_press("aim")
	await _wait(0.6)
	for burst: int in range(5):
		Input.action_press("fire")
		await _wait(0.19)
		Input.action_release("fire")
		await _wait(0.55)
		if burst == 1:
			await _shot("combat")
	Input.action_release("aim")
	_track_enemy = false
	print("TRAILER combat enemy_hp=", _enemy._health.hp, " state=", _enemy.state)
	await _wait(1.5)
	await _shot("combat_end")
	_enemy.queue_free()
	CameraRig.first_person_mode = false
	var safe: LootContainer = _level.get_node("Interactables/JewelrySafe") as LootContainer
	await _teleport(safe.global_position - safe.global_basis.z * 1.2)
	_player.inventory.add("keycard_security", 1)
	_player.inventory.add("bandage", 2)
	await _wait(1.0)
	_mark("search")
	await _press("interact")
	await _wait(safe.search_s + 0.4)
	_mark("loot")
	await _shot("loot")
	await _wait(2.0)
	Input.warp_mouse(Raid.current.ui._take_all.get_global_rect().get_center())
	Raid.current.ui._take_all.pressed.emit()
	await _wait(1.0)
	print("TRAILER loot value=", _player.inventory.value(), " looting=", Raid.current.ui.is_looting())
	Raid.current.ui.close_all()
	var exit_point: ExtractionPoint = _level.get_node("Extractions/GarageExit") as ExtractionPoint
	_rig._distance = 28.0
	_rig.rotation.y = deg_to_rad(45.0)
	await _teleport(exit_point.global_position + Vector3(5.5, 0, 0))
	await _wait(1.0)
	_mark("exit_approach")
	# Подход к зоне через штатное движение от первого лица.
	CameraRig.first_person_mode = true
	await _wait(0.2)
	_rig._look_yaw = -PI * 0.5
	Input.action_press("move_forward")
	await _wait(0.9)
	Input.action_release("move_forward")
	CameraRig.first_person_mode = false
	await _wait(0.3)
	_mark("evac")
	await _shot("evac")
	await _wait(exit_point.channel_s + 1.0)
	_mark("result")
	await _shot("result")
	print("TRAILER extracted=", Raid.current.is_extracted(1), " loot=", Raid.current.loot_value)
	await _wait(3.0)
	_mark("end")
	FileAccess.open(OUT + "markers.json", FileAccess.WRITE).store_string(JSON.stringify(_marks, "\t"))
	get_tree().quit()


func _process(_delta: float) -> void:
	if _track_enemy and is_instance_valid(_enemy) and _enemy._health.alive:
		var delta: Vector3 = _enemy.global_position + Vector3.UP * 1.15 - _player.eye_position()
		_rig._look_yaw = atan2(delta.x, delta.z)
		_rig._look_pitch = atan2(delta.y, Vector2(delta.x, delta.z).length())
		_player._recoil = 0.0
		_player._recoil_h = 0.0


func _mark(label: String) -> void:
	_marks[label] = {"frame": Engine.get_frames_drawn(), "time": float(Engine.get_frames_drawn()) / 30.0}
	print("TRAILER ", label, " ", _marks[label])


func _shot(label: String) -> void:
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_jpg(ProjectSettings.globalize_path(OUT + label + ".jpg"), 0.92)


func _wait(seconds: float) -> void:
	await get_tree().create_timer(seconds).timeout


func _teleport(point: Vector3) -> void:
	_player.global_position = point + Vector3.UP * 0.05
	_player.velocity = Vector3.ZERO
	_rig.global_position = point
	await _wait(0.15)


func _press(action: String) -> void:
	var event: InputEventAction = InputEventAction.new()
	event.action = action
	event.pressed = true
	Input.parse_input_event(event)
	await get_tree().process_frame
	await get_tree().process_frame
	event = InputEventAction.new()
	event.action = action
	event.pressed = false
	Input.parse_input_event(event)
