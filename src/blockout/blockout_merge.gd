class_name BlockoutMerge
extends RefCounted
## Склейка блокаута из узлов сцены, которые правят руками (docs/design/editable_levels.md): коробки CSGBox3D,
## цилиндры CSGCylinder3D, любые CSG с вырезами (запекаются), марши BlockoutStair, покрытия — MeshInstance3D
## с meta "blockout_mat". В игре всё это — один меш на материал и простые коллизии (study_geometry.gd), как было
## у генератора; исходные узлы убираются (free_sources). Деревья TreeSpot и проверки BlockoutChecks собираются
## списками — их разбирает уровень. Материал узла — ресурс из папки материалов карты: имя файла = ключ палитры
## (на ключ уровень может подставить свой материал, например покрытие улиц); чужой материал идёт как есть.

const Geometry = preload("res://src/blockout/study_geometry.gd")

var geometry: RefCounted
var palette: Dictionary
var materials_dir: String
## Материал без ключа (поставлен руками не из папки) → свой ключ палитры.
var _foreign: Dictionary = {}
var trees: Array[Node] = []
var checks: Array[Node] = []
var water: Array[Node] = []
var sources: Array[Node] = []
## Скрытые глазком в редакторе (вариант, который владелец пробует и отложил): в игре их нет — ни вида, ни коллизии,
## ни проверок; узлы убираются вместе с исходными.
var hidden: Array[Node] = []
var counts: Dictionary = {"boxes": 0, "stairs": 0, "cyls": 0, "csg": 0, "tris": 0}
## Узлы по видам — склейка идёт видами, в том же порядке, что у генератора (коробки, марши, ленты, цилиндры,
## покрытия): у физики фигуры одного тела в том же порядке, ходок на тесных площадках ведёт себя как раньше.
var _boxes: Array[Node] = []
var _stairs: Array[Node] = []
var _beams: Array[Node] = []
var _cyls: Array[Node] = []
var _other: Array[Node] = []
var _surfaces: Array[Node] = []
## Снимок склейки в прежнем формате плана генератора (коробки, марши, цилиндры, треугольники — в мире): его берут
## питоновские инструменты (замер обзора tools/sanatorium_ld_plan.py). Пишется, только если record = true.
var record: bool = false
var snapshot: Dictionary = {"mats": [], "boxes": [], "stairs": [], "beams": [], "cyls": [], "tris": {}}


func _init(target: Node3D, runtime_palette: Dictionary, dir: String) -> void:
	palette = runtime_palette
	materials_dir = dir.trim_suffix("/") + "/"
	geometry = Geometry.new(target, palette)


## Обойти узлы под root (вложенные сцены построек — тоже).
func collect(root: Node) -> void:
	for child: Node in root.get_children():
		if String(child.name).begins_with("_"):
			continue
		if child is Node3D and not (child as Node3D).visible:
			hidden.append(child)
			continue
		if child is CSGShape3D:
			sources.append(child)
			if (child as CSGShape3D).is_root_shape():
				if child is CSGBox3D and not child.has_meta("beam"):
					_boxes.append(child)
				elif child is CSGBox3D:
					_beams.append(child)
				elif child is CSGCylinder3D:
					_cyls.append(child)
				else:
					_other.append(child)
			continue
		if child is BlockoutStair:
			sources.append(child)
			_stairs.append(child)
			continue
		if child is MeshInstance3D and child.has_meta("blockout_mat"):
			sources.append(child)
			_surfaces.append(child)
			continue
		if child is TreeSpot:
			trees.append(child)
			continue
		if child is BlockoutChecks:
			checks.append(child)
			continue
		if child is MeshInstance3D and child.has_meta("water_body"):
			water.append(child)
		collect(child)


func finish() -> void:
	for n: Node in _boxes:
		_csg(n as CSGShape3D)
	for n: Node in _stairs:
		_stair(n as BlockoutStair)
	for n: Node in _beams:
		_csg(n as CSGShape3D)
	for n: Node in _cyls:
		_csg(n as CSGShape3D)
	for n: Node in _other:
		_csg(n as CSGShape3D)
	for n: Node in _surfaces:
		_surface(n as MeshInstance3D)
	geometry.call("finish")


## Убрать исходные узлы (вид уже в склейке). Вызывать после finish.
func free_sources() -> void:
	for n: Node in sources:
		if is_instance_valid(n):
			n.free()
	sources.clear()
	for n: Node in hidden:
		if is_instance_valid(n):
			n.free()
	hidden.clear()


func key_of(m: Material, fallback: String = "struct") -> String:
	if m == null:
		return fallback if palette.has(fallback) else String(palette.keys()[0])
	if m.resource_path.begins_with(materials_dir):
		var key: String = m.resource_path.get_file().get_basename()
		if palette.has(key):
			return key
	if not _foreign.has(m):
		var key2: String = "_m%d" % _foreign.size()
		_foreign[m] = key2
		palette[key2] = m
	return String(_foreign[m])


## Поворот без масштаба (отражённый узел — без отражения: коробке и цилиндру всё равно) и масштаб по осям.
static func split(basis: Basis) -> Array:
	var scale: Vector3 = basis.get_scale().abs()
	var rot: Basis = basis.orthonormalized()
	if rot.determinant() < 0.0:
		rot.x = -rot.x
	return [rot, scale]


func _csg(node: CSGShape3D) -> void:
	var simple: bool = node.operation == CSGShape3D.OPERATION_UNION and node.get_children().filter(
		func(c: Node) -> bool: return c is CSGShape3D).is_empty()
	var xf: Transform3D = node.global_transform
	var parts: Array = split(xf.basis)
	var rot: Basis = parts[0]
	var scale: Vector3 = parts[1]
	if simple and node is CSGBox3D:
		var box: CSGBox3D = node as CSGBox3D
		var bkey: String = key_of(box.material)
		geometry.call("box_basis", xf.origin, rot, box.size * scale, bkey, box.use_collision,
			0 if box.has_meta("beam") else 2)
		counts.boxes += 1
		if record:
			var sz: Vector3 = box.size * scale
			(snapshot.boxes as Array).append([_r(xf.origin.x), _r(xf.origin.y), _r(xf.origin.z), _r(sz.x), _r(sz.y), _r(sz.z),
				_r(rad_to_deg(atan2(rot.z.x, rot.z.z))), _mat_index(bkey), 1 if box.use_collision else 0])
		return
	if simple and node is CSGCylinder3D and not (node as CSGCylinder3D).cone:
		_cylinder(node as CSGCylinder3D, xf.origin, rot, scale)
		counts.cyls += 1
		return
	# вырезы и прочие формы — запечь сетку и коллизию
	var mesh: ArrayMesh = node.bake_static_mesh()
	if mesh != null:
		for s: int in range(mesh.get_surface_count()):
			var key: String = key_of(mesh.surface_get_material(s))
			_emit_arrays(mesh.surface_get_arrays(s), xf, key)
	if node.use_collision:
		var shape: ConcavePolygonShape3D = node.bake_collision_shape()
		if shape != null:
			var cs: CollisionShape3D = CollisionShape3D.new()
			cs.shape = shape
			cs.transform = xf
			(geometry.get("body") as StaticBody3D).add_child(cs)
	counts.csg += 1


## Цилиндр гранями (как у генератора: sides граней от оси +X, крышки), коллизия — цилиндр.
func _cylinder(node: CSGCylinder3D, center: Vector3, rot: Basis, scale: Vector3) -> void:
	var r: float = node.radius * maxf(scale.x, scale.z)
	var h: float = node.height * scale.y
	var key: String = key_of(node.material)
	var up: Vector3 = rot.y * h
	var base: Vector3 = center - up * 0.5
	if record:
		(snapshot.cyls as Array).append([_r(base.x), _r(base.y), _r(base.z), _r(r), _r(h), _mat_index(key),
			1 if node.use_collision else 0, node.sides])
	var sides: int = maxi(node.sides, 3)
	for i: int in range(sides):
		var a0: float = TAU * float(i) / float(sides)
		var a1: float = TAU * float(i + 1) / float(sides)
		var p0: Vector3 = base + (rot.x * cos(a0) + rot.z * sin(a0)) * r
		var p1: Vector3 = base + (rot.x * cos(a1) + rot.z * sin(a1)) * r
		geometry.call("quad", p0, p1, p1 + up, p0 + up, key)
		geometry.call("tri", base + up, p0 + up, p1 + up, key)
		geometry.call("tri", base, p1, p0, key)
	if node.use_collision:
		var shape: CylinderShape3D = CylinderShape3D.new()
		shape.radius = r
		shape.height = h
		var cs: CollisionShape3D = CollisionShape3D.new()
		cs.shape = shape
		cs.transform = Transform3D(rot, center)
		(geometry.get("body") as StaticBody3D).add_child(cs)


## Марш: ступени видом (сплошные до отметки — с коллизией), шаг — по наклонной (как у генератора).
func _stair(node: BlockoutStair) -> void:
	counts.stairs += 1
	var ends: Array[Vector3] = node.world_ends()
	var bottom: Vector3 = ends[0]
	var top: Vector3 = ends[1]
	var key: String = key_of(node.material, "stair")
	# масштаб марша руками: длина и подъём — уже в концах, ширина и низ сплошных ступеней — здесь
	var scale: Vector3 = split(node.global_transform.basis)[1]
	var width: float = node.width * scale.x
	var below: float = node.solid_bottom * scale.y
	if record:
		(snapshot.stairs as Array).append([_r(bottom.x), _r(bottom.y), _r(bottom.z), _r(top.x), _r(top.y), _r(top.z),
			_r(width), node.steps, _r(bottom.y + below) if node.solid else null, _mat_index(key)])
	if not node.solid:
		geometry.call("stairs", bottom, top, width, node.steps, key, true)
		return
	var fill: float = bottom.y + below
	var delta: Vector3 = top - bottom
	var flat: Vector3 = Vector3(delta.x, 0.0, delta.z)
	var direction: Vector3 = flat.normalized()
	var yaw: float = -atan2(direction.x, -direction.z)
	for i: int in range(node.steps):
		var k: float = (float(i) + 0.5) / float(node.steps)
		var tread: float = bottom.y + delta.y * float(i + 1) / float(node.steps)
		var at: Vector3 = bottom + flat * k
		var h: float = maxf(tread - fill, 0.05)
		at.y = tread - h * 0.5
		geometry.call("box", at, Vector3(width, h, flat.length() / float(node.steps) + 0.01), key, true, yaw)
	geometry.call("stairs", bottom, top, width, node.steps, key, false)


## Покрытие (асфальт, мощение, тропа, плотина вдали): треугольники сетки в склейку, твёрдое — с коллизией.
func _surface(node: MeshInstance3D) -> void:
	if node.mesh == null:
		return
	var key: String = String(node.get_meta("blockout_mat"))
	if not palette.has(key):
		key = key_of(node.mesh.surface_get_material(0) if node.mesh.get_surface_count() > 0 else null)
	var solid: bool = bool(node.get_meta("solid", false))
	var xf: Transform3D = node.global_transform
	var faces: PackedVector3Array = PackedVector3Array()
	for s: int in range(node.mesh.get_surface_count()):
		faces.append_array(_emit_arrays(node.mesh.surface_get_arrays(s), xf, key))
	if record:
		_mat_index(key)
		var tkey: String = "%s|%d" % [key, 1 if solid else 0]
		if not (snapshot.tris as Dictionary).has(tkey):
			snapshot.tris[tkey] = []
		for v: Vector3 in faces:
			(snapshot.tris[tkey] as Array).append_array([_r(v.x), _r(v.y), _r(v.z)])
	if solid and not faces.is_empty():
		var shape: ConcavePolygonShape3D = ConcavePolygonShape3D.new()
		shape.backface_collision = true
		shape.set_faces(faces)
		var cs: CollisionShape3D = CollisionShape3D.new()
		cs.shape = shape
		(geometry.get("body") as StaticBody3D).add_child(cs)


func _mat_index(key: String) -> int:
	var mats: Array = snapshot.mats
	var i: int = mats.find(key)
	if i < 0:
		mats.append(key)
		i = mats.size() - 1
	return i


static func _r(v: float) -> float:
	return snappedf(v, 0.001)


## Треугольники поверхности сетки в мир и в склейку; возвращает их вершины (для коллизии).
func _emit_arrays(arrays: Array, xf: Transform3D, key: String) -> PackedVector3Array:
	var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var index: Variant = arrays[Mesh.ARRAY_INDEX]
	var order: PackedInt32Array = index if index is PackedInt32Array and not (index as PackedInt32Array).is_empty() \
		else PackedInt32Array(range(verts.size()))
	var out: PackedVector3Array = PackedVector3Array()
	var i: int = 0
	while i + 2 < order.size():
		var a: Vector3 = xf * verts[order[i]]
		var b: Vector3 = xf * verts[order[i + 1]]
		var c: Vector3 = xf * verts[order[i + 2]]
		geometry.call("tri", a, b, c, key)
		out.append_array([a, b, c])
		counts.tris += 1
		i += 3
	return out
