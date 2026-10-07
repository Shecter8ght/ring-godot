class_name SupportHandIK
extends SkeletonModifier3D
## Опорная (левая) рука на цевье у персонажа целиком (вид сверху, напарники, мародёры).
## Оружие лежит в правой руке (WeaponSocket), клипы Mixamo держат левую где придётся — у
## разных стволов цевьё на разном месте, и кисть висела рядом. После анимации двухзвенная ИК
## (плечо → локоть → запястье) ставит левую кисть на метку LeftGrip модели оружия — ту же, что
## у рук от первого лица; изгиб локтя — как в клипе. Силу (influence) задаёт CharacterAnimator:
## на перезарядке, броске, подборе, раненым и мёртвым рука свободна.

## Узел Grip на кости правой руки: модель оружия — его первый ребёнок.
var grip: Node3D
## На время действия кисть следует за магазином/затвором/глушителем в мировых координатах.
var action_target: Node3D
var action_weight: float = 0.0

var _arm: int = -1
var _fore: int = -1
var _hand: int = -1
var _right: int = -1
var _frame: Basis = Basis.IDENTITY
var _rest_hand: Basis = Basis.IDENTITY
var _model: Node3D
var _marker: Marker3D
var _weapon_rig: WeaponRig


func _ready() -> void:
	var sk := get_skeleton()
	if sk == null:
		return
	_arm = sk.find_bone("mixamorig_LeftArm")
	_fore = sk.find_bone("mixamorig_LeftForeArm")
	_hand = sk.find_bone("mixamorig_LeftHand")
	_right = sk.find_bone("mixamorig_RightHand")
	var middle := sk.find_bone("mixamorig_LeftHandMiddle1")
	var index := sk.find_bone("mixamorig_LeftHandIndex1")
	var pinky := sk.find_bone("mixamorig_LeftHandPinky1")
	if mini(mini(_arm, _fore), mini(_hand, _right)) < 0 or mini(middle, mini(index, pinky)) < 0:
		_arm = -1
		return
	# рамка ладони в позе покоя — как у FirstPersonArms: метка хвата задана в тех же осях
	var wrist := sk.get_bone_global_rest(_hand).origin
	var forward := (sk.get_bone_global_rest(middle).origin - wrist).normalized()
	var across := sk.get_bone_global_rest(index).origin - sk.get_bone_global_rest(pinky).origin
	across = (across - forward * across.dot(forward)).normalized()
	_frame = Basis(across, forward, across.cross(forward))
	_rest_hand = sk.get_bone_global_rest(_hand).basis


## Метка хвата в осях Grip (правая кисть → сокет → модель → метка); нет модели / метки — null.
func _target_in_grip() -> Variant:
	if not is_instance_valid(grip) or not grip.is_inside_tree() or grip.is_queued_for_deletion() or grip.get_child_count() == 0:
		return null
	var model := grip.get_child(0) as Node3D
	if not is_instance_valid(model) or not model.is_inside_tree() or model.is_queued_for_deletion():
		return null
	if not is_instance_valid(_model) or model != _model:
		_model = model
		_marker = model.find_child("LeftGrip", true, false) as Marker3D if model else null
		_weapon_rig = WeaponRig.find_on(model)
	if not is_instance_valid(_marker) or not _marker.is_inside_tree() or _marker.is_queued_for_deletion():
		return null
	var rest: Transform3D = grip.global_transform.affine_inverse() * _marker.global_transform
	if is_instance_valid(action_target) and action_target.is_inside_tree() and not action_target.is_queued_for_deletion() and action_weight > 0.0:
		var action: Transform3D = grip.global_transform.affine_inverse() * action_target.global_transform
		rest = rest.interpolate_with(action, clampf(action_weight, 0.0, 1.0))
	return rest


func _process_modification() -> void:
	if not is_inside_tree():
		return
	var sk := get_skeleton()
	if sk == null or _arm < 0 or not sk.is_inside_tree():
		return
	var in_grip: Variant = _target_in_grip()
	if in_grip == null:
		return
	var target: Transform3D = sk.get_bone_global_pose(_right) * grip.transform * (in_grip as Transform3D)
	# масштаб оружия меняет расстояния, но не размер кисти: от ладони к запястью — в метрах кисти
	target.basis = target.basis.orthonormalized()
	var wrist: Vector3 = target.origin - target.basis * (_marker.get_meta("palm_offset", Vector3.ZERO) as Vector3)
	var arm_pose := sk.get_bone_global_pose(_arm)
	var fore_pose := sk.get_bone_global_pose(_fore)
	var hand_pose := sk.get_bone_global_pose(_hand)
	var a := arm_pose.origin
	var b := fore_pose.origin
	var c := hand_pose.origin
	var upper := a.distance_to(b)
	var lower := b.distance_to(c)
	# локоть гнётся туда же, куда в клипе (иначе — вниз)
	var solution: Dictionary = ArmIKSolver.solve(a, wrist, upper, lower, b - a, sk.global_transform, get_world_3d())
	var elbow: Vector3 = solution.elbow
	var reach: Vector3 = solution.wrist
	var q_arm := Basis(Quaternion((b - a).normalized(), (elbow - a).normalized()))
	var arm_basis := q_arm * arm_pose.basis.orthonormalized()
	var q_fore := Basis(Quaternion((q_arm * (c - b)).normalized(), (reach - elbow).normalized()))
	var fore_basis := q_fore * q_arm * fore_pose.basis.orthonormalized()
	# ладонь — по метке хвата (пальцы вдоль цевья), как у рук от первого лица
	var hand_basis := target.basis * _frame.inverse() * _rest_hand
	_set_global_rotation(sk, _arm, sk.get_bone_global_pose(sk.get_bone_parent(_arm)).basis.orthonormalized(), arm_basis)
	_set_global_rotation(sk, _fore, arm_basis, fore_basis)
	_set_global_rotation(sk, _hand, fore_basis, hand_basis)
	_pose_pm_fingers(sk)


## У ПМ поддерживающие пальцы обхватывают правую кисть: клип целиком задавал прямые фаланги.
## Оси и углы совпадают с хватом FPS; influence модификатора плавно возвращает позу клипа.
func _pose_pm_fingers(sk: Skeleton3D) -> void:
	if not is_instance_valid(_weapon_rig) or _weapon_rig.weapon_id != "wpn_hg_01":
		return
	var curl: Array = _marker.get_meta("curl", []) as Array
	if curl.size() < 3:
		return
	var palm: Vector3 = -_frame.z
	for finger: String in ["Index", "Middle", "Ring", "Pinky"]:
		for joint: int in range(1, 4):
			var bone: int = sk.find_bone("mixamorig_LeftHand" + finger + str(joint))
			if bone < 0:
				continue
			var rest_global: Basis = sk.get_bone_global_rest(bone).basis
			var direction: Vector3 = rest_global.y.normalized()
			var axis: Vector3 = rest_global.inverse() * direction.cross(palm).normalized()
			var rest_rotation: Quaternion = sk.get_bone_rest(bone).basis.get_rotation_quaternion()
			sk.set_bone_pose_rotation(bone, rest_rotation * Quaternion(axis.normalized(), deg_to_rad(float(curl[joint - 1]))))
	var directions: Array = _marker.get_meta("thumb_directions", []) as Array
	if directions.size() < 3:
		return
	var palm_basis: Basis = sk.get_bone_global_pose(_hand).basis * _rest_hand.inverse() * _frame
	for joint: int in range(1, 4):
		var bone: int = sk.find_bone("mixamorig_LeftHandThumb" + str(joint))
		if bone < 0:
			continue
		var pose: Basis = sk.get_bone_global_pose(bone).basis.orthonormalized()
		var direction: Vector3 = (palm_basis * WeaponGrips.vector(directions[joint - 1] as Array)).normalized()
		var desired: Basis = Basis(Quaternion(pose.y.normalized(), direction)) * pose
		_set_global_rotation(sk, bone, sk.get_bone_global_pose(sk.get_bone_parent(bone)).basis.orthonormalized(), desired)


func _set_global_rotation(sk: Skeleton3D, bone: int, parent_basis: Basis, global_basis: Basis) -> void:
	sk.set_bone_pose_rotation(bone, (parent_basis.inverse() * global_basis).orthonormalized().get_rotation_quaternion())
