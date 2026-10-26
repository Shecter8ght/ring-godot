extends Control
## Только рисунок поверх живого осмотра. Ввод принимает HandGripInspector.

var tips: Dictionary = {}
var chain: PackedVector2Array = []
var selected: String = ""
var target: Vector2 = Vector2.INF


func _draw() -> void:
	if chain.size() > 1:
		draw_polyline(chain, Color(0.3, 0.95, 0.9, 0.7), 2.0, true)
	for finger: String in tips:
		var point: Vector2 = tips[finger] as Vector2
		var color: Color = Color(1.0, 0.78, 0.25) if finger == selected else Color(0.25, 0.9, 1.0)
		draw_circle(point, 8.0, Color(0.03, 0.04, 0.05, 0.85))
		draw_arc(point, 7.0, 0.0, TAU, 24, color, 2.0, true)
		draw_circle(point, 2.0, color)
	if target.is_finite():
		draw_line(target - Vector2(9, 0), target + Vector2(9, 0), Color(1.0, 0.45, 0.25), 2.0)
		draw_line(target - Vector2(0, 9), target + Vector2(0, 9), Color(1.0, 0.45, 0.25), 2.0)
