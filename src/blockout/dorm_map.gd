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
	var extent: Vector2 = Vector2(float(plan.bounds[2])-float(plan.bounds[0]),float(plan.bounds[3])-float(plan.bounds[1]))
	var k: float = minf((size.x - 120.0) / extent.x, (size.y - 180.0) / extent.y)
	var origin: Vector2 = (size - extent * k) * 0.5
	var base: Vector2 = Vector2(float(plan.bounds[0]),float(plan.bounds[1]))
	draw_rect(Rect2(Vector2.ZERO, size), Color(0.05, 0.065, 0.08, 0.97))
	for area: Dictionary in plan.get("circulation",[]):
		if int(area.floor)==floor_index+1:
			var r: Array = area.rect
			draw_rect(Rect2(origin+(Vector2(float(r[0]),float(r[1]))-base)*k,Vector2(float(r[2])-float(r[0]),float(r[3])-float(r[1]))*k),Color("675f4b"))
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
		var short_name: String = String(space.label)
		if short_name.length()>10:
			short_name = short_name.left(8)+"…"
		draw_string(ThemeDB.fallback_font,a+Vector2(3,span.y*0.5),short_name,HORIZONTAL_ALIGNMENT_LEFT,-1,12,Color("ecf0eb"))
	var sections: Dictionary = plan.sections
	for key: String in sections:
		if key in ["Site","Roof"]:
			continue
		var section: Dictionary = sections[key]
		var parts: Array[Dictionary] = [section]
		for group: Dictionary in (section.get("groups",{}) as Dictionary).values():
			parts.append(group)
		for part: Dictionary in parts:
			for item: Dictionary in part.boxes:
				var at: Array = item.at
				var span: Array = item.size
				if absf(float(at[1])-floor_y-1.4)>float(span[1])*0.5 or String(item.mat)=="glass":
					continue
				var xz: Vector2 = Vector2(float(at[0]),float(at[2]))
				var dimensions: Vector2 = Vector2(float(span[0]),float(span[2]))
				draw_rect(Rect2(origin+(xz-dimensions*0.5-base)*k,dimensions*k),Color("c8cbc8"))
	for leaf: Node in get_tree().get_nodes_in_group("dorm_study_doors"):
		var door: Node3D = leaf as Node3D
		if absf(door.global_position.y-floor_y)>0.1:
			continue
		var data: Dictionary = door.get("data") as Dictionary
		var a: Vector3 = door.global_position
		var b: Vector3 = door.to_global(Vector3(float(data.width),0,0))
		draw_line(origin+(Vector2(a.x,a.z)-base)*k,origin+(Vector2(b.x,b.z)-base)*k,Color("b89c71"),2)
	var p: Vector2 = origin+(Vector2(walker.position.x,walker.position.z)-base)*k
	draw_circle(p,6,Color("e9bd64"))
	draw_line(p,p+Vector2(-sin(walker.rotation.y),-cos(walker.rotation.y))*20,Color("e9bd64"),3)
	draw_string(ThemeDB.fallback_font,Vector2(40,45),"ОБЩЕЖИТИЕ · %d ЭТАЖ · СЕВЕР ↑" % (floor_index+1),HORIZONTAL_ALIGNMENT_LEFT,-1,25,Color.WHITE)
	draw_string(ThemeDB.fallback_font,Vector2(40,size.y-35),"M — закрыть · 1–9 / 0 — места · N / B — следующие · F — полёт",HORIZONTAL_ALIGNMENT_LEFT,-1,19,Color("d4ddd8"))
