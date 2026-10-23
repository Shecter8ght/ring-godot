class_name HandGripPose
extends RefCounted
## Один слой ручной подгонки для общих рук и клипов ВЕРАСа. Оси сгиба вычисляются
## из исходной анатомии, а не из имён осей конкретного экспорта Blender.

var skeleton: Skeleton3D
var chains: Dictionary = {}
var fingers: Dictionary = {}
var _saved: Dictionary = {}


func configure(sk: Skeleton3D, clips: bool) -> void:
	skeleton = sk
	chains.clear()
	fingers.clear()
	if sk == null:
		return
	for side: String in HandGripProfiles.SIDES:
		var suffix: String = ".R" if side == "Right" else ".L"
		var names: Array = ["upper_arm" + suffix, "forearm" + suffix, "hand" + suffix] if clips else ["mixamorig_" + side + "Arm", "mixamorig_" + side + "ForeArm", "mixamorig_" + side + "Hand"]
		var bones: Array[int] = []
		for name: String in names:
			bones.append(sk.find_bone(name))
		if bones.has(-1):
			continue
		chains[side] = bones
		var wrist: Vector3 = sk.get_bone_global_rest(bones[2]).origin
		var bases: Array[Vector3] = []
		for finger: String in ["Index", "Middle", "Pinky"]:
			var bone: int = _finger_bone(side, finger, 1, clips)
			bases.append(sk.get_bone_global_rest(bone).origin if bone >= 0 else wrist + Vector3.UP)
		var forward: Vector3 = (bases[1] - wrist).normalized()
		var across: Vector3 = bases[0] - bases[2]
		across = (across - forward * across.dot(forward)).normalized()
		var palm: Vector3 = across.cross(forward) * (1.0 if side == "Right" else -1.0)
		for finger: String in HandGripProfiles.FINGERS:
			var joints: Array[Dictionary] = []
			for joint: int in range(1, 4):
				var bone: int = _finger_bone(side, finger, joint, clips)
				if bone < 0:
					continue
				var rest: Basis = sk.get_bone_global_rest(bone).basis.orthonormalized()
				var curl: Vector3 = rest.y.cross(palm).normalized()
				joints.append({"bone": bone, "curl": (rest.inverse() * curl).normalized(), "spread": (rest.inverse() * palm).normalized()})
			fingers[side + finger] = joints


func _finger_bone(side: String, finger: String, joint: int, clips: bool) -> int:
	if not clips:
		return skeleton.find_bone("mixamorig_" + side + "Hand" + finger + str(joint))
	var name: String = {"Index": "f_index", "Middle": "f_middle", "Ring": "f_ring", "Pinky": "f_pinky", "Thumb": "thumb"}[finger]
	return skeleton.find_bone("%s.%02d.%s" % [name, joint, "R" if side == "Right" else "L"])


static func wrist_target(base: Transform3D, weapon_basis: Basis, value: Dictionary, weight: float) -> Transform3D:
	if weight <= 0.0 or ((value.position as Vector3).is_zero_approx() and (value.rotation as Vector3).is_zero_approx()):
		return base
	var rotation: Quaternion = Basis.from_euler((value.rotation as Vector3) * (PI / 180.0)).get_rotation_quaternion()
	var turn: Basis = Basis(Quaternion.IDENTITY.slerp(rotation, weight))
	return Transform3D(weapon_basis * turn * weapon_basis.inverse() * base.basis,
		base.origin + weapon_basis * (value.position as Vector3) * weight)


func apply_fingers(side: String, value: Dictionary, weight: float) -> void:
	if skeleton == null or weight <= 0.0:
		return
	for finger: String in HandGripProfiles.FINGERS:
		var entry: Dictionary = (value.fingers as Dictionary)[finger]
		var bend: Vector3 = entry.bend as Vector3
		var joints: Array = fingers.get(side + finger, [])
		for index: int in range(joints.size()):
			if is_zero_approx(bend[index]) and (index != 0 or (is_zero_approx(float(entry.spread)) and is_zero_approx(float(entry.twist)))):
				continue
			var joint: Dictionary = joints[index]
			var q: Quaternion = Quaternion(joint.curl as Vector3, deg_to_rad(bend[index]) * weight)
			if index == 0:
				q *= Quaternion(joint.spread as Vector3, deg_to_rad(float(entry.spread)) * weight)
				q *= Quaternion(Vector3.UP, deg_to_rad(float(entry.twist)) * weight)
			var bone: int = int(joint.bone)
			skeleton.set_bone_pose_rotation(bone, (skeleton.get_bone_pose_rotation(bone) * q).normalized())


## У клипов сохраняем все затронутые кости и возвращаем их ДО следующего шага
## анимации: не все клипы записывают положение, масштаб и каждый сустав пальца.
func capture() -> void:
	_saved.clear()
	if skeleton == null:
		return
	for side: String in chains:
		for bone: int in chains[side]:
			_save_bone(bone)
	for joints: Array in fingers.values():
		for joint: Dictionary in joints:
			_save_bone(int(joint.bone))


func _save_bone(bone: int) -> void:
	_saved[bone] = [skeleton.get_bone_pose_position(bone), skeleton.get_bone_pose_rotation(bone), skeleton.get_bone_pose_scale(bone)]


func restore() -> void:
	if skeleton != null:
		for bone: int in _saved:
			var pose: Array = _saved[bone]
			skeleton.set_bone_pose_position(bone, pose[0])
			skeleton.set_bone_pose_rotation(bone, pose[1])
			skeleton.set_bone_pose_scale(bone, pose[2])
	_saved.clear()


func move_arm(side: String, target: Transform3D) -> void:
	if skeleton == null or not chains.has(side):
		return
	var bones: Array = chains[side]
	var up: Transform3D = skeleton.get_bone_global_pose(bones[0])
	var fore: Transform3D = skeleton.get_bone_global_pose(bones[1])
	var hand: Transform3D = skeleton.get_bone_global_pose(bones[2])
	var upper: float = up.origin.distance_to(fore.origin)
	var lower: float = fore.origin.distance_to(hand.origin)
	var shoulder: Vector3 = up.origin
	var reach: float = (upper + lower) * 0.98
	if shoulder.distance_to(target.origin) > reach:
		shoulder = target.origin + (shoulder - target.origin).normalized() * reach
	var pole: Vector3 = fore.origin - (up.origin + hand.origin) * 0.5
	var solved: Dictionary = ArmIKSolver.solve(shoulder, target.origin, upper, lower, pole, skeleton.global_transform)
	var elbow: Vector3 = solved.elbow
	var wrist: Vector3 = solved.wrist
	var upper_rotation: Basis = Basis(Quaternion((fore.origin - up.origin).normalized(), (elbow - shoulder).normalized()))
	var new_up: Transform3D = Transform3D(upper_rotation * up.basis, shoulder)
	_set_bone(bones[0], new_up)
	var fore_now: Transform3D = new_up * (up.affine_inverse() * fore)
	var lower_rotation: Basis = Basis(Quaternion((upper_rotation * (hand.origin - fore.origin)).normalized(), (wrist - elbow).normalized()))
	_set_bone(bones[1], Transform3D(lower_rotation * fore_now.basis, elbow))
	_set_bone(bones[2], Transform3D(target.basis, wrist))


func _set_bone(bone: int, pose: Transform3D) -> void:
	var scale: Vector3 = skeleton.get_bone_pose_scale(bone)
	skeleton.set_bone_global_pose(bone, pose)
	skeleton.set_bone_pose_scale(bone, scale)
