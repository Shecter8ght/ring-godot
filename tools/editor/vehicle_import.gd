@tool
extends EditorScenePostImport
## Импорт транспорта RING (assets/models/ring_vehicles/*.gltf; в .import — root_type StaticBody3D и
## этот скрипт). Корень модели — одно статичное тело, внутри — формы статичных сеток LOD0, а не тело
## на каждую деталь и не выпуклая оболочка. Поэтому пули и зрение проходят там, где нет геометрии,
## а Climb находит настоящие капот и крышу. Корень — в группе nav_source.
## Навмеш печётся по поверхностям, не по объёму: под корпусом выше роста (автобус, грузовик) пол
## остался бы «проходимым». Поэтому ещё препятствие навигации (NavigationObstacle3D) по следу
## машины на земле — оно вырезает навмеш на всю высоту корпуса.
## Работает для любой расстановки модели в любой сцене — сцену уровня трогать не надо.
## Только редактор/импорт (compile_check папку tools/editor пропускает).


func _post_import(scene: Node) -> Object:
	var root := scene as Node3D
	if root == null:
		return scene
	var pts := PackedVector3Array()
	var count: int = 0
	for n in root.find_children("*", "MeshInstance3D", true, false):
		var mi := n as MeshInstance3D
		if mi.mesh == null or String(mi.name).contains("_LOD1") or String(mi.name).contains("_LOD2"):
			continue
		pts.append_array(_mesh_points(mi, _to_root(mi, root)))
		var shape := mi.mesh.create_trimesh_shape() as ConcavePolygonShape3D
		shape.backface_collision = true
		var cs := CollisionShape3D.new()
		cs.name = "Collision_%d" % count
		cs.shape = shape
		cs.transform = _to_root(mi, root)
		root.add_child(cs)
		cs.owner = root
		count += 1
	if pts.size() < 4 or count == 0:
		return scene
	_add_nav_block(root, pts)
	root.add_to_group("nav_source", true)
	return scene


## Все точки ближней сетки в координатах корня — для следа навигации.
func _mesh_points(mi: MeshInstance3D, xf: Transform3D) -> PackedVector3Array:
	var pts := PackedVector3Array()
	for surface in range(mi.mesh.get_surface_count()):
		var arrays: Array = mi.mesh.surface_get_arrays(surface)
		var vertices := arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array
		for p in vertices:
			pts.append(xf * p)
	return pts


## След машины на земле (выпуклая оболочка точек в плане) — препятствие при выпечке навмеша.
## Наклонённая модель (перевёрнутый остов) — след по её положению в сцене не известен заранее,
## поэтому в своих координатах; для лежащих на боку остовов это всё равно их габарит.
func _add_nav_block(root: Node3D, pts: PackedVector3Array) -> void:
	var flat := PackedVector2Array()
	var lo := INF
	var hi := -INF
	for p in pts:
		flat.append(Vector2(p.x, p.z))
		lo = minf(lo, p.y)
		hi = maxf(hi, p.y)
	var hull := Geometry2D.convex_hull(flat)
	if hull.size() < 4:
		return
	var verts := PackedVector3Array()
	# convex_hull замыкает контур первой точкой — её не повторять
	for i in range(hull.size() - 1):
		verts.append(Vector3(hull[i].x, 0.0, hull[i].y))
	var ob := NavigationObstacle3D.new()
	ob.name = "NavBlock"
	ob.position = Vector3(0.0, lo, 0.0)
	ob.height = hi - lo
	ob.vertices = verts
	ob.affect_navigation_mesh = true
	# навмеш отступает от машины на радиус агента, как от стен
	ob.carve_navigation_mesh = false
	ob.avoidance_enabled = false
	root.add_child(ob)
	ob.owner = root


## Положение меша относительно корня (узлы ещё не в дереве — global_transform нет).
func _to_root(n: Node3D, root: Node3D) -> Transform3D:
	var xf := Transform3D.IDENTITY
	var cur: Node = n
	while cur != null and cur != root:
		if cur is Node3D:
			xf = (cur as Node3D).transform * xf
		cur = cur.get_parent()
	return xf
