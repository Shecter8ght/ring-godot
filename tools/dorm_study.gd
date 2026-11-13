extends Node3D
## Этап 1 общежития: прогулка, физическая проверка пеших маршрутов и одни и те же виды для всех этапов.
## tools/dorm_study.cmd; -- verify; -- shots; -- v3shots (материалы v03 при свете «вечер Б» → docs/screens/dorm/v3,
## DORM_V3_VIEWS=01_corridor,04_wash — выборочно; архивы пробы света не трогает). JSON — tools/build_dorm.py.

const Walker = preload("res://src/blockout/study_walker.gd")
const PlanMap = preload("res://src/blockout/dorm_map.gd")
const LEVEL: String = "res://scenes/levels/dorm_study.tscn"
const LightCapture = preload("res://tools/dorm_light_capture.gd")
const LightPlacer = preload("res://tools/dorm_light_placer.gd")

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
var fov_h: float = 80.0
var fov_slider: HSlider
var fov_label: Label
var lighting: Node3D
## F10 или U — весь интерфейс стенда скрыт (подсказки, панель света, план, подписи в мире): смотреть на свет без помех.
var hud_hidden: bool = false
## L — расстановка оставленного людьми света по месту (только прогулка).
var placer: Node


func _enter_tree() -> void:
	Profile.use_file("user://profile_dorm_study_test.json", true)


func _ready() -> void:
	started_ms = Time.get_ticks_msec()
	get_node("/root/Pause").set_process_input(false)
	get_node("/root/Quests").process_mode = Node.PROCESS_MODE_DISABLED
	get_node("/root/Contracts").process_mode = Node.PROCESS_MODE_DISABLED
	for arg: String in OS.get_cmdline_user_args():
		if arg in ["verify", "shots", "bake", "v3shots"]:
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
	DisplayServer.window_set_title("RING · Общежитие · пробный свет · редакция %s" % str(plan.environment.get("lighting_revision",plan.version)))
	world = (load(LEVEL) as PackedScene).instantiate() as Node3D
	add_child(world)
	walker = Walker.new() as CharacterBody3D
	walker.name = "StudyWalker"
	add_child(walker)
	camera = walker.get("camera") as Camera3D
	lighting = world.get_node_or_null("Lighting") as Node3D
	if lighting!=null and mode!="verify":
		lighting.call("attach_camera",camera)
	fov_h = float(plan.scale.fov_h)
	_ui()
	Settings.map_labels_changed.connect(_sync_map_labels)
	_set_fov(fov_h)
	get_viewport().size_changed.connect(_refresh_fov)
	await _frames(4)
	_jump_to(current)
	if mode == "walk":
		placer = LightPlacer.new()
		placer.name = "LightPlacer"
		add_child(placer)
		placer.call("setup",camera,world,hud.get_child(0) as Control)
		if lighting!=null:
			for index: int in range(plan.environment.cases.size()):
				if String(plan.environment.cases[index].id)==String(plan.environment.default):
					await lighting.call("set_case",index)
					break
			print("dorm: стартовый свет · ",plan.environment.cases[int(lighting.get("case_index"))].label)
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		print("dorm: прогулка · WASD, Shift, C, Space · E дверь, ящик · M план · 1–9/0 и N/B места · F полёт · H подписи · F9 как в Таркове · F10 / U скрыть интерфейс · L расставить свет · Esc мышь / FOV 60–110°")
	else:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		walker.set("is_probe", true)
		await _frames(4)
		if mode == "verify":
			await _verify()
		elif mode == "bake":
			var success: bool = await lighting.call("ensure_baked",true)
			get_tree().quit(0 if success else 1)
		elif mode == "v3shots":
			await _v3_shots()
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
	shade.size = Vector2(980, 126)
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
	fov_label = Label.new()
	fov_label.position = Vector2(30, 105)
	fov_label.add_theme_font_size_override("font_size", 17)
	root.add_child(fov_label)
	fov_slider = HSlider.new()
	fov_slider.position = Vector2(245, 104)
	fov_slider.size = Vector2(360, 26)
	fov_slider.min_value = 60.0
	fov_slider.max_value = 110.0
	fov_slider.step = 1.0
	fov_slider.focus_mode = Control.FOCUS_NONE
	fov_slider.value = fov_h
	fov_slider.tooltip_text = "Поле зрения по горизонтали. Esc — освободить мышь для настройки."
	fov_slider.value_changed.connect(_set_fov)
	root.add_child(fov_slider)
	for preset: int in [80,95,110]:
		var button: Button = Button.new()
		button.text = "%d°" % preset
		button.focus_mode = Control.FOCUS_NONE
		button.position = Vector2(625+[80,95,110].find(preset)*75, 100)
		button.size = Vector2(65, 32)
		button.pressed.connect(_set_fov.bind(float(preset)))
		root.add_child(button)
	# подсказка внизу переносится по ширине окна: одной строкой она уходила за край, и «скрыть интерфейс» не было видно
	var help: Label = Label.new()
	help.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	help.offset_left = 28
	help.offset_right = -28
	help.offset_bottom = -14
	help.grow_vertical = Control.GROW_DIRECTION_BEGIN
	help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	help.text = "F10 или U — скрыть весь интерфейс (для записи) · WASD · Shift бег · C присесть · Space прыжок · E дверь, ящик · F полёт (Space вверх / Ctrl вниз)"
	help.text += "\nM план · 1–9 / 0 места · N / B следующее / предыдущее · R вход · H подписи · Esc мышь / угол зрения · L расставить свет"
	help.text += "\nF1–F4 свет · F5 холодные коридоры · F6 ночь Б · F7 Б без оконных источников · F8 ночная луна · F9 как в Таркове"
	help.add_theme_font_size_override("font_size", 16)
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
	if lighting!=null and mode!="verify":
		lighting.call("create_controls",root)


func _process(_delta: float) -> void:
	if not is_instance_valid(walker) or not is_instance_valid(status):
		return
	title.text = "Общежитие · этап 1 · %d: %s · F10 / U — скрыть интерфейс" % [current, String(plan.locations[current-1].label)]
	status.text = "x %.2f · y %.2f · z %.2f · глаз 1,62 м · поле зрения %.0f° · %d к/с%s" % [
		walker.position.x,walker.position.y,walker.position.z,fov_h,Engine.get_frames_per_second(),
		" · полёт" if bool(walker.get("flight")) else ""]
	if map.visible:
		map.queue_redraw()


func _set_fov(value: float) -> void:
	fov_h = clampf(value,60.0,110.0)
	if is_instance_valid(fov_slider):
		fov_slider.set_value_no_signal(fov_h)
	if is_instance_valid(fov_label):
		fov_label.text = "Угол по горизонтали: %.0f°" % fov_h
	_refresh_fov()


func _refresh_fov() -> void:
	if is_instance_valid(camera):
		var viewport_size: Vector2 = get_viewport().get_visible_rect().size
		camera.fov = Settings.fov_v_from_h(fov_h,viewport_size.x/maxf(viewport_size.y,1.0))


func _unhandled_input(event: InputEvent) -> void:
	if mode != "walk":
		return
	if placer!=null and bool(placer.call("handle",event)):
		get_viewport().set_input_as_handled()
		return
	if event is InputEventMouseButton and (event as InputEventMouseButton).pressed and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	if not (event is InputEventKey and (event as InputEventKey).pressed and not event.is_echo()):
		return
	var key: InputEventKey = event as InputEventKey
	match key.physical_keycode:
		KEY_F1, KEY_F2, KEY_F3, KEY_F4:
			lighting.call("set_case",key.physical_keycode-KEY_F1)
		KEY_F5:
			lighting.call("set_cool_corridors",not bool(lighting.get("cool_corridors")))
		KEY_F6, KEY_F7:
			lighting.call("set_case",4+key.physical_keycode-KEY_F6)
		KEY_F8:
			lighting.call("set_night_exterior",not bool(lighting.get("night_exterior")))
		KEY_F9:
			lighting.call("set_tarkov",not bool(lighting.get("tarkov")))
		KEY_F10, KEY_U:
			_toggle_hud()
		KEY_L:
			placer.call("toggle")
		KEY_BRACKETLEFT, KEY_BRACKETRIGHT:
			if bool(placer.get("active")):
				placer.call("change_charge",-0.05 if key.physical_keycode==KEY_BRACKETLEFT else 0.05)
		KEY_E:
			var hit: Dictionary = _ray(camera.global_position,camera.global_position-camera.global_basis.z*3.0)
			if not hit.is_empty():
				var leaf: Node = (hit.collider as Node).get_parent()
				# ящик партии 3 (коробка столкновений — в сетке модели): открыть, как при обыске
				var box: Node = leaf
				while box!=null and not box.is_in_group("dorm_loot_boxes"):
					box = box.get_parent()
				if box!=null:
					box.call("open")
				elif leaf.is_in_group("dorm_study_doors"):
					# Обе створки одной двери переключаются вместе.
					var uid: String = String((leaf.get("data") as Dictionary).door_uid)
					var open_door: bool = not bool(leaf.get("is_open"))
					for other: Node in get_tree().get_nodes_in_group("dorm_study_doors"):
						if String((other.get("data") as Dictionary).door_uid)==uid:
							other.call("set_open",open_door)
		KEY_ESCAPE:
			Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		KEY_M:
			map.visible = not map.visible
			walker.set("blocked_input", map.visible)
		KEY_H:
			Settings.set_map_labels(not Settings.map_labels)
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


func _toggle_hud() -> void:
	hud_hidden = not hud_hidden
	hud.visible = not hud_hidden
	_sync_map_labels()


func _sync_map_labels() -> void:
	for node: Node in get_tree().get_nodes_in_group("dorm_study_labels"):
		(node as Node3D).visible = Settings.map_labels and not hud_hidden


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
	_check("Собственный свет редакции 6.1 загружен, шесть вариантов",lighting!=null and lighting.get("environment") is Environment and plan.environment.cases.size()==6,
		{"default":plan.environment.default,"author":plan.environment.author})
	# Владелец 2026-11-02: открыты все пять этажей, жилые 1–4, пятый — технический (docs/design/dorm_routes.md).
	var rooms: Array[int] = [0,0,0,0,0]
	var tech: int = 0
	var spaces: int = 0
	for space: Dictionary in plan.spaces:
		if bool(space.open):
			spaces += 1
			if String(space.kind)=="room":
				rooms[int(space.floor)-1] += 1
			tech += 1 if String(space.kind)=="tech" else 0
	var living: Array[int] = rooms.slice(0,4)
	_check("Пять этажей открыты: 1–4 по 8–10 жилых комнат, 5-й — технический зал",plan.scale.floor_y.size()==5 and living.min()>=8 and living.max()<=10 and rooms[4]==0 and tech>=2,
		{"rooms":rooms,"tech":tech,"open_spaces":spaces})
	_check("Капсула, глаз и скорость соответствуют игроку",is_equal_approx(camera.position.y,Balance.ADS_EYE.stand),
		{"capsule_height":Balance.STANCE_HEIGHT.stand,"capsule_radius":Balance.CAPSULE_RADIUS,"eye":camera.position.y,"walk_m_s":Balance.PLAYER_WALK_SPEED,"jump":false,"flight":false})
	for f: int in range(5):
		var y: float = float(plan.scale.floor_y[f])
		var probe_x: float = float(plan.checks.ceiling_probe_x)
		var ceiling_hit: Dictionary = _ray(Vector3(probe_x,y+0.1,0),Vector3(probe_x,y+8,0))
		var clearance: float = (ceiling_hit.position as Vector3).y-y if not ceiling_hit.is_empty() else INF
		_check("Высота потолка %d-го этажа" % (f+1),absf(clearance-float(plan.scale.ceiling_clear[f]))<0.03,{"clear_m":clearance})
		if f==4:
			continue   # 5-й этаж — открытый технический зал, коридора нет
		var left: Dictionary = _ray(Vector3(probe_x,y+1.3,0),Vector3(probe_x,y+1.3,-4))
		var right: Dictionary = _ray(Vector3(probe_x,y+1.3,0),Vector3(probe_x,y+1.3,4))
		var width_m: float = (right.position as Vector3).z-(left.position as Vector3).z if not left.is_empty() and not right.is_empty() else INF
		var expected_width: float = float(plan.scale.corridor_clear)
		_check("Коридор %d-го этажа: %.1f м в свету" % [f+1,expected_width],absf(width_m-expected_width)<0.02,{"clear_m":width_m})
	var core: Dictionary = plan.stair_core
	var core_rect: Array = core.rect
	var core_width: float = float(core_rect[2])-float(core_rect[0])
	_check("Лестница в середине корпуса, марши от стены до стены",absf(core_width-3.3)<0.01 and float(core.center_x)>float(plan.checks.ceiling_probe_x)*2.0,
		{"clear_width_m":core_width,"marches_m":[1.5,1.5],"middle_gap_m":0.3,"side_gaps_m":0.0,"center_x":core.center_x})
	await _verify_details()
	for location: Dictionary in plan.locations:
		_jump_to(int(location.id))
		await _frames(12)
		_check("Точка осмотра: "+String(location.label),_standing_clear(walker.position) and walker.is_on_floor(),{"foot":str(walker.position)})
	for route: Dictionary in plan.routes:
		var points: Array[Vector3] = []
		for at: Array in route.points:
			points.append(_vec(at))
		if bool(route.get("climb",false)) or bool(route.get("ladder",false)):
			_check_climb_route(route,points)
			continue
		var passed: bool = await _walk_path(points)
		_check(String(route.label)+" — пешком",passed,route_detail.duplicate())
	# Каждый путь начинается на площадке лестницы. Точки внутри помещений достигаются без телепортации.
	# Мебель (furnish_rooms.py) может стоять на точке плана — стол у окна, баррикада: точку сдвигает к середине комнаты
	# до свободного места (комната должна оставаться проходимой, а не точка — пустой).
	var furniture: Array[AABB] = _furniture_boxes()
	for space: Dictionary in plan.spaces:
		if not bool(space.open):
			continue
		var y: float = float(space.y)
		var points: Array[Vector3] = [_vec(plan.floor_routes[int(space.floor)-1].start)]
		var middle: Vector3 = _vec(space.path[space.path.size()-1])
		for k: int in range(space.path.size()):
			points.append(_vec(space.path[k]) if k==0 else _free_point(_vec(space.path[k]),middle,furniture))
		if space.has("probe_points"):
			for at: Array in space.probe_points:
				points.append(_free_point(_vec(at),middle,furniture))
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
	var report_path: String = output_dir.path_join("validation.json")
	var temporary: String = report_path+".r6.tmp"
	var report: FileAccess = FileAccess.open(temporary,FileAccess.WRITE)
	if report==null:
		push_error("dorm: не записан отчёт "+output_dir+" · "+str(FileAccess.get_open_error()))
		get_tree().quit(1)
		return
	report.store_string(JSON.stringify({"stage":1,"revision":float(plan.environment.get("lighting_revision",plan.version)),"geometry_revision":plan.version,"checks":results,"fails":fails,"walked_m":route_distance,
		"scale":plan.scale,"engine":Engine.get_version_info().string,"duration_sec":(Time.get_ticks_msec()-started_ms)/1000.0},"\t"))
	report.close()
	var saved: bool = false
	for attempt: int in range(10):
		if DirAccess.rename_absolute(temporary,report_path)==OK:
			saved = true
			break
		await get_tree().create_timer(.1).timeout
	if not saved:
		push_error("dorm: итоговый отчёт заблокирован; сохранён полный "+temporary)
		get_tree().quit(1)
		return
	print("dorm: проверок %d, провалов %d, пройдено %.1f м" % [results.size(),fails,route_distance])
	get_tree().quit(mini(fails,255))


## Пути на руках (куча под проломом — подтянуться) и по вертикальной лестнице ходок прогулки пройти не может:
## проверяются высоты — каждая ступень кучи стоит на полу, до края сверху не выше Balance.CLIMB.max_h (и выше
## max_h_loaded: с перегрузом не залезть); у люка — лестница игры на месте и над ней открыто небо.
func _check_climb_route(route: Dictionary, points: Array[Vector3]) -> void:
	if bool(route.get("ladder",false)):
		var ladders: int = get_tree().get_nodes_in_group(Ladder.LINK_GROUP).size()
		var top: Vector3 = points[points.size()-1]
		var below: Vector3 = points[1]
		var sky: Dictionary = _ray(Vector3(below.x,below.y+1.0,top.z+.85),Vector3(below.x,top.y+6.0,top.z+.85))
		_check(String(route.label)+" — лестница на месте, над люком открыто",ladders>0 and sky.is_empty(),{"ladders":ladders,"hit":str(sky.get("position",""))})
		return
	var ok: bool = true
	var detail: Dictionary = {}
	for i: int in range(1,points.size()):
		var at: Vector3 = points[i]
		var hit: Dictionary = _ray(at+Vector3.UP*0.6,at+Vector3.DOWN*0.5)
		var ground: float = (hit.position as Vector3).y if not hit.is_empty() else -INF
		ok = ok and absf(ground-at.y)<0.08
		detail["p%d" % i] = snappedf(ground,0.01)
	var reach: float = points[points.size()-1].y-points[points.size()-2].y
	ok = ok and reach<=float(Balance.CLIMB.max_h) and reach>float(Balance.CLIMB.max_h_loaded)
	detail["climb_m"] = snappedf(reach,0.01)
	_check(String(route.label)+" — высоты кучи и края",ok,detail)


func _verify_details() -> void:
	var portal_errors: Array[String] = []
	var min_height: float = INF
	var min_width: float = INF
	var annex_portals: int = 0
	for portal: Dictionary in plan.portals:
		if String(portal.kind)!="transverse":
			continue
		var foot: Vector3 = _vec(portal.at)
		annex_portals += 1 if String(portal.get("travel_axis","x"))=="z" else 0
		var top: Dictionary = _ray(foot+Vector3.UP*0.12,foot+Vector3.UP*4.5)
		var across: Vector3 = Vector3.RIGHT if String(portal.get("travel_axis","x"))=="z" else Vector3.BACK
		var left: Dictionary = _ray(foot+Vector3.UP*0.04,foot+Vector3.UP*0.04-across*3)
		var right: Dictionary = _ray(foot+Vector3.UP*0.04,foot+Vector3.UP*0.04+across*3)
		var height: float = (top.position as Vector3).y-foot.y if not top.is_empty() else 0.0
		var width: float = ((right.position as Vector3)-(left.position as Vector3)).dot(across) if not left.is_empty() and not right.is_empty() else 0.0
		min_height = minf(min_height,height)
		min_width = minf(min_width,width)
		if height<2.599 or width<2.999:
			portal_errors.append(String(portal.id))
	_check("Порталы: от 2,6 м под балкой и 3,0 м между пилястрами с плинтусами",portal_errors.is_empty(),
		{"minimum_height_m":min_height,"minimum_width_m":min_width,"failed":portal_errors})
	_check("В хозкрыле по два портала на каждом жилом этаже",annex_portals==8,{"annex_portals":annex_portals})
	var bad_leaves: Array[String] = []
	var poses: Dictionary = {}
	var grilles: int = 0
	var leaves: Array[Node] = get_tree().get_nodes_in_group("dorm_study_doors")
	for leaf: Node in leaves:
		var data: Dictionary = leaf.get("data") as Dictionary
		poses[String(data.pose)] = int(poses.get(String(data.pose),0))+1
		grilles += 1 if bool(data.grille) else 0
		leaf.call("set_open",false,false)
		await _frames(2)
		var at: Vector3 = Vector3(float(data.width)/2,1.2,0)
		var a: Vector3 = (leaf as Node3D).to_global(at+Vector3(0,0,0.4))
		var b: Vector3 = (leaf as Node3D).to_global(at-Vector3(0,0,0.4))
		var hit: Dictionary = _ray(a,b)
		var closed_solid: bool = not hit.is_empty() and (hit.collider as Node).get_parent()==leaf
		leaf.call("set_open",true,false)
		await _frames(2)
		if not closed_solid or not _ray(a,b).is_empty():
			bad_leaves.append(String(data.id))
		leaf.call("reset_pose")
	_check("Полотна 40 мм блокируют проход закрытыми и освобождают его на петлях",bad_leaves.is_empty() and poses.size()==3 and grilles>0,
		{"leaves":leaves.size(),"poses":poses,"with_grille":grilles,"failed":bad_leaves})
	var bad_windows: Array[int] = []
	for i: int in range(plan.windows.size()):
		var window: Dictionary = plan.windows[i]
		var at: Vector3 = _vec(window.at)
		var inward: Vector3
		if String(window.axis)=="z":
			inward = Vector3(0,0,-1 if at.z>0 else 1)
		else:
			inward = Vector3(-1 if at.x>float(plan.main_rect[2]) else 1,0,0)
		var inside: Vector3 = at+inward*float(plan.scale.walls.facade)/2
		var sill: Dictionary = _ray(inside+inward*0.15+Vector3.UP*0.08,inside+inward*0.15-Vector3.UP*0.12)
		var rib_offset: Vector3 = Vector3(0.05,0,0) if String(window.axis)=="z" else Vector3(0,0,0.05)
		var radiator: Dictionary = _ray(inside+rib_offset+inward*0.7-Vector3.UP*0.35,inside+rib_offset+inward*0.02-Vector3.UP*0.35)
		if sill.is_empty() or radiator.is_empty() or String((sill.collider as Node).get_parent().name)!="window_sills" or String((radiator.collider as Node).get_parent().name)!="radiators":
			bad_windows.append(i)
	_check("Под каждым окном есть выступающий подоконник и батарея 1:1",bad_windows.is_empty(),{"windows":plan.windows.size(),"failed":bad_windows})
	var bad_niches: Array[String] = []
	for niche: Dictionary in plan.niches:
		var at: Vector3 = _vec(niche.at)
		var hit: Dictionary = _ray(at+Vector3(0,0,0.45),at-Vector3(0,0,0.3))
		var depth: float = at.z-(hit.position as Vector3).z if not hit.is_empty() else 0.0
		if depth<0.19 or depth>0.26:
			bad_niches.append(String(niche.id))
	_check("Ниши утоплены в стену; за карманом остаётся 0,13 м кладки",bad_niches.is_empty(),{"niches":plan.niches.size(),"failed":bad_niches})
	_set_fov(110.0)
	var viewport_size: Vector2 = get_viewport().get_visible_rect().size
	var measured_h: float = rad_to_deg(2.0*atan(tan(deg_to_rad(camera.fov)/2.0)*viewport_size.x/viewport_size.y))
	_check("Ползунок FOV до 110° по горизонтали",is_equal_approx(fov_slider.max_value,110.0) and absf(measured_h-110.0)<0.01,{"min":fov_slider.min_value,"max":fov_slider.max_value,"measured_h":measured_h})
	_set_fov(float(plan.scale.fov_h))


func _open_nearby_doors() -> void:
	# Проверка пользуется теми же петлями, что клавиша E; коллизии не отключаются.
	for leaf: Node in get_tree().get_nodes_in_group("dorm_study_doors"):
		var delta: Vector3 = (leaf as Node3D).global_position-walker.position
		if absf(delta.y)<0.3 and Vector2(delta.x,delta.z).length()<2.2 and not bool(leaf.get("is_open")):
			leaf.call("set_open",true,false)


## Коробки столкновений мебели в мире (по их узлам; наклонённые — описанным прямоугольником).
func _furniture_boxes() -> Array[AABB]:
	var boxes: Array[AABB] = []
	for node: Node in get_tree().get_nodes_in_group("dorm_furniture"):
		for found: Node in node.find_children("*","CollisionShape3D",true,false):
			var shape: CollisionShape3D = found as CollisionShape3D
			var box: BoxShape3D = shape.shape as BoxShape3D
			if box!=null:
				boxes.append(shape.global_transform*AABB(-box.size*0.5,box.size))
	return boxes


## Точка плана, на которой стоит мебель (с запасом на ширину идущего), — ближайшая свободная в сторону середины.
func _free_point(at: Vector3, middle: Vector3, boxes: Array[AABB]) -> Vector3:
	var p: Vector3 = at
	for step: int in range(50):
		var blocked: bool = false
		for box: AABB in boxes:
			if p.x>box.position.x-0.45 and p.x<box.end.x+0.45 and p.z>box.position.z-0.45 and p.z<box.end.z+0.45 \
					and box.position.y<p.y+1.0 and box.end.y>p.y+0.05:
				blocked = true
				break
		if not blocked:
			return p
		var to: Vector3 = Vector3(middle.x-p.x,0.0,middle.z-p.z)
		if to.length()<0.1:
			return p
		p += to.normalized()*0.1
	return p


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
			_open_nearby_doors()
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


func _v3_shots() -> void:
	if DisplayServer.get_name()=="headless":
		push_error("dorm: снимки требуют оконного запуска")
		get_tree().quit(1)
		return
	if lighting!=null:
		# DORM_V3_CASE=overcast_A — другой случай света (по умолчанию — выбранный владельцем)
		var case_id: String = OS.get_environment("DORM_V3_CASE") if OS.get_environment("DORM_V3_CASE")!="" else String(plan.environment.default)
		for index: int in range(plan.environment.cases.size()):
			if String(plan.environment.cases[index].id)==case_id:
				await lighting.call("set_case",index)
				break
		# DORM_V3_TARKOV=0 — без света «как в Таркове» (он основной, F9 в прогулке)
		if OS.get_environment("DORM_V3_TARKOV")!="":
			await lighting.call("set_tarkov",OS.get_environment("DORM_V3_TARKOV")!="0")
	walker.set_physics_process(false)
	hud.hide()
	for node: Node in get_tree().get_nodes_in_group("dorm_study_labels"):
		(node as Node3D).hide()
	var folder: String = output_dir.path_join("v3")
	DirAccess.make_dir_recursive_absolute(folder)
	var only: PackedStringArray = OS.get_environment("DORM_V3_VIEWS").split(",",false)
	Engine.max_fps = 0
	var fails: int = 0
	for leaf: Node in get_tree().get_nodes_in_group("dorm_study_doors"):
		leaf.call("reset_pose")
	# DORM_V3_LOOT=open — ящики, чемоданы, сумки и коробки партии 3 открыты, как после обыска
	if OS.get_environment("DORM_V3_LOOT")=="open":
		for box: Node in get_tree().get_nodes_in_group("dorm_loot_boxes"):
			box.call("open")
	# свои кадры: DORM_V3_VIEW="имя:x:y:z:куда_x:куда_y:куда_z;…" (глаз и точка взгляда в метрах); с ними штатные — только из DORM_V3_VIEWS
	# DORM_V3_FILL=1 — свет от камеры, как фонарь в руке: проверить мелочь и следы в тёмных местах
	if OS.get_environment("DORM_V3_FILL")!="":
		var fill: OmniLight3D = OmniLight3D.new()
		fill.omni_range = 9.0
		fill.light_energy = 1.6
		fill.shadow_enabled = true
		camera.add_child(fill)
	var views: Array[Dictionary] = []
	for spec: String in OS.get_environment("DORM_V3_VIEW").split(";",false):
		var p: PackedStringArray = spec.split(":")
		if p.size()==7:
			views.append({"id":p[0],"eye":Vector3(p[1].to_float(),p[2].to_float(),p[3].to_float()),"look":Vector3(p[4].to_float(),p[5].to_float(),p[6].to_float())})
	var all_shots: bool = only.is_empty() and views.is_empty()
	for view: Dictionary in plan.shots:
		if all_shots or String(view.id) in only:
			views.append({"id":view.id,"eye":_vec(view.foot)+Vector3.UP*float(view.eye_height),"look":_vec(view.look)})
	for view: Dictionary in views:
		camera.global_position = view.eye
		camera.look_at(view.look,Vector3.UP)
		await _frames(40)
		# время кадра на видеокарте (как в пробе света: синхронизацию держит драйвер) — среднее за 60 кадров
		var rid: RID = get_viewport().get_viewport_rid()
		RenderingServer.viewport_set_measure_render_time(rid,true)
		var gpu: float = 0.0
		for i: int in range(60):
			await RenderingServer.frame_post_draw
			gpu += RenderingServer.viewport_get_measured_render_time_gpu(rid)
		gpu /= 60.0
		print("dorm: %s — видеокарта %.2f мс (%.0f к/с)" % [String(view.id),gpu,1000.0/maxf(gpu,0.001)])
		await RenderingServer.frame_post_draw
		var filename: String = "v3_"+String(view.id)+".png"
		var error: Error = get_viewport().get_texture().get_image().save_png(folder.path_join(filename))
		if error!=OK:
			fails += 1
		print("dorm: снимок ",filename," ошибка=",error)
	world.queue_free()
	await _frames(3)
	get_tree().quit(fails)


func _shots() -> void:
	if lighting!=null:
		# матрица r6.1 сравнивается с архивами — свет той редакции, без «как в Таркове»
		await lighting.call("set_tarkov",false)
		var capture: RefCounted = LightCapture.new()
		await capture.call("run",self)
		return
	if DisplayServer.get_name()=="headless":
		push_error("dorm: снимки требуют оконного запуска")
		get_tree().quit(1)
		return
	walker.set_physics_process(false)
	hud.hide()
	for node: Node in get_tree().get_nodes_in_group("dorm_study_labels"):
		(node as Node3D).hide()
	DirAccess.make_dir_recursive_absolute(output_dir)
	var fails: int = 0
	for angle: float in [float(plan.scale.fov_h),95.0]:
		var manifest: Array[Dictionary] = []
		_set_fov(angle)
		var prefix: String = "stage1_" if angle==float(plan.scale.fov_h) else "stage1_fov95_"
		for leaf: Node in get_tree().get_nodes_in_group("dorm_study_doors"):
			leaf.call("reset_pose")
		for view: Dictionary in plan.shots:
			if angle==95.0 and String(view.id) not in ["01_corridor","02_room","05_stairs_bottom"]:
				continue
			var foot: Vector3 = _vec(view.foot)
			camera.global_position = foot+Vector3.UP*float(view.eye_height)
			camera.look_at(_vec(view.look),Vector3.UP)
			await _frames(24)
			await RenderingServer.frame_post_draw
			var filename: String = prefix+String(view.id)+".png"
			var error: Error = get_viewport().get_texture().get_image().save_png(output_dir.path_join(filename))
			if error!=OK:
				fails += 1
			manifest.append({"id":view.id,"revision":plan.version,"label":view.label,"file":filename,"foot":view.foot,"camera":[camera.global_position.x,camera.global_position.y,camera.global_position.z],
				"look":view.look,"eye_height":view.eye_height,"fov_h":angle,"fov_v":camera.fov,"viewport":get_viewport().get_visible_rect().size,"stage":1})
			print("dorm: снимок ",filename," ошибка=",error)
		var report_name: String = "stage1_views.json" if angle==float(plan.scale.fov_h) else "stage1_fov95_views.json"
		var report: FileAccess = FileAccess.open(output_dir.path_join(report_name),FileAccess.WRITE)
		report.store_string(JSON.stringify(manifest,"\t"))
		report.close()
	_set_fov(float(plan.scale.fov_h))
	world.queue_free()
	await _frames(3)
	get_tree().quit(fails)
