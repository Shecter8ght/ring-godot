extends Node3D
## Прогулка, проверка и снимки серого блокаута карты «Санаторий» (docs/design/sanatorium_map.md; уровень —
## scenes/levels/sanatorium_study.tscn, план — data/blockouts/sanatorium.json, генератор — tools/build_sanatorium.py).
##   tools/sanatorium_study.cmd                                                         — прогулка
##   tools/godot.cmd --headless --fixed-fps 60 res://tools/sanatorium_study.tscn -- verify — проверка пешком
##   tools/godot.cmd --windowed --resolution 1600x900 res://tools/sanatorium_study.tscn -- shots — снимки мест
##   tools/godot.cmd --windowed --resolution 1920x1080 --disable-vsync res://tools/sanatorium_study.tscn -- perf — замер кадров
##     по видам и местам: средний кадр, худший 1 %, время видеокарты, треугольники → perf.txt, perf.json
##   tools/sanatorium_play.cmd — та же карта с настоящим игроком, оружием и ботами (мир — этот стенд без ходока)
## Прогулка: WASD, Shift — бег, Space — прыжок, C — присесть, F — полёт (Shift — быстрее, Space / Ctrl — вверх / вниз),
## M — план (схема участка), 1–9, 0 — места 1–10, N / B — следующее / прошлое, R — к текущему месту, Esc — мышь.
## SANATORIUM_TIME=day|dusk|night, SANATORIUM_WEATHER=clear|overcast|rain|fog — свет рейдов; SANATORIUM_OUTPUT —
## папка отчёта и снимков (docs/screens/sanatorium); SANATORIUM_ROUTES=id,id — проверить только эти обходы;
## SANATORIUM_SHOTS=имя,имя — только эти снимки. Код выхода проверки — число провалов.

const LEVEL: String = "res://scenes/levels/sanatorium_study.tscn"
const Walker = preload("res://src/blockout/study_walker.gd")
const VIEW_FAR: float = 4000.0
const PERF_WARM: int = 90
const PERF_MEASURE: int = 240

var world: Node3D
var landscape: Node3D
var terrain: Node3D
var plan: Dictionary = {}
var y0: float = 0.0
var walker: CharacterBody3D
var mode: String = "walk"
var current: int = 0
var results: Array[Dictionary] = []
var hud: CanvasLayer
var title: Label
var status: Label
var map_layer: Control
var map_texture: TextureRect
var map_marker: ColorRect
var status_timer: float = 0.0
var out_dir: String = ""
var stats: Dictionary = {}


func _enter_tree() -> void:
	# внутри «игрока и ботов» (tools/sanatorium_play.gd) профиль ставит он; при F6 из сцены уровня — уровень
	if not has_meta("embedded") and world == null:
		Profile.use_file("user://profile_sanatorium_study_test.json", true)


func _ready() -> void:
	get_node("/root/Pause").set_process_input(false)
	get_node("/root/Quests").process_mode = Node.PROCESS_MODE_DISABLED
	get_node("/root/Contracts").process_mode = Node.PROCESS_MODE_DISABLED
	for arg: String in OS.get_cmdline_user_args():
		if arg in ["verify", "shots", "perf", "snapshot"]:
			mode = arg
	if has_meta("embedded"):
		mode = "embed"
	out_dir = _env("SANATORIUM_OUTPUT", ProjectSettings.globalize_path("res://docs/screens/sanatorium"))
	DisplayServer.window_set_title("RING · «Санаторий» · серый блокаут 1:1")
	var started: int = Time.get_ticks_msec()
	_environment()
	if world == null:
		world = (load(LEVEL) as PackedScene).instantiate() as Node3D
		add_child(world)
	landscape = world.get_node("Landscape") as Node3D
	terrain = world.get_node("Terrain") as Node3D
	plan = landscape.get("plan") as Dictionary
	stats.build_ms = Time.get_ticks_msec() - started
	stats.landscape_ms = int(landscape.get("built_ms"))
	if mode == "embed":
		return
	if mode == "snapshot":
		# снимок сцены для замера обзора (tools/sanatorium_ld_plan.py): объёмы и деревья в прежнем формате плана
		landscape.call("write_snapshot")
		print("sanatorium_study: снимок сцены → data/blockouts/sanatorium_snapshot*.json, коробок %d" % int((plan.stats as Dictionary).get("boxes", 0)))
		get_tree().quit(0)
		return
	walker = Walker.new()
	walker.name = "StudyWalker"
	add_child(walker)
	(walker.get("camera") as Camera3D).far = VIEW_FAR
	_ui()
	await _frames(4)
	_jump(5)
	print("sanatorium_study: сборка %d мс (объёмы %d мс), коробок %d, помещений %d, обходов %d" % [int(stats.build_ms),
		int(stats.landscape_ms), int((plan.stats as Dictionary).get("boxes", 0)), (plan.rooms as Array).size(), (plan.routes as Array).size()])
	if mode == "walk":
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		return
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	walker.set("is_probe", true)
	await _frames(6)
	if mode == "verify":
		await _verify()
	elif mode == "perf":
		await _perf()
	else:
		await _shots()


func _env(key: String, fallback: String) -> String:
	var value: String = OS.get_environment(key)
	return value if value != "" else fallback


func _frames(n: int) -> void:
	for i: int in range(n):
		await get_tree().physics_frame


## Свет и небо — общий свет рейдовых карт (RaidAtmosphere), как на настоящей карте.
func _environment() -> void:
	RaidConditions.current = RaidConditions.normalized({"time": _env("SANATORIUM_TIME", "day"),
		"weather": _env("SANATORIUM_WEATHER", "clear"), "power": "on"})
	var we: WorldEnvironment = WorldEnvironment.new()
	we.name = "WorldEnvironment"
	add_child(we)
	var sun: DirectionalLight3D = DirectionalLight3D.new()
	sun.name = "Sun"
	sun.rotation_degrees = Vector3(-40.0, -35.0, 0.0)
	sun.shadow_enabled = true
	add_child(sun)
	var atmosphere: RaidAtmosphere = RaidAtmosphere.new()
	atmosphere.name = "Atmosphere"
	add_child(atmosphere)
	atmosphere.apply()


# ---------------------------------------------------------------- для режима с игроком (tools/sanatorium_play.gd)

func ground(x: float, z: float) -> float:
	return y0 + float(terrain.call("height_at", x, z))


func _place_at(i: int) -> Array:
	var p: Dictionary = (plan.places as Array)[i]
	var at: Array = p.at
	var look: Array = p.look
	var floor_y: float = float(p.floor)
	return [Vector3(float(at[0]), floor_y + 0.05, float(at[1])), Vector3(float(look[0]), floor_y + 1.5, float(look[1]))]


# ---------------------------------------------------------------- прогулка

func _jump(i: int) -> void:
	var places: Array = plan.places
	current = posmod(i, places.size())
	var target: Array = _place_at(current)
	walker.call("teleport", target[0] + Vector3.UP * 0.05, target[1])
	if title:
		title.text = "«Санаторий» · %s" % String((places[current] as Dictionary).name)


func _unhandled_input(event: InputEvent) -> void:
	if mode != "walk":
		return
	if event is InputEventMouseButton and (event as InputEventMouseButton).pressed and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	if not (event is InputEventKey) or not (event as InputEventKey).pressed or event.is_echo():
		return
	var key: Key = (event as InputEventKey).physical_keycode
	if key == KEY_ESCAPE:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif key == KEY_M:
		map_layer.visible = not map_layer.visible
	elif key >= KEY_1 and key <= KEY_9:
		_jump(int(key - KEY_1))
	elif key == KEY_0:
		_jump(9)
	elif key == KEY_N:
		_jump(current + 1)
	elif key == KEY_B:
		_jump(current - 1)
	elif key == KEY_R:
		_jump(current)
		walker.set("travelled_m", 0.0)
		walker.set("walking_sec", 0.0)


func _process(delta: float) -> void:
	if hud == null or not is_instance_valid(walker):
		return
	status_timer -= delta
	if status_timer <= 0.0:
		status_timer = 0.25
		_update_status()
	if map_layer.visible:
		_update_marker()


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
	shade.position = Vector2(18, 18)
	shade.size = Vector2(980, 82)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(shade)
	title = Label.new()
	title.position = Vector2(32, 24)
	title.add_theme_font_size_override("font_size", 22)
	title.add_theme_color_override("font_color", Color("e0e3d2"))
	root.add_child(title)
	status = Label.new()
	status.position = Vector2(32, 58)
	status.add_theme_font_size_override("font_size", 16)
	root.add_child(status)
	var controls: Label = Label.new()
	controls.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	controls.position = Vector2(24, -84)
	controls.add_theme_font_size_override("font_size", 16)
	controls.add_theme_color_override("font_shadow_color", Color.BLACK)
	controls.add_theme_constant_override("shadow_outline_size", 8)
	controls.text = ("WASD — идти   Shift — бежать   Space — прыжок   C — присесть   F — полёт (Shift — быстрее)\n"
		+ "M — план участка   1–9, 0 — места   N / B — следующее / прошлое   R — к месту (и сброс счёта пути)   Esc — мышь\n"
		+ "Серый блокаут для замера масштаба: здания по принятым планам, проходы × 1,3, высоты × 1,15, ступени 1:1. Не рейд.")
	root.add_child(controls)
	map_layer = Control.new()
	map_layer.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	map_layer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	map_layer.hide()
	hud.add_child(map_layer)
	var dim: ColorRect = ColorRect.new()
	dim.color = Color(0, 0, 0, 0.55)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	map_layer.add_child(dim)
	map_texture = TextureRect.new()
	map_texture.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	map_texture.offset_top = 20
	map_texture.offset_bottom = -20
	map_texture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	map_texture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	map_texture.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var image: Image = Image.load_from_file(ProjectSettings.globalize_path(String(plan.plan_image)))
	if image:
		var crop: Array = plan.plan_image_crop
		image = image.get_region(Rect2i(int(crop[0]), int(crop[1]), mini(int(crop[2]), image.get_width()), mini(int(crop[3]), image.get_height())))
		map_texture.texture = ImageTexture.create_from_image(image)
	map_layer.add_child(map_texture)
	map_marker = ColorRect.new()
	map_marker.color = Color(1.0, 0.2, 0.1)
	map_marker.size = Vector2(14, 14)
	map_marker.mouse_filter = Control.MOUSE_FILTER_IGNORE
	map_layer.add_child(map_marker)


func _update_marker() -> void:
	if map_texture.texture == null:
		return
	var rect: Array = plan.plan_image_rect
	var tex: Vector2 = map_texture.texture.get_size()
	var area: Vector2 = map_texture.size
	var k: float = minf(area.x / tex.x, area.y / tex.y)
	var offset: Vector2 = map_texture.position + (area - tex * k) * 0.5
	var u: float = (walker.global_position.x - float(rect[0])) / (float(rect[2]) - float(rect[0]))
	var v: float = (walker.global_position.z - float(rect[1])) / (float(rect[3]) - float(rect[1]))
	map_marker.position = offset + Vector2(u, v) * tex * k - map_marker.size * 0.5


func _update_status() -> void:
	var p: Vector3 = walker.global_position
	var nearest: String = ""
	var best: float = INF
	for place: Dictionary in plan.places:
		var m: Array = place.marker
		var d: float = Vector2(p.x - float(m[0]), p.z - float(m[1])).length()
		if d < best:
			best = d
			nearest = String(place.name)
	if title and mode == "walk":
		title.text = "«Санаторий» · рядом: %s" % nearest
	status.text = "x %.0f  z %.0f · %+.1f м над озером · %.1f м/с · %.0f к/с · пройдено %.0f м за %.0f с%s" % [
		p.x, p.z, p.y - y0, Vector2(walker.velocity.x, walker.velocity.z).length(), Engine.get_frames_per_second(),
		float(walker.get("travelled_m")), float(walker.get("walking_sec")), " · полёт" if bool(walker.get("flight")) else ""]


# ---------------------------------------------------------------- проверка пешком

func _check(label: String, passed: bool, details: Variant = {}) -> void:
	results.append({"check": label, "pass": passed, "details": details})
	print("sanatorium_study: %s · %s %s" % ["PASS" if passed else "FAIL", label, JSON.stringify(details)])


func _capsule_clear(at: Vector3) -> bool:
	var query: PhysicsShapeQueryParameters3D = PhysicsShapeQueryParameters3D.new()
	query.shape = (walker.get("capsule") as CollisionShape3D).shape
	query.transform = Transform3D(Basis.IDENTITY, at + Vector3.UP * (Balance.STANCE_HEIGHT.stand * 0.5 + 0.06))
	query.collision_mask = 1
	return get_world_3d().direct_space_state.intersect_shape(query, 1).is_empty()


func _verify() -> void:
	var st: Dictionary = plan.stats
	_check("Собрано: объёмы, марши, помещения, обходы", int(st.boxes) > 3000 and int(st.stairs) > 60 and int(st.rooms) > 500,
		{"stats": st, "build_ms": stats.build_ms, "landscape_ms": stats.landscape_ms, "triangles": int(landscape.get_node("_Generated").get_meta("triangles", 0))})
	_check("Габариты и скорость ходока — из Balance", is_equal_approx(((walker.get("capsule") as CollisionShape3D).shape as CapsuleShape3D).height,
		Balance.STANCE_HEIGHT.stand), {"walk_m_s": Balance.PLAYER_WALK_SPEED, "sprint_m_s": Balance.PLAYER_SPRINT_SPEED})
	# места: точка появления свободна и под ногами пол
	for i: int in range((plan.places as Array).size()):
		_jump(i)
		await _frames(10)
		var p: Vector3 = walker.global_position
		var want: float = float(((plan.places as Array)[i] as Dictionary).floor)
		_check("Место «%s»: свободно, стоит на полу" % String(((plan.places as Array)[i] as Dictionary).name),
			_capsule_clear(p) and walker.is_on_floor() and absf(p.y - want) < 0.4, {"at": str(p), "floor": want})
	# обходы: здания (все помещения и лестницы), спуски, маршруты по участку
	var only: PackedStringArray = _env("SANATORIUM_ROUTES", "").split(",", false)
	var reached: Dictionary = {}
	var walked: float = 0.0
	var walked_sec: float = 0.0
	var started: int = Time.get_ticks_msec()
	for route: Dictionary in plan.routes:
		if not only.is_empty() and not String(route.id) in only:
			continue
		walker.set("travelled_m", 0.0)
		walker.set("walking_sec", 0.0)
		var res: Dictionary = await _walk_route(route)
		walked += float(walker.get("travelled_m"))
		walked_sec += float(walker.get("walking_sec"))
		var bad: Array = []
		for c: Array in route.checks:
			var idx: int = int(c[0])
			var got: float = float((res.heights as Dictionary).get(idx, INF))
			if absf(got - float(c[2])) < 0.45:
				reached[String(c[1])] = true
			else:
				bad.append({"uid": String(c[1]), "want": float(c[2]), "got": snappedf(got, 0.01)})
		var details: Dictionary = {"points": (route.points as Array).size(), "checks": (route.checks as Array).size(),
			"m": snappedf(float(walker.get("travelled_m")), 1.0), "s": snappedf(float(walker.get("walking_sec")), 1.0)}
		if not bool(res.ok):
			details["stuck"] = res.stuck
		if not bad.is_empty():
			details["wrong_level"] = bad
		_check("Пешком: %s" % String(route.label), bool(res.ok) and bad.is_empty(), details)
	if only.is_empty():
		var missing: Array = []
		for room: Dictionary in plan.rooms:
			if not reached.has(String(room.uid)):
				missing.append("%s · %s" % [String(room.building), String(room.name)])
		_check("Все помещения пройдены пешком (%d)" % (plan.rooms as Array).size(), missing.is_empty(),
			{"missing": missing.slice(0, 40), "missing_count": missing.size()})
	# нельзя: с набережной в озеро, через забор на восток
	for n: Dictionary in plan.negative:
		var a: Array = n.from
		var b: Array = n.to
		var from: Vector3 = Vector3(float(a[0]), ground(float(a[0]), float(a[1])) + 0.1, float(a[1]))
		var to: Vector3 = Vector3(float(b[0]), from.y, float(b[1]))
		var res: Dictionary = await _walk_route({"points": [[from.x, from.y, from.z], [to.x, to.y, to.z]]}, 900)
		var x: float = walker.global_position.x
		var held: bool = x > float(n.stop_x) if to.x < from.x else x < float(n.stop_x)
		_check(String(n.label), not bool(res.ok) and held, {"x": snappedf(x, 0.1), "limit": n.stop_x})
	var fails: int = results.filter(func(r: Dictionary) -> bool: return not bool(r.pass)).size()
	DirAccess.make_dir_recursive_absolute(out_dir)
	var report: FileAccess = FileAccess.open(out_dir.path_join("validation.json"), FileAccess.WRITE)
	report.store_string(JSON.stringify({"checks": results, "fails": fails, "walked_m": snappedf(walked, 1.0),
		"walked_sim_s": snappedf(walked_sec, 1.0), "real_s": (Time.get_ticks_msec() - started) / 1000.0,
		"deviations": plan.get("deviations", []), "levels": plan.get("levels", {})}, "\t"))
	report.close()
	print("sanatorium_study: пройдено %.0f м (%.0f с хода), проверок %d, провалов %d" % [walked, walked_sec, results.size(), fails])
	get_tree().quit(mini(fails, 255))


## Ходок идёт по точкам обхода по физике (как игрок): бегом между точками, у точки — шагом, чтобы поворот в дверь не
## заносил в косяк. Возвращает {ok, stuck, heights: {индекс точки: высота ног по приходе}}.
func _walk_route(route: Dictionary, frame_limit: int = 20000) -> Dictionary:
	var pts: Array = route.points
	var heights: Dictionary = {}
	var first: Vector3 = Vector3(float(pts[0][0]), float(pts[0][1]) + 0.1, float(pts[0][2]))
	var second: Vector3 = Vector3(float(pts[1][0]), first.y, float(pts[1][2])) if pts.size() > 1 else first + Vector3.FORWARD
	walker.set("probe_direction", Vector3.ZERO)
	walker.set("probe_sprint", true)
	walker.call("teleport", first, second)
	await _frames(8)
	heights[0] = walker.global_position.y
	for i: int in range(1, pts.size()):
		var target: Vector3 = Vector3(float(pts[i][0]), float(pts[i][1]), float(pts[i][2]))
		var previous: float = INF
		var stalled: int = 0
		var stuck_total: int = 0
		var side: float = 1.0
		var reached: bool = false
		for frame: int in range(frame_limit):
			var delta: Vector3 = target - walker.global_position
			delta.y = 0.0
			var dist: float = delta.length()
			if dist < 0.22:
				reached = true
				break
			if dist > previous - 0.002:
				stalled += 1
				stuck_total += 1
			else:
				stalled = 0
			previous = dist
			if stuck_total > 700 or walker.global_position.y < -15.0:
				break
			if stalled > 40:
				# упёрся (угол тесной площадки лестницы): сначала шаг назад от цели, потом вбок — как человек; без шага
				# назад исход зависел от долей миллиметра (порядок касаний у физики) — 2026-11-08, перенос в сцены
				for k: int in range(10):
					walker.set("probe_direction", -delta.normalized() * 0.6)
					await get_tree().physics_frame
				for k: int in range(22):
					walker.set("probe_direction", delta.normalized().cross(Vector3.UP) * side * 0.6)
					await get_tree().physics_frame
				side = -side
				stalled = 0
				previous = INF
			# направление — единичное (по нему же ходок ищет ступеньку впереди); у точки — шагом, а не бегом
			walker.set("probe_sprint", dist > 2.4)
			walker.set("probe_direction", delta.normalized())
			await get_tree().physics_frame
		if not reached:
			walker.set("probe_direction", Vector3.ZERO)
			return {"ok": false, "stuck": {"at": str(walker.global_position), "to": str(target), "point": i}, "heights": heights}
		heights[i] = walker.global_position.y
		if _env("SANATORIUM_TRACE", "") != "":
			print("  точка %d: цель %s, ходок %s" % [i, str(target), str(walker.global_position)])
	walker.set("probe_direction", Vector3.ZERO)
	walker.velocity = Vector3.ZERO
	return {"ok": true, "stuck": {}, "heights": heights}


# ---------------------------------------------------------------- снимки

func _shots() -> void:
	walker.set_physics_process(false)
	hud.hide()
	DirAccess.make_dir_recursive_absolute(out_dir)
	var camera: Camera3D = walker.get("camera") as Camera3D
	camera.fov = 62.0
	var views: Array[Dictionary] = _view_list()
	var only: PackedStringArray = _env("SANATORIUM_SHOTS", "").split(",", false)
	var perf: Array = []
	for v: Dictionary in views:
		if not only.is_empty() and not String(v.id) in only:
			continue
		walker.global_position = (v.at as Vector3) - Vector3.UP * 1.62
		camera.global_position = v.at
		camera.look_at(v.look, Vector3.UP)
		await _frames(50)
		var fps: Array = []
		for k: int in range(30):
			await get_tree().process_frame
			fps.append(Engine.get_frames_per_second())
		var image: Image = get_viewport().get_texture().get_image()
		if image:
			image.save_jpg(out_dir.path_join("%s.jpg" % String(v.id)), 0.88)
		perf.append({"id": v.id, "fps": fps.max(), "draws": int(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)),
			"primitives": int(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME))})
		print("sanatorium_study: снимок %s · %s" % [String(v.id), JSON.stringify(perf[-1])])
	var f: FileAccess = FileAccess.open(out_dir.path_join("shots.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify({"views": perf, "time": _env("SANATORIUM_TIME", "day")}, "\t"))
	f.close()
	get_tree().quit(0)


## Виды для снимков и замера: виды генератора (глаз — по полу и земле) и места карты.
func _view_list() -> Array[Dictionary]:
	var views: Array[Dictionary] = []
	for v: Dictionary in plan.get("views", []):
		var at: Array = v.at
		var look: Array = v.look
		views.append({"id": String(v.id), "at": Vector3(float(at[0]), float(at[1]), float(at[2])),
			"look": Vector3(float(look[0]), float(look[1]), float(look[2]))})
	for i: int in range((plan.places as Array).size()):
		var t: Array = _place_at(i)
		var p: Dictionary = (plan.places as Array)[i]
		views.append({"id": "place_%02d" % int(p.n), "at": (t[0] as Vector3) + Vector3.UP * 1.62, "look": t[1]})
	return views


## Замер кадров: на каждом виде и месте прогрев, потом PERF_MEASURE кадров без вертикальной синхронизации — средний
## кадр, худший 1 %, время видеокарты, треугольники и вызовы. Среднее — только по точкам на высоте глаз (облёты сверху
## и с озера — для картинки). Поле зрения — как у игрока.
func _perf() -> void:
	walker.set_physics_process(false)
	hud.hide()
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	DirAccess.make_dir_recursive_absolute(out_dir)
	var camera: Camera3D = walker.get("camera") as Camera3D
	camera.fov = Settings.fps_fov_v()
	var vp: RID = get_viewport().get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(vp, true)
	var size: Vector2i = DisplayServer.window_get_size()
	var lines: PackedStringArray = [
		"«Санаторий», серый блокаут · замер кадров",
		"%s · %dx%d · качество %s · %s, %s · деревьев %d · сборка %d мс" % [RenderingServer.get_video_adapter_name(), size.x, size.y,
			Settings.quality, String(RaidConditions.current.time), String(RaidConditions.current.weather), int((plan.stats as Dictionary).get("trees", 0)),
			int(stats.build_ms)],
		"  %-22s %7s %7s %7s %7s %10s %8s" % ["точка", "к/с", "мс", "1% мс", "GPU мс", "треуг.", "вызовов"],
	]
	for l: String in lines:
		print(l)
	var rows: Array = []
	var total: float = 0.0
	var count: int = 0
	var worst_row: Dictionary = {}
	var only: PackedStringArray = _env("SANATORIUM_SHOTS", "").split(",", false)
	for v: Dictionary in _view_list():
		if not only.is_empty() and not String(v.id) in only:
			continue
		var at: Vector3 = v.at
		walker.global_position = at - Vector3.UP * 1.62
		camera.global_position = at
		camera.look_at(v.look, Vector3.UP)
		for i: int in range(PERF_WARM):
			await get_tree().process_frame
		var times: Array[float] = []
		var gpu: float = 0.0
		var t0: int = Time.get_ticks_usec()
		for i: int in range(PERF_MEASURE):
			await get_tree().process_frame
			var t1: int = Time.get_ticks_usec()
			times.append(float(t1 - t0) / 1000.0)
			t0 = t1
			gpu += RenderingServer.viewport_get_measured_render_time_gpu(vp)
		times.sort()
		var mean: float = 0.0
		for t: float in times:
			mean += t
		mean /= float(times.size())
		var eye: bool = not String(v.id) in ["00_overview", "00_from_lake"]      # облёты сверху и с озера — для картинки
		var row: Dictionary = {"id": String(v.id), "fps": snappedf(1000.0 / mean, 0.1), "ms": snappedf(mean, 0.01),
			"low1_ms": snappedf(times[int(times.size() * 0.99)], 0.01), "gpu_ms": snappedf(gpu / float(PERF_MEASURE), 0.01),
			"tris": int(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)),
			"draws": int(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)), "eye": eye}
		rows.append(row)
		var line: String = "  %-22s %7.1f %7.2f %7.2f %7.2f %10d %8d%s" % [row.id, row.fps, row.ms, row.low1_ms, row.gpu_ms, row.tris,
			row.draws, "" if eye else "  (облёт)"]
		print(line)
		lines.append(line)
		if eye:
			total += mean
			count += 1
			if worst_row.is_empty() or float(row.ms) > float(worst_row.ms):
				worst_row = row
	var summary: Dictionary = {}
	if count > 0:
		summary = {"points": count, "fps_mean": snappedf(1000.0 / (total / count), 0.1), "ms_mean": snappedf(total / count, 0.01),
			"worst": worst_row}
		var avg: String = "  на высоте глаз: %d точек, в среднем %.1f к/с (%.2f мс); хуже всего — %s: %.1f к/с, 1%% — %.2f мс" % [
			count, float(summary.fps_mean), float(summary.ms_mean), String(worst_row.id), float(worst_row.fps), float(worst_row.low1_ms)]
		print(avg)
		lines.append(avg)
	var f: FileAccess = FileAccess.open(out_dir.path_join("perf.txt"), FileAccess.WRITE)
	f.store_string("
".join(lines) + "
")
	f.close()
	var j: FileAccess = FileAccess.open(out_dir.path_join("perf.json"), FileAccess.WRITE)
	j.store_string(JSON.stringify({"adapter": RenderingServer.get_video_adapter_name(), "size": [size.x, size.y],
		"quality": Settings.quality, "time": String(RaidConditions.current.time), "weather": String(RaidConditions.current.weather),
		"summary": summary, "points": rows}, "	"))
	j.close()
	get_tree().quit(0)
