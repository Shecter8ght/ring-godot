@tool
class_name DistrictPaving
extends StaticBody3D
## Полоса покрытия по ломаной в плане (мировые X, Z): асфальт проезда, тротуар, площадка.
## Ложится на рельеф DistrictTerrain (группа "district_terrain") с шагом 1 м, по краям — бетонный
## бордюр. Точки и ширину можно править в инспекторе — полоса перестраивается сразу.

@export var points: PackedVector2Array = PackedVector2Array():
	set(value):
		points = value
		_queue()
@export var width: float = 5.5:
	set(value):
		width = maxf(0.3, value)
		_queue()
## Высота бордюра над покрытием, м (0 — без бордюра).
@export var curb_height: float = 0.15:
	set(value):
		curb_height = maxf(0.0, value)
		_queue()
@export var lift: float = 0.05:
	set(value):
		lift = value
		_queue()
@export var material: Material:
	set(value):
		material = value
		_queue()
@export var curb_material: Material:
	set(value):
		curb_material = value
		_queue()
@export var surface: String = "asphalt"

const STEP: float = 1.0
const CURB_W: float = 0.15

var _pending: bool = false


func _ready() -> void:
	set_meta("surface", surface)
	_build.call_deferred()


func _queue() -> void:
	if not is_inside_tree() or _pending:
		return
	_pending = true
	_build.call_deferred()


func _height(terrain: Node, p: Vector2) -> float:
	if terrain and terrain.has_method("height_at"):
		return float(terrain.call("height_at", p.x, p.y)) - global_position.y
	return 0.0


func _build() -> void:
	_pending = false
	for child in get_children():
		if String(child.name).begins_with("_"):
			child.free()
	if points.size() < 2:
		return
	var terrain: Node = get_tree().get_first_node_in_group("district_terrain") if is_inside_tree() else null
	# сплошная осевая с шагом 1 м и нормалями на изломах (биссектриса — без щелей)
	var axis: PackedVector2Array = PackedVector2Array()
	for i in range(points.size() - 1):
		var a: Vector2 = points[i]
		var b: Vector2 = points[i + 1]
		var n: int = maxi(1, int(ceil(a.distance_to(b) / STEP)))
		for k in range(n):
			axis.append(a.lerp(b, float(k) / float(n)))
	axis.append(points[points.size() - 1])
	var sides: Array[Vector2] = []
	for i in range(axis.size()):
		var prev: Vector2 = axis[maxi(i - 1, 0)]
		var next: Vector2 = axis[mini(i + 1, axis.size() - 1)]
		var d: Vector2 = (next - prev).normalized()
		sides.append(Vector2(-d.y, d.x))
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var faces := PackedVector3Array()
	var half: float = width * 0.5
	var origin := Vector2(global_position.x, global_position.z)
	for i in range(axis.size() - 1):
		var quad: Array[Vector3] = []
		for k in [i, i + 1]:
			for s in [-1.0, 1.0]:
				var p: Vector2 = axis[k] + sides[k] * half * s
				quad.append(Vector3(p.x - origin.x, _height(terrain, p) + lift, p.y - origin.y))
		var tri := [quad[0], quad[2], quad[1], quad[1], quad[2], quad[3]]
		for v: Vector3 in tri:
			st.set_uv(Vector2(v.x + origin.x, v.z + origin.y))
			st.set_normal(Vector3.UP)
			st.add_vertex(v)
			faces.append(v)
	st.generate_tangents()
	var mi := MeshInstance3D.new()
	mi.name = "_Surface"
	mi.mesh = st.commit()
	if material:
		mi.material_override = material
	add_child(mi)
	var shape := ConcavePolygonShape3D.new()
	shape.set_faces(faces)
	var col := CollisionShape3D.new()
	col.name = "_Collision"
	col.shape = shape
	add_child(col)
	if curb_height > 0.0:
		_curbs(axis, sides, terrain, origin)


func _curbs(axis: PackedVector2Array, sides: Array[Vector2], terrain: Node, origin: Vector2) -> void:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	# грани бордюра — без сглаживания (иначе он круглый, как труба)
	st.set_smooth_group(0xFFFFFFFF)
	var half: float = width * 0.5
	for s in [-1.0, 1.0]:
		for i in range(axis.size() - 1):
			var pts: Array[Vector3] = []
			for k in [i, i + 1]:
				for off in [0.0, CURB_W]:
					var p: Vector2 = axis[k] + sides[k] * (half + off) * s
					pts.append(Vector3(p.x - origin.x, _height(terrain, p) + lift, p.y - origin.y))
			var up := Vector3(0, curb_height, 0)
			var down := Vector3(0, -0.25, 0)
			# верх, внутренняя и внешняя грани бордюра
			_quad(st, pts[0] + up, pts[2] + up, pts[3] + up, pts[1] + up, origin)
			_quad(st, pts[0] + down, pts[2] + down, pts[2] + up, pts[0] + up, origin)
			_quad(st, pts[1] + up, pts[3] + up, pts[3] + down, pts[1] + down, origin)
	st.generate_normals()
	st.generate_tangents()
	var mi := MeshInstance3D.new()
	mi.name = "_Curbs"
	mi.mesh = st.commit()
	if curb_material:
		mi.material_override = curb_material
	add_child(mi)


func _quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3, origin: Vector2) -> void:
	for v: Vector3 in [a, b, c, a, c, d]:
		var w := v + Vector3(origin.x, 0, origin.y)
		st.set_uv(Vector2(w.x + w.z, w.y) if absf((b - a).y) + absf((c - b).y) > 0.05 else Vector2(w.x, w.z))
		st.add_vertex(v)
