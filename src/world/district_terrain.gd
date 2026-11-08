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
## Маска грязи / камня / щебня / листвы (как у шейдера) — из чего земля в точке, читается по первому
## попаданию или шагу.
var _splat_path: String = ""
var _splat: Image
var _material: ShaderMaterial
## «Трава издали» от DistrictGrass (имена параметров шейдера → значения): переживает пересборку рельефа.
var _far_grass: Dictionary = {}
## Высоты из файла до выемок (excavations): кисть земли правит обе сетки, сохраняется эта — выемки не впекаются.
var _source_heights: PackedFloat32Array = PackedFloat32Array()
var _heights_file: String = ""
var _mask_texture: ImageTexture


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


## «Трава издали» (Balance.GRASS.far_look): DistrictGrass передаёт карту густоты травы и отрезок, где травинки
## уходят в землю, — дальше газон рельефа в траве берёт их вид. Ключи — имена параметров шейдера.
func set_far_grass(params: Dictionary) -> void:
	_far_grass = params
	_apply_far_grass()


func _apply_far_grass() -> void:
	if _material == null:
		return
	for key: String in _far_grass:
		_material.set_shader_parameter(key, _far_grass[key])


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


## Из чего земля в точке (Surfaces — попадания и шаги): канал маски сильнее mask_min — грязь (R),
## камень (G) или щебень (B) — «gravel», листва (A) — «dirt»; иначе газон; крутой склон — камень.
func surface_at(pos: Vector3, normal: Vector3) -> String:
	var cfg: Dictionary = Balance.TERRAIN_SURFACE
	if normal.y < float(cfg.rock_slope):
		return "gravel"
	if _splat == null and _splat_path != "" and ResourceLoader.exists(_splat_path):
		_splat = (load(_splat_path) as Texture2D).get_image()
		if _splat != null and _splat.is_compressed():
			_splat.decompress()
	if _splat == null or _cols < 2 or _rows < 2:
		return "grass"
	var span: Vector2 = Vector2(float(_cols - 1), float(_rows - 1)) * _step
	var uv: Vector2 = (Vector2(pos.x, pos.z) - _origin) / span
	var px: int = clampi(int(uv.x * _splat.get_width()), 0, _splat.get_width() - 1)
	var py: int = clampi(int(uv.y * _splat.get_height()), 0, _splat.get_height() - 1)
	var m: Color = _splat.get_pixel(px, py)
	var best: float = maxf(maxf(m.r, m.g), maxf(m.b, m.a))
	if best < float(cfg.mask_min):
		return "grass"
	if best == m.r:
		return "mud"
	if best == m.a:
		return "dirt"
	return "gravel"


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
	_heights_file = String(terrain.get("heights", ""))
	_source_heights = _heights.duplicate()
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
	_splat_path = String((terrain.get("textures", {}) as Dictionary).get("splat", ""))
	_splat = null
	_mask_texture = null
	material.set_shader_parameter("splat_origin", _origin)
	material.set_shader_parameter("splat_size", Vector2(float(_cols - 1), float(_rows - 1)) * _step)
	var tiles: Array = terrain.get("layer_tiles", [3.0, 3.0, 2.5, 3.0, 4.0, 2.0])
	material.set_shader_parameter("layer_tile", PackedFloat32Array(tiles))
	_material = material
	_apply_far_grass()
	var cells: int = int(round(float(tile_size) / _step))
	var tz: int = 0
	while tz < _rows - 1:
		var tx: int = 0
		while tx < _cols - 1:
			_tile(root, material, tx, tz, mini(cells, _cols - 1 - tx), mini(cells, _rows - 1 - tz))
			tx += cells
		tz += cells


# ---------------------------------------------------------------- кисть земли в редакторе (addons/ring_level_tools)

func cells() -> Vector2i:
	return Vector2i(_cols, _rows)


func cell_origin() -> Vector2:
	return _origin


func cell_step() -> float:
	return _step


func heights_data() -> PackedFloat32Array:
	return _heights


## Новые высоты от кисти: разница идёт и в исходную сетку (её и сохраняем — выемки остаются отдельно).
func set_heights_data(data: PackedFloat32Array) -> void:
	if data.size() != _heights.size():
		return
	if _source_heights.size() == data.size():
		for i: int in range(data.size()):
			if data[i] != _heights[i]:
				_source_heights[i] += data[i] - _heights[i]
	_heights = data


func heights_for_save() -> PackedFloat32Array:
	return _source_heights if _source_heights.size() == _heights.size() else _heights


func heights_path() -> String:
	return _heights_file


## Грунты кисти: 0 — основа (все маски вниз), дальше — каналы масок по порядку.
func brush_grounds() -> PackedStringArray:
	return PackedStringArray(["Газон", "Грязь", "Камень", "Щебень", "Листва"])


## Маски грунта для правки (живые картинки — правка сразу видна и в шагах, и в попаданиях).
func brush_masks() -> Array[Image]:
	if _splat == null and _splat_path != "" and ResourceLoader.exists(_splat_path):
		_splat = (load(_splat_path) as Texture2D).get_image()
	if _splat != null:
		if _splat.is_compressed():
			_splat.decompress()
		# из импортированной текстуры приходит с мипами: правка шла бы только в нулевой уровень, издали — старая маска
		if _splat.has_mipmaps():
			_splat.clear_mipmaps()
		if _splat.get_format() != Image.FORMAT_RGBA8:
			_splat.convert(Image.FORMAT_RGBA8)
	var out: Array[Image] = []
	if _splat != null:
		out.append(_splat)
	return out


func brush_mask_channels() -> PackedInt32Array:
	return PackedInt32Array([4])


func brush_mask_paths() -> PackedStringArray:
	return PackedStringArray([_splat_path])


## Показать правку масок в шейдере (своя текстура вместо импортированной; после сохранения — снова файл).
func brush_push_masks() -> void:
	var masks: Array[Image] = brush_masks()
	if masks.is_empty() or _material == null:
		return
	if _mask_texture == null or Vector2i(_mask_texture.get_size()) != masks[0].get_size():
		_mask_texture = ImageTexture.create_from_image(masks[0])
		_material.set_shader_parameter("splat", _mask_texture)
	else:
		_mask_texture.update(masks[0])


## Пересобрать плитки, которые задевает прямоугольник мира (после правки высот кистью).
func rebuild_area(area: Rect2) -> void:
	var root: Node3D = get_node_or_null("_Generated") as Node3D
	if root == null or _material == null:
		_build()
		return
	var grown: Rect2 = area.grow(2.0 * _step)
	var n: int = int(round(float(tile_size) / _step))
	var tz: int = 0
	while tz < _rows - 1:
		var tx: int = 0
		while tx < _cols - 1:
			var w: int = mini(n, _cols - 1 - tx)
			var d: int = mini(n, _rows - 1 - tz)
			var rect: Rect2 = Rect2(_origin.x + float(tx) * _step, _origin.y + float(tz) * _step, float(w) * _step, float(d) * _step)
			if rect.intersects(grown):
				for name: String in ["Terrain_%d_%d" % [tx, tz], "Ground_%d_%d" % [tx, tz]]:
					var old: Node = root.get_node_or_null(name)
					if old:
						root.remove_child(old)
						old.free()
				_tile(root, _material, tx, tz, w, d)
			tx += n
		tz += n


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
	body.set_meta("surface_map", self)
	var shape := HeightMapShape3D.new()
	shape.map_width = w + 1
	shape.map_depth = d + 1
	shape.map_data = samples
	var col := CollisionShape3D.new()
	col.shape = shape
	col.scale = Vector3(_step, 1.0, _step)
	body.add_child(col)
	root.add_child(body)
