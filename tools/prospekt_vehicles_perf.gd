extends Node3D
## Замер кадров в секунду на «Проспекте» там, где много своего транспорта (tools/prospekt_vehicles): паркинг −1,
## стоянки, поворот проспекта, вид сверху. Камера в точке, кадры прогреваются, затем среднее время кадра и 1 % худших.
## «off» — пачки машин (MultiMesh «model_PV_*») скрыты: сравнение «без машин / с машинами» в одной сборке.
## «lod» — снимки одной машины с 4, 10, 20, 40 и 80 м (поле зрения игрока) в docs/screens/prospekt_vehicles/lod_*.png:
## видно ли переключение уровней детализации, которые Godot строит при импорте.
##   tools/godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/prospekt_vehicles_perf.tscn [-- off | lod]

const LEVEL: String = "res://scenes/levels/prospekt_study.tscn"
const WARM: int = 120
const MEASURE: int = 300
## Точка: имя, камера, куда смотрит.
const VIEWS: Array = [
	["паркинг_ряды", Vector3(-190, -1.6, -60.4), Vector3(-150, -2.0, -60.4)],
	["паркинг_битые", Vector3(-150, -1.6, -60.4), Vector3(-120, -2.4, -60.4)],
	["стоянка_яруса", Vector3(-146, 1.62, 17), Vector3(-102, 2, 48)],
	["стоянка_двор", Vector3(-150, 1.62, -38), Vector3(-120, 0.8, -45)],
	["поворот", Vector3(-40, 1.62, -12), Vector3(40, 3, 30)],
	["проспект_восток", Vector3(-170, 1.62, -12), Vector3(-60, 2, -6)],
	["сверху", Vector3(-30, 120, 60), Vector3(-60, 0, 0)],
]
## Машина для снимков уровней детализации (двор у дома на повороте) и направление, откуда смотреть.
const LOD_TARGET: Vector3 = Vector3(-36.0, 0.7, 53.0)
const LOD_DIR: Vector3 = Vector3(0.55, 0.22, -0.8)
const LOD_DIST: Array = [4.0, 10.0, 20.0, 40.0, 80.0]

var camera: Camera3D


func _ready() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var world: Node3D = (load(LEVEL) as PackedScene).instantiate() as Node3D
	add_child(world)
	camera = Camera3D.new()
	camera.fov = Settings.fps_fov_v()
	camera.far = 2000.0
	add_child(camera)
	camera.make_current()
	for i: int in range(30):
		await get_tree().process_frame
	var hud: Node = world.find_child("Hud", true, false)
	if hud is CanvasItem:
		(hud as CanvasItem).hide()
	if args.has("lod"):
		await _lod_shots()
		get_tree().quit()
		return
	var cars_off: bool = args.has("off")
	var batches: int = 0
	for node: Node in world.find_children("model_PV_*", "MultiMeshInstance3D", true, false):
		batches += 1
		(node as Node3D).visible = not cars_off
	var label: String = "без_машин" if cars_off else "с_машинами"
	print("prospekt_vehicles_perf: %s, пачек машин %d" % [label, batches])
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
	var f: FileAccess = FileAccess.open("user://prospekt_vehicles_perf_%s.txt" % label, FileAccess.WRITE)
	f.store_string("\n".join(lines) + "\n")
	f.close()
	get_tree().quit()


## Одна машина с нескольких расстояний при поле зрения игрока: снимки для сравнения переходов детализации.
func _lod_shots() -> void:
	var out: String = ProjectSettings.globalize_path("res://docs/screens/prospekt_vehicles")
	DirAccess.make_dir_recursive_absolute(out)
	for d: float in LOD_DIST:
		camera.global_position = LOD_TARGET + LOD_DIR.normalized() * d
		camera.look_at(LOD_TARGET, Vector3.UP)
		for i: int in range(40):
			await get_tree().process_frame
		await RenderingServer.frame_post_draw
		var image: Image = get_viewport().get_texture().get_image()
		var path: String = out.path_join("lod_%02d.png" % int(d))
		print("prospekt_vehicles_perf: снимок ", path, " ошибка=", image.save_png(path))
