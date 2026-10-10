extends Node
## Перепись геометрии уровня: какие модели дают треугольники и вызовы отрисовки. Загружает уровень,
## ждёт мародёров, считает по всем видимым MeshInstance3D / MultiMeshInstance3D: треугольники ×
## число экземпляров, группирует по файлу модели (или по узлу-владельцу), печатает первые 40.
## tools/godot.cmd --headless res://tools/mesh_census.tscn [-- res://scenes/levels/xxx.tscn]


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var scene := args[0] if args.size() > 0 else "res://scenes/levels/f1_ring.tscn"
	RaidEvents.enabled = false
	await get_tree().process_frame
	var inst: Node = load(scene).instantiate()
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	for i in range(600):
		await get_tree().process_frame
		if get_tree().get_nodes_in_group("marauders").size() > 0 and i > 120:
			break
	var by: Dictionary = {}
	var total := 0
	var count := 0
	for n in inst.find_children("*", "GeometryInstance3D", true, false):
		var gi := n as GeometryInstance3D
		if not gi.is_visible_in_tree():
			continue
		var tris := 0
		var key := ""
		var surfaces := 0
		if gi is MeshInstance3D and (gi as MeshInstance3D).mesh:
			var mesh := (gi as MeshInstance3D).mesh
			tris = _tris(mesh)
			surfaces = mesh.get_surface_count()
			key = mesh.resource_path.get_slice("::", 0)
		elif gi is MultiMeshInstance3D and (gi as MultiMeshInstance3D).multimesh and (gi as MultiMeshInstance3D).multimesh.mesh:
			var mm := (gi as MultiMeshInstance3D).multimesh
			tris = _tris(mm.mesh) * maxi(mm.visible_instance_count if mm.visible_instance_count >= 0 else mm.instance_count, 0)
			surfaces = mm.mesh.get_surface_count()
			key = "multimesh:" + mm.mesh.resource_path.get_slice("::", 0)
		else:
			continue
		if key == "" or key.ends_with(":"):
			# сетка собрана кодом — по узлу-владельцу (сцене) и скрипту ближайшего предка
			key = "код:" + _owner_key(gi)
		var rec: Array = by.get(key, [0, 0, 0, 0.0])
		rec[0] = int(rec[0]) + tris
		rec[1] = int(rec[1]) + 1
		rec[2] = int(rec[2]) + surfaces
		rec[3] = maxf(float(rec[3]), gi.visibility_range_end)
		by[key] = rec
		total += tris
		count += 1
	var keys: Array = by.keys()
	keys.sort_custom(func(a: String, b: String) -> bool: return int(by[a][0]) > int(by[b][0]))
	print("mesh_census: %s — %d узлов геометрии, %.2f млн треугольников" % [scene, count, total / 1e6])
	print("  %10s %6s %6s %7s  %s" % ["треуг.", "узлов", "поверх", "видно м", "модель"])
	for i in range(mini(40, keys.size())):
		var r: Array = by[keys[i]]
		print("  %10d %6d %6d %7.0f  %s" % [int(r[0]), int(r[1]), int(r[2]), float(r[3]), String(keys[i])])
	get_tree().quit()


func _tris(mesh: Mesh) -> int:
	var t := 0
	for s in mesh.get_surface_count():
		var arr := mesh.surface_get_arrays(s)
		if arr.is_empty():
			continue
		var idx: Variant = arr[Mesh.ARRAY_INDEX]
		if idx != null and (idx as PackedInt32Array).size() > 0:
			t += (idx as PackedInt32Array).size() / 3
		elif arr[Mesh.ARRAY_VERTEX] != null:
			t += (arr[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() / 3
	return t


func _owner_key(n: Node) -> String:
	var p := n.get_parent()
	while p:
		if p.scene_file_path != "":
			return p.scene_file_path
		if p.get_script():
			return (p.get_script() as Script).resource_path
		p = p.get_parent()
	return String(n.name)
