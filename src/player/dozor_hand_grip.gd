class_name DozorHandGrip
extends RefCounted
## Starter pose only. Original pistol markers are restored on T-off; no source rig is changed.

const PATH := "res://data/dozor_hand_grip.json"
const SAVED := "dozor_saved_grip"
static var _spec: Dictionary = {}


static func spec() -> Dictionary:
	if _spec.is_empty():
		_spec = JSON.parse_string(FileAccess.get_file_as_string(PATH)) as Dictionary
	return _spec


static func tube() -> Transform3D:
	var s: Dictionary = spec()
	return Transform3D(Basis.from_euler(WeaponGrips.vector(s.tube_rotation_deg) * PI / 180.0), WeaponGrips.vector(s.tube_position))


static func apply(weapon: Node3D, enabled: bool, id: String) -> Node3D:
	if not is_instance_valid(weapon):
		return null
	var marker: Node3D = weapon.find_child("LeftGrip", true, false) as Node3D
	if marker == null:
		return null
	var keys: Dictionary = weapon.get_meta("hand_grip_keys", {})
	if not enabled:
		if marker.has_meta(SAVED):
			var saved: Dictionary = marker.get_meta(SAVED)
			marker.transform = saved.transform
			for field: String in ["curl", "thumb_directions", "contact_pose"]:
				if saved.has(field): marker.set_meta(field, saved[field])
				elif marker.has_meta(field): marker.remove_meta(field)
			keys.Left = saved.key
			weapon.set_meta("hand_grip_keys", keys)
			marker.remove_meta(SAVED)
		return null
	if not marker.has_meta(SAVED):
		var saved: Dictionary = {"transform": marker.transform, "key": String(keys.get("Left", id))}
		for field: String in ["curl", "thumb_directions", "contact_pose"]:
			if marker.has_meta(field): saved[field] = marker.get_meta(field)
		marker.set_meta(SAVED, saved)
	var s: Dictionary = spec()
	var forward: Vector3 = WeaponGrips.vector(s.fingers).normalized()
	var across: Vector3 = WeaponGrips.vector(s.thumb).normalized()
	marker.transform = tube() * Transform3D(Basis(across, forward, across.cross(forward)), WeaponGrips.vector(s.palm_position))
	marker.set_meta("curl", s.curl)
	marker.set_meta("thumb_directions", s.thumb_directions)
	if marker.has_meta("contact_pose"): marker.remove_meta("contact_pose")
	keys.Left = String(HandGripProfiles.keys(id, {}, true).Left)
	weapon.set_meta("hand_grip_keys", keys)
	var holder: Node3D = weapon.get_node_or_null("DozorHandHolder") as Node3D
	if holder == null:
		holder = Node3D.new()
		holder.name = "DozorHandHolder"
		holder.set_meta("dozor_starter", true)
		weapon.add_child(holder)
	holder.transform = tube()
	return holder


## Apply the same wrist translation/rotation as the hand editor, around the unscaled wrist.
static func follow_edits(weapon: Node3D, arms: FirstPersonArms, holder: Node3D) -> void:
	if not is_instance_valid(holder): return
	var marker: Node3D = arms._grips.get("Left") as Node3D
	if marker == null or not marker.has_meta(SAVED): return
	var profiles: Dictionary = arms.grip_profiles if arms.grip_preview else HandGripProfiles.active()
	var key: String = String((weapon.get_meta("hand_grip_keys", {}) as Dictionary).get("Left", ""))
	var value: Dictionary = HandGripProfiles.values(profiles, key, "Left")
	var contact: Transform3D = WeaponModels.between(weapon, marker)
	var offset: Vector3 = WeaponGrips.vector(arms._palm_offsets.Left)
	var wrist: Vector3 = contact.origin - contact.basis * offset
	var rotation: Basis = Basis.from_euler((value.rotation as Vector3) * PI / 180.0)
	var base: Transform3D = tube()
	holder.transform = Transform3D(rotation * base.basis, wrist + rotation * (base.origin - wrist) + (value.position as Vector3))
