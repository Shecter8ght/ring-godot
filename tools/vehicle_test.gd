extends Node3D
## Транспорт (assets/models/ring_vehicles): одно статичное тело на корне, точные формы деталей внутри;
## пуля упирается в машину; навмеш под машиной вырезан на всю высоту корпуса (и у автобуса выше
## роста), в том числе у повёрнутой машины — а рядом с ней проходимо.
## godot --headless --path . res://tools/vehicle_test.tscn

const CARS := [["RING_bus_damaged", Vector3(-16, 0, 0), 0.0], ["RING_bus_worn", Vector3(0, 0, 0), 90.0],
	["RING_sedan_worn", Vector3(14, 0, -8), 30.0], ["RING_truck_worn", Vector3(14, 0, 10), -60.0]]

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	var geo := StaticBody3D.new()
	geo.add_to_group("nav_source")
	add_child(geo)
	var cs := CollisionShape3D.new()
	var sh := BoxShape3D.new()
	sh.size = Vector3(80, 1, 80)
	cs.shape = sh
	cs.position = Vector3(0, -0.5, 0)
	geo.add_child(cs)
	var cars: Array[Node3D] = []
	for c in CARS:
		var car := (load("res://assets/models/ring_vehicles/%s.gltf" % c[0]) as PackedScene).instantiate() as Node3D
		add_child(car)
		car.position = c[1]
		car.rotation_degrees.y = float(c[2])
		cars.append(car)
	var one := true
	for car in cars:
		var shapes := car.find_children("*", "CollisionShape3D", false, false)
		var bodies := car.find_children("*", "CollisionObject3D", true, false)
		one = one and car is StaticBody3D and not shapes.is_empty() and bodies.is_empty() and car.get_node_or_null("NavBlock") != null
	_check("у каждой машины статичное тело с формами деталей и след для навмеша", one, "")
	await get_tree().physics_frame
	var space := get_world_3d().direct_space_state
	var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(-30, 1.0, 0), Vector3(-2, 1.0, 0)))
	_check("пуля упирается в автобус", not hit.is_empty() and hit.collider == cars[0], str(hit.get("collider")))
	var sedan := cars[2]
	var above := space.intersect_ray(PhysicsRayQueryParameters3D.create(sedan.to_global(Vector3(0, 1.2, 3.0)), sedan.to_global(Vector3(0, 1.2, 1.0))))
	_check("над капотом седана нет невидимого объёма", above.is_empty(), str(above))
	var metal := space.intersect_ray(PhysicsRayQueryParameters3D.create(sedan.to_global(Vector3(0, 0.75, 3.0)), sedan.to_global(Vector3(0, 0.75, 1.0))))
	_check("в кузов седана луч попадает", not metal.is_empty() and metal.collider == sedan, str(metal.get("collider")))
	var region := NavigationRegion3D.new()
	var nm := NavigationMesh.new()
	nm.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	nm.geometry_collision_mask = Hitscan.LAYER_WORLD | Hitscan.LAYER_GLASS
	nm.geometry_source_geometry_mode = NavigationMesh.SOURCE_GEOMETRY_GROUPS_WITH_CHILDREN
	nm.geometry_source_group_name = "nav_source"
	nm.cell_size = 0.25
	nm.cell_height = 0.25
	nm.agent_height = 1.8
	nm.agent_radius = 0.5
	nm.agent_max_climb = 0.4
	region.navigation_mesh = nm
	add_child(region)
	region.bake_navigation_mesh(false)
	var map := get_world_3d().navigation_map
	for i in range(120):
		await get_tree().physics_frame
		if NavigationServer3D.map_get_iteration_id(map) > 0 and NavigationServer3D.map_get_closest_point(map, Vector3(30, 0, 30)).distance_to(Vector3(30, 0, 30)) < 1.0:
			break
	var bad: Array[String] = []
	for car in cars:
		var g := Vector3(car.position.x, 0.0, car.position.z)
		var near := NavigationServer3D.map_get_closest_point(map, g)
		if near.y < 1.0 and Vector2(near.x - g.x, near.z - g.z).length() < 0.8:
			bad.append(String(car.name))
	_check("под машинами (и под высокими) навмеша нет", bad.is_empty(), str(bad))
	# автобус под 90°: вдоль X ему 5 м от центра — внутри, вдоль Z — снаружи (не вырезано лишнее)
	var inside := NavigationServer3D.map_get_closest_point(map, Vector3(4.0, 0, 0))
	var outside := NavigationServer3D.map_get_closest_point(map, Vector3(0, 0, 4.0))
	_check("повёрнутый автобус вырезан по своему следу", Vector2(inside.x - 4.0, inside.z).length() > 0.8 and Vector2(outside.x, outside.z - 4.0).length() < 0.3,
		"в следе: ближайшая точка в %.1f м; рядом: %.1f м" % [Vector2(inside.x - 4.0, inside.z).length(), Vector2(outside.x, outside.z - 4.0).length()])
	print("vehicle_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
