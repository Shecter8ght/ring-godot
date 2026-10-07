class_name WeaponCollisionIK
extends SkeletonModifier3D
## Правая рука отводит оружие от стены; следующий SupportHandIK ставит левую на новое цевьё.
## Модификатор работает после клипа и до обновления BoneAttachment, без сдвига одного оружия.

var grip: Node3D
var actor: CharacterBody3D
var enabled_for_pose: bool = true
var clearance: WeaponClearance = WeaponClearance.new()
var max_hand_error: float = 0.0
var arms_clear: bool = true
var _model: Node3D
var _right: int = -1
var _fore: int = -1
var _arm: int = -1


func _ready() -> void:
	var skeleton: Skeleton3D = get_skeleton()
	if skeleton:
		_right = skeleton.find_bone("mixamorig_RightHand")
		_fore = skeleton.find_bone("mixamorig_RightForeArm")
		_arm = skeleton.find_bone("mixamorig_RightArm")


func _process_modification() -> void:
	if not is_inside_tree(): return
	var skeleton: Skeleton3D = get_skeleton()
	if not enabled_for_pose or not is_instance_valid(grip) or not grip.visible or skeleton == null or _arm < 0 or grip.get_child_count() == 0:
		return
	var model: Node3D = grip.get_child(0) as Node3D
	if model == null or model.is_queued_for_deletion(): return
	if _model != model:
		_model = model
		clearance.bind(model)
	clearance.refresh_action(model, WeaponRig.find_on(model))
	var hand: Transform3D = skeleton.get_bone_global_pose(_right)
	var wanted: Transform3D = skeleton.global_transform * hand * grip.transform * model.transform
	var body: Node3D = actor.get_node_or_null("Body") as Node3D
	var forward: Vector3 = body.global_basis.z.normalized() if body else actor.global_basis.z.normalized()
	var floor_weight: float = 0.0
	clearance.sideways = actor is Player and (actor as Player).stance == Player.Stance.PRONE
	if actor is Player:
		var person: Player = actor as Player
		forward = person.look_dir() if person.ads else (person.get_node("Body") as Node3D).global_basis.z.normalized()
		if not person.is_local() or person.ads:
			floor_weight = person.weapon_obstruction
			clearance.ready_up = person.weapon_ready_up
	var up: Vector3 = Vector3.UP if absf(forward.y) < 0.99 else Vector3.FORWARD
	var reference: Transform3D = Transform3D(Basis.looking_at(forward, up), actor.global_position)
	var exclude: Array[RID] = [actor.get_rid()]
	# В полном клипе рукоять у груди: небольшой подъём сохраняет досягаемость цевья.
	clearance.low_ready_lift = float(Balance.WEAPON_CLEARANCE.body_low_lift)
	var solved: Transform3D = clearance.solve(get_world_3d(), wanted, reference, exclude, get_process_delta_time(), floor_weight, clearance.ready_up or clearance.sideways)
	model.visible = clearance.valid
	if not clearance.valid:
		var support: SupportHandIK = skeleton.get_node_or_null("SupportHandIK") as SupportHandIK
		if support: support.influence = 0.0
	if actor is Player:
		var person: Player = actor as Player
		if person.is_local() and not person.ads:
			person.weapon_obstruction = clearance.weight if clearance.valid else 1.0
			person.weapon_ready_up = clearance.ready_up
	max_hand_error = 0.0
	arms_clear = true
	if clearance.weight > 0.0001:
		var target: Transform3D = skeleton.global_transform.affine_inverse() * solved * wanted.affine_inverse() * skeleton.global_transform * hand
		_solve_arm(skeleton, "Right", target, exclude)
	# Свободная рука продолжает клип, но её запястье и рукав также учитывают препятствия.
	var left: int = skeleton.find_bone("mixamorig_LeftHand")
	if left >= 0:
		var left_pose: Transform3D = skeleton.get_bone_global_pose(left)
		var position: Vector3 = WeaponClearance.safe_shoulder(get_world_3d(), skeleton.global_transform * left_pose.origin, float(Balance.WEAPON_CLEARANCE.hand_radius), exclude)
		left_pose.origin = skeleton.global_transform.affine_inverse() * position
		_solve_arm(skeleton, "Left", left_pose, exclude)


func _solve_arm(skeleton: Skeleton3D, side: String, target: Transform3D, exclude: Array[RID]) -> void:
	var arm: int = skeleton.find_bone("mixamorig_" + side + "Arm")
	var fore: int = skeleton.find_bone("mixamorig_" + side + "ForeArm")
	var hand: int = skeleton.find_bone("mixamorig_" + side + "Hand")
	var arm_pose: Transform3D = skeleton.get_bone_global_pose(arm)
	var fore_pose: Transform3D = skeleton.get_bone_global_pose(fore)
	var hand_pose: Transform3D = skeleton.get_bone_global_pose(hand)
	if not clearance.valid:
		var safe: Vector3 = WeaponClearance.safe_shoulder(get_world_3d(), skeleton.global_transform * target.origin, float(Balance.WEAPON_CLEARANCE.hand_radius), exclude, skeleton.global_transform * arm_pose.origin)
		target.origin = skeleton.global_transform.affine_inverse() * safe
	var solution: Dictionary = ArmIKSolver.solve(arm_pose.origin, target.origin,
		arm_pose.origin.distance_to(fore_pose.origin), fore_pose.origin.distance_to(hand_pose.origin),
		fore_pose.origin - arm_pose.origin, skeleton.global_transform, get_world_3d(), exclude)
	var elbow: Vector3 = solution.elbow
	var wrist: Vector3 = solution.wrist
	var turn_arm: Basis = Basis(Quaternion((fore_pose.origin - arm_pose.origin).normalized(), (elbow - arm_pose.origin).normalized()))
	var arm_basis: Basis = turn_arm * arm_pose.basis.orthonormalized()
	var turn_fore: Basis = Basis(Quaternion((turn_arm * (hand_pose.origin - fore_pose.origin)).normalized(), (wrist - elbow).normalized()))
	var fore_basis: Basis = turn_fore * turn_arm * fore_pose.basis.orthonormalized()
	var parent_basis: Basis = skeleton.get_bone_global_pose(skeleton.get_bone_parent(arm)).basis.orthonormalized()
	skeleton.set_bone_pose_rotation(arm, (parent_basis.inverse() * arm_basis).get_rotation_quaternion())
	skeleton.set_bone_pose_rotation(fore, (arm_basis.inverse() * fore_basis).get_rotation_quaternion())
	skeleton.set_bone_pose_rotation(hand, (fore_basis.inverse() * target.basis.orthonormalized()).get_rotation_quaternion())
	max_hand_error = maxf(max_hand_error, skeleton.get_bone_global_pose(hand).origin.distance_to(target.origin))
	arms_clear = arms_clear and bool(solution.clear)
