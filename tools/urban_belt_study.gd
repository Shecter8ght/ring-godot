extends Node3D
## Изолированный запуск масштаба: не входит в рейд и не меняет список игровых карт.

const Walker = preload("res://src/blockout/study_walker.gd")
const Landscape = preload("res://src/blockout/study_landscape.gd")
const PlanMap = preload("res://src/blockout/study_map.gd")
const LEVEL: String = "res://scenes/levels/urban_belt_study.tscn"

var world: Node3D
var landscape: Landscape
var walker: Walker
var plan: Dictionary
var hud: CanvasLayer
var title: Label
var status: Label
var controls: Label
var map: PlanMap
var output_dir: String
var results: Array[Dictionary] = []
var mode: String = "walk"

func _enter_tree() -> void:
	# Отложенный sync контрактов тоже должен видеть отдельный тестовый профиль.
	if world == null:
		Profile.use_file("user://profile_urban_belt_study_test.json", true)

func _ready() -> void:
	DisplayServer.window_set_title("RING · Городской пояс · БЛОКАУТ 1:1")
	# Esc здесь освобождает мышь; общее меню не запускает переход в убежище.
	get_node("/root/Pause").set_process_input(false)
	get_node("/root/Quests").process_mode = Node.PROCESS_MODE_DISABLED
	get_node("/root/Contracts").process_mode = Node.PROCESS_MODE_DISABLED
	for arg: String in OS.get_cmdline_user_args():
		if arg in ["verify", "shots"]:
			mode = arg
	output_dir = OS.get_environment("URBAN_STUDY_OUTPUT")
	if output_dir.is_empty():
		output_dir = ProjectSettings.globalize_path("res://docs/screens/urban_belt_study")
	if world == null:
		world = (load(LEVEL) as PackedScene).instantiate() as Node3D
		add_child(world)
	landscape = world.get_node("Landscape") as Landscape
	plan = landscape.plan
	walker = Walker.new()
	walker.name = "StudyWalker"
	add_child(walker)
	_ui()
	_jump_to(2)
	if mode == "walk":
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		print("urban_belt_study: прогулка; WASD, Shift, M — карта, F — полёт, 1–6 — места, Esc — мышь")
	else:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		walker.is_probe = true
		await _frames(6)
		if mode == "verify":
			await _verify()
		else:
			await _shots()

func _ui() -> void:
	hud = CanvasLayer.new()
	hud.name = "StudyUI"
	add_child(hud)
	var root: Control = Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(root)
	var shade: ColorRect = ColorRect.new()
	shade.color = Color(0.035, 0.055, 0.05, 0.85)
	shade.position = Vector2(18,18)
	shade.size = Vector2(600, 82)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(shade)
	title = Label.new()
	title.position = Vector2(32,24)
	title.add_theme_font_size_override("font_size", 22)
	title.add_theme_color_override("font_color", Color("e0e3d2"))
	root.add_child(title)
	status = Label.new()
	status.position = Vector2(32,58)
	status.add_theme_font_size_override("font_size", 16)
	root.add_child(status)
	controls = Label.new()
	controls.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	controls.position = Vector2(24,-84)
	controls.add_theme_font_size_override("font_size", 16)
	controls.add_theme_color_override("font_shadow_color", Color.BLACK)
	controls.add_theme_constant_override("shadow_outline_size", 8)
	controls.text = "WASD — идти   Shift — бежать   Space — прыжок   C — присесть\nM — план   1–6 — перейти к месту   F — полёт   R — начать прогулку заново\nEsc — освободить мышь · щелчок — продолжить · это исследование, не рейд"
	root.add_child(controls)
	map = PlanMap.new()
	map.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	map.plan = plan
	map.walker = walker
	map.visible = false
	root.add_child(map)

func _process(_delta: float) -> void:
	if not is_instance_valid(walker):
		return
	var nearest: Dictionary = plan.locations[0]
	var distance: float = INF
	for loc: Dictionary in plan.locations:
		var p: Array = loc.at
		var current: float = Vector2(walker.global_position.x - float(p[0]), walker.global_position.z - float(p[1])).length()
		if current < distance:
			distance = current
			nearest = loc
	title.text = "%d · %s  |  БЛОКАУТ 1:1" % [int(nearest.id), String(nearest.label)]
	var speed_m: float = Vector2(walker.velocity.x, walker.velocity.z).length()
	status.text = "%s · %.2f м/с · путь %.0f м · %d:%02d · высота %.1f м" % ["ПОЛЁТ" if walker.flight else "ПЕШКОМ", speed_m, walker.travelled_m, int(walker.walking_sec) / 60, int(walker.walking_sec) % 60, walker.global_position.y]
	if map.visible:
		map.queue_redraw()

func _unhandled_input(event: InputEvent) -> void:
	if mode != "walk":
		return
	if event is InputEventMouseButton and (event as InputEventMouseButton).pressed and not map.visible:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	if not event is InputEventKey or not (event as InputEventKey).pressed or event.is_echo():
		return
	var key: int = (event as InputEventKey).physical_keycode
	if key == KEY_ESCAPE:
		if map.visible:
			map.hide()
			walker.blocked_input = false
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	if key == KEY_M:
		map.visible = not map.visible
		walker.blocked_input = map.visible
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE if map.visible else Input.MOUSE_MODE_CAPTURED
	if key >= KEY_1 and key <= KEY_6:
		_jump_to(key - KEY_0)
		map.hide()
		walker.blocked_input = false
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	if key == KEY_R:
		_jump_to(2)
		walker.travelled_m = 0.0
		walker.walking_sec = 0.0

func _jump_to(index: int) -> void:
	var loc: Dictionary = plan.locations[index - 1]
	var p: Array = loc.spawn
	var target: Array = loc.look
	var at: Vector3 = Vector3(float(p[0]), landscape.ground(float(p[0]), float(p[1])) + 0.08, float(p[1]))
	walker.teleport(at, Vector3(float(target[0]), at.y, float(target[1])))

func _frames(count: int) -> void:
	for i: int in range(count):
		await get_tree().physics_frame

func _check(label: String, passed: bool, details: Dictionary = {}) -> void:
	results.append({"check":label,"pass":passed,"details":details})
	print("urban_belt_study: %s · %s %s" % ["PASS" if passed else "FAIL", label, JSON.stringify(details)])

func _verify() -> void:
	_check("Число мест и физический масштаб", plan.locations.size() == 6 and is_equal_approx(float(plan.scale_m_per_pixel),0.8), {"area_m2":plan.boundary_area_m2,"swamp_m2":plan.swamp_polygon_area_m2})
	_check("Габариты и скорость из Balance", is_equal_approx((walker.capsule.shape as CapsuleShape3D).height,1.8) and is_equal_approx(Balance.PLAYER_WALK_SPEED,1.82), {"walk_m_s":Balance.PLAYER_WALK_SPEED,"sprint_m_s":Balance.PLAYER_SPRINT_SPEED,"eye_m":walker.camera.position.y})
	var panel_height: float = float(world.get_node("Residential/Panel_01").get_meta("height_m"))
	_check("Пятиэтажные дома имеют высоту 15 м", is_equal_approx(panel_height,15.0), {"height_m":panel_height})
	var wet_at: Vector3 = Vector3(-156,10,-209.6)
	var wet_query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(wet_at,wet_at-Vector3.UP*20,1)
	var wet_hit: Dictionary = walker.get_world_3d().direct_space_state.intersect_ray(wet_query)
	var wet_y: float = (wet_hit.position as Vector3).y if not wet_hit.is_empty() else INF
	_check("Вода находится над настоящим понижением рельефа", wet_y < -0.8, {"bed_y":wet_y,"water_y":-0.5})
	for loc: Dictionary in plan.locations:
		_jump_to(int(loc.id))
		await _frames(8)
		var query: PhysicsShapeQueryParameters3D = PhysicsShapeQueryParameters3D.new()
		query.shape = walker.capsule.shape
		query.transform = Transform3D(Basis.IDENTITY, walker.global_position + Vector3.UP * (Balance.STANCE_HEIGHT.stand * 0.5 + 0.04))
		query.collision_mask = 1
		var clear: bool = walker.get_world_3d().direct_space_state.intersect_shape(query,1).is_empty()
		_check("Безопасная стартовая точка " + String(loc.label), clear and walker.is_on_floor(), {"position":str(walker.global_position)})
	for route: Dictionary in plan.probe_routes:
		var path: Array[Vector3] = []
		for p: Array in route.points:
			path.append(Vector3(float(p[0]), landscape.ground(float(p[0]),float(p[1])) + 0.04,float(p[1])))
		var distance_before: float = walker.travelled_m
		var passed: bool = await _walk_path(path,true)
		_check("Проход капсулой: " + String(route.id), passed, {"walked_m":snappedf(walker.travelled_m-distance_before,0.1),"position":str(walker.global_position)})
	# Проверяется реальная коллизия обеих лестниц, все повороты и выход на крышу.
	for node_path: String in ["Construction/Construction_09F","Construction/Construction_05F","Residential/Panel_06_Enterable"]:
		var building: Node3D = world.get_node(node_path) as Node3D
		var count: int = int(building.get("floors"))
		var story: float = float(building.get("story_height"))
		var origin: Vector2 = building.get("stair_origin") as Vector2
		var path: Array[Vector3] = [building.to_global(Vector3(origin.x - 1.05,0.14,3.45))]
		for level: int in range(count):
			var y: float = 0.1 + float(level) * story
			path.append(building.to_global(Vector3(origin.x - 1.05,y+story*0.5,-3.45)))
			path.append(building.to_global(Vector3(origin.x + 1.05,y+story*0.5,-3.45)))
			path.append(building.to_global(Vector3(origin.x + 1.05,y+story,3.45)))
			path.append(building.to_global(Vector3(origin.x - 1.05,y+story,3.45)))
		var passed: bool = await _walk_path(path,false)
		await _frames(10)
		var target_y: float = building.global_position.y + float(count) * story + 0.1
		_check("Лестница и крыша: " + node_path, passed and absf(walker.global_position.y-target_y)<0.25, {"expected_y":target_y,"actual_y":walker.global_position.y})
	var mass: Node3D = world.get_node("Residential/Panel_01") as Node3D
	var outside: Vector3 = mass.to_global(Vector3(0,0.04,-9.0))
	walker.teleport(outside,outside+Vector3.FORWARD)
	await _frames(5)
	_check("Закрытый фасад останавливает капсулу", walker.test_move(walker.global_transform, mass.global_basis * Vector3(0,0,7.0)))
	var visual_count: int = 0
	var triangle_count: int = 0
	for mesh: Node in world.find_children("*","MeshInstance3D",true,false):
		var visual: MeshInstance3D = mesh as MeshInstance3D
		visual_count += 1
		if visual.mesh:
			for surface: int in range(visual.mesh.get_surface_count()):
				triangle_count += visual.mesh.surface_get_array_len(surface) / 3
	var fails: int = 0
	for result: Dictionary in results:
		if not bool(result["pass"]):
			fails += 1
	DirAccess.make_dir_recursive_absolute(output_dir)
	var report: Dictionary = {"scene":LEVEL,"checks":results,"fails":fails,"renderer":RenderingServer.get_current_rendering_method(),"mesh_batches":visual_count,"mesh_triangles_excluding_multimesh":triangle_count,"buildings":plan.buildings.size(),"balance_unchanged":true,"limitations":["Бой, добыча, эвакуация и сетевой режим не проверяются этим исследованием","Условные материалы и растительность; нет итоговых PBR ассетов","Измеряются скорости без выносливости, снаряжения и перегруза"]}
	var file: FileAccess = FileAccess.open(output_dir.path_join("validation.json"),FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"\t"))
	file.close()
	print("urban_belt_study: DONE checks=%d fails=%d" % [results.size(),fails])
	get_tree().quit(fails)

func _walk_path(path: Array[Vector3], sprint: bool) -> bool:
	walker.probe_direction = Vector3.ZERO
	walker.probe_sprint = sprint
	walker.teleport(path[0],path[0]+Vector3.FORWARD)
	await _frames(10)
	for target: Vector3 in path.slice(1):
		var previous: float = INF
		var stalled: int = 0
		var reached: bool = false
		for frame: int in range(18000):
			var delta: Vector3 = target-walker.global_position
			delta.y = 0.0
			if delta.length() < 0.16:
				reached = true
				break
			if delta.length() > previous-0.001:
				stalled += 1
			else:
				stalled = 0
			previous = delta.length()
			if stalled > 160 or walker.global_position.y < -5.0:
				break
			walker.probe_direction = delta.normalized()
			await get_tree().physics_frame
		walker.probe_direction = Vector3.ZERO
		walker.velocity.x = 0.0
		walker.velocity.z = 0.0
		if not reached:
			print("urban_belt_study: stuck at %s towards %s" % [str(walker.global_position),str(target)])
			return false
	return true

func _shots() -> void:
	walker.set_physics_process(false)
	hud.hide()
	DirAccess.make_dir_recursive_absolute(output_dir)
	var views: Array[Dictionary] = [
		{"id":"01_overview","at":Vector3(0,650,390),"look":Vector3(0,0,-15)},
		{"id":"02_panel_street","at":Vector3(-177.6,1.62,94.4),"look":Vector3(-177.6,5.0,-18.0)},
		{"id":"03_swamp","at":Vector3(-201.6,1.62,-119.8),"look":Vector3(-146,-0.5,-189)},
		{"id":"04_construction","at":Vector3(45.6,1.62,-112),"look":Vector3(103.2,15,-137.6)},
		{"id":"05_roof_view","at":Vector3(71.8,30.52,-124.1),"look":Vector3(-130,3,70)},
		{"id":"06_bus_station","at":Vector3(-64,1.62,133.6),"look":Vector3(20,1.62,191)}]
	for view: Dictionary in views:
		var environment: Environment = (world.get_node("WorldEnvironment") as WorldEnvironment).environment
		environment.fog_enabled = view.id != "01_overview"
		walker.camera.global_position = view.at
		walker.camera.look_at(view.look,Vector3.UP)
		walker.camera.fov = 62.0 if view.id == "01_overview" else Settings.fps_fov_v()
		await _frames(35)
		await RenderingServer.frame_post_draw
		var image: Image = get_viewport().get_texture().get_image()
		var path: String = output_dir.path_join(String(view.id)+".png")
		var error: Error = image.save_png(path)
		print("urban_belt_study: shot ",path," error=",error)
	# Отдельно проверяем читаемость реального интерфейса и плана на весь экран.
	walker.camera.position = Vector3(0,Balance.ADS_EYE.stand,0)
	walker.camera.rotation = Vector3.ZERO
	_jump_to(2)
	hud.show()
	await _frames(10)
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(output_dir.path_join("07_walk_hud.png"))
	map.show()
	map.queue_redraw()
	await _frames(10)
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(output_dir.path_join("08_map.png"))
	get_tree().quit()
