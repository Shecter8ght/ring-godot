class_name FirstPersonArms
extends Node3D
## Настоящие кисти и рукава Persona. Оружие задаёт цель, двухзвенная ИК сгибает локти.
## Отдельная сцена исключает голову и торс из камеры, сохраняя полный персонаж для теней.

const MODEL: String = "res://assets/models/characters/persona_arms.glb"
@export var shoulder_origin: Vector3 = Vector3(0.24, -0.43, 0.08)
var skeleton: Skeleton3D
var _rest: Array[Transform3D] = []
var _frames: Dictionary = {}
var _grips: Dictionary = {}
var _weapon: Node3D
var _actions: Dictionary = {}
var max_grip_error: float = 0.0
var max_length_error: float = 0.0
var arms_clear: bool = true
var collision_exclude: Array[RID] = []


func _ready() -> void:
	if not ResourceLoader.exists(MODEL):
		return
	var model: Node3D = (load(MODEL) as PackedScene).instantiate() as Node3D
	add_child(model)
	skeleton = model.find_children("*", "Skeleton3D", true, false)[0] as Skeleton3D
	for mesh: Node in model.find_children("*", "MeshInstance3D", true, false):
		var instance: MeshInstance3D = mesh as MeshInstance3D
		instance.layers = 2
		instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	for bone: int in range(skeleton.get_bone_count()):
		_rest.append(skeleton.get_bone_global_rest(bone))
	for side: String in ["Right", "Left"]:
		var wrist: Vector3 = _rest[_bone(side + "Hand")].origin
		var forward: Vector3 = (_rest[_bone(side + "HandMiddle1")].origin - wrist).normalized()
		var across: Vector3 = _rest[_bone(side + "HandIndex1")].origin - _rest[_bone(side + "HandPinky1")].origin
		across = (across - forward * across.dot(forward)).normalized()
		_frames[side] = Basis(across, forward, across.cross(forward))
	visible = false


func unbind_weapon() -> void:
	_weapon = null
	_grips.clear()
	_actions.clear()
	visible = false


func bind_weapon(weapon: Node3D) -> void:
	_weapon = weapon
	_grips.clear()
	_actions.clear()
	for side: String in ["Right", "Left"]:
		var marker: Node3D = weapon.find_child(side + "Grip", true, false) as Node3D
		if marker:
			_grips[side] = marker


## Анимация магазина, затвора или помпы может временно забрать кисть с хвата.
## Цель задаёт тот же контакт ладони, что и Grip; weight=0 возвращает обычный хват.
func set_hand_target(side: String, target: Node3D, weight: float) -> void:
	if not side in ["Right", "Left"]:
		return
	if weight <= 0.0 or target == null:
		_actions.erase(side)
	else:
		_actions[side] = {"target": target, "weight": clampf(weight, 0.0, 1.0)}


func update_pose() -> void:
	visible = skeleton != null and is_instance_valid(_weapon) and _grips.size() == 2
	if not visible:
		return
	max_grip_error = 0.0
	max_length_error = 0.0
	arms_clear = true
	# Каждый кадр считаем от rest: декомпозиция глобальной позы иначе накапливает scale.
	skeleton.reset_bone_poses()
	for side: String in ["Right", "Left"]:
		_solve(side, _grips[side] as Node3D)


func _bone(suffix: String) -> int:
	return skeleton.find_bone("mixamorig_" + suffix)


func _solve(side: String, marker: Node3D) -> void:
	var arm: int = _bone(side + "Arm")
	var forearm: int = _bone(side + "ForeArm")
	var hand: int = _bone(side + "Hand")
	var target: Transform3D = skeleton.global_transform.affine_inverse() * marker.global_transform
	if _actions.has(side):
		var action: Dictionary = _actions[side]
		if is_instance_valid(action.target):
			var action_pose: Transform3D = skeleton.global_transform.affine_inverse() * (action.target as Node3D).global_transform
			action_pose.basis = action_pose.basis.orthonormalized()
			target.basis = target.basis.orthonormalized()
			target = target.interpolate_with(action_pose, float(action.weight))
	# Масштаб оружия меняет расстояния между сокетами, но не размер кистей.
	target.basis = target.basis.orthonormalized()
	target.origin -= target.basis * (marker.get_meta("palm_offset") as Vector3)
	var contact_pose: Dictionary = marker.get_meta("contact_pose", {}) as Dictionary
	if not contact_pose.is_empty():
		target.origin += skeleton.global_basis.inverse() * _weapon.global_basis.orthonormalized() * WeaponGrips.vector(contact_pose.shift)
	var sign_x: float = 1.0 if side == "Right" else -1.0
	var shoulder: Vector3 = shoulder_origin * Vector3(sign_x, 1.0, 1.0)
	var upper_length: float = _rest[arm].origin.distance_to(_rest[forearm].origin)
	var lower_length: float = _rest[forearm].origin.distance_to(_rest[hand].origin)
	var reach: float = (upper_length + lower_length) * 0.98
	var delta: Vector3 = target.origin - shoulder
	# Плечевой пояс следует за поднятым или далёким цевьём; кости не растягиваются.
	if delta.length() > reach:
		shoulder = _reachable_shoulder(shoulder, target.origin, reach)
	var world: World3D = get_world_3d()
	var sleeve_radius: float = float(Balance.WEAPON_CLEARANCE.upper_sleeve_radius) * maxf(skeleton.global_basis.x.length(), maxf(skeleton.global_basis.y.length(), skeleton.global_basis.z.length()))
	# ViewmodelSpace меняет видимую ширину плеч: ограничиваем именно мировую геометрию.
	shoulder = skeleton.global_transform.affine_inverse() * WeaponClearance.safe_shoulder(world, skeleton.to_global(shoulder), sleeve_radius, collision_exclude, global_position)
	if shoulder.distance_to(target.origin) > reach:
		# Пол меняет высоту плеча лёжа; повторно сохраняем досягаемость длинного цевья.
		shoulder = _reachable_shoulder(shoulder, target.origin, reach)
		shoulder = skeleton.global_transform.affine_inverse() * WeaponClearance.safe_shoulder(world, skeleton.to_global(shoulder), sleeve_radius, collision_exclude, global_position)
	var pole: Vector3 = Vector3(sign_x * 0.65, -1.0, 0.15)
	var solved: Dictionary = ArmIKSolver.solve(shoulder, target.origin, upper_length, lower_length, pole, skeleton.global_transform, world, collision_exclude, global_position)
	var elbow: Vector3 = solved.elbow
	arms_clear = arms_clear and bool(solved.clear)
	var frame: Basis = _frames[side]
	var hand_basis: Basis = target.basis * frame.inverse() * _rest[hand].basis
	var wrist_rotation: Basis = hand_basis * _rest[hand].basis.inverse()
	_set_segment(arm, forearm, shoulder, elbow, wrist_rotation, true)
	_set_segment(forearm, hand, elbow, solved.wrist as Vector3, wrist_rotation)
	skeleton.set_bone_global_pose(hand, Transform3D(hand_basis, solved.wrist as Vector3))
	if contact_pose.is_empty():
		_curl_fingers(side, marker.get_meta("curl") as Array)
		_pose_thumb(side, target.basis, absf(marker.basis.y.x) > 0.5, marker.get_meta("thumb_directions", []) as Array)
	else:
		for joint: String in contact_pose.joints:
			var q: Array = contact_pose.joints[joint]
			skeleton.set_bone_pose_rotation(_bone(side + "Hand" + joint), Quaternion(float(q[0]), float(q[1]), float(q[2]), float(q[3])))
	max_grip_error = maxf(max_grip_error, skeleton.get_bone_global_pose(hand).origin.distance_to(target.origin))
	var actual_arm: Vector3 = skeleton.get_bone_global_pose(arm).origin
	var actual_elbow: Vector3 = skeleton.get_bone_global_pose(forearm).origin
	var actual_wrist: Vector3 = skeleton.get_bone_global_pose(hand).origin
	max_length_error = maxf(max_length_error, maxf(absf(actual_arm.distance_to(actual_elbow) - upper_length), absf(actual_elbow.distance_to(actual_wrist) - lower_length)))


## Сохраняем низкое плечо, подавая его вбок только при недосягаемом поперечном хвате.
func _reachable_shoulder(shoulder: Vector3, target: Vector3, reach: float) -> Vector3:
	var delta: Vector3 = target - shoulder
	var margin: float = float(Balance.WEAPON_CLEARANCE.reach_margin)
	shoulder.y = target.y - clampf(delta.y, -reach + margin, reach - margin)
	delta = target - shoulder
	var allowed_x: float = sqrt(maxf(margin * margin, reach * reach - delta.y * delta.y)) - margin
	shoulder.x = target.x - clampf(delta.x, -allowed_x, allowed_x)
	delta = target - shoulder
	shoulder.z = target.z + sqrt(maxf(margin * margin, reach * reach - delta.x * delta.x - delta.y * delta.y))
	return shoulder


func _set_segment(bone: int, child: int, start: Vector3, finish: Vector3, wrist_rotation: Basis, move_shoulder: bool = false) -> void:
	var old_direction: Vector3 = wrist_rotation * (_rest[child].origin - _rest[bone].origin).normalized()
	var new_direction: Vector3 = (finish - start).normalized()
	var rotation: Basis = Basis(Quaternion(old_direction, new_direction))
	var pose: Transform3D = Transform3D(rotation * wrist_rotation * _rest[bone].basis, start)
	if move_shoulder:
		# Плечевой пояс следует за перенесённым плечом, чтобы цепь сохраняла согласованную позу.
		var parent: int = skeleton.get_bone_parent(bone)
		skeleton.set_bone_global_pose(parent, pose * _rest[bone].affine_inverse() * _rest[parent])
	skeleton.set_bone_global_pose(bone, pose)


func _curl_fingers(side: String, curl: Array) -> void:
	var frame: Basis = _frames[side]
	var palm: Vector3 = frame.z * (1.0 if side == "Right" else -1.0)
	for finger: String in ["Index", "Middle", "Ring", "Pinky", "Thumb"]:
		for joint: int in range(1, 4):
			var bone: int = _bone(side + "Hand" + finger + str(joint))
			var rest_local: Transform3D = skeleton.get_bone_rest(bone)
			var direction: Vector3 = _rest[bone].basis.y.normalized()
			var axis: Vector3 = direction.cross(palm).normalized()
			axis = _rest[bone].basis.inverse() * axis
			var angle: float = float(curl[joint - 1])
			if finger == "Thumb":
				angle *= 0.35
			elif finger == "Index" and side == "Right":
				angle *= 0.65
			skeleton.set_bone_pose_rotation(bone, rest_local.basis.get_rotation_quaternion() * Quaternion(axis.normalized(), deg_to_rad(angle)))


func _pose_thumb(side: String, frame: Basis, support: bool, directions: Array = []) -> void:
	for joint: int in range(1, 4):
		var bone: int = _bone(side + "HandThumb" + str(joint))
		var pose: Transform3D = skeleton.get_bone_global_pose(bone)
		var direction: Vector3 = Vector3(0.5, 0.866, 0.0) if joint == 1 else Vector3(0.05, 1.0, 0.0)
		if support:
			direction = Vector3(0.6, 0.1, -0.8) if joint == 1 else Vector3(1.0, 0.0, 0.0)
		# Индивидуальный хват задаёт направления большого пальца в осях ладони.
		if directions.size() >= joint:
			direction = WeaponGrips.vector(directions[joint - 1] as Array)
		var swing: Basis = Basis(Quaternion(pose.basis.y.normalized(), (frame * direction).normalized()))
		pose.basis = swing * pose.basis
		pose.basis = pose.basis.orthonormalized()
		skeleton.set_bone_global_pose(bone, pose)
