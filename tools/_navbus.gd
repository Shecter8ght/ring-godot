extends Node3D
func _ready() -> void:
	await get_tree().process_frame
	var geo := StaticBody3D.new()
	geo.add_to_group("nav_source")
	add_child(geo)
	var cs := CollisionShape3D.new()
	var sh := BoxShape3D.new()
	sh.size = Vector3(60, 1, 60)
	cs.shape = sh
	cs.position = Vector3(0, -0.5, 0)
	geo.add_child(cs)
	var ids := ["RING_bus_damaged", "RING_sedan_worn", "RING_truck_worn"]
	# коробка размером с автобус для сравнения
	var bx := StaticBody3D.new()
	bx.add_to_group("nav_source")
	add_child(bx)
	bx.position = Vector3(0, 0, 18)
	var bcs := CollisionShape3D.new()
	var bsh := BoxShape3D.new()
	bsh.size = Vector3(2.9, 3.3, 10.8)
	bcs.shape = bsh
	bcs.position = Vector3(0, 1.6, 0)
	bx.add_child(bcs)
	for i in range(ids.size()):
		var car := (load("res://assets/models/ring_vehicles/%s.gltf" % ids[i]) as PackedScene).instantiate() as Node3D
		add_child(car)
		car.position = Vector3(-15 + 15 * i, 0.0, 0)
		var c := car.get_node("Collision") as CollisionShape3D
		var pts := (c.shape as ConvexPolygonShape3D).points
		var lo := 1e9
		var hi := -1e9
		for p in pts:
			lo = minf(lo, p.y)
			hi = maxf(hi, p.y)
		print(ids[i], " hull y ", lo, "..", hi, " groups ", car.get_groups(), " layer ", (car as CollisionObject3D).collision_layer)
	var region := NavigationRegion3D.new()
	var nm := NavigationMesh.new()
	nm.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	nm.geometry_collision_mask = 1 | 32
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
		if NavigationServer3D.map_get_iteration_id(map) > 0 and NavigationServer3D.map_get_closest_point(map, Vector3(0, 0, -20)).distance_to(Vector3(0, 0, -20)) < 1.0:
			break
	for i in range(ids.size()):
		var g := Vector3(-15 + 15 * i, 0, 0)
		print(ids[i], " closest ", NavigationServer3D.map_get_closest_point(map, g))
	print("box closest ", NavigationServer3D.map_get_closest_point(map, Vector3(0, 0, 18)))
	var verts := nm.get_vertices()
	for i in range(nm.get_polygon_count()):
		var poly := nm.get_polygon(i)
		var c := Vector3.ZERO
		for vi in poly:
			c += verts[vi]
		c /= poly.size()
		if absf(c.x + 15.0) < 2.0 and absf(c.z) < 6.0:
			print("poly near bus: ", c, " verts ", poly.size())
	get_tree().quit()
