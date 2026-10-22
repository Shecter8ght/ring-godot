class_name Metka4Model
extends RefCounted
## Принятая игровая сетка: два отдельных крепления и 24 кости провода.
## Поза провода рассчитывается при сборке; вместе с оружием комплект движется одним узлом.

const ID := "tac_laser_01"
const DIR := "res://assets/models/attachments/metka4/"
static var _materials: Dictionary = {}
static var _manifest: Dictionary = {}


static func standalone() -> Node3D:
	var scene: PackedScene = load(DIR + "metka4.glb") as PackedScene
	if scene == null:
		return Node3D.new()
	var root: Node3D = scene.instantiate() as Node3D
	root.name = "METKA4"
	if _manifest.is_empty():
		_manifest = JSON.parse_string(FileAccess.get_file_as_string(DIR + "manifest.json")) as Dictionary
	for raw: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mesh: MeshInstance3D = raw as MeshInstance3D
		var name: String = String(mesh.name)
		var atlas: String = "details"
		if name == "Main_Body":
			atlas = "main"
		elif name == "Remote_Body" or name == "Cable":
			atlas = "remote"
		if name in ["Main_Lenses", "Main_Window"]:
			var optical: Array = (_manifest.get("optical_materials", {}) as Dictionary).get(name, [])
			for surface: int in range(mesh.mesh.get_surface_count()):
				if surface < optical.size():
					mesh.set_surface_override_material(surface, _optical(name + str(surface), optical[surface]))
		else:
			mesh.material_override = _atlas(atlas)
	return root


static func _atlas(atlas: String) -> StandardMaterial3D:
	if _materials.has(atlas):
		return _materials[atlas]
	var mat: StandardMaterial3D = StandardMaterial3D.new()
	mat.resource_name = "METKA4_" + atlas
	var stem: String = DIR + "metka4_" + atlas
	mat.albedo_texture = load(stem + "_base_color.png") as Texture2D
	mat.metallic_texture = load(stem + "_metallic.png") as Texture2D
	mat.metallic_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	mat.metallic = 1.0
	mat.roughness_texture = load(stem + "_roughness.png") as Texture2D
	mat.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	mat.roughness = 1.0
	mat.normal_enabled = true
	mat.normal_texture = load(stem + "_normal.png") as Texture2D
	mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	_materials[atlas] = mat
	return mat


static func _optical(key: String, data: Dictionary) -> StandardMaterial3D:
	if _materials.has(key):
		return _materials[key]
	var mat: StandardMaterial3D = StandardMaterial3D.new()
	mat.resource_name = String(data.get("name", key))
	var c: Array = data.get("color", [0.01, 0.02, 0.03, 1.0])
	mat.albedo_color = Color(float(c[0]), float(c[1]), float(c[2]), float(c[3])).linear_to_srgb()
	mat.roughness = float(data.get("roughness", 0.12))
	mat.metallic = float(data.get("metallic", 0.0))
	if float(data.get("transmission", 0.0)) > 0.1:
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		mat.albedo_color.a = 0.18
	_materials[key] = mat
	return mat


static func fit(root: Node3D, model: String, mods: Dictionary, weapon_id: String = "") -> void:
	var used: bool = false
	for rec: Variant in mods.values():
		if WeaponDb.mod_id(rec) == ID:
			used = true
			break
	if not used:
		return
	var wid: String = weapon_id
	# Старые прямые вызовы fit без id (инструменты/предпросмотр) сохраняют прежнюю подпись.
	if wid == "":
		for id: Variant in WeaponDb.ids("weapons"):
			if WeaponBuild.model_of(String(id)) == model:
				wid = String(id)
				break
	var resolved: Dictionary = AttachmentRemote.resolve(wid, mods)
	if String(resolved.why) != "":
		return
	for key: String in WeaponBuild.sorted_keys(resolved.mods):
		var rec: Dictionary = resolved.mods[key] if resolved.mods[key] is Dictionary else {}
		if WeaponDb.mod_id(rec) != ID:
			continue
		var parent: Node3D = root.find_child("Attachment_" + WeaponBuild.node_name(key), true, false) as Node3D
		if parent == null:
			continue
		var kit: Node3D = standalone()
		parent.add_child(kit)
		var mf: Transform3D = AttachmentRemote.main_frame(model, resolved.mods, key)
		var rf: Transform3D = AttachmentRemote.remote_frame(model, rec)
		(kit.find_child("Main_Mount", true, false) as Node3D).transform = mf
		(kit.find_child("Remote_Mount", true, false) as Node3D).transform = rf
		var points: PackedVector3Array = AttachmentRemote.cable_points(mf, rf, AttachmentRemote.foreend_center(model), AttachmentRemote.foreend_radii(model))
		_skin_cable(kit, points)
		if not kit.is_node_ready():
			kit.ready.connect(_skin_cable.bind(kit, points), CONNECT_ONE_SHOT)
		kit.set_meta("remote", rec.remote)
		var emitter: Node3D = kit.find_child("Laser_Emitter", true, false) as Node3D
		var beam: LaserSight = LaserSight.new()
		beam.name = "LaserBeam_" + WeaponBuild.node_name(key)
		beam.set_meta("mount", key)
		beam.set_color(Color(0.12, 1.0, 0.18))
		beam.visible = false
		emitter.add_child(beam)
		parent.set_meta("asset_loaded", true)


static func _to_root(node: Node3D, root: Node3D) -> Transform3D:
	var tf: Transform3D = node.transform
	var p: Node = node.get_parent()
	while p != root and p is Node3D:
		tf = (p as Node3D).transform * tf
		p = p.get_parent()
	return tf


static func _sample(points: PackedVector3Array, distance: float) -> Vector3:
	for i: int in range(1, points.size()):
		var length: float = points[i - 1].distance_to(points[i])
		if distance <= length:
			return points[i - 1].lerp(points[i], distance / maxf(length, 0.000001))
		distance -= length
	return points[points.size() - 1]


static func _skin_cable(kit: Node3D, points: PackedVector3Array) -> void:
	var skeleton: Skeleton3D = kit.find_child("Skeleton3D", true, false) as Skeleton3D
	if skeleton == null or points.size() < 2:
		return
	var to_bones: Transform3D = _to_root(skeleton, kit).affine_inverse()
	var length: float = AttachmentRemote.route_length(points)
	var n: int = skeleton.get_bone_count()
	for i: int in range(n):
		var start: Vector3 = to_bones * _sample(points, length * float(i) / n)
		var end: Vector3 = to_bones * _sample(points, length * float(i + 1) / n)
		var y: Vector3 = (end - start).normalized()
		var reference: Vector3 = Vector3.FORWARD if absf(y.dot(Vector3.FORWARD)) < 0.9 else Vector3.RIGHT
		var x: Vector3 = y.cross(reference).normalized()
		var z: Vector3 = x.cross(y).normalized()
		var basis: Basis = Basis(x, y, z)
		# Длина кости — расстояние между соседними rest origins; последний сегмент равен среднему.
		var rest_length: float = AttachmentRemote.LENGTH / n
		if i + 1 < n:
			rest_length = skeleton.get_bone_global_rest(i).origin.distance_to(skeleton.get_bone_global_rest(i + 1).origin)
		# Масштаб последнего сегмента закрывает конец точно. Масштаб родителей создавал
		# сдвиг и срез при разложении локальной позы в цепи с поворотами.
		if i == n - 1:
			basis.y *= start.distance_to(end) / maxf(rest_length, 0.000001)
		skeleton.set_bone_global_pose(i, Transform3D(basis, start))
	# Граница исходной позы не покрывает все стороны цевья: задаём границу новой трассы.
	var cable: MeshInstance3D = kit.find_child("Cable", true, false) as MeshInstance3D
	var bounds: AABB = AABB(points[0], Vector3.ZERO)
	for p: Vector3 in points:
		bounds = bounds.expand(p)
	cable.custom_aabb = _to_root(cable, kit).affine_inverse() * bounds.grow(0.004)
	kit.set_meta("cable_length_m", length)
