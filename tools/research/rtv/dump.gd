extends SceneTree
# Только чтение: подключить пакет игры и выписать настройки проекта, окружение, шейдеры и свет карт.
# Запускает tools/research/rtv/run.sh; окружение: RTV_PCK, RTV_OUT, RTV_SHADERS, RTV_MAPS (через запятую).

var out: FileAccess

func w(s: String) -> void:
	out.store_line(s)

func _init() -> void:
	out = FileAccess.open(OS.get_environment("RTV_OUT"), FileAccess.WRITE)
	if not ProjectSettings.load_resource_pack(OS.get_environment("RTV_PCK"), false):
		w("pack load failed")
		quit(1)
		return
	_project()
	_shaders()
	_env("res://Environment/Main.tres")
	_env("res://Environment/Attribute.tres")
	_env("res://Environment/Skyboxes/Dynamic.tres")
	for map: String in OS.get_environment("RTV_MAPS").split(",", false):
		_scene_summary(map)
	out.close()
	quit(0)

func _project() -> void:
	w("=== project.binary")
	var f: FileAccess = FileAccess.open("res://project.binary", FileAccess.READ)
	if f == null:
		w("no project.binary")
		return
	var magic: String = f.get_buffer(4).get_string_from_ascii()
	var count: int = f.get_32()
	w("magic %s, %d keys" % [magic, count])
	for i: int in count:
		var klen: int = f.get_32()
		var key: String = f.get_buffer(klen).get_string_from_utf8()
		var vlen: int = f.get_32()
		var v: Variant = bytes_to_var(f.get_buffer(vlen))
		var s: String = str(v)
		if s.length() > 300:
			s = s.substr(0, 300) + "…"
		w("%s = %s" % [key, s])

func _shaders() -> void:
	DirAccess.make_dir_recursive_absolute(OS.get_environment("RTV_SHADERS"))
	var d: DirAccess = DirAccess.open("res://Shaders")
	if d == null:
		w("no Shaders dir")
		return
	for fn: String in d.get_files():
		if fn.ends_with(".gdshader") or fn.ends_with(".gdshaderinc"):
			var txt: String = FileAccess.get_file_as_string("res://Shaders/" + fn)
			var o: FileAccess = FileAccess.open(OS.get_environment("RTV_SHADERS") + "/" + fn, FileAccess.WRITE)
			o.store_string(txt)
			o.close()

func _props(obj: Object, prefix: String) -> void:
	for p: Dictionary in obj.get_property_list():
		if not (int(p.usage) & PROPERTY_USAGE_STORAGE):
			continue
		var n: String = p.name
		if n in ["script", "resource_local_to_scene", "resource_name", "resource_path"]:
			continue
		var v: Variant = obj.get(n)
		var s: String = str(v)
		if v is Resource:
			s = "%s(%s)" % [(v as Resource).get_class(), (v as Resource).resource_path]
		if s.length() > 200:
			s = s.substr(0, 200) + "…"
		w("%s%s = %s" % [prefix, n, s])

func _env(path: String) -> void:
	w("=== " + path)
	var r: Resource = load(path)
	if r == null:
		w("load failed")
		return
	w("class " + r.get_class())
	_props(r, "  ")
	if r is Environment and (r as Environment).sky != null:
		var sky: Sky = (r as Environment).sky
		w("  -- sky material")
		if sky.sky_material != null:
			_props(sky.sky_material, "    ")

# Сводка карты: какие узлы света, окружение, GI, окклюдеры, LOD, сколько чего.
func _scene_summary(path: String) -> void:
	w("=== scene " + path)
	var ps: PackedScene = load(path) as PackedScene
	if ps == null:
		w("load failed")
		return
	var st: SceneState = ps.get_state()
	var counts: Dictionary = {}
	for i: int in st.get_node_count():
		var t: String = str(st.get_node_type(i))
		if t == "":
			var inst: PackedScene = st.get_node_instance(i)
			t = "inst:" + (inst.resource_path if inst != null else "?")
		counts[t] = int(counts.get(t, 0)) + 1
		if t in ["DirectionalLight3D", "WorldEnvironment", "VoxelGI", "LightmapGI", "ReflectionProbe", "FogVolume", "Camera3D", "OccluderInstance3D", "OmniLight3D", "SpotLight3D"] and int(counts[t]) <= 3:
			w("  node %s (%s) path=%s" % [st.get_node_name(i), t, st.get_node_path(i)])
			for j: int in st.get_node_property_count(i):
				var v: Variant = st.get_node_property_value(i, j)
				var s: String = str(v)
				if v is Resource:
					s = "%s(%s)" % [(v as Resource).get_class(), (v as Resource).resource_path]
				if s.length() > 160:
					s = s.substr(0, 160) + "…"
				w("    %s = %s" % [st.get_node_property_name(i, j), s])
	var keys: Array = counts.keys()
	keys.sort_custom(func(a: Variant, b: Variant) -> bool: return int(counts[a]) > int(counts[b]))
	var line: PackedStringArray = []
	for k: Variant in keys.slice(0, 40):
		line.append("%s×%d" % [k, counts[k]])
	w("  nodes %d: %s" % [st.get_node_count(), ", ".join(line)])
