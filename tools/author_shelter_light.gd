extends Node
## Офлайн-авторинг: подготовка запечённого света убежища (LightmapGI). Полы, потолки, стены и несущие
## конструкции получают вторую развёртку (UV2) и режим «статичный» — их рассеянный свет и мягкие тени
## считаются заранее; тонкое (трубы, перила, вентиляция) и все предметы — «динамичные», освещаются
## зондами того же запекания. SDFGI в окружении выключается (свет уже в карте), SSIL и SSAO остаются.
## Само запекание — в редакторе (в игре и без окна его нет): tools/bake_shelter_light.cmd.
## Порядок: author_shelter_scene → author_shelter_dressing → author_shelter_grime → этот → запекание.
## tools/godot.cmd --headless res://tools/author_shelter_light.tscn

const BASE: String = "res://levels/shelter/"
const OUT: String = "res://levels/shelter/lightmap/"
## Плотность карты света, м на тексель: стены и полы.
const TEXEL: float = 0.1
## Что из архитектуры — в карту (по началу имени), остальное архитектурное — на зондах.
const STATIC_PREFIXES: Array[String] = ["SH_Int_Floor_", "SH_Int_Ceiling_", "SH_Int_Wall_", "SH_Int_TechnicalStructure"]

var _level: Node3D
var _counts: Dictionary = {"static": 0, "dynamic": 0, "unwrapped": 0}


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	_level = (load(BASE + "Shelter_Interior.tscn") as PackedScene).instantiate() as Node3D
	var arch: Node = _level.get_node("Architecture")
	var done: Dictionary = {}
	for node: Node in _level.find_children("*", "GeometryInstance3D", true, false):
		var gi: GeometryInstance3D = node as GeometryInstance3D
		var top: Node = _top_child(arch, gi)
		var baked: bool = top != null and gi is MeshInstance3D and _is_static(String(top.name))
		if not baked:
			if gi.gi_mode != GeometryInstance3D.GI_MODE_DYNAMIC:
				gi.gi_mode = GeometryInstance3D.GI_MODE_DYNAMIC
				_editable_owner(gi)
			_counts.dynamic += 1
			continue
		# стены и полы — вложенные сцены: правки внутри сохраняются, только если экземпляр «редактируемый»
		if top.scene_file_path != "":
			_level.set_editable_instance(top, true)
		var mi: MeshInstance3D = gi as MeshInstance3D
		var src: ArrayMesh = mi.mesh as ArrayMesh
		if not done.has(src.resource_path):
			done[src.resource_path] = _unwrap(src)
		mi.mesh = done[src.resource_path]
		mi.gi_mode = GeometryInstance3D.GI_MODE_STATIC
		mi.gi_lightmap_texel_scale = 1.0
		_counts.static += 1
	var previous: Node = _level.get_node_or_null("LightmapGI")
	if previous:
		previous.free()
	var lm: LightmapGI = LightmapGI.new()
	lm.name = "LightmapGI"
	lm.quality = LightmapGI.BAKE_QUALITY_HIGH
	lm.bounces = 3
	lm.bounce_indirect_energy = 1.0
	lm.interior = true
	lm.directional = false
	lm.use_denoiser = true
	lm.environment_mode = LightmapGI.ENVIRONMENT_MODE_DISABLED
	lm.generate_probes_subdiv = LightmapGI.GENERATE_PROBES_SUBDIV_16
	lm.max_texture_size = 8192
	_level.add_child(lm)
	lm.owner = _level
	var we: WorldEnvironment = _level.get_node("WorldEnvironment") as WorldEnvironment
	we.environment.sdfgi_enabled = false
	we.environment.set_meta("lightmap", true)
	var packed: PackedScene = PackedScene.new()
	assert(packed.pack(_level) == OK)
	assert(ShelterSave.save(packed, BASE + "Shelter_Interior.tscn") == OK)
	# варианты запечённого света по погоде и питанию (ShelterWeather): наследники сцены, редактор
	# запекает каждый в levels/shelter/lightmap/Shelter_<вид>.lmbake
	var scenes: PackedStringArray = PackedStringArray()
	for v: Array in ShelterWeather.bake_variants():
		var path: String = OUT + "Shelter_%s.tscn" % String(v[0])
		var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
		f.store_string('[gd_scene load_steps=2 format=3]

[ext_resource type="PackedScene" path="%sShelter_Interior.tscn" id="1_base"]

[node name="Shelter_Interior" instance=ExtResource("1_base")]
' % BASE)
		f.close()
		scenes.append(path)
	_counts["variants"] = scenes.size()
	var list: FileAccess = FileAccess.open(OUT + "variants.txt", FileAccess.WRITE)
	list.store_string(";".join(scenes))
	list.close()
	print("LIGHT_PREPARED " + JSON.stringify(_counts))
	_level.free()
	get_tree().quit()


## Узел внутри вложенной сцены: её экземпляр в уровне — «редактируемый», иначе правка не сохранится.
func _editable_owner(n: Node) -> void:
	var o: Node = n.owner
	while o and o != _level:
		if o.scene_file_path != "" and o.owner == _level:
			_level.set_editable_instance(o, true)
			return
		o = o.owner
	return


func _is_static(label: String) -> bool:
	for p: String in STATIC_PREFIXES:
		if label.begins_with(p):
			return true
	return false


## Прямой потомок Architecture, внутри которого лежит узел (null — не архитектура).
func _top_child(arch: Node, n: Node) -> Node:
	var cur: Node = n
	while cur and cur.get_parent() != arch:
		cur = cur.get_parent()
		if cur == _level:
			return null
	return cur


## Копия меша со второй развёрткой — в levels/shelter/lightmap/ (исходник не трогаем).
func _unwrap(src: ArrayMesh) -> ArrayMesh:
	# повторный запуск: сцена уже держит копию с UV2 — разворачивать заново из исходника
	if src.resource_path.begins_with(OUT):
		src = load(BASE + "props/" + src.resource_path.get_file().trim_suffix("_lm.res") + ".res") as ArrayMesh
	var mesh: ArrayMesh = src.duplicate() as ArrayMesh
	var err: Error = mesh.lightmap_unwrap(Transform3D.IDENTITY, TEXEL)
	assert(err == OK, "UV2 не построена: " + src.resource_path)
	var path: String = OUT + src.resource_path.get_file().get_basename() + "_lm.res"
	assert(ShelterSave.save(mesh, path) == OK)
	_counts.unwrapped += 1
	return load(path) as ArrayMesh
