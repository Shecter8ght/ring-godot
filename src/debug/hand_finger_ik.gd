extends RefCounted
## Экспериментальная подгонка одного пальца. FK считается на копии трёх локальных
## поворотов; результат — обычные поправки профиля, без растяжения и физики в рейде.
## TriangleMesh BVH: https://docs.godotengine.org/en/stable/classes/class_trianglemesh.html

const DIRECTIONS: Array[Vector3] = [Vector3.RIGHT, Vector3.LEFT, Vector3.UP, Vector3.DOWN, Vector3.FORWARD, Vector3.BACK]
const INSIDE_RAY: Vector3 = Vector3(1.0, 0.173, 0.327)
const MAX_ITERATIONS: int = 8
const MAX_STEP_DEG: float = 12.0
const CONTACT_WEIGHT: float = 120.0
## BVH в миллиметрах: короткие лучи через мелкие треугольники в метрах
## терялись на допуске пересечения Godot (особенно спусковая скоба).
const BVH_UNITS: float = 1000.0

var pose: HandGripPose
var side: String
var finger: String
var rotations: Array[Vector3] = []
var colliders: Array[Dictionary] = []
var _bones: Array[int] = []
var _locals: Array[Transform3D] = []
var _reference: Array[Quaternion] = []
var _start: Array[Vector3] = []
var _parent: Transform3D
var _tip: Vector3
var _cache: Dictionary = {}
var last_usec: int = 0


func begin(overlay: HandGripPose, hand_side: String, digit: String, entry: Dictionary) -> bool:
	pose = overlay
	side = hand_side
	finger = digit
	_bones.clear()
	_locals.clear()
	_reference.clear()
	rotations.clear()
	var joints: Array = pose.fingers.get(side + finger, [])
	if joints.size() != 3:
		return false
	for index: int in range(3):
		var bone: int = int(joints[index].bone)
		_bones.append(bone)
		_locals.append(pose.skeleton.get_bone_pose(bone))
		var turn: Vector3 = entry.rotation[index] as Vector3
		rotations.append(turn)
		var extra: Quaternion = Basis.from_euler(turn * (PI / 180.0)).get_rotation_quaternion()
		_reference.append((pose.skeleton.get_bone_pose_rotation(bone) * extra.inverse()).normalized())
	_start = rotations.duplicate()
	_tip = pose.finger_tip_offset(side, finger)
	_sync_parent()
	return true


func _sync_parent() -> void:
	var parent: int = pose.skeleton.get_bone_parent(_bones[0])
	_parent = pose.skeleton.global_transform
	if parent >= 0:
		_parent *= pose.skeleton.get_bone_global_pose(parent)


func points(turns: Array[Vector3]) -> PackedVector3Array:
	var result: PackedVector3Array = []
	var transform: Transform3D = _parent
	for index: int in range(3):
		var q: Quaternion = _reference[index] * Basis.from_euler(turns[index] * (PI / 180.0)).get_rotation_quaternion()
		transform *= Transform3D(Basis(q).scaled(_locals[index].basis.get_scale()), _locals[index].origin)
		result.append(transform.origin)
	result.append(transform * _tip)
	return result


## Один BVH на неизменную сетку; поза подвижных деталей фиксируется при начале drag.
## Оружейные сетки со skin запекаются только в памяти. Скелет рук всегда исключён.
func rebuild_colliders(root: Node3D, hands: Skeleton3D) -> int:
	colliders.clear()
	for node: Node in root.find_children("*", "MeshInstance3D", true, false):
		var instance: MeshInstance3D = node as MeshInstance3D
		if not instance.is_visible_in_tree() or instance.mesh == null or instance.has_meta("reticle_dot"):
			continue
		var ignored: bool = false
		var ancestor: Node = instance
		while ancestor != null and ancestor != root:
			if bool(ancestor.get_meta("weapon_clearance_ignore", false)):
				ignored = true
				break
			ancestor = ancestor.get_parent()
		if ignored or (instance.skin != null and instance.get_node_or_null(instance.skeleton) == hands):
			continue
		var mesh: Mesh = instance.mesh
		if instance.skin != null:
			mesh = instance.bake_mesh_from_current_skeleton_pose()
		if mesh == null:
			continue
		var id: int = mesh.get_instance_id()
		var cached: Dictionary = _cache.get(id, {}) as Dictionary
		var triangle: TriangleMesh = cached.get("triangles") as TriangleMesh
		if triangle == null:
			var faces: PackedVector3Array = mesh.get_faces()
			if faces.is_empty():
				continue
			for vertex: int in range(faces.size()):
				faces[vertex] *= BVH_UNITS
			triangle = TriangleMesh.new()
			if not triangle.create_from_faces(faces):
				continue
			# Сохраняем ресурс вместе с BVH: instance_id не должен переиспользоваться.
			if instance.skin == null:
				_cache[id] = {"mesh": mesh, "triangles": triangle}
		var scale: Vector3 = instance.global_basis.get_scale().abs()
		var inverse: Transform3D = Transform3D(Basis.IDENTITY.scaled(Vector3.ONE * BVH_UNITS), Vector3.ZERO) * instance.global_transform.affine_inverse()
		var bounds: AABB = mesh.get_aabb()
		colliders.append({"mesh": mesh, "triangles": triangle,
			"instance": weakref(instance),
			"inverse": inverse, "forward": inverse.affine_inverse(),
			"bounds": AABB(bounds.position * BVH_UNITS, bounds.size * BVH_UNITS),
			"min_scale": maxf(0.001, minf(scale.x, minf(scale.y, scale.z))) / BVH_UNITS})
	return colliders.size()


func _sync_colliders() -> void:
	for item: Dictionary in colliders:
		var instance: MeshInstance3D = (item.instance as WeakRef).get_ref() as MeshInstance3D
		if instance == null:
			continue
		var inverse: Transform3D = Transform3D(Basis.IDENTITY.scaled(Vector3.ONE * BVH_UNITS), Vector3.ZERO) * instance.global_transform.affine_inverse()
		item.inverse = inverse
		item.forward = inverse.affine_inverse()
		var scale: Vector3 = instance.global_basis.get_scale().abs()
		item.min_scale = maxf(0.001, minf(scale.x, minf(scale.y, scale.z))) / BVH_UNITS


func _inside_depth(triangle: TriangleMesh, point: Vector3, bounds: AABB) -> float:
	var direction: Vector3 = INSIDE_RAY.normalized()
	var finish: Vector3 = point + direction * (bounds.size.length() * 2.0 + 1.0)
	var start: Vector3 = point
	var count: int = 0
	var first: float = 0.0
	for attempt: int in range(32):
		var hit: Dictionary = triangle.intersect_segment(start, finish)
		if hit.is_empty():
			return first if count % 2 == 1 else -1.0
		if count == 0:
			first = point.distance_to(hit.position as Vector3)
		count += 1
		start = (hit.position as Vector3) + direction * 0.01
	# Сложная / открытая сетка: короткие лучи ниже всё ещё проверят поверхность.
	return -1.0


func contact_depth(point: Vector3, radius: float) -> float:
	var depth: float = 0.0
	for item: Dictionary in colliders:
		var inverse: Transform3D = item.inverse as Transform3D
		var at: Vector3 = inverse * point
		var local_radius: float = radius / float(item.min_scale)
		var bounds: AABB = item.bounds as AABB
		if not bounds.grow(local_radius).has_point(at):
			continue
		var triangle: TriangleMesh = item.triangles as TriangleMesh
		if bounds.has_point(at):
			var inside: float = _inside_depth(triangle, at, bounds)
			if inside >= 0.0:
				depth = maxf(depth, radius + minf(inside * float(item.min_scale), 0.03))
				continue
		for direction: Vector3 in DIRECTIONS:
			var hit: Dictionary = triangle.intersect_segment(at, inverse * (point + direction * radius))
			if not hit.is_empty():
				var distance: float = ((item.forward as Transform3D) * (hit.position as Vector3)).distance_to(point)
				depth = maxf(depth, radius - distance)
	return depth


func penetration(chain: PackedVector3Array, radius: float) -> float:
	var result: float = 0.0
	for index: int in range(3):
		for fraction: float in [0.25, 0.5, 0.75, 1.0]:
			var depth: float = contact_depth(chain[index].lerp(chain[index + 1], fraction), radius)
			result += depth * depth
		# Тонкая скоба между пробами не должна исчезать из проверки.
		for item: Dictionary in colliders:
			var inverse: Transform3D = item.inverse as Transform3D
			var hit: Dictionary = (item.triangles as TriangleMesh).intersect_segment(inverse * chain[index], inverse * chain[index + 1])
			if not hit.is_empty():
				result += radius * radius
	return result


func _cost(turns: Array[Vector3], target: Vector3, radius: float) -> float:
	var chain: PackedVector3Array = points(turns)
	var cost: float = chain[3].distance_squared_to(target)
	if radius > 0.0:
		cost += penetration(chain, radius) * CONTACT_WEIGHT
	for index: int in range(3):
		# Небольшой приоритет ближайшей исходной позы, без самопроизвольных оборотов.
		cost += turns[index].distance_squared_to(_start[index]) * 0.0000000001
	return cost


func solve(target: Vector3, radius: float) -> Dictionary:
	var started: int = Time.get_ticks_usec()
	_sync_parent()
	_sync_colliders()
	var score: float = _cost(rotations, target, radius)
	for iteration: int in range(MAX_ITERATIONS):
		var improved: bool = false
		var step: float = MAX_STEP_DEG / pow(2.0, float(iteration / 2))
		# От основания к кончику: препятствие на средней фаланге влияет на всю цепь.
		for index: int in range(3):
			for axis: int in range(3):
				var chosen: float = rotations[index][axis]
				for sign_value: float in [-1.0, 1.0]:
					var candidate: Array[Vector3] = rotations.duplicate()
					candidate[index][axis] = clampf(rotations[index][axis] + sign_value * step,
						maxf(-180.0, _start[index][axis] - 110.0), minf(180.0, _start[index][axis] + 110.0))
					var trial: float = _cost(candidate, target, radius)
					if trial < score - 0.00000000001:
						score = trial
						chosen = candidate[index][axis]
						improved = true
				rotations[index][axis] = chosen
		if not improved and iteration >= 4:
			break
	var chain: PackedVector3Array = points(rotations)
	last_usec = Time.get_ticks_usec() - started
	return {"rotation": rotations.duplicate(), "points": chain,
		"error": chain[3].distance_to(target), "contact": radius > 0.0 and penetration(chain, radius) > 0.000001}
