extends Node
## «Проспект»: где рвётся навигация вдоль лестниц. Каждая лестница плана (stairs в prospekt_snapshot.json)
## проходится по осевой линии шагом STEP_M; у каждой точки — расстояние до ближайшей точки навигации и её высота.
## Печатает по лестнице: покрытие, самый длинный разрыв, ширину, уклон; с аргументом `-- detail=N,M` — ещё и
## каждый шаг этих лестниц. Геометрию не правит; код выхода — 0.
##   tools/godot.cmd --headless res://tools/prospekt_nav_stairs.tscn [-- detail=58,53]

const LEVEL := "res://scenes/levels/prospekt.tscn"
const SNAPSHOT := "res://data/blockouts/prospekt_snapshot.json"
const STEP_M := 0.25
## Точка оси «покрыта», если навигация ближе этого, м (поверхность навигации лежит над пандусом на высоту ячейки).
const NEAR_M := 0.45


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "dusk", "weather": "clear", "power": "on"}
	Profile.use_file("user://profile_prospekt_nav_stairs.json", true)
	var detail: Array[int] = []
	var maps: Array[int] = []
	var areas: Array[Vector3] = []
	var paths: Array[String] = []
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("detail="):
			for part: String in arg.substr(7).split(","):
				detail.append(int(part))
		if arg.begins_with("path="):
			paths.append(arg.substr(5))
		if arg.begins_with("area="):
			var parts: PackedStringArray = arg.substr(5).split(",")
			areas.append(Vector3(float(parts[0]), float(parts[1]), float(parts[2])))
		if arg.begins_with("map="):
			for part: String in arg.substr(4).split(","):
				maps.append(int(part))
	await get_tree().process_frame
	StairNavigation.debug = true
	var level: Node = load(LEVEL).instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	var t0: int = Time.get_ticks_msec()
	while int(level.get("_marauders_spawned")) <= 0 and Time.get_ticks_msec() - t0 < 180000:
		await get_tree().process_frame
	var map: RID = (level as Node3D).get_world_3d().navigation_map
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(SNAPSHOT))
	var stairs: Array = (parsed as Dictionary).stairs
	var bad: int = 0
	for spec: String in paths:
		var ends: PackedStringArray = spec.split(":")
		var pa: PackedStringArray = ends[0].split(",")
		var pb: PackedStringArray = ends[1].split(",")
		var va := Vector3(float(pa[0]), float(pa[1]), float(pa[2]))
		var vb := Vector3(float(pb[0]), float(pb[1]), float(pb[2]))
		print("PATH | %s → %s: %s (ближайшие точки сетки: %s / %s)" % [va, vb, NavigationServer3D.map_get_path(map, va, vb, true),
			NavigationServer3D.map_get_closest_point(map, va), NavigationServer3D.map_get_closest_point(map, vb)])
	for center: Vector3 in areas:
		_print_area(level as Node3D, map, center)
	for index in maps:
		_print_ends(level as Node3D, map, stairs[index] as Dictionary, index)
	for index in range(stairs.size()):
		var s: Dictionary = stairs[index]
		var a: Array = s.from
		var b: Array = s.to
		var start := Vector3(float(a[0]), float(a[1]), float(a[2]))
		var finish := Vector3(float(b[0]), float(b[1]), float(b[2]))
		var length: float = start.distance_to(finish)
		var flat: float = Vector2(finish.x - start.x, finish.z - start.z).length()
		var angle: float = rad_to_deg(atan2(absf(finish.y - start.y), flat))
		var n: int = int(ceil(length / STEP_M))
		var covered: int = 0
		var run: int = 0
		var longest: int = 0
		var lines: Array[String] = []
		for i in range(n + 1):
			var p: Vector3 = start.lerp(finish, float(i) / float(n))
			var q: Vector3 = NavigationServer3D.map_get_closest_point(map, p)
			var d: float = q.distance_to(p)
			if d < NEAR_M:
				covered += 1
				run = 0
			else:
				run += 1
				longest = maxi(longest, run)
			if detail.has(index):
				lines.append("    шаг %.2f м: точка y %.2f, до навигации %.2f м (её y %.2f)" % [float(i) * length / float(n), p.y, d, q.y])
		var share: float = float(covered) / float(n + 1)
		# путь от площадки перед низом марша до площадки за верхом — идёт ли он по маршу (а не в обход или никак)
		var dir: Vector3 = (Vector3(finish.x - start.x, 0.0, finish.z - start.z)).normalized()
		var from_p: Vector3 = NavigationServer3D.map_get_closest_point(map, start - dir * 1.2)
		var to_p: Vector3 = NavigationServer3D.map_get_closest_point(map, finish + dir * 1.2)
		var q := NavigationPathQueryParameters3D.new()
		q.map = map
		q.start_position = from_p
		q.target_position = to_p
		q.path_search_max_polygons = 0
		var r := NavigationPathQueryResult3D.new()
		NavigationServer3D.query_path(q, r)
		var path_len: float = 0.0
		for k in range(1, r.path.size()):
			path_len += r.path[k - 1].distance_to(r.path[k])
		var through: bool = not r.path.is_empty() and r.path[r.path.size() - 1].distance_to(to_p) < 0.6 			and path_len < from_p.distance_to(to_p) * 1.5 + 3.0
		if not through:
			bad += 1
		# концы связки (Balance.STAIR_NAV_LINK.reach_m): есть ли у них сетка ближе радиуса связей карты (1 м)
		var reach: float = float(Balance.STAIR_NAV.pad_m) * 0.5
		var e0: Vector3 = start - dir * reach
		var e1: Vector3 = finish + dir * reach
		var d0: float = NavigationServer3D.map_get_closest_point(map, e0).distance_to(e0)
		var d1: float = NavigationServer3D.map_get_closest_point(map, e1).distance_to(e1)
		if not through:
			print("STAIRFAIL | #%d конец-низ %s → сетка %s; конец-верх %s → сетка %s" % [index, e0, NavigationServer3D.map_get_closest_point(map, e0), e1, NavigationServer3D.map_get_closest_point(map, e1)])
		print("STAIR | #%d %s w %.2f, %.1f°, длина %.1f м, подступенок %.2f | сетка у оси %.0f %%, разрыв до %.2f м | концы до сетки %.2f / %.2f м | путь %s (%.0f м при прямой %.0f) | %s" % [
			index, String(s.get("mat", "")), float(s.width), angle, length, absf(finish.y - start.y) / float(s.count),
			share * 100.0, float(longest) * length / float(n), d0, d1, "есть" if not r.path.is_empty() else "нет", path_len,
			from_p.distance_to(to_p), "ХОДИТ" if through else "РВЁТСЯ"])
		for line: String in lines:
			print(line)
	print("STAIR итого: лестниц %d, с разрывом %d" % [stairs.size(), bad])
	# по ковру: путь от точки, к которой привязан нижний конец, до такой же у верхнего (ковёр нигде не должен быть тупиком)
	var dead: int = 0
	for row: Dictionary in StairNavigation.report:
		var lo: Vector3 = row.low_to if (row.low_to as Vector3).is_finite() else row.low
		var hi: Vector3 = row.high_to if (row.high_to as Vector3).is_finite() else row.high
		var q2 := NavigationPathQueryParameters3D.new()
		q2.map = map
		q2.start_position = lo
		q2.target_position = hi
		q2.path_search_max_polygons = 0
		var r2 := NavigationPathQueryResult3D.new()
		NavigationServer3D.query_path(q2, r2)
		var len2: float = 0.0
		for k in range(1, r2.path.size()):
			len2 += r2.path[k - 1].distance_to(r2.path[k])
		var ok2: bool = not r2.path.is_empty() and r2.path[r2.path.size() - 1].distance_to(hi) < 0.6 and len2 < lo.distance_to(hi) * 1.6 + 3.0
		if not ok2:
			dead += 1
			if dead <= 6:
				print("CARPETDBG | lo %s hi %s | низ-связка: %s | верх-связка: %s" % [lo, hi,
					_ends(map, lo, row.low), _ends(map, row.high, hi)])
		print("CARPET | %s → %s | концы %s / %s | путь %.0f м при прямой %.0f | %s" % [row.low, row.high, row.low_kind, row.high_kind, len2, lo.distance_to(hi), "ОК" if ok2 else "ТУПИК"])
	print("CARPET итого: ковров %d, тупиков %d" % [StairNavigation.report.size(), dead])
	get_tree().quit(0)


## Площадки у концов марша глазами физики: '.' — пол на высоте конца, '#' — выше (препятствие), ' ' — пустота / ниже,
## 'n' — рядом есть сетка навигации (ближе 0,3 м по плоскости). Квадрат 8 × 8 м вокруг каждого конца, шаг 0,5 м; ось марша — вправо.
func _print_ends(level: Node3D, map: RID, s: Dictionary, index: int) -> void:
	var space: PhysicsDirectSpaceState3D = level.get_world_3d().direct_space_state
	var a: Array = s.from
	var b: Array = s.to
	var start := Vector3(float(a[0]), float(a[1]), float(a[2]))
	var finish := Vector3(float(b[0]), float(b[1]), float(b[2]))
	var dir: Vector3 = Vector3(finish.x - start.x, 0.0, finish.z - start.z).normalized()
	var side: Vector3 = dir.cross(Vector3.UP)
	for end_name: String in ["низ", "верх"]:
		var c: Vector3 = start if end_name == "низ" else finish
		var out: Vector3 = -dir if end_name == "низ" else dir
		print("ENDMAP | #%d %s: центр %s, наружу %s (вверх по строкам — влево от оси)" % [index, end_name, c, out])
		for row in range(-8, 9):
			var line: String = ""
			for col in range(-6, 11):
				var p: Vector3 = c + out * (float(col) * 0.5) + side * (float(row) * -0.5)
				var top: Vector3 = Vector3(p.x, c.y + 1.7, p.z)
				var q := PhysicsRayQueryParameters3D.create(top, top + Vector3.DOWN * 3.0, Hitscan.LAYER_WORLD)
				var hit: Dictionary = space.intersect_ray(q)
				var ch: String = " "
				if not hit.is_empty():
					var dy: float = (hit.position as Vector3).y - c.y
					ch = "." if absf(dy) < 0.15 else ("#" if dy > 0.0 else " ")
				var np: Vector3 = NavigationServer3D.map_get_closest_point(map, Vector3(p.x, c.y + 0.5, p.z))
				if Vector2(np.x - p.x, np.z - p.z).length() < 0.3 and absf(np.y - (c.y + 0.5)) < 0.3:
					ch = "n"
				if row == 0 and col == 0:
					ch = "O" if ch != "n" else "N"
				line += ch
			print("ENDMAP | " + line)


## Конец пути из a в b: дошёл ли и где остановился (для разбора связок ковра).
func _ends(map: RID, a: Vector3, b: Vector3) -> String:
	var q := NavigationPathQueryParameters3D.new()
	q.map = map
	q.start_position = a
	q.target_position = b
	q.path_search_max_polygons = 0
	var r := NavigationPathQueryResult3D.new()
	NavigationServer3D.query_path(q, r)
	if r.path.is_empty():
		return "пусто"
	return "до %.2f м от цели, точек %d, конец %s" % [r.path[r.path.size() - 1].distance_to(b), r.path.size(), r.path[r.path.size() - 1]]


## Вид сверху на 16 × 16 м вокруг точки: '.' — пол на её высоте (±0,15), '#' — выше, ' ' — пустота / ниже, 'n' — сетка навигации рядом.
func _print_area(level: Node3D, map: RID, c: Vector3) -> void:
	var space: PhysicsDirectSpaceState3D = level.get_world_3d().direct_space_state
	print("AREA | центр %s (вверх по строкам — минус Z, вправо — плюс X)" % c)
	for row in range(-16, 17):
		var line: String = ""
		for col in range(-16, 17):
			var p := Vector3(c.x + float(col) * 0.5, c.y, c.z + float(row) * 0.5)
			var top := Vector3(p.x, c.y + 1.7, p.z)
			var q := PhysicsRayQueryParameters3D.create(top, top + Vector3.DOWN * 3.0, Hitscan.LAYER_WORLD)
			var hit: Dictionary = space.intersect_ray(q)
			var ch: String = " "
			if not hit.is_empty():
				var dy: float = (hit.position as Vector3).y - c.y
				ch = "." if absf(dy) < 0.15 else ("#" if dy > 0.0 else " ")
			var np: Vector3 = NavigationServer3D.map_get_closest_point(map, Vector3(p.x, c.y + 0.5, p.z))
			if Vector2(np.x - p.x, np.z - p.z).length() < 0.3 and absf(np.y - (c.y + 0.5)) < 0.3:
				ch = "n"
			line += ch
		print("AREA | " + line)
