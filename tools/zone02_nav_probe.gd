extends SceneTree
## Диагностика рёбер кэша на сетке сшивки NavigationServer.

const RULES: Script = preload("res://src/core/balance.gd")


func _initialize() -> void:
	var edges: Dictionary = {}
	for x: int in range(6):
		for z: int in range(5):
			var mesh: NavigationMesh = load("res://data/navigation/zone02/tile_%d_%d.res" % [x, z]) as NavigationMesh
			var vertices: PackedVector3Array = mesh.get_vertices()
			for p: int in range(mesh.get_polygon_count()):
				var polygon: PackedInt32Array = mesh.get_polygon(p)
				for i: int in range(polygon.size()):
					var a: Vector3 = vertices[polygon[i]]
					var b: Vector3 = vertices[polygon[(i + 1) % polygon.size()]]
					var ka: String = _key(a)
					var kb: String = _key(b)
					var key: String = ka + "/" + kb if ka < kb else kb + "/" + ka
					if not edges.has(key):
						edges[key] = []
					(edges[key] as Array).append([x, z, p, a, b])
	var errors: int = 0
	for key: String in edges:
		if (edges[key] as Array).size() > 2:
			print("duplicate: ", edges[key])
			for entry: Array in edges[key]:
				var mesh: NavigationMesh = load("res://data/navigation/zone02/tile_%d_%d.res" % [entry[0], entry[1]]) as NavigationMesh
				var polygon: PackedInt32Array = mesh.get_polygon(int(entry[2]))
				var points: PackedVector3Array = PackedVector3Array()
				for index: int in polygon:
					points.append(mesh.get_vertices()[index])
				print("   polygon: ", points)
			errors += 1
	print("nav_probe: duplicates ", errors)
	quit(1 if errors > 0 else 0)


func _key(point: Vector3) -> String:
	var settings: Dictionary = RULES.URBAN_WORLD
	var cell: float = float(settings.nav_cell) * float(settings.nav_merge_scale)
	var height: float = float(settings.nav_height) * float(settings.nav_merge_scale)
	return str(Vector3i(roundi(point.x / cell), roundi(point.y / height), roundi(point.z / cell)))
