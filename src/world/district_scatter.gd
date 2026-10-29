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
## Скан растительности (Poly Haven): материал GLB переводится в листву — отсечение по альфе,
## видно с обеих сторон, просвет на солнце, оттенок экземпляра (приглушённый, разный у кустов).
@export var foliage: bool = false
## Общий оттенок листвы (поздняя осень — желтее и тусклее скана).
@export var foliage_tint: Color = Color(1, 1, 1)
## Деревьям — коллизия ствола (цилиндр), траве — нет.
@export var trunk_radius: float = 0.0
## Высота цилиндра коллизии, м (ствол — 4, пень — меньше: выше пули проходят свободно).
@export var trunk_height: float = 4.0
## Дальний вид (два скрещённых силуэта, tools/build_spruce.py): дальше near_distance — он вместо модели.
@export_file("*.glb") var far_model: String = ""
@export var near_distance: float = 90.0
## Средний вид (LOD1: ветви толще, карточек меньше; tools/zone01_trees): от mid_distance до near_distance — он вместо модели.
@export_file("*.glb") var mid_model: String = ""
@export var mid_distance: float = 45.0
## Клетка дальнего вида, м (0 — как cell): силуэтов видно сотни, крупная клетка — меньше вызовов отрисовки.
@export var far_cell: float = 0.0
## Заслоняет ли россыпь свет в SDFGI. Да: без этого кроны и стволы освещены со всех сторон, как одиночное
## дерево в поле, — лес белёсый, «в инее» (проба 2026-10-19, владелец: цвет деревьев исказился). Нет —
## под кронами светлее, но сама листва без своей тени.
@export var gi_occluder: bool = true
## Точки — в координатах корня своей сцены (owner), а не мира: россыпь едет вместе со сценой,
## поставленной со сдвигом или поворотом (готовые куски зоны 1 на новых местах).
@export var local_points: bool = false:
	set(value):
		local_points = value
		_queue()

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
	var far_mesh: Mesh = _load_model(far_model) if far_model != "" else null
	var mid_mesh: Mesh = _load_model(mid_model) if mid_model != "" else null
	# дальше ближней модели — средняя (если есть), затем дальний вид
	var near_end: float = mid_distance if mid_mesh else (near_distance if far_mesh else view_distance)
	var mid_end: float = near_distance if far_mesh else view_distance
	var far_separate: bool = far_mesh != null and far_cell > cell
	var far_cells: Dictionary = {}
	# из координат точек — в координаты узла: мир минус положение узла или через корень сцены
	var to_node: Transform3D = Transform3D(Basis.IDENTITY, -global_position)
	if local_points and is_inside_tree():
		var frame: Node3D = owner as Node3D if owner is Node3D else get_parent_node_3d()
		if frame:
			to_node = global_transform.affine_inverse() * frame.global_transform
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
		mm.use_colors = model == "" or foliage
		mm.mesh = mesh
		mm.instance_count = list.size()
		for i in range(list.size()):
			var p: Array = list[i]
			var basis := Basis(Vector3.UP, deg_to_rad(float(p[3]))).scaled(Vector3.ONE * float(p[4]))
			mm.set_instance_transform(i, to_node * Transform3D(basis, Vector3(float(p[0]), float(p[1]), float(p[2]))))
			if mm.use_colors:
				# оттенок пучка: от выгоревшего до оливкового (из угла поворота — без лишних данных)
				var t: float = fposmod(float(p[3]) * 0.137, 1.0)
				var k: float = 0.85 + 0.3 * fposmod(float(p[3]) * 0.071, 1.0)
				if foliage:
					# скан: от своего цвета к пожухлому
					mm.set_instance_color(i, Color(1, 1, 1).lerp(Color(0.95, 0.82, 0.55), t) * k)
				else:
					mm.set_instance_color(i, Color(0.62, 0.6, 0.48).lerp(Color(0.5, 0.56, 0.36), t) * k)
			if body:
				var shape := CylinderShape3D.new()
				shape.radius = trunk_radius * float(p[4])
				shape.height = trunk_height * float(p[4])
				var col := CollisionShape3D.new()
				col.shape = shape
				col.position = to_node * Vector3(float(p[0]), float(p[1]) + trunk_height * float(p[4]) * 0.5, float(p[2]))
				body.add_child(col)
		var mmi := MultiMeshInstance3D.new()
		mmi.name = "_Cell_%d_%d" % [c.x, c.y]
		mmi.multimesh = mm
		mmi.visibility_range_end = near_end
		mmi.visibility_range_end_margin = 8.0 if (far_mesh or mid_mesh) else view_distance * 0.1
		mmi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mmi.gi_mode = GeometryInstance3D.GI_MODE_STATIC if gi_occluder else GeometryInstance3D.GI_MODE_DISABLED
		add_child(mmi)
		if mid_mesh:
			var md := MultiMesh.new()
			md.transform_format = MultiMesh.TRANSFORM_3D
			md.mesh = mid_mesh
			md.instance_count = mm.instance_count
			for i in range(mm.instance_count):
				md.set_instance_transform(i, mm.get_instance_transform(i))
			var mdi := MultiMeshInstance3D.new()
			mdi.name = "_Mid_%d_%d" % [c.x, c.y]
			mdi.multimesh = md
			mdi.visibility_range_begin = mid_distance
			mdi.visibility_range_begin_margin = 6.0
			mdi.visibility_range_end = mid_end
			mdi.visibility_range_end_margin = 8.0 if far_mesh else view_distance * 0.1
			mdi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
			mdi.cast_shadow = mmi.cast_shadow
			mdi.gi_mode = mmi.gi_mode
			add_child(mdi)
		if far_separate:
			# дальний вид — своей крупной клеткой (после обхода)
			for i in range(mm.instance_count):
				var t: Transform3D = mm.get_instance_transform(i)
				var fc := Vector2i(int(floor(float(list[i][0]) / far_cell)), int(floor(float(list[i][2]) / far_cell)))
				if not far_cells.has(fc):
					far_cells[fc] = []
				(far_cells[fc] as Array).append(t)
		elif far_mesh:
			var fm := MultiMesh.new()
			fm.transform_format = MultiMesh.TRANSFORM_3D
			fm.mesh = far_mesh
			fm.instance_count = mm.instance_count
			for i in range(mm.instance_count):
				fm.set_instance_transform(i, mm.get_instance_transform(i))
			var fmi := MultiMeshInstance3D.new()
			fmi.name = "_Far_%d_%d" % [c.x, c.y]
			fmi.multimesh = fm
			fmi.visibility_range_begin = near_distance
			fmi.visibility_range_begin_margin = 8.0
			fmi.visibility_range_end = view_distance
			fmi.visibility_range_end_margin = view_distance * 0.1
			fmi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
			fmi.cast_shadow = mmi.cast_shadow
			fmi.gi_mode = mmi.gi_mode
			add_child(fmi)
	for fc: Vector2i in far_cells:
		var ts: Array = far_cells[fc]
		var fm := MultiMesh.new()
		fm.transform_format = MultiMesh.TRANSFORM_3D
		fm.mesh = far_mesh
		fm.instance_count = ts.size()
		for i in range(ts.size()):
			fm.set_instance_transform(i, ts[i])
		var fmi := MultiMeshInstance3D.new()
		fmi.name = "_Far_%d_%d" % [fc.x, fc.y]
		fmi.multimesh = fm
		fmi.visibility_range_begin = near_distance
		fmi.visibility_range_begin_margin = 8.0
		fmi.visibility_range_end = view_distance
		fmi.visibility_range_end_margin = view_distance * 0.1
		fmi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		fmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		fmi.gi_mode = GeometryInstance3D.GI_MODE_STATIC if gi_occluder else GeometryInstance3D.GI_MODE_DISABLED
		add_child(fmi)


func _mesh() -> Mesh:
	if model != "":
		return _load_model(model)
	return _tuft()


## Первый меш модели; материалы — по именам слотов из materials_dir (или листва, если foliage).
func _load_model(path: String) -> Mesh:
	if path != "":
		if not ResourceLoader.exists(path):
			return null
		var inst: Node = (load(path) as PackedScene).instantiate()
		var found: Array[Node] = inst.find_children("*", "MeshInstance3D", true, false)
		if found.is_empty():
			inst.free()
			return null
		var src: Mesh = (found[0] as MeshInstance3D).mesh
		var mesh: Mesh = src.duplicate()
		for i in range(mesh.get_surface_count()):
			var mat: Material = mesh.surface_get_material(i)
			if foliage and mat is BaseMaterial3D:
				mesh.surface_set_material(i, _foliage_material(mat as BaseMaterial3D))
				continue
			if mat:
				var mat_path: String = "%s/%s.tres" % [materials_dir, mat.resource_name]
				if ResourceLoader.exists(mat_path):
					mesh.surface_set_material(i, load(mat_path))
		inst.free()
		return mesh
	return null


func _foliage_material(src: BaseMaterial3D) -> BaseMaterial3D:
	var m := src.duplicate() as BaseMaterial3D
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	m.alpha_scissor_threshold = 0.4
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.vertex_color_use_as_albedo = true
	m.albedo_color = foliage_tint
	m.backlight_enabled = true
	m.backlight = Color(0.18, 0.2, 0.1)
	# листва и трава почти не блестят: с бликом (0.5 по умолчанию) в пасмурно и в тумане ровное
	# светлое небо отражается в нормалях «вверх» — трава седеет, листья серебрятся
	m.metallic_specular = 0.12
	m.roughness = 1.0
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	return m


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
