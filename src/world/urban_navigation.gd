class_name UrbanNavigation
extends Node3D
## Навигация по тем же коллайдерам, что у SectorLevel, с заранее выпеченными тайлами.
## Тайл — два региона: полоса у швов с соседними тайлами (Seam_x_z) и всё остальное (Tile_x_z). Края тайлов
## по разные стороны шва бывают разбиты по-разному, их сшивают связи по краю, а их сервер сверяет попарно по
## всем свободным рёбрам карты: у ТЦ 45 тыс. рёбер — 6–9 с на каждую синхронизацию. Связи по краю включены
## только у полос (~2 тыс. рёбер, десятки мс), связность та же (tools/nav_seams_test.tscn).

signal ready_for_agents

const CACHE_DIR: String = "res://data/navigation/zone01"
## Сцены и компоненты, от которых зависит выпечка, для каждой карты (кэш сверяется по хэшам).
const SOURCES := {
	"zone01_mall": ["res://data/sectors/zone01_mall.json", "res://scenes/levels/zone01_mall.tscn", "res://scenes/levels/zone01",
		"res://data/terrain/zone01_heights.r32", "res://src/world/district_terrain.gd",
		"res://src/world/district_model.gd", "res://assets/zone01/nw/manifest.json", "res://assets/zone01/nw/furniture.json",
		# постройки, интерьеры и укрытия блокаутов (левел-дизайн) — тоже источник навигации
		"res://src/blockout/study_building.gd", "res://src/blockout/study_geometry.gd"],
	# территория ТЦ — серый черновик (tools/build_mall_study.py) внутри рейдового уровня
	"mall_map": ["res://data/sectors/mall_map.json", "res://scenes/levels/mall_map.tscn",
		"res://scenes/levels/mall_study.tscn", "res://data/blockouts/mall_study.json", "res://data/sectors/mall_1f.json",
		"res://src/blockout/mall_landscape.gd", "res://src/blockout/mall_ring.gd", "res://src/blockout/mall_filler.gd",
		"res://src/blockout/mall_streets.gd", "res://src/blockout/mall_park.gd",
		"res://src/blockout/study_building.gd", "res://src/blockout/study_geometry.gd"],
	# «Проспект» — серый блокаут (tools/build_prospekt.py) внутри рейдового уровня
	"prospekt": ["res://data/sectors/prospekt.json", "res://scenes/levels/prospekt.tscn",
		"res://scenes/levels/prospekt_study.tscn", "res://data/blockouts/prospekt.json", "res://data/urban95_models.json",
		"res://src/blockout/prospekt_landscape.gd", "res://src/blockout/mall_landscape.gd", "res://src/blockout/mall_filler.gd",
		"res://src/blockout/flat_section.gd", "res://src/blockout/study_building.gd", "res://src/blockout/study_geometry.gd"],
}

var definition: Dictionary = {}
var save_cache: bool = false
var _bake_done: bool = false
var _map: RID
var _previous_cell: float = 0.25
var _previous_height: float = 0.25


func _config() -> Dictionary:
	# ТЦ — обычная сетка: с точной (как у Пригорода) сервер не публиковал тайлы территории за отведённое время (2026-10-19)
	if String(definition.get("id", "")) == "zone01_mall":
		return Balance.URBAN_WORLD.merged(Balance.ZONE01_INTERIOR_NAV, true)
	return Balance.URBAN_WORLD


func _ready() -> void:
	_prepare.call_deferred()


func _exit_tree() -> void:
	if _map.is_valid():
		NavigationServer3D.map_set_cell_size(_map, _previous_cell)
		NavigationServer3D.map_set_cell_height(_map, _previous_height)
		NavigationServer3D.map_set_merge_rasterizer_cell_scale(_map, float(ProjectSettings.get_setting("navigation/3d/merge_rasterizer_cell_scale", 1.0)))


func _prepare() -> void:
	var map: RID = get_world_3d().navigation_map
	_map = map
	_previous_cell = NavigationServer3D.map_get_cell_size(map)
	_previous_height = NavigationServer3D.map_get_cell_height(map)
	var initial_iteration: int = NavigationServer3D.map_get_iteration_id(map)
	var cfg: Dictionary = _config()
	NavigationServer3D.map_set_cell_size(map, float(cfg.nav_cell))
	NavigationServer3D.map_set_cell_height(map, float(cfg.nav_height))
	NavigationServer3D.map_set_merge_rasterizer_cell_scale(map, float(cfg.nav_merge_scale))
	var bounds: Array = definition.get("bounds", [-750, -625, 750, 625])
	var tile: float = float(cfg.nav_tile)
	var columns: int = int(ceil((float(bounds[2]) - float(bounds[0])) / tile))
	var rows: int = int(ceil((float(bounds[3]) - float(bounds[1])) / tile))
	var cached: bool = not save_cache and _cache_valid()
	for x in range(columns):
		for z in range(rows):
			cached = cached and ResourceLoader.exists(_path(x, z)) and ResourceLoader.exists(_seam_path(x, z))
	var source := NavigationMeshSourceGeometryData3D.new()
	if not cached:
		# Дети сцены уже построили статические коллайдеры; физика догоняет их через кадр.
		await get_tree().physics_frame
		var parser: NavigationMesh = _settings()
		NavigationServer3D.parse_source_geometry_data(parser, source, get_parent().get_parent())
		if not source.has_data():
			push_error("навигация: нет исходной геометрии")
			return
		if save_cache:
			DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(_cache_dir()))
	var start_ms: int = Time.get_ticks_msec()
	var synchronization_samples := PackedVector3Array()
	# Тайлы попадают в карту разом после выпечки: каждый добавленный по ходу запускает полную синхронизацию
	# карты (секунды), её не прервать, и последняя начиналась бы с опозданием.
	var regions: Array[NavigationRegion3D] = []
	for x in range(columns):
		for z in range(rows):
			# [полоса у швов, остальное]
			var parts: Array[NavigationMesh] = []
			if cached:
				parts = [load(_seam_path(x, z)) as NavigationMesh, load(_path(x, z)) as NavigationMesh]
			else:
				var mesh: NavigationMesh = _settings()
				var border: float = float(cfg.nav_border)
				mesh.border_size = border
				mesh.filter_baking_aabb = AABB(Vector3(float(bounds[0]) + float(x) * tile - border, -16, float(bounds[1]) + float(z) * tile - border), Vector3(tile + border * 2, 54, tile + border * 2))
				_bake_done = false
				NavigationServer3D.bake_from_source_geometry_data_async(mesh, source, _finished)
				while not _bake_done:
					await get_tree().process_frame
				_remove_submerged(mesh)
				_fix_unset_heights(mesh, mesh.filter_baking_aabb.end.y)
				parts = _split_seams(mesh, x, z, columns, rows)
				if save_cache:
					var paths: Array[String] = [_seam_path(x, z), _path(x, z)]
					for index in range(paths.size()):
						if ResourceSaver.save(parts[index], paths[index]) != OK:
							push_error("навигация: не сохранён " + paths[index])
				print("навигация: тайл %d/%d, полигонов %d, у швов %d" % [x * rows + z + 1, columns * rows, mesh.get_polygon_count(), parts[0].get_polygon_count()])
			for index in range(parts.size()):
				var region := NavigationRegion3D.new()
				region.name = ("Seam_%d_%d" if index == 0 else "Tile_%d_%d") % [x, z]
				region.navigation_mesh = parts[index]
				# связи по краю нужны только на швах (см. описание класса)
				region.use_edge_connections = index == 0
				regions.append(region)
			var sample_mesh: NavigationMesh = parts[1] if parts[1].get_polygon_count() > 0 else parts[0]
			if sample_mesh.get_polygon_count() > 0:
				var polygon: PackedInt32Array = sample_mesh.get_polygon(sample_mesh.get_polygon_count() / 2)
				var vertices: PackedVector3Array = sample_mesh.get_vertices()
				if not polygon.is_empty():
					synchronization_samples.append(vertices[polygon[0]])
	for region: NavigationRegion3D in regions:
		add_child(region)
	if save_cache:
		_write_manifest()
	print("навигация: %d тайлов, %d мс, кэш %s" % [columns * rows, Time.get_ticks_msec() - start_ms, str(cached)])
	# Асинхронная синхронизация тридцати регионов может занимать больше одного физического кадра.
	var synchronization_start: int = Time.get_ticks_msec()
	var synchronization_frames: int = 0
	var last_iteration: int = NavigationServer3D.map_get_iteration_id(map)
	while NavigationServer3D.map_get_iteration_id(map) <= initial_iteration or not _map_contains_regions(map, synchronization_samples):
		# Сервер может выпустить карту в несколько итераций (регионы досинхронизируются вразнобой, каждая
		# итерация большой карты — секунды): срок считаем от последней выпущенной, ошибка — только если он встал.
		if NavigationServer3D.map_get_iteration_id(map) != last_iteration:
			last_iteration = NavigationServer3D.map_get_iteration_id(map)
			synchronization_start = Time.get_ticks_msec()
		# Первый кадр Forward+ может долго компилировать шейдеры. Даём серверу реальные
		# физические кадры на публикацию, даже если во время первого из них истёк таймер.
		if synchronization_frames >= 120 and Time.get_ticks_msec() - synchronization_start > int(float(cfg.publish_sec) * 1000.0):
			for sample: Vector3 in synchronization_samples:
				var closest: Vector3 = NavigationServer3D.map_get_closest_point(map, sample)
				if closest.distance_to(sample) > float(_config().nav_cell):
					push_warning("Навигация: не опубликована опора %s, ближайшая %s" % [sample, closest])
			push_error("навигация: сервер не подготовил полигоны")
			return
		await get_tree().physics_frame
		synchronization_frames += 1
	# ковры и связки лестниц (Balance.STAIR_NAV): сетка из кэша их не содержит, по крутым маршам без них не пройти
	await StairNavigation.build(self, map)
	# Низкие ограждения — связки «перелезть» у каждого тайла. Кэш содержит только поверхности,
	# поэтому связки строятся заново по физике уровня и только с посадкой на навигацию.
	var vault_links: int = 0
	for child: Node in get_children():
		var region := child as NavigationRegion3D
		if region:
			vault_links += await Vault.build_links(region, region)
	if vault_links > 0:
		await NavigationServer3D.map_changed
	print("навигация: связок «перелезть» %d" % vault_links)
	ready_for_agents.emit()


func _map_contains_regions(map: RID, samples: PackedVector3Array) -> bool:
	# Кэш добавляет все тайлы сразу. Первый готовый тайл ещё не означает готовность всей карты.
	for child: Node in get_children():
		if child is NavigationRegion3D:
			var region := child as NavigationRegion3D
			if region.navigation_mesh.get_polygon_count() > 0 and NavigationServer3D.region_get_iteration_id(region.get_rid()) == 0:
				return false
	for sample: Vector3 in samples:
		if NavigationServer3D.map_get_closest_point(map, sample).distance_to(sample) > float(_config().nav_cell):
			return false
	return not samples.is_empty()


func _cache_dir() -> String:
	return String(definition.get("nav_cache", CACHE_DIR))


func _path(x: int, z: int) -> String:
	return "%s/tile_%d_%d.res" % [_cache_dir(), x, z]


func _seam_path(x: int, z: int) -> String:
	return "%s/seam_%d_%d.res" % [_cache_dir(), x, z]


func _cache_valid() -> bool:
	var path: String = _cache_dir() + "/manifest.json"
	if not FileAccess.file_exists(path):
		return false
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not parsed is Dictionary:
		return false
	var manifest: Dictionary = parsed
	if manifest.get("settings", {}) != _settings_signature():
		return false
	var files: Dictionary = manifest.get("files", {})
	if files.is_empty():
		return false
	for source_path: String in files:
		# В экспорте текстовые сцены могут быть заменены бинарными ресурсами.
		if not FileAccess.file_exists(source_path) and not ResourceLoader.exists(source_path):
			return false
		if FileAccess.file_exists(source_path) and _source_hash(source_path) != String(files[source_path]):
			return false
	return true


func _write_manifest() -> void:
	var paths: Array[String] = []
	for source: String in SOURCES.get(String(definition.get("id", "zone01_mall")), SOURCES["zone01_mall"]):
		if source.get_extension() == "":
			for filename: String in DirAccess.get_files_at(source):
				if filename.get_extension() == "tscn":
					paths.append(source + "/" + filename)
		else:
			paths.append(source)
	for component: String in ["blockout_building", "blockout_opening", "blockout_mesh", "urban_props", "urban_road", "urban_navigation"]:
		paths.append("res://src/world/" + component + ".gd")
		var scene_path: String = "res://scenes/world/" + component + ".tscn"
		if FileAccess.file_exists(scene_path):
			paths.append(scene_path)
	var hashes: Dictionary = {}
	for path: String in paths:
		hashes[path] = _source_hash(path)
	var file: FileAccess = FileAccess.open(_cache_dir() + "/manifest.json", FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify({"settings": _settings_signature(), "files": hashes}, "\t") + "\n")
	else:
		push_error("навигация: не сохранён манифест")


func _source_hash(path: String) -> String:
	# Карта высот — двоичные float, её нельзя проверять как текст UTF-8.
	if path.get_extension() == "r32":
		return FileAccess.get_sha256(path)
	# Git нормализует текст в LF: кэш не должен устаревать только из-за CRLF другой машины.
	return FileAccess.get_file_as_string(path).replace("\r\n", "\n").sha256_text()


func _settings_signature() -> Dictionary:
	var signature: Dictionary = {}
	var cfg: Dictionary = _config()
	for key: String in cfg:
		if key.begins_with("nav_"):
			signature[key] = cfg[key]
	return signature


func _finished() -> void:
	_bake_done = true


func _remove_submerged(mesh: NavigationMesh) -> void:
	var vertices: PackedVector3Array = mesh.get_vertices()
	var polygons: Array[PackedInt32Array] = []
	var water_y: float = float((definition.get("river", {}) as Dictionary).get("surface_y", -8.0))
	for index in range(mesh.get_polygon_count()):
		var polygon: PackedInt32Array = mesh.get_polygon(index)
		var dry: bool = true
		for vertex in polygon:
			dry = dry and vertices[vertex].y > water_y
		if dry:
			polygons.append(polygon)
	mesh.clear_polygons()
	for polygon in polygons:
		mesh.add_polygon(polygon)


## Recast изредка оставляет точке детальной сетки «высоту не задана» (0xFFFF клеток — у ТЦ 16 368 м): многоугольник
## с ней тянется в небо, путь через него уводит точку пути вверх. Такой точке — среднюю высоту соседей по многоугольникам;
## соседей нет — многоугольник убираем.
func _fix_unset_heights(mesh: NavigationMesh, top: float) -> void:
	var vertices: PackedVector3Array = mesh.get_vertices()
	var sums: Dictionary = {}
	var counts: Dictionary = {}
	for index in range(mesh.get_polygon_count()):
		var polygon: PackedInt32Array = mesh.get_polygon(index)
		for vertex in polygon:
			if vertices[vertex].y <= top:
				continue
			for other in polygon:
				if vertices[other].y <= top:
					sums[vertex] = float(sums.get(vertex, 0.0)) + vertices[other].y
					counts[vertex] = int(counts.get(vertex, 0)) + 1
	var fixed: int = 0
	for vertex: int in counts:
		var point: Vector3 = vertices[vertex]
		point.y = float(sums[vertex]) / float(counts[vertex])
		vertices[vertex] = point
		fixed += 1
	var polygons: Array[PackedInt32Array] = []
	for index in range(mesh.get_polygon_count()):
		var polygon: PackedInt32Array = mesh.get_polygon(index)
		var sane: bool = true
		for vertex in polygon:
			sane = sane and vertices[vertex].y <= top
		if sane:
			polygons.append(polygon)
	if fixed == 0 and polygons.size() == mesh.get_polygon_count():
		return
	print("навигация: точек без высоты %d, убрано многоугольников %d" % [fixed, mesh.get_polygon_count() - polygons.size()])
	mesh.vertices = vertices
	mesh.clear_polygons()
	for polygon in polygons:
		mesh.add_polygon(polygon)


## Тайл → [многоугольники у швов с соседними тайлами (хоть одна точка ближе nav_seam_band), остальные],
## у каждой части только свои точки.
func _split_seams(mesh: NavigationMesh, x: int, z: int, columns: int, rows: int) -> Array[NavigationMesh]:
	var cfg: Dictionary = _config()
	var bounds: Array = definition.get("bounds", [-750, -625, 750, 625])
	var tile: float = float(cfg.nav_tile)
	var band: float = float(cfg.nav_seam_band)
	var x0: float = float(bounds[0]) + float(x) * tile
	var z0: float = float(bounds[1]) + float(z) * tile
	# швы с соседями: (ось, координата линии)
	var seams: Array[Vector2] = []
	if x > 0:
		seams.append(Vector2(Vector3.AXIS_X, x0))
	if x < columns - 1:
		seams.append(Vector2(Vector3.AXIS_X, x0 + tile))
	if z > 0:
		seams.append(Vector2(Vector3.AXIS_Z, z0))
	if z < rows - 1:
		seams.append(Vector2(Vector3.AXIS_Z, z0 + tile))
	var vertices: PackedVector3Array = mesh.get_vertices()
	var near := PackedByteArray()
	near.resize(vertices.size())
	for index in range(vertices.size()):
		for seam: Vector2 in seams:
			if absf(vertices[index][int(seam.x)] - seam.y) < band:
				near[index] = 1
	var part_vertices: Array[PackedVector3Array] = [PackedVector3Array(), PackedVector3Array()]
	var part_polygons: Array = [[], []]
	var remap: Array[PackedInt32Array] = [PackedInt32Array(), PackedInt32Array()]
	for part in range(2):
		remap[part].resize(vertices.size())
		remap[part].fill(-1)
	for index in range(mesh.get_polygon_count()):
		var polygon: PackedInt32Array = mesh.get_polygon(index)
		var part: int = 1
		for vertex in polygon:
			if near[vertex] == 1:
				part = 0
		var local := PackedInt32Array()
		for vertex in polygon:
			if remap[part][vertex] < 0:
				remap[part][vertex] = part_vertices[part].size()
				part_vertices[part].append(vertices[vertex])
			local.append(remap[part][vertex])
		(part_polygons[part] as Array).append(local)
	var parts: Array[NavigationMesh] = []
	for part in range(2):
		var piece: NavigationMesh = _settings()
		piece.vertices = part_vertices[part]
		for polygon: PackedInt32Array in part_polygons[part]:
			piece.add_polygon(polygon)
		parts.append(piece)
	return parts


func _settings() -> NavigationMesh:
	var mesh := NavigationMesh.new()
	var cfg: Dictionary = _config()
	mesh.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	mesh.geometry_collision_mask = Hitscan.LAYER_WORLD
	mesh.geometry_source_geometry_mode = NavigationMesh.SOURCE_GEOMETRY_GROUPS_WITH_CHILDREN
	mesh.geometry_source_group_name = "nav_source"
	mesh.cell_size = float(cfg.nav_cell)
	mesh.cell_height = float(cfg.nav_height)
	mesh.agent_height = ceilf(float(cfg.nav_agent_height) / mesh.cell_height) * mesh.cell_height
	mesh.agent_radius = float(cfg.nav_radius)
	mesh.agent_max_climb = floorf(float(cfg.nav_climb) / mesh.cell_height) * mesh.cell_height
	mesh.agent_max_slope = float(cfg.nav_slope)
	mesh.edge_max_error = 1.0
	mesh.detail_sample_max_error = float(cfg.nav_detail_error)
	mesh.region_min_size = 4.0
	mesh.region_merge_size = 12.0
	return mesh
