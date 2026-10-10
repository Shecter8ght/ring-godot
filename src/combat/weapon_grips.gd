class_name WeaponGrips
extends RefCounted
## Точки хвата живут на оружии и наследуют масштаб/крен вместе с обвесами.

static var _profiles: Dictionary = {}
static var _contacts: Dictionary = {}


## Оружие с личным хватом сохраняет контакт правой кисти в общем сокете Persona.
static func socket_offset(model: String, weapon: Dictionary) -> Vector3:
	if not weapon.has("hand_grips"):
		return Vector3.ZERO
	if _profiles.is_empty():
		_profiles = JSON.parse_string(FileAccess.get_file_as_string("res://data/weapon_grips.json")) as Dictionary
	var base: Dictionary = (_profiles.get(model, {}) as Dictionary).get("right", {}) as Dictionary
	var custom: Dictionary = (weapon.hand_grips as Dictionary).get("right", {}) as Dictionary
	if not base.has("pos") or not custom.has("pos"):
		return Vector3.ZERO
	return (vector(base.pos) - vector(custom.pos)) * float(weapon.get("scale", 1.0))


static func fit(root: Node3D, model: String, weapon: Dictionary, mods: Dictionary) -> void:
	if _profiles.is_empty():
		_profiles = JSON.parse_string(FileAccess.get_file_as_string("res://data/weapon_grips.json")) as Dictionary
	if _contacts.is_empty() and FileAccess.file_exists("res://data/hand_contacts.json"):
		_contacts = JSON.parse_string(FileAccess.get_file_as_string("res://data/hand_contacts.json")) as Dictionary
	var profile: Dictionary = (weapon.get("hand_grips", _profiles.get(model, {})) as Dictionary).duplicate(true)
	if profile.is_empty():
		return
	# под цевьём может стоять несколько устройств: ладонь — на рукоятке, если она есть
	var under_key: String = _under_key(mods)
	var attachment: Dictionary = WeaponDb.attachment(WeaponDb.mod_id(mods.get(under_key, {})))
	var grip: String = String(attachment.get("look", ""))
	var contact_attachment: String = WeaponDb.mod_id(mods.get(under_key, {}))
	var under_pos: Vector3 = Vector3.ZERO
	var under_socket: Dictionary = WeaponMods.socket(model, "underbarrel")
	if not under_socket.is_empty():
		under_pos = under_socket.pos
		if under_key != "":
			under_pos.z = WeaponBuild.placed_z(model, mods, under_key)
	if grip == "grip_offset":
		# у рукоятки под 45° своей позы контакта нет — пальцы как на вертикальной
		contact_attachment = "grip_vertical_01"
	elif not attachment.is_empty() and not grip in ["grip_vertical", "grip_angled"]:
		contact_attachment = "tac_flashlight_01"
	if model == "pistol":
		contact_attachment = ""
	var contact_key: String = "%s_%.3f_%s" % [model, float(weapon.get("scale", 1.0)), contact_attachment]
	if _profiles.has(grip):
		if not under_socket.is_empty():
			profile.left = (_profiles[grip] as Dictionary).duplicate(true)
			profile.left["scale"] = float(attachment.get("scale", 1.0))
			profile.left["offset"] = under_pos
			if contact_attachment == "grip_compact_01":
				# Короткую рукоятку держим выше: указательный опирается у цевья.
				profile.left.pos[1] = -0.030
	elif not attachment.is_empty() and profile.has("underbarrel_clearance"):
		if not under_socket.is_empty():
			# Фонарь и сошки занимают низ цевья: ладонь переносится за их крепление.
			profile.left.pos[2] = minf(float(profile.left.pos[2]), under_pos.z - float(profile.underbarrel_clearance))
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
		if data.has("thumb_directions"):
			marker.set_meta("thumb_directions", data.thumb_directions)
		var asset_marker: Node3D = root.find_child("GripR" if side == "right" else "GripL", true, false) as Node3D
		if asset_marker:
			# Empty задаёт контакт ладони; размер кисти и сгиб пальцев остаются из профиля.
			marker.transform = WeaponRig._relative_transform(asset_marker, root)
		elif _contacts.has(contact_key) and not weapon.has("hand_grips"):
			marker.set_meta("contact_pose", _contacts[contact_key]["Right" if side == "right" else "Left"])
		root.add_child(marker)


static func vector(value: Array) -> Vector3:
	return Vector3(float(value[0]), float(value[1]), float(value[2]))


## Устройство под цевьём, на котором лежит ладонь: рукоятка, иначе самое заднее ("" — пусто).
static func _under_key(mods: Dictionary) -> String:
	var best: String = ""
	for k: Variant in mods:
		var key: String = String(k)
		if WeaponBuild.depth(key) != 0 or WeaponBuild.base_of(key) != "underbarrel":
			continue
		if String(WeaponDb.attachment(WeaponDb.mod_id(mods[k])).get("look", "")).begins_with("grip_"):
			return key
		if best == "" or key < best:
			best = key
	return best
