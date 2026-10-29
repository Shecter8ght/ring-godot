extends RefCounted
## CPU VoxelGI cannot evaluate dorm_finish.gdshader. Supply its same diffuse colors
## only during synchronous bake(), then restore the original mesh before any frame.
## The rendered geometry, shader, collision and base colors remain untouched.
## Материалы v03 (meta "dorm_gi", src/blockout/dorm_v3) подменяются своими средними цветами (замер по кадрам Blender;
## мозаика лестницы — среднее карты Terrazzo005 с подкраской и грязью).
const VERSION = "dorm_v3_diffuse_proxy_6_stairs"
const V3_COLORS: Dictionary = {"paint":"5b6b58","wash":"c3bfb3","reveal":"c3bfb3","ceiling":"b9b4a8","floor":"4d3a2b",
	"tile":"beb9ab","tile_floor":"6c5343","stair_landing":"6a645c","stair_tread":"6a645c"}
var plan: Dictionary
var saved: Array[Dictionary] = []
var materials: Dictionary = {}
var cuts: Array[float] = []
var triangles: int = 0

func _init(value: Dictionary) -> void:
	plan = value
	for f: int in range(plan.scale.floor_y.size()):
		cuts.append(float(plan.scale.floor_y[f])-.001)
		cuts.append(float(plan.scale.floor_y[f])+float(plan.scale.ceiling_clear[f])*2.0/3.0)
	cuts.sort()
	_add_material("green",Color(String(plan.finish.green)))
	_add_material("white",Color(String(plan.finish.white)))
	_add_material("exterior",Color(.396,.418,.434).linear_to_srgb())
	# Mean of the existing procedural tile and its 2%-wide grout lines, in linear light.
	_add_material("tile",(Color(.73,.78,.74).srgb_to_linear()*.99).lerp(Color(.29,.32,.29),.0396).linear_to_srgb())
	_add_material("tile_floor",(Color("939d94").srgb_to_linear()*.99).lerp(Color(.29,.32,.29),.0396).linear_to_srgb())
	for key: String in V3_COLORS:_add_material("v3_"+key,Color(String(V3_COLORS[key])))

func begin(root: Node) -> void:
	for child: Node in root.get_children():
		if child is MeshInstance3D:
			var instance: MeshInstance3D = child as MeshInstance3D
			if instance.gi_mode==GeometryInstance3D.GI_MODE_STATIC and instance.mesh!=null:
				var replacement: ArrayMesh = _proxy(instance)
				if replacement!=null:
					saved.append({"instance":instance,"mesh":instance.mesh})
					instance.mesh = replacement
		begin(child)

func restore() -> void:
	for record: Dictionary in saved:(record.instance as MeshInstance3D).mesh = record.mesh as Mesh
	saved.clear()

func _add_material(key: String, color: Color) -> void:
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = color
	materials[key] = material

func _proxy(instance: MeshInstance3D) -> ArrayMesh:
	var original: Mesh = instance.mesh
	var uses_finish: bool = false
	for s: int in range(original.get_surface_count()):
		if instance.get_active_material(s) is ShaderMaterial:uses_finish = true
	if not uses_finish:return null
	var result: ArrayMesh = ArrayMesh.new()
	var buckets: Dictionary = {}
	for s: int in range(original.get_surface_count()):
		var material: Material = instance.get_active_material(s)
		var arrays: Array = original.surface_get_arrays(s)
		if not material is ShaderMaterial:
			result.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
			result.surface_set_material(result.get_surface_count()-1,material)
			continue
		var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
		var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX] if arrays[Mesh.ARRAY_INDEX]!=null else PackedInt32Array()
		var count: int = indices.size() if not indices.is_empty() else vertices.size()
		var v3: String = String(material.get_meta("dorm_gi","")) if material.has_meta("dorm_gi") else ""
		var finish_mode: Variant = (material as ShaderMaterial).get_shader_parameter("finish_mode")
		if v3=="" and finish_mode==null:
			# Краска модулей (dorm_module_paint.gdshader) — своим цветом; иной шейдер — как есть.
			var paint: Variant = (material as ShaderMaterial).get_shader_parameter("paint")
			var proxy: StandardMaterial3D = null
			if paint is Color:
				proxy = StandardMaterial3D.new()
				proxy.albedo_color = (paint as Color)*0.85
			result.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
			result.surface_set_material(result.get_surface_count()-1,proxy if proxy!=null else material)
			continue
		var tile: bool = v3!="wall" and (v3!="" or int(finish_mode)>0)
		for face: int in range(0,count,3):
			var polygon: Array[Vector3] = []
			var normal: Vector3 = Vector3.UP
			for corner: int in range(3):
				var index: int = indices[face+corner] if not indices.is_empty() else face+corner
				polygon.append(instance.global_transform*vertices[index])
				if corner==0 and index<normals.size():normal = normals[index]
			var polygons: Array = [polygon]
			if not tile:
				for cut: float in cuts:
					var split: Array = []
					for piece: Array[Vector3] in polygons:split.append_array(_split(piece,cut))
					polygons = split
			for piece: Array[Vector3] in polygons:
				var center: Vector3 = Vector3.ZERO
				for vertex: Vector3 in piece:center += vertex
				center /= piece.size()
				var key: String = ("tile_floor" if String(instance.name).begins_with("Mesh_tile_floor") else "tile") if tile else _wall_color(center)
				if v3!="":
					key = "v3_"+v3 if v3!="wall" else {"green":"v3_paint","white":"v3_wash","exterior":"exterior"}[key]
				if not buckets.has(key):buckets[key] = {"vertices":PackedVector3Array(),"normals":PackedVector3Array()}
				var bucket: Dictionary = buckets[key]
				var out_vertices: PackedVector3Array = bucket.vertices
				var out_normals: PackedVector3Array = bucket.normals
				for j: int in range(1,piece.size()-1):
					if (piece[j]-piece[0]).cross(piece[j+1]-piece[0]).length_squared()<1e-14:continue
					for vertex: Vector3 in [piece[0],piece[j],piece[j+1]]:
						out_vertices.append(instance.global_transform.affine_inverse()*vertex)
						out_normals.append(normal)
					triangles += 1
				bucket.vertices = out_vertices;bucket.normals = out_normals
	for key: String in buckets:
		var arrays: Array = []
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = buckets[key].vertices
		arrays[Mesh.ARRAY_NORMAL] = buckets[key].normals
		result.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
		result.surface_set_material(result.get_surface_count()-1,materials[key])
	return result

func _wall_color(at: Vector3) -> String:
	if not _inside(at,plan.main_rect) and not _inside(at,plan.annex_rect):return "exterior"
	var floor_index: int = 0
	for f: int in range(1,plan.scale.floor_y.size()):
		if at.y>=float(plan.scale.floor_y[f])-.001:floor_index = f
	return "white" if at.y-float(plan.scale.floor_y[floor_index])>=float(plan.scale.ceiling_clear[floor_index])*2.0/3.0 else "green"

static func _inside(at: Vector3, rect: Array) -> bool:
	return at.x>=float(rect[0])-.001 and at.z>=float(rect[1])-.001 and at.x<=float(rect[2])+.001 and at.z<=float(rect[3])+.001

static func _split(polygon: Array[Vector3], height: float) -> Array:
	var low: Array[Vector3] = []
	var high: Array[Vector3] = []
	var minimum: float = polygon[0].y
	var maximum: float = minimum
	for vertex: Vector3 in polygon:
		minimum = minf(minimum,vertex.y);maximum = maxf(maximum,vertex.y)
	if minimum>=height-.000001 or maximum<=height+.000001:return [polygon]
	for i: int in range(polygon.size()):
		var a: Vector3 = polygon[i]
		var b: Vector3 = polygon[(i+1)%polygon.size()]
		if a.y<=height:low.append(a)
		if a.y>=height:high.append(a)
		if (a.y<height and b.y>height) or (a.y>height and b.y<height):
			var cut: Vector3 = a.lerp(b,(height-a.y)/(b.y-a.y))
			low.append(cut);high.append(cut)
	var result: Array = []
	if low.size()>=3:result.append(low)
	if high.size()>=3:result.append(high)
	return result
