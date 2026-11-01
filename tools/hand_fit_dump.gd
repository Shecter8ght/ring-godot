extends Node
## Геометрия для калибровки хвата: данные меша и скелета, без изменения исходников.

func _vec(v: Vector3) -> Array:
	return [v.x, v.y, v.z]

func _tr(t: Transform3D) -> Array:
	return [_vec(t.basis.x), _vec(t.basis.y), _vec(t.basis.z), _vec(t.origin)]

func _ready() -> void:
	var arms: FirstPersonArms = load("res://scenes/player/first_person_arms.tscn").instantiate() as FirstPersonArms
	add_child(arms)
	var bones: Array = []
	var sk: Skeleton3D = arms.skeleton
	for i: int in range(sk.get_bone_count()):
		bones.append({"name": sk.get_bone_name(i), "parent": sk.get_bone_parent(i), "rest": _tr(sk.get_bone_global_rest(i))})
	var meshes: Array = []
	for node: Node in arms.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = node as MeshInstance3D
		if not mi.name.begins_with("Human") or mi.name.contains("casual"):
			continue
		var binds: Array = []
		for i: int in range(mi.skin.get_bind_count()):
			binds.append({"bone": sk.find_bone(mi.skin.get_bind_name(i)), "pose": _tr(mi.skin.get_bind_pose(i))})
		for surface: int in range(mi.mesh.get_surface_count()):
			var arrays: Array = mi.mesh.surface_get_arrays(surface)
			var points: Array = []
			for v: Vector3 in arrays[Mesh.ARRAY_VERTEX]:
				points.append(_vec(v))
			meshes.append({"points": points, "bones": Array(arrays[Mesh.ARRAY_BONES]), "weights": Array(arrays[Mesh.ARRAY_WEIGHTS]), "binds": binds})
	var cases: Array = []
	var weapons: Dictionary = (JSON.parse_string(FileAccess.get_file_as_string(WeaponDb.WEAPONS_PATH)) as Dictionary).weapons
	var keys: Dictionary = {}
	var ids: Array = ["pistol", "rifle", "shotgun", "bolt"]
	ids.append_array(weapons.keys())
	for id: String in ids:
		for att: String in ["", "grip_vertical_01", "tac_flashlight_01"]:
			var weapon: Dictionary = WeaponDb.weapon(id)
			var model: String = String(weapon.get("model", id))
			if model == "pistol" and att != "":
				continue
			var key: String = "%s_%.3f_%s" % [model, float(weapon.get("scale", 1.0)), att]
			if keys.has(key):
				continue
			keys[key] = true
			var mods: Dictionary = {} if att == "" else {"underbarrel": {"id": att}}
			var gun: Node3D = WeaponModels.build(id, mods)
			add_child(gun)
			arms.bind_weapon(gun)
			for side: String in ["Right", "Left"]:
				var marker: Node3D = gun.find_child(side + "Grip", true, false) as Node3D
				if marker.has_meta("contact_pose"):
					marker.remove_meta("contact_pose")
			arms.update_pose()
			var poses: Array = []
			for i: int in range(sk.get_bone_count()):
				poses.append(_tr(sk.global_transform * sk.get_bone_global_pose(i)))
			var hulls: Array = []
			for node: Node in gun.find_children("*", "MeshInstance3D", true, false):
				var mi: MeshInstance3D = node as MeshInstance3D
				if not mi.visible:
					continue
				var faces: PackedVector3Array = mi.mesh.get_faces()
				var points: Array = []
				for p: Vector3 in faces:
					points.append(_vec(mi.global_transform * p))
				hulls.append(points)
			cases.append({"key": key, "id": id, "attachment": att, "poses": poses, "hulls": hulls})
			gun.free()
	DirAccess.make_dir_recursive_absolute("res://tools/hand_fit")
	FileAccess.open("res://tools/hand_fit/.gdignore", FileAccess.WRITE).close()
	FileAccess.open("res://tools/hand_fit/input.json", FileAccess.WRITE).store_string(JSON.stringify({"bones": bones, "meshes": meshes, "cases": cases}))
	print("HAND FIT DUMP cases=", cases.size(), " meshes=", meshes.size())
	arms.queue_free()
	await get_tree().process_frame
	get_tree().quit()
