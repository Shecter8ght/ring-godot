extends Node
## Левел-дизайн Пригорода (зона 1, docs/design/zone01_level_design.md): в каждом зале с интерьером есть что
## обыскать и до каждого места лута можно дойти; места заказа «Вернуть машину» стоят и доступны; от каждого
## появления есть путь к выходу; серверная заперта, ключ в администрации; открытые отрезки улиц без укрытий.
## tools/godot.cmd --headless res://tools/zone01_ld_test.tscn

const CAR_SITES: Array[String] = ["car_belt_search", "car_belt_hangar", "car_belt_car_body", "car_belt_car_marking",
	"car_belt_photo_engine", "car_belt_photo_radiator", "car_belt_photo_wheel", "car_belt_photo_wiring",
	"car_belt_car_battery", "car_belt_car_wheel", "car_belt_delivery", "car_belt_parts_wheel", "car_belt_parts_radiator"]
## Открытый отрезок улицы: укрытия (любая коллизия мира) нет ближе COVER_M по сторонам на высоте груди.
const COVER_M := 9.0
const MAX_OPEN_M := 60.0

var failures: int = 0
var checks: int = 0
var level: Node3D
var map: RID


func _ready() -> void:
	Profile.use_file("user://zone01_ld_test.json", true)
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	level = (load("res://scenes/levels/zone01_mall.tscn") as PackedScene).instantiate() as Node3D
	level.set_script(null)
	add_child(level)
	await get_tree().physics_frame
	await get_tree().physics_frame
	var layout: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/zone01_layout.json"))
	# --- интерьеры и лут
	var total: int = 0
	var lines: Array[String] = []
	for b: Node in level.get_node("Layout/Buildings").get_children():
		var interior: String = String(b.get("interior"))
		var kind: String = String(b.get("kind"))
		if interior == "" and not kind in ["apartments", "house"]:
			continue
		var n: int = int(b.get_meta("loot_count", 0))
		total += n
		lines.append("%s %d" % [b.name, n])
		if interior != "":
			check("в «%s» есть что обыскать" % String(b.get("label")), n > 0, str(n))
	print("  лут по зданиям: ", ", ".join(lines))
	check("мест лута в зданиях не меньше 120", total >= 120, str(total))
	var door := level.get_node_or_null("Layout/Buildings/N_service/Gameplay/VaultDoor") as Door
	check("серверная техкорпуса заперта ключом", door != null and door.required_key == "key_server", "")
	var key := level.get_node_or_null("Layout/Buildings/Admin/Gameplay/Key_0") as KeyPickup
	check("ключ от серверной лежит в администрации", key != null and key.key_id == "key_server", "")
	# --- навигация
	var navigation := UrbanNavigation.new()
	navigation.definition = SectorBuilder.load_def("res://data/sectors/zone01_mall.json")
	level.get_node("Navigation").add_child(navigation)
	await navigation.ready_for_agents
	map = level.get_world_3d().navigation_map
	var hub: Vector3 = NavigationServer3D.map_get_closest_point(map, Vector3(0.0, 0.0, 60.0))
	var unreachable: Array[String] = []
	var inside: int = 0
	for node: Node in get_tree().get_nodes_in_group("loot_containers"):
		var c := node as LootContainer
		if c == null or not level.get_node("Layout").is_ancestor_of(c):
			continue
		inside += 1
		if not _reach(hub, c.global_position - Vector3.UP * Balance.LOOT_POINT_HEIGHT, 1.6):
			unreachable.append(String(c.get_parent().get_parent().name) + "/" + String(c.name))
	check("до всех мест лута в зданиях можно дойти (%d)" % inside, unreachable.is_empty(),
		"нет пути: %d — %s" % [unreachable.size(), ", ".join(unreachable.slice(0, 12))])
	# --- заказ «Вернуть машину»
	var anchors: Dictionary = {}
	for a: Node in get_tree().get_nodes_in_group("quest_anchors"):
		anchors[String(a.get("site_id"))] = a
	for sid: String in CAR_SITES:
		var a := anchors.get(sid) as Node3D
		check("место заказа %s стоит и до него можно дойти" % sid, a != null and _reach(hub, a.global_position, 1.6),
			"" if a == null else "%v" % a.global_position)
	var car := level.get_node_or_null("CarRecovery/Hangar8/IlyaCar") as Node3D
	check("машина Ильи в ангаре № 8", car != null, "")
	# --- появление → выход
	var extracts: Array[Vector3] = []
	for n: Node in level.get_node("Gameplay").get_children():
		if String(n.name).begins_with("Extraction_"):
			extracts.append((n as Node3D).global_position)
	for n: Node in level.get_node("Gameplay").get_children():
		if not String(n.name).begins_with("Entry_"):
			continue
		var from: Vector3 = (n as Node3D).global_position
		var best: float = INF
		for e: Vector3 in extracts:
			var length: float = _path_length(from, e)
			best = minf(best, length)
		check("от появления «%s» есть путь к выходу" % String(n.get("display_name")), best < INF, "%.0f м" % best)
	# --- открытые отрезки улиц (к сведению; провал — только совсем голые)
	var worst: float = 0.0
	var worst_at: String = ""
	var long_runs: int = 0
	for road: Dictionary in layout.roads:
		var pts: Array = road.points
		var run: float = 0.0
		var run_from: Vector2 = Vector2.ZERO
		for i: int in range(pts.size() - 1):
			var a := Vector2(float(pts[i][0]), float(pts[i][1]))
			var b := Vector2(float(pts[i + 1][0]), float(pts[i + 1][1]))
			var steps: int = maxi(1, int(a.distance_to(b) / 5.0))
			for k: int in range(steps):
				var p: Vector2 = a.lerp(b, float(k) / float(steps))
				if _open(p):
					if run == 0.0:
						run_from = p
					run += a.distance_to(b) / float(steps)
				else:
					if run > 30.0:
						long_runs += 1
					if run > worst:
						worst = run
						worst_at = "%s (%.0f, %.0f)" % [String(road.label), run_from.x, run_from.y]
					run = 0.0
		if run > worst:
			worst = run
			worst_at = "%s (%.0f, %.0f)" % [String(road.label), run_from.x, run_from.y]
	print("  открытых отрезков улиц длиннее 30 м: %d; самый длинный %.0f м — %s" % [long_runs, worst, worst_at])
	check("на улицах нет голых отрезков длиннее %.0f м" % MAX_OPEN_M, worst <= MAX_OPEN_M, "%.0f м" % worst)
	print("zone01_ld_test: checks=", checks, " failures=", failures)
	get_tree().quit(1 if failures else 0)


## Есть ли путь от from к точке у to: конец пути не дальше tol по горизонтали и 1,2 м по высоте.
func _reach(from: Vector3, to: Vector3, tol: float) -> bool:
	var path: PackedVector3Array = _query(from, to)
	if path.is_empty():
		return false
	var end: Vector3 = path[-1]
	return Vector2(end.x - to.x, end.z - to.z).length() < tol and absf(end.y - to.y) < 1.2


func _path_length(from: Vector3, to: Vector3) -> float:
	var path: PackedVector3Array = _query(from, to)
	if path.is_empty() or path[-1].distance_to(to) > 8.0:
		return INF
	var length: float = 0.0
	for i: int in range(1, path.size()):
		length += path[i - 1].distance_to(path[i])
	return length


func _query(from: Vector3, to: Vector3) -> PackedVector3Array:
	var query := NavigationPathQueryParameters3D.new()
	query.map = map
	query.start_position = from
	query.target_position = to
	query.path_search_max_polygons = 400000
	var result := NavigationPathQueryResult3D.new()
	NavigationServer3D.query_path(query, result)
	return result.path


## Голо ли у точки улицы: на высоте груди ни одного препятствия ближе COVER_M ни в одну сторону.
func _open(p: Vector2) -> bool:
	var space := level.get_world_3d().direct_space_state
	var down: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(p.x, 60.0, p.y), Vector3(p.x, -30.0, p.y), Hitscan.LAYER_WORLD))
	if down.is_empty():
		return false
	var eye: Vector3 = (down.position as Vector3) + Vector3.UP * 1.0
	for i: int in range(16):
		var ang: float = float(i) * TAU / 16.0
		var to: Vector3 = eye + Vector3(cos(ang), 0.0, sin(ang)) * COVER_M
		if not space.intersect_ray(PhysicsRayQueryParameters3D.create(eye, to, Hitscan.LAYER_WORLD)).is_empty():
			return false
	return true


func check(title: String, passed: bool, info: String) -> void:
	checks += 1
	if not passed:
		failures += 1
	print("OK   " if passed else "FAIL ", title, ("  — " + info) if info != "" else "")
