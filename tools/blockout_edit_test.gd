extends Node3D
## Правка «Санатория» руками (docs/level_editing.md): то, что владелец делает в редакторе, — и в игре так же.
##   tools/godot.cmd --headless res://tools/blockout_edit_test.tscn
## Скрытый глазком коттедж — в игре его нет: ни крыши под лучом, ни помещений в проверке пешком. Валун ×2 — коллизия
## выше во столько же. Повёрнутая беседка — настил на том же уровне. Марш ×1,5 по ширине — в склейке шире во столько же.
## (Исходные коробки и марши после склейки убираются — точки считаются по узлам сцены до входа в дерево.)

const LEVEL: String = "res://scenes/levels/sanatorium_study.tscn"

var results: Array[Dictionary] = []


func _ready() -> void:
	Profile.use_file("user://profile_blockout_edit_test.json", true)
	var packed: PackedScene = load(LEVEL) as PackedScene
	# эталон: как есть
	var base: Node3D = packed.instantiate() as Node3D
	var p0: Dictionary = _points(base)
	add_child(base)
	await _frames(3)
	var before: Dictionary = _measure(base, p0, p0)
	var rooms_before: int = ((base.get_node("Landscape").get("plan") as Dictionary).rooms as Array).size()
	base.queue_free()
	await _frames(2)
	# правки, как руками в редакторе: спрятать, растянуть, повернуть
	var edited: Node3D = packed.instantiate() as Node3D
	var land: Node = edited.get_node("Landscape")
	(land.get_node("Постройки/Коттедж 1") as Node3D).visible = false
	(land.get_node("Валуны/Валун 1") as Node3D).scale = Vector3.ONE * 2.0
	(land.get_node("Беседки/Беседка 1") as Node3D).rotate_y(PI * 0.5)
	var p1: Dictionary = _points(edited)
	_first_stair(edited).scale = Vector3(1.5, 1.0, 1.0)
	add_child(edited)
	await _frames(3)
	var after: Dictionary = _measure(edited, p1, p0)
	var rooms_after: int = ((land.get("plan") as Dictionary).rooms as Array).size()
	_check("Скрытый коттедж: крыши под лучом нет", float(before.cottage_hit) - float(after.cottage_hit) > 3.0,
		{"было": before.cottage_hit, "стало": after.cottage_hit})
	_check("Скрытый коттедж: его помещений нет в проверке", rooms_before - rooms_after == int(p0.cottage_rooms),
		{"было": rooms_before, "стало": rooms_after, "у коттеджа": p0.cottage_rooms})
	var want_top: float = float(p0.rock_origin_y) + 2.0 * (float(before.rock_hit) - float(p0.rock_origin_y))
	_check("Валун ×2: верх коллизии вдвое дальше от низа", absf(float(after.rock_hit) - want_top) < 0.3,
		{"было": before.rock_hit, "стало": after.rock_hit, "ждали": want_top})
	_check("Беседка повёрнута: настил на том же уровне", absf(float(after.gazebo_hit) - float(before.gazebo_hit)) < 0.05,
		{"было": before.gazebo_hit, "стало": after.gazebo_hit})
	var widths: Array[float] = []
	for s: Array in ((land.get("snapshot") as Dictionary).stairs as Array):
		if Vector2(float(s[0]) - (p0.stair_bottom as Vector3).x, float(s[2]) - (p0.stair_bottom as Vector3).z).length() < 0.05:
			widths.append(float(s[6]))
	_check("Марш ×1,5 по ширине: в склейке шире во столько же", not widths.is_empty() and absf(widths[0] - float(p0.stair_width) * 1.5) < 0.01,
		{"было": p0.stair_width, "стало": widths})
	var fails: int = results.filter(func(r: Dictionary) -> bool: return not bool(r.pass)).size()
	print("blockout_edit_test: проверок %d, провалов %d" % [results.size(), fails])
	get_tree().quit(mini(fails, 255))


func _first_stair(level: Node) -> Node3D:
	for n: Node in level.get_node("Landscape/Постройки/Главный корпус").find_children("*", "Node3D", true, false):
		if n is BlockoutStair:
			return n as Node3D
	return null


## Трансформ узла относительно корня уровня (узел ещё не в дереве — global_transform нет).
func _chain(node: Node, root: Node) -> Transform3D:
	var xf: Transform3D = Transform3D.IDENTITY
	var n: Node = node
	while n != null and n != root:
		if n is Node3D:
			xf = (n as Node3D).transform * xf
		n = n.get_parent()
	return xf


## Точки для лучей: коттедж 1, середина первой коробки валуна 1, беседка 1, край первого марша главного корпуса.
func _points(level: Node3D) -> Dictionary:
	var land: Node = level.get_node("Landscape")
	var cottage: Node3D = land.get_node("Постройки/Коттедж 1") as Node3D
	var rock: Node3D = land.get_node("Валуны/Валун 1") as Node3D
	var box: Node3D = rock.find_children("*", "CSGBox3D", true, false)[0] as Node3D
	var stair: BlockoutStair = _first_stair(level) as BlockoutStair
	var sxf: Transform3D = _chain(stair, level)
	var bottom: Vector3 = sxf * Vector3.ZERO
	var rooms: int = 0
	for n: Node in cottage.find_children("*", "Node3D", true, false):
		if n is BlockoutChecks:
			rooms += ((n as BlockoutChecks).rooms as Array).size()
	return {"cottage": _chain(cottage, level).origin, "rock": _chain(box, level).origin,
		"rock_origin_y": _chain(rock, level).origin.y, "gazebo": _chain(land.get_node("Беседки/Беседка 1"), level).origin,
		"stair_bottom": bottom, "stair_width": stair.width, "cottage_rooms": rooms}


## Лучи сверху после склейки.
func _measure(_level: Node3D, p: Dictionary, _base: Dictionary) -> Dictionary:
	return {"cottage_hit": _down(p.cottage), "rock_hit": _down(p.rock), "gazebo_hit": _down(p.gazebo)}


func _down(at: Vector3) -> float:
	var q: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(Vector3(at.x, at.y + 120.0, at.z),
		Vector3(at.x, at.y - 120.0, at.z), 1)
	var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(q)
	return float((hit.position as Vector3).y) if not hit.is_empty() else -INF


func _check(label: String, passed: bool, details: Dictionary) -> void:
	results.append({"check": label, "pass": passed})
	print("blockout_edit_test: %s · %s %s" % ["PASS" if passed else "FAIL", label, JSON.stringify(details)])


func _frames(n: int) -> void:
	for i: int in range(n):
		await get_tree().physics_frame
