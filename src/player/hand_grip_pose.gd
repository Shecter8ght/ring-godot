class_name HandGripPose
extends RefCounted
## Один слой ручной подгонки для общих рук и клипов ВЕРАСа. Оси сгиба вычисляются
## из исходной анатомии, а не из имён осей конкретного экспорта Blender.

var skeleton: Skeleton3D
var chains: Dictionary = {}
var fingers: Dictionary = {}
## Точка хвата на ладони в осях кости кисти (rest) — вокруг неё кисть меняет размер.
var grip_centers: Dictionary = {}
var _tips: Dictionary = {}
var _saved: Dictionary = {}
## Стенд задаёт размер кистей сам (> 0); иначе FPS_HAND_SCALE из окружения или Balance.
static var scale_override: float = 0.0
static var _env_scale: float = -1.0


static func hand_scale() -> float:
	if scale_override > 0.0:
		return scale_override
	if _env_scale < 0.0:
		var env: String = OS.get_environment("FPS_HAND_SCALE")
		_env_scale = clampf(env.to_float(), 0.3, 2.0) if env.is_valid_float() else 0.0
	return _env_scale if _env_scale > 0.0 else float(Balance.FPS_HAND_SCALE.k)


## Размер кистей для конкретных рук: у выгрузки с исправленными пропорциями (tools/fps_hands_fix.py, в её .json —
## hands_fix; владелец 2026-11-06: «руки в порядок привести») кисть уже настоящего размера — 1.0; у прежних (клипы
## ВЕРАСа, руки гранаты) — Balance.FPS_HAND_SCALE.k. Проба стенда и FPS_HAND_SCALE из окружения — поверх обоих.
static func hand_scale_for(fixed: bool) -> float:
	if scale_override > 0.0:
		return scale_override
	hand_scale()
	if _env_scale > 0.0:
		return _env_scale
	return 1.0 if fixed else float(Balance.FPS_HAND_SCALE.k)


func configure(sk: Skeleton3D, clips: bool) -> void:
	skeleton = sk
	chains.clear()
	fingers.clear()
	_tips.clear()
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
		var center: Vector3 = wrist + (bases[1] - wrist) * float(Balance.FPS_HAND_SCALE.forward) + palm * float(Balance.FPS_HAND_SCALE.palm)
		grip_centers[side] = sk.get_bone_global_rest(bones[2]).affine_inverse() * center
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
			var turn: Vector3 = (entry.rotation as Array)[index] as Vector3
			if turn.is_zero_approx() and is_zero_approx(bend[index]) and (index != 0 or (is_zero_approx(float(entry.spread)) and is_zero_approx(float(entry.twist)))):
				continue
			var joint: Dictionary = joints[index]
			var q: Quaternion = Quaternion(joint.curl as Vector3, deg_to_rad(bend[index]) * weight)
			if index == 0:
				q *= Quaternion(joint.spread as Vector3, deg_to_rad(float(entry.spread)) * weight)
				q *= Quaternion(Vector3.UP, deg_to_rad(float(entry.twist)) * weight)
			q *= Quaternion.IDENTITY.slerp(Basis.from_euler(turn * (PI / 180.0)).get_rotation_quaternion(), weight)
			var bone: int = int(joint.bone)
			skeleton.set_bone_pose_rotation(bone, (skeleton.get_bone_pose_rotation(bone) * q).normalized())


## Конец перчатки из весов последней фаланги; исходная сетка и риг не изменяются.
func finger_tip_offset(side: String, finger: String) -> Vector3:
	var key: String = side + finger
	if _tips.has(key):
		return _tips[key] as Vector3
	var joints: Array = fingers.get(key, [])
	if joints.size() != 3:
		return Vector3.ZERO
	var bone: int = int(joints[2].bone)
	var length: float = skeleton.get_bone_global_rest(bone).origin.distance_to(skeleton.get_bone_global_rest(int(joints[1].bone)).origin) * 0.8
	var samples: Array[Vector3] = []
	for node: Node in skeleton.find_children("*", "MeshInstance3D", true, false):
		var instance: MeshInstance3D = node as MeshInstance3D
		if instance.mesh == null or instance.skin == null:
			continue
		var bind: int = -1
		for index: int in range(instance.skin.get_bind_count()):
			if instance.skin.get_bind_bone(index) == bone or instance.skin.get_bind_name(index) == skeleton.get_bone_name(bone):
				bind = index
				break
		if bind < 0:
			continue
		for surface: int in range(instance.mesh.get_surface_count()):
			var arrays: Array = instance.mesh.surface_get_arrays(surface)
			if arrays[Mesh.ARRAY_BONES] == null or arrays[Mesh.ARRAY_WEIGHTS] == null:
				continue
			var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var bones: PackedInt32Array = arrays[Mesh.ARRAY_BONES]
			var weights: PackedFloat32Array = arrays[Mesh.ARRAY_WEIGHTS]
			var stride: int = bones.size() / vertices.size()
			for vertex: int in range(vertices.size()):
				for slot: int in range(stride):
					if bones[vertex * stride + slot] == bind and weights[vertex * stride + slot] >= 0.3:
						samples.append(instance.skin.get_bind_pose(bind) * vertices[vertex])
	var furthest: float = 0.0
	for point: Vector3 in samples:
		furthest = maxf(furthest, point.y)
	var tip: Vector3 = Vector3(0.0, length, 0.0)
	if furthest > 0.004 and furthest < 0.09:
		var center: Vector3 = Vector3.ZERO
		var count: int = 0
		for point: Vector3 in samples:
			if point.y >= furthest * 0.9:
				center += point
				count += 1
		tip = center / float(maxi(count, 1))
		tip.y = furthest
	_tips[key] = tip
	return tip


func finger_points(side: String, finger: String) -> PackedVector3Array:
	var points: PackedVector3Array = []
	var joints: Array = fingers.get(side + finger, [])
	for joint: Dictionary in joints:
		points.append(skeleton.to_global(skeleton.get_bone_global_pose(int(joint.bone)).origin))
	if joints.size() == 3:
		points.append(skeleton.global_transform * skeleton.get_bone_global_pose(int(joints[2].bone)) * finger_tip_offset(side, finger))
	return points


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


## Подгонка хвата могла уже сохранить позу этого кадра — её и оставляем.
func capture_once() -> void:
	if _saved.is_empty():
		capture()


## Кисть вместе с пальцами в k раз: точка хвата на ладони остаётся на месте, запястье подаётся
## к ней, локоть пересчитывается. Уменьшается всё предплечье: у одной кисти манжета перчатки
## уходила внутрь рукава и из-под неё торчала кожа запястья. Вызывать последним, когда поза кадра готова.
func scale_hand(side: String, k: float) -> void:
	if skeleton == null or not chains.has(side) or not grip_centers.has(side) or is_equal_approx(k, 1.0):
		return
	var forearm_bone: int = chains[side][1]
	var hand: Transform3D = skeleton.get_bone_global_pose(chains[side][2])
	var turn: Basis = hand.basis.orthonormalized()
	var wrist: Vector3 = hand.origin + turn * (grip_centers[side] as Vector3) * (1.0 - k)
	skeleton.set_bone_pose_scale(forearm_bone, skeleton.get_bone_pose_scale(forearm_bone) * k)
	move_arm(side, Transform3D(turn, wrist))


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
