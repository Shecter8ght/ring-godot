extends Control
## План исследования показывает положение пешехода, но не вводит игровые выходы.

var plan: Dictionary = {}
var walker: Node3D
var font: Font

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	font = ThemeDB.fallback_font

func map_point(p: Vector2, rect: Rect2) -> Vector2:
	return rect.position + (p - Vector2(-350, -330)) / Vector2(700, 660) * rect.size

func points(source: Array, rect: Rect2) -> PackedVector2Array:
	var result: PackedVector2Array = PackedVector2Array()
	for p: Array in source:
		result.append(map_point(Vector2(float(p[0]), float(p[1])), rect))
	return result

func _draw() -> void:
	if plan.is_empty():
		return
	draw_rect(Rect2(Vector2.ZERO, size), Color(0.035, 0.05, 0.05, 0.96))
	var extent: float = minf(size.x * 0.68, size.y * 0.80)
	var rect: Rect2 = Rect2((size - Vector2(extent * 700.0 / 660.0, extent)) * 0.5, Vector2(extent * 700.0 / 660.0, extent))
	draw_colored_polygon(points(plan.boundary, rect), Color("364537"))
	draw_colored_polygon(points(plan.swamp, rect), Color("4a6970"))
	for road: Dictionary in plan.roads:
		draw_polyline(points(road.points, rect), Color("8b8e7d"), maxf(1.5, float(road.width) * rect.size.x / 700.0), true)
	for ridge: Array in plan.dry_ridges:
		draw_polyline(points(ridge, rect), Color("869574"), 3.0, true)
	draw_polyline(points(plan.tracks, rect), Color("afa28a"), 3.0, true)
	for b: Dictionary in plan.buildings:
		var p: Array = b.at
		var span: Array = b.size
		var center: Vector2 = Vector2(float(p[0]), float(p[1]))
		var half: Vector2 = Vector2(float(span[0]), float(span[1])) * 0.5
		var polygon: PackedVector2Array = PackedVector2Array()
		for local: Vector2 in [Vector2(-half.x, -half.y), Vector2(half.x, -half.y), half, Vector2(-half.x, half.y)]:
			polygon.append(map_point(center + local.rotated(-deg_to_rad(float(b.yaw))), rect))
		draw_colored_polygon(polygon, Color("c1bca8") if String(b.kind) in ["hall", "apartments", "skeleton"] else Color("7d837b"))
	for loc: Dictionary in plan.locations:
		var p: Array = loc.at
		var at: Vector2 = map_point(Vector2(float(p[0]), float(p[1])), rect)
		draw_circle(at, 13.0, Color("172624"))
		draw_string(font, at + Vector2(-5, 6), str(int(loc.id)), HORIZONTAL_ALIGNMENT_LEFT, -1, 17, Color("e3e6d4"))
		draw_string(font, at + Vector2(18, 5), String(loc.label), HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color("e3e6d4"))
	for exit: Dictionary in plan.exits:
		var p: Array = exit.at
		var at: Vector2 = map_point(Vector2(float(p[0]), float(p[1])), rect)
		draw_rect(Rect2(at - Vector2(4, 4), Vector2(8, 8)), Color("9fbd9d"))
	if is_instance_valid(walker):
		var at: Vector2 = map_point(Vector2(walker.global_position.x, walker.global_position.z), rect)
		var arrow: PackedVector2Array = PackedVector2Array()
		for local: Vector2 in [Vector2(0, -11), Vector2(6, 7), Vector2(-6, 7)]:
			arrow.append(at + local.rotated(-walker.rotation.y))
		draw_colored_polygon(arrow, Color.WHITE)
	draw_string(font, Vector2(rect.position.x, rect.position.y - 20), "ГОРОДСКОЙ ПОЯС · БЛОКАУТ 1:1 · СЕВЕР ↑", HORIZONTAL_ALIGNMENT_LEFT, -1, 20, Color("e3e6d4"))
	draw_string(font, Vector2(rect.position.x, rect.end.y + 30), "M — закрыть   ·   1–6 — перейти к месту   ·   светлые здания доступны", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color("c0c9bd"))
	var a: Vector2 = rect.end + Vector2(-100 * rect.size.x / 700.0, 14)
	draw_line(a, rect.end + Vector2(0,14), Color("c0c9bd"), 2)
	draw_string(font, a + Vector2(0, 35), "100 м", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color("c0c9bd"))
