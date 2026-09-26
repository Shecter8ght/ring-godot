@tool
extends EditorScenePostImport
## Импорт транспорта RING (assets/models/ring_vehicles/*.gltf; в .import — root_type StaticBody3D и
## этот скрипт). Коллизия «родительская»: корень модели — одно статичное тело на всю машину (или
## дверь), внутри — одна выпуклая оболочка по всем мешам, а не тело на каждую деталь. Корень — в
## группе nav_source: навмеш её обходит (мародёры объезжают), пули и перелезание в неё упираются.
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
	root.add_to_group("nav_source", true)
	return scene


## Положение меша относительно корня (узлы ещё не в дереве — global_transform нет).
func _to_root(n: Node3D, root: Node3D) -> Transform3D:
	var xf := Transform3D.IDENTITY
	var cur: Node = n
	while cur != null and cur != root:
		if cur is Node3D:
			xf = (cur as Node3D).transform * xf
		cur = cur.get_parent()
	return xf
