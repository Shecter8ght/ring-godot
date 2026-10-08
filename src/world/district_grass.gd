@tool
class_name DistrictGrass
extends Node3D
## Сплошной травяной покров вокруг камеры: клетки cell×cell м заполняются пучками (сканы Poly Haven)
## по карте плотности (PNG, 1 пиксель = 1 м, R — трава, G — сорняки) и высоте DistrictTerrain.
## Раскладка в клетке — детерминированная (хэш клетки): у всех игроков одинаковая, данных не хранит.
## Клетки дальше radius освобождаются; за кадр строится не больше build_per_frame клеток.

@export_file("*.png") var density_map: String = ""
@export var origin: Vector2 = Vector2.ZERO
@export var models: PackedStringArray = PackedStringArray()
@export var weed_models: PackedStringArray = PackedStringArray()
@export_dir var materials_dir: String = "res://assets/zone01/materials"
@export var tint: Color = Color(0.8, 0.76, 0.66)
## Пучков на м² при плотности 1.
@export var per_m2: float = 14.0
@export var cell: float = 12.0
@export var radius: float = 32.0
@export var scale_range: Vector2 = Vector2(2.0, 3.2)
@export var build_per_frame: int = 4

var _density: Image
var _terrain: Node
var _meshes: Array[Mesh] = []
var _weeds: Array[Mesh] = []
var _cells: Dictionary = {}


func _ready() -> void:
	if Engine.is_editor_hint():
		return
	if density_map == "" or not ResourceLoader.exists(density_map):
		return
	_density = (load(density_map) as Texture2D).get_image()
	if _density.is_compressed():
		_density.decompress()
	_terrain = get_tree().get_first_node_in_group("district_terrain")
	for path in models:
		var m := _load_mesh(path)
		if m:
			_meshes.append(m)
	for path in weed_models:
		var m := _load_mesh(path)
		if m:
			_weeds.append(m)


func _load_mesh(path: String) -> Mesh:
	if not ResourceLoader.exists(path):
		return null
	var inst: Node = (load(path) as PackedScene).instantiate()
	var found: Array[Node] = inst.find_children("*", "MeshInstance3D", true, false)
	var mesh: Mesh = null
	if not found.is_empty():
		var src_mesh: Mesh = (found[0] as MeshInstance3D).mesh
		var out := ArrayMesh.new()
		for i in range(src_mesh.get_surface_count()):
			# нормали травы — почти вверх: пучок освещён как часть газона, а не чёрные стебли сбоку
			var arrays: Array = src_mesh.surface_get_arrays(i)
			var nrm: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
			for k in range(nrm.size()):
				nrm[k] = (nrm[k] * 0.25 + Vector3.UP).normalized()
			arrays[Mesh.ARRAY_NORMAL] = nrm
			arrays[Mesh.ARRAY_TANGENT] = null
			out.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
			out.surface_set_material(i, src_mesh.surface_get_material(i))
		mesh = out
		for i in range(mesh.get_surface_count()):
			var src := mesh.surface_get_material(i) as BaseMaterial3D
			if src:
				var m := src.duplicate() as BaseMaterial3D
				m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
				m.alpha_scissor_threshold = 0.4
				m.cull_mode = BaseMaterial3D.CULL_DISABLED
				m.vertex_color_use_as_albedo = true
				m.albedo_color = tint
				m.backlight_enabled = true
				m.backlight = Color(0.2, 0.2, 0.1)
				m.roughness = 0.95
				m.normal_enabled = false
				mesh.surface_set_material(i, m)
	inst.free()
	return mesh


func _density_at(x: float, z: float) -> Color:
	var px: int = int(x - origin.x)
	var pz: int = int(z - origin.y)
	if px < 0 or pz < 0 or px >= _density.get_width() or pz >= _density.get_height():
		return Color(0, 0, 0)
	return _density.get_pixel(px, pz)


func _process(_delta: float) -> void:
	if _density == null or _meshes.is_empty():
		return
	var cam := get_viewport().get_camera_3d()
	if cam == null:
		return
	var p := cam.global_position
	var c0 := Vector2i(floori(p.x / cell), floori(p.z / cell))
	var r: int = int(ceil(radius / cell))
	var want: Dictionary = {}
	var todo: Array[Vector2i] = []
	for dz in range(-r, r + 1):
		for dx in range(-r, r + 1):
			var c := c0 + Vector2i(dx, dz)
			var center := Vector2((float(c.x) + 0.5) * cell, (float(c.y) + 0.5) * cell)
			if center.distance_to(Vector2(p.x, p.z)) > radius + cell * 0.71:
				continue
			want[c] = true
			if not _cells.has(c):
				todo.append(c)
	for c: Vector2i in _cells.keys():
		if not want.has(c):
			(_cells[c] as Node).queue_free()
			_cells.erase(c)
	# ближние — первыми
	todo.sort_custom(func(a: Vector2i, b: Vector2i) -> bool: return (a - c0).length_squared() < (b - c0).length_squared())
	for i in range(mini(build_per_frame, todo.size())):
		_cells[todo[i]] = _build_cell(todo[i])


func _build_cell(c: Vector2i) -> Node3D:
	var root := Node3D.new()
	root.name = "Cell_%d_%d" % [c.x, c.y]
	add_child(root)
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(Vector2i(c.x * 73856093, c.y * 19349663))
	var per_mesh: Array = []
	for i in range(_meshes.size() + _weeds.size()):
		per_mesh.append([])
	var n: int = int(cell * cell * per_m2)
	for i in range(n):
		var x: float = (float(c.x) + rng.randf()) * cell
		var z: float = (float(c.y) + rng.randf()) * cell
		var d := _density_at(x, z)
		var roll: float = rng.randf()
		var idx: int = -1
		if roll < d.r:
			idx = rng.randi_range(0, _meshes.size() - 1)
		elif roll < d.r + d.g * 0.15 and not _weeds.is_empty():
			idx = _meshes.size() + rng.randi_range(0, _weeds.size() - 1)
		if idx < 0:
			continue
		var y: float = float(_terrain.call("height_at", x, z)) if _terrain else 0.0
		var s: float = rng.randf_range(scale_range.x, scale_range.y) * (0.75 + 0.35 * d.r)
		var t := Transform3D(Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3(s, s * rng.randf_range(0.85, 1.25), s)), Vector3(x, y - 0.03, z))
		(per_mesh[idx] as Array).append([t, rng.randf()])
	for i in range(per_mesh.size()):
		var list: Array = per_mesh[i]
		if list.is_empty():
			continue
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.mesh = _meshes[i] if i < _meshes.size() else _weeds[i - _meshes.size()]
		mm.instance_count = list.size()
		for k in range(list.size()):
			mm.set_instance_transform(k, list[k][0])
			var v: float = float(list[k][1])
			mm.set_instance_color(k, Color(1, 1, 1).lerp(Color(0.92, 0.8, 0.55), v) * (0.8 + 0.3 * fposmod(v * 7.3, 1.0)))
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(mmi)
	return root
