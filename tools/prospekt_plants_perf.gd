extends Node3D
## Замер кадров в секунду на «Проспекте» там, где стоят свои растения (tools/prospekt_plants): сквер, берёзы вдоль
## восточного края, тополя у двора, вид сверху. Камера в точке, кадры прогреваются, затем среднее время кадра и 1 % худших.
## С аргументом «off» пачки растений (MultiMesh «model_P_*») скрыты — сравнение «без растений / с растениями» в одной сборке.
##   tools/godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/prospekt_plants_perf.tscn [-- off]

const LEVEL: String = "res://scenes/levels/prospekt_study.tscn"
const WARM: int = 120
const MEASURE: int = 300
## Точка: имя, камера, куда смотрит.
const VIEWS: Array = [
	["сквер_вход", Vector3(-35, 1.62, 25), Vector3(-5, 2, 75)],
	["сквер_центр", Vector3(-10, 1.62, 110), Vector3(10, 3, 150)],
	["сквер_площадка", Vector3(-2, 1.62, 143), Vector3(-36, 1.5, 168)],
	["сквер_север", Vector3(10, 1.62, 190), Vector3(-20, 4, 215)],
	["берёзы_восток", Vector3(30, 1.62, 60), Vector3(55, 5, 120)],
	["двор_тополя", Vector3(-140, 1.62, -70), Vector3(-120, 8, -88)],
	["сверху_сквер", Vector3(0, 120, 40), Vector3(0, 0, 140)],
]

var camera: Camera3D


func _ready() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	var hide_plants: bool = OS.get_cmdline_user_args().has("off")
	var world: Node3D = (load(LEVEL) as PackedScene).instantiate() as Node3D
	add_child(world)
	camera = Camera3D.new()
	camera.fov = Settings.fps_fov_v()
	camera.far = 2000.0
	add_child(camera)
	camera.make_current()
	for i: int in range(30):
		await get_tree().process_frame
	var plants: int = 0
	for node: Node in world.find_children("model_P_*", "MultiMeshInstance3D", true, false):
		plants += 1
		(node as Node3D).visible = not hide_plants
	var label: String = "без_растений" if hide_plants else "с_растениями"
	print("prospekt_plants_perf: %s, пачек растений %d" % [label, plants])
	print("  %-18s %8s %8s %8s %10s %8s" % ["точка", "FPS", "мс", "1% мс", "треуг.", "вызовов"])
	var lines: PackedStringArray = []
	var total: float = 0.0
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
		var draws: int = int(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME))
		var line: String = "  %-18s %8.1f %8.2f %8.2f %10d %8d" % [String(v[0]), 1000.0 / mean, mean, worst, tris, draws]
		print(line)
		lines.append(line)
		total += mean
	var avg: String = "  среднее: %.1f к/с (%.2f мс)" % [1000.0 / (total / VIEWS.size()), total / VIEWS.size()]
	print(avg)
	lines.append(avg)
	var f: FileAccess = FileAccess.open("user://prospekt_plants_perf_%s.txt" % label, FileAccess.WRITE)
	f.store_string("\n".join(lines) + "\n")
	f.close()
	get_tree().quit()
