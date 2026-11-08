extends RefCounted
## Сборщик простых объёмов: одна поверхность на материал, отдельные простые коллизии.
## Детали остаются внутри именованного здания, поэтому его можно заменить целиком.
## У граней коробок в UV/UV2 — расстояния до рёбер, м (см. _edges): по ним шейдер бетона территории ТЦ
## (src/world/cast_concrete.gdshader) кладёт швы, грязь у земли и потёки от кромки. Серым материалам не мешают.

## Расстояние до рёбер у треугольников (рельеф, полосы по земле) — «далеко»: ни швов, ни грязи у кромки.
const FAR_EDGE_M: float = 9.0

var parent: Node3D
var body: StaticBody3D
var streams: Dictionary = {}
var palette: Dictionary = {}
## Из чего поверхность по ключу материала (Surfaces: шаги, попадания): у коллизии коробки и лестницы — meta "surface".
## Пусто — без меток, как раньше.
var surface_of: Dictionary = {}
var unit_vertices: PackedVector3Array
var unit_normals: PackedVector3Array
var unit_indices: PackedInt32Array
var triangles: int = 0

func _init(target: Node3D, materials: Dictionary) -> void:
	parent = target
	palette = materials
	body = StaticBody3D.new()
	body.name = "Collision"
	body.collision_layer = 1
	body.collision_mask = 0
	parent.add_child(body)
	var cube: BoxMesh = BoxMesh.new()
	cube.size = Vector3.ONE
	var arrays: Array = cube.get_mesh_arrays()
	unit_vertices = arrays[Mesh.ARRAY_VERTEX]
	unit_normals = arrays[Mesh.ARRAY_NORMAL]
	unit_indices = arrays[Mesh.ARRAY_INDEX]

func stream(key: String) -> SurfaceTool:
	if not streams.has(key):
		var st: SurfaceTool = SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		st.set_material(palette[key])
		streams[key] = st
	return streams[key] as SurfaceTool

func box(at: Vector3, size: Vector3, key: String, solid: bool = true, yaw: float = 0.0) -> void:
	var basis: Basis = Basis(Vector3.UP, yaw)
	var st: SurfaceTool = stream(key)
	for index: int in unit_indices:
		_edges(st, unit_vertices[index], unit_normals[index], size, 2)
		st.set_normal(basis * unit_normals[index])
		st.add_vertex(at + basis * (unit_vertices[index] * size))
	triangles += 12
	if solid:
		var shape: BoxShape3D = BoxShape3D.new()
		shape.size = size
		var cs: CollisionShape3D = CollisionShape3D.new()
		cs.shape = shape
		cs.position = at
		cs.rotation.y = yaw
		if surface_of.has(key):
			cs.set_meta("surface", surface_of[key])
		body.add_child(cs)

## Коробка с любым поворотом (узел сцены, правленный руками: повёрнут, наклонён, отражён): rot — поворот без масштаба,
## size — размер с учётом масштаба узла. across — ось «поперёк» для расстояний до рёбер (у box — 2, у beam — 0).
func box_basis(at: Vector3, rot: Basis, size: Vector3, key: String, solid: bool = true, across: int = 2) -> void:
	var st: SurfaceTool = stream(key)
	for index: int in unit_indices:
		_edges(st, unit_vertices[index], unit_normals[index], size, across)
		st.set_normal(rot * unit_normals[index])
		st.add_vertex(at + rot * (unit_vertices[index] * size))
	triangles += 12
	if solid:
		var shape: BoxShape3D = BoxShape3D.new()
		shape.size = size
		var cs: CollisionShape3D = CollisionShape3D.new()
		cs.shape = shape
		cs.transform = Transform3D(rot, at)
		if surface_of.has(key):
			cs.set_meta("surface", surface_of[key])
		body.add_child(cs)

func tri(a: Vector3, b: Vector3, c: Vector3, key: String) -> void:
	var st: SurfaceTool = stream(key)
	var normal: Vector3 = (c - a).cross(b - a).normalized()
	st.set_uv(Vector2(FAR_EDGE_M, FAR_EDGE_M))
	st.set_uv2(Vector2(FAR_EDGE_M, FAR_EDGE_M))
	if key == "water" and normal.y < 0.0:
		var swap: Vector3 = b
		b = c
		c = swap
		normal = -normal
	st.set_normal(normal)
	st.add_vertex(a)
	st.add_vertex(b)
	st.add_vertex(c)
	triangles += 1

func quad(a: Vector3, b: Vector3, c: Vector3, d: Vector3, key: String) -> void:
	tri(a, b, c, key)
	tri(a, c, d, key)

## visual = false — только коллизия (вид даёт модель на том же месте).
func beam(a: Vector3, b: Vector3, width: float, depth: float, key: String, solid: bool = false, visual: bool = true) -> void:
	var length_m: float = a.distance_to(b)
	if length_m < 0.001:
		return
	var basis: Basis = Basis.looking_at((b - a).normalized(), Vector3.UP)
	var size: Vector3 = Vector3(width, depth, length_m)
	var mid: Vector3 = (a + b) * 0.5
	if visual:
		var st: SurfaceTool = stream(key)
		for index: int in unit_indices:
			_edges(st, unit_vertices[index], unit_normals[index], size, 0)
			st.set_normal(basis * unit_normals[index])
			st.add_vertex(mid + basis * (unit_vertices[index] * size))
		triangles += 12
	if solid:
		var shape: BoxShape3D = BoxShape3D.new()
		shape.size = size
		var cs: CollisionShape3D = CollisionShape3D.new()
		cs.shape = shape
		cs.transform = Transform3D(basis, mid)
		body.add_child(cs)

## Расстояния до рёбер грани коробки (local — вершина единичного куба, normal — его грань, size — размер, м).
## Боковая грань: UV — до двух вертикальных рёбер, UV2 — от низа и до верха. Верх и низ: UV — до рёбер
## по оси across (поперёк стенки / по ходу ступени: у box — локальная Z, у beam — X), UV2 — вдоль другой оси.
## У соседних кусков с нахлёстом это одно и то же в нахлёсте — шейдер не мерцает.
func _edges(st: SurfaceTool, local: Vector3, normal: Vector3, size: Vector3, across: int) -> void:
	var k: Vector3 = local + Vector3(0.5, 0.5, 0.5)
	if absf(normal.y) > 0.5:
		var along: int = 2 - across
		st.set_uv(Vector2(k[across] * size[across], (1.0 - k[across]) * size[across]))
		st.set_uv2(Vector2(k[along] * size[along], (1.0 - k[along]) * size[along]))
	else:
		var h: int = 2 if absf(normal.x) > 0.5 else 0
		st.set_uv(Vector2(k[h] * size[h], (1.0 - k[h]) * size[h]))
		st.set_uv2(Vector2(k.y * size.y, (1.0 - k.y) * size.y))

func stairs(start: Vector3, finish: Vector3, width: float, count: int, key: String, visual: bool = true) -> void:
	# Ступени видны, физика идёт по наклонной поверхности без застревания капсулы (visual = false — только она).
	var delta: Vector3 = finish - start
	var flat: Vector3 = Vector3(delta.x, 0.0, delta.z)
	var direction: Vector3 = flat.normalized()
	var side: Vector3 = direction.cross(Vector3.UP) * width * 0.5
	var yaw: float = -atan2(direction.x, -direction.z)
	for i: int in range(count if visual else 0):
		var k: float = (float(i) + 0.5) / float(count)
		var at: Vector3 = start + flat * k
		at.y = start.y + delta.y * float(i + 1) / float(count) - 0.08
		box(at, Vector3(width, 0.16, flat.length() / float(count) + 0.01), key, false, yaw)
	var points: PackedVector3Array = PackedVector3Array([
		start - side - Vector3.UP * 0.18, start + side - Vector3.UP * 0.18,
		start - side, start + side, finish - side, finish + side,
		finish - side - Vector3.UP * 0.18, finish + side - Vector3.UP * 0.18])
	var shape: ConvexPolygonShape3D = ConvexPolygonShape3D.new()
	shape.points = points
	var cs: CollisionShape3D = CollisionShape3D.new()
	cs.shape = shape
	if surface_of.has(key):
		cs.set_meta("surface", surface_of[key])
	body.add_child(cs)

func collision_box(at: Vector3, size: Vector3) -> void:
	var shape: BoxShape3D = BoxShape3D.new()
	shape.size = size
	var cs: CollisionShape3D = CollisionShape3D.new()
	cs.shape = shape
	cs.position = at
	body.add_child(cs)

func finish() -> void:
	for key: String in streams:
		var mesh: ArrayMesh = (streams[key] as SurfaceTool).commit()
		var visual: MeshInstance3D = MeshInstance3D.new()
		visual.name = "Mesh_" + key
		visual.mesh = mesh
		parent.add_child(visual)
	parent.set_meta("triangles", triangles)

static func materials() -> Dictionary:
	var colors: Dictionary = {
		"concrete": Color("85877d"), "wall": Color("a0a093"), "slab": Color("777c76"),
		"dark": Color("343e3c"), "steel": Color("665c4e"), "rust": Color("8f7255"),
		"ground": Color("626a51"), "mud": Color("4f5949"), "water": Color("3e5658"),
		"road": Color("555a56"), "walk": Color("7b8072"), "court": Color("68776d"),
		"stripe": Color("b3b29a"), "bark": Color("606052"), "foliage": Color("3e5140"),
		"bus": Color("aaa88b"), "accent": Color("b09b73"), "marker": Color("a0bea2")}
	var result: Dictionary = {}
	for key: String in colors:
		var material: StandardMaterial3D = StandardMaterial3D.new()
		material.albedo_color = colors[key]
		material.roughness = 0.9
		if key == "water":
			material.roughness = 0.24
			material.metallic = 0.18
		result[key] = material
	return result
