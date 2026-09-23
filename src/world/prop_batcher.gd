@tool
class_name PropBatcher
extends RefCounted
## Склейка мешей пропсов: тысячи мелких MeshInstance (каждая коробка на стеллаже — свой объект)
## превращаются в один меш на клетку сетки и материал. Без этого в прицеле, где камера видит
## на сотни метров, кадр упирается в 100+ тысяч вызовов отрисовки.
## Плоские цвета (SectorMaterials.flat) уходят в цвет вершин — материалов остаётся несколько.
## Коллизии и сами узлы пропов (StaticBody3D с именем-типом, по нему Surfaces узнаёт материал)
## остаются на месте — пропадают только их меши.


## Склеивает все MeshInstance3D под root. cell — размер клетки, м (чем меньше, тем точнее
## отсечение по экрану/дистанции, но больше объектов); vis_end — дальше этого клетка не рисуется.
## Возвращает число получившихся мешей.
static func batch(root: Node3D, cell: float, vis_end: float) -> int:
	var meshes: Array[MeshInstance3D] = []
	_collect(root, meshes)
	# ключ группы -> {arrays..., material}
	var groups: Dictionary = {}
	for mi in meshes:
		if mi.mesh == null:
			continue
		var xf := _relative_xform(mi, root)
		var c := Vector2i(floori(xf.origin.x / cell), floori(xf.origin.z / cell))
		for s in range(mi.mesh.get_surface_count()):
			var mat: Material = mi.material_override if mi.material_override else mi.mesh.surface_get_material(s)
			var color := Color.WHITE
			var key: String
			var out_mat: Material = mat
			var sm := mat as StandardMaterial3D
			if sm and sm.albedo_texture == null and not sm.vertex_color_use_as_albedo and sm.transparency == BaseMaterial3D.TRANSPARENCY_DISABLED:
				color = sm.albedo_color
				key = "%d,%d:vc:%.2f:%.2f" % [c.x, c.y, sm.roughness, sm.metallic]
				out_mat = SectorMaterials.flat_vc(sm.roughness, sm.metallic)
			else:
				key = "%d,%d:m%d" % [c.x, c.y, mat.get_instance_id() if mat else 0]
			if not groups.has(key):
				groups[key] = {"v": PackedVector3Array(), "n": PackedVector3Array(), "t": PackedFloat32Array(),
					"uv": PackedVector2Array(), "c": PackedColorArray(), "i": PackedInt32Array(), "mat": out_mat}
			_append(groups[key], mi.mesh.surface_get_arrays(s), xf, color)
		mi.get_parent().remove_child(mi)
		mi.free()
	var out := Node3D.new()
	out.name = "Batched"
	root.add_child(out)
	var made := 0
	for key in groups:
		var g: Dictionary = groups[key]
		# пустые поверхности (вырожденные примитивы) не дают меша
		if (g.v as PackedVector3Array).is_empty():
			continue
		made += 1
		var arr := []
		arr.resize(Mesh.ARRAY_MAX)
		arr[Mesh.ARRAY_VERTEX] = g.v
		arr[Mesh.ARRAY_NORMAL] = g.n
		arr[Mesh.ARRAY_TANGENT] = g.t
		arr[Mesh.ARRAY_TEX_UV] = g.uv
		arr[Mesh.ARRAY_COLOR] = g.c
		arr[Mesh.ARRAY_INDEX] = g.i
		var am := ArrayMesh.new()
		am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
		var mi := MeshInstance3D.new()
		mi.name = String(key).replace(":", "_").replace(",", "_").replace(".", "")
		mi.mesh = am
		mi.material_override = g.mat
		mi.visibility_range_end = vis_end
		mi.visibility_range_end_margin = 8.0
		out.add_child(mi)
	return made


static func _collect(n: Node, out: Array[MeshInstance3D]) -> void:
	for c in n.get_children():
		if c is MeshInstance3D:
			out.append(c)
		_collect(c, out)


## Трансформ узла относительно root по цепочке родителей — узлы ещё не в дереве сцены.
static func _relative_xform(n: Node3D, root: Node3D) -> Transform3D:
	var xf := n.transform
	var p := n.get_parent()
	while p != null and p != root:
		var p3 := p as Node3D
		if p3:
			xf = p3.transform * xf
		p = p.get_parent()
	return xf


## Дописывает поверхность в группу. Packed-массивы в словаре — значения: достаём, отвязываем
## (чтобы не копировать при каждой записи), дописываем и кладём обратно.
static func _append(g: Dictionary, a: Array, xf: Transform3D, color: Color) -> void:
	var gv: PackedVector3Array = g.v
	var gn: PackedVector3Array = g.n
	var gt: PackedFloat32Array = g.t
	var guv: PackedVector2Array = g.uv
	var gc: PackedColorArray = g.c
	var gi: PackedInt32Array = g.i
	g.v = PackedVector3Array()
	g.n = PackedVector3Array()
	g.t = PackedFloat32Array()
	g.uv = PackedVector2Array()
	g.c = PackedColorArray()
	g.i = PackedInt32Array()
	var verts: PackedVector3Array = a[Mesh.ARRAY_VERTEX]
	var base := gv.size()
	var nb := xf.basis.inverse().transposed()
	var normals: PackedVector3Array = a[Mesh.ARRAY_NORMAL] if a[Mesh.ARRAY_NORMAL] != null else PackedVector3Array()
	var tangents: PackedFloat32Array = a[Mesh.ARRAY_TANGENT] if a[Mesh.ARRAY_TANGENT] != null else PackedFloat32Array()
	var uvs: PackedVector2Array = a[Mesh.ARRAY_TEX_UV] if a[Mesh.ARRAY_TEX_UV] != null else PackedVector2Array()
	for k in range(verts.size()):
		gv.append(xf * verts[k])
		gn.append((nb * normals[k]).normalized() if normals.size() > k else Vector3.UP)
		if tangents.size() >= (k + 1) * 4:
			var tv := (xf.basis * Vector3(tangents[k * 4], tangents[k * 4 + 1], tangents[k * 4 + 2])).normalized()
			gt.append_array(PackedFloat32Array([tv.x, tv.y, tv.z, tangents[k * 4 + 3]]))
		else:
			gt.append_array(PackedFloat32Array([1.0, 0.0, 0.0, 1.0]))
		guv.append(uvs[k] if uvs.size() > k else Vector2.ZERO)
		gc.append(color)
	var idx: PackedInt32Array = a[Mesh.ARRAY_INDEX] if a[Mesh.ARRAY_INDEX] != null else PackedInt32Array()
	if idx.size() > 0:
		for i in idx:
			gi.append(base + i)
	else:
		for i in range(verts.size()):
			gi.append(base + i)
	g.v = gv
	g.n = gn
	g.t = gt
	g.uv = guv
	g.c = gc
	g.i = gi
