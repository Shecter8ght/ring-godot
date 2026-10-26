class_name GrenadeModel
extends Node3D
## Игровая производная принятой v08. Чека с кольцом и скоба остаются отдельными узлами.

const ASSET: String = "res://assets/models/weapons/grenade/grenade.glb"
const HANDS: String = "res://assets/models/weapons/grenade/grenade_veras_hands.glb"
static var _materials: Dictionary = {}
var hands_model: Node3D
var hands_skeleton: Skeleton3D
var _hands_animation: AnimationPlayer
var _hands_progress: float = -1.0
var _hand_pose: HandGripPose = HandGripPose.new()
var _pin: Node3D
var _lever: Node3D
var _pin_home: Vector3 = Vector3.ZERO
var _lever_home: Vector3 = Vector3.ZERO
var _left_home: Transform3D = Transform3D.IDENTITY
var _pin_mesh: MeshInstance3D


static func create(first_person: bool = false) -> GrenadeModel:
	var root: GrenadeModel = GrenadeModel.new()
	root.name = "Weapon_grenade"
	if ResourceLoader.exists(ASSET):
		var model: Node3D = (load(ASSET) as PackedScene).instantiate() as Node3D
		root.add_child(model)
		for child: Node in model.find_children("*", "MeshInstance3D", true, false):
			var mesh: MeshInstance3D = child as MeshInstance3D
			mesh.material_override = _material("body" if String(mesh.name) == "LP_GrenadeBody" else "mechanism")
		root._pin = model.find_child("Pin", true, false) as Node3D
		root._lever = model.find_child("Lever", true, false) as Node3D
		root._pin_mesh = model.find_child("LP_SafetyPin", true, false) as MeshInstance3D
		root.set_meta("asset_loaded", true)
	else:
		# Обязательный запасной вид проекта при недоступной библиотеке assets.
		WeaponModels._grenade(root)
		root.set_meta("asset_loaded", false)
	if root._pin:
		root._pin_home = root._pin.position
	if root._lever:
		root._lever_home = root._lever.rotation
	WeaponGrips.fit(root, "grenade", {}, {})
	var left: Node3D = root.get_node_or_null("LeftGrip") as Node3D
	if left:
		root._left_home = left.transform
	root.set_meta("ads_z", 0.38)
	root.set_meta("sight_h", 0.0)
	if first_person:
		root._attach_hands()
	return root


func _attach_hands() -> void:
	if not ResourceLoader.exists(HANDS):
		return
	hands_model = (load(HANDS) as PackedScene).instantiate() as Node3D
	hands_model.name = "VERAS54_Hands"
	add_child(hands_model)
	set_meta("hands_source", "VERAS54_FPS_ArmsRig")
	var skeletons: Array[Node] = hands_model.find_children("*", "Skeleton3D", true, false)
	if not skeletons.is_empty():
		hands_skeleton = skeletons[0] as Skeleton3D
		_hand_pose.configure(hands_skeleton, true)
	var animations: Array[Node] = hands_model.find_children("*", "AnimationPlayer", true, false)
	if not animations.is_empty():
		_hands_animation = animations[0] as AnimationPlayer
		_hands_animation.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
		if _hands_animation.has_animation("pin_pull"):
			_hands_animation.play("pin_pull")
			_hands_animation.seek(0.0, true)


static func _material(atlas: String) -> StandardMaterial3D:
	if _materials.has(atlas):
		return _materials[atlas] as StandardMaterial3D
	var material: StandardMaterial3D = StandardMaterial3D.new()
	var path: String = "res://assets/models/weapons/grenade/grenade_%s_" % atlas
	material.albedo_texture = load(path + "albedo.png") as Texture2D
	var orm: Texture2D = load(path + "orm.png") as Texture2D
	material.roughness_texture = orm
	material.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
	material.metallic = 1.0
	material.metallic_texture = orm
	material.metallic_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_BLUE
	material.ao_enabled = true
	material.ao_texture = orm
	material.ao_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	material.normal_enabled = true
	material.normal_texture = load(path + "normal.png") as Texture2D
	_materials[atlas] = material
	return material


func prepare(progress: float) -> void:
	# Возвращаем позу до уменьшения даже при неподвижной чеке: иначе масштаб копится.
	_hand_pose.restore()
	var amount: float = clampf(progress, 0.0, 1.0)
	if _hands_animation and _hands_animation.has_animation("pin_pull") and not is_equal_approx(_hands_progress, amount):
		_hands_progress = amount
		_hands_animation.seek(amount * _hands_animation.get_animation("pin_pull").length, true)
		_hands_animation.advance(0.0)
	# Исходный контроль двигает чеку по −Y Blender, то есть +Z после glTF.
	var travel: float = 0.0006 * minf(1.0, amount / 0.16) + 0.0514 * maxf(0.0, (amount - 0.16) / 0.84)
	if _pin:
		_pin.visible = true
		_pin.position = _pin_home + Vector3(0.0, 0.0, travel)
	if _lever:
		_lever.visible = true
		_lever.rotation = _lever_home
	if _pin_mesh and _pin_mesh.mesh.get_blend_shape_count() > 0:
		_pin_mesh.set_blend_shape_value(0, minf(1.0, amount / 0.16))
	var left: Node3D = get_node_or_null("LeftGrip") as Node3D
	if left:
		left.transform = _left_home
		if amount > 0.0 and _pin:
			left.position = _pin_home + Vector3(0.0155, -0.0075, 0.0122 + travel)
			left.set_meta("curl", [20, 80, 65])
		else:
			left.set_meta("curl", [25, 45, 30])
	if is_inside_tree() and hands_skeleton:
		var k: float = HandGripPose.hand_scale()
		if not is_equal_approx(k, 1.0):
			_hand_pose.capture_once()
			for side: String in HandGripProfiles.SIDES:
				_hand_pose.scale_hand(side, k)


func release() -> void:
	# Летящая граната уже без извлечённой чеки и отпущенного рычага.
	if _pin:
		_pin.visible = false
	if _lever:
		_lever.visible = false
