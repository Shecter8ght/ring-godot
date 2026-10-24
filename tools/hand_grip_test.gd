extends Node
## Настоящие игровые руки обоих типов: положение, пальцы, изоляция, сохранение,
## отсутствие накопления, возврат клипа после действия и управление стендом.

var _checks: int = 0
var _fails: int = 0
var _lab: WeaponPoseLab
var _out: String = ""
var _size: Vector2i = Vector2i.ZERO


func _ready() -> void:
	Engine.max_fps = 90
	HandGripProfiles.storage_path = "user://hand_grip_test.cfg"
	WeaponPoseProfiles.storage_path = "user://hand_grip_weapon_pose_test.cfg"
	DirAccess.remove_absolute(HandGripProfiles.storage_path)
	DirAccess.remove_absolute(WeaponPoseProfiles.storage_path)
	HandGripProfiles.reload()
	WeaponPoseProfiles.reload()
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("out="):
			_out = argument.substr(4)
		elif argument.begins_with("size="):
			var dimensions: PackedStringArray = argument.substr(5).split("x")
			_size = Vector2i(int(dimensions[0]), int(dimensions[1]))
	if _size.x > 0 and DisplayServer.get_name() != "headless":
		get_window().mode = Window.MODE_WINDOWED
		get_window().size = _size
		get_window().content_scale_size = _size
	if not _out.is_empty():
		DirAccess.make_dir_recursive_absolute(_out)
		var ignore: FileAccess = FileAccess.open(_out.path_join(".gdignore"), FileAccess.WRITE)
		if ignore:
			ignore.store_string("")
	_lab = (load("res://scenes/debug/weapon_pose_lab.tscn") as PackedScene).instantiate() as WeaponPoseLab
	add_child(_lab)
	await _frames(90)
	_check("open at hands tab; gameplay blocked", _lab._panel.tabs.current_tab == 1 and _lab._player.ui_blocked())
	_check("inspector shares live world", _lab._inspector.view.world_3d == _lab.get_world_3d() and _lab._inspector.visible)
	_check("panel does not overlap inspection area", _lab._panel.get_global_rect().end.x <= _lab._inspector.get_global_rect().position.x)
	await _shot("01_grip_veras")
	await _test_orbit()
	var rifle_index: int = _lab._weapon_index
	await _exercise("clips", true)
	_check("draft isolated from saved game", HandGripProfiles.active().is_empty())
	await _key(KEY_F7)
	await _frames(20)
	_check("comparison excludes hand overrides", (_lab._rig._viewmodel as ViewmodelClips).grip_profiles.is_empty())
	await _key(KEY_F7)
	await _frames(20)
	_check("comparison restores draft", not (_lab._rig._viewmodel as ViewmodelClips).grip_profiles.is_empty())
	_check("save both profile files", _lab._save())
	HandGripProfiles.reload()
	var rifle_key: String = _lab._hand_key()
	var rifle_side: String = _lab._hand_side()
	_check("saved hand survives reload", is_equal_approx((HandGripProfiles.values(HandGripProfiles.active(), rifle_key, rifle_side).position as Vector3).z, 0.03))
	_lab._panel.grip._position[2].value = 6.0
	_lab._restore()
	_check("restore discards unsaved edit", is_equal_approx(_lab._panel.grip._position[2].value, 3.0) and not _lab._dirty)
	# Проверяем именно обычный игровой путь, без черновика стенда.
	var clip: ViewmodelClips = _lab._rig._viewmodel as ViewmodelClips
	clip.grip_preview = false
	clip.grip_profiles = {}
	var player: Player = _lab._player
	clip.update(player, 0.02)
	_check("saved profile is consumed by normal clips", clip._hand_pose._saved.size() > 0)
	# Настоящая анимация отпускает ручную подгонку и затем возвращает её в стойку.
	clip._play(clip._clip_name("reload"), 0.0, 1.0)
	await _frames(22)
	_check("reload animation owns hands", clip.is_busy() and clip._hand_weight < 0.05 and clip._hand_pose._saved.is_empty())
	clip._play(clip._clip_name("idle"), 0.0)
	await _frames(24)
	_check("manual grip returns after action", clip._hand_weight > 0.99 and clip._hand_pose._saved.size() > 0)
	_lab._panel.grip.use_in_game.button_pressed = false
	_lab._save()
	_check("disable preserves data and returns game to source grip", HandGripProfiles.active().is_empty() and not HandGripProfiles.snapshot().is_empty())
	_lab._panel.grip.use_in_game.button_pressed = true
	var grip_index: int = -1
	for index: int in range(_lab._catalog.size()):
		if String(_lab._catalog[index].id) == "wpn_ar_01" and String(_lab._catalog[index].get("grip", "")) == "grip_vertical_01":
			grip_index = index
			break
	_check("Veras VARN V1 selectable directly", grip_index >= 0)
	if grip_index >= 0:
		_lab._select_weapon(grip_index)
		await _frames(55)
		_check("underbarrel has its own draft", _lab._panel.grip._position[2].value == 0.0)
		var gripped: ViewmodelClips = _lab._rig._viewmodel as ViewmodelClips
		_check("frozen preview equips real VARN clip set", gripped._set == "varn_v1" and WeaponDb.mod_id(_lab._player.weapon_mods.get("underbarrel", {})) == "grip_vertical_01")
		gripped._anim.speed_scale = 0.0
		var hand: int = gripped._hand_pose.chains.Left[2]
		var before_grip: Transform3D = _relative_wrist(gripped._arm_skel, hand)
		_lab._panel.grip._position[2].value = 2.0
		await _frames(130)
		_check("custom hand layers over existing rail IK without drift", absf((_relative_wrist(gripped._arm_skel, hand).origin - before_grip.origin).z - 0.02) < 0.002)
		await _shot("04_veras_vertical_grip")
	var pistol_index: int = _index("wpn_hg_02")
	_check("pistol in catalog", pistol_index >= 0)
	_lab._select_weapon(pistol_index)
	await _frames(75)
	_check("other weapon starts at zero", _lab._panel.grip._position[2].value == 0.0)
	await _exercise("shared", false)
	_check("shared arms keep length and wrist contact", _lab._rig._arms.max_length_error < 0.001 and _lab._rig._arms.max_grip_error < 0.001)
	HandGripProfiles.save_profiles(_lab._hand_draft, true)
	var original_wrist: Transform3D = _relative_wrist(_lab._rig._arms.skeleton, _lab._rig._arms._hand_pose.chains.Left[2])
	_lab._rig._arms.grip_preview = false
	_lab._rig._arms.update_pose()
	_check("saved profile is consumed by normal shared arms", original_wrist.is_equal_approx(_relative_wrist(_lab._rig._arms.skeleton, _lab._rig._arms._hand_pose.chains.Left[2])))
	await _key(KEY_F8)
	await _frames(3)
	_check("F8 first person", not _lab._inspector.visible)
	await _shot("04_grip_pistol_fps")
	await _key(KEY_F8)
	await _frames(3)
	_check("F8 inspector", _lab._inspector.visible)
	await _key(KEY_F6)
	_check("F6 hands back player controls", not _lab.is_open() and _lab._player.is_physics_processing() and not _lab._inspector.visible)
	var before: Vector3 = _lab._player.global_position
	Input.action_press("move_forward")
	await _frames(35)
	Input.action_release("move_forward")
	_check("movement with draft", _lab._player.global_position.distance_to(before) > 0.1)
	await _key(KEY_F6)
	_check("F6 returns editor", _lab.is_open() and not _lab._player.is_physics_processing())
	_lab._select_weapon(rifle_index)
	await _frames(45)
	_check("weapon switch retains independent draft", is_equal_approx(_lab._panel.grip._position[2].value, 3.0))
	_lab._reset_hand()
	_check("reset only chosen hand", (_lab._panel.grip._value.position as Vector3).is_zero_approx())
	_lab._select_weapon(_index("signal_launcher"))
	await _frames(65)
	_check("one handed flare gun selects right hand", _lab._panel.grip.sides.selected == 1 and _lab._panel.grip.sides.is_item_disabled(0))
	var signal_vm: ViewmodelClips = _lab._rig._viewmodel as ViewmodelClips
	signal_vm._anim.speed_scale = 0.0
	var signal_wrist: int = signal_vm._hand_pose.chains.Right[2]
	var signal_before: Transform3D = _relative_wrist(signal_vm._arm_skel, signal_wrist)
	_lab._panel.grip._position[0].value = -2.0
	await _frames(25)
	_check("flare grip moves relative to weapon", absf((_relative_wrist(signal_vm._arm_skel, signal_wrist).origin - signal_before.origin).x + 0.02) < 0.002)
	await _shot("05_flare_right")
	_test_storage()
	await _test_transfer()
	DirAccess.remove_absolute(HandGripProfiles.storage_path)
	DirAccess.remove_absolute(WeaponPoseProfiles.storage_path)
	print("HAND_GRIP_TEST checks=%d failures=%d" % [_checks, _fails])
	get_tree().quit(1 if _fails else 0)


func _exercise(label: String, clips: bool) -> void:
	var sk: Skeleton3D = _lab._rig._arms.skeleton
	var overlay: HandGripPose = _lab._rig._arms._hand_pose
	if clips:
		var vm: ViewmodelClips = _lab._rig._viewmodel as ViewmodelClips
		sk = vm._arm_skel
		overlay = vm._hand_pose
		vm._anim.speed_scale = 0.0
	await _frames(5)
	var left: int = overlay.chains.Left[2]
	var right: int = overlay.chains.Right[2]
	var base_left: Transform3D = _relative_wrist(sk, left)
	var base_right: Transform3D = _relative_wrist(sk, right)
	var lengths: Vector2 = _lengths(sk, overlay.chains.Left)
	_lab._panel.grip._position[2].value = 3.0
	await _frames(30)
	var shifted: Transform3D = _relative_wrist(sk, left)
	_check(label + " left follows three centimeter control", absf((shifted.origin - base_left.origin).z - 0.03) < 0.002)
	_check(label + " other hand stays in place", _relative_wrist(sk, right).origin.distance_to(base_right.origin) < 0.002)
	_check(label + " arm lengths unchanged", _lengths(sk, overlay.chains.Left).distance_to(lengths) < 0.001)
	await _frames(140)
	_check(label + " wrist offset does not accumulate", _relative_wrist(sk, left).origin.distance_to(shifted.origin) < 0.002)
	_lab._panel.grip._rotation[1].value = 12.0
	await _frames(15)
	_check(label + " wrist turns", shifted.basis.get_rotation_quaternion().angle_to(_relative_wrist(sk, left).basis.get_rotation_quaternion()) > deg_to_rad(10.0))
	# Каждый палец и каждый сустав действительно меняет кость обеих схем экспорта.
	for finger_index: int in range(5):
		_lab._panel.grip.fingers.select(finger_index)
		_lab._panel.grip._show_finger()
		var finger: String = HandGripProfiles.FINGERS[finger_index]
		for joint: int in range(3):
			var bone: int = int((overlay.fingers["Left" + finger] as Array)[joint].bone)
			var original: Quaternion = sk.get_bone_pose_rotation(bone)
			_lab._panel.grip._bend[joint].value = 18.0
			await _frames(3)
			_check("%s %s joint %d responds" % [label, finger, joint + 1], original.angle_to(sk.get_bone_pose_rotation(bone)) > deg_to_rad(16.0))
		var first: int = int((overlay.fingers["Left" + finger] as Array)[0].bone)
		var original: Quaternion = sk.get_bone_pose_rotation(first)
		_lab._panel.grip._spread.value = 10.0
		_lab._panel.grip._twist.value = 10.0
		await _frames(3)
		_check(label + " " + finger + " spread and twist respond", original.angle_to(sk.get_bone_pose_rotation(first)) > 0.1)
	var finger_bone: int = int((overlay.fingers.LeftIndex as Array)[0].bone)
	var stable: Quaternion = sk.get_bone_pose_rotation(finger_bone)
	await _frames(130)
	_check(label + " finger edits do not accumulate", stable.angle_to(sk.get_bone_pose_rotation(finger_bone)) < 0.001)
	_lab._panel.grip.tabs.current_tab = 2
	await _frames(5)
	await _shot("02_" + label + "_fingers")
	_lab._panel.grip.tabs.current_tab = 0
	_lab._panel.grip.views.select(2)
	await _frames(10)
	await _shot("02_" + label + "_both_hands")
	_lab._panel.grip.sides.select(1)
	_lab._refresh_hand_values()
	_check(label + " right controls independent", _lab._panel.grip._position[2].value == 0.0 and _lab._panel.grip._bend[0].value == 0.0)
	_lab._panel.grip._position[0].value = -1.0
	await _frames(20)
	_check(label + " right hand editable", absf((_relative_wrist(sk, right).origin - base_right.origin).x + 0.01) < 0.002)
	_lab._panel.grip.views.select(1)
	await _frames(10)
	await _shot("03_" + label + "_right")
	_lab._reset_hand()
	_lab._panel.grip.sides.select(0)
	_lab._refresh_hand_values()


func _test_storage() -> void:
	var bare: Dictionary = HandGripProfiles.keys("wpn_ar_01", {})
	var vertical: Dictionary = HandGripProfiles.keys("wpn_ar_01", {"underbarrel": {"id": "grip_vertical_01", "slot": 3}})
	var moved: Dictionary = HandGripProfiles.keys("wpn_ar_01", {"underbarrel": {"id": "grip_vertical_01", "slot": 7}, "optic_primary": {"id": "red_dot_01"}})
	_check("right grip shared between underbarrel builds", bare.Right == vertical.Right)
	_check("left grip separate for underbarrel attachment", bare.Left != vertical.Left)
	_check("moving rail or changing scope keeps hand adjustment", vertical.Left == moved.Left)
	var malformed: Dictionary = HandGripProfiles.sanitize({"position": Vector3(INF, 0, 0), "rotation": Vector3(0, 1000, 0),
		"fingers": {"Index": {"bend": Vector3(1000, -1000, NAN), "spread": "invalid", "twist": INF}}})
	_check("invalid data bounded and finite", (malformed.position as Vector3).is_zero_approx() and (malformed.rotation as Vector3).y == HandGripProfiles.ROTATION_LIMIT
		and (malformed.fingers.Index.bend as Vector3).is_zero_approx() and malformed.fingers.Index.spread == 0.0 and malformed.fingers.Index.twist == 0.0)


func _test_transfer() -> void:
	var unchanged: Dictionary = _lab._hand_draft.duplicate(true)
	var dirty_before: bool = _lab._dirty
	_check("empty transfer buffer disables paste without editing", _lab._panel.grip.paste_grip.disabled and not _lab._paste_hand_grip()
		and _lab._hand_draft == unchanged and _lab._dirty == dirty_before)
	var pm: int = _index("wpn_hg_01")
	var glock: int = _index("wpn_hg_02")
	var third_pistol: int = _index("wpn_hg_03")
	_check("PM and two target pistols exist", pm >= 0 and glock >= 0 and third_pistol >= 0)
	if pm < 0 or glock < 0 or third_pistol < 0:
		return
	_lab._select_weapon(pm)
	await _frames(45)
	var expected: Dictionary = {}
	for side_index: int in range(2):
		_set_transfer_hand(side_index)
		var side: String = HandGripProfiles.SIDES[side_index]
		expected[side] = HandGripProfiles.values(_lab._hand_draft, "wpn_hg_01", side)
	_lab._panel.grip.tabs.current_tab = 3
	_lab._panel.grip.transfer_scope.select(0)
	unchanged = _lab._hand_draft.duplicate(true)
	dirty_before = _lab._dirty
	await _press_transfer_button(_lab._panel.grip.copy_grip)
	_check("copy both hands includes unsaved settings and all fingers", _lab._hand_buffer.hands == expected and not _lab._panel.grip.paste_grip.disabled)
	_check("copy is read only", _lab._hand_draft == unchanged and _lab._dirty == dirty_before)
	_check("transfer identifies PM source", _lab._panel.grip.transfer_info.text.contains("ПМ"))
	_lab._panel.grip._position[0].value = 0.9
	var latest_source: Dictionary = HandGripProfiles.values(_lab._hand_draft, "wpn_hg_01", "Right")
	_check("source edits do not change copied snapshot", latest_source != expected.Right and _lab._hand_buffer.hands == expected)
	_lab._select_weapon(glock)
	await _frames(40)
	var wrist: int = _lab._rig._arms._hand_pose.chains.Left[2]
	var before: Transform3D = _relative_wrist(_lab._rig._arms.skeleton, wrist)
	WeaponPoseProfiles.put(_lab._draft, "wpn_hg_02", "hip", Vector3(0.04, 0, 0), Vector3.ZERO)
	var weapon_poses: Dictionary = _lab._draft.duplicate(true)
	_lab._panel.compare.button_pressed = true
	await _press_transfer_button(_lab._panel.grip.paste_grip)
	await _frames(35)
	_check("PM to Glock copies both wrists and complete finger data", HandGripProfiles.values(_lab._hand_draft, "wpn_hg_02", "Left") == expected.Left
		and HandGripProfiles.values(_lab._hand_draft, "wpn_hg_02", "Right") == expected.Right)
	_check("paste updates live hands and exits comparison", not _lab._panel.compare.button_pressed and _lab._dirty
		and _relative_wrist(_lab._rig._arms.skeleton, wrist).origin.distance_to(before.origin) > 0.005)
	_check("paste keeps source and weapon framing", HandGripProfiles.values(_lab._hand_draft, "wpn_hg_01", "Right") == latest_source and _lab._draft == weapon_poses)
	_check("pasted settings are not saved implicitly", HandGripProfiles.values(HandGripProfiles.snapshot(), "wpn_hg_02", "Right") != expected.Right)
	_check("save pasted grip", _lab._save())
	HandGripProfiles.reload()
	_check("pasted grip survives reload", HandGripProfiles.values(HandGripProfiles.active(), "wpn_hg_02", "Left") == expected.Left
		and HandGripProfiles.values(HandGripProfiles.active(), "wpn_hg_02", "Right") == expected.Right)
	_lab._panel.grip._position[0].value = 2.6
	_lab._select_weapon(third_pistol)
	await _frames(35)
	_lab._panel.grip.paste_grip.pressed.emit()
	_check("reuse buffer on third pistol without linked edits", HandGripProfiles.values(_lab._hand_draft, "wpn_hg_03", "Left") == expected.Left
		and HandGripProfiles.values(_lab._hand_draft, "wpn_hg_03", "Right") == expected.Right and _lab._hand_buffer.hands == expected)
	_lab._select_weapon(pm)
	_lab._panel.grip.transfer_scope.select(2)
	_lab._panel.grip.copy_grip.pressed.emit()
	_check("copy right wrist only", _lab._hand_buffer.hands.size() == 1 and _lab._hand_buffer.hands.has("Right"))
	_lab._select_weapon(glock)
	var left_before: Dictionary = HandGripProfiles.values(_lab._hand_draft, "wpn_hg_02", "Left")
	_lab._panel.grip.paste_grip.pressed.emit()
	_check("right only paste leaves left untouched", HandGripProfiles.values(_lab._hand_draft, "wpn_hg_02", "Left") == left_before
		and HandGripProfiles.values(_lab._hand_draft, "wpn_hg_02", "Right") == latest_source and _lab._panel.grip.sides.selected == 1)
	_lab._select_weapon(pm)
	_lab._panel.grip.sides.select(0)
	_lab._refresh_hand_values()
	_lab._panel.grip._position[0].value = 2.8
	var left_source: Dictionary = HandGripProfiles.values(_lab._hand_draft, "wpn_hg_01", "Left")
	_lab._panel.grip.transfer_scope.select(1)
	_lab._panel.grip.copy_grip.pressed.emit()
	_lab._select_weapon(glock)
	_lab._panel.grip.paste_grip.pressed.emit()
	_check("left only paste leaves right untouched", _lab._hand_buffer.hands.size() == 1 and HandGripProfiles.values(_lab._hand_draft, "wpn_hg_02", "Left") == left_source
		and HandGripProfiles.values(_lab._hand_draft, "wpn_hg_02", "Right") == latest_source and _lab._panel.grip.sides.selected == 0)
	_lab._select_weapon(_index("signal_launcher"))
	unchanged = _lab._hand_draft.duplicate(true)
	_check("left only buffer cannot alter one handed flare gun", not _lab._paste_hand_grip() and _lab._hand_draft == unchanged)
	_lab._select_weapon(pm)
	_lab._panel.grip.transfer_scope.select(0)
	_lab._panel.grip.copy_grip.pressed.emit()
	_lab._select_weapon(glock)
	_lab._panel.grip.paste_grip.pressed.emit()
	await _frames(45)
	await _shot("06_pistol_grip_transfer")


func _set_transfer_hand(side_index: int) -> void:
	_lab._panel.grip.sides.select(side_index)
	_lab._refresh_hand_values()
	var position: Vector3 = Vector3(1.3, -0.8, 2.1) if side_index == 0 else Vector3(-0.7, 1.1, -0.4)
	var rotation: Vector3 = Vector3(7, -5, 3) if side_index == 0 else Vector3(-3, 4, -2)
	for axis: int in range(3):
		_lab._panel.grip._position[axis].value = position[axis]
		_lab._panel.grip._rotation[axis].value = rotation[axis]
	for finger: int in range(5):
		_lab._panel.grip.fingers.select(finger)
		_lab._panel.grip._show_finger()
		_lab._panel.grip._bend[0].value = 6 + finger * 2 + side_index
		_lab._panel.grip._bend[1].value = 11 + finger + side_index
		_lab._panel.grip._bend[2].value = -9 + finger * 2 - side_index
		_lab._panel.grip._spread.value = 4 + finger + side_index
		_lab._panel.grip._twist.value = -3 - finger - side_index


func _press_transfer_button(button: Button) -> void:
	if DisplayServer.get_name() == "headless":
		button.pressed.emit()
		return
	for scroll: Node in _lab._panel.find_children("*", "ScrollContainer", true, false):
		if scroll.is_ancestor_of(button):
			(scroll as ScrollContainer).ensure_control_visible(button)
	await _frames(3)
	var point: Vector2 = button.get_global_rect().get_center()
	var motion: InputEventMouseMotion = InputEventMouseMotion.new()
	motion.position = point
	Input.parse_input_event(motion)
	await _frames(2)
	var press: InputEventMouseButton = InputEventMouseButton.new()
	press.position = point
	press.button_index = MOUSE_BUTTON_LEFT
	press.pressed = true
	Input.parse_input_event(press)
	await _frames(2)
	press = InputEventMouseButton.new()
	press.position = point
	press.button_index = MOUSE_BUTTON_LEFT
	Input.parse_input_event(press)
	await _frames(3)


func _relative_wrist(sk: Skeleton3D, bone: int) -> Transform3D:
	var result: Transform3D = _lab._rig._vm_frame().global_transform.affine_inverse() * sk.global_transform * sk.get_bone_global_pose(bone)
	result.basis = result.basis.orthonormalized()
	return result


func _test_orbit() -> void:
	if DisplayServer.get_name() == "headless":
		return
	var surface: SubViewportContainer = _lab._inspector.surface
	var point: Vector2 = surface.get_global_rect().get_center()
	var before_yaw: float = _lab._inspector.yaw
	var before_distance: float = _lab._inspector.distance
	var carry: bool = _lab._player.carry_low
	var button: InputEventMouseButton = InputEventMouseButton.new()
	button.position = point
	button.button_index = MOUSE_BUTTON_LEFT
	button.pressed = true
	Input.parse_input_event(button)
	await _frames(2)
	var motion: InputEventMouseMotion = InputEventMouseMotion.new()
	motion.position = point + Vector2(30, 0)
	motion.relative = Vector2(30, 0)
	motion.button_mask = MOUSE_BUTTON_MASK_LEFT
	Input.parse_input_event(motion)
	await _frames(2)
	button = InputEventMouseButton.new()
	button.position = motion.position
	button.button_index = MOUSE_BUTTON_LEFT
	Input.parse_input_event(button)
	await _frames(2)
	button = InputEventMouseButton.new()
	button.position = point
	button.button_index = MOUSE_BUTTON_WHEEL_UP
	button.pressed = true
	Input.parse_input_event(button)
	await _frames(2)
	_check("mouse drag orbits actual inspection view", absf(_lab._inspector.yaw - before_yaw) > 0.1)
	_check("mouse wheel zooms inspection without lowering weapon", _lab._inspector.distance < before_distance and _lab._player.carry_low == carry)
	_lab._inspector._last_mode = -1


func _lengths(sk: Skeleton3D, bones: Array) -> Vector2:
	var up: Vector3 = sk.get_bone_global_pose(bones[0]).origin
	var fore: Vector3 = sk.get_bone_global_pose(bones[1]).origin
	var hand: Vector3 = sk.get_bone_global_pose(bones[2]).origin
	return Vector2(up.distance_to(fore), fore.distance_to(hand))


func _index(id: String) -> int:
	for index: int in range(_lab._catalog.size()):
		if String(_lab._catalog[index].id) == id and String(_lab._catalog[index].preset) == "":
			return index
	return -1


func _key(keycode: Key) -> void:
	var event: InputEventKey = InputEventKey.new()
	event.keycode = keycode
	event.pressed = true
	Input.parse_input_event(event)
	await _frames(2)
	event = InputEventKey.new()
	event.keycode = keycode
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
	_fails += 0 if result else 1
	print("PASS " if result else "FAIL ", label)
