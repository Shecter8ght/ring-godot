extends Node
## Снимки зоны 1 (район ТЦ) в docs/screens/zone01_*.png: обзор с воздуха и виды с высоты глаз.
## tools/godot.cmd res://tools/zone01_shots.tscn       (ZONE01_ONLY=yard,plaza — выборочно)

const OUT_DIR := "res://docs/screens"
const SCENE := "res://scenes/levels/zone01_mall.tscn"

## имя: [откуда (x, над землёй, z), куда смотреть (x, y абсолютная, z), угол обзора]
const SHOTS := {
	"warmup": [Vector3(0, 300, 300), Vector3(0, 0, 0), 60.0],
	"aerial": [Vector3(40, 380, 420), Vector3(0, 0, 20), 50.0],
	"aerial_top": [Vector3(15, 760, 41), Vector3(15, 0, 40), 50.0],
	"aerial_yard": [Vector3(-120, 70, -20), Vector3(-200, 0, -105), 55.0],
	"plaza": [Vector3(30, 1.7, -152), Vector3(0, 12, 0), 70.0],
	"yard": [Vector3(-196, 1.7, -66), Vector3(-212, 7, -136), 70.0],
	"yard_entrance": [Vector3(-200, 1.7, -118), Vector3(-212, 4, -132), 70.0],
	"yard_brick": [Vector3(-212, 1.7, -88), Vector3(-232, 5, -80), 70.0],
	"yard_k2": [Vector3(-186, 1.7, -100), Vector3(-160, 6, -112), 70.0],
	"yard_bins": [Vector3(-171, 1.7, -76), Vector3(-181, 0.6, -66), 70.0],
	"yard_cars": [Vector3(-200, 1.7, -112), Vector3(-190, 0.5, -118), 70.0],
	"yard_garages": [Vector3(-232, 1.7, -128), Vector3(-270, 3, -150), 70.0],
	"ravine": [Vector3(-330, 1.8, 38), Vector3(-300, -6, 100), 70.0],
	"ravine_bottom": [Vector3(-341, 1.7, 0), Vector3(-344, -3, -50), 70.0],
	"overpass": [Vector3(0, 1.7, -140), Vector3(0, 3, -200), 70.0],
	"embankment": [Vector3(-80, 1.7, -160), Vector3(-20, 6, -192), 70.0],
	"hill": [Vector3(120, 1.7, 100), Vector3(370, 20, 185), 60.0],
	"hill_top": [Vector3(360, 1.7, 175), Vector3(150, 0, 60), 70.0],
	"loading": [Vector3(42, 1.7, 182), Vector3(-5, -3, 130), 70.0],
	"forest_road": [Vector3(-3, 1.7, 225), Vector3(-2, 1, 295), 70.0],
	"spruce_close": [Vector3(30, 1.7, 236), Vector3(40, 6, 252), 70.0],
	"birch_close": [Vector3(-212, 1.7, -96), Vector3(-214, 5, -82), 70.0],
	"rain_up": [Vector3(-196, 1.7, -96), Vector3(-196, 30, -80), 75.0],
	"rain_street": [Vector3(-205, 1.7, -122), Vector3(-185, 1.0, -120), 70.0],
	"sun_forest": [Vector3(-60, 1.7, 240), Vector3(0, 0, 0), 70.0],
	"sun_yard": [Vector3(-200, 1.7, -100), Vector3(0, 0, 0), 70.0],
	"garages": [Vector3(250, 1.7, -110), Vector3(300, 4, -20), 70.0],
}


func _ready() -> void:
	var only: PackedStringArray = OS.get_environment("ZONE01_ONLY").split(",", false)
	# условия рейда для снимков: ZONE01_TIME=day|dusk|night, ZONE01_WEATHER=clear|rain|fog|heat
	RaidConditions.from_host = {"time": OS.get_environment("ZONE01_TIME") if OS.has_environment("ZONE01_TIME") else "day",
		"weather": OS.get_environment("ZONE01_WEATHER") if OS.has_environment("ZONE01_WEATHER") else "clear", "power": "on"}
	# ZONE01_SKY=имя — подменить панораму неба (сравнение вариантов): assets/sky/<имя>.hdr
	if OS.get_environment("ZONE01_SKY") != "":
		RaidAtmosphere.hdri_override = "res://assets/sky/%s.hdr" % OS.get_environment("ZONE01_SKY")
	var level: Node = (load(SCENE) as PackedScene).instantiate()
	get_tree().root.add_child.call_deferred(level)
	await get_tree().process_frame
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	# мародёры не нужны в кадре (и не стреляют в «оператора»)
	for m in level.get_node("Marauders").get_children():
		m.queue_free()
	var me: Node3D = Raid.current.local_player()
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	for layer: Node in get_tree().root.find_children("*", "CanvasLayer", true, false):
		(layer as CanvasLayer).visible = false
	var terrain := level.find_child("Terrain", true, false) as DistrictTerrain
	var debug_view: int = int(OS.get_environment("ZONE01_DEBUG"))
	if terrain and debug_view > 0:
		for mi: Node in terrain.find_children("*", "MeshInstance3D", true, false):
			((mi as MeshInstance3D).mesh.surface_get_material(0) as ShaderMaterial).set_shader_parameter("debug_view", debug_view)
			break
	# замер: ZONE01_PERF=noterrain,nograss,notrees,noshadow — что отключить
	var perf: PackedStringArray = OS.get_environment("ZONE01_PERF").split(",", false)
	if terrain and "noterrain" in perf:
		var plain := StandardMaterial3D.new()
		for mi: Node in terrain.find_children("*", "MeshInstance3D", true, false):
			(mi as MeshInstance3D).material_override = plain
	for scat: Node in level.find_children("*", "Node3D", true, false):
		if scat is DistrictScatter:
			var is_grass: bool = (scat as DistrictScatter).key == "grass"
			if (is_grass and "nograss" in perf) or (not is_grass and "notrees" in perf):
				(scat as Node3D).visible = false
	if "noshadow" in perf:
		for l: Node in level.find_children("*", "DirectionalLight3D", true, false):
			(l as DirectionalLight3D).shadow_enabled = false
	var cam := Camera3D.new()
	cam.far = 3000.0
	# служебный слой карты дождя (RainOcclusion) — не для глаз, как у камеры игрока
	cam.cull_mask &= ~RainOcclusion.LAYER
	level.add_child(cam)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT_DIR))
	for shot_name: String in SHOTS:
		if not only.is_empty() and not shot_name in only:
			continue
		var shot: Array = SHOTS[shot_name]
		var from: Vector3 = shot[0]
		# глазами игрока (ZONE01_PLAYERCAM=1) — пока ненадёжно: риг сглаживает взгляд
		var ground_shot: bool = OS.get_environment("ZONE01_PLAYERCAM") == "1" and from.y < 50.0 and me != null and rig != null
		if terrain and from.y < 50.0:
			from.y += terrain.height_at(from.x, from.z)
		if ground_shot:
			# с земли — глазами игрока: дождь, капли и карта «что над головой» следуют за его камерой
			cam.current = false
			me.global_position = from - Vector3(0, 1.6, 0)
			CameraRig.first_person_mode = true
			for i in range(3):
				await get_tree().process_frame
			var d: Vector3 = (shot[1] as Vector3) - from
			# вперёд у камеры игрока — (sin yaw, 0, cos yaw)
			rig._look_yaw = atan2(d.x, d.z)
			rig._look_pitch = atan2(d.y, Vector2(d.x, d.z).length())
		else:
			if me and from.y < 60.0:
				me.global_position = from - Vector3(0, 1.7, 0)
			cam.fov = float(shot[2])
			cam.global_position = from
			var target: Vector3 = shot[1]
			if shot_name.begins_with("sun_"):
				# против солнца: направление на солнце (свет идёт вдоль −Z узла), чуть вверх
				var sun := level.find_child("Sun", true, false) as DirectionalLight3D
				var to_sun: Vector3 = sun.global_basis.z
				to_sun.y = clampf(to_sun.y, 0.08, 0.3)
				target = from + to_sun.normalized() * 50.0
			cam.look_at(target, Vector3.UP)
			cam.current = true
		for i in range(90):
			await get_tree().process_frame
		if shot_name.ends_with("_up"):
			await get_tree().create_timer(4.0).timeout
		if ground_shot:
			print("  игрок ", me.global_position, " камера ", get_viewport().get_camera_3d().global_position, " взгляд ", -get_viewport().get_camera_3d().global_basis.z)
		var img := get_viewport().get_texture().get_image()
		var out := ProjectSettings.globalize_path("%s/zone01_%s.png" % [OUT_DIR, shot_name])
		img.save_png(out)
		print("zone01_shots: %s  FPS %d, отрисовок %d, примитивов %d" % [shot_name, Engine.get_frames_per_second(),
			RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
			RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)])
	get_tree().quit(0)
