class_name WeaponClearance
extends RefCounted
## Проверяет законченный объём оружия с обвесами и кистями, затем выбирает свободную позу.
## IK получает преобразование всей сборки: обе кисти сохраняют исходные точки хвата.

const MASK: int = Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_GLASS
var weight: float = 0.0
var ready_up: bool = false
var valid: bool = true
var low_ready_lift: float = 0.0
var sideways: bool = false
var bounds: AABB
var _pivot: Vector3 = Vector3.ZERO
var _animated: bool = false
## Руки со скелетом (вьюмодель с клипами): кисти берутся по костям, а поза клипа появляется только
## после первого шага анимации — габарит пересчитать тогда.
var _pose_pending: bool = false
var _box: BoxShape3D = BoxShape3D.new()
var _query: PhysicsShapeQueryParameters3D = PhysicsShapeQueryParameters3D.new()
static var _segment: CapsuleShape3D = CapsuleShape3D.new()
static var _segment_query: PhysicsShapeQueryParameters3D = PhysicsShapeQueryParameters3D.new()
static var _sphere: SphereShape3D = SphereShape3D.new()
static var _sphere_query: PhysicsShapeQueryParameters3D = PhysicsShapeQueryParameters3D.new()


func bind(model: Node3D) -> void:
	weight = 0.0
	valid = true
	_animated = false
	_refresh_bounds(model)
	_pose_pending = not _hand_bones(model).is_empty()
	_query.shape = _box
	_query.collision_mask = MASK
	_query.margin = float(Balance.WEAPON_CLEARANCE.margin)


## Магазин и кисть покидают исходный объём во время перезарядки.
func refresh_action(model: Node3D, rig: WeaponRig) -> void:
	var busy: bool = (rig != null and rig.is_busy()) or (model.has_method("is_busy") and bool(model.call("is_busy")))
	if busy or _animated or _pose_pending: _refresh_bounds(model)
	_animated = busy
	_pose_pending = false
	# у сцены рук с клипами (ВЕРАС) рига нет: кисти уже в габарите по костям
	if busy and rig != null:
		var hand: Node3D = rig.get_hand_target()
		if hand and rig.get_hand_weight() > 0.0:
			var pose: Transform3D = WeaponRig._relative_transform(hand, model)
			var point: Vector3 = pose.origin
			var radius: Vector3 = Vector3.ONE * float(Balance.WEAPON_CLEARANCE.hand_radius)
			bounds = bounds.merge(AABB(point - radius, radius * 2.0))
			var grip: Node3D = model.find_child("LeftGrip", true, false) as Node3D
			if grip:
				var wrist: Vector3 = point - pose.basis.orthonormalized() * (grip.get_meta("palm_offset", Vector3.ZERO) as Vector3)
				bounds = bounds.merge(AABB(wrist - radius, radius * 2.0))


func _refresh_bounds(model: Node3D) -> void:
	bounds = AABB()
	_pivot = Vector3.ZERO
	var first: bool = true
	for node: Node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh: MeshInstance3D = node as MeshInstance3D
		# У меша со скелетом get_aabb — габарит позы покоя (у рук из Blender это T-поза шириной
		# 1.6 м): ствол упирался бы во всё вокруг. Кисти таких рук — ниже, по костям.
		if mesh.mesh == null or mesh.skin != null or bool(mesh.get_meta("weapon_clearance_ignore", false)) or String(mesh.name).begins_with("Laser"):
			continue
		var local: AABB = WeaponRig._relative_transform(mesh, model) * mesh.get_aabb()
		bounds = local if first else bounds.merge(local)
		first = false
	for side: String in ["Right", "Left"]:
		var grip: Node3D = model.find_child(side + "Grip", true, false) as Node3D
		if grip:
			var local: Transform3D = WeaponRig._relative_transform(grip, model)
			var wrist: Vector3 = local.origin - local.basis.orthonormalized() * (grip.get_meta("palm_offset", Vector3.ZERO) as Vector3)
			var radius: Vector3 = Vector3.ONE * float(Balance.WEAPON_CLEARANCE.hand_radius)
			bounds = bounds.merge(AABB(wrist - radius, radius * 2.0)).merge(AABB(local.origin - radius, radius * 2.0))
			if side == "Right": _pivot = wrist
	var radius: Vector3 = Vector3.ONE * float(Balance.WEAPON_CLEARANCE.hand_radius)
	var inverse: Transform3D = model.global_transform.affine_inverse() if model.is_inside_tree() else Transform3D.IDENTITY
	for hand: Array in _hand_bones(model):
		var sk: Skeleton3D = hand[0] as Skeleton3D
		var point: Vector3 = inverse * (sk.global_transform * sk.get_bone_global_pose(int(hand[1])).origin) if model.is_inside_tree() 			else WeaponRig._relative_transform(sk, model) * sk.get_bone_global_pose(int(hand[1])).origin
		bounds = bounds.merge(AABB(point - radius, radius * 2.0))
		if String(hand[2]) == "R": _pivot = point


## Кисти рук со скелетом: [скелет, кость, сторона]. Только у скелетов, на которых есть кожа.
func _hand_bones(model: Node3D) -> Array:
	var out: Array = []
	for node: Node in model.find_children("*", "Skeleton3D", true, false):
		var sk: Skeleton3D = node as Skeleton3D
		for side: String in ["L", "R"]:
			var bone: int = sk.find_bone("hand." + side)
			if bone >= 0:
				out.append([sk, bone, side])
	return out


## Transform3D может содержать масштаб ViewmodelSpace: переводим все восемь углов в OBB.
func _prepare(pose: Transform3D, exclude: Array[RID]) -> void:
	var basis: Basis = pose.basis.orthonormalized()
	var local: AABB = Transform3D(basis.inverse() * pose.basis, Vector3.ZERO) * bounds
	_box.size = local.size.max(Vector3.ONE * 0.001)
	_query.transform = Transform3D(basis, pose.origin + basis * local.get_center())
	_query.exclude = exclude
	_query.motion = Vector3.ZERO


## Опора под стволом (земля, пол, ступень — контакт снизу) не преграда: на неё оружие ложится,
## а не «складывается». Преграда — то, во что ствол упирается сбоку или спереди (стена, столб, дерево).
const GROUND_NORMAL_Y: float = 0.6


func overlaps(world: World3D, pose: Transform3D, exclude: Array[RID] = []) -> bool:
	var ex: Array[RID] = exclude.duplicate()
	for i in range(6):
		_prepare(pose, ex)
		var rest: Dictionary = world.direct_space_state.get_rest_info(_query)
		if rest.is_empty():
			return false
		if (rest.normal as Vector3).y < GROUND_NORMAL_Y:
			return true
		ex.append(rest.rid as RID)
	return true


func _clear(world: World3D, pose: Transform3D, reference: Transform3D, exclude: Array[RID], anticipate: bool) -> bool:
	if overlaps(world, pose, exclude): return false
	if not anticipate: return true
	# упреждение — только по горизонтали взгляда: шаг к стене, а не к земле под ногами
	var ahead: Vector3 = -reference.basis.z
	ahead.y = 0.0
	if ahead.length() < 0.2: return true
	_query.motion = ahead.normalized() * float(Balance.WEAPON_CLEARANCE.lead)
	var fractions: PackedFloat32Array = world.direct_space_state.cast_motion(_query)
	return fractions.is_empty() or fractions[0] >= 0.999


func folded(pose: Transform3D, reference: Transform3D, amount: float, up: bool) -> Transform3D:
	var direction: float = 1.0 if up else -1.0
	var axis: Vector3 = reference.basis.y if sideways else reference.basis.x
	var turn: Basis = Basis(axis.normalized(), deg_to_rad(float(Balance.WEAPON_CLEARANCE.ready_deg)) * amount * direction)
	var pivot: Vector3 = pose * _pivot
	var origin: Vector3 = pivot + turn * (pose.origin - pivot)
	var retract: float = float(Balance.WEAPON_CLEARANCE.action_retract if _animated else Balance.WEAPON_CLEARANCE.retract)
	if up and not sideways and not _animated: retract = float(Balance.WEAPON_CLEARANCE.high_retract)
	if sideways and not _animated: retract = float(Balance.WEAPON_CLEARANCE.prone_retract)
	origin += reference.basis.z.normalized() * retract * amount
	origin += reference.basis.y.normalized() * float(Balance.WEAPON_CLEARANCE.lift) * amount * direction
	# Поднятый ствол держится у плеча: кисть не должна оказаться перед самым глазом.
	if up and not sideways:
		origin -= reference.basis.y.normalized() * float(Balance.WEAPON_CLEARANCE.high_drop) * amount
	elif not sideways:
		var action_drop: float = float(Balance.WEAPON_CLEARANCE.low_drop) if _animated else 0.0
		origin += reference.basis.y.normalized() * (low_ready_lift - action_drop) * amount
	return Transform3D(turn * pose.basis, origin)


func _minimum(world: World3D, pose: Transform3D, reference: Transform3D, exclude: Array[RID], up: bool, anticipate: bool) -> float:
	var steps: int = int(Balance.WEAPON_CLEARANCE.samples)
	var low: float = 0.0
	for step: int in range(1, steps + 1):
		var high: float = float(step) / float(steps)
		if _clear(world, folded(pose, reference, high, up), reference, exclude, anticipate):
			for iteration: int in range(int(Balance.WEAPON_CLEARANCE.refine)):
				var middle: float = (low + high) * 0.5
				if _clear(world, folded(pose, reference, middle, up), reference, exclude, anticipate): high = middle
				else: low = middle
			return high
		low = high
	return INF


func solve(world: World3D, pose: Transform3D, reference: Transform3D, exclude: Array[RID], delta: float, minimum: float = 0.0, prefer_up: bool = false) -> Transform3D:
	if world == null: return pose
	if weight < 0.001: ready_up = prefer_up
	var required: float = 0.0
	if not _clear(world, pose, reference, exclude, true):
		required = _minimum(world, pose, reference, exclude, ready_up, true)
		if not is_finite(required):
			var alternative: float = _minimum(world, pose, reference, exclude, not ready_up, true)
			if is_finite(alternative):
				ready_up = not ready_up
				required = alternative
		# В очень тесном месте сохранить фактический зазор, даже если ранний запас не помещается.
		if not is_finite(required):
			required = _minimum(world, pose, reference, exclude, ready_up, false)
			if not is_finite(required):
				required = _minimum(world, pose, reference, exclude, not ready_up, false)
				if is_finite(required): ready_up = not ready_up
	valid = is_finite(required)
	if not valid: required = 1.0
	required = maxf(required, minimum)
	var seconds: float = float(Balance.WEAPON_CLEARANCE.enter_sec if required > weight else Balance.WEAPON_CLEARANCE.return_sec)
	weight = move_toward(weight, required, delta / seconds)
	var result: Transform3D = folded(pose, reference, weight, ready_up)
	# При быстром движении ограничение объёма важнее плавности визуального возврата.
	if overlaps(world, result, exclude):
		weight = maxf(weight, required)
		result = folded(pose, reference, weight, ready_up)
	valid = valid and not overlaps(world, result, exclude)
	return result


static func segment_clear(world: World3D, a: Vector3, b: Vector3, radius: float, exclude: Array[RID] = []) -> bool:
	if world == null: return true
	var line: Vector3 = b - a
	_segment.radius = radius
	_segment.height = line.length() + radius * 2.0
	var query: PhysicsShapeQueryParameters3D = _segment_query
	query.shape = _segment
	query.transform = Transform3D(Basis(Quaternion(Vector3.UP, line.normalized())) if line.length_squared() > 0.000001 else Basis.IDENTITY, (a + b) * 0.5)
	query.collision_mask = MASK
	query.exclude = exclude
	return world.direct_space_state.intersect_shape(query, 1).is_empty()


static func safe_shoulder(world: World3D, point: Vector3, radius: float, exclude: Array[RID], anchor: Vector3 = Vector3.INF) -> Vector3:
	_sphere.radius = radius
	var query: PhysicsShapeQueryParameters3D = _sphere_query
	query.shape = _sphere
	query.collision_mask = MASK
	query.exclude = exclude
	if anchor.is_finite():
		query.transform = Transform3D(Basis.IDENTITY, anchor)
		query.motion = point - anchor
		var travel: PackedFloat32Array = world.direct_space_state.cast_motion(query)
		if not travel.is_empty() and travel[0] < 1.0:
			var safe: Vector3 = anchor + query.motion * travel[0]
			query.transform.origin = anchor + query.motion * minf(1.0, travel[0] + 0.001)
			var boundary: Dictionary = world.direct_space_state.get_rest_info(query)
			if not boundary.is_empty():
				var normal: Vector3 = boundary.normal
				point += normal * (safe - point).dot(normal)
			else: point = safe
	query.motion = Vector3.ZERO
	for step: int in range(int(Balance.WEAPON_CLEARANCE.shoulder_steps)):
		query.transform = Transform3D(Basis.IDENTITY, point)
		var contact: Dictionary = world.direct_space_state.get_rest_info(query)
		if contact.is_empty(): break
		point += (contact.normal as Vector3) * float(Balance.WEAPON_CLEARANCE.shoulder_step)
	return point
