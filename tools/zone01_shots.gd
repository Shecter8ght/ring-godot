extends Node
## Снимки зоны 1 «Городской пояс» в docs/screens/zone01_*.png: обзор с воздуха и виды с высоты глаз.
## tools/godot.cmd res://tools/zone01_shots.tscn       (ZONE01_ONLY=yard,plaza — выборочно)

const OUT_DIR := "res://docs/screens"
const SCENE := "res://scenes/levels/zone01_mall.tscn"

## имя: [откуда (x, над землёй, z), куда смотреть (x, y абсолютная, z), угол обзора]
const SHOTS := {
	"warmup": [Vector3(0, 300, 300), Vector3(0, 0, 0), 60.0],
	"aerial": [Vector3(-60, 380, 420), Vector3(-60, 0, -20), 50.0],
	"aerial_top": [Vector3(-67, 760, -14), Vector3(-67, 0, -15), 50.0],
	"aerial_swamp": [Vector3(-60, 140, -60), Vector3(-130, 0, -250), 55.0],
	"aerial_rail": [Vector3(60, 120, -20), Vector3(210, 0, -100), 55.0],
	"aerial_yard": [Vector3(-120, 70, -20), Vector3(-200, 0, -105), 55.0],
	"swamp": [Vector3(-120, 1.7, -172), Vector3(-130, -1, -250), 70.0],
	"swamp_in": [Vector3(-160, 1.7, -238), Vector3(-90, -1, -270), 70.0],
	"river": [Vector3(40, 1.7, -280), Vector3(120, -1, -306), 70.0],
	"rail_gap": [Vector3(150, 1.7, -60), Vector3(215, 2, -60), 70.0],
	"rail_north": [Vector3(191, 1.7, -100), Vector3(205, 3, -240), 70.0],
	"station_site": [Vector3(100, 1.7, 60), Vector3(160, 1, 170), 70.0],
	"bus_site": [Vector3(-10, 1.7, 60), Vector3(-10, 1, 160), 70.0],
	"construction_site": [Vector3(90, 1.7, -60), Vector3(100, 1, -160), 70.0],
	"yard": [Vector3(-196, 1.7, -66), Vector3(-212, 7, -136), 70.0],
	"yard_entrance": [Vector3(-200, 1.7, -118), Vector3(-212, 4, -132), 70.0],
	"yard_brick": [Vector3(-212, 1.7, -88), Vector3(-232, 5, -80), 70.0],
	"yard_k2": [Vector3(-186, 1.7, -100), Vector3(-160, 6, -112), 70.0],
	"yard_bins": [Vector3(-171, 1.7, -76), Vector3(-181, 0.6, -66), 70.0],
	"yard_cars": [Vector3(-200, 1.7, -112), Vector3(-190, 0.5, -118), 70.0],
	"wall_n": [Vector3(-206, 1.7, -147), Vector3(-212, 1.5, -144.5), 70.0],
	"wall_s": [Vector3(-206, 1.7, -129), Vector3(-218, 1.0, -131), 70.0],
	"wall_e": [Vector3(-180, 1.7, -136), Vector3(-184, 1.0, -142), 70.0],
	"shadow_k2": [Vector3(-139, 1.7, -96), Vector3(-148, 0.0, -108), 70.0],
	"shadow_k2b": [Vector3(-132, 1.7, -120), Vector3(-150, 2.0, -104), 70.0],
	"shadow_close": [Vector3(-146.6, 1.7, -104), Vector3(-148.5, 0.0, -98), 75.0],
	"sun_shadow": [Vector3(-141, 1.7, -112), Vector3(0, 0, 0), 75.0],
	"porch_k3": [Vector3(-219, 1.7, -64), Vector3(-230, 1.0, -74.5), 75.0],
	"yard_garages": [Vector3(-232, 1.7, -128), Vector3(-270, 3, -150), 70.0],
	"ravine": [Vector3(-330, 1.8, 38), Vector3(-300, -6, 100), 70.0],
	"ravine_bottom": [Vector3(-341, 1.7, 0), Vector3(-344, -3, -50), 70.0],
	"forest_road": [Vector3(-292, 1.7, -205), Vector3(-330, 1, -280), 70.0],
	"spruce_close": [Vector3(20, 1.7, 285), Vector3(30, 6, 300), 70.0],
	"birch_close": [Vector3(-212, 1.7, -96), Vector3(-214, 5, -82), 70.0],
	"pine_grove": [Vector3(-60, 1.7, 284), Vector3(-80, 9, 300), 70.0],
	"pine_old": [Vector3(-152, 1.7, 160), Vector3(-165.7, 8, 178), 70.0],
	"pine_yard": [Vector3(-198, 1.7, -92), Vector3(-208, 8, -72), 70.0],
	"rain_up": [Vector3(-196, 1.7, -96), Vector3(-196, 30, -80), 75.0],
	"rain_street": [Vector3(-205, 1.7, -122), Vector3(-185, 1.0, -120), 70.0],
	"sun_forest": [Vector3(-60, 1.7, 284), Vector3(0, 0, 0), 70.0],
	"forest_floor": [Vector3(-60, 1.7, 284), Vector3(-56, 0, 291), 75.0],
	"sun_yard": [Vector3(-200, 1.7, -100), Vector3(0, 0, 0), 70.0],
	"garages": [Vector3(191, 1.7, -100), Vector3(191, 2, -200), 70.0],
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
