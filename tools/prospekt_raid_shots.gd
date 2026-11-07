extends Node
## Свет «Проспекта» в рейде (tools/prospekt_light.py): день / закат / ночь × ясно / пасмурно / дождь / туман / жара,
## с одних точек (проспект, площадь, зал супермаркета). Уровень грузится заново на каждое условие, мародёры убраны,
## интерфейс скрыт. По умолчанию — глазами игрока: его камера с привыканием глаза и «объективом» (CameraLook),
## как видит игрок; PROSPEKT_CLEAN=1 — своей камерой без них (чистый свет сцены).
##   tools/godot.cmd --windowed --resolution 1600x900 res://tools/prospekt_raid_shots.tscn
## → PROSPEKT_OUTPUT (по умолчанию user://prospekt_raid_shots)/<условие>__<кадр>.png; PROSPEKT_CASES=day,night — выборочно.
## PROSPEKT_VIEWS=avenue,hall — точки; PROSPEKT_HIDE_LABELS=1 — убрать подписи блокаута;
## PROSPEKT_ANGULAR=0 — сравнить с обычной фильтрацией теней без PCSS.
## RAID_LIGHT_SCENE=res://… — другая карта; RAID_LIGHT_VIEW=имя:x:y:z:куда_x:куда_y:куда_z;… — её камеры.
## RAID_LIGHT_REUSE=1 — переключать условия на одной карте (проверяет и переходы погоды без повторного навмеша).

const SCENE: String = "res://scenes/levels/prospekt.tscn"
const CASES: Array[Dictionary] = [
	{"id": "day", "time": "day", "weather": "clear"},
	{"id": "dusk", "time": "dusk", "weather": "clear"},
	{"id": "night", "time": "night", "weather": "clear"},
	{"id": "day_overcast", "time": "day", "weather": "overcast"},
	{"id": "day_rain", "time": "day", "weather": "rain"},
	{"id": "day_fog", "time": "day", "weather": "fog"},
	{"id": "day_heat", "time": "day", "weather": "heat"},
	{"id": "dusk_overcast", "time": "dusk", "weather": "overcast"},
	{"id": "dusk_rain", "time": "dusk", "weather": "rain"},
	{"id": "dusk_fog", "time": "dusk", "weather": "fog"},
	{"id": "dusk_heat", "time": "dusk", "weather": "heat"},
	{"id": "night_overcast", "time": "night", "weather": "overcast"},
	{"id": "night_rain", "time": "night", "weather": "rain"},
	{"id": "night_fog", "time": "night", "weather": "fog"},
	{"id": "night_heat", "time": "night", "weather": "heat"},
]
const VIEWS: Array[Dictionary] = [
	{"id": "avenue", "at": Vector3(-170, 1.62, -40.93), "look": Vector3(-60, 2, -29.26)},
	{"id": "plaza", "at": Vector3(100.91, 1.62, 47.79), "look": Vector3(121.3, 2, -16.3)},
	{"id": "hall", "at": Vector3(-108, 1.62, 50), "look": Vector3(-102, 1.5, 82)},
]
## SDFGI набирает отражённый свет и глаз привыкает не сразу
const SETTLE_FRAMES: int = 240
## Слои, которые остаются: капли на линзе, «объектив» камеры игрока
const KEEP_LAYERS: Array[String] = ["LensLayer"]


func _ready() -> void:
	Profile.use_file("user://profile_prospekt_light_test.json", true)
	Profile.ensure()
	RaidEvents.enabled = false
	get_tree().node_added.connect(func(n: Node) -> void:
		if n is Marauder:
			n.process_mode = Node.PROCESS_MODE_DISABLED
			(n as Node3D).visible = false)
	var scene_path: String = OS.get_environment("RAID_LIGHT_SCENE")
	if scene_path == "":
		scene_path = SCENE
	var shot_views: Array[Dictionary] = VIEWS.duplicate()
	if OS.get_environment("RAID_LIGHT_VIEW") != "":
		shot_views.clear()
		for spec: String in OS.get_environment("RAID_LIGHT_VIEW").split(";", false):
			var p: PackedStringArray = spec.split(":")
			if p.size() == 7:
				shot_views.append({"id": p[0], "at": Vector3(p[1].to_float(), p[2].to_float(), p[3].to_float()),
					"look": Vector3(p[4].to_float(), p[5].to_float(), p[6].to_float())})
	var clean: bool = OS.get_environment("PROSPEKT_CLEAN") != ""
	if clean:
		Settings.lens_fx = false
	var out_dir: String = OS.get_environment("PROSPEKT_OUTPUT")
	if out_dir.is_empty():
		out_dir = ProjectSettings.globalize_path("user://prospekt_raid_shots")
	DirAccess.make_dir_recursive_absolute(out_dir)
	var only: PackedStringArray = OS.get_environment("PROSPEKT_CASES").split(",", false)
	var views: PackedStringArray = OS.get_environment("PROSPEKT_VIEWS").split(",", false)
	var reuse: bool = OS.get_environment("RAID_LIGHT_REUSE") == "1"
	var level: Node = null
	for c: Dictionary in CASES:
		if not only.is_empty() and not String(c.id) in only:
			continue
		RaidConditions.from_host = {"time": c.time, "weather": c.weather, "power": "on"}
		if level == null:
			level = (load(scene_path) as PackedScene).instantiate()
			# корень ещё расставляет детей (первый кадр) — добавить отложенно
			get_tree().root.add_child.call_deferred(level)
			await _frames(2)
			get_tree().current_scene = level
		else:
			RaidConditions.current = RaidConditions.from_host.duplicate()
			AtmosphereSky.reset_blend()
			RaidAtmosphere.current.apply()
			RaidWeather.current.conditions_changed()
			if DayCycle.current:
				DayCycle.current.set_hour(float((Balance.RAID_TIME[String(c.time)] as Dictionary).start_hour))
		# Население ещё ждёт навмеш: не создавать бойцов для съёмки света.
		var population: AIPopulation = level.get_node_or_null("Population") as AIPopulation
		if population:
			population.posts_only = true
			population.keep_posts.clear()
		for warden: Node in level.find_children("*", "Node3D", true, false):
			if warden is GateWarden:
				warden.set_physics_process(false)
		await _frames(30)
		if OS.get_environment("PROSPEKT_HIDE_LABELS") == "1":
			for label: Node in level.find_children("*", "Label3D", true, false):
				(label as Label3D).visible = false
		var marauders: Node = level.get_node_or_null("Marauders")
		if marauders:
			for m: Node in marauders.get_children():
				m.queue_free()
		# прячем интерфейс (HUD уровня и игрока); погода (капли на линзе) и «объектив» остаются
		for layer: Node in get_tree().root.find_children("*", "CanvasLayer", true, false):
			if not (String(layer.name) in KEEP_LAYERS or layer is RainLens):
				(layer as CanvasLayer).visible = false
		var me: Player = Raid.current.local_player() if Raid.current else null
		var rig: CameraRig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
		var camera: Camera3D = null
		if clean or me == null or rig == null:
			camera = Camera3D.new()
			# слои — как у камеры игрока: служебные (карта дождя «что над головой») ей не видны
			var player_cam: Camera3D = get_viewport().get_camera_3d()
			if player_cam:
				camera.cull_mask = player_cam.cull_mask
			camera.fov = Settings.fps_fov_v()
			camera.far = 2000.0
			level.add_child(camera)
			camera.make_current()
		else:
			me.health.hp = 1e9
			me.health.max_hp = 1e9
			CameraRig.first_person_mode = true
		var sun: DirectionalLight3D = level.get_node_or_null("Sun") as DirectionalLight3D
		if sun and OS.get_environment("PROSPEKT_ANGULAR") != "":
			sun.light_angular_distance = float(OS.get_environment("PROSPEKT_ANGULAR"))
		var we: WorldEnvironment = level.find_child("WorldEnvironment", false, false) as WorldEnvironment
		# для поиска причин: PROSPEKT_ENV_OFF=sdfgi,ssao,fog,adjustment — выключить части окружения
		for part: String in OS.get_environment("PROSPEKT_ENV_OFF").split(",", false):
			we.environment.set(part + "_enabled", false)
		print("prospekt_raid_shots: %s — солнце %.2f (%s), рассеянный %.2f, выдержка %.2f, дымка %s %.2f, %s" % [c.id,
			sun.light_energy if sun else 0.0, "видно" if sun and sun.visible else "нет",
			we.environment.ambient_light_energy, we.environment.tonemap_exposure,
			"вкл" if we.environment.fog_enabled else "выкл", we.environment.fog_density,
			"своя камера" if camera else "глазами игрока"])
		for view: Dictionary in shot_views:
			if not views.is_empty() and not String(view.id) in views:
				continue
			var at: Vector3 = view.at
			var look: Vector3 = view.look
			if camera:
				camera.global_position = at
				camera.look_at(look, Vector3.UP)
			else:
				me.global_position = Vector3(at.x, at.y - float(Balance.ADS_EYE.stand), at.z)
				me.velocity = Vector3.ZERO
				var d: Vector3 = look - at
				rig._look_yaw = atan2(d.x, d.z)
				rig._look_pitch = atan2(d.y, Vector2(d.x, d.z).length())
			await _frames(SETTLE_FRAMES)
			await RenderingServer.frame_post_draw
			var path: String = out_dir.path_join("%s__%s.png" % [c.id, view.id])
			print("prospekt_raid_shots: снимок ", path, " ошибка=", get_viewport().get_texture().get_image().save_png(path))
		if not reuse:
			level.queue_free()
			level = null
			await _frames(10)
	if level:
		level.queue_free()
		await _frames(10)
	get_tree().quit()


func _frames(count: int) -> void:
	for i: int in range(count):
		await get_tree().process_frame
