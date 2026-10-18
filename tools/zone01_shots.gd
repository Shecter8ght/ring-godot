extends Node
## Снимки зоны 1 «Городской пояс» в docs/screens/zone01_*.png: обзор с воздуха и виды с высоты глаз.
## tools/godot.cmd res://tools/zone01_shots.tscn       (ZONE01_ONLY=yard,plaza — выборочно)

const OUT_DIR := "res://docs/screens"
const SCENE := "res://scenes/levels/zone01_mall.tscn"

## имя: [откуда (x, над землёй, z), куда смотреть (x, y абсолютная, z), угол обзора]
const SHOTS := {
	"warmup": [Vector3(0, 300, 300), Vector3(0, 0, 0), 60.0],
	"aerial": [Vector3(0, 380, 420), Vector3(0, 0, 0), 50.0],
	"aerial_top": [Vector3(0, 760, 1), Vector3(0, 0, 0), 50.0],
	"aerial_swamp": [Vector3(-20, 140, -40), Vector3(-110, 0, -190), 55.0],
	"aerial_rail": [Vector3(120, 120, 60), Vector3(230, 0, 150), 55.0],
	"aerial_yard": [Vector3(-120, 70, 60), Vector3(-176, 0, -8), 55.0],
	"aerial_construction": [Vector3(20, 110, -10), Vector3(80, 0, -110), 55.0],
	"aerial_bus": [Vector3(-80, 100, 90), Vector3(-30, 0, 190), 55.0],
	"aerial_market": [Vector3(-120, 90, 140), Vector3(-190, 0, 180), 55.0],
	"aerial_houses": [Vector3(150, 70, -90), Vector3(200, 0, -160), 55.0],
	"swamp": [Vector3(-150, 1.7, -90), Vector3(-140, -1, -180), 70.0],
	"swamp_in": [Vector3(-30, 2.4, -193), Vector3(-100, -0.5, -240), 70.0],
	"ravine_n": [Vector3(60, 1.7, -245), Vector3(120, -5, -275), 70.0],
	"rail_bridge": [Vector3(230, 1.7, -62), Vector3(289, 3, -56), 70.0],
	"rail_yard": [Vector3(232, 2.5, 118), Vector3(219, 3.0, 175), 70.0],
	"station_site": [Vector3(150, 1.7, 120), Vector3(200, 2, 170), 70.0],
	"bus_site": [Vector3(-90, 1.7, 115), Vector3(-20, 1, 200), 70.0],
	"construction_site": [Vector3(60, 1.7, -40), Vector3(90, 8, -150), 70.0],
	"market": [Vector3(-140, 1.7, 100), Vector3(-200, 1, 180), 70.0],
	"residential": [Vector3(-30, 1.7, 30), Vector3(-90, 5, 0), 70.0],
	"sports": [Vector3(20, 1.7, 80), Vector3(50, 1, 40), 70.0],
	"yard": [Vector3(-172, 1.7, 31), Vector3(-188, 7, -39), 70.0],
	"yard_entrance": [Vector3(-176, 1.7, -21), Vector3(-188, 4, -35), 70.0],
	"yard_brick": [Vector3(-188, 1.7, 9), Vector3(-208, 5, 17), 70.0],
	"yard_k2": [Vector3(-162, 1.7, -3), Vector3(-136, 6, -15), 70.0],
	"yard_bins": [Vector3(-147, 1.7, 21), Vector3(-157, 0.6, 31), 70.0],
	"yard_cars": [Vector3(-176, 1.7, -15), Vector3(-166, 0.5, -21), 70.0],
	"wall_n": [Vector3(-182, 1.7, -50), Vector3(-188, 1.5, -47.5), 70.0],
	"wall_s": [Vector3(-182, 1.7, -32), Vector3(-194, 1, -34), 70.0],
	"wall_e": [Vector3(-156, 1.7, -39), Vector3(-160, 1, -45), 70.0],
	"shadow_k2": [Vector3(-115, 1.7, 1), Vector3(-124, 0, -11), 70.0],
	"shadow_k2b": [Vector3(-108, 1.7, -23), Vector3(-126, 2, -7), 70.0],
	"shadow_close": [Vector3(-122.6, 1.7, -7), Vector3(-124.5, 0, -1), 75.0],
	"sun_shadow": [Vector3(-117, 1.7, -15), Vector3(0, 0, 0), 75.0],
	"porch_k3": [Vector3(-195, 1.7, 33), Vector3(-206, 1, 22.5), 75.0],
	"yard_garages": [Vector3(-208, 1.7, -31), Vector3(-246, 3, -53), 70.0],
	"ravine": [Vector3(240, 1.8, -163), Vector3(210, -6, -225), 70.0],
	"ravine_bottom": [Vector3(251, 1.7, -125), Vector3(254, -3, -75), 70.0],
	"forest_road": [Vector3(-280, 1.7, -200), Vector3(-290, 1, -270), 70.0],
	"spruce_close": [Vector3(20, 1.7, 280), Vector3(30, 6, 295), 70.0],
	"birch_close": [Vector3(-188, 1.7, 1), Vector3(-190, 5, 15), 70.0],
	"pine_grove": [Vector3(-60, 1.7, 280), Vector3(-80, 9, 295), 70.0],
	"pine_old": [Vector3(-40, 1.7, 60), Vector3(-55, 8, 75), 70.0],
	"pine_yard": [Vector3(-174, 1.7, 5), Vector3(-184, 8, 25), 70.0],
	"rain_up": [Vector3(-172, 1.7, 1), Vector3(-172, 30, 17), 75.0],
	"rain_street": [Vector3(-181, 1.7, -25), Vector3(-161, 1, -23), 70.0],
	"sun_forest": [Vector3(-60, 1.7, 280), Vector3(0, 0, 0), 70.0],
	"forest_floor": [Vector3(-60, 1.7, 280), Vector3(-56, 0, 287), 75.0],
	"sun_yard": [Vector3(-176, 1.7, -3), Vector3(0, 0, 0), 70.0],
	"garages": [Vector3(215, 1.7, 47), Vector3(180, 1, 47), 70.0],
	"overpass_under": [Vector3(-20, 1.7, 232), Vector3(60, 6, 250), 70.0],
	"supermarket": [Vector3(8, 1.7, 46), Vector3(35, 3, 6), 70.0],
	"cinema": [Vector3(40, 1.7, 150), Vector3(81, 5, 112), 70.0],
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
	var we := level.find_child("WorldEnvironment", true, false) as WorldEnvironment
	if we and "nosdfgi" in perf:
		we.environment.sdfgi_enabled = false
	if we and "nossil" in perf:
		we.environment.ssil_enabled = false
	if we and "novol" in perf:
		we.environment.volumetric_fog_enabled = false
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
			if shot_name == "sun_shadow":
				# из тени дома — к солнцу, взгляд на землю
				var sun0 := level.find_child("Sun", true, false) as DirectionalLight3D
				var ts: Vector3 = sun0.global_basis.z
				target = from + Vector3(ts.x, 0.0, ts.z).normalized() * 8.0 + Vector3(0, -1.7, 0)
			elif shot_name.begins_with("sun_"):
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
			await get_tree().create_timer(float(OS.get_environment("ZONE01_UP_SEC")) if OS.has_environment("ZONE01_UP_SEC") else 4.0).timeout
		if ground_shot:
			print("  игрок ", me.global_position, " камера ", get_viewport().get_camera_3d().global_position, " взгляд ", -get_viewport().get_camera_3d().global_basis.z)
		var img := get_viewport().get_texture().get_image()
		var out := ProjectSettings.globalize_path("%s/zone01_%s.png" % [OUT_DIR, shot_name])
		img.save_png(out)
		print("zone01_shots: %s  FPS %d, отрисовок %d, примитивов %d" % [shot_name, Engine.get_frames_per_second(),
			RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
			RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)])
	get_tree().quit(0)
