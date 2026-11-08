@tool
extends EditorNode3DGizmoPlugin
## Щелчок по куску карты в окне 3D выделяет его узел (карты правятся руками, docs/level_editing.md). Вид кусков —
## дочерние сетки, которые узел строит сам (кусок улицы PlanPiece — невидимая коробка «_Pick», вещь PropSpot и дерево
## TreeSpot — «_Preview», лестница BlockoutStair — ступени); у сеток без хозяина в сцене редактор щелчок не ловит, поэтому
## у самого узла — «гизмо» с коробкой по габариту этих сеток (только для щелчка, без линий на экране).

const TYPES: Array[String] = ["PlanPiece", "PropSpot", "TreeSpot", "BlockoutStair"]


func _get_gizmo_name() -> String:
	return "Куски карты (щелчок)"


func _has_gizmo(for_node_3d: Node3D) -> bool:
	var s: Script = for_node_3d.get_script() as Script
	return s != null and String(s.get_global_name()) in TYPES


func _redraw(gizmo: EditorNode3DGizmo) -> void:
	gizmo.clear()
	var node: Node3D = gizmo.get_node_3d()
	if node == null:
		return
	var faces: PackedVector3Array = PackedVector3Array()
	for child: Node in node.get_children(true):
		var mi: MeshInstance3D = child as MeshInstance3D
		if mi == null or mi.mesh == null or not (String(mi.name).begins_with("_") or String(mi.name).begins_with("@")):
			continue
		_box_faces(faces, mi.transform * mi.mesh.get_aabb())
	if faces.is_empty():
		return
	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = faces
	var mesh: ArrayMesh = ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	gizmo.add_collision_triangles(mesh.generate_triangle_mesh())


## 12 треугольников коробки.
static func _box_faces(out: PackedVector3Array, box: AABB) -> void:
	var a: Vector3 = box.position
	var b: Vector3 = box.end
	var c: Array[Vector3] = [Vector3(a.x, a.y, a.z), Vector3(b.x, a.y, a.z), Vector3(b.x, a.y, b.z), Vector3(a.x, a.y, b.z),
		Vector3(a.x, b.y, a.z), Vector3(b.x, b.y, a.z), Vector3(b.x, b.y, b.z), Vector3(a.x, b.y, b.z)]
	for q: Array in [[0, 1, 2, 3], [7, 6, 5, 4], [0, 4, 5, 1], [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0]]:
		out.append_array(PackedVector3Array([c[q[0]], c[q[1]], c[q[2]], c[q[0]], c[q[2]], c[q[3]]]))
