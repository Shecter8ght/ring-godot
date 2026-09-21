class_name SectorBuilder
extends RefCounted
## Собирает сектор кольца из данных (data/sectors/*.json) в узлы: полы, стены, проёмы, свет.
## Координаты — полярные от центра кольца: угол a в градусах (от +X к +Z), радиус r в метрах.
## Помещение — кольцевой сектор [a0,a1]×[r0,r1]; стены строятся по границам помещений
## один раз на линию, проёмы вырезают их. Ничего не кладётся руками — только данные.

## Длина сегмента дуги, м: чем меньше, тем круглее стены и полы.
const SEG_LEN := 1.0
## Сдвиг от линии стены при поиске помещений по сторонам, м / град.
const EPS_R := 0.05
const EPS_A := 0.05

var _def: Dictionary
var _rooms: Array = []
var _openings: Array = []
var _wall_h: float = 7.0
var _wall_t: float = 0.3
var _fence_h: float = 2.2
var _barrier_h: float = 2.6
## SurfaceTool на материал — весь сектор одного материала рисуется одним мешем.
var _walls: Dictionary = {}
var _floors: Dictionary = {}


static func polar(a_deg: float, r: float) -> Vector3:
	var a := deg_to_rad(a_deg)
	return Vector3(r * cos(a), 0.0, r * sin(a))


static func load_def(path: String) -> Dictionary:
	var text := FileAccess.get_file_as_string(path)
	var parsed: Variant = JSON.parse_string(text)
	if parsed == null or not (parsed is Dictionary):
		push_error("SectorBuilder: не удалось прочитать " + path)
		return {}
	return parsed


## Строит сектор и возвращает корневой узел. В meta корня: rooms (массив словарей), spawn (Vector3).
func build(path: String) -> Node3D:
	_def = load_def(path)
	var root := Node3D.new()
	root.name = String(_def.get("id", "sector"))
	if _def.is_empty():
		return root
	_rooms = _def.get("rooms", [])
	_openings = _def.get("openings", [])
	var walls: Dictionary = _def.get("walls", {})
	_wall_h = float(walls.get("height", 7.0))
	_wall_t = float(walls.get("thickness", 0.3))
	_fence_h = float(walls.get("fence_height", 2.2))
	_barrier_h = float(walls.get("barrier_height", 2.6))

	_build_floors()
	_build_walls()
	_emit_meshes(root)
	_build_floor_collider(root)
	_build_lights(root)
	_build_markers(root)

	root.set_meta("rooms", _rooms)
	var sp: Dictionary = _def.get("spawn", {})
	root.set_meta("spawn", polar(float(sp.get("a", 0.0)), float(sp.get("r", 100.0))))
	return root


# ---------------------------------------------------------------- геометрия

func _st(store: Dictionary, mat_id: String) -> SurfaceTool:
	if not store.has(mat_id):
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		store[mat_id] = st
	return store[mat_id]


func _build_floors() -> void:
	for room in _rooms:
		var a0 := float(room.a[0])
		var a1 := float(room.a[1])
		var r0 := float(room.r[0])
		var r1 := float(room.r[1])
		var st := _st(_floors, String(room.get("floor", "concrete_floor_worn_001")))
		var n := maxi(1, int(ceil(deg_to_rad(a1 - a0) * r1 / SEG_LEN)))
		for i in range(n):
			var aa := lerpf(a0, a1, float(i) / n)
			var ab := lerpf(a0, a1, float(i + 1) / n)
			var p00 := polar(aa, r0)
			var p01 := polar(aa, r1)
			var p10 := polar(ab, r0)
			var p11 := polar(ab, r1)
			_quad(st, p00, p10, p11, p01, Vector3.UP, _uv_xz(p00), _uv_xz(p10), _uv_xz(p11), _uv_xz(p01))


func _uv_xz(p: Vector3) -> Vector2:
	return Vector2(p.x, p.z)


## Четырёхугольник против часовой (если смотреть вдоль -normal).
func _quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3, n: Vector3, ua: Vector2, ub: Vector2, uc: Vector2, ud: Vector2) -> void:
	st.set_normal(n)
	st.set_uv(ua)
	st.add_vertex(a)
	st.set_uv(uc)
	st.add_vertex(c)
	st.set_uv(ub)
	st.add_vertex(b)
	st.set_normal(n)
	st.set_uv(ua)
	st.add_vertex(a)
	st.set_uv(ud)
	st.add_vertex(d)
	st.set_uv(uc)
	st.add_vertex(c)


## Стена-полоса по ломаной points толщиной t и высотой h. UV: u — длина вдоль, v — высота (метры).
func _wall_strip(st: SurfaceTool, points: PackedVector3Array, t: float, h: float) -> void:
	var u := 0.0
	for i in range(points.size() - 1):
		var p0 := points[i]
		var p1 := points[i + 1]
		var d := (p1 - p0)
		var len := d.length()
		if len < 0.001:
			continue
		d /= len
		var n := Vector3(-d.z, 0.0, d.x)
		var o := n * (t * 0.5)
		var up := Vector3.UP * h
		# левая грань (по нормали n)
		_quad(st, p0 + o, p1 + o, p1 + o + up, p0 + o + up, n, Vector2(u, 0), Vector2(u + len, 0), Vector2(u + len, h), Vector2(u, h))
		# правая грань
		_quad(st, p1 - o, p0 - o, p0 - o + up, p1 - o + up, -n, Vector2(u + len, 0), Vector2(u, 0), Vector2(u, h), Vector2(u + len, h))
		# верх
		_quad(st, p0 - o + up, p1 - o + up, p1 + o + up, p0 + o + up, Vector3.UP, Vector2(u, 0), Vector2(u + len, 0), Vector2(u + len, t), Vector2(u, t))
		u += len
	# торцы
	if points.size() >= 2:
		_cap(st, points[0], points[1], t, h, true)
		_cap(st, points[points.size() - 1], points[points.size() - 2], t, h, false)


func _cap(st: SurfaceTool, p: Vector3, towards: Vector3, t: float, h: float, start: bool) -> void:
	var d := (towards - p).normalized()
	var n := Vector3(-d.z, 0.0, d.x)
	var o := n * (t * 0.5)
	var up := Vector3.UP * h
	var out := -d
	if start:
		_quad(st, p - o, p + o, p + o + up, p - o + up, out, Vector2(0, 0), Vector2(t, 0), Vector2(t, h), Vector2(0, h))
	else:
		_quad(st, p + o, p - o, p - o + up, p + o + up, out, Vector2(0, 0), Vector2(t, 0), Vector2(t, h), Vector2(0, h))


func _arc_points(r: float, a0: float, a1: float) -> PackedVector3Array:
	var pts := PackedVector3Array()
	var n := maxi(1, int(ceil(deg_to_rad(absf(a1 - a0)) * r / SEG_LEN)))
	for i in range(n + 1):
		pts.append(polar(lerpf(a0, a1, float(i) / n), r))
	return pts


# ---------------------------------------------------------------- стены по линиям

func _room_at(a: float, r: float) -> Dictionary:
	for room in _rooms:
		if a >= float(room.a[0]) - 1e-6 and a <= float(room.a[1]) + 1e-6 and r >= float(room.r[0]) - 1e-6 and r <= float(room.r[1]) + 1e-6:
			return room
	return {}


func _opening_at(kind_wall: String, fixed: float, along: float) -> Dictionary:
	for op in _openings:
		if String(op.wall) != kind_wall:
			continue
		var f := float(op.r) if kind_wall == "arc" else float(op.a)
		if absf(f - fixed) > 0.01:
			continue
		var rng: Array = op.a if kind_wall == "arc" else op.r
		if along >= float(rng[0]) - 1e-6 and along <= float(rng[1]) + 1e-6:
			return op
	return {}


func _build_walls() -> void:
	# Линии: дуги по радиусу и радиальные по углу; на каждой — точки разбиения.
	var arcs: Dictionary = {}
	var rads: Dictionary = {}
	for room in _rooms:
		for r in [float(room.r[0]), float(room.r[1])]:
			_add_breaks(arcs, r, [float(room.a[0]), float(room.a[1])])
		for a in [float(room.a[0]), float(room.a[1])]:
			_add_breaks(rads, a, [float(room.r[0]), float(room.r[1])])
	for op in _openings:
		if String(op.wall) == "arc":
			_add_breaks(arcs, float(op.r), [float(op.a[0]), float(op.a[1])])
		else:
			_add_breaks(rads, float(op.a), [float(op.r[0]), float(op.r[1])])

	for key in arcs:
		var r: float = arcs[key].fixed
		var br: Array = arcs[key].breaks
		br.sort()
		for i in range(br.size() - 1):
			var a0: float = br[i]
			var a1: float = br[i + 1]
			if a1 - a0 < 1e-4:
				continue
			var mid := (a0 + a1) * 0.5
			var inner := _room_at(mid, r - EPS_R)
			var outer := _room_at(mid, r + EPS_R)
			var op := _opening_at("arc", r, mid)
			_emit_wall_segment(_arc_points(r, a0, a1), inner, outer, op)
	for key in rads:
		var a: float = rads[key].fixed
		var br: Array = rads[key].breaks
		br.sort()
		for i in range(br.size() - 1):
			var r0: float = br[i]
			var r1: float = br[i + 1]
			if r1 - r0 < 1e-4:
				continue
			var mid := (r0 + r1) * 0.5
			var before := _room_at(a - EPS_A, mid)
			var after := _room_at(a + EPS_A, mid)
			var op := _opening_at("radial", a, mid)
			var pts := PackedVector3Array([polar(a, r0), polar(a, r1)])
			_emit_wall_segment(pts, before, after, op)


func _add_breaks(lines: Dictionary, fixed: float, ends: Array) -> void:
	var key := "%.2f" % fixed
	if not lines.has(key):
		lines[key] = {"fixed": fixed, "breaks": []}
	for e in ends:
		var found := false
		for b in lines[key].breaks:
			if absf(float(b) - float(e)) < 1e-4:
				found = true
				break
		if not found:
			lines[key].breaks.append(float(e))


func _emit_wall_segment(pts: PackedVector3Array, side_a: Dictionary, side_b: Dictionary, op: Dictionary) -> void:
	if not op.is_empty():
		match String(op.kind):
			"open", "door", "shutter", "gate":
				return
			"locked":
				_wall_strip(_st(_walls, "painted_metal_shutter"), pts, _wall_t * 0.5, _wall_h)
				return
			"barrier":
				_wall_strip(_st(_walls, "concrete_block_wall_02"), pts, _wall_t * 2.0, _barrier_h)
				return
	if side_a.is_empty() and side_b.is_empty():
		return
	var a_out: bool = side_a.is_empty() or bool(side_a.get("outdoor", false))
	var b_out: bool = side_b.is_empty() or bool(side_b.get("outdoor", false))
	if a_out and b_out:
		# двор–двор: границы нет; двор–пустота: ограда периметра
		if side_a.is_empty() or side_b.is_empty():
			_wall_strip(_st(_walls, "concrete_block_wall_02"), pts, _wall_t, _fence_h)
		return
	var indoor := side_b if a_out else side_a
	var other := side_a if a_out else side_b
	# Стена наружу здания — панели фасада, между помещениями — материал помещения.
	var mat := "concrete_panels" if (other.is_empty() or bool(other.get("outdoor", false))) else String(indoor.get("wall", "painted_plaster_wall"))
	_wall_strip(_st(_walls, mat), pts, _wall_t, _wall_h)


# ---------------------------------------------------------------- узлы

func _emit_meshes(root: Node3D) -> void:
	var floors := Node3D.new()
	floors.name = "Floors"
	root.add_child(floors)
	for mat_id in _floors:
		floors.add_child(_mesh_node(_floors[mat_id], String(mat_id), false))
	var walls := StaticBody3D.new()
	walls.name = "Walls"
	root.add_child(walls)
	for mat_id in _walls:
		var mi := _mesh_node(_walls[mat_id], String(mat_id), true)
		walls.add_child(mi)
		var cs := CollisionShape3D.new()
		cs.name = mi.name + "_col"
		cs.shape = (mi.mesh as ArrayMesh).create_trimesh_shape()
		walls.add_child(cs)


func _mesh_node(st: SurfaceTool, mat_id: String, shadows: bool) -> MeshInstance3D:
	st.generate_tangents()
	var mesh := st.commit()
	var mi := MeshInstance3D.new()
	mi.name = mat_id
	mi.mesh = mesh
	mi.material_override = SectorMaterials.get_material(mat_id)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi


func _build_floor_collider(root: Node3D) -> void:
	var body := StaticBody3D.new()
	body.name = "Ground"
	var cs := CollisionShape3D.new()
	cs.shape = WorldBoundaryShape3D.new()
	body.add_child(cs)
	root.add_child(body)


## Аварийный свет внутри и прожекторы на дворах. Закрытые помещения — тёмные.
func _build_lights(root: Node3D) -> void:
	var lights := Node3D.new()
	lights.name = "Lights"
	root.add_child(lights)
	for room in _rooms:
		if bool(room.get("locked", false)):
			continue
		var a0 := float(room.a[0])
		var a1 := float(room.a[1])
		var r0 := float(room.r[0])
		var r1 := float(room.r[1])
		var rm := (r0 + r1) * 0.5
		var arc_len := deg_to_rad(a1 - a0) * rm
		var depth := r1 - r0
		var outdoor := bool(room.get("outdoor", false))
		var step := 22.0 if outdoor else 11.0
		var na := maxi(1, int(round(arc_len / step)))
		var nr := maxi(1, int(round(depth / step)))
		for i in range(na):
			for j in range(nr):
				var a := lerpf(a0, a1, (i + 0.5) / na)
				var r := lerpf(r0, r1, (j + 0.5) / nr)
				var pos := polar(a, r)
				if outdoor:
					var spot := SpotLight3D.new()
					spot.position = pos + Vector3(0, 8.0, 0)
					spot.rotation_degrees.x = -90.0
					spot.light_color = Color(1.0, 0.74, 0.45)
					spot.light_energy = 9.0
					spot.spot_range = 30.0
					spot.spot_angle = 55.0
					spot.shadow_enabled = true
					lights.add_child(spot)
				else:
					var omni := OmniLight3D.new()
					omni.position = pos + Vector3(0, minf(_wall_h - 1.0, 5.5), 0)
					omni.light_color = Color(0.82, 0.92, 0.88)
					omni.light_energy = 3.5
					omni.omni_range = 13.0
					omni.omni_attenuation = 1.4
					lights.add_child(omni)


## Точки эвакуации из проёмов kind=gate с полем extraction.
func _build_markers(root: Node3D) -> void:
	var marks := Node3D.new()
	marks.name = "Markers"
	root.add_child(marks)
	for op in _openings:
		if not op.has("extraction"):
			continue
		var m := Node3D.new()
		m.name = String(op.extraction)
		if String(op.wall) == "arc":
			m.position = polar((float(op.a[0]) + float(op.a[1])) * 0.5, float(op.r))
		else:
			m.position = polar(float(op.a), (float(op.r[0]) + float(op.r[1])) * 0.5)
		m.add_to_group("extractions")
		marks.add_child(m)
