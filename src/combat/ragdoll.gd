class_name Ragdoll
extends Node3D
## Регдолл для капсульных персонажей: при смерти капсула прячется, на её месте — манекен из
## 11 тел (голова, грудь, таз, плечи/предплечья, бёдра/голени) на суставах с пределами
## сгиба. Импульс пули/взрыва — в ту часть, куда попали. Чисто визуальный: считается на каждом
## peer у себя, в сеть не идёт. Через RAGDOLL_FREEZE_SEC тела замирают, чтобы не жрать физику.
## По телам можно стрелять — они дёргаются от пуль (слой LAYER_DEBRIS).

## Части: имя -> [форма, размер/радиус+высота, центр в позе стоя (м), масса]
const PARTS := {
	"pelvis": ["box", Vector3(0.32, 0.2, 0.22), Vector3(0, 0.95, 0), 12.0],
	"chest": ["box", Vector3(0.38, 0.42, 0.24), Vector3(0, 1.28, 0), 16.0],
	"head": ["sphere", Vector3(0.12, 0, 0), Vector3(0, 1.64, 0.01), 5.0],
	"arm_l": ["capsule", Vector3(0.055, 0.32, 0), Vector3(0.25, 1.3, 0), 2.5],
	"arm_r": ["capsule", Vector3(0.055, 0.32, 0), Vector3(-0.25, 1.3, 0), 2.5],
	"fore_l": ["capsule", Vector3(0.048, 0.3, 0), Vector3(0.25, 0.99, 0), 1.8],
	"fore_r": ["capsule", Vector3(0.048, 0.3, 0), Vector3(-0.25, 0.99, 0), 1.8],
	"thigh_l": ["capsule", Vector3(0.075, 0.44, 0), Vector3(0.1, 0.63, 0), 8.0],
	"thigh_r": ["capsule", Vector3(0.075, 0.44, 0), Vector3(-0.1, 0.63, 0), 8.0],
	"shin_l": ["capsule", Vector3(0.06, 0.44, 0), Vector3(0.1, 0.22, 0), 4.5],
	"shin_r": ["capsule", Vector3(0.06, 0.44, 0), Vector3(-0.1, 0.22, 0), 4.5],
}

## Суставы: [тело A, тело B, точка в позе стоя, пределы X (сгиб вперёд-назад), Y (скрут), Z (вбок)], рад.
## Знак X: поворот вокруг +X уводит нижний конец тела B назад (−Z) — так сгибается колено.
const JOINTS := [
	["chest", "head", Vector3(0, 1.52, 0), Vector2(-0.6, 0.7), Vector2(-0.8, 0.8), Vector2(-0.4, 0.4)],
	["pelvis", "chest", Vector3(0, 1.06, 0), Vector2(-0.5, 0.9), Vector2(-0.4, 0.4), Vector2(-0.3, 0.3)],
	["chest", "arm_l", Vector3(0.24, 1.46, 0), Vector2(-2.2, 1.0), Vector2(-0.8, 0.8), Vector2(-0.3, 1.5)],
	["chest", "arm_r", Vector3(-0.24, 1.46, 0), Vector2(-2.2, 1.0), Vector2(-0.8, 0.8), Vector2(-1.5, 0.3)],
	["arm_l", "fore_l", Vector3(0.25, 1.14, 0), Vector2(-2.3, 0.0), Vector2(-0.1, 0.1), Vector2(-0.05, 0.05)],
	["arm_r", "fore_r", Vector3(-0.25, 1.14, 0), Vector2(-2.3, 0.0), Vector2(-0.1, 0.1), Vector2(-0.05, 0.05)],
	["pelvis", "thigh_l", Vector3(0.1, 0.87, 0), Vector2(-1.6, 0.4), Vector2(-0.4, 0.4), Vector2(-0.2, 0.7)],
	["pelvis", "thigh_r", Vector3(-0.1, 0.87, 0), Vector2(-1.6, 0.4), Vector2(-0.4, 0.4), Vector2(-0.7, 0.2)],
	["thigh_l", "shin_l", Vector3(0.1, 0.43, 0), Vector2(0.0, 2.3), Vector2(-0.05, 0.05), Vector2(-0.05, 0.05)],
	["thigh_r", "shin_r", Vector3(-0.1, 0.43, 0), Vector2(0.0, 2.3), Vector2(-0.05, 0.05), Vector2(-0.05, 0.05)],
]

var bodies: Dictionary = {}
var _age: float = 0.0


## Ставит манекен в позу персонажа (xf — корень на полу, лицом по +Z), толкает импульсом в точке at.
## body_mat/head_mat — материалы капсулы и «лица», чтобы тело не меняло цвет при падении.
static func spawn(parent: Node, xf: Transform3D, velocity: Vector3, impulse: Vector3, at: Vector3, body_mat: Material, head_mat: Material) -> Ragdoll:
	var rd := Ragdoll.new()
	rd.name = "Ragdoll"
	rd.add_to_group("ragdolls")
	parent.add_child(rd)
	rd.global_transform = Transform3D.IDENTITY
	for id in PARTS:
		var spec: Array = PARTS[id]
		var b := RagdollPart.new()
		b.name = id
		b.mass = float(spec[3])
		b.linear_damp = float(Balance.RAGDOLL_DAMP.linear)
		b.angular_damp = float(Balance.RAGDOLL_DAMP.angular)
		b.collision_layer = Hitscan.LAYER_DEBRIS
		b.collision_mask = Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_DEBRIS | Hitscan.LAYER_GLASS
		b.continuous_cd = true
		var cs := CollisionShape3D.new()
		var mi := MeshInstance3D.new()
		var size: Vector3 = spec[1]
		match String(spec[0]):
			"box":
				var sh := BoxShape3D.new()
				sh.size = size
				cs.shape = sh
				var bm := CapsuleMesh.new()
				bm.radius = minf(size.x, size.z) * 0.55
				bm.height = size.y + 0.08
				mi.mesh = bm
				mi.scale = Vector3(size.x / (bm.radius * 2.0), 1.0, size.z / (bm.radius * 2.0))
			"sphere":
				var sh := SphereShape3D.new()
				sh.radius = size.x
				cs.shape = sh
				var sm := SphereMesh.new()
				sm.radius = size.x
				sm.height = size.x * 2.0
				mi.mesh = sm
			_:
				var sh := CapsuleShape3D.new()
				sh.radius = size.x
				sh.height = size.y
				cs.shape = sh
				var cm := CapsuleMesh.new()
				cm.radius = size.x
				cm.height = size.y
				mi.mesh = cm
		mi.material_override = head_mat if id == "head" else body_mat
		b.add_child(cs)
		b.add_child(mi)
		rd.add_child(b)
		b.global_transform = xf * Transform3D(Basis.IDENTITY, spec[2])
		b.linear_velocity = velocity * Balance.RAGDOLL_CARRY
		rd.bodies[id] = b
	for j in JOINTS:
		var joint := Generic6DOFJoint3D.new()
		rd.add_child(joint)
		joint.global_transform = xf * Transform3D(Basis.IDENTITY, j[2])
		joint.node_a = joint.get_path_to(rd.bodies[j[0]])
		joint.node_b = joint.get_path_to(rd.bodies[j[1]])
		var lims: Array[Vector2] = [j[3], j[4], j[5]]
		for axis in range(3):
			var lim: Vector2 = lims[axis]
			match axis:
				0:
					joint.set_flag_x(Generic6DOFJoint3D.FLAG_ENABLE_ANGULAR_LIMIT, true)
					joint.set_param_x(Generic6DOFJoint3D.PARAM_ANGULAR_LOWER_LIMIT, lim.x)
					joint.set_param_x(Generic6DOFJoint3D.PARAM_ANGULAR_UPPER_LIMIT, lim.y)
				1:
					joint.set_flag_y(Generic6DOFJoint3D.FLAG_ENABLE_ANGULAR_LIMIT, true)
					joint.set_param_y(Generic6DOFJoint3D.PARAM_ANGULAR_LOWER_LIMIT, lim.x)
					joint.set_param_y(Generic6DOFJoint3D.PARAM_ANGULAR_UPPER_LIMIT, lim.y)
				2:
					joint.set_flag_z(Generic6DOFJoint3D.FLAG_ENABLE_ANGULAR_LIMIT, true)
					joint.set_param_z(Generic6DOFJoint3D.PARAM_ANGULAR_LOWER_LIMIT, lim.x)
					joint.set_param_z(Generic6DOFJoint3D.PARAM_ANGULAR_UPPER_LIMIT, lim.y)
	rd.push(impulse, at)
	return rd


## Толчок в ближайшую к точке часть (пуля, осколок, взрыв).
func push(impulse: Vector3, at: Vector3) -> void:
	var best: RigidBody3D = null
	var best_d := INF
	for id in bodies:
		var b: RigidBody3D = bodies[id]
		var d := b.global_position.distance_to(at)
		if d < best_d:
			best_d = d
			best = b
	if best:
		for id in bodies:
			(bodies[id] as RigidBody3D).freeze = false
		best.apply_impulse(impulse, at - best.global_position)
		_age = 0.0


## Грудь — за ней следит камера, когда погиб свой игрок.
func chest() -> Node3D:
	return bodies.get("chest")


func _physics_process(delta: float) -> void:
	_age += delta
	if _age > Balance.RAGDOLL_FREEZE_SEC:
		for id in bodies:
			var b: RigidBody3D = bodies[id]
			if b.linear_velocity.length() < 0.05:
				b.freeze = true
