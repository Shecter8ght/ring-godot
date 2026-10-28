extends Control
## Срез текущего этажа; план следует за пешеходом и не вводит игровые выходы.

var plan: Dictionary = {}
var walker: CharacterBody3D


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func _draw() -> void:
	if plan.is_empty() or not is_instance_valid(walker):
		return
	var floor_index: int = 0
	var levels: Array = plan.scale.floor_y
	for i: int in range(3):
		if walker.position.y >= float(levels[i]) - 0.2:
			floor_index = i
	var floor_y: float = float(levels[floor_index])
	var extent: Vector2 = Vector2(53.0, 55.0)
	var k: float = minf((size.x - 120.0) / extent.x, (size.y - 180.0) / extent.y)
	var origin: Vector2 = (size - extent * k) * 0.5
	var base: Vector2 = Vector2(-10.0, -42.0)
	draw_rect(Rect2(Vector2.ZERO, size), Color(0.05, 0.065, 0.08, 0.97))
	for space: Dictionary in plan.spaces:
		if int(space.floor) != floor_index + 1 or not bool(space.open):
			continue
		var r: Array = space.rect
		var a: Vector2 = origin + (Vector2(float(r[0]),float(r[1]))-base)*k
		var span: Vector2 = Vector2(float(r[2])-float(r[0]),float(r[3])-float(r[1]))*k
		if space.has("polygon"):
			var polygon: PackedVector2Array = PackedVector2Array()
			for at: Array in space.polygon:
				polygon.append(origin+(Vector2(float(at[0]),float(at[1]))-base)*k)
			draw_colored_polygon(polygon,Color("405d65"))
		else:
			draw_rect(Rect2(a,span), Color("5c6870") if String(space.kind)=="room" else Color("405d65"))
		draw_string(ThemeDB.fallback_font,a+Vector2(5,span.y*0.5),String(space.label),HORIZONTAL_ALIGNMENT_LEFT,-1,14,Color("ecf0eb"))
	var sections: Dictionary = plan.sections
	for key: String in ["Floor%d" % (floor_index+1), "WestStair", "EastStair", "NorthAnnex"]:
		var section: Dictionary = sections[key]
		for item: Dictionary in section.boxes:
			var at: Array = item.at
			var span: Array = item.size
			if absf(float(at[1])-floor_y-1.4)>float(span[1])*0.5 or String(item.mat)=="glass":
				continue
			var xz: Vector2 = Vector2(float(at[0]),float(at[2]))
			var dimensions: Vector2 = Vector2(float(span[0]),float(span[2]))
			draw_rect(Rect2(origin+(xz-dimensions*0.5-base)*k,dimensions*k),Color("c8cbc8"))
	var p: Vector2 = origin+(Vector2(walker.position.x,walker.position.z)-base)*k
	draw_circle(p,6,Color("e9bd64"))
	draw_line(p,p+Vector2(-sin(walker.rotation.y),-cos(walker.rotation.y))*20,Color("e9bd64"),3)
	draw_string(ThemeDB.fallback_font,Vector2(40,45),"ОБЩЕЖИТИЕ · %d ЭТАЖ · СЕВЕР ↑" % (floor_index+1),HORIZONTAL_ALIGNMENT_LEFT,-1,25,Color.WHITE)
	draw_string(ThemeDB.fallback_font,Vector2(40,size.y-35),"M — закрыть · 1–9 / 0 — места · N / B — следующие · F — полёт",HORIZONTAL_ALIGNMENT_LEFT,-1,19,Color("d4ddd8"))
