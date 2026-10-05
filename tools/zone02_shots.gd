extends Node
## Снимки настоящего рейда: вся планировка, районы, мост, масштаб игрока и штатная карта M.

var _level: Node3D
var _camera: Camera3D
var _player: Player
var _layers: Dictionary = {}
var _ranges: Dictionary = {}
var _fade_modes: Dictionary = {}


func _ready() -> void:
	Profile.use_file("user://profile_zone02_shots_test.json", true)
	Profile.pending_raid = false
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	_level = (load("res://scenes/levels/zone02_urban_belt.tscn") as PackedScene).instantiate() as Node3D
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	while not bool(_level.get("_nav_baked")):
		await get_tree().process_frame
	_player = Raid.current.local_player()
	_player.health.invulnerable = true
	CameraRig.first_person_mode = false
	Input.action_release("aim")
	for enemy in _level.get_node("Marauders").get_children():
		enemy.set_physics_process(false)
	_camera = Camera3D.new()
	_camera.name = "SurveyCamera"
	_camera.far = 3000.0
	_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	_level.add_child(_camera)
	_camera.current = true
	for node in _level.find_children("*", "CanvasLayer", true, false):
		var layer: CanvasLayer = node as CanvasLayer
		_layers[layer] = layer.visible
		layer.visible = false
	# Игровое отсечение рассчитано на низкую камеру, а не на съёмку с высоты 1.7 км.
	for node in _level.find_children("*", "GeometryInstance3D", true, false):
		var geometry: GeometryInstance3D = node as GeometryInstance3D
		_ranges[geometry] = geometry.visibility_range_end
		geometry.visibility_range_end = 0.0
		var mesh: MeshInstance3D = geometry as MeshInstance3D
		if mesh and mesh.material_override is BaseMaterial3D:
			var material: BaseMaterial3D = mesh.material_override as BaseMaterial3D
			if not _fade_modes.has(material):
				_fade_modes[material] = material.distance_fade_mode
				material.distance_fade_mode = BaseMaterial3D.DISTANCE_FADE_DISABLED
	await _shot("overview", Vector3(0, 1700, 1130), Vector3(0, 0, -70), 1450)
	await _shot("residential", Vector3(-530, 170, -125), Vector3(-520, 2, -310), 310)
	await _shot("commercial", Vector3(20, 150, 55), Vector3(20, 0, -160), 270)
	await _shot("administration", Vector3(-30, 170, 440), Vector3(0, -1, 233), 305)
	await _shot("bus_station", Vector3(390, 165, 515), Vector3(380, -2, 292), 320)
	await _shot("garages", Vector3(480, 130, -110), Vector3(470, 0, -330), 270)
	await _shot("sports_field", Vector3(635, 100, 155), Vector3(560, -2, 20), 180)
	await _shot("south_bridge", Vector3(-65, 150, 775), Vector3(-20, -3, 555), 260)
	await _shot("facade", Vector3(-620, 17, -451), Vector3(-595, 10, -400), 95)
	RaidConditions.current = {"time": "night", "weather": "clear", "power": "on"}
	RaidAtmosphere.current.apply()
	_camera.projection = Camera3D.PROJECTION_PERSPECTIVE
	_camera.fov = 70.0
	await _shot("night", Vector3(20, 12, -45), Vector3(20, 5, -153), 155)
	RaidConditions.current = {"time": "day", "weather": "clear", "power": "on"}
	RaidAtmosphere.current.apply()
	_camera.queue_free()
	for layer: CanvasLayer in _layers:
		layer.visible = bool(_layers[layer])
	for geometry: GeometryInstance3D in _ranges:
		geometry.visibility_range_end = float(_ranges[geometry])
	for material: BaseMaterial3D in _fade_modes:
		material.distance_fade_mode = int(_fade_modes[material]) as BaseMaterial3D.DistanceFadeMode
	_player.global_position = Vector3(-500, 2.5, -146)
	_player.velocity = Vector3.ZERO
	(_level.get_node("CameraRig/Pivot/Camera3D") as Camera3D).current = true
	await _capture("player_scale")
	RaidConditions.current = {"time": "dusk", "weather": "rain", "power": "on"}
	RaidAtmosphere.current.apply()
	RaidWeather.current._apply_static()
	for index in range(120):
		await get_tree().process_frame
	await _capture("rain")
	RaidConditions.current = {"time": "day", "weather": "clear", "power": "on"}
	RaidAtmosphere.current.apply()
	RaidWeather.current._apply_static()
	var map: MapView = _level.get_node("Map") as MapView
	var action := InputEventAction.new()
	action.action = "map"
	action.pressed = true
	map._unhandled_input(action)
	await _capture("map")
	Floors.select("zone02")
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	for index in range(60):
		await get_tree().process_frame
	var hideout: Node = get_tree().current_scene
	for node: Node in get_tree().get_nodes_in_group("interactables"):
		if node is HideoutStation and (node as HideoutStation).kind == HideoutStation.Kind.EXIT:
			hideout.call("open_station", node)
			break
	await _capture("route")
	print("zone02_shots: снимки сохранены")
	get_tree().quit()


func _shot(id: String, eye: Vector3, target: Vector3, width: float) -> void:
	_camera.position = eye
	_camera.look_at(target)
	_camera.size = width
	await _capture(id)


func _capture(id: String) -> void:
	for index in range(12):
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var image: Image = get_viewport().get_texture().get_image()
	var path: String = "res://docs/screens/zone02_" + id + ".png"
	var error: Error = image.save_png(ProjectSettings.globalize_path(path))
	print("zone02 shot: %s %s" % [id, error_string(error)])
