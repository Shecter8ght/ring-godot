extends Node3D
## Замер кадров в секунду на «Проспекте» там, где стоят ограждения и город (tools/prospekt_city): забор района,
## гаражи, контейнеры, опоры, контактная сеть, остановка, КТП — и общий вид сверху. Камера стоит в точке, кадры
## прогреваются, потом считается среднее время кадра и 1 % худших; таблица в консоль и в user:// (сравнение до/после).
##   tools/godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/prospekt_city_perf.tscn [-- метка] [без_sdfgi] [без_ssao]
## «без_…» выключает эффект окружения карты на время замера — цена SDFGI / SSAO на одной сборке (свет принят 2026-10-29).

const LEVEL: String = "res://scenes/levels/prospekt_study.tscn"
const WARM: int = 120
const MEASURE: int = 300
## Точка: имя, камера, куда смотрит.
const VIEWS: Array = [
	["забор_север", Vector3(-100, 1.62, -131.3), Vector3(-60, 3, -142.3)],
	["забор_восток", Vector3(181.3, 1.62, 8.7), Vector3(191.3, 2, 90)],
	["двор_линии", Vector3(-130, 1.62, -129.3), Vector3(-160, 7, -152.3)],
	["гаражи_двор7", Vector3(-196, 1.62, 82), Vector3(-205, 1.5, 74)],
	["проспект_троллейбус", Vector3(-185, 1.62, -42.58), Vector3(-120, 6, -19.83)],
	["пути_контактная_сеть", Vector3(10, 8.3, 266), Vector3(141.3, 10, 276)],
	["остановка_площадь", Vector3(-180, 1.62, 9.63), Vector3(-195, 2, 40)],
	["сверху_общий", Vector3(-30, 430, 330), Vector3(-30, 0, 60)],
	# помещения: здесь работает SDFGI (тёмные залы)
	["зал_супермаркета", Vector3(-108, 1.62, 50), Vector3(-102, 1.5, 82)],
	["паркинг_минус1", Vector3(-110, -1.6, -73.3), Vector3(-170, -2.2, -73.3)],
]

var camera: Camera3D


func _ready() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	var label: String = "без_метки"
	var off: PackedStringArray = []
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("без_"):
			off.append(arg.trim_prefix("без_"))
		else:
			label = arg
	if not off.is_empty():
		label += "_без_" + "_".join(off)
	var world: Node3D = (load(LEVEL) as PackedScene).instantiate() as Node3D
	add_child(world)
	for found: Node in world.find_children("*", "WorldEnvironment", true, false):
		var env: Environment = (found as WorldEnvironment).environment
		if env != null:
			env.sdfgi_enabled = env.sdfgi_enabled and not off.has("sdfgi")
			env.ssao_enabled = env.ssao_enabled and not off.has("ssao")
	camera = Camera3D.new()
	camera.fov = 70.0
	camera.far = 2000.0
	add_child(camera)
	camera.make_current()
	for i: int in range(30):
		await get_tree().process_frame
	var lines: PackedStringArray = []
	var total: float = 0.0
	print("prospekt_city_perf: %s" % label)
	print("  %-22s %8s %8s %8s %10s" % ["точка", "FPS", "мс", "1% мс", "треуг."])
	for v: Array in VIEWS:
		camera.global_position = v[1]
		camera.look_at(v[2], Vector3.UP)
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
		var line: String = "  %-22s %8.1f %8.2f %8.2f %10d" % [String(v[0]), 1000.0 / mean, mean, worst, tris]
		print(line)
		lines.append(line)
		total += mean
	var avg: String = "  среднее: %.1f к/с (%.2f мс)" % [1000.0 / (total / VIEWS.size()), total / VIEWS.size()]
	print(avg)
	lines.append(avg)
	var f: FileAccess = FileAccess.open("user://prospekt_city_perf_%s.txt" % label, FileAccess.WRITE)
	f.store_string("\n".join(lines) + "\n")
	f.close()
	get_tree().quit()
