extends Control
## План черновика ТЦ (M): граница, лес, дороги, парковки, площадь, двор, сквер, водоём, постройки,
## места, появления и выходы, положение пешехода, наполнение (укрытия, ЛЭП, теплотрасса, истории).
## Как на согласованной схеме, север вверху.

const MallLandscape = preload("res://src/blockout/mall_landscape.gd")

var plan: Dictionary = {}
var walker: Node3D
var font: Font
var _extent: Rect2 = Rect2(-470, -400, 930, 800)
## Пятна крупных наборов наполнения на плане (ширина × длина, м); остальное — точкой.
const FOOTPRINTS: Dictionary = {"car": Vector2(1.9, 4.6), "truck": Vector2(2.5, 7.2), "truck_cab": Vector2(2.5, 6.0),
	"trailer": Vector2(2.5, 13.0), "bus_wreck": Vector2(2.6, 12.0), "container40": Vector2(2.4, 12.2),
	"container20": Vector2(2.4, 6.1), "garage": Vector2(3.2, 6.0), "garage_open": Vector2(3.2, 6.0),
	"cabin": Vector2(2.4, 6.0), "slab": Vector2(2.0, 6.0), "pipes": Vector2(3.2, 8.0), "fence": Vector2(0.3, 3.0),
	"billboard": Vector2(12.0, 0.8), "billboard_fallen": Vector2(12.0, 4.0), "bus_stop": Vector2(6.0, 2.0)}


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	font = ThemeDB.fallback_font


func map_point(p: Vector2, rect: Rect2) -> Vector2:
	return rect.position + (p - _extent.position) / _extent.size * rect.size


func points(source: Array, rect: Rect2) -> PackedVector2Array:
	var result: PackedVector2Array = PackedVector2Array()
	for p: Array in source:
		result.append(map_point(Vector2(float(p[0]), float(p[1])), rect))
	return result


func _wedge(rect: Rect2, a0: float, a1: float, r0: float, r1: float, color: Color) -> void:
	var span: float = fposmod(a1 - a0, 360.0)
	if span < 0.01:
		span = 360.0
	var n: int = maxi(4, int(span / 3.0))
	var pts: PackedVector2Array = PackedVector2Array()
	for i: int in range(n + 1):
		pts.append(map_point(MallLandscape.polar(a0 + span * float(i) / float(n), r1), rect))
	for i: int in range(n, -1, -1):
		pts.append(map_point(MallLandscape.polar(a0 + span * float(i) / float(n), r0), rect))
	draw_colored_polygon(pts, color)


func _draw() -> void:
	if plan.is_empty():
		return
	var bounds: Array = plan.bounds
	_extent = Rect2(float(bounds[0]), float(bounds[1]), float(bounds[2]) - float(bounds[0]), float(bounds[3]) - float(bounds[1]))
	draw_rect(Rect2(Vector2.ZERO, size), Color(0.035, 0.05, 0.05, 0.96))
	var h: float = minf(size.y * 0.84, size.x * 0.8 * _extent.size.y / _extent.size.x)
	var w: float = h * _extent.size.x / _extent.size.y
	var rect: Rect2 = Rect2((size - Vector2(w, h)) * 0.5, Vector2(w, h))
	var k: float = rect.size.x / _extent.size.x
	draw_colored_polygon(points(plan.boundary, rect), Color("3d4a39"))
	for f: Array in plan.forest:
		draw_colored_polygon(points(f, rect), Color("2f4a2f"))
	for p: Dictionary in plan.parkings:
		_wedge(rect, float(p.a[0]), float(p.a[1]), float(p.r[0]), float(p.r[1]), Color("555a55"))
	var sq: Dictionary = plan.square
	_wedge(rect, float(sq.a[0]), float(sq.a[1]), float(sq.r[0]), float(sq.r[1]), Color("4c6447"))
	var pl: Dictionary = plan.plaza
	_wedge(rect, float(pl.a[0]), float(pl.a[1]), float(pl.r[0]), float(pl.r[1]), Color("8f8670"))
	var y: Dictionary = plan.yard
	_wedge(rect, float(y.a[0]), float(y.a[1]), float(y.r[0]), float(y.r[1]), Color("6e6a5c"))
	for road: Dictionary in plan.roads:
		draw_polyline(points(road.points, rect), Color("8b8e7d"), maxf(1.5, float(road.width) * k), true)
	var hw: Dictionary = plan.highway
	draw_line(map_point(Vector2(float(hw.x[0]), float(hw.z)), rect), map_point(Vector2(float(hw.x[1]), float(hw.z)), rect), Color("777a70"), float(hw.width) * k)
	var pond: Dictionary = plan.pond
	draw_circle(map_point(Vector2(float(pond.at[0]), float(pond.at[1])), rect), float(pond.size[1]) * 0.5 * k, Color("4a6970"))
	var mall: Dictionary = plan.mall
	draw_circle(map_point(Vector2.ZERO, rect), float(mall.r) * k, Color("b9ae95"))
	draw_circle(map_point(Vector2.ZERO, rect), 30.0 * k, Color("a5bcc4"))
	for b: Dictionary in plan.buildings:
		var c: Array = b.at
		var span: Array = b.size
		var center: Vector2 = Vector2(float(c[0]), float(c[1]))
		var half: Vector2 = Vector2(float(span[0]), float(span[1])) * 0.5
		var polygon: PackedVector2Array = PackedVector2Array()
		for local: Vector2 in [Vector2(-half.x, -half.y), Vector2(half.x, -half.y), half, Vector2(-half.x, half.y)]:
			polygon.append(map_point(center + local.rotated(-deg_to_rad(float(b.yaw))), rect))
		draw_colored_polygon(polygon, Color("c1bca8") if String(b.kind) in ["hall", "skeleton"] else Color("7d837b"))
	_draw_relief(plan.get("relief", {}) as Dictionary, rect, k)
	_draw_filler(plan.get("filler", {}) as Dictionary, rect, k)
	for s: Dictionary in plan.spawns:
		draw_circle(map_point(Vector2(float(s.at[0]), float(s.at[1])), rect), 6.0, Color("3d6fb5"))
	for e: Dictionary in plan.exits:
		var at: Vector2 = map_point(Vector2(float(e.at[0]), float(e.at[1])), rect)
		draw_colored_polygon(PackedVector2Array([at + Vector2(0, -8), at + Vector2(7, 5), at + Vector2(-7, 5)]), Color("3c9b5a") if bool(e.always) else Color("c48a2c"))
	for loc: Dictionary in plan.locations:
		var at: Vector2 = map_point(Vector2(float(loc.at[0]), float(loc.at[1])), rect)
		draw_circle(at, 11.0, Color("172624"))
		draw_string(font, at + Vector2(-6 if int(loc.id) < 10 else -10, 6), str(int(loc.id)), HORIZONTAL_ALIGNMENT_LEFT, -1, 15, Color("e3e6d4"))
	if is_instance_valid(walker):
		var at: Vector2 = map_point(Vector2(walker.global_position.x, walker.global_position.z), rect)
		var arrow: PackedVector2Array = PackedVector2Array()
		for local: Vector2 in [Vector2(0, -11), Vector2(6, 7), Vector2(-6, 7)]:
			arrow.append(at + local.rotated(-walker.rotation.y))
		draw_colored_polygon(arrow, Color.WHITE)
	draw_string(font, Vector2(rect.position.x, rect.position.y - 20), "ТЦ «РИНГ» · ТЕРРИТОРИЯ · ЧЕРНОВИК 1:1 · СЕВЕР ↑", HORIZONTAL_ALIGNMENT_LEFT, -1, 20, Color("e3e6d4"))
	draw_string(font, Vector2(rect.position.x, rect.end.y + 28), "M — закрыть · 1–9, 0 — места 1–10 · N / B — места · синие — появление, зелёные — выход, жёлтые — по условию · ◆ — история · оранжевая — теплотрасса · пунктир — ЛЭП · синяя — речка · зубцы — утёс", HORIZONTAL_ALIGNMENT_LEFT, -1, 15, Color("c0c9bd"))
	var a: Vector2 = rect.end + Vector2(-100.0 * k, 12)
	draw_line(a, rect.end + Vector2(0, 12), Color("c0c9bd"), 2)
	draw_string(font, a + Vector2(0, 30), "100 м", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color("c0c9bd"))


## Рельеф: горки (кольца), утёсы (кромка с зубцами вниз), речка с мостами и бродом.
func _draw_relief(relief: Dictionary, rect: Rect2, k: float) -> void:
	if relief.is_empty():
		return
	for hill: Array in relief.get("hills", []):
		var c: Vector2 = map_point(Vector2(float(hill[0]), float(hill[1])), rect)
		for ring: float in [1.0, 0.66, 0.33]:
			draw_arc(c, float(hill[2]) * ring * k, 0.0, TAU, 32, Color(0.75, 0.7, 0.55, 0.35 + 0.15 * (1.0 - ring)), 1.0)
	var river: Dictionary = relief.get("river", {}) as Dictionary
	if river.has("points"):
		draw_polyline(points(river.points, rect), Color("4f7f95"), maxf(2.0, 12.0 * k))
		for bridge: Dictionary in river.bridges:
			var at: Vector2 = map_point(Vector2(float(bridge.at[0]), float(bridge.at[1])), rect)
			draw_rect(Rect2(at - Vector2(5, 3), Vector2(10, 6)), Color("c9c2ac"))
		for ford: Dictionary in river.fords:
			draw_circle(map_point(Vector2(float(ford.at[0]), float(ford.at[1])), rect), 4.0, Color("8fb3c0"))
	for cliff: Dictionary in relief.get("cliffs", []):
		var edge: PackedVector2Array = points(cliff.points, rect)
		draw_polyline(edge, Color("2e2a25"), 3.0)
		for i: int in range(edge.size() - 1):
			var dir: Vector2 = (edge[i + 1] - edge[i]).normalized()
			# зубцы — к низу утёса
			var down: Vector2 = Vector2(-dir.y, dir.x) * -float(cliff.side) * 6.0
			for t: float in [0.2, 0.4, 0.6, 0.8]:
				var q: Vector2 = edge[i].lerp(edge[i + 1], t)
				draw_line(q, q + down, Color("2e2a25"), 1.5)


## Наполнение: колея, кювет, котлован, отвалы, воронка, теплотрасса, ЛЭП, укрытия и кусты, истории.
func _draw_filler(filler: Dictionary, rect: Rect2, k: float) -> void:
	if filler.is_empty():
		return
	var earth: Dictionary = filler.get("earth", {}) as Dictionary
	for ditch: Dictionary in earth.get("ditches", []):
		draw_polyline(points(ditch.points, rect), Color("4d6a6f"), maxf(1.0, float(ditch.width) * k * 0.6))
	for pit: Array in earth.get("pits", []):
		var half: Vector2 = Vector2(float(pit[2]), float(pit[3])) * 0.5
		var c: Vector2 = Vector2(float(pit[0]), float(pit[1]))
		draw_rect(Rect2(map_point(c - half, rect), half * 2.0 * k), Color("5f5140"))
	for m: Array in earth.get("mounds", []):
		draw_circle(map_point(Vector2(float(m[0]), float(m[1])), rect), maxf(float(m[2]), float(m[3])) * k, Color("6b5a43"))
	for c: Array in earth.get("craters", []):
		draw_circle(map_point(Vector2(float(c[0]), float(c[1])), rect), float(c[2]) * k, Color("2c2722"))
	var lines: Dictionary = filler.get("lines", {}) as Dictionary
	for rut: Array in lines.get("ruts", []):
		draw_polyline(points(rut, rect), Color("6a5a43"), 1.0)
	var heat: Dictionary = lines.get("heat", {}) as Dictionary
	if heat.has("points"):
		draw_polyline(points(heat.points, rect), Color("d97a2b"), 3.0)
	var power: Dictionary = lines.get("power", {}) as Dictionary
	var towers: PackedVector2Array = points(power.get("towers", []), rect)
	for i: int in range(towers.size() - 1):
		draw_dashed_line(towers[i], towers[i + 1], Color("c9cbbf"), 1.5, 6.0)
	for t: Vector2 in towers:
		draw_rect(Rect2(t - Vector2(3, 3), Vector2(6, 6)), Color("c9cbbf"))
	for item: Array in filler.get("items", []):
		var kit: String = String(item[0])
		var at: Vector2 = map_point(Vector2(float(item[1]), float(item[2])), rect)
		if kit in ["bush", "sapling"]:
			draw_circle(at, 1.1, Color("587a45"))
		elif kit in ["puddle", "find", "suitcase", "log", "fire_ring", "cart"]:
			continue
		elif FOOTPRINTS.has(kit):
			var span: Vector2 = FOOTPRINTS[kit] * k * 0.5
			var yaw: float = deg_to_rad(float(item[3]))
			var poly: PackedVector2Array = PackedVector2Array()
			for local: Vector2 in [Vector2(-span.x, -span.y), Vector2(span.x, -span.y), span, Vector2(-span.x, span.y)]:
				# локальная Z набора → вдоль поворота yaw (как Basis(UP, yaw) в мире)
				poly.append(at + Vector2(local.x * cos(yaw) + local.y * sin(yaw), -local.x * sin(yaw) + local.y * cos(yaw)))
			draw_colored_polygon(poly, Color("a8a594") if kit != "fence" else Color("8fa3a8"))
		else:
			draw_rect(Rect2(at - Vector2(1.5, 1.5), Vector2(3, 3)), Color("a8a594"))
	for story: Dictionary in filler.get("stories", []):
		var at: Vector2 = map_point(Vector2(float(story.at[0]), float(story.at[1])), rect)
		draw_colored_polygon(PackedVector2Array([at + Vector2(0, -6), at + Vector2(5, 0), at + Vector2(0, 6), at + Vector2(-5, 0)]), Color("f0c27a"))
		draw_string(font, at + Vector2(8, 4), String(story.label), HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color("f0d9b0"))
