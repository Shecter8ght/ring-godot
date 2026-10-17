@tool
extends Node3D
## Улицы черновика территории ТЦ (владелец, 2026-10-17: «дороги бедные, галерея — щиты на ножках»):
## крытая галерея автостанции (пол, стойки по краям, сплошная кровля по рельефу), разметка и «зебры»,
## бордюры, отбойники трассы и моста, площадки скругления перекрёстков, разметка мест на парковках,
## опоры проводов. Данные — streets в data/blockouts/mall_study.json (tools/mall_study_streets.py);
## знаки, фонари, светофоры и столбики — наборы наполнения (src/blockout/mall_filler.gd).

const Geometry = preload("res://src/blockout/study_geometry.gd")
const MallLandscape = preload("res://src/blockout/mall_landscape.gd")

## Шаг пролёта галереи, м: стойки по краям через столько.
const GALLERY_BAY: float = 6.0
## Высота подъёма разметки над землёй: дорога лежит на 0,06, разметка — чуть выше.
const MARK_LIFT: float = 0.075
const STALL_LIFT: float = 0.05

var landscape: MallLandscape
var generated: Node3D
var stats: Dictionary = {}


func _ready() -> void:
	landscape = get_node_or_null("../Landscape") as MallLandscape
	if landscape == null or landscape.plan.is_empty():
		return
	rebuild()


func rebuild() -> void:
	if is_instance_valid(generated):
		generated.free()
	generated = Node3D.new()
	generated.name = "_Streets"
	add_child(generated)
	var g: RefCounted = Geometry.new(generated, _palette())
	var streets: Dictionary = landscape.plan.get("streets", {}) as Dictionary
	for pad: Array in streets.get("pads", []):
		landscape.drape_disk(g, Vector2(float(pad[0]), float(pad[1])), float(pad[2]), "road", 0.058)
	for mark: Dictionary in streets.get("marks", []):
		_mark(g, mark)
	for curb: Array in streets.get("curbs", []):
		_curb(g, MallLandscape.poly(curb))
	for rail: Dictionary in streets.get("rails", []):
		if String(rail.kind) == "jersey":
			_jersey(g, MallLandscape.poly(rail.points))
		else:
			_wbeam(g, MallLandscape.poly(rail.points))
	for line: Array in streets.get("poles", []):
		_pole_line(g, MallLandscape.poly(line))
	_gallery(g)
	_stalls(g)
	for gas: Array in (landscape.plan.get("filler", {}) as Dictionary).get("gas", []):
		_gas_pipe(g, MallLandscape.poly(gas))
	g.finish()
	stats = {"triangles": g.triangles, "collision_shapes": (g.body as StaticBody3D).get_child_count()}
	set_meta("stats", stats)


func _palette() -> Dictionary:
	var result: Dictionary = Geometry.materials()
	var extra: Dictionary = {"plaza": Color("a49c86"), "metal": Color("9ea2a0"), "timber": Color("5f4c38"),
		"curb": Color("97978c"), "paint": Color("c9c7b6"), "gas": Color("d2ad2c")}
	for key: String in extra:
		var material: StandardMaterial3D = StandardMaterial3D.new()
		material.albedo_color = extra[key]
		material.roughness = 0.9
		result[key] = material
	return result


# ---------------------------------------------------------------- разметка, бордюры, отбойники

## Линия разметки по земле; dash — [штрих, разрыв], м.
func _mark(g: RefCounted, mark: Dictionary) -> void:
	var line: PackedVector2Array = MallLandscape.poly(mark.points)
	var width: float = float(mark.width)
	var dash: Variant = mark.get("dash")
	if dash == null:
		landscape.drape_strip(g, line, width, "paint", MARK_LIFT)
		return
	var on: float = float((dash as Array)[0])
	var off: float = float((dash as Array)[1])
	var total: float = _length(line)
	var s: float = 0.0
	while s < total:
		var piece: PackedVector2Array = _sub_line(line, s, minf(total, s + on))
		if piece.size() > 1:
			landscape.drape_strip(g, piece, width, "paint", MARK_LIFT)
		s += on + off


## Бордюрный камень вдоль края дороги: 0,25 × 0,2 м, по земле кусками между точками.
func _curb(g: RefCounted, line: PackedVector2Array) -> void:
	for i: int in range(line.size() - 1):
		var a: Vector3 = Vector3(line[i].x, landscape.ground(line[i].x, line[i].y) + 0.1, line[i].y)
		var b: Vector3 = Vector3(line[i + 1].x, landscape.ground(line[i + 1].x, line[i + 1].y) + 0.1, line[i + 1].y)
		g.beam(a, b, 0.25, 0.2, "curb")


## Металлический отбойник: стойки через 2 м, волна на 0,6 м; коллизия кусками по 4 м.
func _wbeam(g: RefCounted, line: PackedVector2Array) -> void:
	for p: Vector2 in _resample(line, 2.0):
		g.box(Vector3(p.x, landscape.ground(p.x, p.y) + 0.38, p.y), Vector3(0.12, 0.76, 0.09), "steel", false)
	var pts: PackedVector2Array = _resample(line, 4.0)
	for i: int in range(pts.size() - 1):
		var a: Vector3 = Vector3(pts[i].x, landscape.ground(pts[i].x, pts[i].y) + 0.6, pts[i].y)
		var b: Vector3 = Vector3(pts[i + 1].x, landscape.ground(pts[i + 1].x, pts[i + 1].y) + 0.6, pts[i + 1].y)
		g.beam(a, b, 0.05, 0.32, "metal", true)


## Бетонный разделитель «Нью-Джерси» посередине трассы.
func _jersey(g: RefCounted, line: PackedVector2Array) -> void:
	var pts: PackedVector2Array = _resample(line, 3.0)
	for i: int in range(pts.size() - 1):
		var a: Vector3 = Vector3(pts[i].x, landscape.ground(pts[i].x, pts[i].y) + 0.45, pts[i].y)
		var b: Vector3 = Vector3(pts[i + 1].x, landscape.ground(pts[i + 1].x, pts[i + 1].y) + 0.45, pts[i + 1].y)
		g.beam(a, b, 0.45, 0.9, "concrete", true)
		g.beam(a - Vector3.UP * 0.35, b - Vector3.UP * 0.35, 0.65, 0.2, "concrete")


## Опоры проводов 0,4/10 кВ: деревянная стойка 9 м, траверса, три провода с провисом к соседней опоре.
func _pole_line(g: RefCounted, line: PackedVector2Array) -> void:
	var mounts: Array = []
	for i: int in range(line.size()):
		var p: Vector2 = line[i]
		var dir: Vector2 = (line[mini(i + 1, line.size() - 1)] - line[maxi(i - 1, 0)]).normalized()
		var across: Vector2 = Vector2(-dir.y, dir.x)
		var y: float = landscape.ground(p.x, p.y)
		g.box(Vector3(p.x, y + 4.5, p.y), Vector3(0.26, 9.0, 0.26), "timber", true)
		g.box(Vector3(p.x, y + 8.55, p.y), Vector3(2.2, 0.12, 0.12), "timber", false, -atan2(across.y, across.x))
		var points: Array[Vector3] = []
		for k: float in [-0.9, 0.0, 0.9]:
			var at: Vector3 = Vector3(p.x + across.x * k, y + 8.7 + (0.25 if k == 0.0 else 0.0), p.y + across.y * k)
			g.box(at + Vector3.DOWN * 0.08, Vector3(0.08, 0.18, 0.08), "concrete", false)
			points.append(at)
		mounts.append(points)
	for i: int in range(mounts.size() - 1):
		for k: int in range(3):
			var a: Vector3 = (mounts[i] as Array)[k]
			var b: Vector3 = (mounts[i + 1] as Array)[k]
			_wire(g, a, b, a.distance_to(b) / 60.0)


func _wire(g: RefCounted, a: Vector3, b: Vector3, sag: float) -> void:
	var previous: Vector3 = a
	for i: int in range(1, 9):
		var t: float = float(i) / 8.0
		var p: Vector3 = a.lerp(b, t) - Vector3.UP * sag * 4.0 * t * (1.0 - t)
		g.beam(previous, p, 0.03, 0.03, "dark")
		previous = p


# ---------------------------------------------------------------- газовые трубы

## Высота газовой трубы над землёй: под ней проходят в рост; над дорогой — П-образный подъём.
const GAS_LOW: float = 2.2
const GAS_HIGH: float = 5.4

## Жёлтая газовая труба на стойках через 6 м; над дорогой поднимается П-образно (стояки по краям).
func _gas_pipe(g: RefCounted, line: PackedVector2Array) -> void:
	var pts: PackedVector2Array = _resample(line, 0.5)
	var high: Array[bool] = []
	for p: Vector2 in pts:
		high.append(_near_road(p, 2.0))
	# подъём чуть шире дороги: по метру с каждой стороны
	var widened: Array[bool] = high.duplicate()
	for i: int in range(pts.size()):
		for k: int in range(maxi(0, i - 2), mini(pts.size(), i + 3)):
			widened[i] = widened[i] or high[k]
	var run_start: int = 0
	for i: int in range(1, pts.size() + 1):
		if i < pts.size() and widened[i] == widened[run_start]:
			continue
		var h: float = GAS_HIGH if widened[run_start] else GAS_LOW
		var step: int = 6
		var k: int = run_start
		while k < i - 1:
			var n: int = mini(k + step, i - 1)
			var a: Vector3 = Vector3(pts[k].x, landscape.ground(pts[k].x, pts[k].y) + h, pts[k].y)
			var b: Vector3 = Vector3(pts[n].x, landscape.ground(pts[n].x, pts[n].y) + h, pts[n].y)
			g.beam(a, b, 0.16, 0.16, "gas", true)
			k = n
		# стойки через 6 м на низких участках; стояки на концах подъёма
		if not widened[run_start]:
			var s: int = run_start
			while s < i:
				var p: Vector2 = pts[s]
				var y: float = landscape.ground(p.x, p.y)
				g.box(Vector3(p.x, y + h * 0.5 - 0.05, p.y), Vector3(0.08, h - 0.1, 0.08), "steel", false)
				s += 12
		else:
			for e: int in [run_start, i - 1]:
				var p: Vector2 = pts[e]
				var y: float = landscape.ground(p.x, p.y)
				g.box(Vector3(p.x, y + (GAS_LOW + GAS_HIGH) * 0.5, p.y), Vector3(0.16, GAS_HIGH - GAS_LOW + 0.16, 0.16), "gas", true)
				g.box(Vector3(p.x, y + GAS_HIGH * 0.5, p.y), Vector3(0.1, GAS_HIGH, 0.1), "steel", false)
		run_start = i


func _near_road(p: Vector2, margin: float) -> bool:
	var plan: Dictionary = landscape.plan
	for road: Dictionary in plan.roads:
		if String(road.id) == "loop":
			if absf(p.length() - float((plan.mall as Dictionary).loop_r)) < float(road.width) * 0.5 + margin:
				return true
		elif MallLandscape.line_distance(p, MallLandscape.poly(road.points)) < float(road.width) * 0.5 + margin:
			return true
	return false


# ---------------------------------------------------------------- галерея автостанции

## Крытая галерея: мощёный пол, стойки по обоим краям через пролёт, сплошная кровля с бортом по рельефу.
## На уступе (лестница через стенку террас) пролёт без кровли и стоек — там марш.
func _gallery(g: RefCounted) -> void:
	var gallery: Dictionary = landscape.plan.get("gallery", {}) as Dictionary
	if gallery.is_empty():
		return
	var width: float = float(gallery.width)
	var h: float = float(gallery.height)
	for part: Array in gallery.parts:
		var line: PackedVector2Array = MallLandscape.poly(part)
		landscape.drape_strip(g, line, width, "plaza", 0.065)
		for i: int in range(line.size() - 1):
			var a: Vector2 = line[i]
			var b: Vector2 = line[i + 1]
			var count: int = maxi(1, ceili(a.distance_to(b) / GALLERY_BAY))
			var dir: Vector2 = (b - a).normalized()
			var across: Vector2 = Vector2(-dir.y, dir.x)
			for k: int in range(count):
				var p0: Vector2 = a.lerp(b, float(k) / float(count))
				var p1: Vector2 = a.lerp(b, float(k + 1) / float(count))
				var y0: float = _floor_y(p0, across, width)
				var y1: float = _floor_y(p1, across, width)
				if absf(y0 - y1) > 0.8 or _step_between(p0, p1):
					continue
				var r0: Vector3 = Vector3(p0.x, y0 + h, p0.y)
				var r1: Vector3 = Vector3(p1.x, y1 + h, p1.y)
				g.beam(r0, r1, width + 0.7, 0.2, "slab", true)
				for side: float in [-1.0, 1.0]:
					var o: Vector3 = Vector3(across.x, 0.0, across.y) * side * (width * 0.5 + 0.3)
					g.beam(r0 + o - Vector3.UP * 0.22, r1 + o - Vector3.UP * 0.22, 0.1, 0.42, "accent")
					# стойки — в начале пролёта и в конце последнего
					for q: Vector2 in ([p0, p1] if k == count - 1 else [p0]):
						var yq: float = _floor_y(q, across, width)
						var post: Vector2 = q + across * side * (width * 0.5 - 0.15)
						g.box(Vector3(post.x, yq + h * 0.5, post.y), Vector3(0.2, h, 0.2), "steel", true)


## Высота пола галереи в точке — по высшей кромке (стойки не висят над откосом).
func _floor_y(p: Vector2, across: Vector2, width: float) -> float:
	var y: float = landscape.ground(p.x, p.y)
	for side: float in [-1.0, 1.0]:
		var q: Vector2 = p + across * side * width * 0.5
		y = maxf(y, landscape.ground(q.x, q.y))
	return y


## Есть ли между точками уступ (стенка террас): земля посередине уходит от прямой больше чем на 0,5 м.
func _step_between(a: Vector2, b: Vector2) -> bool:
	var ya: float = landscape.ground(a.x, a.y)
	var yb: float = landscape.ground(b.x, b.y)
	for t: float in [0.25, 0.5, 0.75]:
		var m: Vector2 = a.lerp(b, t)
		if absf(landscape.ground(m.x, m.y) - lerpf(ya, yb, t)) > 0.5:
			return true
	return false


# ---------------------------------------------------------------- парковки

## Разметка мест: радиальные линии между местами в рядах брошенных машин (как ставит MallLandscape),
## у стенок террас, пандусов, въездов, аллеи и галереи — нет.
func _stalls(g: RefCounted) -> void:
	for p: Dictionary in landscape.plan.parkings:
		var a: Array = (p.rows as Dictionary).a
		var r: Array = p.r
		var span: float = fposmod(float(a[1]) - float(a[0]), 360.0)
		var rad: float = float(r[0]) + 6.0
		while rad < float(r[1]) - 4.0:
			var count: int = int(deg_to_rad(span) * rad / 3.0)
			for i: int in range(count + 1):
				var ang: float = float(a[0]) + span * float(i) / float(count)
				var mid: Vector2 = MallLandscape.polar(ang, rad)
				if landscape.parking_spot_blocked(mid, ang, rad):
					continue
				var line: PackedVector2Array = PackedVector2Array([MallLandscape.polar(ang, rad - 2.6), MallLandscape.polar(ang, rad + 2.6)])
				landscape.drape_strip(g, line, 0.12, "paint", STALL_LIFT)
			rad += 16.0


# ---------------------------------------------------------------- ломаные

func _length(line: PackedVector2Array) -> float:
	var total: float = 0.0
	for i: int in range(line.size() - 1):
		total += line[i].distance_to(line[i + 1])
	return total


func _point_at(line: PackedVector2Array, s: float) -> Vector2:
	for i: int in range(line.size() - 1):
		var d: float = line[i].distance_to(line[i + 1])
		if s <= d or i == line.size() - 2:
			return line[i].lerp(line[i + 1], clampf(s / maxf(d, 0.001), 0.0, 1.0))
		s -= d
	return line[line.size() - 1]


## Кусок ломаной от s0 до s1 (с вершинами между ними).
func _sub_line(line: PackedVector2Array, s0: float, s1: float) -> PackedVector2Array:
	var out: PackedVector2Array = PackedVector2Array([_point_at(line, s0)])
	var walked: float = 0.0
	for i: int in range(line.size() - 1):
		walked += line[i].distance_to(line[i + 1])
		if walked > s0 and walked < s1:
			out.append(line[i + 1])
	out.append(_point_at(line, s1))
	return out


## Точки ломаной через step (концы — точно).
func _resample(line: PackedVector2Array, step: float) -> PackedVector2Array:
	var total: float = _length(line)
	var count: int = maxi(1, ceili(total / step))
	var out: PackedVector2Array = PackedVector2Array()
	for k: int in range(count + 1):
		out.append(_point_at(line, total * float(k) / float(count)))
	return out
