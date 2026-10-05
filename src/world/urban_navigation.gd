class_name UrbanNavigation
extends Node3D
## Навигация по тем же коллайдерам, что у SectorLevel, с заранее выпеченными тайлами.

signal ready_for_agents

const CACHE_DIR: String = "res://data/navigation/zone02"

var definition: Dictionary = {}
var save_cache: bool = false
var _bake_done: bool = false
var _map: RID
var _previous_cell: float = 0.25
var _previous_height: float = 0.25


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
	NavigationServer3D.map_set_cell_size(map, float(Balance.URBAN_WORLD.nav_cell))
	NavigationServer3D.map_set_cell_height(map, float(Balance.URBAN_WORLD.nav_height))
	NavigationServer3D.map_set_merge_rasterizer_cell_scale(map, float(Balance.URBAN_WORLD.nav_merge_scale))
	var bounds: Array = definition.get("bounds", [-750, -625, 750, 625])
	var tile: float = float(Balance.URBAN_WORLD.nav_tile)
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
			push_error("zone02: нет исходной геометрии для навигации")
			return
		if save_cache:
			DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(CACHE_DIR))
	var start_ms: int = Time.get_ticks_msec()
	for x in range(columns):
		for z in range(rows):
			var mesh: NavigationMesh
			if cached:
				mesh = load(_path(x, z)) as NavigationMesh
			else:
				mesh = _settings()
				var border: float = float(Balance.URBAN_WORLD.nav_border)
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
						push_error("zone02: не сохранён " + _path(x, z))
				print("zone02 nav: %d/%d, полигонов %d" % [x * rows + z + 1, columns * rows, mesh.get_polygon_count()])
			var region := NavigationRegion3D.new()
			region.name = "Tile_%d_%d" % [x, z]
			region.navigation_mesh = mesh
			add_child(region)
	if save_cache:
		_write_manifest()
	print("zone02: навигация %d тайлов, %d мс, кэш %s" % [columns * rows, Time.get_ticks_msec() - start_ms, str(cached)])
	# Асинхронная синхронизация тридцати регионов может занимать больше одного физического кадра.
	var synchronization_start: int = Time.get_ticks_msec()
	while NavigationServer3D.map_get_iteration_id(map) <= initial_iteration or not NavigationServer3D.map_get_closest_point_owner(map, Vector3.ZERO).is_valid():
		if Time.get_ticks_msec() - synchronization_start > 10000:
			push_error("zone02: сервер навигации не подготовил полигоны")
			return
		await get_tree().physics_frame
	ready_for_agents.emit()


func _path(x: int, z: int) -> String:
	return "%s/tile_%d_%d.res" % [CACHE_DIR, x, z]


func _cache_valid() -> bool:
	var path: String = CACHE_DIR + "/manifest.json"
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
	var paths: Array[String] = ["res://data/sectors/zone02_urban_belt.json", "res://scenes/levels/zone02_urban_belt.tscn"]
	for filename: String in DirAccess.get_files_at("res://scenes/levels/zone02"):
		if filename.get_extension() == "tscn":
			paths.append("res://scenes/levels/zone02/" + filename)
	for component: String in ["blockout_building", "blockout_opening", "blockout_mesh", "urban_props", "urban_road", "urban_terrain", "urban_facade", "urban_navigation"]:
		paths.append("res://src/world/" + component + ".gd")
		var scene_path: String = "res://scenes/world/" + component + ".tscn"
		if FileAccess.file_exists(scene_path):
			paths.append(scene_path)
	var hashes: Dictionary = {}
	for path: String in paths:
		hashes[path] = _source_hash(path)
	var file: FileAccess = FileAccess.open(CACHE_DIR + "/manifest.json", FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify({"settings": _settings_signature(), "files": hashes}, "\t") + "\n")
	else:
		push_error("zone02: не сохранён манифест навигации")


func _source_hash(path: String) -> String:
	# Git нормализует текст в LF: кэш не должен устаревать только из-за CRLF другой машины.
	return FileAccess.get_file_as_string(path).replace("\r\n", "\n").sha256_text()


func _settings_signature() -> Dictionary:
	var signature: Dictionary = {}
	for key: String in Balance.URBAN_WORLD:
		if key.begins_with("nav_"):
			signature[key] = Balance.URBAN_WORLD[key]
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
	mesh.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	mesh.geometry_collision_mask = Hitscan.LAYER_WORLD
	mesh.geometry_source_geometry_mode = NavigationMesh.SOURCE_GEOMETRY_GROUPS_WITH_CHILDREN
	mesh.geometry_source_group_name = "nav_source"
	mesh.cell_size = float(Balance.URBAN_WORLD.nav_cell)
	mesh.cell_height = float(Balance.URBAN_WORLD.nav_height)
	mesh.agent_height = ceilf(float(Balance.URBAN_WORLD.nav_agent_height) / mesh.cell_height) * mesh.cell_height
	mesh.agent_radius = float(Balance.URBAN_WORLD.nav_radius)
	mesh.agent_max_climb = floorf(float(Balance.URBAN_WORLD.nav_climb) / mesh.cell_height) * mesh.cell_height
	mesh.agent_max_slope = float(Balance.URBAN_WORLD.nav_slope)
	mesh.edge_max_error = 1.0
	mesh.detail_sample_max_error = float(Balance.URBAN_WORLD.nav_detail_error)
	mesh.region_min_size = 4.0
	mesh.region_merge_size = 12.0
	return mesh
