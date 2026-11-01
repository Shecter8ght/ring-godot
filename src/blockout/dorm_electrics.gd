@tool
extends RefCounted
## Электрика общежития в стенде: игровые модели (tools/dorm_modules/electrics_game.py → assets/models/dorm/electrics,
## index electrics.json), расстановка — data/blockouts/dorm_electrics.json (tools/dorm_modules/electrify.py).
## Светильник — один узел со склеенной сеткой на модель и отделку (у модели детали — отдельные узлы glTF); мигающие
## (lights в данных) — модель как есть, трубки светятся (dorm_flicker_light.gd). Настенное и провода — их сотни на
## этаж: склеены по клеткам 10 м в одну сетку с поверхностью на материал, клетка не рисуется дальше far.
## Вариант отделки и закраски — карты textures/<набор>__<код>_* вместо карт материала набора (нормаль — набора).

const PATH: String = "res://data/blockouts/dorm_electrics.json"
const DIR: String = "res://assets/models/dorm/electrics"
const FlickerLight = preload("res://src/blockout/dorm_flicker_light.gd")
const CELL: float = 10.0

var _index: Dictionary = {}
var _scenes: Dictionary = {}
## Материалы на набор, вариант и поверхность; склеенные светильники — на модель и отделку.
var _mats: Dictionary = {}
var _fixtures: Dictionary = {}
var _mirrored: Dictionary = {}
static var _data: Dictionary = {}
static var _data_time: int = -1


static func available() -> bool:
	return ResourceLoader.exists(DIR + "/el_box.gltf") and FileAccess.file_exists(PATH)


## Расстановка читается один раз на все узлы этажей (перечитывается, если файл сменился).
static func data() -> Dictionary:
	var time: int = FileAccess.get_modified_time(PATH)
	if time != _data_time:
		_data = _read(PATH)
		_data_time = time
	return _data


func build(parent: Node3D, section_id: String, data: Dictionary) -> void:
	if _index.is_empty():
		_index = _read(DIR + "/electrics.json")
	var flicker: Dictionary = {}
	for light: Dictionary in data.get("lights", []):
		if String(light.section) == section_id:
			flicker[String(light.fixture)] = light
	var cells: Dictionary = {}
	var root: Node3D = Node3D.new()
	root.name = "Электрика"
	parent.add_child(root)
	for item: Dictionary in data.get("items", []):
		if String(item.section) != section_id:
			continue
		var model: String = String(item.model)
		var info: Dictionary = _index.get(model, {})
		if info.is_empty():
			continue
		var b: Array = item.basis
		var xf: Transform3D = Transform3D(Basis(Vector3(b[0], b[1], b[2]), Vector3(b[3], b[4], b[5]), Vector3(b[6], b[7], b[8])),
			_vec(item.origin))
		var variant: Dictionary = item.get("variant", {})
		if String(info.kind) == "ceiling":
			if flicker.has(String(item.id)):
				root.add_child(_flicker_fixture(item, xf, variant, flicker[String(item.id)]))
			else:
				root.add_child(_fixture(item, xf, variant))
			continue
		var key: Vector3i = Vector3i(floori(xf.origin.x / CELL), floori(xf.origin.y / CELL), floori(xf.origin.z / CELL))
		if not cells.has(key):
			cells[key] = {"far": float(item.get("far", 20.0)), "surfaces": {}}
		var cell: Dictionary = cells[key]
		cell.far = maxf(float(cell.far), float(item.get("far", 20.0)))
		var center: Vector3 = (Vector3(key) + Vector3(0.5, 0.5, 0.5)) * CELL
		for part: Array in _parts(model, item):
			var mat: Material = _material(part[2] as StandardMaterial3D, variant)
			var mat_key: String = str(mat.get_instance_id())
			if not cell.surfaces.has(mat_key):
				var st: SurfaceTool = SurfaceTool.new()
				st.begin(Mesh.PRIMITIVE_TRIANGLES)
				cell.surfaces[mat_key] = [st, mat]
			var tool: SurfaceTool = cell.surfaces[mat_key][0]
			_append(tool, part[0] as Mesh, int(part[1]), Transform3D(Basis.IDENTITY, -center) * xf * (part[3] as Transform3D))
	for key: Vector3i in cells:
		var cell: Dictionary = cells[key]
		var mesh: ArrayMesh = ArrayMesh.new()
		for mat_key: String in cell.surfaces:
			var pair: Array = cell.surfaces[mat_key]
			(pair[0] as SurfaceTool).commit(mesh)
			mesh.surface_set_material(mesh.get_surface_count() - 1, pair[1] as Material)
		var node: MeshInstance3D = MeshInstance3D.new()
		node.name = "Электрика_%d_%d_%d" % [key.x, key.y, key.z]
		node.mesh = mesh
		node.position = (Vector3(key) + Vector3(0.5, 0.5, 0.5)) * CELL
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		node.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
		node.visibility_range_end = float(cell.far) + CELL * 0.7
		node.visibility_range_end_margin = 2.0
		node.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		root.add_child(node)


## Склейка поверхности в клетку. Залом провода в другую сторону поставлен зеркально (electrify.py): у такой копии
## обход треугольников и знак бинормали развёрнуты, иначе лицо смотрело бы внутрь.
func _append(tool: SurfaceTool, mesh: Mesh, surface: int, xf: Transform3D) -> void:
	if xf.basis.determinant() >= 0.0:
		tool.append_from(mesh, surface, xf)
		return
	var key: String = "%d|%d" % [mesh.get_instance_id(), surface]
	if not _mirrored.has(key):
		var arrays: Array = mesh.surface_get_arrays(surface)
		var idx: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
		for i: int in range(0, idx.size(), 3):
			var a: int = idx[i + 1]
			idx[i + 1] = idx[i + 2]
			idx[i + 2] = a
		arrays[Mesh.ARRAY_INDEX] = idx
		if arrays[Mesh.ARRAY_TANGENT] != null:
			var tan: PackedFloat32Array = arrays[Mesh.ARRAY_TANGENT]
			for i: int in range(3, tan.size(), 4):
				tan[i] = -tan[i]
			arrays[Mesh.ARRAY_TANGENT] = tan
		var flipped: ArrayMesh = ArrayMesh.new()
		flipped.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		_mirrored[key] = flipped
	tool.append_from(_mirrored[key] as ArrayMesh, 0, xf)


## Детали модели: [сетка, поверхность, материал, положение в модели]; рычажок и клавиша — в позе «выключено», если так.
func _parts(model: String, item: Dictionary) -> Array:
	var scene: Node3D = _scene(model)
	var out: Array = []
	var mover: Dictionary = (_index[model] as Dictionary).get("mover", {})
	for found: Node in scene.find_children("*", "MeshInstance3D", true, false):
		var mesh_node: MeshInstance3D = found as MeshInstance3D
		var xf: Transform3D = _relative(scene, mesh_node)
		if not mover.is_empty() and mesh_node.name.begins_with(String(mover.node)) and not bool(item.get("switch_on", true)):
			xf = xf * Transform3D(Basis(Vector3.RIGHT, deg_to_rad(-2.0 * float(mover.on_deg))), Vector3.ZERO)
		for s: int in range(mesh_node.mesh.get_surface_count()):
			out.append([mesh_node.mesh, s, mesh_node.mesh.surface_get_material(s), xf])
	return out


## Светильник одним узлом: сетка склеена один раз на модель и отделку, общая у всех таких же.
func _fixture(item: Dictionary, xf: Transform3D, variant: Dictionary) -> MeshInstance3D:
	var model: String = String(item.model)
	var key: String = model + "|" + JSON.stringify(variant)
	if not _fixtures.has(key):
		var groups: Dictionary = {}
		for part: Array in _parts(model, item):
			var mat: Material = _material(part[2] as StandardMaterial3D, variant)
			var mat_key: String = str(mat.get_instance_id())
			if not groups.has(mat_key):
				var st: SurfaceTool = SurfaceTool.new()
				st.begin(Mesh.PRIMITIVE_TRIANGLES)
				groups[mat_key] = [st, mat]
			(groups[mat_key][0] as SurfaceTool).append_from(part[0] as Mesh, int(part[1]), part[3] as Transform3D)
		var mesh: ArrayMesh = ArrayMesh.new()
		for mat_key: String in groups:
			(groups[mat_key][0] as SurfaceTool).commit(mesh)
			mesh.surface_set_material(mesh.get_surface_count() - 1, groups[mat_key][1] as Material)
		_fixtures[key] = mesh
	var node: MeshInstance3D = MeshInstance3D.new()
	node.name = String(item.id)
	node.mesh = _fixtures[key] as ArrayMesh
	node.transform = xf
	node.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
	node.visibility_range_end = float(item.get("far", 40.0))
	node.visibility_range_end_margin = 3.0
	node.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
	node.add_to_group("dorm_electrics")
	return node


## Мигающий: модель как есть (целые трубки — свои узлы), их материал — копия со свечением, свет — под светильником.
func _flicker_fixture(item: Dictionary, xf: Transform3D, variant: Dictionary, light: Dictionary) -> Node3D:
	var node: Node3D = (load(DIR + "/" + String(item.model) + ".gltf") as PackedScene).instantiate() as Node3D
	node.name = String(item.id)
	node.transform = xf
	var glow: Array[StandardMaterial3D] = []
	var tubes: int = 0
	for found: Node in node.find_children("*", "MeshInstance3D", true, false):
		var mesh_node: MeshInstance3D = found as MeshInstance3D
		mesh_node.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
		var tube: bool = mesh_node.name.begins_with("Трубка_люминофор") and not mesh_node.name.contains("обломок")
		if tube:
			tubes += 1
		for s: int in range(mesh_node.mesh.get_surface_count()):
			var mat: StandardMaterial3D = _material(mesh_node.mesh.surface_get_material(s) as StandardMaterial3D, variant)
			if tube:
				mat = mat.duplicate() as StandardMaterial3D
				mat.emission_enabled = true
				mat.emission = FlickerLight.COLOR
				mat.emission_energy_multiplier = FlickerLight.GLOW
				glow.append(mat)
			if mat != mesh_node.mesh.surface_get_material(s):
				mesh_node.set_surface_override_material(s, mat)
	var source: Node3D = FlickerLight.new() as Node3D
	source.name = "Мерцание"
	source.set("seed_value", int(light.get("seed", 1)))
	source.set("tubes", tubes)
	source.set("tube_materials", glow)
	node.add_child(source)
	node.add_to_group("dorm_electrics")
	return node


## Материал поверхности: стекло колбы — прозрачное, молочное (плафон, рассеиватель) — просвечивает; вариант набора —
## свои карты цвета и ORM.
func _material(source: StandardMaterial3D, variant: Dictionary) -> Material:
	if source == null:
		return null
	var name_id: String = source.resource_name
	var set_name: String = name_id.get_slice("_стекло", 0).get_slice("_опал", 0)
	var code: String = String(variant.get(set_name, ""))
	var key: String = name_id + "|" + code
	if _mats.has(key):
		return _mats[key] as Material
	var mat: StandardMaterial3D = source.duplicate() as StandardMaterial3D
	if code != "":
		var base: String = "%s/textures/%s__%s_" % [DIR, set_name, code]
		var color: Texture2D = load(base + "baseColor.webp") as Texture2D
		var orm: Texture2D = load(base + "occlusionRoughnessMetallic.webp") as Texture2D
		if color != null:
			mat.albedo_texture = color
		if orm != null:
			mat.roughness_texture = orm
			mat.metallic_texture = orm
			if mat.ao_enabled:
				mat.ao_texture = orm
	if name_id.ends_with("_стекло"):
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		mat.albedo_color = Color(0.9, 0.92, 0.9, 0.22)
		mat.metallic = 0.0
		mat.roughness = 0.08
	elif name_id.ends_with("_опал"):
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		mat.albedo_color = Color(1.0, 1.0, 1.0, 0.86 if code != "PL-PRZ" else 0.55)
		mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	else:
		mat.transparency = BaseMaterial3D.TRANSPARENCY_DISABLED
	_mats[key] = mat
	return mat


func _scene(model: String) -> Node3D:
	if not _scenes.has(model):
		_scenes[model] = (load(DIR + "/" + model + ".gltf") as PackedScene).instantiate()
	return _scenes[model] as Node3D


func free_scenes() -> void:
	for scene: Node in _scenes.values():
		scene.free()
	_scenes.clear()


static func _relative(root: Node3D, node: Node3D) -> Transform3D:
	var xf: Transform3D = node.transform
	var p: Node = node.get_parent()
	while p != null and p != root:
		xf = (p as Node3D).transform * xf
		p = p.get_parent()
	return xf


static func _vec(values: Array) -> Vector3:
	return Vector3(float(values[0]), float(values[1]), float(values[2]))


static func _read(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed as Dictionary if parsed is Dictionary else {}
