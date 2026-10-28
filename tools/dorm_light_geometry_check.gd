extends SceneTree
## Compare the same plan with/without per-floor draw packets. Triangle coordinates,
## normals, UV/UV2 and materials, plus all collision shapes/transforms must be identical.
var rows: Array[Dictionary] = []
var faces: Array[String] = []
var shapes: Array[String] = []
var meshes: int = 0

func _initialize() -> void:call_deferred("_run")

func _run() -> void:
	var plan: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/blockouts/dorm.json")) as Dictionary
	var script: Script = load("res://src/blockout/dorm_geometry.gd") as Script
	for split: bool in [false,true]:
		var world: Node3D = Node3D.new();root.add_child(world)
		for key: String in plan.sections:
			var section: Node3D = Node3D.new();section.set_script(script)
			section.set("section_id",key);section.set("split_gi_batches",split);world.add_child(section)
		await process_frame
		faces.clear();shapes.clear();meshes = 0
		_scan(world)
		faces.sort();shapes.sort()
		rows.append({"split_gi_batches":split,"triangles":faces.size(),"collision_shapes":shapes.size(),"meshes":meshes,
			"triangle_attributes_sha256":"\n".join(faces).sha256_text(),"collision_sha256":"\n".join(shapes).sha256_text()})
		world.queue_free();await process_frame
	var passed: bool = rows[0].triangle_attributes_sha256==rows[1].triangle_attributes_sha256 and rows[0].collision_sha256==rows[1].collision_sha256
	var output: String = ProjectSettings.globalize_path("res://docs/screens/dorm/light_geometry_guard.json")
	var file: FileAccess = FileAccess.open(output,FileAccess.WRITE);file.store_string(JSON.stringify({"pass":passed,"variants":rows},"\t"));file.close()
	print("DORM_RENDER_GEOMETRY_GUARD ","PASS" if passed else "FAIL"," ",JSON.stringify(rows))
	quit(0 if passed else 1)

func _scan(node: Node) -> void:
	if node is MeshInstance3D:
		var instance: MeshInstance3D = node as MeshInstance3D
		meshes += 1
		for s: int in range(instance.mesh.get_surface_count()):
			var arrays: Array = instance.mesh.surface_get_arrays(s)
			var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
			var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX] if arrays[Mesh.ARRAY_INDEX]!=null else PackedInt32Array()
			var count: int = indices.size() if not indices.is_empty() else vertices.size()
			var material: Material = instance.get_active_material(s)
			var signature: String = str(material.albedo_color)+str(material.roughness)+str(material.metallic) if material is StandardMaterial3D else (material as ShaderMaterial).shader.code.sha256_text()
			for i: int in range(0,count,3):
				var data: Array = [signature]
				for j: int in range(3):
					var index: int = indices[i+j] if not indices.is_empty() else i+j
					data.append(str(instance.global_transform*vertices[index]));data.append(str(instance.global_basis*normals[index]))
					for attribute: int in [Mesh.ARRAY_TEX_UV,Mesh.ARRAY_TEX_UV2]:
						if arrays[attribute]!=null and arrays[attribute].size()>index:data.append(str(arrays[attribute][index]))
				faces.append(JSON.stringify(data).sha256_text())
	if node is CollisionShape3D:
		var collider: CollisionShape3D = node as CollisionShape3D
		var shape: Shape3D = collider.shape
		var dimensions: String = str((shape as BoxShape3D).size) if shape is BoxShape3D else shape.get_class()
		shapes.append(str(collider.global_transform)+dimensions+str(collider.disabled))
	for child: Node in node.get_children():_scan(child)
