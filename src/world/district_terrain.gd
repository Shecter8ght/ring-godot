@tool
class_name DistrictTerrain
extends Node3D
## Рельеф района из готовой карты высот (её считает tools/build_zone01.py): насыпь, овраг, холм,
## выемки и площадки. Меш — плитками (отсекаются по видимости), коллизия — HeightMapShape3D
## на каждую плитку. Поверхность — шейдер district_terrain: маска (грязь/камень/щебень/листва)
## поверх осеннего газона, камень сам выходит на крутых склонах.

@export_file("*.json") var data_path: String = "res://data/sectors/zone01_mall.json":
	set(value):
		data_path = value
		_queue_build()
## Шаг сетки видимого меша, м (коллизия всегда по шагу карты высот).
@export var render_step: int = 2:
	set(value):
		render_step = clampi(value, 1, 8)
		_queue_build()
@export var tile_size: int = 64:
	set(value):
		tile_size = clampi(value, 16, 256)
		_queue_build()
## Локальные выемки под настоящими подвалами: position.y — дно, X/Z — границы.
## Исходная карта высот сохраняется; у видимой земли и физики одна исправленная сетка.
@export var excavations: Array[AABB] = []:
	set(value):
		excavations = value
		_queue_build()

const SHADER: Shader = preload("res://src/world/district_terrain.gdshader")

var _heights: PackedFloat32Array = PackedFloat32Array()
var _cols: int = 0
var _rows: int = 0
var _origin: Vector2 = Vector2.ZERO
var _step: float = 1.0
var _pending: bool = false


func _ready() -> void:
	add_to_group("district_terrain")
	_build()
	if not Engine.is_editor_hint():
		add_to_group("nav_source")


func _queue_build() -> void:
	if not is_inside_tree() or _pending:
		return
	_pending = true
	_build.call_deferred()


## Высота земли в мировой точке (билинейно по карте); вне карты — край карты.
func height_at(x: float, z: float) -> float:
	if _heights.is_empty():
		return 0.0
	var fx: float = clampf((x - _origin.x) / _step, 0.0, float(_cols - 1) - 0.001)
	var fz: float = clampf((z - _origin.y) / _step, 0.0, float(_rows - 1) - 0.001)
	var ix: int = int(fx)
	var iz: int = int(fz)
	var tx: float = fx - float(ix)
	var tz: float = fz - float(iz)
	var a: float = _heights[iz * _cols + ix]
	var b: float = _heights[iz * _cols + ix + 1]
	var c: float = _heights[(iz + 1) * _cols + ix]
	var d: float = _heights[(iz + 1) * _cols + ix + 1]
	return lerpf(lerpf(a, b, tx), lerpf(c, d, tx), tz)


func _cell(ix: int, iz: int) -> float:
	return _heights[clampi(iz, 0, _rows - 1) * _cols + clampi(ix, 0, _cols - 1)]


func _load() -> Dictionary:
	var definition: Dictionary = SectorBuilder.load_def(data_path)
	var terrain: Dictionary = definition.get("terrain", {})
	if terrain.is_empty():
		return {}
	var origin: Array = terrain.get("origin", [0, 0])
	var grid: Array = terrain.get("grid", [0, 0])
	_origin = Vector2(float(origin[0]), float(origin[1]))
	_cols = int(grid[0])
	_rows = int(grid[1])
	_step = float(terrain.get("step", 1.0))
	var bytes: PackedByteArray = FileAccess.get_file_as_bytes(String(terrain.get("heights", "")))
	_heights = bytes.to_float32_array()
	if _heights.size() != _cols * _rows:
		push_error("DistrictTerrain: карта высот %s не совпадает с сеткой %dx%d" % [terrain.get("heights", ""), _cols, _rows])
		_heights = PackedFloat32Array()
		return {}
	for excavation: AABB in excavations:
		var first_x: int = maxi(0, int(ceil((excavation.position.x - _origin.x) / _step)))
		var last_x: int = mini(_cols - 1, int(floor((excavation.end.x - _origin.x) / _step)))
		var first_z: int = maxi(0, int(ceil((excavation.position.z - _origin.y) / _step)))
		var last_z: int = mini(_rows - 1, int(floor((excavation.end.z - _origin.y) / _step)))
		for iz in range(first_z, last_z + 1):
			for ix in range(first_x, last_x + 1):
				_heights[iz * _cols + ix] = minf(_heights[iz * _cols + ix], excavation.position.y)
	return terrain


func _build() -> void:
	_pending = false
	var old: Node = get_node_or_null("_Generated")
	if old:
		old.free()
	var terrain: Dictionary = _load()
	if terrain.is_empty():
		return
	var root := Node3D.new()
	root.name = "_Generated"
	add_child(root)
	var material := ShaderMaterial.new()
	material.shader = SHADER
	for key: String in ["albedo_array", "normal_array", "arm_array", "splat", "noise"]:
		var path: String = String((terrain.get("textures", {}) as Dictionary).get(key, ""))
		if ResourceLoader.exists(path):
			material.set_shader_parameter(key, load(path))
	material.set_shader_parameter("splat_origin", _origin)
	material.set_shader_parameter("splat_size", Vector2(float(_cols - 1), float(_rows - 1)) * _step)
	var tiles: Array = terrain.get("layer_tiles", [3.0, 3.0, 2.5, 3.0, 4.0, 2.0])
	material.set_shader_parameter("layer_tile", PackedFloat32Array(tiles))
	var cells: int = int(round(float(tile_size) / _step))
	var tz: int = 0
	while tz < _rows - 1:
		var tx: int = 0
		while tx < _cols - 1:
			_tile(root, material, tx, tz, mini(cells, _cols - 1 - tx), mini(cells, _rows - 1 - tz))
			tx += cells
		tz += cells


func _tile(root: Node3D, material: ShaderMaterial, x0: int, z0: int, w: int, d: int) -> void:
	var step: int = mini(render_step, maxi(1, mini(w, d)))
	var nx: int = int(ceil(float(w) / float(step)))
	var nz: int = int(ceil(float(d) / float(step)))
	var verts := PackedVector3Array()
	var normals := PackedVector3Array()
	var uvs := PackedVector2Array()
	var tangents := PackedFloat32Array()
	var base := Vector3(_origin.x + float(x0) * _step, 0.0, _origin.y + float(z0) * _step)
	for j in range(nz + 1):
		var iz: int = mini(z0 + j * step, z0 + d)
		for i in range(nx + 1):
			var ix: int = mini(x0 + i * step, x0 + w)
			var p := Vector3(_origin.x + float(ix) * _step, _cell(ix, iz), _origin.y + float(iz) * _step)
			verts.append(p - base)
			# нормаль по соседям карты (не по крупной сетке меша) — свет и уклон точнее
			var n := Vector3(_cell(ix - 1, iz) - _cell(ix + 1, iz), 2.0 * _step, _cell(ix, iz - 1) - _cell(ix, iz + 1)).normalized()
			normals.append(n)
			uvs.append(Vector2(p.x, p.z))
			var t := Vector3(1, 0, 0)
			t = (t - n * n.dot(t)).normalized()
			tangents.append_array([t.x, t.y, t.z, 1.0])
	var indices := PackedInt32Array()
	for j in range(nz):
		for i in range(nx):
			var a: int = j * (nx + 1) + i
			var b: int = a + 1
			var c: int = a + nx + 1
			var e: int = c + 1
			indices.append_array([a, b, c, b, e, c])
	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_TANGENT] = tangents
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_INDEX] = indices
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	mesh.surface_set_material(0, material)
	var mi := MeshInstance3D.new()
	mi.name = "Terrain_%d_%d" % [x0, z0]
	mi.mesh = mesh
	mi.position = base
	# рельеф сам себя затеняет на склонах оврага и холма — тени нужны
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	root.add_child(mi)
	# коллизия — по полной карте высот плитки
	var samples := PackedFloat32Array()
	for j in range(d + 1):
		for i in range(w + 1):
			samples.append(_cell(x0 + i, z0 + j))
	var body := StaticBody3D.new()
	body.name = "Ground_%d_%d" % [x0, z0]
	body.position = base + Vector3(float(w) * _step * 0.5, 0.0, float(d) * _step * 0.5)
	body.set_meta("surface", "grass")
	var shape := HeightMapShape3D.new()
	shape.map_width = w + 1
	shape.map_depth = d + 1
	shape.map_data = samples
	var col := CollisionShape3D.new()
	col.shape = shape
	col.scale = Vector3(_step, 1.0, _step)
	body.add_child(col)
	root.add_child(body)
