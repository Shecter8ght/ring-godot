class_name ArmIKSolver
extends RefCounted
## Аналитическая двухзвенная цепь: длины сохраняются, свободный локоть выбирается по рукаву.

static func solve(shoulder: Vector3, target: Vector3, upper: float, lower: float, pole: Vector3, skeleton_world: Transform3D, world: World3D = null, exclude: Array[RID] = [], eye: Vector3 = Vector3.INF) -> Dictionary:
	var delta: Vector3 = target - shoulder
	var distance: float = clampf(delta.length(), absf(upper - lower) + float(Balance.WEAPON_CLEARANCE.reach_margin), upper + lower - float(Balance.WEAPON_CLEARANCE.reach_margin))
	var direction: Vector3 = delta.normalized() if delta.length_squared() > 0.000001 else Vector3.FORWARD
	var reach: Vector3 = shoulder + direction * distance
	pole -= direction * pole.dot(direction)
	if pole.length_squared() < 0.000001:
		pole = direction.cross(Vector3.RIGHT if absf(direction.x) < 0.9 else Vector3.UP)
	pole = pole.normalized()
	var along: float = (upper * upper - lower * lower + distance * distance) / (2.0 * distance)
	var height: float = sqrt(maxf(0.0, upper * upper - along * along))
	var elbow: Vector3 = shoulder + direction * along + pole * height
	var radius: float = float(Balance.WEAPON_CLEARANCE.sleeve_radius) * maxf(skeleton_world.basis.x.length(), maxf(skeleton_world.basis.y.length(), skeleton_world.basis.z.length()))
	var upper_radius: float = radius * float(Balance.WEAPON_CLEARANCE.upper_sleeve_radius) / float(Balance.WEAPON_CLEARANCE.sleeve_radius)
	for angle: float in Balance.WEAPON_CLEARANCE.elbow_angles:
		var candidate: Vector3 = shoulder + direction * along + pole.rotated(direction, deg_to_rad(angle)) * height
		if eye.is_finite() and (not _eye_clear(eye, skeleton_world * shoulder, skeleton_world * candidate, upper_radius) or not _eye_clear(eye, skeleton_world * candidate, skeleton_world * reach, radius)):
			continue
		if WeaponClearance.segment_clear(world, skeleton_world * shoulder, skeleton_world * candidate, upper_radius, exclude) \
			and WeaponClearance.segment_clear(world, skeleton_world * candidate, skeleton_world * reach, radius, exclude):
			return {"elbow":candidate, "wrist":reach, "clear":true}
	return {"elbow":elbow, "wrist":reach, "clear":false}


static func _eye_clear(eye: Vector3, a: Vector3, b: Vector3, radius: float) -> bool:
	var line: Vector3 = b - a
	var t: float = clampf((eye - a).dot(line) / maxf(line.length_squared(), 0.000001), 0.0, 1.0)
	return eye.distance_to(a + line * t) > radius + float(Balance.WEAPON_CLEARANCE.view_clear)
