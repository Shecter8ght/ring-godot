extends Node3D
## Замер кадров в секунду на «Проспекте» в точках, где этап 5а поставил свет интерьеров (зал «Яруса», склад, зал вокзала, холл
## полиции, блокпост под эстакадой, башня схода). Аргумент — метка прогона («до», «после»): файл user://prospekt_light_perf_<метка>.txt.
##   tools/godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/prospekt_light_perf.tscn [-- метка]

const LEVEL: String = "res://scenes/levels/prospekt_study.tscn"
const WARM: int = 120
const MEASURE: int = 300
## Точка: имя, камера, куда смотрит.
const VIEWS: Array = [
	["зал_Яруса", Vector3(-108, 1.62, 50), Vector3(-102, 1.5, 82)],
	["склад_Яруса", Vector3(-100, 1.62, 92), Vector3(-100, 2, 114)],
	["зал_вокзала", Vector3(146, 1.62, 222), Vector3(146, 3, 244)],
	["полиция_холл", Vector3(-192, 1.62, 17), Vector3(-192, 1.5, 22)],
	["под_эстакадой_блокпост", Vector3(-234, 1.62, -30), Vector3(-234, 3, 5)],
	["башня_схода", Vector3(-219.2, 1.62, 199.0), Vector3(-219.2, 3, 192.5)],
]

var camera: Camera3D


func _ready() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	var tag: String = String(OS.get_cmdline_user_args()[0]) if OS.get_cmdline_user_args().size() > 0 else "now"
	var world: Node3D = (load(LEVEL) as PackedScene).instantiate() as Node3D
	add_child(world)
	camera = Camera3D.new()
	camera.fov = Settings.fps_fov_v()
	camera.far = 2000.0
	add_child(camera)
	camera.make_current()
	for i: int in range(30):
		await get_tree().process_frame
	var label: String = tag
	var omni: int = 0
	for node: Node in world.find_children("*", "OmniLight3D", true, false):
		omni += 1
	print("prospekt_light_perf: %s, источников света OmniLight3D в сцене %d" % [label, omni])
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
	var f: FileAccess = FileAccess.open("user://prospekt_light_perf_%s.txt" % label, FileAccess.WRITE)
	f.store_string("\n".join(lines) + "\n")
	f.close()
	get_tree().quit()
