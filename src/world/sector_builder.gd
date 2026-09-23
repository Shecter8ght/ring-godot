@tool
class_name SectorBuilder
extends RefCounted
## Собирает сектор кольца из данных (data/sectors/*.json) в узлы: полы, стены, проёмы, свет.
## Координаты — полярные от центра кольца: угол a в градусах (от +X к +Z), радиус r в метрах.
## Помещение — кольцевой сектор [a0,a1]×[r0,r1]; стены строятся по границам помещений
## один раз на линию, проёмы вырезают их. Ничего не кладётся руками — только данные.
## Постройки вокруг (паркинг, техкомплекс…) — отдельные сцены в сцене уровня, их двигают руками.
##
## Блокаут ("greybox": true в JSON): стены без текстур и декора, толщина — по классу конструкции
## (фасад / противопожарная / несущая / перегородка, числа в блоке "walls", нормы —
## docs/building_standards.md). Скрипт @tool: в редакторе строит превью без дверей и пропсов.

## Длина сегмента дуги, м: чем меньше, тем круглее стены и полы.
const SEG_LEN := 1.0
## Сдвиг от линии стены при поиске помещений по сторонам, м / град.
const EPS_R := 0.05
const EPS_A := 0.05
## Радиальная стена ближе этого к границе сектора — противопожарная (между пожарными отсеками), град.
const FIRE_TOL_DEG := 2.0
## Склейка пропсов: клетка, м, и дальность, дальше которой клетка не рисуется, м (изометрия видит
## ~80 м от камеры; в прицеле дальше всё равно стены и дымка).
const PROP_BATCH_CELL := 24.0
const PROP_VIS_END := 110.0
## Пол закрытой части кольца по поясам (ключи ring.zones).
const ZONE_FLOOR := {
	"atr": "large_floor_tiles_02", "gal": "large_floor_tiles_02", "inn": "worn_tile_floor", "st": "large_floor_tiles_02",
	"out": "worn_tile_floor", "back": "concrete_floor_worn_001", "svc": "concrete_floor_worn_001",
}

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
## Стекло — отдельным мешем: без теней и с прозрачностью.
var _glass: Dictionary = {}
## Где уже стоит пилястра/колонна — чтобы на стыках стен не было двойных.
var _posts: Dictionary = {}
var _doors: Array[Door] = []
var _labels: Array[Label3D] = []
## Архитектурные размеры (блок "arch" в JSON поверх ARCH_DEFAULT, м).
var _arch: Dictionary = {}
## Блокаут: серые классы стен вместо текстур, без декора (цоколь, карниз, пилястры, баннеры).
var _greybox: bool = false
## Толщина по классу стены (блок "walls"); чего нет — _base_t.
var _thick: Dictionary = {}
var _base_t: float = 0.3
var _ring: Dictionary = {}
var _fire_angles: Array[float] = []
## Превью в редакторе: без дверей-сцен и пропсов (их скрипты работают только в игре).
var _preview: bool = false

const DOOR_SCENE := preload("res://scenes/props/door.tscn")
const ARCH_DEFAULT := {
	"plinth_h": 0.4, "cornice_h": 0.35, "pilaster_w": 0.5, "pilaster_spacing": 6.0, "column_spacing": 6.0,
	"storefront_h": 3.6, "door_h": 2.2, "shutter_h": 3.2, "gate_h": 4.5,
	"entrance_w": 3.2, "pane_w": 1.6, "broken_pane_pct": 22, "sign_h": 0.9,
}


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
	_base_t = _wall_t
	_thick = walls
	_greybox = bool(_def.get("greybox", false))
	_ring = _def.get("ring", {})
	_preview = Engine.is_editor_hint()
	for sec in _def.get("sectors", []):
		for a in sec.a:
			if not float(a) in _fire_angles:
				_fire_angles.append(float(a))
	_arch = ARCH_DEFAULT.duplicate()
	_arch.merge(_def.get("arch", {}), true)

	_build_floors()
	_build_walls()
	_build_surroundings()
	if not _greybox:
		_build_overhead()
	_emit_meshes(root)
	_build_floor_collider(root)
	_build_lights(root)
	_build_markers(root)
	if not _preview:
		_build_props(root)

	root.set_meta("rooms", _rooms)
	root.set_meta("ring", _ring)
	root.set_meta("camera_yaw", float(_def.get("camera_yaw", -45.0)))
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


## Стена-полоса по ломаной points толщиной t, от высоты y0 до y0+h. UV: u — длина вдоль, v — высота (метры).
func _wall_strip(st: SurfaceTool, points: PackedVector3Array, t: float, h: float, y0: float = 0.0) -> void:
	var u := 0.0
	var base := Vector3.UP * y0
	for i in range(points.size() - 1):
		var p0 := points[i] + base
		var p1 := points[i + 1] + base
		var d := (p1 - p0)
		var len := d.length()
		if len < 0.001:
			continue
		d /= len
		var n := Vector3(-d.z, 0.0, d.x)
		var o := n * (t * 0.5)
		var up := Vector3.UP * h
		# левая грань (по нормали n)
		_quad(st, p0 + o, p1 + o, p1 + o + up, p0 + o + up, n, Vector2(u, y0), Vector2(u + len, y0), Vector2(u + len, y0 + h), Vector2(u, y0 + h))
		# правая грань
		_quad(st, p1 - o, p0 - o, p0 - o + up, p1 - o + up, -n, Vector2(u + len, y0), Vector2(u, y0), Vector2(u, y0 + h), Vector2(u + len, y0 + h))
		# верх
		_quad(st, p0 - o + up, p1 - o + up, p1 + o + up, p0 + o + up, Vector3.UP, Vector2(u, 0), Vector2(u + len, 0), Vector2(u + len, t), Vector2(u, t))
		# низ (виден у карнизов и ригелей снизу)
		if y0 > 0.001:
			_quad(st, p0 + o, p1 + o, p1 - o, p0 - o, Vector3.DOWN, Vector2(u, 0), Vector2(u + len, 0), Vector2(u + len, t), Vector2(u, t))
		u += len
	# торцы
	if points.size() >= 2:
		_cap(st, points[0] + base, points[1] + base, t, h, true)
		_cap(st, points[points.size() - 1] + base, points[points.size() - 2] + base, t, h, false)


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


## Столб/пилястра: короткая стена длиной w поперёк линии в точке p, вдоль направления dir.
func _post(st: SurfaceTool, p: Vector3, dir: Vector3, w: float, t: float, h: float, y0: float = 0.0) -> void:
	var half := dir.normalized() * (w * 0.5)
	_wall_strip(st, PackedVector3Array([p - half, p + half]), t, h, y0)


# ---------------------------------------------------------------- линии стен
# Линия — дуга (kind "arc", fixed = r, параметр = угол) или радиус (kind "radial", fixed = a, параметр = r).

func _line_point(line: Dictionary, p: float) -> Vector3:
	return polar(p, float(line.fixed)) if String(line.kind) == "arc" else polar(float(line.fixed), p)


## Длина отрезка линии в метрах между параметрами p0 и p1.
func _line_len(line: Dictionary, p0: float, p1: float) -> float:
	if String(line.kind) == "arc":
		return deg_to_rad(absf(p1 - p0)) * float(line.fixed)
	return absf(p1 - p0)


## Параметр, отстоящий от p0 на dist метров в сторону роста параметра.
func _line_advance(line: Dictionary, p0: float, dist: float) -> float:
	if String(line.kind) == "arc":
		return p0 + rad_to_deg(dist / float(line.fixed))
	return p0 + dist


func _line_points(line: Dictionary, p0: float, p1: float) -> PackedVector3Array:
	if String(line.kind) == "arc":
		return _arc_points(float(line.fixed), p0, p1)
	return PackedVector3Array([_line_point(line, p0), _line_point(line, p1)])


func _line_dir(line: Dictionary, p: float) -> Vector3:
	var eps := 0.01
	return (_line_point(line, p + eps) - _line_point(line, p - eps)).normalized()


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
		var line := {"kind": "arc", "fixed": arcs[key].fixed}
		var r: float = arcs[key].fixed
		var br: Array = arcs[key].breaks
		br.sort()
		for i in range(br.size() - 1):
			var a0: float = br[i]
			var a1: float = br[i + 1]
			if a1 - a0 < 1e-4:
				continue
			var mid := (a0 + a1) * 0.5
			_emit_wall_segment(line, a0, a1, _room_at(mid, r - EPS_R), _room_at(mid, r + EPS_R), _opening_at("arc", r, mid))
	for key in rads:
		var line := {"kind": "radial", "fixed": rads[key].fixed}
		var a: float = rads[key].fixed
		var br: Array = rads[key].breaks
		br.sort()
		for i in range(br.size() - 1):
			var r0: float = br[i]
			var r1: float = br[i + 1]
			if r1 - r0 < 1e-4:
				continue
			var mid := (r0 + r1) * 0.5
			_emit_wall_segment(line, r0, r1, _room_at(a - EPS_A, mid), _room_at(a + EPS_A, mid), _opening_at("radial", a, mid))


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


func _emit_wall_segment(line: Dictionary, p0: float, p1: float, side_a: Dictionary, side_b: Dictionary, op: Dictionary) -> void:
	if side_a.is_empty() and side_b.is_empty():
		return
	var a_out: bool = side_a.is_empty() or bool(side_a.get("outdoor", false))
	var b_out: bool = side_b.is_empty() or bool(side_b.get("outdoor", false))
	var indoor := side_b if a_out else side_a
	var other := side_a if a_out else side_b
	var facade := other.is_empty() or bool(other.get("outdoor", false))
	var cls := _wall_class(line, side_a, side_b, facade)
	# толщина — на отрезок: все помощники ниже (ригели, роллеты, косяки) берут её из _wall_t
	_wall_t = float(_thick.get(cls, _base_t))
	var mat := "concrete_panels" if facade else String(indoor.get("wall", "painted_plaster_wall"))
	if _greybox:
		mat = "gb_" + cls
	var pts := _line_points(line, p0, p1)

	if not op.is_empty():
		match String(op.kind):
			"open":
				_colonnade(line, p0, p1, mat, float(op.get("height", float(_arch.storefront_h))))
			"storefront":
				_storefront(line, p0, p1, mat, side_a, side_b)
			"door":
				_doorway(line, p0, p1, mat, float(op.get("height", float(_arch.door_h))))
			"shutter":
				_rolling_gate(line, p0, p1, mat, float(op.get("height", float(_arch.shutter_h))), false)
			"gate":
				_rolling_gate(line, p0, p1, mat, float(op.get("height", float(_arch.gate_h))), false)
			"locked":
				_rolling_gate(line, p0, p1, mat, float(op.get("height", float(_arch.shutter_h))), true)
			"barrier":
				_wall_strip(_st(_walls, _gb("concrete_block_wall_02", "gb_fence")), pts, _wall_t * 2.0, _barrier_h)
		return

	if a_out and b_out:
		# двор–двор: границы нет; двор–пустота: ограда периметра. У кольца территорию
		# ограничивает забор участка (см. _build_ring_surroundings), дворы между собой открыты.
		if (side_a.is_empty() or side_b.is_empty()) and _ring.is_empty():
			_wall_strip(_st(_walls, "concrete_block_wall_02"), pts, _wall_t, _fence_h)
		return
	_solid_wall(line, p0, p1, mat)


## Класс конструкции стены — от него толщина и серый тон в блокауте.
## facade — наружная; fire — радиальная на границе сектора (пожарный отсек, REI 150);
## structural — дуги между поясами кольца и стены коридоров/техядер; остальное — перегородки арендаторов.
func _wall_class(line: Dictionary, side_a: Dictionary, side_b: Dictionary, facade: bool) -> String:
	if facade:
		return "facade"
	if String(line.kind) == "arc":
		return "structural"
	for fa in _fire_angles:
		if absf(float(line.fixed) - fa) <= FIRE_TOL_DEG:
			return "fire"
	for side in [side_a, side_b]:
		if bool(side.get("core", false)) or String(side.get("type", "")) in ["corridor", "gallery", "atrium"]:
			return "structural"
	return "partition"


## Текстурный материал или его серая замена в блокауте.
func _gb(textured: String, grey: String) -> String:
	return grey if _greybox else textured


## Глухая стена с цоколем, карнизом и пилястрами по концам и через шаг.
func _solid_wall(line: Dictionary, p0: float, p1: float, mat: String) -> void:
	var pts := _line_points(line, p0, p1)
	_wall_strip(_st(_walls, mat), pts, _wall_t, _wall_h)
	if _greybox:
		return
	_wall_strip(_st(_walls, "concrete_wall_006"), pts, _wall_t + 0.12, float(_arch.plinth_h))
	_wall_strip(_st(_walls, mat), pts, _wall_t + 0.16, float(_arch.cornice_h), _wall_h - float(_arch.cornice_h))
	_pilaster(line, p0, mat)
	_pilaster(line, p1, mat)
	var len := _line_len(line, p0, p1)
	var n := int(floor(len / float(_arch.pilaster_spacing)))
	for i in range(1, n + 1):
		var p := _line_advance(line, p0, len * float(i) / float(n + 1))
		_pilaster(line, p, mat)


func _pilaster(line: Dictionary, p: float, mat: String) -> void:
	if _greybox:
		return
	var pos := _line_point(line, p)
	var key := "%.1f,%.1f" % [pos.x, pos.z]
	if _posts.has(key):
		return
	_posts[key] = true
	_post(_st(_walls, mat), pos, _line_dir(line, p), float(_arch.pilaster_w), _wall_t + 0.4, _wall_h)


## Ригель над проёмом: стена от высоты y до верха, с карнизом.
func _lintel(line: Dictionary, p0: float, p1: float, mat: String, y: float) -> void:
	var pts := _line_points(line, p0, p1)
	_wall_strip(_st(_walls, mat), pts, _wall_t, _wall_h - y, y)
	if _greybox:
		return
	_wall_strip(_st(_walls, mat), pts, _wall_t + 0.16, float(_arch.cornice_h), _wall_h - float(_arch.cornice_h))


## Колоннада: проход без стены, балка только под перекрытием, колонны по концам и через шаг.
func _colonnade(line: Dictionary, p0: float, p1: float, mat: String, _y: float) -> void:
	if _greybox:
		# балка перекрытия и колонны по сетке каркаса (квадратные, шаг column_grid)
		_lintel(line, p0, p1, mat, _wall_h - 0.7)
		var col := float(_thick.get("column", 0.6))
		var clen := _line_len(line, p0, p1)
		var cn := maxi(1, int(round(clen / float(_thick.get("column_grid", 9.0)))))
		for i in range(cn + 1):
			var cp := _line_advance(line, p0, clen * float(i) / float(cn))
			var pos := _line_point(line, cp)
			var key := "%.1f,%.1f" % [pos.x, pos.z]
			if _posts.has(key):
				continue
			_posts[key] = true
			_post(_st(_walls, "gb_structural"), pos, _line_dir(line, cp), col, col, _wall_h)
		return
	_lintel(line, p0, p1, mat, _wall_h - float(_arch.cornice_h) * 2.0)
	_pilaster(line, p0, mat)
	_pilaster(line, p1, mat)
	var len := _line_len(line, p0, p1)
	var n := int(floor(len / float(_arch.column_spacing)))
	for i in range(1, n + 1):
		_pilaster(line, _line_advance(line, p0, len * float(i) / float(n + 1)), mat)


## Дверной проём: ригель, косяки и створка (сцена door.tscn) на петле у p0.
func _doorway(line: Dictionary, p0: float, p1: float, mat: String, y: float) -> void:
	_lintel(line, p0, p1, mat, y)
	_pilaster(line, p0, mat)
	_pilaster(line, p1, mat)
	# в блокауте пилястр нет — створка на весь проём
	var jamb := 0.1 if _greybox else float(_arch.pilaster_w)
	var width := _line_len(line, p0, p1) - jamb
	var hinge := _line_point(line, _line_advance(line, p0, jamb * 0.5))
	var dir := _line_dir(line, p0)
	if _preview:
		return
	var door := DOOR_SCENE.instantiate() as Door
	door.width = width
	door.height = y - 0.05
	door.transform = Transform3D(Basis(dir, Vector3.UP, dir.cross(Vector3.UP).normalized()), hinge)
	_doors.append(door)


## Роллета: рулон под ригелем; closed — полотно опущено до пола (непроходимо).
func _rolling_gate(line: Dictionary, p0: float, p1: float, mat: String, y: float, closed: bool) -> void:
	_lintel(line, p0, p1, mat, y)
	_pilaster(line, p0, mat)
	_pilaster(line, p1, mat)
	var pts := _line_points(line, p0, p1)
	var shutter := _gb("painted_metal_shutter", "steel_dark")
	_wall_strip(_st(_walls, shutter), pts, _wall_t + 0.3, 0.45, y - 0.45)
	if closed:
		_wall_strip(_st(_walls, shutter), pts, 0.06, y - 0.45)


## Витрина: стекло в стальных рамах по бокам, вход посередине с рулоном роллеты и вывеской.
func _storefront(line: Dictionary, p0: float, p1: float, mat: String, side_a: Dictionary, side_b: Dictionary) -> void:
	var y: float = float(_arch.storefront_h)
	_lintel(line, p0, p1, mat, y)
	_pilaster(line, p0, mat)
	_pilaster(line, p1, mat)
	var len := _line_len(line, p0, p1)
	var entrance := minf(float(_arch.entrance_w), len * 0.6)
	var e0 := _line_advance(line, p0, (len - entrance) * 0.5)
	var e1 := _line_advance(line, p0, (len + entrance) * 0.5)
	_glass_run(line, p0, e0, y)
	_glass_run(line, e1, p1, y)
	# вход: рулон роллеты и вывеска над ним
	var ent := _line_points(line, e0, e1)
	_wall_strip(_st(_walls, _gb("painted_metal_shutter", "steel_dark")), ent, _wall_t + 0.3, 0.45, y - 0.45)
	var shop := side_a if String(side_a.get("type", "")) == "retail" else side_b
	var gallery_side := side_b if shop == side_a else side_a
	if shop.is_empty():
		return
	var s0 := _line_advance(line, e0, -1.0)
	var s1 := _line_advance(line, e1, 1.0)
	var sign_pts := _line_points(line, s0, s1)
	if not _greybox:
		_wall_strip(_st(_walls, "sign_panel"), sign_pts, _wall_t + 0.24, float(_arch.sign_h), y + 0.5)
	# подпись — в сторону галереи
	var mid := _line_advance(line, e0, entrance * 0.5)
	var pos := _line_point(line, mid)
	var toward_gallery := _side_normal(line, mid, gallery_side)
	var label := Label3D.new()
	label.text = String(shop.get("name", "")).to_upper()
	label.font_size = 64
	label.pixel_size = 0.01
	label.modulate = Color(1.0, 0.86, 0.6)
	label.shaded = false
	label.outline_size = 0
	label.position = pos + toward_gallery * (_wall_t * 0.5 + 0.5) + Vector3.UP * (y + 0.5 + float(_arch.sign_h) * 0.5)
	label.basis = Basis.looking_at(-toward_gallery, Vector3.UP)
	_labels.append(label)


## Единичная нормаль линии в точке p, направленная в сторону помещения room.
func _side_normal(line: Dictionary, p: float, room: Dictionary) -> Vector3:
	var d := _line_dir(line, p)
	var n := Vector3(-d.z, 0.0, d.x)
	if room.is_empty():
		return n
	var probe := _line_point(line, p) + n * 0.5
	var pa := rad_to_deg(atan2(probe.z, probe.x))
	var pr := probe.length()
	var inside := pa >= float(room.a[0]) and pa <= float(room.a[1]) and pr >= float(room.r[0]) and pr <= float(room.r[1])
	return n if inside else -n


## Стеклянные панели между стойками; часть панелей выбита (детерминированно по позиции).
func _glass_run(line: Dictionary, p0: float, p1: float, y: float) -> void:
	var len := _line_len(line, p0, p1)
	if len < 0.3:
		return
	var n := maxi(1, int(round(len / float(_arch.pane_w))))
	var steel := _st(_walls, "steel_dark")
	# нижняя и верхняя рейки рамы
	var pts := _line_points(line, p0, p1)
	_wall_strip(steel, pts, 0.12, float(_arch.plinth_h))
	_wall_strip(steel, pts, 0.12, 0.12, y - 0.12)
	for i in range(n + 1):
		var p := _line_advance(line, p0, len * float(i) / float(n))
		_post(steel, _line_point(line, p), _line_dir(line, p), 0.08, 0.1, y)
	for i in range(n):
		var q0 := _line_advance(line, p0, len * float(i) / float(n))
		var q1 := _line_advance(line, p0, len * float(i + 1) / float(n))
		var c := _line_point(line, (q0 + q1) * 0.5)
		var broken := (hash("%.1f:%.1f" % [c.x, c.z]) % 100) < int(_arch.broken_pane_pct)
		if broken:
			continue
		_wall_strip(_st(_glass, "glass"), _line_points(line, q0, q1), 0.02, y - float(_arch.plinth_h) - 0.12, float(_arch.plinth_h))


## Окружение: кольцо продолжается за пределами сектора — полы, фасад и стена галереи без проёмов,
## асфальт вокруг здания. Каждый пояс радиусов достраивается там, где в нём нет помещений сектора.
func _build_surroundings() -> void:
	if not _ring.is_empty():
		_build_ring_surroundings()
		return
	var bands := [
		{"r": [0.5, 25.0], "floor": "large_floor_tiles_02"},
		{"r": [25.0, 33.0], "floor": "large_floor_tiles_02", "wall_r": 33.0, "wall": "painted_plaster_wall", "wall_h": _wall_h},
		{"r": [33.0, 84.0], "floor": "worn_tile_floor"},
		{"r": [84.0, 90.0], "floor": "concrete_floor_worn_001", "wall_r": 90.0, "wall": "concrete_panels", "wall_h": _wall_h},
		{"r": [90.0, 125.0], "floor": "asphalt_02", "wall_r": 125.0, "wall": "concrete_block_wall_02", "wall_h": _fence_h},
	]
	for band in bands:
		var r0: float = band.r[0]
		var r1: float = band.r[1]
		var a_min := 1e9
		var a_max := -1e9
		for room in _rooms:
			if float(room.r[1]) <= r0 + 1e-3 or float(room.r[0]) >= r1 - 1e-3:
				continue
			a_min = minf(a_min, float(room.a[0]))
			a_max = maxf(a_max, float(room.a[1]))
		var c0 := a_max if a_max > -1e8 else 0.0
		var c1 := (a_min + 360.0) if a_min < 1e8 else 360.0
		if c1 - c0 < 1.0:
			continue
		_annulus(_st(_floors, String(band.floor)), c0, c1, r0, r1, 0.0)
		if band.has("wall_r"):
			_wall_strip(_st(_walls, String(band.wall)), _arc_points(float(band.wall_r), c0, c1), _wall_t, float(band.wall_h))
	_annulus(_st(_floors, "asphalt_02"), 0.0, 360.0, 90.0, 420.0, -0.03)


## Кольцо целиком: закрытая часть (полы поясов, несущие дуги), фасад на всю высоту здания по кругу,
## асфальт участка и забор территории — проходима только открытая часть участка.
func _build_ring_surroundings() -> void:
	var outer := float(_ring.get("outer_r", 200.0))
	var site := float(_ring.get("site_r", 300.0))
	var a0 := float(_def.angle[0])
	var a1 := float(_def.angle[1])
	var c0 := a1
	var c1 := a0 + 360.0
	var zones: Dictionary = _ring.get("zones", {})
	var inner_arcs: Array[float] = []
	for key in zones:
		var z: Array = zones[key]
		_annulus(_st(_floors, String(ZONE_FLOOR.get(key, "concrete_floor_worn_001"))), c0, c1, float(z[0]), float(z[1]), 0.0)
		if key != "atr" and float(z[0]) > 1.0:
			inner_arcs.append(float(z[0]))
	# несущие дуги закрытой части — за роллетами видно, что кольцо продолжается
	var t_str := float(_thick.get("structural", _base_t))
	for r in inner_arcs:
		if r >= outer - 0.01:
			continue
		_wall_strip(_st(_walls, _gb("painted_plaster_wall", "gb_structural")), _arc_points(r, c0, c1), t_str, _wall_h)
	# фасад: закрытая часть — во всю высоту здания; над открытой — верхние этажи поверх стен 1F
	var t_fac := float(_thick.get("facade", _base_t))
	var bh := float(_thick.get("building_height", _wall_h))
	var fmat := _gb("concrete_panels", "gb_facade")
	_wall_strip(_st(_walls, fmat), _arc_points(outer, c0, c1), t_fac, bh)
	if bh > _wall_h:
		_wall_strip(_st(_walls, fmat), _arc_points(outer, a0, a1), t_fac, bh - _wall_h, _wall_h)
	# участок: асфальт вокруг и забор — дуга по краю открытой части и две радиальные отсечки
	_annulus(_st(_floors, "asphalt_02"), 0.0, 360.0, outer, site + 40.0, -0.03)
	var fence_h := float(_thick.get("site_fence_height", _fence_h))
	var t_fence := float(_thick.get("fence", _base_t))
	var fence := _st(_walls, _gb("concrete_block_wall_02", "gb_fence"))
	_wall_strip(fence, _arc_points(site, a0, a1), t_fence, fence_h)
	for a in [a0, a1]:
		_wall_strip(fence, PackedVector3Array([polar(a, outer), polar(a, site)]), t_fence, fence_h)


func _annulus(st: SurfaceTool, a0: float, a1: float, r0: float, r1: float, y: float) -> void:
	var n := maxi(1, int(ceil(deg_to_rad(a1 - a0) * r1 / (SEG_LEN * 2.0))))
	var lift := Vector3.UP * y
	for i in range(n):
		var aa := lerpf(a0, a1, float(i) / n)
		var ab := lerpf(a0, a1, float(i + 1) / n)
		var p00 := polar(aa, r0) + lift
		var p01 := polar(aa, r1) + lift
		var p10 := polar(ab, r0) + lift
		var p11 := polar(ab, r1) + lift
		_quad(st, p00, p10, p11, p01, Vector3.UP, _uv_xz(p00), _uv_xz(p10), _uv_xz(p11), _uv_xz(p01))


# ---------------------------------------------------------------- узлы

func _emit_meshes(root: Node3D) -> void:
	# Полы — с коллайдерами: по ним печётся навмеш (визуальные меши для этого не читаем — дорого).
	var floors := StaticBody3D.new()
	floors.name = "Floors"
	root.add_child(floors)
	for mat_id in _floors:
		var fi := _mesh_node(_floors[mat_id], String(mat_id), false)
		floors.add_child(fi)
		var fcs := CollisionShape3D.new()
		fcs.name = fi.name + "_col"
		fcs.shape = (fi.mesh as ArrayMesh).create_trimesh_shape()
		floors.add_child(fcs)
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
	_add_occluder(root, walls)
	for mat_id in _glass:
		var gi := _mesh_node(_glass[mat_id], String(mat_id), false)
		walls.add_child(gi)
		var gcs := CollisionShape3D.new()
		gcs.name = gi.name + "_col"
		gcs.shape = (gi.mesh as ArrayMesh).create_trimesh_shape()
		walls.add_child(gcs)
	var doors := Node3D.new()
	doors.name = "Doors"
	root.add_child(doors)
	for d in _doors:
		doors.add_child(d)
	var signs := Node3D.new()
	signs.name = "Signs"
	root.add_child(signs)
	for l in _labels:
		signs.add_child(l)


## Глухие стены — окклюдеры: что целиком за ними, не рисуется. Нужно в прицеле, где камера видит
## на сотни метров. Рамы, стекло, вывески и баннеры не закрывают обзор — их не берём.
func _add_occluder(root: Node3D, walls: Node3D) -> void:
	var meshes: Array[Mesh] = []
	for c in walls.get_children():
		var mi := c as MeshInstance3D
		if mi == null or String(mi.name) in ["steel_dark", "sign_panel"] or String(mi.name).begins_with("banner_"):
			continue
		meshes.append(mi.mesh)
	var oi := BlockoutMesh.make_occluder(meshes)
	if oi:
		root.add_child(oi)


func _mesh_node(st: SurfaceTool, mat_id: String, shadows: bool) -> MeshInstance3D:
	st.generate_tangents()
	var mesh := st.commit()
	var mi := MeshInstance3D.new()
	mi.name = mat_id
	mi.mesh = mesh
	# Всё, что не пол, растворяется у камеры, чтобы стена между камерой и игроком не закрывала обзор.
	mi.material_override = SectorMaterials.get_material(mat_id, shadows)
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
		# атриум освещён через купол; у большого кольца шаг реже — иначе сотни точечных огней
		if not _ring.is_empty() and String(room.get("type", "")) == "atrium":
			continue
		var step := 22.0 if outdoor else 11.0
		if not _ring.is_empty():
			step = 32.0 if outdoor else 15.0
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
					spot.shadow_enabled = _ring.is_empty()
					lights.add_child(spot)
				else:
					var omni := OmniLight3D.new()
					omni.position = pos + Vector3(0, minf(_wall_h - 1.0, 5.5), 0)
					omni.light_color = Color(0.82, 0.92, 0.88)
					omni.light_energy = 3.5
					omni.omni_range = 13.0
					omni.omni_attenuation = 1.4
					lights.add_child(omni)


## Пропсы по правилам помещений (см. PropPlacement). Сид — из id сектора: расстановка воспроизводима.
func _build_props(root: Node3D) -> void:
	var props := Node3D.new()
	props.name = "Props"
	root.add_child(props)
	var placement := PropPlacement.new()
	placement.place(props, _rooms, _openings, root.get_meta("spawn", Vector3.ZERO), hash(String(_def.get("id", ""))))
	root.set_meta("prop_count", placement.count)
	# меши пропсов склеиваются по клеткам — иначе каждая коробка на стеллаже отдельный вызов отрисовки
	root.set_meta("prop_batches", PropBatcher.batch(props, PROP_BATCH_CELL, PROP_VIS_END))


## Верхний слой: балки перекрытия поперёк помещений, вентиляционный короб вдоль коридора,
## баннеры на колоннаде атриума — то, что делает коробки зданием при взгляде сверху.
func _build_overhead() -> void:
	var steel := _st(_walls, "steel_dark")
	var duct := _st(_walls, "metal_plate")
	for room in _rooms:
		if bool(room.get("outdoor", false)) or bool(room.get("locked", false)):
			continue
		var a0 := float(room.a[0])
		var a1 := float(room.a[1])
		var r0 := float(room.r[0])
		var r1 := float(room.r[1])
		var t := String(room.get("type", ""))
		if t == "atrium":
			continue
		if t == "corridor":
			var rm := (r0 + r1) * 0.5
			_wall_strip(duct, _arc_points(rm, a0, a1), 0.7, 0.5, _wall_h - 1.5)
			continue
		var rm2 := (r0 + r1) * 0.5
		var len := deg_to_rad(a1 - a0) * rm2
		var n := int(floor(len / 4.0))
		for i in range(1, n + 1):
			var a := lerpf(a0, a1, float(i) / float(n + 1))
			_wall_strip(steel, PackedVector3Array([polar(a, r0 + 0.3), polar(a, r1 - 0.3)]), 0.25, 0.5, _wall_h - 0.6)
	# баннеры: на каждой второй колонне колоннады
	var banner_colors := [Color(0.12, 0.14, 0.36), Color(0.3, 0.12, 0.36), Color(0.45, 0.1, 0.1), Color(0.1, 0.25, 0.3)]
	var k := 0
	for op in _openings:
		if String(op.kind) != "open" or String(op.wall) != "arc":
			continue
		var r := float(op.r)
		var len := deg_to_rad(float(op.a[1]) - float(op.a[0])) * r
		var n := int(floor(len / float(_arch.column_spacing)))
		for i in range(1, n + 1, 2):
			var a := float(op.a[0]) + rad_to_deg(len * float(i) / float(n + 1) / r)
			var c: Color = banner_colors[k % banner_colors.size()]
			k += 1
			var st := _st(_walls, "banner_%d" % (k % banner_colors.size()))
			var half := rad_to_deg(0.6 / r)
			var pts := _arc_points(r + 0.45, a - half, a + half)
			_wall_strip(st, pts, 0.04, 3.2, _wall_h - float(_arch.cornice_h) * 2.0 - 3.4)


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
