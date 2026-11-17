extends Node
## Карты маршрутов для окна «План рейда» и полноэкранной карты на M: каждая
## рейдовая сцена маршрута (data/floors.json, scene) снимается сверху ортокамерой днём, без тумана и пределов
## дальности — assets/maps/<id>.webp; метки — выходы (имя, условие: ключ, рубильник, «не каждый рейд», без рюкзака)
## и заходы с края (SpawnPoint.entry) — data/raid_maps.json в мировых XZ, границы снимка — bounds сектора.
## tools/godot.cmd --windowed --resolution 1280x720 res://tools/raid_map_bake.tscn [-- id …]; затем --import.

const OUT_DIR := "res://assets/maps"
const OUT_JSON := "res://data/raid_maps.json"
## Ширина снимка, точки (высота — по пропорциям bounds).
const WIDTH := 2048
const CAM_HEIGHT := 700.0

var _maps: Dictionary = {}


func _ready() -> void:
	await get_tree().process_frame
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT_DIR))
	if FileAccess.file_exists(OUT_JSON):
		var old: Variant = JSON.parse_string(FileAccess.get_file_as_string(OUT_JSON))
		if old is Dictionary:
			_maps = (old as Dictionary).get("maps", {})
	var only := OS.get_cmdline_user_args()
	for f: Dictionary in Floors.all():
		var scene := String(f.get("scene", ""))
		if scene == "" or (not only.is_empty() and not String(f.id) in only):
			continue
		await _bake(String(f.id), scene)
	var out := {"_comment": "Карты маршрутов для окна «План рейда» и карты на M: снимок сверху (image), его границы в мировых XZ (bounds: x0, z0, x1, z1), "
		+ "граница участка (boundary), выходы и заходы с края. Север (-Z) вверху. Собирает tools/raid_map_bake.tscn.", "maps": _maps}
	var fa := FileAccess.open(OUT_JSON, FileAccess.WRITE)
	fa.store_string(JSON.stringify(out, " ", false) + "\n")
	fa.close()
	print("raid_map_bake: карт %d → %s" % [_maps.size(), OUT_JSON])
	get_tree().quit(0)


func _bake(id: String, scene_path: String) -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	var level: Node = (load(scene_path) as PackedScene).instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	# сектор и наполнение строятся первые кадры; выходы появляются со сценой
	for _i in range(900):
		await get_tree().process_frame
		if not get_tree().get_nodes_in_group("extractions").is_empty() and _i > 240:
			break
	var def: Dictionary = SectorBuilder.load_def(_sector_path(level, id))
	var b: Array = def.get("bounds", [-200, -200, 200, 200])
	var bounds := Rect2(float(b[0]), float(b[1]), float(b[2]) - float(b[0]), float(b[3]) - float(b[1]))
	# с высоты всё дальше пределов дальности (склейка пропсов, деревья) — на снимок показать всё; живых убрать
	for n: Node in level.find_children("*", "GeometryInstance3D", true, false):
		var gi := n as GeometryInstance3D
		gi.visibility_range_begin = 0.0
		gi.visibility_range_end = 0.0
	for group: String in ["marauders", "players", "rivals"]:
		for n: Node in get_tree().get_nodes_in_group(group):
			if n is Node3D:
				(n as Node3D).visible = false
	for n: Node in level.find_children("*", "DirectionalLight3D", true, false):
		(n as DirectionalLight3D).directional_shadow_max_distance = CAM_HEIGHT + bounds.size.length()
	var vp := SubViewport.new()
	vp.size = Vector2i(WIDTH, int(round(float(WIDTH) * bounds.size.y / bounds.size.x)))
	vp.world_3d = get_tree().root.world_3d
	vp.msaa_3d = Viewport.MSAA_4X
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(vp)
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = bounds.size.y
	cam.near = 1.0
	cam.far = CAM_HEIGHT + 400.0
	var c := bounds.get_center()
	cam.position = Vector3(c.x, CAM_HEIGHT, c.y)
	cam.rotation_degrees = Vector3(-90, 0, 0)
	# свой вид: без тумана и дымки уровня (с высоты всё уходило бы в молоко), ровный рассеянный свет
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.16, 0.17, 0.18)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.78, 0.8, 0.84)
	env.ambient_light_energy = 0.7
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_exposure = 1.05
	cam.environment = env
	vp.add_child(cam)
	cam.current = true
	for _i in range(30):
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var img: Image = vp.get_texture().get_image()
	var path := "%s/%s.webp" % [OUT_DIR, id]
	img.save_webp(ProjectSettings.globalize_path(path), true, 0.86)
	var exits: Array = []
	for n: Node in get_tree().get_nodes_in_group("extractions"):
		if not level.is_ancestor_of(n):
			continue
		var e := n as ExtractionPoint
		var p := e.global_position
		exits.append({"name": e.display_name if e.display_name != "" else String(e.name), "x": snappedf(p.x, 0.1), "z": snappedf(p.z, 0.1),
			"key": e.required_key, "switch": e.required_switch, "alt_key": e.alt_key, "chance": e.chance, "no_backpack": e.no_backpack,
			"rule": e.rule})
	var entries: Array = []
	for n: Node in get_tree().get_nodes_in_group("spawn_points"):
		if not level.is_ancestor_of(n) or not (n is SpawnPoint and (n as SpawnPoint).entry):
			continue
		var s := n as SpawnPoint
		entries.append({"name": s.display_name if s.display_name != "" else String(s.name), "x": snappedf(s.global_position.x, 0.1),
			"z": snappedf(s.global_position.z, 0.1)})
	_maps[id] = {"image": path, "bounds": b, "boundary": def.get("boundary", []), "exits": exits, "entries": entries}
	print("raid_map_bake: %s — %d×%d, выходов %d, заходов %d" % [id, vp.size.x, vp.size.y, exits.size(), entries.size()])
	vp.queue_free()
	get_tree().current_scene = null
	level.queue_free()
	for _i in range(30):
		await get_tree().process_frame


## Путь к данным сектора уровня (у рейдовой сцены — свойство sector_path у узла уровня).
func _sector_path(level: Node, id: String) -> String:
	for n: Node in [level] + level.find_children("*", "", true, false):
		if "sector_path" in n and String(n.get("sector_path")) != "":
			return String(n.get("sector_path"))
	return "res://data/sectors/%s.json" % id
