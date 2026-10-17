extends Control
## План черновика ТЦ (M): граница, лес, дороги, парковки, площадь, двор, сквер, водоём, постройки,
## места, появления и выходы, положение пешехода. Как на согласованной схеме, север вверху.

const MallLandscape = preload("res://src/blockout/mall_landscape.gd")

var plan: Dictionary = {}
var walker: Node3D
var font: Font
var _extent: Rect2 = Rect2(-470, -400, 930, 800)


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
	draw_string(font, Vector2(rect.position.x, rect.end.y + 28), "M — закрыть · 1–9, 0 — места 1–10 · N / B — следующее / прошлое место · синие — появление, зелёные — выход, жёлтые — по условию", HORIZONTAL_ALIGNMENT_LEFT, -1, 15, Color("c0c9bd"))
	var a: Vector2 = rect.end + Vector2(-100.0 * k, 12)
	draw_line(a, rect.end + Vector2(0, 12), Color("c0c9bd"), 2)
	draw_string(font, a + Vector2(0, 30), "100 м", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color("c0c9bd"))
