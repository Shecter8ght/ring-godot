extends Node
## Стенд навигации на лестнице: наклонный марш (как StudyGeometry.stairs — выпуклая наклонная плита) разной ширины и
## уклона на ровных площадках, печёт навигацию теми же параметрами Balance.URBAN_WORLD и проверяет путь от низа к верху.
## Показывает, от чего рвётся навигация: узкий марш (эрозия радиуса) или крутой (подъём ячейки). Код выхода — 0.
##   tools/godot.cmd --headless res://tools/nav_stair_probe.tscn

const WIDTHS: Array = [1.1, 1.3, 1.6, 2.0, 2.4, 2.9, 4.0]
const ANGLES: Array = [19.0, 22.0, 25.0, 26.6, 28.0, 35.0]
const RUN_M := 8.0


func _ready() -> void:
	await get_tree().process_frame
	for mode: String in ["", "rails", "walls", "rails+carpet", "walls+carpet"]:
		print("PROBE | боковое ограждение: %s | ширина / уклон: %s" % [mode if mode != "" else "нет", "  ".join(ANGLES.map(func(a: Variant) -> String: return "%5.1f°" % float(a)))])
		for w: float in WIDTHS:
			var row: Array[String] = []
			for a: float in ANGLES:
				row.append(await _case(w, a, mode))
			print("PROBE | %.1f м: %s" % [w, "  ".join(row)])
	get_tree().quit(0)


## Поручни как у Prospekt._stair_rails (поручень 0,9 м и ригель 0,45 м над кромками, на RAIL_INSET_M от края марша).
func _rails(body: StaticBody3D, start: Vector3, finish: Vector3, width: float) -> void:
	for sgn: float in [-1.0, 1.0]:
		var off := Vector3(0.0, 0.0, sgn * (width * 0.5 - 0.18))
		for h: float in [0.9, 0.45]:
			var half: float = 0.025 if h > 0.5 else 0.015
			var pts := PackedVector3Array()
			for end: Vector3 in [start, finish]:
				for dz: float in [-half, half]:
					for dy: float in [-half, half]:
						pts.append(end + off + Vector3(0.0, h + dy, dz))
			var shape := ConvexPolygonShape3D.new()
			shape.points = pts
			var cs := CollisionShape3D.new()
			cs.shape = shape
			body.add_child(cs)


## Стены вплотную к маршу (шахта лестницы): плиты от пола до потолка.
func _walls(body: StaticBody3D, start: Vector3, finish: Vector3, width: float) -> void:
	for sgn: float in [-1.0, 1.0]:
		var off := Vector3(0.0, 0.0, sgn * (width * 0.5 + 0.1))
		var pts := PackedVector3Array()
		for end: Vector3 in [start, finish]:
			for dz: float in [-0.1, 0.1]:
				for dy: float in [-0.2, 4.0]:
					pts.append(end + off + Vector3(0.0, dy, dz))
		var shape := ConvexPolygonShape3D.new()
		shape.points = pts
		var cs := CollisionShape3D.new()
		cs.shape = shape
		body.add_child(cs)


func _case(width: float, angle: float, mode: String) -> String:
	var root := Node3D.new()
	add_child(root)
	var body := StaticBody3D.new()
	body.collision_layer = 1
	body.add_to_group("nav_source")
	root.add_child(body)
	var rise: float = RUN_M * tan(deg_to_rad(angle))
	# нижняя и верхняя площадки (по 10 м), марш по оси +X
	_box(body, Vector3(-5.0, -0.5, 0.0), Vector3(10.0, 1.0, 14.0))
	_box(body, Vector3(RUN_M + 5.0, rise - 0.5, 0.0), Vector3(10.0, 1.0, 14.0))
	var start := Vector3(0.0, 0.0, 0.0)
	var finish := Vector3(RUN_M, rise, 0.0)
	var side := Vector3(0.0, 0.0, width * 0.5)
	var shape := ConvexPolygonShape3D.new()
	shape.points = PackedVector3Array([start - side - Vector3.UP * 0.18, start + side - Vector3.UP * 0.18,
		start - side, start + side, finish - side, finish + side,
		finish - side - Vector3.UP * 0.18, finish + side - Vector3.UP * 0.18])
	var cs := CollisionShape3D.new()
	cs.shape = shape
	body.add_child(cs)
	if mode.begins_with("rails"):
		_rails(body, start, finish, width)
	elif mode.begins_with("walls"):
		_walls(body, start, finish, width)
	await get_tree().physics_frame
	await get_tree().physics_frame
	var cfg: Dictionary = Balance.URBAN_WORLD
	var mesh := NavigationMesh.new()
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
	var source := NavigationMeshSourceGeometryData3D.new()
	NavigationServer3D.parse_source_geometry_data(mesh, source, root)
	NavigationServer3D.bake_from_source_geometry_data(mesh, source)
	var map: RID = root.get_world_3d().navigation_map
	NavigationServer3D.map_set_cell_size(map, float(cfg.nav_cell))
	NavigationServer3D.map_set_cell_height(map, float(cfg.nav_height))
	var region := NavigationRegion3D.new()
	region.navigation_mesh = mesh
	root.add_child(region)
	for i in range(4):
		await get_tree().physics_frame
	if mode.ends_with("carpet"):
		StairNavigation.register(root, start, finish, width)
		await StairNavigation.build(root, map)
		for i in range(4):
			await get_tree().physics_frame
	var a: Vector3 = NavigationServer3D.map_get_closest_point(map, Vector3(-3.0, 0.0, 0.0))
	var b: Vector3 = NavigationServer3D.map_get_closest_point(map, Vector3(RUN_M + 3.0, rise, 0.0))
	var path: PackedVector3Array = NavigationServer3D.map_get_path(map, a, b, true)
	if mode == "rails+carpet" and width == 1.6 and (angle == 22.0 or angle == 25.0):
		var row: Dictionary = StairNavigation.report[0]
		print("PROBEDBG | %.0f° путь %s" % [angle, path])
		print("PROBEDBG |   низ %s → %s, верх %s → %s" % [row.low, row.low_to, row.high, row.high_to])
		print("PROBEDBG |   a→низ: %s; низ→верх: %s; верх→b: %s" % [_ends(map, a, row.low), _ends(map, row.low, row.high), _ends(map, row.high, b)])
	var ok: bool = not path.is_empty() and path[path.size() - 1].distance_to(b) < 0.6
	if width == WIDTHS[0] and angle == ANGLES[0]:
		print("PROBE контроль: полигонов %d, a %s, b %s, путь %d точек" % [mesh.get_polygon_count(), a, b, path.size()])
	root.queue_free()
	await get_tree().physics_frame
	return "  да  " if ok else "  --  "


func _box(body: StaticBody3D, at: Vector3, size: Vector3) -> void:
	var shape := BoxShape3D.new()
	shape.size = size
	var cs := CollisionShape3D.new()
	cs.shape = shape
	cs.position = at
	body.add_child(cs)


func _ends(map: RID, a: Vector3, b: Vector3) -> String:
	var path: PackedVector3Array = NavigationServer3D.map_get_path(map, a, b, true)
	if path.is_empty():
		return "пусто"
	return "до цели %.2f м, точек %d, конец %s" % [path[path.size() - 1].distance_to(b), path.size(), path[path.size() - 1]]
