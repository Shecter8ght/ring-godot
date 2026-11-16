@tool
extends EditorScenePostImport
## В glTF лежат индексы дальних форм. Все уровни используют вершины, UV и материал ближней сетки.


func _post_import(scene: Node) -> Object:
	var source := get_source_file()
	var gltf = JSON.parse_string(FileAccess.get_file_as_string(source))
	if not gltf is Dictionary:
		return scene
	# Импорт в редакторе переставляет вершины. Берём массивы из glTF в исходном порядке,
	# а материал берём из сцены после импорта, с её сжатыми текстурами.
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	state.handle_binary_image = GLTFState.HANDLE_BINARY_DISCARD_TEXTURES
	if document.append_from_file(source, state) != OK:
		return scene
	var authored := state.get_meshes()
	var bytes := FileAccess.get_file_as_bytes(source.get_basename() + ".bin")
	var updated := {}
	for i in range(authored.size()):
		var mesh: Dictionary = gltf["meshes"][i]
		var levels: Array = mesh.get("extras", {}).get("cordon_lods", [])
		if levels.is_empty():
			continue
		var instance := scene.find_child(mesh["name"], true, false) as MeshInstance3D
		var replacement := _with_lods(instance, authored[i].mesh, mesh, levels, gltf, bytes)
		if replacement == null:
			push_error("Башня кордона: индексы LOD не соответствуют сетке %s" % mesh["name"])
			return scene
		updated[instance] = replacement
	for instance in updated:
		instance.mesh = updated[instance]
	return scene


func _with_lods(instance: MeshInstance3D, authored: ImporterMesh, description: Dictionary, levels: Array,
		gltf: Dictionary, bytes: PackedByteArray) -> ArrayMesh:
	if instance == null or not instance.mesh is ArrayMesh or authored.get_surface_count() != 1:
		return null
	var original := instance.mesh as ArrayMesh
	var arrays := authored.get_surface_arrays(0)
	var vertex_count: int = arrays[Mesh.ARRAY_VERTEX].size()
	var base := _indices(gltf, bytes, int(description["primitives"][0]["indices"]), vertex_count)
	# Проверяем порядок до применения LOD: импортёр или новый экспорт могут переставить вершины.
	if base.is_empty() or base != arrays[Mesh.ARRAY_INDEX]:
		return null
	var lods := {}
	var previous_count := base.size()
	var previous_distance := 0.0
	for level in levels:
		var distance := float(level["threshold"])
		var indices := _indices(gltf, bytes, int(level["accessor"]), vertex_count)
		if indices.is_empty() or indices.size() >= previous_count or distance <= previous_distance:
			return null
		lods[distance] = indices
		previous_count = indices.size()
		previous_distance = distance
	var result := ArrayMesh.new()
	result.resource_name = original.resource_name
	result.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays, [], lods,
		original.surface_get_format(0) & Mesh.ARRAY_FLAG_COMPRESS_ATTRIBUTES)
	result.surface_set_material(0, original.surface_get_material(0))
	var shadow_arrays := []
	shadow_arrays.resize(Mesh.ARRAY_MAX)
	shadow_arrays[Mesh.ARRAY_VERTEX] = arrays[Mesh.ARRAY_VERTEX]
	shadow_arrays[Mesh.ARRAY_INDEX] = base
	var shadow := ArrayMesh.new()
	shadow.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, shadow_arrays, [], lods)
	result.shadow_mesh = shadow
	return result


func _indices(gltf: Dictionary, bytes: PackedByteArray, index: int, vertex_count: int) -> PackedInt32Array:
	var accessor: Dictionary = gltf["accessors"][index]
	var view: Dictionary = gltf["bufferViews"][int(accessor["bufferView"])]
	var offset := int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
	var count := int(accessor["count"])
	if accessor["componentType"] != 5123 or count % 3 != 0 or offset < 0 or offset + count * 2 > bytes.size():
		return PackedInt32Array()
	var indices := PackedInt32Array()
	indices.resize(count)
	for i in range(0, count, 3):
		var a := bytes.decode_u16(offset + i * 2)
		var b := bytes.decode_u16(offset + i * 2 + 2)
		var c := bytes.decode_u16(offset + i * 2 + 4)
		if maxi(a, maxi(b, c)) >= vertex_count:
			return PackedInt32Array()
		# У glTF и Godot противоположный порядок обхода треугольника.
		indices[i] = a
		indices[i + 1] = c
		indices[i + 2] = b
	return indices
