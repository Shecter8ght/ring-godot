extends SceneTree
# Данные игры текстом: ресурсы (.tres без материалов) и деревья ключевых сцен с их свойствами.
# Запускает tools/research/rtv/run.sh; окружение: RTV_PCK, RTV_DATA (папка вывода),
# RTV_LIST (файл со списком путей ресурсов), RTV_SCENES (через запятую).

var out_dir: String

func _init() -> void:
	ProjectSettings.load_resource_pack(OS.get_environment("RTV_PCK"), false)
	out_dir = OS.get_environment("RTV_DATA")
	var list: PackedStringArray = FileAccess.get_file_as_string(OS.get_environment("RTV_LIST")).split("\n", false)
	var n: int = 0
	for path: String in list:
		var r: Resource = load("res://" + path)
		if r == null:
			continue
		var lines: PackedStringArray = ["# %s (%s)" % [path, r.get_class()]]
		_props(r, "", lines, 0)
		_write(path + ".txt", lines)
		n += 1
	print("resources ", n)
	for sp: String in OS.get_environment("RTV_SCENES").split(",", false):
		_scene(sp)
	quit(0)

func _write(rel: String, lines: PackedStringArray) -> void:
	var path: String = out_dir.path_join(rel)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	f.store_string("\n".join(lines) + "\n")
	f.close()

func _val(v: Variant, prefix: String, lines: PackedStringArray, depth: int) -> String:
	if v is Resource:
		var r: Resource = v
		var rp: String = r.resource_path
		if rp != "" and not ("::" in rp):
			return "%s(%s)" % [r.get_class(), rp]
		if depth < 3 and not (r is Texture2D or r is Mesh or r is Material or r is AudioStream or r is Animation or r is Shape3D):
			lines.append("%s<%s inline>" % [prefix, r.get_class()])
			_props(r, prefix + "    ", lines, depth + 1)
			return "^"
		return "%s(inline)" % r.get_class()
	if v is Array and (v as Array).size() > 0 and (v as Array)[0] is Resource:
		var arr: Array = v
		var parts: PackedStringArray = []
		for e: Variant in arr:
			parts.append(_val(e, prefix + "  ", lines, depth))
		return "[" + ", ".join(parts) + "]"
	var s: String = str(v)
	if s.length() > 400:
		s = s.substr(0, 400) + "…"
	return s

func _props(obj: Object, prefix: String, lines: PackedStringArray, depth: int) -> void:
	for p: Dictionary in obj.get_property_list():
		if not (int(p.usage) & PROPERTY_USAGE_STORAGE):
			continue
		var name: String = p.name
		if name in ["resource_local_to_scene", "resource_name", "resource_path", "resource_scene_unique_id"]:
			continue
		var v: Variant = obj.get(name)
		if name == "script":
			if v != null:
				lines.append("%sscript = %s" % [prefix, (v as Script).resource_path])
			continue
		var at: int = lines.size()
		var s: String = _val(v, prefix + "  ", lines, depth)
		if s == "^":
			lines.insert(at, "%s%s =" % [prefix, name])
		else:
			lines.insert(at, "%s%s = %s" % [prefix, name, s])

func _scene(path: String) -> void:
	var ps: PackedScene = load(path) as PackedScene
	if ps == null:
		return
	var st: SceneState = ps.get_state()
	var lines: PackedStringArray = ["# scene " + path]
	for i: int in st.get_node_count():
		var t: String = str(st.get_node_type(i))
		var inst: PackedScene = st.get_node_instance(i)
		if inst != null:
			t += " inst " + inst.resource_path
		lines.append("[%s] %s" % [st.get_node_path(i), t])
		for j: int in st.get_node_property_count(i):
			var v: Variant = st.get_node_property_value(i, j)
			var pn: String = st.get_node_property_name(i, j)
			if v is Script:
				lines.append("    %s = %s" % [pn, (v as Script).resource_path])
				continue
			var at: int = lines.size()
			var s: String = _val(v, "      ", lines, 1)
			if s == "^":
				lines.insert(at, "    %s =" % pn)
			else:
				lines.insert(at, "    %s = %s" % [pn, s])
	_write("scenes/" + path.trim_prefix("res://").replace("/", "__") + ".txt", lines)
