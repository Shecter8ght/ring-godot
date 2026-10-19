extends Node
## Кадры в секунду на территории ТЦ (scenes/levels/mall_study.tscn — она же земля рейдовой карты mall_map):
## покрытия PBR (MallGround, шейдер paved_ground) и бетон стенок, ступеней, бордюров (шейдер cast_concrete)
## против прежних серых с шумом по трём осям — на одних и тех же кадрах в одном прогоне: новые, прежние
## (на те же меши), снова новые — порядок не влияет, нагрузка машины от других программ — тоже. Печатает
## FPS и время кадра на видеокарте по каждому кадру и в среднем (новые — лучший из двух проходов).
##   tools/godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/mall_ground_perf.tscn

const MallGround = preload("res://src/blockout/mall_ground.gd")
## Кадр: имя, откуда, куда смотреть (двор у улики, двор, дорога, площадь, парковки сверху).
const VIEWS: Array = [
	["yard_eye", Vector3(70.5, -2.3, -157.0), Vector3(76.0, -4.0, -150.0)],
	["yard_wide", Vector3(132.0, -2.3, -136.7), Vector3(100.7, -3.5, -104.3)],
	["road_eye", Vector3(258.0, 1.7, -8.0), Vector3(250.0, 0.0, 25.0)],
	["plaza_eye", Vector3(22.0, 1.62, 150.0), Vector3(0.0, 4.0, 100.0)],
	["terraces", Vector3(-150.0, 18.0, 290.0), Vector3(-60.0, -2.0, 190.0)],
	["parking_high", Vector3(180.0, 14.0, 170.0), Vector3(120.0, -2.0, 110.0)]]
const WARM_FRAMES: int = 60
const FRAMES: int = 240

var _cam: Camera3D


func _ready() -> void:
	# сцена черновика не корень — своя прогулка (mall_study_level.gd) не запускается
	var world: Node3D = (load("res://scenes/levels/mall_study.tscn") as PackedScene).instantiate() as Node3D
	add_child(world)
	_cam = Camera3D.new()
	_cam.fov = Settings.fps_fov_v()
	_cam.far = 4000.0
	add_child(_cam)
	_cam.make_current()
	RenderingServer.viewport_set_measure_render_time(get_viewport().get_viewport_rid(), true)
	for i: int in range(30):
		await get_tree().process_frame
	var ground: Array[MeshInstance3D] = []
	for node: Node in world.find_children("Mesh_*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = node as MeshInstance3D
		var material: ShaderMaterial = mi.mesh.surface_get_material(0) as ShaderMaterial if mi.mesh else null
		if material != null and material.shader in [MallGround.SHADER, MallGround.CONCRETE_SHADER]:
			ground.append(mi)
	print("mall_ground_perf: мешей покрытий и бетона %d" % ground.size())
	var results: Dictionary = {}
	var old: StandardMaterial3D = _old_material()
	for mode: String in ["pbr", "old", "pbr2"]:
		for mi: MeshInstance3D in ground:
			mi.material_override = old if mode == "old" else null
		for view: Array in VIEWS:
			results["%s/%s" % [mode, view[0]]] = await _measure(view[1], view[2])
	var sum: Dictionary = {"pbr": Vector2.ZERO, "old": Vector2.ZERO}
	for view: Array in VIEWS:
		var a1: Vector2 = results["pbr/%s" % view[0]]
		var a2: Vector2 = results["pbr2/%s" % view[0]]
		var a: Vector2 = a1 if a1.x > a2.x else a2
		var b: Vector2 = results["old/%s" % view[0]]
		sum.pbr += a
		sum.old += b
		print("mall_ground_perf: %-13s PBR %6.1f к/с (GPU %5.2f мс)   прежние %6.1f к/с (GPU %5.2f мс)" % [view[0], a.x, a.y, b.x, b.y])
	var n: float = float(VIEWS.size())
	print("mall_ground_perf: в среднем     PBR %6.1f к/с (GPU %5.2f мс)   прежние %6.1f к/с (GPU %5.2f мс)" % [
		sum.pbr.x / n, sum.pbr.y / n, sum.old.x / n, sum.old.y / n])
	get_tree().quit()


## FPS и время видеокарты, мс, на кадре.
func _measure(at: Vector3, look: Vector3) -> Vector2:
	_cam.global_position = at
	_cam.look_at(look, Vector3.UP)
	for i: int in range(WARM_FRAMES):
		await get_tree().process_frame
	var gpu: float = 0.0
	var start: int = Time.get_ticks_usec()
	for i: int in range(FRAMES):
		await get_tree().process_frame
		gpu += RenderingServer.viewport_get_measured_render_time_gpu(get_viewport().get_viewport_rid())
	var sec: float = float(Time.get_ticks_usec() - start) / 1000000.0
	return Vector2(float(FRAMES) / sec, gpu / float(FRAMES))


## Прежнее покрытие: серый цвет и мелкий шум по трём осям мира (как MallLandscape._with_detail).
func _old_material() -> StandardMaterial3D:
	var noise: FastNoiseLite = FastNoiseLite.new()
	noise.seed = 7
	noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	noise.frequency = 0.045
	noise.fractal_octaves = 4
	var texture: NoiseTexture2D = NoiseTexture2D.new()
	texture.width = 256
	texture.height = 256
	texture.seamless = true
	texture.noise = noise
	var m: StandardMaterial3D = StandardMaterial3D.new()
	m.albedo_color = Color("5f625d") * 1.14
	m.albedo_texture = texture
	m.uv1_triplanar = true
	m.uv1_world_triplanar = true
	m.uv1_scale = Vector3.ONE * 0.22
	m.roughness = 0.9
	return m
