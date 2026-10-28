extends Node3D
## Этап 1 общежития: прогулка, физическая проверка пеших маршрутов и одни и те же виды для всех этапов.
## tools/dorm_study.cmd; -- verify; -- shots. JSON — tools/build_dorm.py.

const Walker = preload("res://src/blockout/study_walker.gd")
const PlanMap = preload("res://src/blockout/dorm_map.gd")
const LEVEL: String = "res://scenes/levels/dorm_study.tscn"

var plan: Dictionary = {}
var world: Node3D
var walker: CharacterBody3D
var camera: Camera3D
var hud: CanvasLayer
var title: Label
var status: Label
var map: Control
var current: int = 8
var mode: String = "walk"
var output_dir: String
var results: Array[Dictionary] = []
var route_distance: float = 0.0
var route_detail: Dictionary = {}
var started_ms: int = 0


func _enter_tree() -> void:
	Profile.use_file("user://profile_dorm_study_test.json", true)


func _ready() -> void:
	started_ms = Time.get_ticks_msec()
	DisplayServer.window_set_title("RING · Общежитие · этап 1: планировка 2")
	get_node("/root/Pause").set_process_input(false)
	get_node("/root/Quests").process_mode = Node.PROCESS_MODE_DISABLED
	get_node("/root/Contracts").process_mode = Node.PROCESS_MODE_DISABLED
	for arg: String in OS.get_cmdline_user_args():
		if arg in ["verify", "shots"]:
			mode = arg
	output_dir = OS.get_environment("DORM_OUTPUT")
	if output_dir.is_empty():
		output_dir = ProjectSettings.globalize_path("res://docs/screens/dorm")
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://data/blockouts/dorm.json"))
	if not parsed is Dictionary:
		push_error("dorm: нет плана, запустите python -X utf8 tools/build_dorm.py")
		get_tree().quit(1)
		return
	plan = parsed as Dictionary
	world = (load(LEVEL) as PackedScene).instantiate() as Node3D
	add_child(world)
	walker = Walker.new() as CharacterBody3D
	walker.name = "StudyWalker"
	add_child(walker)
	camera = walker.get("camera") as Camera3D
	camera.fov = Settings.fov_v_from_h(float(plan.scale.fov_h))
	_ui()
	await _frames(4)
	_jump_to(current)
	if mode == "walk":
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		print("dorm: прогулка · WASD, Shift, C, Space · M план · 1–9/0 и N/B места · F полёт · H подписи · Esc мышь")
	else:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		walker.set("is_probe", true)
		await _frames(4)
		if mode == "verify":
			await _verify()
		else:
			await _shots()


func _ui() -> void:
	hud = CanvasLayer.new()
	hud.name = "DormStudyUI"
	add_child(hud)
	var root: Control = Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(root)
	var shade: ColorRect = ColorRect.new()
	shade.color = Color(0.03, 0.04, 0.05, 0.8)
	shade.position = Vector2(18, 18)
	shade.size = Vector2(980, 80)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(shade)
	title = Label.new()
	title.position = Vector2(30, 24)
	title.add_theme_font_size_override("font_size", 24)
	root.add_child(title)
	status = Label.new()
	status.position = Vector2(30, 60)
	status.add_theme_font_size_override("font_size", 17)
	root.add_child(status)
	var help: Label = Label.new()
	help.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	help.position = Vector2(28, -85)
	help.text = "WASD · Shift бег · C присесть · Space прыжок · F полёт (Space вверх / Ctrl вниз)\nM план этажа · 1–9 / 0 места · N / B следующее / предыдущее · R вход · H подписи · Esc мышь"
	help.add_theme_font_size_override("font_size", 18)
	help.add_theme_color_override("font_shadow_color", Color.BLACK)
	help.add_theme_constant_override("shadow_offset_x", 1)
	help.add_theme_constant_override("shadow_offset_y", 1)
	root.add_child(help)
	map = PlanMap.new() as Control
	map.set("plan", plan)
	map.set("walker", walker)
	map.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	map.hide()
	root.add_child(map)


func _process(_delta: float) -> void:
	if not is_instance_valid(walker) or not is_instance_valid(status):
		return
	title.text = "Общежитие · этап 1 · %d: %s" % [current, String(plan.locations[current-1].label)]
	status.text = "x %.2f · y %.2f · z %.2f · глаз 1,62 м · поле зрения 80° · %d к/с%s" % [
		walker.position.x,walker.position.y,walker.position.z,Engine.get_frames_per_second(),
		" · полёт" if bool(walker.get("flight")) else ""]
	if map.visible:
		map.queue_redraw()


func _unhandled_input(event: InputEvent) -> void:
	if mode != "walk":
		return
	if event is InputEventMouseButton and (event as InputEventMouseButton).pressed and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	if not (event is InputEventKey and (event as InputEventKey).pressed and not event.is_echo()):
		return
	var key: InputEventKey = event as InputEventKey
	match key.physical_keycode:
		KEY_ESCAPE:
			Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		KEY_M:
			map.visible = not map.visible
			walker.set("blocked_input", map.visible)
		KEY_H:
			for node: Node in get_tree().get_nodes_in_group("dorm_study_labels"):
				(node as Node3D).visible = not (node as Node3D).visible
		KEY_R:
			_jump_to(8)
		KEY_N:
			_jump_to(current % plan.locations.size() + 1)
		KEY_B:
			_jump_to((current - 2 + plan.locations.size()) % plan.locations.size() + 1)
		KEY_1, KEY_2, KEY_3, KEY_4, KEY_5, KEY_6, KEY_7, KEY_8, KEY_9:
			_jump_to(key.physical_keycode - KEY_1 + 1)
		KEY_0:
			_jump_to(10)


func _jump_to(index: int) -> void:
	current = index
	var location: Dictionary = plan.locations[index-1]
	var foot: Vector3 = _vec(location.foot)
	walker.call("teleport", foot + Vector3.UP * 0.04, _vec(location.look))
	walker.call("_set_crouch", false)
	camera.position = Vector3(0,1.62,0)
	camera.look_at(_vec(location.look), Vector3.UP)


func _frames(count: int) -> void:
	for i: int in range(count):
		await get_tree().physics_frame


static func _vec(values: Array) -> Vector3:
	return Vector3(float(values[0]),float(values[1]),float(values[2]))


func _check(label: String, passed: bool, details: Dictionary = {}) -> void:
	results.append({"check":label,"pass":passed,"details":details})
	print("dorm: %s · %s %s" % ["PASS" if passed else "FAIL",label,JSON.stringify(details)])


func _ray(a: Vector3, b: Vector3) -> Dictionary:
	return walker.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(a,b,1))


func _standing_clear(foot: Vector3) -> bool:
	var shape: CapsuleShape3D = (walker.get("capsule") as CollisionShape3D).shape as CapsuleShape3D
	var query: PhysicsShapeQueryParameters3D = PhysicsShapeQueryParameters3D.new()
	query.shape = shape
	query.transform = Transform3D(Basis.IDENTITY,foot+Vector3.UP*(shape.height*0.5+0.025))
	query.collision_mask = 1
	return walker.get_world_3d().direct_space_state.intersect_shape(query,1).is_empty()


func _verify() -> void:
	# При --fixed-fps 60 движок считает обычные шаги физики без ожидания реального времени.
	# Размер капсулы, ходьба, снап и подъём на ступень — из настоящего StudyWalker / Balance.
	var rooms: Array[int] = [0,0,0]
	var spaces: int = 0
	for space: Dictionary in plan.spaces:
		if bool(space.open):
			spaces += 1
			if String(space.kind)=="room":
				rooms[int(space.floor)-1] += 1
	_check("Пять этажей, открыты три; по 8–10 жилых комнат",plan.scale.floor_y.size()==5 and rooms.min()>=8 and rooms.max()<=10,{"rooms":rooms,"open_spaces":spaces})
	_check("Капсула, глаз и скорость соответствуют игроку",is_equal_approx(camera.position.y,Balance.ADS_EYE.stand),
		{"capsule_height":Balance.STANCE_HEIGHT.stand,"capsule_radius":Balance.CAPSULE_RADIUS,"eye":camera.position.y,"walk_m_s":Balance.PLAYER_WALK_SPEED,"jump":false,"flight":false})
	for f: int in range(3):
		var y: float = float(plan.scale.floor_y[f])
		var probe_x: float = float(plan.checks.ceiling_probe_x)
		var ceiling_hit: Dictionary = _ray(Vector3(probe_x,y+0.1,0),Vector3(probe_x,y+8,0))
		var clearance: float = (ceiling_hit.position as Vector3).y-y if not ceiling_hit.is_empty() else INF
		_check("Высота потолка %d-го этажа" % (f+1),absf(clearance-float(plan.scale.ceiling_clear[f]))<0.03,{"clear_m":clearance})
		var left: Dictionary = _ray(Vector3(probe_x,y+1.3,0),Vector3(probe_x,y+1.3,-4))
		var right: Dictionary = _ray(Vector3(probe_x,y+1.3,0),Vector3(probe_x,y+1.3,4))
		var width_m: float = (right.position as Vector3).z-(left.position as Vector3).z if not left.is_empty() and not right.is_empty() else INF
		_check("Коридор %d-го этажа расширен до 3,6 м" % (f+1),absf(width_m-3.6)<0.02,{"clear_m":width_m})
	var core: Dictionary = plan.stair_core
	var core_rect: Array = core.rect
	var core_width: float = float(core_rect[2])-float(core_rect[0])
	_check("Лестница в середине корпуса, марши от стены до стены",absf(core_width-3.3)<0.01 and float(core.center_x)>float(plan.checks.ceiling_probe_x)*2.0,
		{"clear_width_m":core_width,"marches_m":[1.5,1.5],"middle_gap_m":0.3,"side_gaps_m":0.0,"center_x":core.center_x})
	for location: Dictionary in plan.locations:
		_jump_to(int(location.id))
		await _frames(12)
		_check("Точка осмотра: "+String(location.label),_standing_clear(walker.position) and walker.is_on_floor(),{"foot":str(walker.position)})
	for route: Dictionary in plan.routes:
		var points: Array[Vector3] = []
		for at: Array in route.points:
			points.append(_vec(at))
		var passed: bool = await _walk_path(points)
		_check(String(route.label)+" — пешком",passed,route_detail.duplicate())
	# Каждый путь начинается на площадке лестницы. Точки внутри помещений достигаются без телепортации.
	for space: Dictionary in plan.spaces:
		if not bool(space.open):
			continue
		var y: float = float(space.y)
		var points: Array[Vector3] = [_vec(plan.floor_routes[int(space.floor)-1].start)]
		for at: Array in space.path:
			points.append(_vec(at))
		if space.has("probe_points"):
			for at: Array in space.probe_points:
				points.append(_vec(at))
		elif String(space.kind)!="stairs":
			var rect: Array = space.rect
			points.append(Vector3(float(rect[0])+0.8,y,float(rect[1])+0.8))
			points.append(Vector3(float(rect[2])-0.8,y,float(rect[3])-0.8))
		var passed: bool = await _walk_path(points)
		_check("Доступно: %d этаж, %s" % [int(space.floor),String(space.label)],passed,route_detail.duplicate())
	for floor_route: Dictionary in plan.floor_routes:
		var passed: bool = await _walk_path([_vec(floor_route.start),_vec(floor_route.end)])
		_check("Весь открытый коридор, %d этаж" % int(floor_route.floor),passed,route_detail.duplicate())
	for barrier: Dictionary in plan.barriers:
		var reached: bool = await _walk_path([_vec(barrier.from),_vec(barrier.to)])
		var normal: Vector3 = _vec(barrier.normal)
		var before: bool = (walker.position-_vec(barrier.point)).dot(normal)>0.15
		_check("Нельзя пройти: "+String(barrier.label),not reached and before,route_detail.duplicate())
	var bad_doors: Array[String] = []
	var sealed: int = 0
	for door: Dictionary in plan.doors:
		if bool(door.open):
			continue
		sealed += 1
		var at: Vector3 = _vec(door.at)+Vector3.UP*1.2
		var normal: Vector3 = Vector3.RIGHT if String(door.get("axis","z"))=="x" else Vector3.BACK
		var hit: Dictionary = _ray(at+normal*0.6,at-normal*0.6)
		if hit.is_empty():
			bad_doors.append(String(door.id)+str(door.at))
	_check("Заваренные двери имеют настоящую коллизию",bad_doors.is_empty(),{"count":sealed,"missing":bad_doors})
	var stair_ok: bool = true
	for stair: Dictionary in plan.stairs:
		stair_ok = stair_ok and float(stair.riser)>=0.15 and float(stair.riser)<=0.17 and is_equal_approx(float(stair.tread),0.3)
	_check("Ступени 1:1, марш 1,5 м",stair_ok,{"tread":0.3,"riser_ground":plan.stairs[0].riser,"riser_upper":plan.stairs[2].riser})
	var room_widths: Dictionary = {}
	for space: Dictionary in plan.spaces:
		if String(space.kind)=="room" and bool(space.open):
			room_widths[str(space.get("width_scale",1.0))] = true
	_check("Жилые комнаты разной ширины: ×1 / ×1,3 / ×1,4 / ×1,5",room_widths.size()==4,{"multipliers":room_widths.keys(),"widths_m":plan.scale.room_widths,"window_leaf_scale":plan.scale.window_leaf_scale})
	var fails: int = 0
	for result: Dictionary in results:
		if not bool(result.pass):
			fails += 1
	DirAccess.make_dir_recursive_absolute(output_dir)
	var report: FileAccess = FileAccess.open(output_dir.path_join("validation.json"),FileAccess.WRITE)
	report.store_string(JSON.stringify({"stage":1,"checks":results,"fails":fails,"walked_m":route_distance,
		"scale":plan.scale,"engine":Engine.get_version_info().string,"duration_sec":(Time.get_ticks_msec()-started_ms)/1000.0},"\t"))
	report.close()
	print("dorm: проверок %d, провалов %d, пройдено %.1f м" % [results.size(),fails,route_distance])
	get_tree().quit(mini(fails,255))


func _walk_path(points: Array[Vector3]) -> bool:
	walker.set("probe_direction",Vector3.ZERO)
	walker.set("probe_sprint",false)
	walker.call("teleport",points[0]+Vector3.UP*0.04,points[0]+Vector3.FORWARD)
	await _frames(10)
	var distance_m: float = 0.0
	var passed: bool = true
	var missed: Vector3 = Vector3.ZERO
	for target: Vector3 in points.slice(1):
		var reached: bool = false
		var stalled: int = 0
		var previous: Vector3 = walker.position
		var budget: int = maxi(240,int(previous.distance_to(target)/Balance.PLAYER_WALK_SPEED*Engine.physics_ticks_per_second)+180)
		for frame: int in range(budget):
			var delta: Vector3 = target-walker.position
			var height_error: float = absf(delta.y)
			delta.y = 0
			if delta.length()<0.16 and height_error<0.18 and walker.is_on_floor():
				reached = true
				break
			walker.set("probe_direction",delta.normalized())
			await get_tree().physics_frame
			var moved: float = previous.distance_to(walker.position)
			distance_m += moved
			stalled = stalled+1 if moved<0.0005 else 0
			previous = walker.position
			if stalled>90 or walker.position.y< -1:
				break
		walker.set("probe_direction",Vector3.ZERO)
		walker.velocity = Vector3.ZERO
		if not reached:
			passed = false
			missed = target
			break
	route_distance += distance_m
	route_detail = {"end":str(walker.position),"distance_m":snappedf(distance_m,0.01),"on_floor":walker.is_on_floor()}
	if not passed:
		route_detail["missed"] = str(missed)
	return passed


func _shots() -> void:
	if DisplayServer.get_name()=="headless":
		push_error("dorm: снимки требуют оконного запуска")
		get_tree().quit(1)
		return
	walker.set_physics_process(false)
	hud.hide()
	for node: Node in get_tree().get_nodes_in_group("dorm_study_labels"):
		(node as Node3D).hide()
	DirAccess.make_dir_recursive_absolute(output_dir)
	var manifest: Array[Dictionary] = []
	var fails: int = 0
	for view: Dictionary in plan.shots:
		var foot: Vector3 = _vec(view.foot)
		camera.global_position = foot+Vector3.UP*float(view.eye_height)
		camera.look_at(_vec(view.look),Vector3.UP)
		await _frames(24)
		await RenderingServer.frame_post_draw
		var filename: String = "stage1_%s.png" % String(view.id)
		var error: Error = get_viewport().get_texture().get_image().save_png(output_dir.path_join(filename))
		if error!=OK:
			fails += 1
		manifest.append({"id":view.id,"revision":plan.version,"label":view.label,"file":filename,"foot":view.foot,"camera":[camera.global_position.x,camera.global_position.y,camera.global_position.z],
			"look":view.look,"eye_height":view.eye_height,"fov_h":plan.scale.fov_h,"fov_v":camera.fov,"viewport":get_viewport().get_visible_rect().size,"stage":1})
		print("dorm: снимок ",filename," ошибка=",error)
	var report: FileAccess = FileAccess.open(output_dir.path_join("stage1_views.json"),FileAccess.WRITE)
	report.store_string(JSON.stringify(manifest,"\t"))
	report.close()
	world.queue_free()
	await _frames(3)
	get_tree().quit(fails)
