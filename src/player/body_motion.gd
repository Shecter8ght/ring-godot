class_name BodyMotion
extends SkeletonModifier3D
## Живость поверх клипов (модификатор скелета после анимации, до рук у оружия — SupportHandIK и
## WeaponCollisionIK идут следом и ставят кисти уже к повёрнутому корпусу). Углы считает
## CharacterAnimator (там же пружины и сглаживание), здесь они только раскладываются по костям:
## - ноги с тазом отстают от корпуса при поворотах (hips_yaw), корпус доворачивается обратно (torso_yaw);
## - корпус и голова смотрят вверх-вниз за прицелом (pitch, head_pitch) — ствол идёт за взглядом;
## - наклон вбок при выглядывании (roll), голова при этом держится ровнее;
## - наклон на разгоне, торможении и в повороте (lean_fwd, lean_side);
## - дыхание грудью и плечами (breath), подброс от выстрела (recoil), вздрагивание от попадания (flinch).
## Оси — модели Persona: +Z вперёд, +X влево, +Y вверх. Углы в радианах.

var model: Node3D
var hips_yaw: float = 0.0
var torso_yaw: float = 0.0
var pitch: float = 0.0
var head_pitch: float = 0.0
## + — наклон вправо.
var roll: float = 0.0
## + — корпус вперёд.
var lean_fwd: float = 0.0
## + — корпус вправо.
var lean_side: float = 0.0
var breath: float = 0.0
## + — ствол и грудь вверх.
var recoil: float = 0.0
## x — вбок (+ вправо), y — назад (+ корпус назад).
var flinch: Vector2 = Vector2.ZERO

const UP := Vector3(0.0, 1.0, 0.0)
const FORWARD := Vector3(0.0, 0.0, 1.0)
## Вправо от персонажа: -X модели.
const RIGHT := Vector3(-1.0, 0.0, 0.0)

var _hips: int = -1
var _spine: PackedInt32Array = PackedInt32Array()
var _neck: int = -1
var _head: int = -1
var _shoulder_l: int = -1
var _shoulder_r: int = -1


func _ready() -> void:
	var sk := get_skeleton()
	if sk == null:
		return
	_hips = sk.find_bone("mixamorig_Hips")
	_spine = PackedInt32Array([sk.find_bone("mixamorig_Spine"), sk.find_bone("mixamorig_Spine1"), sk.find_bone("mixamorig_Spine2")])
	_neck = sk.find_bone("mixamorig_Neck")
	_head = sk.find_bone("mixamorig_Head")
	_shoulder_l = sk.find_bone("mixamorig_LeftShoulder")
	_shoulder_r = sk.find_bone("mixamorig_RightShoulder")
	if _hips < 0 or _spine.has(-1) or _neck < 0 or _head < 0:
		_hips = -1


func _process_modification() -> void:
	var sk := get_skeleton()
	if sk == null or _hips < 0 or not is_instance_valid(model) or not sk.is_inside_tree():
		return
	# оси модели → оси скелета (у GLB скелет может лежать под повёрнутым узлом)
	var m2s: Basis = sk.global_basis.orthonormalized().inverse() * model.global_basis.orthonormalized()
	var up: Vector3 = (m2s * UP).normalized()
	var fwd: Vector3 = (m2s * FORWARD).normalized()
	var right: Vector3 = (m2s * RIGHT).normalized()
	# таз с ногами — на отставание ног
	_turn(sk, _hips, Quaternion(up, hips_yaw))
	# позвоночник снизу вверх: доворот, взгляд, наклоны, дыхание, отдача, вздрагивание (доли — Balance)
	var share: Dictionary = Balance.BODY_MOTION.spine
	for i in range(_spine.size()):
		var k: Array = share[str(i)]
		var p: float = pitch * float(k[0]) - lean_fwd * float(k[1]) + breath * float(k[2]) + recoil * float(k[3]) + flinch.y * float(k[4])
		var r: float = (roll * float(k[5]) + lean_side * float(k[1]) + flinch.x * float(k[4]))
		_turn(sk, _spine[i], Quaternion(up, -torso_yaw * float(k[6])) * Quaternion(right, p) * Quaternion(fwd, r))
	# голова держит взгляд: отдача и дыхание её почти не качают, при выглядывании — ровнее корпуса
	var head: Dictionary = Balance.BODY_MOTION.head
	var hp: float = head_pitch * 0.5 - (recoil + breath) * float(head.steady) * 0.5
	var hr: float = -roll * float(head.roll_keep) * 0.5
	_turn(sk, _neck, Quaternion(right, hp) * Quaternion(fwd, hr))
	_turn(sk, _head, Quaternion(right, hp) * Quaternion(fwd, hr))
	# вдох поднимает плечи
	var lift: float = breath * float(Balance.BODY_MOTION.shoulder_breath)
	if _shoulder_l >= 0:
		_turn(sk, _shoulder_l, Quaternion(fwd, lift))
	if _shoulder_r >= 0:
		_turn(sk, _shoulder_r, Quaternion(fwd, -lift))


## Повернуть кость вокруг её начала поворотом q в осях скелета; дети идут следом.
func _turn(sk: Skeleton3D, bone: int, q: Quaternion) -> void:
	if q.is_equal_approx(Quaternion.IDENTITY):
		return
	var parent: int = sk.get_bone_parent(bone)
	var parent_basis: Basis = sk.get_bone_global_pose(parent).basis.orthonormalized() if parent >= 0 else Basis.IDENTITY
	var global_basis: Basis = Basis(q) * sk.get_bone_global_pose(bone).basis.orthonormalized()
	sk.set_bone_pose_rotation(bone, (parent_basis.inverse() * global_basis).orthonormalized().get_rotation_quaternion())
