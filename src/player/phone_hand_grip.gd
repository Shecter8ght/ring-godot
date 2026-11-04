class_name PhoneHandGrip
extends RefCounted
## Thumb contact on the physical side button, using the existing hand's measured chain.

static func matrix(rows: Array) -> Transform3D:
	return Transform3D(Basis(Vector3(rows[0][0], rows[1][0], rows[2][0]),
		Vector3(rows[0][1], rows[1][1], rows[2][1]), Vector3(rows[0][2], rows[1][2], rows[2][2])),
		Vector3(rows[0][3], rows[1][3], rows[2][3]))

static func load_pose(path: String, sk: Skeleton3D) -> Dictionary:
	if not FileAccess.file_exists(path): return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not parsed is Dictionary or int(parsed.get("version", 0)) != 1: return {}
	var data: Dictionary = parsed
	var runtime: Array = []
	for entry: Dictionary in data.get("bones", []):
		var bone := sk.find_bone(String(entry.name))
		if bone < 0:
			push_error("Phone pose bone missing: " + String(entry.name)); return {}
		runtime.append({"bone":bone, "transform":matrix(entry.phone_transform)})
	if runtime.is_empty(): return {}
	data["runtime_bones"] = runtime
	data["runtime_phone"] = matrix(data.phone_in_camera)
	return data

static func apply_pose(arms: FirstPersonArms, device: Node3D, data: Dictionary, value: Dictionary) -> void:
	var sk := arms.skeleton
	sk.reset_bone_poses()
	var frame := sk.global_transform.affine_inverse() * device.global_transform
	for entry: Dictionary in data.runtime_bones:
		sk.set_bone_global_pose(int(entry.bone), frame * (entry.transform as Transform3D))
	# The file already contains the owner's 0.8 scale. Do not scale again or solve fingers over it.
	arms.visible = true
	if not (value.position as Vector3).is_zero_approx() or not (value.rotation as Vector3).is_zero_approx():
		var hand := sk.find_bone("mixamorig_RightHand")
		var target := HandGripPose.wrist_target(sk.global_transform * sk.get_bone_global_pose(hand), device.global_basis.orthonormalized(), value, 1.0)
		arms._hand_pose.move_arm("Right", sk.global_transform.affine_inverse() * target)
	arms._hand_pose.apply_fingers("Right", value, 1.0)

static func solve_thumb(arms: FirstPersonArms, target: Vector3) -> float:
	return solve_finger(arms, "Thumb", target)

static func solve_finger(arms: FirstPersonArms, finger: String, target: Vector3) -> float:
	var sk := arms.skeleton
	var hand := arms._hand_pose
	var joints: Array = hand.fingers.get("Right" + finger, [])
	if joints.size() != 3: return INF
	var local_target := sk.global_transform.affine_inverse() * target
	var tip_offset := hand.finger_tip_offset("Right", finger)
	for iteration: int in 8:
		for joint: int in [2, 1, 0]:
			var bone: int = int(joints[joint].bone)
			var pose := sk.get_bone_global_pose(bone)
			var tip := sk.get_bone_global_pose(int(joints[2].bone)) * tip_offset
			var from := tip - pose.origin
			var to := local_target - pose.origin
			if minf(from.length(), to.length()) < 0.0001: continue
			var q := Quaternion(from.normalized(), to.normalized())
			var angle := q.get_angle()
			if angle > 0.3: q = Quaternion.IDENTITY.slerp(q, 0.3 / angle)
			pose.basis = Basis(q) * pose.basis
			sk.set_bone_global_pose(bone, pose)
	var end := sk.get_bone_global_pose(int(joints[2].bone)) * tip_offset
	return end.distance_to(local_target)
