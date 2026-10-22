extends Node
## Проверяет настоящие поля интерфейса, позу CameraRig, изоляцию черновика, сохранение и F6.

var _fails: int = 0
var _checks: int = 0
var _lab: WeaponPoseLab
var _out: String = ""


func _ready() -> void:
	Engine.max_fps = 90
	WeaponPoseProfiles.storage_path = "user://weapon_pose_lab_test.cfg"
	DirAccess.remove_absolute(WeaponPoseProfiles.storage_path)
	WeaponPoseProfiles.reload()
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("out="):
			_out = argument.substr(4)
	if not _out.is_empty():
		DirAccess.make_dir_recursive_absolute(_out)
	_lab = (load("res://scenes/debug/weapon_pose_lab.tscn") as PackedScene).instantiate() as WeaponPoseLab
	add_child(_lab)
	await _frames(90)
	_check("panel blocks game input", _lab.is_open() and _lab._player.ui_blocked() and not _lab._player.is_physics_processing())
	_check("real viewmodel visible", _lab._rig.ads_active and _lab._rig._viewmodel.visible)
	_check("catalog includes all weapon models and sandbox builds", _lab._catalog.size() > WeaponDb.sandbox().size())
	await _shot("weapon_pose_interface")
	var rifle: String = _lab._player.weapon_id
	var rifle_index: int = _lab._weapon_index
	var initial_x: float = _lab._rig._viewmodel.position.x
	_lab._panel._position[0].value = 12.3
	await _frames(30)
	_check("centimeters become meters", is_equal_approx((WeaponPoseProfiles.values(_lab._draft, rifle, "hip").position as Vector3).x, 0.123))
	_check("real camera pose follows UI", _lab._rig._viewmodel.position.x > initial_x + 0.08)
	var shifted_x: float = _lab._rig._viewmodel.position.x
	await _frames(90)
	_check("offset does not accumulate", absf(_lab._rig._viewmodel.position.x - shifted_x) < 0.025)
	_check("draft does not change saved gameplay poses", WeaponPoseProfiles.active().is_empty())
	await _shot("weapon_pose_shifted")
	await _key(KEY_F7)
	await _frames(30)
	_check("comparison shows original without erasing draft", _lab._rig.weapon_pose_profiles.is_empty() and not _lab._draft.is_empty())
	await _key(KEY_F7)
	await _frames(15)
	_check("comparison returns to draft", _lab._rig.weapon_pose_profiles.has(rifle))
	_lab._select_pose(1)
	_lab._panel._position[2].value = -8.0
	await _frames(60)
	_check("ADS preview works with panel open", _lab._player.aiming and _lab._rig._aim_pose > 0.99)
	_check("ADS offset is separate", is_equal_approx((WeaponPoseProfiles.values(_lab._draft, rifle, "ads").position as Vector3).z, -0.08)
		and is_equal_approx((WeaponPoseProfiles.values(_lab._draft, rifle, "hip").position as Vector3).x, 0.123))
	await _shot("weapon_pose_ads")
	_lab._reset_pose()
	_check("reset changes only selected pose", (WeaponPoseProfiles.values(_lab._draft, rifle, "ads").position as Vector3).is_zero_approx()
		and is_equal_approx((WeaponPoseProfiles.values(_lab._draft, rifle, "hip").position as Vector3).x, 0.123))
	_lab._select_pose(2)
	_lab._panel._position[1].value = 3.0
	await _frames(60)
	_check("lowered pose previews", _lab._player.weapon_lowered > 0.95)
	await _shot("weapon_pose_low")
	_lab._select_stance(2)
	_check("prone selects available hip pose", _lab._pose == "hip" and _lab._player.stance == Player.Stance.PRONE)
	_lab._select_stance(0)
	var pistol_index: int = -1
	for index: int in range(_lab._catalog.size()):
		if String(_lab._catalog[index].id) == "wpn_hg_02":
			pistol_index = index
			break
	_check("pistol available", pistol_index >= 0)
	if pistol_index >= 0:
		_lab._select_weapon(pistol_index)
		await _frames(60)
		_check("other weapon has independent offsets", is_zero_approx(_lab._panel._position[0].value))
		_lab._panel._position[2].value = -5.0
		await _shot("weapon_pose_pistol")
	_lab._select_weapon(rifle_index)
	await _frames(45)
	_check("weapon switch restores draft", is_equal_approx(_lab._panel._position[0].value, 12.3))
	_check("save succeeds", _lab._save())
	WeaponPoseProfiles.reload()
	_check("saved values survive reload", is_equal_approx((WeaponPoseProfiles.values(WeaponPoseProfiles.snapshot(), rifle, "hip").position as Vector3).x, 0.123))
	_lab._panel._position[0].value = 22.0
	_lab._restore()
	_check("restore discards unsaved changes", is_equal_approx(_lab._panel._position[0].value, 12.3) and not _lab._dirty)
	_lab._panel.use_in_game.button_pressed = false
	_lab._save()
	WeaponPoseProfiles.reload()
	_check("gameplay can use defaults without deleting presets", WeaponPoseProfiles.active().is_empty() and not WeaponPoseProfiles.snapshot().is_empty())
	# Оси, границы и плавное смешивание проверяются независимо от дыхания и отдачи.
	var profiles: Dictionary = {}
	WeaponPoseProfiles.put(profiles, rifle, "hip", Vector3(0.1, 0, 0), Vector3.ZERO)
	WeaponPoseProfiles.put(profiles, rifle, "ads", Vector3(0, 0, -0.2), Vector3(0, 20, 0))
	WeaponPoseProfiles.put(profiles, rifle, "low", Vector3(0, -0.1, 0), Vector3.ZERO)
	var middle: Transform3D = WeaponPoseProfiles.apply(Transform3D.IDENTITY, profiles, rifle, 0.5, 0.0)
	_check("pose blend is continuous", middle.origin.is_equal_approx(Vector3(0.05, 0, -0.1)) and absf(rad_to_deg(middle.basis.get_euler().y) - 10.0) < 0.01)
	_check("unknown weapon keeps exact base transform", WeaponPoseProfiles.apply(middle, profiles, "unknown", 1.0, 1.0).is_equal_approx(middle))
	WeaponPoseProfiles.put(profiles, rifle, "hip", Vector3(INF, 0, 0), Vector3(0, 900, 0))
	_check("invalid offsets are bounded", (WeaponPoseProfiles.values(profiles, rifle, "hip").position as Vector3).is_zero_approx()
		and is_equal_approx((WeaponPoseProfiles.values(profiles, rifle, "hip").rotation as Vector3).y, WeaponPoseProfiles.ROTATION_LIMIT))
	_lab._reset_pose()
	await _key(KEY_F6)
	_check("F6 resumes normal player input", not _lab.is_open() and _lab._player.is_physics_processing() and not _lab._player.ui_blocked())
	var before: Vector3 = _lab._player.global_position
	Input.action_press("move_forward")
	await _frames(40)
	Input.action_release("move_forward")
	_check("movement works with panel hidden", _lab._player.global_position.distance_to(before) > 0.1)
	var previous_shot: int = _lab._player.last_shot_ms
	Input.action_press("fire")
	await _frames(15)
	Input.action_release("fire")
	_check("shooting works with panel hidden", _lab._player.last_shot_ms > previous_shot)
	await _key(KEY_F6)
	_check("F6 restores editing without firing", _lab.is_open() and not _lab._player.is_physics_processing())
	DirAccess.remove_absolute(WeaponPoseProfiles.storage_path)
	print("WEAPON_POSE_TEST checks=%d failures=%d" % [_checks, _fails])
	get_tree().quit(1 if _fails > 0 else 0)


func _key(keycode: Key) -> void:
	var event: InputEventKey = InputEventKey.new()
	event.keycode = keycode
	event.pressed = true
	Input.parse_input_event(event)
	await _frames(2)
	event = InputEventKey.new()
	event.keycode = keycode
	event.pressed = false
	Input.parse_input_event(event)
	await _frames(2)


func _shot(name: String) -> void:
	if _out.is_empty() or DisplayServer.get_name() == "headless":
		return
	await RenderingServer.frame_post_draw
	var result: Error = get_viewport().get_texture().get_image().save_png(_out.path_join(name + ".png"))
	_check("screenshot " + name, result == OK)


func _frames(count: int) -> void:
	for frame: int in range(count):
		await get_tree().process_frame


func _check(label: String, result: bool) -> void:
	_checks += 1
	if not result:
		_fails += 1
	print("PASS " if result else "FAIL ", label)
