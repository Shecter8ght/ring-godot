class_name SkinRagdoll
extends PhysicalBoneSimulator3D
## Регдолл на самой модели персонажа (тот же скин, скелет Mixamo «mixamorig_*»): при смерти поверх
## текущей позы скелета ставятся физические кости — капсулы на таз, позвоночник, голову, плечи,
## предплечья, бёдра, голени; суставы с пределами (локти и колени — петли). Кости без физики
## (кисти, стопы, шея, плечевые) идут за родителем. Только картинка: у каждого peer свой, не
## синхронизируется; пули и взрывы толкают (Hitscan, Grenade — группа "ragdolls").

## кость → [до какой кости капсула (пусто — своя длина len), радиус, м, сустав, len м, доля длины]
## Голень — до 0.8 пути к стопе, стопа — своя тонкая капсула до 0.75 пути к носку: ничто не уходит
## в землю с первого кадра (капсула голени до самой стопы была в земле — физика выталкивала, ноги
## тряслись) и стопа не проваливается. Колени и локти — «limb»: узкий конус с малым скручиванием
## (петля с жёсткими пределами упиралась в предел и дрожала).
const BONES := {
	"Hips": ["Spine", 0.13, "", 0.0],
	"Spine": ["Spine2", 0.13, "cone", 0.0],
	"Spine2": ["Neck", 0.15, "cone", 0.0],
	"Head": ["", 0.1, "cone", 0.22],
	"LeftArm": ["LeftForeArm", 0.055, "cone", 0.0],
	"LeftForeArm": ["LeftHand", 0.045, "limb", 0.0],
	"RightArm": ["RightForeArm", 0.055, "cone", 0.0],
	"RightForeArm": ["RightHand", 0.045, "limb", 0.0],
	"LeftUpLeg": ["LeftLeg", 0.08, "cone", 0.0],
	"LeftLeg": ["LeftFoot", 0.055, "limb", 0.0, 0.8],
	"LeftFoot": ["LeftToeBase", 0.03, "foot", 0.0, 0.75],
	"RightUpLeg": ["RightLeg", 0.08, "cone", 0.0],
	"RightLeg": ["RightFoot", 0.055, "limb", 0.0, 0.8],
	"RightFoot": ["RightToeBase", 0.03, "foot", 0.0, 0.75],
}
## масса части, кг: близкие массы — суставы не «дрожат» (большой перепад масс в цепочке раскачивает
## решатель); корпус чуть тяжелее — тело падает «мешком», а не машет руками
const MASS := {"LeftFoot": 2.0, "RightFoot": 2.0, "Hips": 6.0, "Spine": 5.0, "Spine2": 5.0, "Head": 3.0, "LeftUpLeg": 4.0, "RightUpLeg": 4.0,
	"LeftLeg": 3.0, "RightLeg": 3.0}
## Улёгся: все части медленнее этого, м/с, столько секунд — тело замирает совсем (без вечной дрожи).
const REST_SPEED := 0.2
const REST_SEC := 0.6
## Позже этого, с, — замирает в любом случае.
const MAX_SEC := 4.0

## Ноги сталкиваются только друг с другом (свои слои физики).
const LEG_L := ["LeftUpLeg", "LeftLeg", "LeftFoot"]
const LEG_R := ["RightUpLeg", "RightLeg", "RightFoot"]
const LAYER_LEG_L := 1 << 12
const LAYER_LEG_R := 1 << 13

var _prefix: String = "mixamorig_"
var _chest: PhysicalBone3D
var _t: float = 0.0
var _still: float = 0.0
var _frozen: bool = false


## Положить скелет в регдолл: поза — как сейчас, скорость тела — velocity, толчок impulse в точке at
## (мир). Анимация и модификаторы скелета должны быть уже остановлены. null — скелет не тот.
static func start(skel: Skeleton3D, velocity: Vector3, impulse: Vector3, at: Vector3) -> SkinRagdoll:
	if skel == null or skel.find_bone("mixamorig_Hips") < 0:
		return null
	var r := SkinRagdoll.new()
	r.name = "SkinRagdoll"
	skel.add_child(r)
	r._build(skel)
	r.add_to_group("ragdolls")
	r.physical_bones_start_simulation()
	# движок у симулятора физ-обработку сам не включает — следим, когда тело уляжется
	r.set_physics_process(true)
	for pb in r._bones():
		pb.linear_velocity = velocity
	if impulse.length_squared() > 0.0:
		r.push(impulse, at)
	return r


func _bones() -> Array[PhysicalBone3D]:
	var out: Array[PhysicalBone3D] = []
	for c in get_children():
		if c is PhysicalBone3D:
			out.append(c as PhysicalBone3D)
	return out


func _build(skel: Skeleton3D) -> void:
	var damp: Dictionary = Balance.RAGDOLL_DAMP
	for key in BONES:
		var spec: Array = BONES[key]
		var b := skel.find_bone(_prefix + String(key))
		if b < 0:
			continue
		var pose := skel.get_bone_global_pose(b)
		var a := pose.origin
		var tip: Vector3
		var tb := skel.find_bone(_prefix + String(spec[0])) if String(spec[0]) != "" else -1
		if tb >= 0:
			tip = skel.get_bone_global_pose(tb).origin
		else:
			# своя длина — вдоль «вверх» кости (голова)
			tip = a + pose.basis.y.normalized() * float(spec[3])
		if spec.size() > 4:
			tip = a + (tip - a) * float(spec[4])
		var dir := tip - a
		var length := maxf(dir.length(), 0.05)
		dir = dir / length
		var radius := float(spec[1])
		# тело — посередине кости, ось капсулы (Y) — вдоль кости
		var y := dir
		var x := y.cross(Vector3.FORWARD if absf(y.dot(Vector3.FORWARD)) < 0.9 else Vector3.RIGHT).normalized()
		var z := x.cross(y).normalized()
		var body := Transform3D(Basis(x, y, z), a + dir * length * 0.5)
		var pb := PhysicalBone3D.new()
		pb.name = "PB_" + String(key)
		pb.bone_name = _prefix + String(key)
		pb.body_offset = pose.affine_inverse() * body
		# сустав — в начале кости: у конуса ось скручивания (X) — вдоль кости, у петли ось (Z) —
		# поперёк тела (x — вбок: кость × «вперёд»), колено и локоть гнутся вперёд-назад
		var jb := Basis(y, z, x) if String(spec[2]) == "hinge" else Basis(y, -x, z)
		pb.joint_offset = body.affine_inverse() * Transform3D(jb, a)
		match String(spec[2]):
			"cone":
				pb.joint_type = PhysicalBone3D.JOINT_TYPE_CONE
				pb.set("joint_constraints/swing_span", 50.0 if String(key) != "Head" else 35.0)
				pb.set("joint_constraints/twist_span", 25.0)
			"limb":
				pb.joint_type = PhysicalBone3D.JOINT_TYPE_CONE
				pb.set("joint_constraints/swing_span", 70.0)
				pb.set("joint_constraints/twist_span", 8.0)
			"foot":
				# стопа гнётся мало (носок «как у Аладдина» — от свободного сустава; уже 35° — решатель
				# с лёгкой короткой стопой срывается)
				pb.joint_type = PhysicalBone3D.JOINT_TYPE_CONE
				pb.set("joint_constraints/swing_span", 35.0)
				pb.set("joint_constraints/twist_span", 10.0)
			"hinge":
				pb.joint_type = PhysicalBone3D.JOINT_TYPE_HINGE
				pb.set("joint_constraints/angular_limit_enabled", true)
				# запас по обе стороны от прямой: сустав не упирается в предел в покое
				pb.set("joint_constraints/angular_limit_upper", 10.0)
				pb.set("joint_constraints/angular_limit_lower", -130.0)
				pb.set("joint_constraints/angular_limit_softness", 0.9)
				pb.set("joint_constraints/angular_limit_relaxation", 0.5)
			_:
				pb.joint_type = PhysicalBone3D.JOINT_TYPE_NONE
		pb.mass = float(MASS.get(key, 2.0))
		pb.linear_damp = float(damp.linear) * 0.5
		pb.angular_damp = float(damp.angular)
		pb.friction = 1.0
		pb.bounce = 0.0
		# с миром; друг с другом — только левая нога с правой (колено не проходит в колено). Части
		# одной цепочки не сталкиваются: соседние капсулы перекрываются и вечно расталкивались бы
		# («желе»). Пули их видят (слой debris).
		pb.collision_layer = Hitscan.LAYER_DEBRIS
		pb.collision_mask = Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR
		if String(key) in LEG_L:
			pb.collision_layer |= LAYER_LEG_L
			pb.collision_mask |= LAYER_LEG_R
		elif String(key) in LEG_R:
			pb.collision_layer |= LAYER_LEG_R
			pb.collision_mask |= LAYER_LEG_L
		var cs := CollisionShape3D.new()
		var cap := CapsuleShape3D.new()
		cap.radius = radius
		cap.height = maxf(length, radius * 2.0 + 0.01)
		cs.shape = cap
		pb.add_child(cs)
		add_child(pb)
		if String(key) == "Spine2":
			_chest = pb



func _physics_process(delta: float) -> void:
	if _frozen or not is_simulating_physics():
		return
	_t += delta
	var fast := false
	for pb in _bones():
		if pb.linear_velocity.length() > REST_SPEED or pb.angular_velocity.length() > REST_SPEED * 10.0:
			fast = true
			break
	_still = 0.0 if fast else _still + delta
	if _still >= REST_SEC or _t >= MAX_SEC:
		_freeze()


## Тело улеглось: части — неподвижные (статика), поза остаётся как есть.
func _freeze() -> void:
	_frozen = true
	for pb in _bones():
		PhysicsServer3D.body_set_mode(pb.get_rid(), PhysicsServer3D.BODY_MODE_STATIC)


## Грудь — для взрывов (куда толкать).
func chest() -> Node3D:
	return _chest


## Толчок пулей / взрывом: в ближайшую к точке часть тела.
func push(impulse: Vector3, at: Vector3) -> void:
	var best: PhysicalBone3D = null
	var bd := INF
	for pb in _bones():
		var d := pb.global_position.distance_squared_to(at)
		if d < bd:
			bd = d
			best = pb
	if best:
		# толкнули улёгшееся тело — снова живое
		if _frozen:
			_frozen = false
			_still = 0.0
			_t = 0.0
			for pb in _bones():
				PhysicsServer3D.body_set_mode(pb.get_rid(), PhysicsServer3D.BODY_MODE_RIGID)
		best.apply_impulse(impulse, at - best.global_position)
