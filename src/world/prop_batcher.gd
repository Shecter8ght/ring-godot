@tool
class_name PropBatcher
extends RefCounted
## Склейка мешей пропсов: тысячи мелких MeshInstance (каждая коробка на стеллаже — свой объект)
## превращаются в MultiMesh на клетку сетки, форму и материал. Без этого в прицеле, где камера
## видит на сотни метров, кадр упирается в 100+ тысяч вызовов отрисовки.
## Пропсы собраны из примитивов (коробка, цилиндр, сфера): каждый становится экземпляром
## единичной формы с масштабом в трансформе и цветом экземпляра — пересчитывать вершины в
## скрипте не нужно (так уровень собирался 20 с). Плоские цвета (SectorMaterials.flat) уходят в
## цвет экземпляра — материалов остаётся несколько. Коллизии и узлы пропов (StaticBody3D с
## именем-типом, по нему Surfaces узнаёт материал) остаются — пропадают только их меши.

## Единичные формы: ключ -> Mesh.
static var _units: Dictionary = {}


## Склеивает все MeshInstance3D под root. cell — размер клетки, м; vis_end — дальше этого
## клетка не рисуется. Возвращает число получившихся MultiMesh.
static func batch(root: Node3D, cell: float, vis_end: float) -> int:
	var meshes: Array[MeshInstance3D] = []
	_collect(root, meshes)
	# ключ группы -> {mesh, mat, xforms: Array[Transform3D], colors: Array[Color]}
	var groups: Dictionary = {}
	for mi in meshes:
		var unit := _unit_for(mi.mesh)
		if unit.is_empty():
			continue
		var mat: Material = mi.material_override if mi.material_override else mi.mesh.surface_get_material(0)
		var xf := _relative_xform(mi, root) * Transform3D(Basis.from_scale(unit.scale), Vector3.ZERO)
		var c := Vector2i(floori(xf.origin.x / cell), floori(xf.origin.z / cell))
		var color := Color.WHITE
		var out_mat: Material = mat
		var mkey: String
		var sm := mat as StandardMaterial3D
		if sm and sm.albedo_texture == null and not sm.vertex_color_use_as_albedo and sm.transparency == BaseMaterial3D.TRANSPARENCY_DISABLED:
			color = sm.albedo_color
			mkey = "vc%.2f_%.2f" % [sm.roughness, sm.metallic]
			out_mat = SectorMaterials.flat_vc(sm.roughness, sm.metallic)
		else:
			mkey = "m%d" % (mat.get_instance_id() if mat else 0)
		var key := "%d_%d_%s_%s" % [c.x, c.y, unit.key, mkey]
		if not groups.has(key):
			groups[key] = {"mesh": unit.mesh, "mat": out_mat, "xforms": [], "colors": []}
		var g: Dictionary = groups[key]
		(g.xforms as Array).append(xf)
		(g.colors as Array).append(color)
		mi.get_parent().remove_child(mi)
		mi.free()
	var out := Node3D.new()
	out.name = "Batched"
	root.add_child(out)
	for key in groups:
		var g: Dictionary = groups[key]
		var xforms: Array = g.xforms
		var cols: Array = g.colors
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.mesh = g.mesh
		mm.instance_count = xforms.size()
		for i in range(xforms.size()):
			mm.set_instance_transform(i, xforms[i])
			mm.set_instance_color(i, cols[i])
		var mmi := MultiMeshInstance3D.new()
		mmi.name = String(key).replace(".", "")
		mmi.multimesh = mm
		mmi.material_override = g.mat
		mmi.visibility_range_end = vis_end
		mmi.visibility_range_end_margin = 8.0
		out.add_child(mmi)
	return groups.size()


## Единичная форма для примитива и масштаб до его размеров. Непримитив — пусто (не склеиваем).
static func _unit_for(mesh: Mesh) -> Dictionary:
	if mesh is BoxMesh:
		return {"key": "box", "mesh": _unit("box"), "scale": (mesh as BoxMesh).size}
	if mesh is CylinderMesh:
		var cy := mesh as CylinderMesh
		if not is_equal_approx(cy.top_radius, cy.bottom_radius):
			return {}
		var d := cy.top_radius * 2.0
		return {"key": "cyl%d" % cy.radial_segments, "mesh": _unit("cyl%d" % cy.radial_segments), "scale": Vector3(d, cy.height, d)}
	if mesh is SphereMesh:
		var sp := mesh as SphereMesh
		return {"key": "sph", "mesh": _unit("sph"), "scale": Vector3(sp.radius * 2.0, sp.height, sp.radius * 2.0)}
	return {}


static func _unit(key: String) -> Mesh:
	if _units.has(key):
		return _units[key]
	var m: PrimitiveMesh
	if key == "box":
		m = BoxMesh.new()
	elif key.begins_with("cyl"):
		var cy := CylinderMesh.new()
		cy.top_radius = 0.5
		cy.bottom_radius = 0.5
		cy.height = 1.0
		cy.radial_segments = int(key.trim_prefix("cyl"))
		cy.rings = 1
		m = cy
	else:
		var sp := SphereMesh.new()
		sp.radius = 0.5
		sp.height = 1.0
		sp.radial_segments = 16
		sp.rings = 8
		m = sp
	_units[key] = m
	return m


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
