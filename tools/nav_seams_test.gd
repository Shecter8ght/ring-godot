extends Node
## Швы тайлов UrbanNavigation: связи по краю только у полос у швов (Seam_x_z) дают ту же связность, что прежняя
## раскладка (тайл целиком, связи по краю у всех), а синхронизация карты — десятки мс вместо секунд.
##   tools/godot.cmd --headless res://tools/nav_seams_test.tscn [-- mall_map prospekt zone01_mall]
##   с окном (--windowed --resolution 1280x720) — те же замеры времени под отрисовкой
## Для каждой карты из кэша (кэш должен быть действителен — иначе перепечь tools/bake_*_nav.tscn):
##  1. UrbanNavigation в дереве — время до ready_for_agents, одна пересинхронизация карты, свободные рёбра;
##  2. эталон — своя карта сервера из того же кэша: тайл одним регионом, связи по краю у всех — то же время;
##  3. переходы через каждый шов: от каждого ребра на шве — на 1 м в свой тайл и на 1 м в соседний;
##  4. заходы (SpawnPoint) → выходы (ExtractionPoint) сцены уровня;
##  5. случайные пары точек карты.
## В 3–5 путь в эталоне и в новой раскладке: дошёл ли и длина. Расхождение — ошибка, код выхода 1.

const MAPS: Array[String] = ["mall_map", "prospekt", "zone01_mall"]
const LEVELS: Dictionary = {"mall_map": "res://scenes/levels/mall_map.tscn",
	"prospekt": "res://scenes/levels/prospekt.tscn", "zone01_mall": "res://scenes/levels/zone01_mall.tscn"}
## шаг от ребра шва в каждый тайл, м
const STEP: float = 1.0
## точка «есть на навигации», если ближайшая на сетке не дальше, м (по горизонтали / по высоте)
const SNAP_XZ: float = 0.4
const SNAP_Y: float = 1.0
## заход и выход могут стоять в стороне от сетки (площадка, зона эвакуации)
const POINT_SNAP: float = 6.0
const RANDOM_PAIRS: int = 150
## допуск длины пути: доля и метры
const LENGTH_TOLERANCE: float = 0.01
const LENGTH_SLACK: float = 0.3
## длинные пути: допуск выбора коридора A* (по лучшему из двух направлений)
const ASTAR_TOLERANCE: float = 0.05
const ASTAR_SLACK: float = 2.0

var _failures: int = 0


func _ready() -> void:
	await get_tree().process_frame
	var ids: Array[String] = []
	for argument: String in OS.get_cmdline_user_args():
		if LEVELS.has(argument):
			ids.append(argument)
	if ids.is_empty():
		ids = MAPS
	for id: String in ids:
		await _check(id)
	print("nav_seams_test: %s" % ("ГОТОВО, расхождений нет" if _failures == 0 else "ОШИБОК %d" % _failures))
	get_tree().quit(0 if _failures == 0 else 1)


func _check(id: String) -> void:
	var definition: Dictionary = SectorBuilder.load_def("res://data/sectors/%s.json" % id)
	var holder := Node3D.new()
	add_child(holder)
	var navigation := UrbanNavigation.new()
	navigation.definition = definition
	if not navigation._cache_valid():
		_fail("[%s] кэш навигации недействителен — перепечь tools/bake_*_nav.tscn" % id)
		holder.queue_free()
		return
	var cfg: Dictionary = navigation._config()
	var ready: Array[bool] = [false]
	navigation.ready_for_agents.connect(func() -> void: ready[0] = true)
	var start: int = Time.get_ticks_msec()
	holder.add_child(navigation)
	while not ready[0] and Time.get_ticks_msec() - start < 120000:
		await get_tree().process_frame
	if not ready[0]:
		_fail("[%s] навигация не готова за 120 с" % id)
		holder.queue_free()
		return
	var new_ms: int = Time.get_ticks_msec() - start
	var new_map: RID = get_viewport().get_world_3d().navigation_map
	var new_resync: int = await _resync(new_map)
	var free_edges: int = NavigationServer3D.get_process_info(NavigationServer3D.INFO_EDGE_FREE_COUNT)
	# эталон: те же тайлы одним регионом со связями по краю у всех
	var tiles: Dictionary = {}
	var seams: Dictionary = {}
	for child: Node in navigation.get_children():
		if child is NavigationRegion3D:
			var key: String = String(child.name).substr(String(child.name).find("_") + 1)
			if String(child.name).begins_with("Seam_"):
				seams[key] = (child as NavigationRegion3D).navigation_mesh
			else:
				tiles[key] = (child as NavigationRegion3D).navigation_mesh
	_inside_tiles(id, definition, cfg, seams, tiles)
	var reference: RID = NavigationServer3D.map_create()
	NavigationServer3D.map_set_cell_size(reference, float(cfg.nav_cell))
	NavigationServer3D.map_set_cell_height(reference, float(cfg.nav_height))
	NavigationServer3D.map_set_merge_rasterizer_cell_scale(reference, float(cfg.nav_merge_scale))
	NavigationServer3D.map_set_active(reference, true)
	var regions: Array[RID] = []
	var samples := PackedVector3Array()
	start = Time.get_ticks_msec()
	for key: String in tiles:
		var whole: NavigationMesh = _merged(seams[key], tiles[key])
		var region: RID = NavigationServer3D.region_create()
		NavigationServer3D.region_set_navigation_mesh(region, whole)
		NavigationServer3D.region_set_map(region, reference)
		regions.append(region)
		if whole.get_polygon_count() > 0:
			samples.append(whole.get_vertices()[whole.get_polygon(whole.get_polygon_count() / 2)[0]])
	while not _published(reference, regions, samples, float(cfg.nav_cell)) and Time.get_ticks_msec() - start < 120000:
		await get_tree().physics_frame
	var reference_ms: int = Time.get_ticks_msec() - start
	var reference_resync: int = await _resync(reference)
	var seam_polygons: int = 0
	var polygons: int = 0
	for key: String in tiles:
		seam_polygons += (seams[key] as NavigationMesh).get_polygon_count()
		polygons += (seams[key] as NavigationMesh).get_polygon_count() + (tiles[key] as NavigationMesh).get_polygon_count()
	print("[%s] многоугольников %d, у швов %d; свободных рёбер со связями по краю %d (окно %s)" % [id, polygons, seam_polygons,
		free_edges, str(DisplayServer.get_name() != "headless")])
	print("[%s] до готовности: полосы у швов %d мс, эталон %d мс; пересинхронизация: полосы %d мс, эталон %d мс" % [id,
		new_ms, reference_ms, new_resync, reference_resync])
	await _seam_crossings(id, definition, cfg, seams, new_map, reference)
	await _entries_to_exits(id, new_map, reference)
	await _random_pairs(id, definition, new_map, reference)
	for region: RID in regions:
		NavigationServer3D.free_rid(region)
	NavigationServer3D.free_rid(reference)
	holder.queue_free()
	for i in range(5):
		await get_tree().physics_frame


## Полоса у шва ловит все связи по краю, только если многоугольники тайла не выходят за его границы
## (Recast обрезает рамку border_size): тогда ребро ближе запаса связей к соседу — в полосе.
func _inside_tiles(id: String, definition: Dictionary, cfg: Dictionary, seams: Dictionary, tiles: Dictionary) -> void:
	var bounds: Array = definition.get("bounds")
	var tile: float = float(cfg.nav_tile)
	var outside: int = 0
	for key: String in tiles:
		var cell: PackedStringArray = key.split("_")
		var rect := Rect2(float(bounds[0]) + float(cell[0]) * tile - 0.01, float(bounds[1]) + float(cell[1]) * tile - 0.01, tile + 0.02, tile + 0.02)
		for mesh: NavigationMesh in [seams[key], tiles[key]]:
			for vertex: Vector3 in mesh.get_vertices():
				if not rect.has_point(Vector2(vertex.x, vertex.z)):
					outside += 1
	if outside > 0:
		_fail("[%s] точек сетки за границей своего тайла: %d" % [id, outside])


## Время одной полной сборки карты сервером: запас связей по краю чуть сдвигаем и возвращаем.
func _resync(map: RID) -> int:
	var margin: float = NavigationServer3D.map_get_edge_connection_margin(map)
	var iteration: int = NavigationServer3D.map_get_iteration_id(map)
	var start: int = Time.get_ticks_msec()
	NavigationServer3D.map_set_edge_connection_margin(map, margin + 0.0001)
	while NavigationServer3D.map_get_iteration_id(map) == iteration and Time.get_ticks_msec() - start < 120000:
		await get_tree().physics_frame
	var elapsed: int = Time.get_ticks_msec() - start
	iteration = NavigationServer3D.map_get_iteration_id(map)
	NavigationServer3D.map_set_edge_connection_margin(map, margin)
	while NavigationServer3D.map_get_iteration_id(map) == iteration and Time.get_ticks_msec() - start < 240000:
		await get_tree().physics_frame
	return elapsed


func _published(map: RID, regions: Array[RID], samples: PackedVector3Array, cell: float) -> bool:
	for region: RID in regions:
		if NavigationServer3D.region_get_iteration_id(region) == 0:
			return false
	for sample: Vector3 in samples:
		if NavigationServer3D.map_get_closest_point(map, sample).distance_to(sample) > cell:
			return false
	return not samples.is_empty()


func _merged(a: NavigationMesh, b: NavigationMesh) -> NavigationMesh:
	var whole := NavigationMesh.new()
	whole.cell_size = a.cell_size
	whole.cell_height = a.cell_height
	whole.agent_height = a.agent_height
	whole.agent_radius = a.agent_radius
	var vertices: PackedVector3Array = a.get_vertices()
	var offset: int = vertices.size()
	vertices.append_array(b.get_vertices())
	whole.vertices = vertices
	for index in range(a.get_polygon_count()):
		whole.add_polygon(a.get_polygon(index))
	for index in range(b.get_polygon_count()):
		var polygon: PackedInt32Array = b.get_polygon(index)
		for corner in range(polygon.size()):
			polygon[corner] += offset
		whole.add_polygon(polygon)
	return whole


## Каждое ребро полосы, лежащее на линии шва с соседом: шаг в свой тайл и в соседний.
func _seam_crossings(id: String, definition: Dictionary, cfg: Dictionary, seams: Dictionary, new_map: RID, reference: RID) -> void:
	var bounds: Array = definition.get("bounds")
	var tile: float = float(cfg.nav_tile)
	var seen: Dictionary = {}
	var stats: Dictionary = {"edges": 0, "both": 0, "none": 0, "off": 0}
	for key: String in seams:
		var cell: PackedStringArray = key.split("_")
		var x0: float = float(bounds[0]) + float(cell[0]) * tile
		var z0: float = float(bounds[1]) + float(cell[1]) * tile
		var center := Vector3(x0 + tile * 0.5, 0.0, z0 + tile * 0.5)
		var mesh: NavigationMesh = seams[key]
		var vertices: PackedVector3Array = mesh.get_vertices()
		for index in range(mesh.get_polygon_count()):
			var polygon: PackedInt32Array = mesh.get_polygon(index)
			for corner in range(polygon.size()):
				var a: Vector3 = vertices[polygon[corner]]
				var b: Vector3 = vertices[polygon[(corner + 1) % polygon.size()]]
				var inward := Vector3.ZERO
				for line: Vector2 in [Vector2(0, x0), Vector2(0, x0 + tile), Vector2(2, z0), Vector2(2, z0 + tile)]:
					var axis: int = int(line.x)
					if absf(a[axis] - line.y) < 0.01 and absf(b[axis] - line.y) < 0.01:
						inward[axis] = signf(center[axis] - line.y)
				var middle: Vector3 = (a + b) * 0.5
				if inward == Vector3.ZERO or a.distance_to(b) < 0.05:
					continue
				var mark: Vector3i = Vector3i((middle * 10.0).round())
				if seen.has(mark):
					continue
				seen[mark] = true
				stats.edges += 1
				var from: Vector3 = _snap(reference, middle + inward * STEP, SNAP_XZ)
				var to: Vector3 = _snap(reference, middle - inward * STEP, SNAP_XZ)
				if is_nan(from.x) or is_nan(to.x):
					stats.off += 1
					continue
				var verdict: String = _compare(new_map, reference, from, to)
				if verdict == "both":
					stats.both += 1
				elif verdict == "none":
					stats.none += 1
				else:
					_fail("[%s] шов у %s: %s" % [id, middle, verdict])
				if stats.edges % 200 == 0:
					await get_tree().process_frame
	print("[%s] швы: рёбер %d, проход в обеих раскладках %d, нет прохода в обеих %d, по ту сторону нет сетки %d" % [id,
		stats.edges, stats.both, stats.none, stats.off])


func _entries_to_exits(id: String, new_map: RID, reference: RID) -> void:
	var level: Node = (load(LEVELS[id]) as PackedScene).instantiate()
	var entries: Array[Vector3] = []
	var exits: Array[Vector3] = []
	var away: Array[String] = []
	for node: Node in level.find_children("*", "Node3D", true, false):
		if node is SpawnPoint or node is ExtractionPoint:
			var position: Vector3 = _position(node as Node3D)
			var snapped: Vector3 = _snap(reference, position, POINT_SNAP)
			if is_nan(snapped.x):
				away.append("%s %s" % [node.name, position])
			elif node is SpawnPoint:
				entries.append(snapped)
			else:
				exits.append(snapped)
	level.free()
	var reached: int = 0
	var lost: int = 0
	for entry: Vector3 in entries:
		for exit: Vector3 in exits:
			var verdict: String = _compare(new_map, reference, entry, exit, true)
			if verdict == "both" or verdict == "astar":
				reached += 1
			elif verdict == "none":
				lost += 1
				print("[%s]   нет пути и в эталоне: %s → %s" % [id, entry, exit])
			else:
				_fail("[%s] заход %s → выход %s: %s" % [id, entry, exit, verdict])
		await get_tree().process_frame
	if entries.is_empty() or exits.is_empty():
		_fail("[%s] в сцене нет заходов или выходов" % id)
	print("[%s] заходы → выходы: %d × %d, дошли в обеих %d, нет пути в обеих %d, вне сетки %s" % [id, entries.size(), exits.size(),
		reached, lost, str(away)])


func _random_pairs(id: String, definition: Dictionary, new_map: RID, reference: RID) -> void:
	var bounds: Array = definition.get("bounds")
	var random := RandomNumberGenerator.new()
	random.seed = hash(id)
	var stats: Dictionary = {"both": 0, "astar": 0, "none": 0}
	for pair in range(RANDOM_PAIRS):
		var ends: Array[Vector3] = []
		for end in range(2):
			var probe := Vector3(random.randf_range(float(bounds[0]), float(bounds[2])), 0.0, random.randf_range(float(bounds[1]), float(bounds[3])))
			ends.append(NavigationServer3D.map_get_closest_point(reference, probe))
		var verdict: String = _compare(new_map, reference, ends[0], ends[1], true)
		if stats.has(verdict):
			stats[verdict] += 1
		else:
			_fail("[%s] пара %s → %s: %s" % [id, ends[0], ends[1], verdict])
		if pair % 10 == 0:
			await get_tree().process_frame
	print("[%s] случайные пары: %d, дошли в обеих %d (другой коридор A* %d), нет пути в обеих %d" % [id, RANDOM_PAIRS,
		stats.both + stats.astar, stats.astar, stats.none])


## "both" — обе дошли, длины совпали; "none" — обе не дошли; иначе — описание расхождения. A* сервера не ищет
## кратчайший путь: при другом порядке многоугольников (два региона на тайл) по открытой площадке он может выбрать
## другой коридор. Для длинных путей (relaxed) длины сверяются ещё по лучшему из двух направлений — "astar".
func _compare(new_map: RID, reference: RID, from: Vector3, to: Vector3, relaxed: bool = false) -> String:
	var fresh: PackedVector3Array = NavigationServer3D.map_get_path(new_map, from, to, true)
	var old: PackedVector3Array = NavigationServer3D.map_get_path(reference, from, to, true)
	var fresh_reached: bool = not fresh.is_empty() and fresh[fresh.size() - 1].distance_to(to) < SNAP_XZ
	var old_reached: bool = not old.is_empty() and old[old.size() - 1].distance_to(to) < SNAP_XZ
	if fresh_reached != old_reached:
		return "дошёл: полосы %s, эталон %s" % [str(fresh_reached), str(old_reached)]
	if not fresh_reached:
		return "none"
	var fresh_length: float = _length(fresh)
	var old_length: float = _length(old)
	if absf(fresh_length - old_length) <= old_length * LENGTH_TOLERANCE + LENGTH_SLACK:
		return "both"
	if relaxed:
		var fresh_best: float = minf(fresh_length, _length(NavigationServer3D.map_get_path(new_map, to, from, true)))
		var old_best: float = minf(old_length, _length(NavigationServer3D.map_get_path(reference, to, from, true)))
		if absf(fresh_best - old_best) <= minf(fresh_best, old_best) * ASTAR_TOLERANCE + ASTAR_SLACK:
			return "astar"
	return "длина: полосы %.1f м, эталон %.1f м" % [fresh_length, old_length]


func _length(path: PackedVector3Array) -> float:
	var total: float = 0.0
	for index in range(1, path.size()):
		total += path[index - 1].distance_to(path[index])
	return total


## Ближайшая точка сетки, если она рядом с желаемой, иначе NaN.
func _snap(map: RID, point: Vector3, reach: float) -> Vector3:
	var closest: Vector3 = NavigationServer3D.map_get_closest_point(map, point)
	if Vector2(closest.x - point.x, closest.z - point.z).length() > reach or absf(closest.y - point.y) > maxf(SNAP_Y, reach):
		return Vector3(NAN, NAN, NAN)
	return closest


## Положение узла сцены, не добавленной в дерево.
func _position(node: Node3D) -> Vector3:
	var transform: Transform3D = node.transform
	var parent: Node = node.get_parent()
	while parent is Node3D:
		transform = (parent as Node3D).transform * transform
		parent = parent.get_parent()
	return transform.origin


func _fail(message: String) -> void:
	_failures += 1
	if _failures <= 40:
		push_error(message)
		print("ОШИБКА " + message)
