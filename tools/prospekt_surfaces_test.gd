extends Node
## Из чего поверхности «Проспекта» для шагов, гильз и попаданий (Surfaces.kind_at): точки на дороге, тротуаре,
## площади, газонах, детской, корте, стройке, в паркинге −1, на бортике фонтана, бордюре, люке и решётке ливнёвки —
## луч вниз и вид поверхности против ожидаемого. Покрытия размечает ProspektLandscape (surface_at, метки коллизий).
## tools/godot.cmd --headless res://tools/prospekt_surfaces_test.tscn — выход: число провалов.

const SCENE: String = "res://scenes/levels/prospekt_study.tscn"

## [имя, x, z, ожидаемый вид, высота начала луча (NAN — сверху; ниже — под навесами, ларьками, кранами)].
const POINTS: Array = [
	["дорога, западное плечо", -80.0, -25.0, "asphalt", 0.6],
	["тротуар, северный", -80.0, -41.0, "concrete", NAN],
	["площадь сквера", -20.0, 60.0, "concrete", NAN],
	["разделительная, газон", -100.0, -15.6, "grass", NAN],
	["газон рощи", -10.0, 200.0, "grass", NAN],
	["детская, крошка", -35.0, 165.0, "fabric", NAN],
	["корт", -5.0, 166.0, "asphalt", NAN],
	["стройка, грунт (у каркаса)", -120.0, 128.0, "mud", 2.0],
	["двор дома 7, разбитый асфальт", -190.0, 80.0, "asphalt", NAN],
	["паркинг −1, пол", -150.0, -100.0, "concrete", -5.5],
	["бортик фонтана", -12.0, 101.15, "tile", NAN],
	["бордюр у дороги", -100.0, -34.914, "concrete", 0.6],
]


func _ready() -> void:
	var level: Node = (load(SCENE) as PackedScene).instantiate()
	add_child(level)
	for i: int in range(20):
		await get_tree().physics_frame
	var land: Node = _find_landscape(level)
	var fails: int = 0
	var points: Array = POINTS.duplicate(true)
	if land:
		var spots: Array = land.get("_iron_spots")
		var grate: Array = []
		var manhole: Array = []
		for spot: Array in spots:
			if (spot[1] as Vector2).y < 0.3 and grate.is_empty():
				grate = spot
			elif (spot[1] as Vector2).y > 0.3 and manhole.is_empty():
				manhole = spot
		if not manhole.is_empty():
			points.append(["люк", (manhole[0] as Vector2).x, (manhole[0] as Vector2).y, "metal", 0.6])
		if not grate.is_empty():
			points.append(["решётка ливнёвки", (grate[0] as Vector2).x, (grate[0] as Vector2).y, "metal", 0.6])
		print("prospekt_surfaces: люков и решёток на карте — %d" % spots.size())
	else:
		print("prospekt_surfaces: ПРОВАЛ — не найден ландшафт")
		fails += 1
	var space: PhysicsDirectSpaceState3D = get_viewport().find_world_3d().direct_space_state
	for pt: Array in points:
		var x: float = float(pt[1])
		var z: float = float(pt[2])
		var top: float = 30.0 if is_nan(float(pt[4])) else float(pt[4])
		var q := PhysicsRayQueryParameters3D.create(Vector3(x, top, z), Vector3(x, top - 40.0, z), Hitscan.LAYER_WORLD)
		var hit: Dictionary = space.intersect_ray(q)
		var kind: String = Surfaces.kind_at(hit) if not hit.is_empty() else "(ничего)"
		var ok: bool = kind == String(pt[3])
		fails += 0 if ok else 1
		print("  %s  %-32s %-9s (ждём %s)%s%s" % ["ок" if ok else "ПРОВАЛ", String(pt[0]), kind, String(pt[3]),
			"" if hit.is_empty() else "  y=%.2f" % (hit.position as Vector3).y,
			"" if ok or hit.is_empty() else "  " + str((hit.collider as Node).get_path())])
	print("prospekt_surfaces: провалов %d" % fails)
	get_tree().quit(fails)


func _find_landscape(root: Node) -> Node:
	for n: Node in root.find_children("*", "", true, false):
		if n.has_method("surface_at") and n.has_method("lawn_top"):
			return n
	return null
