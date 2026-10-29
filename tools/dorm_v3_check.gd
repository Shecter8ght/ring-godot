extends SceneTree
## Материалы и модули общежития v03 в движке: карты загружены и в каком формате (поля EXR — половинной точности без
## сжатия: формат Image.FORMAT_RH = 9 / RGBH = 11), шейдеры разбираются, палитра стенда отдаёт v03 вместо черновых и каждому параметру нашлась карта.
##   tools/godot.cmd --headless --script res://tools/dorm_v3_check.gd

const Geometry = preload("res://src/blockout/dorm_geometry.gd")


func _init() -> void:
	var failed: int = 0
	var dir: DirAccess = DirAccess.open("res://assets/textures/dorm_v3")
	for file: String in dir.get_files():
		if file.ends_with(".import"):
			continue
		var tex: Texture2D = load("res://assets/textures/dorm_v3/" + file) as Texture2D
		if tex == null:
			print("НЕТ  ", file)
			failed += 1
			continue
		var image: Image = tex.get_image()
		print("%-28s %5d  формат %d" % [file, tex.get_width(), image.get_format() if image else -1])
	var plan: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/blockouts/dorm.json"))
	var palette: Dictionary = Geometry._palette(plan)
	for key: String in ["wall", "reveal", "ceiling", "floor", "tile", "tile_floor"]:
		var material: Material = palette[key]
		var shader: Shader = (material as ShaderMaterial).shader if material is ShaderMaterial else null
		var path: String = shader.resource_path if shader else "—"
		var missing: Array[String] = []
		if shader:
			for uniform: Dictionary in shader.get_shader_uniform_list():
				if int(uniform.type) == TYPE_OBJECT and (material as ShaderMaterial).get_shader_parameter(uniform.name) == null:
					missing.append(String(uniform.name))
		var params: int = shader.get_shader_uniform_list().size() if shader else 0
		print("%-10s %s  параметров %d  без карты %s" % [key, path.get_file(), params, missing])
		if not path.contains("_v3") or not missing.is_empty() or params == 0:
			failed += 1
	# модули Blender: сетки, материалы по слотам, сколько мест на этаже
	var Modules: GDScript = load("res://src/blockout/dorm_modules.gd") as GDScript
	if not bool(Modules.call("available")):
		print("модули: нет файлов assets/models/dorm")
		failed += 1
	else:
		for part: String in ["door_frame", "door_leaf", "window", "radiator"]:
			var mesh: Mesh = Modules.call("mesh", part) as Mesh
			var node: MeshInstance3D = MeshInstance3D.new()
			node.mesh = mesh
			Modules.call("apply_materials", node)
			var bare: int = 0
			for s: int in range(mesh.get_surface_count()):
				if node.get_surface_override_material(s) == null:
					bare += 1
			print("%-11s поверхностей %d, без материала %d, габарит %s" % [part, mesh.get_surface_count(), bare, mesh.get_aabb().size])
			failed += bare
			node.free()
		for section: String in ["Floor1", "Floor2", "NorthAnnex", "CentralStair"]:
			var m: RefCounted = Modules.new(plan, section)
			print("%-12s дверей %d, окон %d" % [section, (m.get("doors") as Dictionary).size(), (m.get("windows") as Dictionary).size()])
	print("dorm v3 check: ", "OK" if failed == 0 else "FAIL %d" % failed)
	quit(1 if failed else 0)
