extends Node
## Выход в рейд пешком: запечённого света нет; дверь тамбура закрыта — не пройти, открыта — коридор;
## по лестнице игрок выходит во двор на землю; план не принят — зона сбора не запускает рейд; принят и
## все в зоне — отсчёт и рейд; вышел из зоны — отсчёт сброшен.
## tools/godot.cmd --headless res://tools/shelter_exit_test.tscn

var _fails: int = 0
var _level: Node
var _me: Player


func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://shelter_exit_test.json", true)
	Profile.modules.generator = 1
	Profile.next_conditions = {"time": "day", "weather": "clear", "power": "on"}
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	await _frames(150)
	_level = get_tree().current_scene
	_me = _level.get("_me") as Player if _level.get("_me") != null else _level.get("_player") as Player
	var ground: float = float(Balance.SHELTER_YARD.ground)
	_check("запечённого света в сцене нет", _level.get_node_or_null("LightmapGI") == null and not DirAccess.dir_exists_absolute("res://levels/shelter/lightmap"))
	var env: Environment = (_level.get_node("WorldEnvironment") as WorldEnvironment).environment
	_check("свет уличный: небо фоном, солнце с тенью", env.background_mode == Environment.BG_SKY and env.sky != null
		and (_level.get_node("Lights/Sun") as DirectionalLight3D).shadow_enabled)
	var door: ShelterExitDoor = _level.find_child("ExitDoor", true, false) as ShelterExitDoor
	var zone: RaidStartZone = get_tree().get_first_node_in_group("raid_start_zones") as RaidStartZone
	_check("двор собран: дверь, зона сбора, земля", door != null and zone != null and _level.find_child("Ground", true, false) != null)
	if door == null or zone == null:
		_finish()
		return
	# закрытая дверь не пускает
	_me.global_position = Vector3(0.0, 0.1, 10.2)
	await _frames(10)
	await _walk_south(2.5)
	_check("дверь закрыта — дальше тамбура не пройти", _me.global_position.z < 11.7, "z %.2f" % _me.global_position.z)
	door.request_use()
	await get_tree().create_timer(float(Balance.SHELTER_YARD.door_sec) + 0.4).timeout
	_check("дверь открылась", door.opened and absf((door.get_node("Leaf") as Node3D).rotation_degrees.y - float(Balance.SHELTER_YARD.door_open_deg)) < 2.0)
	# коридор и лестница: вышел во двор, стоит на земле
	_me.global_position = Vector3(-0.3, 0.1, 10.2)
	await _frames(5)
	await _walk_south(7.0)
	_check("через дверь, коридор и лестницу — на землю двора", _me.global_position.z > 21.0 and absf(_me.global_position.y - ground) < 0.25,
		"z %.2f y %.2f" % [_me.global_position.z, _me.global_position.y])
	# в зоне без плана — рейд не начинается
	_me.global_position = zone.global_position + Vector3(0.5, 0.1, 0.0)
	await get_tree().create_timer(float(Balance.SHELTER_YARD.countdown_sec) + 1.0).timeout
	_check("план не принят — стоим в зоне, рейда нет", get_tree().current_scene == _level and float(_level.get("_start_left")) < 0.0)
	# план принят, но игрок не в зоне
	_me.global_position = Vector3(0.0, ground + 0.1, 30.0)
	_level.call("accept_raid_plan", true)
	await get_tree().create_timer(1.0).timeout
	_check("план принят, игрок не в зоне — отсчёта нет", bool(_level.get("raid_plan_accepted")) and float(_level.get("_start_left")) < 0.0)
	# зашёл в зону — отсчёт; вышел — сброс
	_me.global_position = zone.global_position + Vector3(0.5, 0.1, 0.0)
	await get_tree().create_timer(1.2).timeout
	_check("в зоне с принятым планом — идёт отсчёт", float(_level.get("_start_left")) > 0.0, "%.1f" % float(_level.get("_start_left")))
	_me.global_position = Vector3(0.0, ground + 0.1, 30.0)
	await get_tree().create_timer(0.5).timeout
	_check("вышел из зоны — отсчёт сброшен", float(_level.get("_start_left")) < 0.0)
	_me.global_position = zone.global_position + Vector3(0.5, 0.1, 0.0)
	await get_tree().create_timer(float(Balance.SHELTER_YARD.countdown_sec) + 1.5).timeout
	var now: Node = get_tree().current_scene
	_check("отсчёт вышел — загружается рейд", now != _level and Profile.pending_raid, "" if now == null else now.scene_file_path)
	_finish()


## Идти на юг (к выходу) sec секунд: взгляд — на юг, «вперёд».
func _walk_south(sec: float) -> void:
	var rig: CameraRig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	CameraRig.first_person_mode = true
	await _frames(3)
	rig._look_yaw = 0.0
	rig._look_pitch = 0.0
	await _frames(3)
	Input.action_press("move_forward")
	await get_tree().create_timer(sec).timeout
	Input.action_release("move_forward")
	await _frames(15)


func _finish() -> void:
	print("shelter_exit_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _check(what: String, ok: bool, note: String = "") -> void:
	print("[%s] %s %s" % ["ok" if ok else "ПРОВАЛ", what, note])
	if not ok:
		_fails += 1


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame
