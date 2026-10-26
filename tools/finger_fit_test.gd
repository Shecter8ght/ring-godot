extends Node3D
## Геометрия контакта, неизменность костей, оба рига и настоящий ввод мышью.

var _checks: int = 0
var _fails: int = 0
var _lab: WeaponPoseLab
var _out: String = ""


func _ready() -> void:
	Engine.max_fps = 90
	if DisplayServer.get_name() != "headless":
		get_window().content_scale_size = Vector2i(1280, 720)
		get_window().size = Vector2i(1280, 720)
	HandGripProfiles.storage_path = "user://finger_fit_%d.cfg" % OS.get_process_id()
	WeaponPoseProfiles.storage_path = "user://finger_fit_weapon_%d.cfg" % OS.get_process_id()
	HandGripProfiles.reload()
	WeaponPoseProfiles.reload()
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("out="):
			_out = argument.substr(4)
	if not _out.is_empty():
		DirAccess.make_dir_recursive_absolute(_out)
		var ignore: FileAccess = FileAccess.open(_out.path_join(".gdignore"), FileAccess.WRITE)
		if ignore:
			ignore.store_string("")
	_test_solver()
	_lab = (load("res://scenes/debug/weapon_pose_lab.tscn") as PackedScene).instantiate() as WeaponPoseLab
	add_child(_lab)
	await _frames(55)
	await _test_real_rig(true)
	_lab._select_weapon(_index("wpn_hg_01"))
	await _frames(55)
	await _test_real_rig(false)
	await _test_mouse()
	_check("new rotation fields save", _lab._save())
	var saved: Dictionary = _lab._hand_draft.duplicate(true)
	HandGripProfiles.reload()
	_check("dragged rotations survive disk reload", HandGripProfiles.snapshot() == saved)
	DirAccess.remove_absolute(HandGripProfiles.storage_path)
	DirAccess.remove_absolute(WeaponPoseProfiles.storage_path)
	print("FINGER_FIT_TEST checks=%d failures=%d" % [_checks, _fails])
	get_tree().quit(1 if _fails else 0)


func _test_solver() -> void:
	var skeleton: Skeleton3D = Skeleton3D.new()
	add_child(skeleton)
	for index: int in range(3):
		skeleton.add_bone("Joint%d" % index)
		if index > 0:
			skeleton.set_bone_parent(index, index - 1)
		var rest: Transform3D = Transform3D(Basis.IDENTITY, Vector3(0, 0.04 if index == 1 else (0.03 if index == 2 else 0.0), 0))
		skeleton.set_bone_rest(index, rest)
		skeleton.set_bone_pose(index, rest)
	var pose: HandGripPose = HandGripPose.new()
	pose.skeleton = skeleton
	pose.fingers.RightIndex = [{"bone": 0}, {"bone": 1}, {"bone": 2}]
	pose._tips.RightIndex = Vector3(0, 0.025, 0)
	var fit = preload("res://src/debug/hand_finger_ik.gd").new()
	var entry: Dictionary = HandGripProfiles.sanitize({}).fingers.Index
	_check("synthetic finger configured", fit.begin(pose, "Right", "Index", entry))
	var origin: PackedVector3Array = pose.finger_points("Right", "Index")
	_check("FK matches actual skeleton before solving", fit.points(fit.rotations)[3].distance_to(origin[3]) < 0.00001)
	var target: Vector3 = Vector3(0.04, 0.065, 0.01)
	var result: Dictionary = {}
	for attempt: int in range(5):
		result = fit.solve(target, 0.0)
	_check("free tip converges within three mm", float(result.error) < 0.003)
	_check_lengths("free chain", origin, result.points as PackedVector3Array)
	result = fit.solve(Vector3(0, 5, 0), 0.0)
	_check("unreachable target stays finite", (result.points as PackedVector3Array)[3].is_finite() and float(result.error) > 4.8)
	_check_lengths("unreachable chain", origin, result.points as PackedVector3Array)
	var weapon: Node3D = Node3D.new()
	add_child(weapon)
	var box: MeshInstance3D = MeshInstance3D.new()
	box.mesh = BoxMesh.new()
	(box.mesh as BoxMesh).size = Vector3(0.03, 0.05, 0.03)
	box.position = Vector3(0.025, 0.035, 0)
	weapon.add_child(box)
	_check("one exact triangle collider", fit.rebuild_colliders(weapon, skeleton) == 1)
	_check("inside weapon volume is detected", fit.contact_depth(box.position, 0.006) > 0.006)
	_check("outside weapon volume is clear", fit.contact_depth(Vector3(-0.03, 0.035, 0), 0.006) == 0.0)
	_check("finger radius contacts before center enters", fit.contact_depth(Vector3(0.007, 0.035, 0), 0.006) > 0.002)
	fit.begin(pose, "Right", "Index", entry)
	for attempt: int in range(5):
		result = fit.solve(box.position, 0.006)
	var contact: PackedVector3Array = result.points as PackedVector3Array
	_check("inside target stops tip at weapon surface", fit.contact_depth(contact[3], 0.006) < 0.0015 and float(result.error) > 0.01)
	_check("contact changes several phalanges", (result.rotation as Array)[0] != Vector3.ZERO and (result.rotation as Array)[1] != Vector3.ZERO)
	_check_lengths("contact chain", origin, contact)
	box.position += Vector3(0.1, 0, 0)
	fit.solve(target, 0.0)
	_check("collider follows a moved weapon part", fit.contact_depth(box.position, 0.006) > 0.006 and fit.contact_depth(box.position - Vector3(0.1, 0, 0), 0.006) == 0.0)
	print("CONTACT error_mm=%.2f penetration=%.8f solve_ms=%.2f" % [float(result.error) * 1000.0, fit.penetration(contact, 0.006), float(fit.last_usec) / 1000.0])
	weapon.queue_free()
	skeleton.queue_free()


func _test_real_rig(clips: bool) -> void:
	var overlay: HandGripPose = (_lab._rig._viewmodel as ViewmodelClips)._hand_pose if clips else _lab._rig._arms._hand_pose
	var label: String = "clips" if clips else "shared"
	for side_index: int in range(2):
		_lab._panel.grip.sides.select(side_index)
		_lab._refresh_hand_values()
		for finger: String in HandGripProfiles.FINGERS:
			var points: PackedVector3Array = overlay.finger_points(_lab._hand_side(), finger)
			_check(label + " " + _lab._hand_side() + finger + " visible tip", points.size() == 4 and points[2].distance_to(points[3]) > 0.005 and points[2].distance_to(points[3]) < 0.06)
		_lab._panel.grip.drag_tips.button_pressed = true
		_lab._panel.grip.collision.button_pressed = false
		_lab._update_inspector()
		var chain: PackedVector3Array = overlay.finger_points(_lab._hand_side(), "Index")
		var point: Vector2 = _lab._inspector.camera.unproject_position(chain[3])
		_lab._inspector.dragging = true
		_lab._begin_finger_fit("Index", point)
		var fit = _lab._finger_fit
		_check(label + " FK agrees with live scaled hand", fit.points(fit.rotations)[3].distance_to(chain[3]) < 0.0001)
		_check(label + " weapon collider excludes hand meshes", fit.colliders.size() > 0)
		var no_hands: bool = true
		for collider: Dictionary in fit.colliders:
			var mesh: MeshInstance3D = (collider.instance as WeakRef).get_ref() as MeshInstance3D
			no_hands = no_hands and mesh.skin == null
		_check(label + " arm skin is never a weapon obstacle", no_hands)
		var before: Dictionary = _lab._hand_draft.duplicate(true)
		var target: Vector3 = chain[3] + _lab._inspector.camera.global_basis.x * 0.012
		_lab._drag_target = target
		for attempt: int in range(5):
			_lab._update_finger_fit()
		var solved: PackedVector3Array = fit.points(fit.rotations)
		_check(label + " real tip approaches target", solved[3].distance_to(target) < chain[3].distance_to(target) * 0.6)
		if side_index == 1:
			_test_real_contact(label, fit)
		_check_lengths(label + " real hand", chain, solved, overlay.skeleton.global_transform.affine_inverse())
		_lab._inspector.finish_drag(false)
		await _frames(4)
		var live: PackedVector3Array = overlay.finger_points(_lab._hand_side(), "Index")
		_check(label + " profile reproduces solved tip", live[3].distance_to(solved[3]) < 0.002)
		_lab._undo_finger_fit()
		var expected: Dictionary = HandGripProfiles.values(before, _lab._hand_key(), _lab._hand_side())
		_check(label + " undo preserves original finger", HandGripProfiles.values(_lab._hand_draft, _lab._hand_key(), _lab._hand_side()) == expected)
	_lab._panel.grip.sides.select(1)
	_lab._refresh_hand_values()


func _test_mouse() -> void:
	if DisplayServer.get_name() == "headless":
		return
	_lab._panel.grip.tabs.current_tab = 4
	_lab._panel.grip.drag_tips.button_pressed = false
	_lab._panel.grip.views.select(0)
	_lab._panel.grip.collision.button_pressed = true
	_lab._panel.grip.drag_tips.button_pressed = true
	_check("enabling drag opens inspection from first person", _lab._panel.grip.views.selected == 1)
	await _frames(4)
	var inspector: HandGripInspector = _lab._inspector
	var surface: SubViewportContainer = inspector.surface
	var local: Vector2 = inspector._tips.Index as Vector2
	var point: Vector2 = surface.get_global_rect().position + local
	var initial_yaw: float = inspector.yaw
	var before: Dictionary = _lab._hand_draft.duplicate(true)
	_mouse(point, true)
	await _frames(2)
	_check("real mouse picks fingertip", inspector.dragging and _lab._finger_fit.finger == "Index")
	var motion: InputEventMouseMotion = InputEventMouseMotion.new()
	motion.position = point + Vector2(-28, 16)
	motion.relative = Vector2(-28, 16)
	motion.button_mask = MOUSE_BUTTON_MASK_LEFT
	Input.parse_input_event(motion)
	await _frames(5)
	_check("dragging tip does not orbit camera", is_equal_approx(initial_yaw, inspector.yaw))
	_check("mouse drag records joint rotations", _lab._hand_draft != before)
	await _shot("01_finger_drag_contact")
	var depth: float = _lab._drag_depth
	print("REAL_DRAG solve_ms=%.2f parts=%d" % [float(_lab._finger_fit.last_usec) / 1000.0, _lab._finger_fit.colliders.size()])
	var wheel: InputEventMouseButton = InputEventMouseButton.new()
	wheel.position = motion.position
	wheel.button_index = MOUSE_BUTTON_WHEEL_DOWN
	wheel.pressed = true
	Input.parse_input_event(wheel)
	await _frames(2)
	_check("drag wheel adjusts target depth", _lab._drag_depth > depth)
	var escape: InputEventKey = InputEventKey.new()
	escape.keycode = KEY_ESCAPE
	escape.pressed = true
	Input.parse_input_event(escape)
	await _frames(2)
	_check("Esc cancels drag and keeps editor open", not inspector.dragging and _lab.is_open())
	_check("Esc restores that finger", HandGripProfiles.values(_lab._hand_draft, _lab._hand_key(), _lab._hand_side()) == HandGripProfiles.values(before, _lab._hand_key(), _lab._hand_side()))
	_mouse(motion.position, false)
	escape = InputEventKey.new()
	escape.keycode = KEY_ESCAPE
	Input.parse_input_event(escape)
	await _frames(3)
	point = surface.get_global_rect().position + (inspector._tips.Index as Vector2)
	_mouse(point, true)
	await _frames(2)
	motion = InputEventMouseMotion.new()
	motion.position = point + Vector2(18, -12)
	motion.relative = Vector2(18, -12)
	motion.button_mask = MOUSE_BUTTON_MASK_LEFT
	Input.parse_input_event(motion)
	await _frames(4)
	_mouse(motion.position, false)
	await _frames(3)
	_check("mouse release retains fitted pose and enables undo", not inspector.dragging and not _lab._panel.grip.undo_finger.disabled
		and HandGripProfiles.values(_lab._hand_draft, _lab._hand_key(), _lab._hand_side()) != HandGripProfiles.values(before, _lab._hand_key(), _lab._hand_side()))
	_lab._panel.grip.tabs.current_tab = 2
	_lab._panel.grip.joints.select(2)
	_lab._panel.grip._show_joint()
	_lab._panel.grip._joint_rotation[2].value = 12.5
	await _frames(3)
	for scroll: Node in _lab._panel.find_children("*", "ScrollContainer", true, false):
		if scroll.is_ancestor_of(_lab._panel.grip._joint_rotation[2]):
			(scroll as ScrollContainer).ensure_control_visible(_lab._panel.grip._joint_rotation[2])
	await _frames(3)
	await _shot("02_finger_three_axes")


func _test_real_contact(label: String, fit: RefCounted) -> void:
	var target: Vector3 = Vector3.INF
	var distance: float = INF
	var tip: Vector3 = fit.points(fit.rotations)[3]
	# Ищем точку внутри ближайшей реальной детали, а не в габарите пустой скобы.
	for item: Dictionary in fit.colliders:
		var bounds: AABB = item.bounds as AABB
		var point: Vector3 = (item.forward as Transform3D) * bounds.get_center()
		var delta: float = point.distance_to(tip)
		if delta < distance and fit.contact_depth(point, 0.004) > 0.004:
			target = point
			distance = delta
	_check(label + " real weapon has a solid nearby contact", target.is_finite() and distance < 0.25)
	if not target.is_finite():
		return
	var result: Dictionary = {}
	for attempt: int in range(2):
		result = fit.solve(target, 0.004)
	var chain: PackedVector3Array = result.points as PackedVector3Array
	_check(label + " real weapon contact leaves a finite reachable chain", chain[3].is_finite() and float(result.error) > 0.002)
	_check(label + " real weapon stops fingertip outside its surface", fit.contact_depth(chain[3], 0.004) < 0.0015)
	print("REAL_CONTACT ", label, " initial_target_mm=%.2f final_error_mm=%.2f tip_depth_mm=%.2f solve_ms=%.2f" % [distance * 1000.0, float(result.error) * 1000.0, fit.contact_depth(chain[3], 0.004) * 1000.0, float(fit.last_usec) / 1000.0])


func _mouse(point: Vector2, pressed: bool) -> void:
	var event: InputEventMouseButton = InputEventMouseButton.new()
	event.position = point
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = pressed
	Input.parse_input_event(event)


func _check_lengths(label: String, before: PackedVector3Array, after: PackedVector3Array, metric: Transform3D = Transform3D.IDENTITY) -> void:
	var same: bool = before[0].distance_to(after[0]) < 0.0001
	for index: int in range(3):
		same = same and absf((metric * before[index]).distance_to(metric * before[index + 1]) - (metric * after[index]).distance_to(metric * after[index + 1])) < 0.0002
	_check(label + " root and lengths unchanged", same)


func _index(id: String) -> int:
	for index: int in range(_lab._catalog.size()):
		if String(_lab._catalog[index].id) == id and String(_lab._catalog[index].preset) == "":
			return index
	return -1


func _frames(count: int) -> void:
	for frame: int in range(count):
		await get_tree().process_frame


func _shot(name: String) -> void:
	if _out.is_empty():
		return
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(_out.path_join(name + ".png"))


func _check(label: String, result: bool) -> void:
	_checks += 1
	_fails += 0 if result else 1
	print("PASS " if result else "FAIL ", label)
