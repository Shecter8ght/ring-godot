@tool
class_name BlockoutMesh
extends RefCounted
## Сборка простых форм блокаута (коробки, пандусы) в SurfaceTool по материалам и выпуск
## в узлы с коллизией. Используют постройки вне кольца (BlockoutBuilding).

## SurfaceTool на материал.
var _st: Dictionary = {}


func st(mat_id: String) -> SurfaceTool:
	if not _st.has(mat_id):
		var s := SurfaceTool.new()
		s.begin(Mesh.PRIMITIVE_TRIANGLES)
		_st[mat_id] = s
	return _st[mat_id]


func is_empty() -> bool:
	return _st.is_empty()


## Коробка по центру и размеру (в локальных осях узла, куда потом выпустим меш).
func box(mat_id: String, center: Vector3, size: Vector3) -> void:
	var s := st(mat_id)
	var h := size * 0.5
	var c := [
		center + Vector3(-h.x, -h.y, -h.z), center + Vector3(h.x, -h.y, -h.z),
		center + Vector3(h.x, -h.y, h.z), center + Vector3(-h.x, -h.y, h.z),
		center + Vector3(-h.x, h.y, -h.z), center + Vector3(h.x, h.y, -h.z),
		center + Vector3(h.x, h.y, h.z), center + Vector3(-h.x, h.y, h.z),
	]
	_quad(s, c[4], c[5], c[6], c[7], Vector3.UP)
	_quad(s, c[3], c[2], c[1], c[0], Vector3.DOWN)
	_quad(s, c[0], c[1], c[5], c[4], Vector3.FORWARD)
	_quad(s, c[2], c[3], c[7], c[6], Vector3.BACK)
	_quad(s, c[3], c[0], c[4], c[7], Vector3.LEFT)
	_quad(s, c[1], c[2], c[6], c[5], Vector3.RIGHT)


## Пандус вдоль Z: от (z0, y0) до (z1, y1), ширина по X [x0, x1], толщина плиты t.
func ramp(mat_id: String, x0: float, x1: float, z0: float, z1: float, y0: float, y1: float, t: float) -> void:
	var s := st(mat_id)
	var a := Vector3(x0, y0, z0)
	var b := Vector3(x1, y0, z0)
	var c := Vector3(x1, y1, z1)
	var d := Vector3(x0, y1, z1)
	var down := Vector3.DOWN * t
	var slope := (d - a).cross(b - a).normalized()
	if slope.y < 0.0:
		slope = -slope
	# верх — по направлению обхода, чтобы нормаль смотрела вверх
	if (z1 - z0) > 0.0:
		_quad(s, a, b, c, d, slope)
		_quad(s, d + down, c + down, b + down, a + down, -slope)
	else:
		_quad(s, b, a, d, c, slope)
		_quad(s, c + down, d + down, a + down, b + down, -slope)
	_quad(s, a + down, a, d, d + down, Vector3.LEFT)
	_quad(s, b, b + down, c + down, c, Vector3.RIGHT)


## Четырёхугольник: вершины по кругу; порядок треугольников выбирается так, чтобы лицевая
## сторона смотрела по нормали n (Godot: лицевая — по часовой, если смотреть навстречу нормали).
func _quad(s: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3, n: Vector3) -> void:
	var face := (b - a).cross(c - a)
	var flip := face.dot(n) > 0.0
	var uv := func(p: Vector3) -> Vector2:
		return Vector2(p.x + p.y, p.z + p.y)
	for tri in ([[a, c, b], [a, d, c]] if flip else [[a, b, c], [a, c, d]]):
		for p in tri:
			s.set_normal(n)
			s.set_uv(uv.call(p))
			s.add_vertex(p)


## Выпускает меши в parent (статическое тело с trimesh-коллизией, если collide).
## cutaway — материал растворяется у камеры (стены), иначе — нет (полы, плиты).
func emit(parent: Node3D, body_name: String, collide: bool, cutaway: bool) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.name = body_name
	parent.add_child(body)
	for mat_id in _st:
		var s: SurfaceTool = _st[mat_id]
		s.generate_tangents()
		var mi := MeshInstance3D.new()
		mi.name = String(mat_id)
		mi.mesh = s.commit()
		mi.material_override = SectorMaterials.get_material(String(mat_id), cutaway)
		body.add_child(mi)
		if collide:
			var cs := CollisionShape3D.new()
			cs.name = String(mat_id) + "_col"
			cs.shape = (mi.mesh as ArrayMesh).create_trimesh_shape()
			body.add_child(cs)
	return body
