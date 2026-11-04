class_name PhoneHandGrip
extends RefCounted
## Thumb contact on the physical side button, using the existing hand's measured chain.

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
