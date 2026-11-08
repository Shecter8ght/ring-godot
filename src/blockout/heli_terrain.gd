@tool
extends "res://src/world/district_terrain.gd"
## Рельеф серого стенда «Вертолёт» (tools/heli_study.gd): карта высот, шейдер и текстуры — как у DistrictTerrain,
## но горы видно на 2–3 км, поэтому у каждой плитки три ступени детализации: вблизи — шаг карты, дальше — ×4 и ×16.
## Стыки ступеней закрыты «юбками» — полосой вниз по краю плитки. Подробная ступень и коллизия — только у
## плиток рядом с тем местом, где ходят (detail_rect, collision_rect); маска земли — PNG без импорта. Шейдер свой
## (heli_terrain.gdshader): слои зоны 1, а на крутых склонах камень с трёх сторон — стены ущелья без растянутых полос.

const HELI_SHADER: Shader = preload("res://src/blockout/heli_terrain.gdshader")

## Где кончается подробная ступень и где начинается самая грубая, м (по центру плитки).
@export var lod_ranges: Vector2 = Vector2(360.0, 1150.0)
## Плитка, клеток карты (при шаге 4 м — 128 м).
@export var tile_cells: int = 32
## Прямоугольник мира (x, z, ширина, глубина), где строится подробная ступень.
@export var detail_rect: Rect2 = Rect2()
## Прямоугольник мира, где у плиток есть коллизия.
@export var collision_rect: Rect2 = Rect2()

## Сколько плиток собрано по ступеням (для отчёта стенда).
var built: Dictionary = {"lod0": 0, "lod1": 0, "lod2": 0, "ground": 0}


func _build() -> void:
	_pending = false
	var old: Node = get_node_or_null("_Generated")
	if old:
		old.free()
	var terrain: Dictionary = _load()
	if terrain.is_empty():
		return
	var root: Node3D = Node3D.new()
	root.name = "_Generated"
	add_child(root)
	var material: ShaderMaterial = ShaderMaterial.new()
	material.shader = _surface_shader()
	var textures: Dictionary = terrain.get("textures", {}) as Dictionary
	for key: String in ["albedo_array", "normal_array", "arm_array", "noise"]:
		var path: String = String(textures.get(key, ""))
		if ResourceLoader.exists(path):
			material.set_shader_parameter(key, load(path))
	var splat_file: String = String(terrain.get("splat_file", ""))
	_splat_path = ""
	_splat = null
	if splat_file != "":
		var image: Image = Image.load_from_file(ProjectSettings.globalize_path(splat_file))
		if image:
			_splat = image
			material.set_shader_parameter("splat", ImageTexture.create_from_image(image))
	_extra_textures(material, terrain)
	material.set_shader_parameter("splat_origin", _origin)
	material.set_shader_parameter("splat_size", Vector2(float(_cols - 1), float(_rows - 1)) * _step)
	material.set_shader_parameter("layer_tile", PackedFloat32Array(terrain.get("layer_tiles", [3.0, 3.0, 2.5, 3.0, 4.0, 2.0])))
	_material = material
	_apply_far_grass()
	built = {"lod0": 0, "lod1": 0, "lod2": 0, "ground": 0}
	var tz: int = 0
	while tz < _rows - 1:
		var tx: int = 0
		while tx < _cols - 1:
			_heli_tile(root, material, tx, tz)
			tx += tile_cells
		tz += tile_cells


## Плитка (tx, tz — первая клетка): ступени детализации и коллизия.
func _heli_tile(root: Node3D, material: ShaderMaterial, tx: int, tz: int) -> void:
	var w: int = mini(tile_cells, _cols - 1 - tx)
	var d: int = mini(tile_cells, _rows - 1 - tz)
	var rect: Rect2 = Rect2(_origin.x + float(tx) * _step, _origin.y + float(tz) * _step, float(w) * _step, float(d) * _step)
	var detailed: bool = detail_rect.intersects(rect)
	if detailed:
		_lod_tile(root, material, tx, tz, w, d, 1, 0.0, lod_ranges.x, 6.0, true)
		built.lod0 += 1
	# средняя ступень: от конца подробной (или с нуля, если её у плитки нет) до начала грубой
	_lod_tile(root, material, tx, tz, w, d, 4, lod_ranges.x if detailed else 0.0, lod_ranges.y, 18.0, true)
	built.lod1 += 1
	_lod_tile(root, material, tx, tz, w, d, 16, lod_ranges.y, 0.0, 60.0, false)
	built.lod2 += 1
	if collision_rect.intersects(rect):
		_ground(root, tx, tz, w, d)
		built.ground += 1


## Высоты в клетке карты (кисть земли в редакторе, tools/level_tools): прямой доступ к сетке.
func cells() -> Vector2i:
	return Vector2i(_cols, _rows)


func cell_origin() -> Vector2:
	return _origin


func cell_step() -> float:
	return _step


func heights_data() -> PackedFloat32Array:
	return _heights


func set_heights_data(data: PackedFloat32Array) -> void:
	if data.size() == _heights.size():
		_heights = data


## Пересобрать плитки, которые задевает прямоугольник мира (после правки высот кистью); нормали
## грубых ступеней берут соседей на 16 клеток — запас на столько же.
func rebuild_area(area: Rect2) -> void:
	var root: Node3D = get_node_or_null("_Generated") as Node3D
	if root == null or _material == null:
		_build()
		return
	var grown: Rect2 = area.grow(16.0 * _step)
	var tz: int = 0
	while tz < _rows - 1:
		var tx: int = 0
		while tx < _cols - 1:
			var w: int = mini(tile_cells, _cols - 1 - tx)
			var d: int = mini(tile_cells, _rows - 1 - tz)
			var rect: Rect2 = Rect2(_origin.x + float(tx) * _step, _origin.y + float(tz) * _step, float(w) * _step, float(d) * _step)
			if rect.intersects(grown):
				for n: String in ["Terrain_%d_%d_s1" % [tx, tz], "Terrain_%d_%d_s4" % [tx, tz], "Terrain_%d_%d_s16" % [tx, tz],
						"Ground_%d_%d" % [tx, tz]]:
					var old: Node = root.get_node_or_null(n)
					if old:
						root.remove_child(old)
						old.free()
				_heli_tile(root, _material, tx, tz)
			tx += tile_cells
		tz += tile_cells


## Шейдер поверхности; наследник ставит свой (земля «Санатория» — восемь грунтов 4K).
func _surface_shader() -> Shader:
	return HELI_SHADER


## Добавочные карты наследника (вторая маска, яркость слоёв) — после основной маски.
func _extra_textures(_material: ShaderMaterial, _terrain: Dictionary) -> void:
	pass


func _lod_tile(root: Node3D, material: ShaderMaterial, x0: int, z0: int, w: int, d: int, step: int,
		range_begin: float, range_end: float, skirt: float, shadow: bool) -> void:
	var nx: int = int(ceil(float(w) / float(step)))
	var nz: int = int(ceil(float(d) / float(step)))
	var base: Vector3 = Vector3(_origin.x + float(x0) * _step, 0.0, _origin.y + float(z0) * _step)
	var verts: PackedVector3Array = PackedVector3Array()
	var normals: PackedVector3Array = PackedVector3Array()
	var uvs: PackedVector2Array = PackedVector2Array()
	var tangents: PackedFloat32Array = PackedFloat32Array()
	for j: int in range(nz + 1):
		var iz: int = mini(z0 + j * step, z0 + d)
		for i: int in range(nx + 1):
			var ix: int = mini(x0 + i * step, x0 + w)
			var p: Vector3 = Vector3(_origin.x + float(ix) * _step, _cell(ix, iz), _origin.y + float(iz) * _step)
			verts.append(p - base)
			# нормаль — по соседям с шагом ступени: грубая сетка не освещается мелкими складками, которых у неё нет
			var s: int = step
			var n: Vector3 = Vector3(_cell(ix - s, iz) - _cell(ix + s, iz), 2.0 * _step * float(s), _cell(ix, iz - s) - _cell(ix, iz + s)).normalized()
			normals.append(n)
			uvs.append(Vector2(p.x, p.z))
			var t: Vector3 = (Vector3(1, 0, 0) - n * n.x).normalized()
			tangents.append_array([t.x, t.y, t.z, 1.0])
	var indices: PackedInt32Array = PackedInt32Array()
	for j: int in range(nz):
		for i: int in range(nx):
			var a: int = j * (nx + 1) + i
			var b: int = a + 1
			var c: int = a + nx + 1
			var e: int = c + 1
			indices.append_array([a, b, c, b, e, c])
	# юбка: край плитки опущен вниз — щели между ступенями разной частоты не просвечивают
	var edge: Array[int] = []
	for i: int in range(nx + 1):
		edge.append(i)
	for j: int in range(1, nz + 1):
		edge.append(j * (nx + 1) + nx)
	for i: int in range(nx - 1, -1, -1):
		edge.append(nz * (nx + 1) + i)
	for j: int in range(nz - 1, -1, -1):
		edge.append(j * (nx + 1))
	for k: int in range(edge.size() - 1):
		var top_a: int = edge[k]
		var top_b: int = edge[k + 1]
		var low_a: int = verts.size()
		for top: int in [top_a, top_b]:
			verts.append(verts[top] - Vector3(0.0, skirt, 0.0))
			normals.append(normals[top])
			uvs.append(uvs[top])
			tangents.append_array([tangents[top * 4], tangents[top * 4 + 1], tangents[top * 4 + 2], 1.0])
		var low_b: int = low_a + 1
		# обе стороны: обход края идёт и по часовой, и против — юбка видна снаружи у любой плитки
		indices.append_array([top_a, low_a, top_b, top_b, low_a, low_b, top_a, top_b, low_a, top_b, low_b, low_a])
	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_TANGENT] = tangents
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_INDEX] = indices
	var mesh: ArrayMesh = ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	mesh.surface_set_material(0, material)
	var mi: MeshInstance3D = MeshInstance3D.new()
	mi.name = "Terrain_%d_%d_s%d" % [x0, z0, step]
	mi.mesh = mesh
	mi.position = base
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadow else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.visibility_range_begin = range_begin
	mi.visibility_range_end = range_end
	# запас на переключение (без растворения: прозрачный проход дорог), чтобы плитка не мигала на границе
	mi.visibility_range_begin_margin = 12.0 if range_begin > 0.0 else 0.0
	mi.visibility_range_end_margin = 12.0 if range_end > 0.0 else 0.0
	root.add_child(mi)


func _ground(root: Node3D, x0: int, z0: int, w: int, d: int) -> void:
	var samples: PackedFloat32Array = PackedFloat32Array()
	for j: int in range(d + 1):
		for i: int in range(w + 1):
			samples.append(_cell(x0 + i, z0 + j))
	var base: Vector3 = Vector3(_origin.x + float(x0) * _step, 0.0, _origin.y + float(z0) * _step)
	var body: StaticBody3D = StaticBody3D.new()
	body.name = "Ground_%d_%d" % [x0, z0]
	body.position = base + Vector3(float(w) * _step * 0.5, 0.0, float(d) * _step * 0.5)
	body.set_meta("surface", "grass")
	body.set_meta("surface_map", self)
	var shape: HeightMapShape3D = HeightMapShape3D.new()
	shape.map_width = w + 1
	shape.map_depth = d + 1
	shape.map_data = samples
	var col: CollisionShape3D = CollisionShape3D.new()
	col.shape = shape
	col.scale = Vector3(_step, 1.0, _step)
	body.add_child(col)
	root.add_child(body)
