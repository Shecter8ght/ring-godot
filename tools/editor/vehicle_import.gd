@tool
extends EditorScenePostImport
## Импорт транспорта RING (assets/models/ring_vehicles/*.gltf; в .import — root_type StaticBody3D и
## этот скрипт). Коллизия «родительская»: корень модели — одно статичное тело на всю машину (или
## дверь), внутри — одна выпуклая оболочка по всем мешам, а не тело на каждую деталь. Корень — в
## группе nav_source: навмеш её обходит (мародёры объезжают), пули и перелезание в неё упираются.
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
	for n in root.find_children("*", "MeshInstance3D", true, false):
		var mi := n as MeshInstance3D
		if mi.mesh == null:
			continue
		var xf := _to_root(mi, root)
		# упрощённая оболочка каждой детали — точек мало, общая оболочка считается по ним
		var hull := mi.mesh.create_convex_shape(true, true)
		for p in hull.points:
			pts.append(xf * p)
	if pts.size() < 4:
		return scene
	var shape := ConvexPolygonShape3D.new()
	shape.points = pts
	var cs := CollisionShape3D.new()
	cs.name = "Collision"
	cs.shape = shape
	root.add_child(cs)
	cs.owner = root
	_add_nav_block(root, pts)
	root.add_to_group("nav_source", true)
	return scene


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
