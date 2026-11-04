class_name PhoneWorldModel
extends Node
## Remote device follows the existing right wrist; only the owner renders the private screen.
var actor: Player
var model: QuestPhoneModel
var _skeleton: Skeleton3D
var _hand: int = -1
var _local_frame := Basis.IDENTITY
var _palm_length: float = 0.085

func _ready() -> void:
	process_priority = 90

func _process(_delta: float) -> void:
	var visible := actor.phone_equipped and actor.is_alive() and not actor.is_downed() and (not actor.is_local() or not actor.ads)
	if not visible:
		if is_instance_valid(model): model.visible = false
		return
	if not is_instance_valid(model):
		if actor._animator == null or not actor._animator.has_model(): return
		var attachment := actor._animator.bone_node("mixamorig_RightHand")
		if attachment == null: return
		_skeleton = attachment.get_parent() as Skeleton3D
		_hand = _skeleton.find_bone("mixamorig_RightHand")
		var rest := _skeleton.get_bone_global_rest(_hand)
		var middle := _skeleton.get_bone_global_rest(_skeleton.find_bone("mixamorig_RightHandMiddle1")).origin
		var index := _skeleton.get_bone_global_rest(_skeleton.find_bone("mixamorig_RightHandIndex1")).origin
		var pinky := _skeleton.get_bone_global_rest(_skeleton.find_bone("mixamorig_RightHandPinky1")).origin
		var forward := (middle - rest.origin).normalized()
		var across := index - pinky
		across = (across - forward * across.dot(forward)).normalized()
		_local_frame = rest.basis.orthonormalized().inverse() * Basis(across, forward, across.cross(forward))
		_palm_length = (_skeleton.global_basis * (middle - rest.origin)).length()
		model = (load("res://scenes/items/quest_phone.tscn") as PackedScene).instantiate() as QuestPhoneModel
		actor.add_child(model)
	model.visible = true
	if is_instance_valid(actor._weapon_model): actor._weapon_model.visible = false
	var hand := _skeleton.global_transform * _skeleton.get_bone_global_pose(_hand)
	var contact := hand.basis.orthonormalized() * _local_frame
	var grip: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/phone_grip.json")) as Dictionary if not model.has_meta("world_grip") else model.get_meta("world_grip")
	model.set_meta("world_grip", grip)
	var grip_basis := Basis.from_euler(WeaponGrips.vector(grip.right.rotation_degrees) * PI / 180.0)
	var basis := contact * grip_basis.inverse()
	model.global_transform = Transform3D(basis, hand.origin + contact * Vector3(0, _palm_length, 0) - basis * WeaponGrips.vector(grip.right.position))
