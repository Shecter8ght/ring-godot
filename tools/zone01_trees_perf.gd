extends Node
## Клёны и тополя зоны 1 (tools/zone01_trees): кадры в секунду и снимки там, где они стоят — двор хрущёвок, ряд тополей
## у дороги, клёны в центре, тополя на севере, опушка, вид сверху. Камера в точке, кадры прогреваются, затем среднее
## время кадра и 1 % худших; снимок кадра — docs/screens/zone01_trees/<метка>_<точка>.png.
## С аргументом «off» клёны и тополя (DistrictScatter tree_maple_* / tree_poplar_*) скрыты — сравнение в одной сборке.
##   tools/godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/zone01_trees_perf.tscn [-- off]
## ZONE01_TREES_TAG=до|после — метка снимков и отчёта; ZONE01_TREES_ONLY=имя,имя — выборочно; ZONE01_TIME, ZONE01_WEATHER — условия;
## ZONE01_QUALITY=low|medium|high — качество графики на время замера (в настройки игрока не пишется).

const SCENE: String = "res://scenes/levels/zone01_mall.tscn"
const OUT_DIR: String = "res://docs/screens/zone01_trees"
const WARM: int = 120
const MEASURE: int = 300
## Точка: имя, камера (x, над землёй, z), куда смотрит (x, y абсолютная, z), угол обзора.
const VIEWS: Array = [
	["двор_клёны", Vector3(-160, 1.7, 42), Vector3(-178, 6, 8), 70.0],
	["двор_ряд_тополей", Vector3(-150, 1.7, -63), Vector3(-212, 8, -55), 70.0],
	["центр_клёны", Vector3(5, 1.7, -22), Vector3(-15, 6, -55), 70.0],
	["север_с_высоты", Vector3(-80, 35, 205), Vector3(-125, 6, 258), 60.0],
	["опушка_вблизи", Vector3(-12, 1.7, -40), Vector3(-6, 9, -52), 75.0],
	["сверху", Vector3(0, 380, 420), Vector3(0, 0, 0), 50.0],
]
## Крупные планы для осмотра (в замер не входят; только по ZONE01_TREES_ONLY): клён дворовый и ясенелистный с ~10 м.
const CLOSE_VIEWS: Array = [
	["клён_вблизи", Vector3(-1.5, 1.7, -52), Vector3(-7.5, 5, -60.2), 70.0],
	["ясенелистный_вблизи", Vector3(-4, 1.7, -19), Vector3(-10.6, 3.5, -25.1), 70.0],
	["тополь_вблизи", Vector3(-3, 1.7, -55), Vector3(-10.7, 9, -65.8), 70.0],
]

var camera: Camera3D


func _ready() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	var hide_trees: bool = OS.get_cmdline_user_args().has("off")
	var only: PackedStringArray = OS.get_environment("ZONE01_TREES_ONLY").split(",", false)
	var tag: String = OS.get_environment("ZONE01_TREES_TAG") if OS.get_environment("ZONE01_TREES_TAG") != "" else "снимок"
	RaidConditions.from_host = {"time": OS.get_environment("ZONE01_TIME") if OS.has_environment("ZONE01_TIME") else "day",
		"weather": OS.get_environment("ZONE01_WEATHER") if OS.has_environment("ZONE01_WEATHER") else "clear", "power": "on"}
	# качество графики на время замера, без записи в настройки игрока (ZONE01_QUALITY=low|medium|high)
	var quality: String = OS.get_environment("ZONE01_QUALITY")
	if quality in Settings.QUALITY:
		Settings.quality = quality
		Settings.apply_graphics()
		Settings.changed.emit()
	var level: Node = (load(SCENE) as PackedScene).instantiate()
	get_tree().root.add_child.call_deferred(level)
	await get_tree().process_frame
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	# мародёры не нужны в кадре (и не стреляют в «оператора»)
	for m: Node in level.get_node("Marauders").get_children():
		m.queue_free()
	for layer: Node in get_tree().root.find_children("*", "CanvasLayer", true, false):
		(layer as CanvasLayer).visible = false
	var packs: int = 0
	var trees: int = 0
	for scat: Node in level.find_children("*", "Node3D", true, false):
		if scat is DistrictScatter:
			var key: String = (scat as DistrictScatter).key
			if key.begins_with("tree_maple") or key.begins_with("tree_poplar"):
				(scat as Node3D).visible = not hide_trees
				for mmi: Node in scat.get_children():
					if mmi is MultiMeshInstance3D:
						packs += 1
						if String(mmi.name).begins_with("_Cell"):
							trees += (mmi as MultiMeshInstance3D).multimesh.instance_count
	var terrain := level.find_child("Terrain", true, false) as DistrictTerrain
	var me: Node3D = Raid.current.local_player() if Raid.current else null
	camera = Camera3D.new()
	camera.far = 3000.0
	camera.cull_mask &= ~RainOcclusion.LAYER
	level.add_child(camera)
	camera.make_current()
	var label: String = "%s_%s" % [tag, "без_клёнов_и_тополей" if hide_trees else "с_клёнами_и_тополями"]
	print("zone01_trees_perf: %s, пачек %d, деревьев %d" % [label, packs, trees])
	print("  %-18s %8s %8s %8s %10s %8s" % ["точка", "FPS", "мс", "1% мс", "треуг.", "вызовов"])
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT_DIR))
	var lines: PackedStringArray = [label]
	var total: float = 0.0
	var count: int = 0
	for v: Array in VIEWS + CLOSE_VIEWS:
		if (only.is_empty() and v in CLOSE_VIEWS) or (not only.is_empty() and not String(v[0]) in only):
			continue
		var from: Vector3 = v[1]
		if terrain and from.y < 50.0:
			from.y += terrain.height_at(from.x, from.z)
		if me:
			# игрок рядом с камерой (окружение вокруг него), но в кадре его не видно
			me.global_position = from - Vector3(0, 1.7, 0)
			me.visible = false
		# руки и ствол от первого лица висят у камеры игрока (CameraRig, ViewmodelSpace) — тоже не в кадр
		for vm: Node in get_tree().root.find_children("ViewmodelSpace", "Node3D", true, false):
			(vm as Node3D).visible = false
		camera.fov = float(v[3])
		camera.global_position = from
		camera.look_at(v[2], Vector3.UP)
		camera.current = true
		for i: int in range(WARM):
			await get_tree().process_frame
		var times: Array[float] = []
		var t0: int = Time.get_ticks_usec()
		for i: int in range(MEASURE):
			await get_tree().process_frame
			var t1: int = Time.get_ticks_usec()
			times.append(float(t1 - t0) / 1000.0)
			t0 = t1
		times.sort()
		var mean: float = 0.0
		for t: float in times:
			mean += t
		mean /= float(times.size())
		var worst: float = times[int(times.size() * 0.99)]
		var tris: int = int(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME))
		var draws: int = int(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME))
		var line: String = "  %-18s %8.1f %8.2f %8.2f %10d %8d" % [String(v[0]), 1000.0 / mean, mean, worst, tris, draws]
		print(line)
		lines.append(line)
		total += mean
		count += 1
		if not hide_trees:
			var img: Image = get_viewport().get_texture().get_image()
			img.save_png(ProjectSettings.globalize_path("%s/%s_%s.png" % [OUT_DIR, tag, String(v[0])]))
	if count > 0:
		var avg: String = "  среднее: %.1f к/с (%.2f мс)" % [1000.0 / (total / count), total / count]
		print(avg)
		lines.append(avg)
	var f: FileAccess = FileAccess.open("user://zone01_trees_perf_%s.txt" % label, FileAccess.WRITE)
	f.store_string("\n".join(lines) + "\n")
	f.close()
	get_tree().quit()
