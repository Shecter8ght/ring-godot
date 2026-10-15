@tool
class_name DistrictGrass
extends Node3D
## Травяной покров вокруг камеры по карте плотности (PNG, 1 пиксель = 1 м, R — трава, G — сорняки)
## и высоте DistrictTerrain. Два яруса:
## — густой нижний (lawn): куртины травинок GrassBlades, своя сетка без прозрачности, ближнее кольцо —
##   полные травинки, дальнее — реже и шире (переход — растворением, GeometryInstance3D.visibility_range),
##   у края травинки уходят в землю;
## — пучки-сканы Poly Haven (высокая сухая трава, сорняки, одуванчики) поверх.
## Оба яруса качаются на ветру и мнутся под ногами и телами (grass_wind.gdshaderinc, GrassTrample).
## Раскладка в клетке — детерминированная (хэш клетки): у всех игроков одинаковая, данных не хранит.
## Клетки дальше радиуса освобождаются; за кадр строится не больше build_per_frame клеток каждого яруса.
## Радиусы и густота — по качеству графики (Balance.GRASS.quality).

const BLADES_SHADER := preload("res://src/world/grass_blades.gdshader")
const SCAN_SHADER := preload("res://src/world/grass_scan.gdshader")

@export_file("*.png") var density_map: String = ""
@export var origin: Vector2 = Vector2.ZERO
@export var models: PackedStringArray = PackedStringArray()
@export var weed_models: PackedStringArray = PackedStringArray()
@export_dir var materials_dir: String = "res://assets/zone01/materials"
@export var tint: Color = Color(0.8, 0.76, 0.66)
## Пучков-сканов на м² при плотности 1.
@export var per_m2: float = 14.0
@export var cell: float = 12.0
## Радиус пучков-сканов на «высоко» (на среднем и низком — меньше, Balance.GRASS.quality).
@export var radius: float = 32.0
@export var scale_range: Vector2 = Vector2(2.0, 3.2)
@export var build_per_frame: int = 4
## Густой нижний ярус травинок.
@export var lawn: bool = true
## Множитель густоты нижнего яруса в этой сцене.
@export var lawn_density: float = 1.0
## Сухость травинок 0..1 (0 — зелёная, 1 — солома).
@export_range(0.0, 1.0) var lawn_dryness: float = 0.3

var _density: Image
var _terrain: Node
var _meshes: Array[Mesh] = []
var _weeds: Array[Mesh] = []
var _scan_mats: Array[ShaderMaterial] = []
var _cells: Dictionary = {}
var _lawn_cells: Dictionary = {}
var _lawn_near: Array[Mesh] = []
var _lawn_far: Array[Mesh] = []
var _lawn_mat: ShaderMaterial
var _wind_noise: NoiseTexture2D
var _height_noise: FastNoiseLite
var _quality: String = ""
var _q: Dictionary = {}


func _ready() -> void:
	if Engine.is_editor_hint():
		return
	if density_map == "" or not ResourceLoader.exists(density_map):
		return
	_density = (load(density_map) as Texture2D).get_image()
	if _density.is_compressed():
		_density.decompress()
	_terrain = get_tree().get_first_node_in_group("district_terrain")
	_wind_noise = _make_wind_noise()
	_height_noise = FastNoiseLite.new()
	_height_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	_height_noise.frequency = 0.09
	_height_noise.seed = 7151
	for path in models:
		_add_scan(path, _meshes)
	for path in weed_models:
		_add_scan(path, _weeds)
	if lawn:
		_build_lawn_meshes()
	if GrassTrample.current == null or not is_instance_valid(GrassTrample.current):
		var tr := GrassTrample.new()
		tr.name = "GrassTrample"
		add_child(tr)
	_apply_quality()
	Settings.changed.connect(_apply_quality)


## Бесшовный шум для ветра (R — порывы) и пятен сухости (G); общий у обоих ярусов.
func _make_wind_noise() -> NoiseTexture2D:
	var n := FastNoiseLite.new()
	n.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	n.frequency = 0.012
	n.fractal_octaves = 3
	n.seed = 913
	var t := NoiseTexture2D.new()
	t.width = 256
	t.height = 256
	t.seamless = true
	t.generate_mipmaps = true
	t.noise = n
	return t


func _add_scan(path: String, into: Array[Mesh]) -> void:
	if not ResourceLoader.exists(path):
		return
	var inst: Node = (load(path) as PackedScene).instantiate()
	var found: Array[Node] = inst.find_children("*", "MeshInstance3D", true, false)
	if not found.is_empty():
		var mesh: Mesh = (found[0] as MeshInstance3D).mesh
		var src := mesh.surface_get_material(0) as BaseMaterial3D
		var m := ShaderMaterial.new()
		m.shader = SCAN_SHADER
		if src:
			m.set_shader_parameter("albedo_tex", src.albedo_texture)
		m.set_shader_parameter("tint", tint)
		m.set_shader_parameter("mesh_height", maxf(mesh.get_aabb().end.y, 0.02))
		m.set_shader_parameter("wind_noise", _wind_noise)
		into.append(mesh)
		_scan_mats.append(m)
	inst.free()


## Куртины густого яруса: несколько раскладок, ближняя (полные травинки) и дальняя (реже, шире).
func _build_lawn_meshes() -> void:
	var cfg: Dictionary = Balance.GRASS
	var patch := float(cfg.patch)
	var height: Vector2 = cfg.height
	for v in range(int(cfg.variants)):
		_lawn_near.append(GrassBlades.patch_mesh(4021 + v * 97, int(cfg.blades_near), int(cfg.segments_near), patch, 1.0, height, float(cfg.thatch)))
		_lawn_far.append(GrassBlades.patch_mesh(7333 + v * 89, int(cfg.blades_far), int(cfg.segments_far), patch, float(cfg.far_width_k), height, float(cfg.thatch)))
	_lawn_mat = ShaderMaterial.new()
	_lawn_mat.shader = BLADES_SHADER
	_lawn_mat.set_shader_parameter("wind_noise", _wind_noise)
	_lawn_mat.set_shader_parameter("dryness", lawn_dryness)


## Радиусы и густота по качеству графики; поменялось — покров строится заново.
func _apply_quality() -> void:
	var q: String = Settings.quality if Settings.quality in Balance.GRASS.quality else "high"
	if q == _quality:
		return
	_quality = q
	_q = Balance.GRASS.quality[q]
	for c: Vector2i in _cells.keys():
		(_cells[c] as Node).queue_free()
	_cells.clear()
	for c: Vector2i in _lawn_cells.keys():
		(_lawn_cells[c] as Node).queue_free()
	_lawn_cells.clear()
	var far := float(_q.far)
	if _lawn_mat:
		_lawn_mat.set_shader_parameter("fade_start", far - float(Balance.GRASS.fade_m))
		_lawn_mat.set_shader_parameter("fade_end", far)
	var sr := _scan_radius()
	for m in _scan_mats:
		m.set_shader_parameter("fade_start", sr - 4.0)
		m.set_shader_parameter("fade_end", sr)


func _scan_radius() -> float:
	return minf(radius, float(_q.get("scan", radius)))


func _density_at(x: float, z: float) -> Color:
	var px: int = int(x - origin.x)
	var pz: int = int(z - origin.y)
	if px < 0 or pz < 0 or px >= _density.get_width() or pz >= _density.get_height():
		return Color(0, 0, 0)
	return _density.get_pixel(px, pz)


func _height(x: float, z: float) -> float:
	return float(_terrain.call("height_at", x, z)) if _terrain else 0.0


func _process(_delta: float) -> void:
	if _density == null or _q.is_empty():
		return
	var cam := get_viewport().get_camera_3d()
	if cam == null:
		return
	var p := cam.global_position
	if not _meshes.is_empty():
		_update_grid(_cells, cell, _scan_radius(), p, _build_cell)
	if not _lawn_near.is_empty():
		_update_grid(_lawn_cells, float(Balance.GRASS.cell), float(_q.far), p, _build_lawn_cell)


## Клетки сетки размера size в радиусе r от p: лишние освобождаются, недостающие строятся (ближние
## первыми, не больше build_per_frame за кадр).
func _update_grid(cells: Dictionary, size: float, r: float, p: Vector3, build: Callable) -> void:
	var c0 := Vector2i(floori(p.x / size), floori(p.z / size))
	var n: int = int(ceil(r / size))
	var want: Dictionary = {}
	var todo: Array[Vector2i] = []
	for dz in range(-n, n + 1):
		for dx in range(-n, n + 1):
			var c := c0 + Vector2i(dx, dz)
			var center := Vector2((float(c.x) + 0.5) * size, (float(c.y) + 0.5) * size)
			if center.distance_to(Vector2(p.x, p.z)) > r + size * 0.71:
				continue
			want[c] = true
			if not cells.has(c):
				todo.append(c)
	for c: Vector2i in cells.keys():
		if not want.has(c):
			(cells[c] as Node).queue_free()
			cells.erase(c)
	todo.sort_custom(func(a: Vector2i, b: Vector2i) -> bool: return (a - c0).length_squared() < (b - c0).length_squared())
	for i in range(mini(build_per_frame, todo.size())):
		cells[todo[i]] = build.call(todo[i])


func _build_cell(c: Vector2i) -> Node3D:
	var root := Node3D.new()
	root.name = "Cell_%d_%d" % [c.x, c.y]
	add_child(root)
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(Vector2i(c.x * 73856093, c.y * 19349663))
	var per_mesh: Array = []
	for i in range(_meshes.size() + _weeds.size()):
		per_mesh.append([])
	var n: int = int(cell * cell * per_m2 * float(_q.get("scan_density", 1.0)))
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
		var y: float = _height(x, z)
		var s: float = rng.randf_range(scale_range.x, scale_range.y) * (0.75 + 0.35 * d.r)
		var t := Transform3D(Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3(s, s * rng.randf_range(0.85, 1.25), s)), Vector3(x, y - 0.03, z))
		(per_mesh[idx] as Array).append([t, rng.randf()])
	for i in range(per_mesh.size()):
		var list: Array = per_mesh[i]
		if list.is_empty():
			continue
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_custom_data = true
		mm.mesh = _meshes[i] if i < _meshes.size() else _weeds[i - _meshes.size()]
		mm.instance_count = list.size()
		for k in range(list.size()):
			mm.set_instance_transform(k, list[k][0])
			var v: float = float(list[k][1])
			# r — яркость, g — сколько в соломенный оттенок
			mm.set_instance_custom_data(k, Color(0.8 + 0.3 * fposmod(v * 7.3, 1.0), v, 0.0, 0.0))
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		mmi.material_override = _scan_mats[i]
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mmi.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
		root.add_child(mmi)
	return root


## Клетка густого яруса: куртины по плотности карты, на земле и по её наклону; высота — пятнами
## (шум), у края травы — ниже и реже. Две раскладки куртин вперемешку, у каждой — ближний и дальний вид.
func _build_lawn_cell(c: Vector2i) -> Node3D:
	var cfg: Dictionary = Balance.GRASS
	var size := float(cfg.cell)
	var root := Node3D.new()
	root.name = "Lawn_%d_%d" % [c.x, c.y]
	var center := Vector3((float(c.x) + 0.5) * size, 0.0, (float(c.y) + 0.5) * size)
	center.y = _height(center.x, center.z)
	root.position = center
	add_child(root)
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(Vector2i(c.x * 92837111, c.y * 689287499))
	var patch := float(cfg.patch)
	var slots: int = int(size * size / (patch * patch) * float(_q.density) * lawn_density)
	var from := float(cfg.lawn_from)
	var full := float(cfg.lawn_full)
	var groups: Array = [[], []]
	var tilt := float(cfg.max_tilt)
	for i in range(slots):
		var x: float = (float(c.x) + rng.randf()) * size
		var z: float = (float(c.y) + rng.randf()) * size
		var d := _density_at(x, z)
		var k := smoothstep(from, full, d.r + d.g * 0.5)
		var roll := rng.randf()
		if roll >= k:
			continue
		var y := _height(x, z)
		# наклон куртины — по склону (иначе край квадрата висит над землёй или тонет)
		var e := 0.3
		var nrm := Vector3(_height(x - e, z) - _height(x + e, z), 2.0 * e, _height(x, z - e) - _height(x, z + e)).normalized()
		if nrm.dot(Vector3.UP) < tilt:
			nrm = Vector3.UP.slerp(nrm, 0.5)
		var yaw := rng.randf() * TAU
		var b := Basis(Vector3.UP, yaw)
		var axis := Vector3.UP.cross(nrm)
		if axis.length() > 0.001:
			b = Basis(axis.normalized(), Vector3.UP.angle_to(nrm)) * b
		var hn := _height_noise.get_noise_2d(x, z) * 0.5 + 0.5
		var hs := lerpf(float(cfg.height_k.x), float(cfg.height_k.y), hn) * (0.7 + 0.3 * k) * rng.randf_range(0.88, 1.12)
		var sxz := rng.randf_range(0.9, 1.15)
		b = b * Basis.from_scale(Vector3(sxz, hs, sxz))
		var t := Transform3D(b, Vector3(x, y - 0.015, z) - center)
		(groups[rng.randi() % 2] as Array).append([t, Color(rng.randf_range(0.9, 1.08), rng.randf(), 0.0, 0.0)])
	var near := float(_q.near)
	var margin := float(cfg.lod_margin)
	var vi: int = absi(hash(c)) % _lawn_near.size()
	for g in range(groups.size()):
		var list: Array = groups[g]
		if list.is_empty():
			continue
		var variant: int = (vi + g) % _lawn_near.size()
		for lod in range(2):
			var mm := MultiMesh.new()
			mm.transform_format = MultiMesh.TRANSFORM_3D
			mm.use_custom_data = true
			mm.mesh = _lawn_near[variant] if lod == 0 else _lawn_far[variant]
			mm.instance_count = list.size()
			for k in range(list.size()):
				mm.set_instance_transform(k, list[k][0])
				mm.set_instance_custom_data(k, list[k][1])
			var mmi := MultiMeshInstance3D.new()
			mmi.multimesh = mm
			mmi.material_override = _lawn_mat
			mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			mmi.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
			mmi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
			if lod == 0:
				mmi.visibility_range_end = near
				mmi.visibility_range_end_margin = margin
			else:
				mmi.visibility_range_begin = near
				mmi.visibility_range_begin_margin = margin
			root.add_child(mmi)
	return root


## Для проверок и замеров: сколько клеток, экземпляров и треугольников в кадре могло бы быть.
func stats() -> Dictionary:
	var lawn_inst := 0
	var lawn_tris := 0
	for c: Vector2i in _lawn_cells:
		for mmi in (_lawn_cells[c] as Node).get_children():
			var mm := (mmi as MultiMeshInstance3D).multimesh
			lawn_inst += mm.instance_count
			var arr: Array = mm.mesh.surface_get_arrays(0)
			lawn_tris += mm.instance_count * (arr[Mesh.ARRAY_INDEX] as PackedInt32Array).size() / 3
	var scan_inst := 0
	for c: Vector2i in _cells:
		for mmi in (_cells[c] as Node).get_children():
			scan_inst += (mmi as MultiMeshInstance3D).multimesh.instance_count
	return {"quality": _quality, "lawn_cells": _lawn_cells.size(), "lawn_instances": lawn_inst, "lawn_tris_all_lods": lawn_tris, "scan_cells": _cells.size(), "scan_instances": scan_inst}
