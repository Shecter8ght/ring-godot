extends Node
## Разовый перенос «Санатория» из плана генератора в сохранённые узлы, которые правят руками (решение владельца
## 2026-11-08, docs/design/editable_levels.md). На входе — план с метками групп (генератор с SANATORIUM_OUT) и деревья:
##   tools/godot.cmd --headless res://tools/sanatorium_to_scenes.tscn -- <план.json> <деревья.json>
## (сценой, а не --script: материалам покрытий нужны автозагрузки).
## Пишет: материалы scenes/levels/sanatorium/materials/<ключ>.tres, сетки покрытий и воды …/meshes, сцены построек
## …/buildings/<id>.tscn и кусков участка …/site/<имя>.tscn; в сцену уровня scenes/levels/sanatorium_study.tscn —
## их экземпляры, беседки, машины, валуны, стройплощадки и деревья участка (TreeSpot) узлами; план без геометрии —
## data/blockouts/sanatorium.json (места, виды, уровни), лес за забором — data/blockouts/sanatorium_vegetation.json.
## Повторный запуск перезапишет ручные правки — после переноса его не запускать.

const Land = preload("res://src/blockout/sanatorium_landscape.gd")
const LEVEL_PATH: String = "res://scenes/levels/sanatorium_study.tscn"
const DIR: String = "res://scenes/levels/sanatorium"
const META_OUT: String = "res://data/blockouts/sanatorium.json"
const VEG_OUT: String = "res://data/blockouts/sanatorium_vegetation.json"
const WATER_SHADER: Shader = preload("res://src/world/district_water.gdshader")
const LAKE_SHADER: Shader = preload("res://src/world/sanatorium_lake.gdshader")
const NOISE: String = "res://assets/terrain/zone01_noise.png"
const FAR_EDGE_M: float = 9.0
## Отдельные вещи (метка генератора без номера на конце → папка в сцене уровня): каждая — свой узел, его двигают,
## крутят, масштабируют, копируют и прячут глазком (владелец пробует раскладку руками).
const ITEM_FOLDERS: Dictionary = {"gazebo": "Беседки", "car": "Машины", "site": "Стройплощадки", "rock": "Валуны",
	"bench_cascade": "Лавки", "bench_spring": "Лавки", "kiosk": "Киоски", "kiosk_terrace": "Киоски", "kiosk_trail": "Киоски",
	"ice_cream": "Киоски", "fountain_terrace": "Фонтаны и родник", "fountain_mole": "Фонтаны и родник",
	"spring": "Фонтаны и родник", "cabin": "Пляж", "umbrella": "Пляж", "boat": "Лодки", "boat_rack": "Лодки",
	"boat_lh": "Лодки", "play": "Детская площадка", "colonnade": "«Стрелка»", "rotunda": "«Стрелка»", "planter": "«Стрелка»"}
const SPECIES_TITLE: Dictionary = {"spruce_a": "Ель", "spruce_b": "Ель б", "spruce_young": "Ель молодая", "pine": "Сосна",
	"pine_slim": "Сосна стройная"}
## Что остаётся в плане (data/blockouts/sanatorium.json): всё, кроме геометрии и меток.
const GEOMETRY_KEYS: Array[String] = ["boxes", "stairs", "beams", "cyls", "tris", "labels", "water", "barriers", "markers",
	"rooms", "routes", "tags", "group_titles"]
const TRANSLIT: Dictionary = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "zh", "з": "z",
	"и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
	"ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya"}

var plan: Dictionary
var mats: Array
var materials: Dictionary = {}
var water_mats: Dictionary = {}
var groups: Dictionary = {}
var order: Array[String] = []
var building_ids: Dictionary = {}
var written: Dictionary = {"buildings": 0, "site": 0, "inline": 0, "nodes": 0, "trees": 0}
var pole_mesh: CylinderMesh
var pole_mats: Dictionary = {}


func _ready() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.size() < 2:
		push_error("нужны: <план.json> <деревья.json>")
		get_tree().quit(2)
		return
	plan = JSON.parse_string(FileAccess.get_file_as_string(args[0])) as Dictionary
	var veg: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(args[1])) as Dictionary
	if plan.is_empty() or not plan.has("tags"):
		push_error("в плане нет меток групп (генератор с SANATORIUM_OUT)")
		get_tree().quit(2)
		return
	mats = plan.mats
	for b: Dictionary in plan.buildings:
		building_ids[String(b.id)] = true
	for d: String in ["materials", "meshes", "buildings", "site"]:
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(DIR.path_join(d)))
	_materials()
	_split()
	var main: Node3D = (load(LEVEL_PATH) as PackedScene).instantiate() as Node3D
	main.set_meta("purpose", "Карта «Санаторий» — блокаут, правится руками в редакторе: постройки — scenes/levels/sanatorium/"
		+ "buildings, участок — …/site, беседки, машины, валуны, стройплощадки, деревья — здесь (docs/design/editable_levels.md; "
		+ "прогулка — tools/sanatorium_study.cmd)")
	(main.get_node("Terrain") as Node).add_to_group("blockout_terrain", true)
	var land: Node3D = main.get_node("Landscape") as Node3D
	for c: Node in land.get_children():
		c.free()
	var folders: Dictionary = {}
	var folder_names: Array[String] = ["Постройки", "Участок"]
	for f0: Variant in ITEM_FOLDERS.values():
		if not String(f0) in folder_names:
			folder_names.append(String(f0))
	folder_names.append("Деревья")
	for f: String in folder_names:
		var n: Node3D = Node3D.new()
		n.name = f
		land.add_child(n)
		n.owner = main
		folders[f] = n
	for gid: String in order:
		var g: Dictionary = groups[gid]
		var root: Node3D = _group_node(gid, g)
		var kind: String = _kind(gid, g)
		if kind == "inline":
			var folder: Node3D = folders[ITEM_FOLDERS.get(_prefix(gid), "Участок")]
			folder.add_child(root, true)
			root.position = g.origin
			root.owner = main
			_own(root, main)
			written.inline += 1
			continue
		var path: String = "%s/%s/%s.tscn" % [DIR, "buildings" if kind == "building" else "site",
			gid if kind == "building" else _slug(String(g.title))]
		_own(root, root)
		var ps: PackedScene = PackedScene.new()
		ps.pack(root)
		ResourceSaver.save(ps, path)
		root.free()
		var inst: Node3D = (load(path) as PackedScene).instantiate() as Node3D
		(folders["Постройки" if kind == "building" else "Участок"] as Node3D).add_child(inst, true)
		inst.position = g.origin
		inst.owner = main
		written["buildings" if kind == "building" else "site"] += 1
	_trees(folders["Деревья"] as Node3D, veg, main)
	var packed: PackedScene = PackedScene.new()
	packed.pack(main)
	ResourceSaver.save(packed, LEVEL_PATH)
	main.free()
	# план без геометрии и лес за забором
	var meta: Dictionary = {}
	for k: String in plan:
		if not k in GEOMETRY_KEYS:
			meta[k] = plan[k]
	meta["edited_in_editor"] = "С 2026-11-08 геометрия, проверки и деревья участка — узлы сцены scenes/levels/sanatorium_study.tscn " \
		+ "(docs/design/editable_levels.md); здесь — места, виды, уровни, материалы и итог генератора (stats)."
	_write(META_OUT, JSON.stringify(meta, "", false))
	var bg: Dictionary = {}
	for k: String in veg:
		if k.ends_with("_bg"):
			bg[k] = veg[k]
	_write(VEG_OUT, JSON.stringify(bg, "", false))
	print("перенос: построек %d, кусков участка %d, на месте %d, узлов %d, деревьев %d" % [written.buildings, written.site,
		written.inline, written.nodes, written.trees])
	get_tree().quit(0)


func _write(path: String, text: String) -> void:
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	f.store_string(text)
	f.close()


## Материалы папки: те же, что строил генераторный узел (серые по назначению, стекло прозрачное).
func _materials() -> void:
	for key: Variant in mats:
		var k: String = String(key)
		var m: StandardMaterial3D = StandardMaterial3D.new()
		m.resource_name = k
		m.albedo_color = Land.COLORS.get(k, Color("a0a093"))
		m.roughness = 0.9
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
		if k == "glass":
			m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			m.roughness = 0.08
			m.metallic_specular = 0.8
		elif k in ["metal", "rail", "car_a", "car_b", "car_c", "car_d", "boat"]:
			m.roughness = 0.5
			m.metallic = 0.3
		elif k == "tile":
			m.roughness = 0.35
		materials[k] = _save(m, "%s/materials/%s.tres" % [DIR, k])
	var lake: ShaderMaterial = ShaderMaterial.new()
	lake.shader = LAKE_SHADER
	# бассейны и фонтаны: два года без ухода — стоячая зелёная вода, ряска пятнами (мутная, дна не видно)
	var pool: ShaderMaterial = ShaderMaterial.new()
	pool.shader = WATER_SHADER
	pool.set_shader_parameter("deep_color", Color(0.06, 0.09, 0.05))
	pool.set_shader_parameter("murk_color", Color(0.14, 0.2, 0.09))
	pool.set_shader_parameter("duckweed", 0.18)
	pool.set_shader_parameter("flow", 0.03)
	if ResourceLoader.exists(NOISE):
		lake.set_shader_parameter("noise_tex", load(NOISE))
		pool.set_shader_parameter("noise_tex", load(NOISE))
	water_mats.lake = _save(lake, "%s/materials/water_lake.tres" % DIR)
	water_mats.pool = _save(pool, "%s/materials/water_pool.tres" % DIR)
	pole_mesh = CylinderMesh.new()
	pole_mesh.top_radius = 0.18
	pole_mesh.bottom_radius = 0.18
	pole_mesh.height = 5.0
	for kind: String in ["exit", "spawn"]:
		var pm: StandardMaterial3D = StandardMaterial3D.new()
		pm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		pm.albedo_color = Color(0.2, 0.85, 0.35) if kind == "exit" else Color(0.3, 0.55, 1.0)
		pole_mats[kind] = pm


## Записать ресурс и закрепить за ним путь: сцены построек ссылаются на файл, а не держат свою копию.
func _save(res: Resource, path: String) -> Resource:
	ResourceSaver.save(res, path)
	res.take_over_path(path)
	return res


## Раскладка записей плана по группам меток.
func _split() -> void:
	var tags: Dictionary = plan.tags
	for list: String in ["boxes", "stairs", "beams", "cyls", "labels", "water", "barriers", "markers", "rooms", "routes"]:
		var rows: Array = plan[list]
		var t: Array = tags[list]
		for i: int in range(rows.size()):
			(_g(String(t[i]))[list] as Array).append(rows[i])
	for key: String in plan.tris:
		var flat: Array = plan.tris[key]
		var t2: Array = (tags.tris as Dictionary)[key]
		for i: int in range(t2.size()):
			var g: Dictionary = _g(String(t2[i]))
			if not (g.tris as Dictionary).has(key):
				g.tris[key] = []
			(g.tris[key] as Array).append(flat.slice(i * 9, i * 9 + 9))
	for gid: String in order:
		groups[gid].origin = _origin(groups[gid])


func _g(gid: String) -> Dictionary:
	if not groups.has(gid):
		groups[gid] = {"title": String((plan.group_titles as Dictionary).get(gid, gid)), "boxes": [], "stairs": [], "beams": [],
			"cyls": [], "tris": {}, "labels": [], "water": [], "barriers": [], "markers": [], "rooms": [], "routes": []}
		order.append(gid)
	return groups[gid]


func _prefix(gid: String) -> String:
	return gid.rstrip("0123456789")


func _kind(gid: String, g: Dictionary) -> String:
	if building_ids.has(gid) or gid.begins_with("s_corps_"):
		return "building"
	if ITEM_FOLDERS.has(_prefix(gid)):
		return "inline"
	var geometry: int = (g.boxes as Array).size() + (g.stairs as Array).size() + (g.beams as Array).size() + \
		(g.cyls as Array).size() + (g.tris as Dictionary).size() + (g.water as Array).size() + (g.barriers as Array).size()
	return "site" if geometry > 0 else "inline"


## Точка группы: середина по плану, низ — самая нижняя отметка объёмов (у постройки — фундамент); с шагом 0,1 м.
func _origin(g: Dictionary) -> Vector3:
	var xs: Array[float] = []
	var zs: Array[float] = []
	var ys: Array[float] = []
	for b: Array in g.boxes:
		xs.append(float(b[0])); zs.append(float(b[2])); ys.append(float(b[1]) - float(b[4]) * 0.5)
	for s: Array in g.stairs:
		xs.append_array([float(s[0]), float(s[3])]); zs.append_array([float(s[2]), float(s[5])]); ys.append(float(s[1]))
	for b: Array in g.beams:
		xs.append_array([float(b[0]), float(b[3])]); zs.append_array([float(b[2]), float(b[5])]); ys.append(minf(float(b[1]), float(b[4])))
	for c: Array in g.cyls:
		xs.append(float(c[0])); zs.append(float(c[2])); ys.append(float(c[1]))
	var tri_y: Array[float] = []
	for key: String in g.tris:
		for t: Array in g.tris[key]:
			for k: int in range(3):
				xs.append(float(t[k * 3])); zs.append(float(t[k * 3 + 2])); tri_y.append(float(t[k * 3 + 1]))
	for l: Array in g.labels:
		xs.append(float(l[0])); zs.append(float(l[2]))
	for m: Array in g.markers:
		xs.append(float(m[1])); zs.append(float(m[3]))
	for w: Dictionary in g.water:
		if w.has("circle"):
			xs.append(float(w.circle[0])); zs.append(float(w.circle[1]))
		else:
			for q: Array in w.poly:
				xs.append(float(q[0])); zs.append(float(q[1]))
	for r: Dictionary in g.rooms:
		xs.append(float(r.at[0])); zs.append(float(r.at[2]))
	if xs.is_empty():
		return Vector3.ZERO
	var y: float = ys.min() if not ys.is_empty() else (tri_y.min() if not tri_y.is_empty() else 0.0)
	return Vector3(snappedf((xs.min() + xs.max()) * 0.5, 0.1), snappedf(y, 0.1), snappedf((zs.min() + zs.max()) * 0.5, 0.1))


## Имя узла по заголовку раздела: «КАСКАД: объёмы» → «Каскад — объёмы» (двоеточие и точка в имени узла нельзя).
func _title(t: String) -> String:
	var s: String = t.strip_edges()
	var first: String = s.split(" ")[0]
	if first.length() > 3 and first == first.to_upper() and first != first.to_lower():
		s = s.to_lower()
		s = s.substr(0, 1).to_upper() + s.substr(1)
	return s.replace(":", " —").replace(".", "").validate_node_name()


func _slug(t: String) -> String:
	var out: String = ""
	for ch: String in t.to_lower():
		if TRANSLIT.has(ch):
			out += String(TRANSLIT[ch])
		elif (ch >= "a" and ch <= "z") or (ch >= "0" and ch <= "9"):
			out += ch
		elif not out.ends_with("_"):
			out += "_"
	return out.strip_edges().trim_prefix("_").trim_suffix("_").left(48)


func _v(a: Array, i: int) -> Vector3:
	return Vector3(float(a[i]), float(a[i + 1]), float(a[i + 2]))


func _folder(root: Node3D, name: String) -> Node3D:
	var n: Node3D = root.get_node_or_null(name) as Node3D
	if n == null:
		n = Node3D.new()
		n.name = name
		root.add_child(n, true)
	return n


## Узлы одной группы относительно её точки.
func _group_node(gid: String, g: Dictionary) -> Node3D:
	var o: Vector3 = g.origin
	var root: Node3D = Node3D.new()
	root.name = _title(String(g.title))
	root.set_meta("group", gid)
	var n: int = 0
	for b: Array in g.boxes:
		var box: CSGBox3D = CSGBox3D.new()
		var key: String = String(mats[int(b[7])])
		box.name = "%s_%04d" % [key, n]
		box.size = Vector3(float(b[3]), float(b[4]), float(b[5]))
		box.position = _v(b, 0) - o
		box.rotation.y = deg_to_rad(float(b[6]))
		box.material = materials[key]
		box.use_collision = int(b[8]) == 1
		_folder(root, "Коробки").add_child(box)
		n += 1
	for b: Array in g.beams:
		var a: Vector3 = _v(b, 0)
		var c: Vector3 = _v(b, 3)
		var beam: CSGBox3D = CSGBox3D.new()
		var key2: String = String(mats[int(b[8])])
		beam.name = "%s_%04d" % [key2, n]
		beam.size = Vector3(float(b[6]), float(b[7]), a.distance_to(c))
		beam.transform = Transform3D(Basis.looking_at((c - a).normalized(), Vector3.UP), (a + c) * 0.5 - o)
		beam.material = materials[key2]
		beam.use_collision = int(b[9]) == 1
		beam.set_meta("beam", true)
		_folder(root, "Коробки").add_child(beam)
		n += 1
	for s: Array in g.stairs:
		var bottom: Vector3 = _v(s, 0)
		var top: Vector3 = _v(s, 3)
		var d: Vector3 = Vector3(top.x - bottom.x, 0.0, top.z - bottom.z)
		var st: BlockoutStair = BlockoutStair.new()
		st.name = "Марш_%03d" % n
		st.position = bottom - o
		st.rotation.y = atan2(-d.x, -d.z)
		st.run = d.length()
		st.rise = top.y - bottom.y
		st.width = float(s[6])
		st.steps = int(s[7])
		st.solid = s[8] != null
		st.solid_bottom = float(s[8]) - bottom.y if s[8] != null else -0.05
		st.material = materials[String(mats[int(s[9])])]
		_folder(root, "Лестницы").add_child(st)
		n += 1
	for c2: Array in g.cyls:
		var cyl: CSGCylinder3D = CSGCylinder3D.new()
		var key3: String = String(mats[int(c2[5])])
		cyl.name = "%s_%04d" % [key3, n]
		cyl.radius = float(c2[3])
		cyl.height = float(c2[4])
		cyl.sides = int(c2[7])
		cyl.position = _v(c2, 0) + Vector3.UP * float(c2[4]) * 0.5 - o
		cyl.material = materials[key3]
		cyl.use_collision = int(c2[6]) == 1
		_folder(root, "Цилиндры").add_child(cyl)
		n += 1
	for key4: String in g.tris:
		var parts: PackedStringArray = key4.split("|")
		var mi: MeshInstance3D = MeshInstance3D.new()
		mi.name = "%s%s" % [parts[0], "_твёрдое" if parts[1] == "1" else ""]
		mi.mesh = _surface_mesh(g.tris[key4], parts[0], o, "%s/meshes/%s_%s_%s.tres" % [DIR, gid, parts[0], parts[1]])
		mi.set_meta("blockout_mat", parts[0])
		mi.set_meta("solid", parts[1] == "1")
		if parts[0] in Land.NO_SHADOW:
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		_folder(root, "Покрытия").add_child(mi)
		n += 1
	for w: Dictionary in g.water:
		_folder(root, "Вода").add_child(_water(gid, w, o), true)
	for l: Array in g.labels:
		_folder(root, "Подписи").add_child(_label(l, o), true)
	for m: Array in g.markers:
		_folder(root, "Знаки").add_child(_marker(m, o), true)
	if not (g.barriers as Array).is_empty():
		var body: StaticBody3D = StaticBody3D.new()
		body.name = "Стенки"
		body.collision_layer = 1
		body.collision_mask = 0
		root.add_child(body)
		for bar: Array in g.barriers:
			var cs: CollisionShape3D = _barrier(bar, o)
			if cs:
				body.add_child(cs, true)
	if not (g.rooms as Array).is_empty() or not (g.routes as Array).is_empty():
		root.add_child(_checks(g, o))
	written.nodes += n
	return root


## Покрытие по рельефу: треугольники уже повёрнуты лицом вверх (как делал генераторный узел), UV — «далеко от рёбер».
func _surface_mesh(tris: Array, key: String, o: Vector3, path: String) -> ArrayMesh:
	var st: SurfaceTool = SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for t: Array in tris:
		var a: Vector3 = _v(t, 0) - o
		var b: Vector3 = _v(t, 3) - o
		var c: Vector3 = _v(t, 6) - o
		if (c - a).cross(b - a).y < 0.0:
			var sw: Vector3 = b
			b = c
			c = sw
		var normal: Vector3 = (c - a).cross(b - a).normalized()
		for p: Vector3 in [a, b, c]:
			st.set_normal(normal)
			st.set_uv(Vector2(FAR_EDGE_M, FAR_EDGE_M))
			st.set_uv2(Vector2(FAR_EDGE_M, FAR_EDGE_M))
			st.add_vertex(p)
	var mesh: ArrayMesh = st.commit()
	mesh.surface_set_material(0, materials[key])
	return _save(mesh, path) as ArrayMesh


func _water(gid: String, body: Dictionary, o: Vector3) -> MeshInstance3D:
	var level: float = float(body.level) - o.y
	var outline: PackedVector2Array = PackedVector2Array()
	var meta: Dictionary = {"name": String(body.name), "level": level}
	if body.has("circle"):
		var c: Array = body.circle
		for k: int in range(28):
			var a: float = TAU * float(k) / 28.0
			outline.append(Vector2(float(c[0]) - o.x + cos(a) * float(c[2]), float(c[1]) - o.z + sin(a) * float(c[2])))
		meta.circle = [float(c[0]) - o.x, float(c[1]) - o.z, float(c[2])]
	else:
		var poly: Array = []
		for q: Array in body.poly:
			outline.append(Vector2(float(q[0]) - o.x, float(q[1]) - o.z))
			poly.append([float(q[0]) - o.x, float(q[1]) - o.z])
		meta.poly = poly
	var tris: PackedInt32Array = Geometry2D.triangulate_polygon(outline)
	var verts: PackedVector3Array = PackedVector3Array()
	var normals: PackedVector3Array = PackedVector3Array()
	for idx: int in tris:
		verts.append(Vector3(outline[idx].x, level, outline[idx].y))
		normals.append(Vector3.UP)
	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_NORMAL] = normals
	var mesh: ArrayMesh = ArrayMesh.new()
	if not verts.is_empty():
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		mesh.surface_set_material(0, water_mats.lake if String(body.name) == "Lake" else water_mats.pool)
	var mi: MeshInstance3D = MeshInstance3D.new()
	mi.name = String(body.name)
	mi.mesh = _save(mesh, "%s/meshes/%s_water_%s.tres" % [DIR, gid, String(body.name)]) as ArrayMesh
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.set_meta("water_body", meta)
	return mi


func _label(l: Array, o: Vector3) -> Label3D:
	var kind: String = String(l[5])
	var label: Label3D = Label3D.new()
	label.name = String(l[3]).replace(":", " —").replace(".", "").left(40).validate_node_name()
	label.text = String(l[3])
	label.position = _v(l, 0) - o
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.pixel_size = float(Land.LABEL_PIXEL.get(kind, 0.01)) * maxf(float(l[4]), 0.3)
	label.font_size = 48
	label.outline_size = 10
	label.modulate = Color(0.97, 0.96, 0.9) if kind != "room" else Color(0.92, 0.95, 1.0)
	label.visibility_range_end = float(Land.LABEL_RANGE.get(kind, 60.0))
	label.visibility_range_end_margin = 4.0
	# крупные подписи построек и плотины вблизи не нужны — закрыли бы полэкрана
	label.visibility_range_begin = float(Land.LABEL_BEGIN.get(kind, 0.0))
	label.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	label.set_meta("kind", kind)
	return label


## Знак выхода или захода: столб и подпись (как у генераторного узла).
func _marker(m: Array, o: Vector3) -> Node3D:
	var kind: String = String(m[0])
	var root: Node3D = Node3D.new()
	root.name = String(m[4]).replace(":", " —").replace(".", "").left(40).validate_node_name()
	root.position = _v(m, 1) - o
	root.set_meta("marker", kind)
	var pole: MeshInstance3D = MeshInstance3D.new()
	pole.name = "Столб"
	pole.mesh = pole_mesh
	pole.material_override = pole_mats[kind]
	pole.position = Vector3.UP * 2.5
	pole.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(pole)
	var label: Label3D = Label3D.new()
	label.name = "Подпись"
	label.text = String(m[4])
	label.position = Vector3.UP * 5.6
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.font_size = 48
	label.outline_size = 10
	label.pixel_size = 0.012
	label.modulate = (pole_mats[kind] as StandardMaterial3D).albedo_color.lightened(0.3)
	label.visibility_range_end = 260.0
	root.add_child(label)
	return root


func _barrier(b: Array, o: Vector3) -> CollisionShape3D:
	var a: Vector2 = Vector2(float(b[0]), float(b[1]))
	var c: Vector2 = Vector2(float(b[2]), float(b[3]))
	var length: float = a.distance_to(c)
	if length < 0.01:
		return null
	var bottom: float = float(b[4])
	var top: float = float(b[5])
	var shape: BoxShape3D = BoxShape3D.new()
	shape.size = Vector3(0.5, top - bottom, length + 0.5)
	var cs: CollisionShape3D = CollisionShape3D.new()
	cs.shape = shape
	var mid: Vector2 = (a + c) * 0.5
	cs.position = Vector3(mid.x, (bottom + top) * 0.5, mid.y) - o
	cs.rotation.y = atan2(c.x - a.x, c.y - a.y)
	return cs


## Помещения и обходы — в координатах группы (высоты проверок — от её низа).
func _checks(g: Dictionary, o: Vector3) -> BlockoutChecks:
	var node: BlockoutChecks = BlockoutChecks.new()
	node.name = "Проверки"
	var rooms: Array = []
	for r: Dictionary in g.rooms:
		var lr: Dictionary = r.duplicate(true)
		lr.at = _local(r.at as Array, o)
		rooms.append(lr)
	var routes: Array = []
	for r2: Dictionary in g.routes:
		var lr2: Dictionary = r2.duplicate(true)
		var pts: Array = []
		for p: Array in r2.points:
			pts.append(_local(p, o))
		lr2.points = pts
		var checks: Array = []
		for c: Array in r2.get("checks", []):
			checks.append([int(c[0]), String(c[1]), snappedf(float(c[2]) - o.y, 0.001)])
		lr2.checks = checks
		routes.append(lr2)
	node.rooms = rooms
	node.routes = routes
	return node


func _local(p: Array, o: Vector3) -> Array:
	return [snappedf(float(p[0]) - o.x, 0.001), snappedf(float(p[1]) - o.y, 0.001), snappedf(float(p[2]) - o.z, 0.001)]


## Деревья участка — узлы TreeSpot по породам (место, поворот, масштаб — как у генератора).
func _trees(folder: Node3D, veg: Dictionary, main: Node3D) -> void:
	for key: String in veg:
		if key.ends_with("_bg") or (veg[key] as Array).is_empty():
			continue
		var sub: Node3D = Node3D.new()
		sub.name = String(SPECIES_TITLE.get(key, key))
		folder.add_child(sub)
		sub.owner = main
		var i: int = 0
		for p: Array in veg[key]:
			i += 1
			var t: TreeSpot = TreeSpot.new()
			t.name = "%s %03d" % [String(SPECIES_TITLE.get(key, key)), i]
			t.species = key
			t.position = Vector3(float(p[0]), float(p[1]), float(p[2]))
			t.rotation.y = deg_to_rad(float(p[3]))
			t.scale = Vector3.ONE * float(p[4])
			sub.add_child(t)
			t.owner = main
			written.trees += 1


func _own(node: Node, owner_node: Node) -> void:
	for c: Node in node.get_children():
		c.owner = owner_node
		if c.scene_file_path == "":
			_own(c, owner_node)
