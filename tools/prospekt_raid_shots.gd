extends Node
## Свет «Проспекта» в рейде (tools/prospekt_light.py): та же карта по условиям — день, закат, ночь, дождь, —
## с одних точек (проспект, площадь, зал супермаркета). Уровень грузится заново на каждое условие, мародёры убраны,
## интерфейс скрыт (резкость карты — нет).
##   tools/godot.cmd --windowed --resolution 1600x900 res://tools/prospekt_raid_shots.tscn
## → PROSPEKT_OUTPUT (по умолчанию user://prospekt_raid_shots)/<условие>__<кадр>.png; PROSPEKT_CASES=day,night — выборочно.

const SCENE: String = "res://scenes/levels/prospekt.tscn"
const CASES: Array[Dictionary] = [
	{"id": "day", "time": "day", "weather": "clear"},
	{"id": "dusk", "time": "dusk", "weather": "clear"},
	{"id": "night", "time": "night", "weather": "clear"},
	{"id": "day_rain", "time": "day", "weather": "rain"},
	{"id": "day_overcast", "time": "day", "weather": "overcast"},
]
const VIEWS: Array[Dictionary] = [
	{"id": "avenue", "at": Vector3(-170, 1.62, -12), "look": Vector3(-60, 2, -6)},
	{"id": "plaza", "at": Vector3(70, 1.62, 50), "look": Vector3(90, 2, 15)},
	{"id": "hall", "at": Vector3(-108, 1.62, 50), "look": Vector3(-102, 1.5, 82)},
]
## SDFGI набирает отражённый свет не сразу
const SETTLE_FRAMES: int = 240


func _ready() -> void:
	RaidEvents.enabled = false
	Settings.lens_fx = false
	var out_dir: String = OS.get_environment("PROSPEKT_OUTPUT")
	if out_dir.is_empty():
		out_dir = ProjectSettings.globalize_path("user://prospekt_raid_shots")
	DirAccess.make_dir_recursive_absolute(out_dir)
	var only: PackedStringArray = OS.get_environment("PROSPEKT_CASES").split(",", false)
	for c: Dictionary in CASES:
		if not only.is_empty() and not String(c.id) in only:
			continue
		RaidConditions.from_host = {"time": c.time, "weather": c.weather, "power": "on"}
		var level: Node = (load(SCENE) as PackedScene).instantiate()
		# корень ещё расставляет детей (первый кадр) — добавить отложенно
		get_tree().root.add_child.call_deferred(level)
		await _frames(2)
		get_tree().current_scene = level
		await _frames(30)
		var marauders: Node = level.get_node_or_null("Marauders")
		if marauders:
			for m: Node in marauders.get_children():
				m.queue_free()
		# прячем интерфейс (HUD уровня и игрока); слои погоды (капли на линзе) и резкость карты остаются
		for layer: Node in get_tree().root.find_children("*", "CanvasLayer", true, false):
			if layer.name == "Sharpen" or layer is RainLens:
				layer.set("visible", OS.get_environment("PROSPEKT_NO_SHARPEN") == "" or layer.name != "Sharpen")
				continue
			(layer as CanvasLayer).visible = false
		var camera: Camera3D = Camera3D.new()
		# слои — как у камеры игрока: служебные (карта дождя «что над головой») ей не видны
		var player_cam: Camera3D = get_viewport().get_camera_3d()
		if player_cam:
			camera.cull_mask = player_cam.cull_mask
		camera.fov = Settings.fps_fov_v()
		camera.far = 2000.0
		level.add_child(camera)
		camera.make_current()
		var sun: DirectionalLight3D = level.get_node_or_null("Sun") as DirectionalLight3D
		var we: WorldEnvironment = level.find_child("WorldEnvironment", false, false) as WorldEnvironment
		# для поиска причин: PROSPEKT_ENV_OFF=sdfgi,ssao,fog,adjust — выключить части окружения
		for part: String in OS.get_environment("PROSPEKT_ENV_OFF").split(",", false):
			we.environment.set(part + "_enabled", false)
		print("prospekt_raid_shots: %s — солнце %.2f (%s), рассеянный %.2f, выдержка %.2f, дымка %s %.2f" % [c.id,
			sun.light_energy if sun else 0.0, "видно" if sun and sun.visible else "нет",
			we.environment.ambient_light_energy, we.environment.tonemap_exposure,
			"вкл" if we.environment.fog_enabled else "выкл", we.environment.fog_density])
		for view: Dictionary in VIEWS:
			camera.global_position = view.at
			camera.look_at(view.look, Vector3.UP)
			await _frames(SETTLE_FRAMES)
			await RenderingServer.frame_post_draw
			var path: String = out_dir.path_join("%s__%s.png" % [c.id, view.id])
			print("prospekt_raid_shots: снимок ", path, " ошибка=", get_viewport().get_texture().get_image().save_png(path))
		level.queue_free()
		await _frames(10)
	get_tree().quit()


func _frames(count: int) -> void:
	for i: int in range(count):
		await get_tree().process_frame
