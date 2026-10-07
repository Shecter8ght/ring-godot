@tool
class_name DistrictScatter
extends Node3D
## Россыпь одинаковых объектов MultiMesh-ами по клеткам (трава, деревья): точки — из JSON
## (их считает генератор района: x, y, z, поворот, масштаб), меш — из GLB (с материалами слотов)
## или пучок травы из карточек. Клетки отсекаются по видимости и дальности (visibility_range).

@export_file("*.json") var data_path: String = "":
	set(value):
		data_path = value
		_queue()
## Ключ списка точек в JSON.
@export var key: String = "":
	set(value):
		key = value
		_queue()
## Модель (GLB) — первый меш с материалами из materials_dir; пусто — пучок травы.
@export_file("*.glb") var model: String = "":
	set(value):
		model = value
		_queue()
@export_dir var materials_dir: String = "res://assets/zone01/materials"
@export var cell: float = 32.0
@export var view_distance: float = 120.0
@export var shadows: bool = true
## Деревьям — коллизия ствола (цилиндр), траве — нет.
@export var trunk_radius: float = 0.0
## Высота цилиндра коллизии, м (ствол — 4, пень — меньше: выше пули проходят свободно).
@export var trunk_height: float = 4.0

var _pending: bool = false


func _ready() -> void:
	_build()


func _queue() -> void:
	if not is_inside_tree() or _pending:
		return
	_pending = true
	_build.call_deferred()


func _build() -> void:
	_pending = false
	for child in get_children():
		if String(child.name).begins_with("_"):
			child.free()
	if data_path == "" or not FileAccess.file_exists(data_path):
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(data_path))
	if not parsed is Dictionary:
		return
	var points: Array = (parsed as Dictionary).get(key, [])
	if points.is_empty():
		return
	var mesh: Mesh = _mesh()
	if mesh == null:
		return
	var cells: Dictionary = {}
	for p: Array in points:
		var c := Vector2i(int(floor(float(p[0]) / cell)), int(floor(float(p[2]) / cell)))
		if not cells.has(c):
			cells[c] = []
		(cells[c] as Array).append(p)
	var body: StaticBody3D = null
	if trunk_radius > 0.0:
		body = StaticBody3D.new()
		body.name = "_Trunks"
		body.set_meta("surface", "wood")
		add_child(body)
	for c: Vector2i in cells:
		var list: Array = cells[c]
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = model == ""
		mm.mesh = mesh
		mm.instance_count = list.size()
		for i in range(list.size()):
			var p: Array = list[i]
			var basis := Basis(Vector3.UP, deg_to_rad(float(p[3]))).scaled(Vector3.ONE * float(p[4]))
			mm.set_instance_transform(i, Transform3D(basis, Vector3(float(p[0]), float(p[1]), float(p[2])) - global_position))
			if mm.use_colors:
				# оттенок пучка: от выгоревшего до оливкового (из угла поворота — без лишних данных)
				var t: float = fposmod(float(p[3]) * 0.137, 1.0)
				mm.set_instance_color(i, Color(0.62, 0.6, 0.48).lerp(Color(0.5, 0.56, 0.36), t) * (0.85 + 0.3 * fposmod(float(p[3]) * 0.071, 1.0)))
			if body:
				var shape := CylinderShape3D.new()
				shape.radius = trunk_radius * float(p[4])
				shape.height = trunk_height * float(p[4])
				var col := CollisionShape3D.new()
				col.shape = shape
				col.position = Vector3(float(p[0]), float(p[1]) + trunk_height * float(p[4]) * 0.5, float(p[2])) - global_position
				body.add_child(col)
		var mmi := MultiMeshInstance3D.new()
		mmi.name = "_Cell_%d_%d" % [c.x, c.y]
		mmi.multimesh = mm
		mmi.visibility_range_end = view_distance
		mmi.visibility_range_end_margin = view_distance * 0.1
		mmi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(mmi)


func _mesh() -> Mesh:
	if model != "":
		if not ResourceLoader.exists(model):
			return null
		var inst: Node = (load(model) as PackedScene).instantiate()
		var found: Array[Node] = inst.find_children("*", "MeshInstance3D", true, false)
		if found.is_empty():
			inst.free()
			return null
		var src: Mesh = (found[0] as MeshInstance3D).mesh
		var mesh: Mesh = src.duplicate()
		for i in range(mesh.get_surface_count()):
			var mat: Material = mesh.surface_get_material(i)
			if mat:
				var path: String = "%s/%s.tres" % [materials_dir, mat.resource_name]
				if ResourceLoader.exists(path):
					mesh.surface_set_material(i, load(path))
		inst.free()
		return mesh
	return _tuft()


## Пучок сухой травы: три карточки звездой, половина атласа по случаю (сухая / с зеленью).
func _tuft() -> Mesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for k in range(3):
		var a: float = float(k) * PI / 3.0 + 0.3
		var dx := Vector3(cos(a), 0, sin(a)) * 0.4
		# верх карточки чуть отклонён наружу — пучок раскрыт, а не «коробка»
		var tilt := Vector3(-sin(a), 0, cos(a)) * (0.12 if k % 2 == 0 else -0.12)
		var u0: float = 0.0 if k % 2 == 0 else 0.5
		var quad := [[-dx, Vector2(u0, 1)], [dx, Vector2(u0 + 0.5, 1)], [dx + tilt + Vector3(0, 0.6, 0), Vector2(u0 + 0.5, 0)], [-dx + tilt + Vector3(0, 0.6, 0), Vector2(u0, 0)]]
		for idx in [0, 1, 2, 0, 2, 3]:
			st.set_normal(Vector3.UP)
			st.set_uv(quad[idx][1])
			st.add_vertex(quad[idx][0])
	var mesh: ArrayMesh = st.commit()
	var path: String = materials_dir + "/GrassTuft.tres"
	if ResourceLoader.exists(path):
		mesh.surface_set_material(0, load(path))
	return mesh
