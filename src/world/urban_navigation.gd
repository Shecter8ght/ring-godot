class_name UrbanNavigation
extends Node3D
## Навигация по тем же коллайдерам, что у SectorLevel, с заранее выпеченными тайлами.

signal ready_for_agents

const CACHE_DIR: String = "res://data/navigation/zone01"
## Сцены и компоненты, от которых зависит выпечка, для каждой карты (кэш сверяется по хэшам).
const SOURCES := {
	"zone01_mall": ["res://data/sectors/zone01_mall.json", "res://scenes/levels/zone01_mall.tscn", "res://scenes/levels/zone01",
		"res://data/terrain/zone01_heights.r32", "res://src/world/district_terrain.gd",
		"res://src/world/district_model.gd", "res://assets/zone01/nw/manifest.json", "res://assets/zone01/nw/furniture.json",
		# постройки, интерьеры и укрытия блокаутов (левел-дизайн) — тоже источник навигации
		"res://src/blockout/study_building.gd", "res://src/blockout/study_geometry.gd"],
}

var definition: Dictionary = {}
var save_cache: bool = false
var _bake_done: bool = false
var _map: RID
var _previous_cell: float = 0.25
var _previous_height: float = 0.25


func _config() -> Dictionary:
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
			cached = cached and ResourceLoader.exists(_path(x, z))
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
	for x in range(columns):
		for z in range(rows):
			var mesh: NavigationMesh
			if cached:
				mesh = load(_path(x, z)) as NavigationMesh
			else:
				mesh = _settings()
				var border: float = float(cfg.nav_border)
				mesh.border_size = border
				mesh.filter_baking_aabb = AABB(Vector3(float(bounds[0]) + float(x) * tile - border, -16, float(bounds[1]) + float(z) * tile - border), Vector3(tile + border * 2, 54, tile + border * 2))
				_bake_done = false
				NavigationServer3D.bake_from_source_geometry_data_async(mesh, source, _finished)
				while not _bake_done:
					await get_tree().process_frame
				_remove_submerged(mesh)
				if save_cache:
					var error: Error = ResourceSaver.save(mesh, _path(x, z))
					if error != OK:
						push_error("навигация: не сохранён " + _path(x, z))
				print("навигация: тайл %d/%d, полигонов %d" % [x * rows + z + 1, columns * rows, mesh.get_polygon_count()])
			var region := NavigationRegion3D.new()
			region.name = "Tile_%d_%d" % [x, z]
			region.navigation_mesh = mesh
			add_child(region)
			if mesh.get_polygon_count() > 0:
				var polygon: PackedInt32Array = mesh.get_polygon(mesh.get_polygon_count() / 2)
				var vertices: PackedVector3Array = mesh.get_vertices()
				if not polygon.is_empty():
					synchronization_samples.append(vertices[polygon[0]])
	if save_cache:
		_write_manifest()
	print("навигация: %d тайлов, %d мс, кэш %s" % [columns * rows, Time.get_ticks_msec() - start_ms, str(cached)])
	# Асинхронная синхронизация тридцати регионов может занимать больше одного физического кадра.
	var synchronization_start: int = Time.get_ticks_msec()
	var synchronization_frames: int = 0
	while NavigationServer3D.map_get_iteration_id(map) <= initial_iteration or not _map_contains_regions(map, synchronization_samples):
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
