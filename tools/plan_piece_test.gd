extends Node
## Улицы «Проспекта» узлами (PlanPiece, docs/level_editing.md): правки владельца доходят до плана и до физики.
## Сдвиг стены, поворот на 90° и на 30° (стена → коробка), растяжение коробки, скрытая глазком плита покрытия,
## копия фонаря, разворот пандуса, подъём лестницы, поворот покрытия с вырезами; в игре узлы убраны,
## повторная сборка плана берёт собранное.
##   tools/godot.cmd --headless res://tools/plan_piece_test.tscn

const SCENE: String = "res://scenes/levels/prospekt_study.tscn"
## Списки улиц; сколько в них кусков — по сцене (владелец правит карту: число меняется).
const LISTS: Array[String] = ["surfaces", "ground_holes", "walk_holes", "slabs", "walls", "boxes", "columns", "stairs", "ramps",
	"beams", "lamps", "signs"]

var _fails: int = 0


func _ready() -> void:
	# как есть: списки плана из узлов — прежнего размера
	var world: Node3D = (load(SCENE) as PackedScene).instantiate() as Node3D
	var pieces: Dictionary = _by_list(world)
	var counts: Dictionary = _sizes(pieces)
	print("  кусков: ", counts)
	var wall: PlanPiece = (pieces.walls as Array)[0]
	var wall_turn: PlanPiece = (pieces.walls as Array)[1]
	var wall_free: PlanPiece = (pieces.walls as Array)[2]
	var box: PlanPiece = _first(pieces.boxes as Array, func(p: PlanPiece) -> bool: return absf(float(p.data.get("yaw", 0.0))) > 1.0)
	var surface: PlanPiece = (pieces.surfaces as Array)[0]
	var holed: PlanPiece = _first(pieces.surfaces as Array, func(p: PlanPiece) -> bool: return not (p.data.get("holes", []) as Array).is_empty())
	var lamp: PlanPiece = (pieces.lamps as Array)[0]
	var ramp: PlanPiece = (pieces.ramps as Array)[0]
	var textured_ramp: PlanPiece = _first(pieces.ramps as Array, func(p: PlanPiece) -> bool: return p.order == 8)
	var stair: PlanPiece = (pieces.stairs as Array)[0]
	var w0: Dictionary = wall.data.duplicate(true)
	var w1: Dictionary = wall_turn.data.duplicate(true)
	var w2: Dictionary = wall_free.data.duplicate(true)
	var b0: Dictionary = box.data.duplicate(true)
	var h0: Dictionary = holed.data.duplicate(true) if holed else {}
	var r0: Dictionary = ramp.data.duplicate(true)
	var s0: Dictionary = stair.data.duplicate(true)
	var lamp0: Array = (lamp.data.a as Array).duplicate()
	var has_textured_ramp: bool = textured_ramp != null
	# правки — как в редакторе: сдвиг, поворот, растяжение, глазок, копия
	wall.position += Vector3(3.0, 0.0, 0.0)
	wall_turn.rotate_y(PI * 0.5)
	wall_free.rotate_y(deg_to_rad(30.0))
	box.scale = Vector3(2.0, 1.0, 1.0)
	surface.visible = false
	if holed:
		holed.rotate_y(PI * 0.5)
	ramp.rotate_y(PI)
	if textured_ramp:
		textured_ramp.data["mat"] = "gravel_023"
		textured_ramp.texture_tile_m = 0.75
		textured_ramp.texture_rotation_deg = 25.0
	stair.position += Vector3(0.0, 1.0, 0.0)
	var copy: PlanPiece = lamp.duplicate() as PlanPiece
	copy.position += Vector3(0.0, 0.0, 5.0)
	lamp.get_parent().add_child(copy)
	copy.owner = world
	add_child(world)
	await get_tree().process_frame
	var land: Node = world.get_node("Landscape")
	var plan: Dictionary = land.get("plan")
	var want: Dictionary = counts.duplicate()
	want.walls = int(counts.walls) - 1
	want.boxes = int(counts.boxes) + 1
	want.surfaces = int(counts.surfaces) - 1
	want.lamps = int(counts.lamps) + 1
	_check("после правок: стена в коробках, покрытие скрыто, фонарь скопирован", _sizes_plan(plan) == want)
	var walls: Array = plan.walls
	var moved: Dictionary = walls[0]
	_check("стена сдвинута на 3 м по X", _near((moved.rect as Array)[0], float((w0.rect as Array)[0]) + 3.0)
		and _near((moved.rect as Array)[2], float((w0.rect as Array)[2]) + 3.0) and _near(moved.y0, w0.y0))
	var turned: Dictionary = walls[1]
	var r1: Array = w1.rect
	var t1: Array = turned.rect
	_check("стена повёрнута на 90°: стороны поменялись, середина на месте",
		_near(float(t1[2]) - float(t1[0]), float(r1[3]) - float(r1[1])) and _near(float(t1[3]) - float(t1[1]), float(r1[2]) - float(r1[0]))
		and _near(float(t1[0]) + float(t1[2]), float(r1[0]) + float(r1[2])))
	var as_box: Dictionary = _find(plan.boxes as Array, func(e: Dictionary) -> bool: return (_near(e.get("yaw", 0.0), 30.0)
		and String(e.mat) == String(w2.get("mat", "wall"))))
	var r2: Array = w2.rect
	_check("стена на 30° — коробка того же размера и материала", not as_box.is_empty()
		and _near((as_box.size as Array)[0], float(r2[2]) - float(r2[0])) and _near((as_box.size as Array)[1], float(w2.y1) - float(w2.y0)))
	var grown: Dictionary = _find(plan.boxes as Array, func(e: Dictionary) -> bool: return (_near((e.at as Array)[0], (b0.at as Array)[0])
		and _near((e.at as Array)[2], (b0.at as Array)[2]) and _near(e.yaw, b0.yaw)))
	_check("коробка растянута вдвое по своей длине (поворот %.1f°)" % float(b0.yaw), not grown.is_empty()
		and _near((grown.size as Array)[0], float((b0.size as Array)[0]) * 2.0) and _near((grown.size as Array)[2], (b0.size as Array)[2]))
	# узлы к этому кадру уже убраны (в игре так и надо) — дальше только записи, снятые до сборки
	_check("нашлось покрытие с вырезами", not h0.is_empty())
	if not h0.is_empty():
		var hr: Dictionary = _find(plan.surfaces as Array, func(e: Dictionary) -> bool: return String(e.id) == String(h0.id))
		var c: Vector2 = _center(h0.rect as Array)
		var hole: Array = (h0.holes as Array)[0]
		var hc: Vector2 = _center(hole)
		var nh: Array = (hr.holes as Array)[0]
		var nc: Vector2 = _center(nh)
		# поворот на +90° вокруг вертикали: (x, z) → (z, −x) от середины
		var want_c: Vector2 = c + Vector2(hc.y - c.y, -(hc.x - c.x))
		_check("покрытие с вырезами повёрнуто: вырез повернулся вместе с ним", nc.distance_to(want_c) < 0.01
			and _near(float(nh[2]) - float(nh[0]), float(hole[3]) - float(hole[1])))
	var rp: Dictionary = plan.ramps[0]
	_check("пандус развёрнут: верх и низ поменялись местами", _near(rp.z0, float(r0.z1)) and _near(rp.z1, float(r0.z0))
		and _near(rp.y0, r0.y0) and _near(rp.y1, r0.y1))
	_check("у пандуса есть индивидуальные настройки текстуры", has_textured_ramp)
	var tex_entry: Dictionary = _find(plan.ramps as Array, func(e: Dictionary) -> bool: return _near(e.get("texture_tile_m", 0.0), 0.75))
	_check("размер и поворот текстуры сохранены в плане", not tex_entry.is_empty() and _near(tex_entry.get("texture_rotation_deg", 0.0), 25.0))
	_check("собранная сетка получила свой материал с размером и поворотом", _custom_material_found(world, 0.75, 25.0))
	var st: Dictionary = plan.stairs[0]
	_check("лестница поднята на 1 м", _near((st.from as Array)[1], float((s0.from as Array)[1]) + 1.0)
		and _near((st.to as Array)[1], float((s0.to as Array)[1]) + 1.0))
	var lamps: Array = plan.lamps
	_check("копия фонаря — рядом с исходным (+5 м по Z)", _near((lamps[1] as Array)[2], float(lamp0[2]) + 5.0)
		or not _find(lamps, func(e: Array) -> bool: return _near(e[0], lamp0[0]) and _near(e[2], float(lamp0[2]) + 5.0), true).is_empty())
	# физика: сдвинутая стена стоит на новом месте (первая стена плана — западная стена перехода: луч внутри перехода
	# с востока бьёт в её восточную грань)
	await get_tree().physics_frame
	var space: PhysicsDirectSpaceState3D = world.get_world_3d().direct_space_state
	var mr: Array = moved.rect
	var from: Vector3 = Vector3(float(mr[2]) + 2.0, (float(moved.y0) + float(moved.y1)) * 0.5, (float(mr[1]) + float(mr[3])) * 0.5)
	var hit: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(from, from - Vector3(6.0, 0.0, 0.0)))
	_check("луч в переходе бьёт в сдвинутую стену (x %.2f)" % float(mr[2]),
		not hit.is_empty() and absf(float((hit.position as Vector3).x) - float(mr[2])) < 0.05)
	# в игре узлы убраны, повторная сборка плана — из собранного
	await get_tree().process_frame
	_check("в игре узлов улиц нет", get_tree().get_nodes_in_group("plan_piece").is_empty())
	land.call("load_plan")
	_check("повторная сборка плана — те же списки", _sizes_plan(land.get("plan")) == want)
	print("plan_piece_test: провалов %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _by_list(world: Node) -> Dictionary:
	var out: Dictionary = {}
	for n: Node in world.find_children("*", "Node3D", true, false):
		if n is PlanPiece:
			var p: PlanPiece = n as PlanPiece
			if not out.has(p.list):
				out[p.list] = []
			(out[p.list] as Array).append(p)
	for key: String in out:
		(out[key] as Array).sort_custom(func(a: PlanPiece, b: PlanPiece) -> bool: return a.order < b.order)
	return out


func _sizes(pieces: Dictionary) -> Dictionary:
	var out: Dictionary = {}
	for key: String in LISTS:
		var n: int = 0
		for p: PlanPiece in pieces.get(key, []):
			if p.visible:
				n += 1
		out[key] = n
	return out


func _sizes_plan(plan: Dictionary) -> Dictionary:
	var out: Dictionary = {}
	for key: String in LISTS:
		out[key] = (plan.get(key, []) as Array).size()
	return out


func _first(list: Array, pred: Callable) -> PlanPiece:
	for p: PlanPiece in list:
		if pred.call(p):
			return p
	return null


func _find(list: Array, pred: Callable, arrays: bool = false) -> Variant:
	for e: Variant in list:
		if pred.call(e):
			return e
	return [] if arrays else {}


func _center(r: Array) -> Vector2:
	return Vector2((float(r[0]) + float(r[2])) * 0.5, (float(r[1]) + float(r[3])) * 0.5)


func _near(a: Variant, b: Variant) -> bool:
	return absf(float(a) - float(b)) < 0.005


func _custom_material_found(world: Node3D, tile: float, degrees: float) -> bool:
	for node: Node in world.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		var materials: Array[Material] = []
		if mi.material_override != null:
			materials.append(mi.material_override)
		if mi.mesh != null:
			for index: int in range(mi.mesh.get_surface_count()):
				materials.append(mi.mesh.surface_get_material(index))
		for material: Material in materials:
			if not material is ShaderMaterial:
				continue
			var tile_value: Variant = (material as ShaderMaterial).get_shader_parameter("tile_m")
			var rotation_value: Variant = (material as ShaderMaterial).get_shader_parameter("texture_rotation")
			if tile_value == null or rotation_value == null:
				continue
			if _near(tile_value, tile) and _near(rad_to_deg(float(rotation_value)), degrees):
				return true
	return false


func _check(what: String, ok: bool) -> void:
	print(("  ок   " if ok else "  ПРОВАЛ ") + what)
	if not ok:
		_fails += 1
