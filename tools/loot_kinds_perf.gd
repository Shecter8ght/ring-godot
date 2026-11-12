extends Node
## «Проспект»: кадры в секунду с моделями контейнеров лута и без них (LootContainerVisual убраны) в местах, где их много:
## склад «Яруса», зал вокзала, ряд гаражей, паркинг −1. Мародёры убраны, интерфейс не рисуется.
##   tools/godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/loot_kinds_perf.tscn
## Печатает по точке: модели видны в кадре, FPS и время кадра (среднее и 1 % худших) с моделями и без.

const SCENE := "res://scenes/levels/prospekt.tscn"
const WARM := 90
const MEASURE := 240
const VIEWS: Array = [
	["склад_Яруса", Vector3(-100, 1.62, 92), Vector3(-108, 1.0, 108)],
	["зал_вокзала", Vector3(172, 1.62, 228), Vector3(176, 1.0, 244)],
	["гаражи", Vector3(-185, 1.62, 125), Vector3(-199, 1.0, 120)],
	["паркинг_минус_1", Vector3(-140, -5.0, -92), Vector3(-150, -6.0, -105)],
	["разгрузка", Vector3(-112, 1.62, 99), Vector3(-116, 1.0, 104)],
]


func _ready() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	Profile.use_file("user://profile_loot_kinds_perf.json", true)
	Profile.ensure()
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	get_tree().node_added.connect(func(n: Node) -> void:
		if n is Marauder:
			n.process_mode = Node.PROCESS_MODE_DISABLED
			(n as Node3D).visible = false)
	var level: Node = (load(SCENE) as PackedScene).instantiate()
	get_tree().root.add_child.call_deferred(level)
	await _frames(3)
	get_tree().current_scene = level
	await _frames(40)
	for m: Node in (level.get_node_or_null("Marauders") as Node).get_children():
		m.queue_free()
	for layer: Node in get_tree().root.find_children("*", "CanvasLayer", true, false):
		(layer as CanvasLayer).visible = false
	var camera := Camera3D.new()
	camera.fov = Settings.fps_fov_v()
	camera.far = 2000.0
	level.add_child(camera)
	camera.make_current()
	var models: Array[Node] = []
	for c: Node in get_tree().get_nodes_in_group("loot_containers"):
		var cc: LootContainer = c as LootContainer
		if cc != null and cc._model != null:
			models.append(cc._model)
	print("loot_kinds_perf: контейнеров с моделью %d" % models.size())
	print("  %-18s %6s | %8s %8s %8s | %8s %8s %8s" % ["точка", "видно", "FPS с", "мс", "1% мс", "FPS без", "мс", "1% мс"])
	for v: Array in VIEWS:
		camera.global_position = v[1]
		camera.look_at(v[2], Vector3.UP)
		var with_m: Dictionary = await _measure(models, true)
		var near: int = 0
		for m: Node in models:
			if is_instance_valid(m) and (m as Node3D).global_position.distance_to(camera.global_position) < float(LootContainerVisual.catalog().get("far", 45.0)):
				near += 1
		var without: Dictionary = await _measure(models, false)
		print("  %-18s %6d | %8.0f %8.2f %8.2f | %8.0f %8.2f %8.2f" % [v[0], near, with_m.fps, with_m.ms, with_m.worst, without.fps, without.ms, without.worst])
	get_tree().quit()


func _measure(models: Array[Node], show: bool) -> Dictionary:
	for m: Node in models:
		if is_instance_valid(m):
			(m as Node3D).visible = show
	await _frames(WARM)
	var times: Array[float] = []
	var last: int = Time.get_ticks_usec()
	for i: int in range(MEASURE):
		await get_tree().process_frame
		var now: int = Time.get_ticks_usec()
		times.append(float(now - last) / 1000.0)
		last = now
	var sum: float = 0.0
	for t: float in times:
		sum += t
	times.sort()
	var worst: float = 0.0
	var k: int = maxi(1, MEASURE / 100)
	for i: int in range(k):
		worst += times[MEASURE - 1 - i]
	var avg: float = sum / float(MEASURE)
	return {"fps": 1000.0 / avg, "ms": avg, "worst": worst / float(k)}


func _frames(count: int) -> void:
	for i: int in range(count):
		await get_tree().process_frame
