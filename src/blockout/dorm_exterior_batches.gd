extends RefCounted
## VoxelGI pairs whole mesh AABBs. Keep the existing exterior faces in packets
## outside the interior volumes, so they receive the outdoor sky instead.
## Copy triangle attributes verbatim; do not change materials or physics.
static func separate(target: Node3D, footprints: Array[Rect2]) -> void:
	for child: Node in target.get_children():
		if not child is MeshInstance3D:continue
		var instance: MeshInstance3D = child as MeshInstance3D
		if not String(instance.name).begins_with("Mesh_wall"):continue
		var original: Mesh = instance.mesh
		var buckets: Dictionary = {}
		for surface: int in range(original.get_surface_count()):
			var arrays: Array = original.surface_get_arrays(surface)
			var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX] if arrays[Mesh.ARRAY_INDEX]!=null else PackedInt32Array()
			var count: int = indices.size() if not indices.is_empty() else vertices.size()
			for face: int in range(0,count,3):
				var corners: Array[int] = []
				var bounds: AABB
				for j: int in range(3):
					var index: int = indices[face+j] if not indices.is_empty() else face+j
					corners.append(index)
					var point: Vector3 = instance.transform*vertices[index]
					bounds = AABB(point,Vector3.ZERO) if j==0 else bounds.expand(point)
				var packet: String = "inside"
				# The requested node bounds, not the power-of-two padded voxel grid.
				var overlaps: bool = false
				for footprint: Rect2 in footprints:overlaps = overlaps or _overlaps(bounds,footprint)
				if not overlaps:
					var normal: Vector3 = arrays[Mesh.ARRAY_NORMAL][corners[0]]
					var axis: int = normal.abs().max_axis_index()
					if axis!=1:packet = "outside_%d_%.4f" % [axis,bounds.position[axis]]
				var key: String = str(surface)+"_"+packet
				if not buckets.has(key):
					var copied: Array = [];copied.resize(Mesh.ARRAY_MAX)
					copied[Mesh.ARRAY_VERTEX] = PackedVector3Array();copied[Mesh.ARRAY_NORMAL] = PackedVector3Array()
					copied[Mesh.ARRAY_TEX_UV] = PackedVector2Array();copied[Mesh.ARRAY_TEX_UV2] = PackedVector2Array()
					buckets[key] = {"arrays":copied,"material":instance.get_active_material(surface),"packet":packet}
				for index: int in corners:
					for attribute: int in [Mesh.ARRAY_VERTEX,Mesh.ARRAY_NORMAL,Mesh.ARRAY_TEX_UV,Mesh.ARRAY_TEX_UV2]:
						(buckets[key].arrays as Array)[attribute].append(arrays[attribute][index])
		var inside: ArrayMesh = ArrayMesh.new()
		for key: String in buckets:
			var record: Dictionary = buckets[key]
			var mesh: ArrayMesh = inside if record.packet=="inside" else ArrayMesh.new()
			mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,record.arrays)
			mesh.surface_set_material(mesh.get_surface_count()-1,record.material)
			if record.packet!="inside":
				var exterior: MeshInstance3D = MeshInstance3D.new()
				exterior.name = String(instance.name)+"_"+String(record.packet)
				exterior.transform = instance.transform;exterior.mesh = mesh
				target.add_child(exterior)
		instance.mesh = inside

static func _overlaps(box: AABB, rect: Rect2) -> bool:
	return box.end.x>=rect.position.x and box.position.x<=rect.end.x and box.end.z>=rect.position.y and box.position.z<=rect.end.y
