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

var _arm: int = -1
var _fore: int = -1
var _hand: int = -1
var _right: int = -1
var _frame: Basis = Basis.IDENTITY
var _rest_hand: Basis = Basis.IDENTITY
var _model: Node3D
var _marker: Marker3D


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
	if grip == null or grip.get_child_count() == 0:
		return null
	var model := grip.get_child(0) as Node3D
	if model != _model:
		_model = model
		_marker = model.find_child("LeftGrip", false, false) as Marker3D if model else null
	if _marker == null or not is_instance_valid(_marker):
		return null
	return _model.transform * _marker.transform


func _process_modification() -> void:
	var sk := get_skeleton()
	if sk == null or _arm < 0:
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
	var to_t := wrist - a
	var dist := clampf(to_t.length(), 0.01, (upper + lower) * 0.999)
	var dir := to_t.normalized()
	# локоть гнётся туда же, куда в клипе (иначе — вниз)
	var pole := (b - a) - dir * (b - a).dot(dir)
	if pole.length() < 0.001:
		pole = Vector3.DOWN - dir * dir.y
	pole = pole.normalized()
	var along := (upper * upper - lower * lower + dist * dist) / (2.0 * dist)
	var height := sqrt(maxf(0.0, upper * upper - along * along))
	var elbow := a + dir * along + pole * height
	var reach := a + dir * dist
	var q_arm := Basis(Quaternion((b - a).normalized(), (elbow - a).normalized()))
	var arm_basis := q_arm * arm_pose.basis.orthonormalized()
	var q_fore := Basis(Quaternion((q_arm * (c - b)).normalized(), (reach - elbow).normalized()))
	var fore_basis := q_fore * q_arm * fore_pose.basis.orthonormalized()
	# ладонь — по метке хвата (пальцы вдоль цевья), как у рук от первого лица
	var hand_basis := target.basis * _frame.inverse() * _rest_hand
	_set_global_rotation(sk, _arm, sk.get_bone_global_pose(sk.get_bone_parent(_arm)).basis.orthonormalized(), arm_basis)
	_set_global_rotation(sk, _fore, arm_basis, fore_basis)
	_set_global_rotation(sk, _hand, fore_basis, hand_basis)


func _set_global_rotation(sk: Skeleton3D, bone: int, parent_basis: Basis, global_basis: Basis) -> void:
	sk.set_bone_pose_rotation(bone, (parent_basis.inverse() * global_basis).orthonormalized().get_rotation_quaternion())
