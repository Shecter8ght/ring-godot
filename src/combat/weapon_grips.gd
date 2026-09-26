class_name WeaponGrips
extends RefCounted
## Точки хвата живут на оружии и наследуют масштаб/крен вместе с обвесами.

static var _profiles: Dictionary = {}
static var _contacts: Dictionary = {}


static func fit(root: Node3D, model: String, weapon: Dictionary, mods: Dictionary) -> void:
	if _profiles.is_empty():
		_profiles = JSON.parse_string(FileAccess.get_file_as_string("res://data/weapon_grips.json")) as Dictionary
	if _contacts.is_empty() and FileAccess.file_exists("res://data/hand_contacts.json"):
		_contacts = JSON.parse_string(FileAccess.get_file_as_string("res://data/hand_contacts.json")) as Dictionary
	var profile: Dictionary = (weapon.get("hand_grips", _profiles.get(model, {})) as Dictionary).duplicate(true)
	if profile.is_empty():
		return
	var attachment: Dictionary = WeaponDb.attachment(WeaponDb.mod_id(mods.get("underbarrel", {})))
	var grip: String = String(attachment.get("look", ""))
	var contact_attachment: String = WeaponDb.mod_id(mods.get("underbarrel", {}))
	if not attachment.is_empty() and not grip in ["grip_vertical", "grip_angled"]:
		contact_attachment = "tac_flashlight_01"
	if model == "pistol":
		contact_attachment = ""
	var contact_key: String = "%s_%.3f_%s" % [model, float(weapon.get("scale", 1.0)), contact_attachment]
	if _profiles.has(grip):
		var mount: Dictionary = WeaponMods.socket(model, "underbarrel")
		if not mount.is_empty():
			profile.left = (_profiles[grip] as Dictionary).duplicate(true)
			profile.left["scale"] = float(attachment.get("scale", 1.0))
			profile.left["offset"] = mount.pos
			if contact_attachment == "grip_compact_01":
				# Короткую рукоятку держим выше: указательный опирается у цевья.
				profile.left.pos[1] = -0.030
	elif not attachment.is_empty() and profile.has("underbarrel_clearance"):
		var mount: Dictionary = WeaponMods.socket(model, "underbarrel")
		if not mount.is_empty():
			# Фонарь и сошки занимают низ цевья: ладонь переносится за их крепление.
			profile.left.pos[2] = minf(float(profile.left.pos[2]), (mount.pos as Vector3).z - float(profile.underbarrel_clearance))
	for side: String in ["right", "left"]:
		if not profile.has(side):
			continue
		var data: Dictionary = profile[side]
		var forward: Vector3 = vector(data.fingers).normalized()
		var across: Vector3 = vector(data.thumb)
		across = (across - forward * across.dot(forward)).normalized()
		var marker: Marker3D = Marker3D.new()
		marker.name = "RightGrip" if side == "right" else "LeftGrip"
		var basis: Basis = Basis(across, forward, across.cross(forward))
		# Контакт масштабируется с геометрией, расстояние от него до запястья — с кистью.
		var palm_offset: Vector3 = Vector3(0.0, 0.085, 0.01 if side == "right" else -0.01)
		var contact: Vector3 = (vector(data.pos) + basis * palm_offset) * float(data.get("scale", 1.0))
		marker.transform = Transform3D(basis, contact + (data.get("offset", Vector3.ZERO) as Vector3))
		marker.set_meta("palm_offset", palm_offset)
		marker.set_meta("curl", data.get("curl", [55, 75, 45]))
		if _contacts.has(contact_key) and not weapon.has("hand_grips"):
			marker.set_meta("contact_pose", _contacts[contact_key]["Right" if side == "right" else "Left"])
		root.add_child(marker)


static func vector(value: Array) -> Vector3:
	return Vector3(float(value[0]), float(value[1]), float(value[2]))
