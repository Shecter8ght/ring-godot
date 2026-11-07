extends Node3D
## Прогулка, проверка и снимки серого блокаута «Проспекта» (scenes/levels/prospekt_study.tscn,
## план — data/blockouts/prospekt.json, генератор — tools/build_prospekt.py).
##   tools/godot.cmd --windowed --resolution 1600x900 res://tools/prospekt_study.tscn              — прогулка
##   tools/godot.cmd --headless res://tools/prospekt_study.tscn -- verify                           — проверка
##   tools/godot.cmd --windowed --resolution 1600x900 res://tools/prospekt_study.tscn -- shots      — снимки
## Прогулка: WASD, Shift — бег, C — присесть, Space — прыжок, M — план, 1–9/0 — места, N/B — следующее /
## прошлое, F — полёт, R — сначала, Esc — мышь. PROSPEKT_OUTPUT — папка отчёта и снимков
## (по умолчанию docs/screens/prospekt). Код выхода проверки — число провалов.

const LEVEL: String = "res://scenes/levels/prospekt_study.tscn"
const Walker = preload("res://src/blockout/study_walker.gd")
const LightVariants = preload("res://tools/prospekt_light_variants.gd")
const START: int = 1

var world: Node3D
var landscape: Node3D
var walker: CharacterBody3D
var plan: Dictionary
var hud: CanvasLayer
var title: Label
var status: Label
var hint: Label
var map: Control
var output_dir: String
var results: Array[Dictionary] = []
var mode: String = "walk"
var current: int = START


func _enter_tree() -> void:
	if world == null:
		Profile.use_file("user://profile_prospekt_study_test.json", true)


func _ready() -> void:
	DisplayServer.window_set_title("RING · «Проспект» · серый блокаут 1:1")
	get_node("/root/Pause").set_process_input(false)
	get_node("/root/Quests").process_mode = Node.PROCESS_MODE_DISABLED
	get_node("/root/Contracts").process_mode = Node.PROCESS_MODE_DISABLED
	for arg: String in OS.get_cmdline_user_args():
		if arg in ["verify", "shots"]:
			mode = arg
	output_dir = OS.get_environment("PROSPEKT_OUTPUT")
	if output_dir.is_empty():
		output_dir = ProjectSettings.globalize_path("res://docs/screens/prospekt")
	if world == null:
		world = (load(LEVEL) as PackedScene).instantiate() as Node3D
		add_child(world)
	landscape = world.get_node("Landscape") as Node3D
	plan = landscape.get("plan") as Dictionary
	walker = Walker.new()
	walker.name = "StudyWalker"
	add_child(walker)
	_ui()
	await _frames(4)
	_jump_to(START)
	if mode == "walk":
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		print("prospekt_study: прогулка; WASD, Shift, M — план, 1–9/0 и N/B — места, F — полёт, Esc — мышь")
	else:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		walker.set("is_probe", true)
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
	shade.position = Vector2(18, 18)
	shade.size = Vector2(760, 82)
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
	controls.text = ("WASD — идти   Shift — бежать   Space — прыжок   C — присесть   F — полёт   R — сначала\n"
		+ "M — план   1–9, 0 — места 1–10   N / B — следующее / прошлое\n"
		+ "Esc — освободить мышь · щелчок — продолжить · это серый блокаут для замера, не рейд · масштаб: проходы × 1,3, высоты × 1,15, предметы 1:1")
	root.add_child(controls)
	hint = Label.new()
	hint.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	hint.grow_horizontal = Control.GROW_DIRECTION_BOTH
	hint.grow_vertical = Control.GROW_DIRECTION_BOTH
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint.add_theme_font_size_override("font_size", 22)
	hint.add_theme_color_override("font_shadow_color", Color.BLACK)
	hint.add_theme_constant_override("shadow_outline_size", 10)
	hint.text = "Щёлкните по картинке — мышь будет управлять обзором\n(или держите ПКМ и ведите мышью). WASD — идти."
	hint.hide()
	root.add_child(hint)
	map = PlanMap.new()
	map.name = "Plan"
	map.set("plan", plan)
	map.set("walker", walker)
	map.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	map.hide()
	root.add_child(map)


func _process(_delta: float) -> void:
	if not is_instance_valid(walker) or plan.is_empty():
		return
	var nearest: Dictionary = plan.locations[0]
	var distance: float = INF
	for loc: Dictionary in plan.locations:
		var at: Array = loc.at
		var d: float = Vector2(walker.global_position.x, walker.global_position.z).distance_to(Vector2(float(at[0]), float(at[1])))
		if d < distance:
			distance = d
			nearest = loc
	title.text = "%d · %s" % [int(nearest.id), String(nearest.label)]
	status.text = "x %.0f  z %.0f  y %.1f · %.1f м/с · пройдено %.0f м за %.0f с · %d к/с%s" % [
		walker.global_position.x, walker.global_position.z, walker.global_position.y,
		Vector2(walker.velocity.x, walker.velocity.z).length(), float(walker.get("travelled_m")), float(walker.get("walking_sec")),
		Engine.get_frames_per_second(), " · полёт" if bool(walker.get("flight")) else ""]
	if mode == "walk":
		hint.visible = Input.mouse_mode != Input.MOUSE_MODE_CAPTURED and not map.visible
	if map.visible:
		map.queue_redraw()


func _unhandled_input(event: InputEvent) -> void:
	if mode != "walk":
		return
	if event is InputEventMouseButton and (event as InputEventMouseButton).pressed and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
		if Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
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
		KEY_R:
			_jump_to(START)
			walker.set("travelled_m", 0.0)
			walker.set("walking_sec", 0.0)
		KEY_N:
			_jump_to(current % plan.locations.size() + 1)
		KEY_B:
			_jump_to((current - 2 + plan.locations.size()) % plan.locations.size() + 1)
		KEY_1, KEY_2, KEY_3, KEY_4, KEY_5, KEY_6, KEY_7, KEY_8, KEY_9:
			_jump_to(key.physical_keycode - KEY_1 + 1)
		KEY_0:
			_jump_to(10)
		KEY_MINUS:
			_jump_to(mini(11, plan.locations.size()))


func _jump_to(index: int) -> void:
	current = index
	var loc: Dictionary = plan.locations[index - 1]
	var p: Array = loc.spawn
	var target: Array = loc.look
	var at: Vector3 = Vector3(float(p[0]), 0.1, float(p[1]))
	walker.call("teleport", at, Vector3(float(target[0]), at.y, float(target[1])))


func _frames(count: int) -> void:
	for i: int in range(count):
		await get_tree().physics_frame


func _check(label: String, passed: bool, details: Dictionary = {}) -> void:
	results.append({"check": label, "pass": passed, "details": details})
	print("prospekt_study: %s · %s %s" % ["PASS" if passed else "FAIL", label, JSON.stringify(details)])


func _ray_y(x: float, z: float, from_y: float = 40.0, depth: float = 80.0) -> float:
	var from: Vector3 = Vector3(x, from_y, z)
	var hit: Dictionary = walker.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(from, from - Vector3.UP * depth, 1))
	return (hit.position as Vector3).y if not hit.is_empty() else INF


# ---------------------------------------------------------------- проверка

func _verify() -> void:
	var buildings: Array = plan.buildings
	var halls: int = 0
	var open_kinds: Array = []
	for node: Node in get_tree().get_nodes_in_group("mall_study_snap"):
		if bool(node.get_meta("enterable", false)) and not String(node.name).begins_with("Outside"):
			halls += 1
			open_kinds.append(node.name)
	_check("Открытые здания собраны: магазины в два этажа, «Ярус», минимаркеты, кафе, каркасы стройки",
		halls >= 10, {"enterable": open_kinds})
	# места лута (владелец 2026-10-24, п. 8): контейнеры и свободно; у каждого места карты — не меньше трёх в 45 м
	var loot: Array = plan.get("loot", []) as Array
	var poor: Array = []
	for loc: Dictionary in plan.locations:
		var at: Array = loc.at
		var near: int = 0
		for l: Dictionary in loot:
			var p: Array = l.at
			if Vector2(float(p[0]), float(p[2])).distance_to(Vector2(float(at[0]), float(at[1]))) < 45.0:
				near += 1
		if near < 3:
			poor.append(String(loc.label))
	var kinds: Dictionary = {}
	for l: Dictionary in loot:
		kinds[String(l.kind)] = int(kinds.get(String(l.kind), 0)) + 1
	_check("Места лута: больше 120, у каждого места карты не меньше трёх", loot.size() > 120 and poor.is_empty(),
		{"count": loot.size(), "kinds": kinds, "poor": poor})
	var filler: Node = world.get_node_or_null("Filler")
	var stats: Dictionary = filler.get_meta("stats", {}) if filler else {}
	_check("Наполнение: машины, ларьки, ограждения, фонари — больше 300 экземпляров", int(stats.get("instances", 0)) > 300, stats)
	_check("Габариты и скорость из Balance", is_equal_approx(((walker.get("capsule") as CollisionShape3D).shape as CapsuleShape3D).height, Balance.STANCE_HEIGHT.stand),
		{"walk_m_s": Balance.PLAYER_WALK_SPEED, "sprint_m_s": Balance.PLAYER_SPRINT_SPEED})
	# уровни: паркинг −1 под плитой двора, переход под дорогой
	var checks: Dictionary = plan.get("checks", {}) as Dictionary
	var pp: Array = checks.get("pit", [-44.0, -70.0])
	var tp: Array = checks.get("tunnel", [-44.0, 0.0])
	var yard_y: float = _ray_y(float(pp[0]), float(pp[1]))
	var want_pit: float = float(checks.get("pit_y", -3.2))
	var pit_y: float = _ray_y(float(pp[0]), float(pp[1]), -1.0, -want_pit + 3.0)
	_check("Паркинг −1: плита двора на нуле, пол на %.1f" % want_pit, absf(yard_y) < 0.2 and absf(pit_y - want_pit) < 0.2,
		{"yard_y": yard_y, "pit_y": pit_y})
	var road_y: float = _ray_y(float(tp[0]), float(tp[1]))
	var tunnel_y: float = _ray_y(float(tp[0]), float(tp[1]), -0.6, 6.0)
	_check("Подземный переход: дорога сверху, пол на −3,3", absf(road_y) < 0.2 and absf(tunnel_y + 3.3) < 0.2, {"road_y": road_y, "tunnel_y": tunnel_y})
	# безопасные точки мест
	for loc: Dictionary in plan.locations:
		_jump_to(int(loc.id))
		await _frames(8)
		var query: PhysicsShapeQueryParameters3D = PhysicsShapeQueryParameters3D.new()
		query.shape = (walker.get("capsule") as CollisionShape3D).shape
		query.transform = Transform3D(Basis.IDENTITY, walker.global_position + Vector3.UP * (Balance.STANCE_HEIGHT.stand * 0.5 + 0.04))
		query.collision_mask = 1
		var clear: bool = walker.get_world_3d().direct_space_state.intersect_shape(query, 1).is_empty()
		_check("Безопасная точка: " + String(loc.label), clear and walker.is_on_floor(), {"position": str(walker.global_position)})
	# подходы: пешеход идёт по физике; открытые куски — по укрытиям наполнения и постройкам
	for route: Dictionary in plan.probe_routes:
		var path: Array[Vector3] = []
		for p: Array in route.points:
			path.append(Vector3(float(p[0]), 0.1, float(p[1])))
		var ok: bool = await _walk_path(path, true)
		var details: Dictionary = {"end": str(walker.global_position)}
		if route.has("max_y"):
			var low: bool = walker.global_position.y <= float(route.max_y)
			details["y"] = walker.global_position.y
			_check("Маршрут «%s»: пройден и спустился под землю" % String(route.label), ok and low, details)
		elif route.has("min_y"):
			var high: bool = walker.global_position.y >= float(route.min_y)
			details["y"] = walker.global_position.y
			_check("Маршрут «%s»: пройден и поднялся на этаж" % String(route.label), ok and high, details)
		else:
			_check("Маршрут «%s» пройден пешком" % String(route.label), ok, details)
		if float(route.get("max_open_m", 0.0)) > 0.0:
			var open: float = _open_stretch(route.points)
			_check("Маршрут «%s»: открытый кусок не длиннее %.0f м" % [String(route.label), float(route.max_open_m)],
				open <= float(route.max_open_m), {"open_m": snappedf(open, 0.5)})
	# кордон — граница: к воротам подойти можно, пройти нельзя
	var cc: Dictionary = checks.get("cordon", {"from": [-110.0, 0.0], "to": [-126.0, 0.0], "stop_x": -121.5}) as Dictionary
	var cf: Array = cc.from
	var ct: Array = cc.to
	var blocked: bool = not await _walk_path([Vector3(float(cf[0]), 0.1, float(cf[1])), Vector3(float(ct[0]), 0.1, float(ct[1]))], true)
	_check("Кордон: плиты через проспект не пройти", blocked and walker.global_position.x > float(cc.stop_x), {"x": walker.global_position.x})
	var fails: int = 0
	for r: Dictionary in results:
		if not bool(r.pass):
			fails += 1
	DirAccess.make_dir_recursive_absolute(output_dir)
	var report: FileAccess = FileAccess.open(output_dir.path_join("validation.json"), FileAccess.WRITE)
	report.store_string(JSON.stringify({"checks": results, "fails": fails, "buildings": buildings.size(),
		"items": int(plan.get("items_count", 0)), "scale": plan.get("scale", {})}, "\t"))
	report.close()
	print("prospekt_study: проверок %d, провалов %d" % [results.size(), fails])
	get_tree().quit(fails)


## Длина самого длинного открытого куска ломаной: точка под укрытием, если ближе 15 м к постройке или укрытию наполнения.
func _open_stretch(points: Array) -> float:
	var cover: PackedVector2Array = PackedVector2Array()
	for c: Array in (plan.filler as Dictionary).get("cover", []):
		cover.append(Vector2(float(c[0]), float(c[1])))
	var rects: Array[Dictionary] = []
	for b: Dictionary in plan.buildings:
		rects.append(b)
	var worst: float = 0.0
	var run: float = 0.0
	var previous: Vector2 = Vector2(float(points[0][0]), float(points[0][1]))
	for i: int in range(1, points.size()):
		var next: Vector2 = Vector2(float(points[i][0]), float(points[i][1]))
		var steps: int = maxi(1, int(previous.distance_to(next) / 2.0))
		for k: int in range(1, steps + 1):
			var p: Vector2 = previous.lerp(next, float(k) / float(steps))
			var covered: bool = false
			for c: Vector2 in cover:
				if c.distance_to(p) < 15.0:
					covered = true
					break
			if not covered:
				for b: Dictionary in rects:
					var at: Array = b.at
					var size: Array = b.size
					var yaw: float = deg_to_rad(float(b.yaw))
					var local: Vector2 = (p - Vector2(float(at[0]), float(at[1]))).rotated(-yaw)
					var dx: float = maxf(absf(local.x) - float(size[0]) * 0.5, 0.0)
					var dz: float = maxf(absf(local.y) - float(size[1]) * 0.5, 0.0)
					if Vector2(dx, dz).length() < 15.0:
						covered = true
						break
			run = 0.0 if covered else run + previous.distance_to(next) / float(steps)
			worst = maxf(worst, run)
		previous = next
	return worst


func _walk_path(path: Array[Vector3], sprint: bool) -> bool:
	walker.set("probe_direction", Vector3.ZERO)
	walker.set("probe_sprint", sprint)
	walker.call("teleport", path[0], path[0] + Vector3.FORWARD)
	await _frames(10)
	for target: Vector3 in path.slice(1):
		var previous: float = INF
		var stalled: int = 0
		var stuck_total: int = 0
		var side: float = 1.0
		var reached: bool = false
		for frame: int in range(24000):
			var delta: Vector3 = target - walker.global_position
			delta.y = 0.0
			if delta.length() < 0.25:
				reached = true
				break
			if delta.length() > previous - 0.001:
				stalled += 1
				stuck_total += 1
			else:
				stalled = 0
			previous = delta.length()
			if stuck_total > 600 or walker.global_position.y < -20.0:
				break
			if stalled > 45:
				for k: int in range(25):
					walker.set("probe_direction", delta.normalized().cross(Vector3.UP) * side)
					await get_tree().physics_frame
				side = -side
				stalled = 0
				previous = INF
			walker.set("probe_direction", delta.normalized())
			await get_tree().physics_frame
		walker.set("probe_direction", Vector3.ZERO)
		walker.velocity.x = 0.0
		walker.velocity.z = 0.0
		if not reached:
			print("prospekt_study: застрял в %s на пути к %s" % [str(walker.global_position), str(target)])
			return false
	return true


# ---------------------------------------------------------------- снимки

func _shots() -> void:
	walker.set_physics_process(false)
	hud.hide()
	DirAccess.make_dir_recursive_absolute(output_dir)
	var camera: Camera3D = walker.get("camera") as Camera3D
	var views: Array[Dictionary] = [
		{"id": "01_overview", "at": Vector3(-30, 430, 330), "look": Vector3(-30, 0, 60)},
		{"id": "02_cordon_eye", "at": Vector3(-200, 1.62, -15.65), "look": Vector3(-150, 2, -33.97)},
		{"id": "03_coffee_eye", "at": Vector3(-184, 1.62, -39.28), "look": Vector3(-184, 1.5, -53.3)},
		{"id": "04_avenue_east", "at": Vector3(-170, 1.62, -40.93), "look": Vector3(-60, 2, -29.26)},
		{"id": "05_underpass", "at": Vector3(-148, 1.62, -36.8), "look": Vector3(-158, -2.5, -42.58)},
		{"id": "06_tunnel_eye", "at": Vector3(-156, -1.7, -33.97), "look": Vector3(-156, -2, 9.63)},
		{"id": "07_parking_lot", "at": Vector3(-146, 1.62, 17), "look": Vector3(-102, 2, 48)},
		{"id": "08_supermarket_hall", "at": Vector3(-108, 1.62, 50), "look": Vector3(-102, 1.5, 82)},
		{"id": "09_dock_yard", "at": Vector3(-102, 1.62, 95), "look": Vector3(-60, 1.5, 97)},
		{"id": "10_yard_zhk", "at": Vector3(-125, 1.62, -131.3), "look": Vector3(-175, 2, -113.3)},
		{"id": "11_parking_minus1", "at": Vector3(-110, -5.68, -73.3), "look": Vector3(-170, -5.0, -73.3)},
		{"id": "12_ramp", "at": Vector3(-110.6, 1.62, -35.98), "look": Vector3(-117.5, -0.5, -61.3)},
		{"id": "13_curve", "at": Vector3(-40, 1.62, -40.93), "look": Vector3(44.71, 3, 27.05)},
		{"id": "14_vershina_plaza", "at": Vector3(11.88, 1.62, -3.22), "look": Vector3(91.3, 20, -71.3)},
		{"id": "15_south_leg", "at": Vector3(94.28, 1.62, 70), "look": Vector3(72.65, 2, 240)},
		{"id": "16_shop_roof", "at": Vector3(-150, 10.0, -57.3), "look": Vector3(-130, 8.0, -37.63)},
		{"id": "17_bird_curve", "at": Vector3(-60, 120, 140), "look": Vector3(20.31, 0, 19.46)},
		{"id": "18_bank", "at": Vector3(-8, 1.62, -22.19), "look": Vector3(-22, 7.0, -75.3)},
		{"id": "19_evac_point", "at": Vector3(139.3, 1.62, 60), "look": Vector3(169.3, 2.0, -19.3)},
		{"id": "20_stop_plaza", "at": Vector3(-180, 1.62, 9.63), "look": Vector3(-195, 2, 40)},
		{"id": "21_square", "at": Vector3(-35, 1.62, 25), "look": Vector3(-5, 2, 75)},
		{"id": "22_site", "at": Vector3(-66, 1.62, 128), "look": Vector3(-110, 9, 160)},
		{"id": "23_tunnel", "at": Vector3(77.19, 1.62, 214), "look": Vector3(64.11, 4, 262)},
		# сценки с транспортом (разбор Таркова и Ready or Not, prospekt_dressing.md § 7)
		{"id": "24_cordon_btr", "at": Vector3(-186, 1.62, -9.11), "look": Vector3(-203, 1.5, -24.54)},
		{"id": "25_bus_overturned", "at": Vector3(-96, 1.62, -2.04), "look": Vector3(-74, 1.5, -24.54)},
		{"id": "26_crash_taxi", "at": Vector3(-72, 1.62, 9.63), "look": Vector3(-58, 1.2, -6.76)},
		{"id": "27_bank_cash", "at": Vector3(-30, 1.62, -67.3), "look": Vector3(-20, 1.2, -83.3)},
		{"id": "28_cordon_police", "at": Vector3(57.6, 1.62, -27.08), "look": Vector3(93.3, 2, -49.3)},
		{"id": "29_roadworks", "at": Vector3(59.4, 1.62, 70), "look": Vector3(70.65, 1.5, 100)},
		{"id": "30_dps_post", "at": Vector3(50.32, 1.62, 128), "look": Vector3(72.65, 1.5, 108)},
		# редакция 4 (замечания владельца 2026-10-24)
		{"id": "31_bank_vault", "at": Vector3(-26.5, -1.6, -81.3), "look": Vector3(-34, -2.2, -73.3)},
		{"id": "32_dig_tunnel", "at": Vector3(-63, -5.68, -83.3), "look": Vector3(-43, -3.0, -75.3)},
		{"id": "33_bank_roof", "at": Vector3(-8, 13.9, -67.3), "look": Vector3(-30, 13.0, -89.3)},
		{"id": "34_square_playground", "at": Vector3(-2, 1.62, 143), "look": Vector3(-36, 1.5, 168)},
		{"id": "35_train_square", "at": Vector3(16, 1.62, 205), "look": Vector3(-6, 3.0, 240)},
		{"id": "36_bird_south", "at": Vector3(141.3, 110, 150), "look": Vector3(-20, 0, 200)},
		{"id": "37_supermarket_checkouts", "at": Vector3(-100, 1.62, 51), "look": Vector3(-138, 2.0, 56)},
		{"id": "38_pit_rows", "at": Vector3(-190, -5.68, -91.7), "look": Vector3(-150, -4.6, -91.7)},
		{"id": "39_monument", "at": Vector3(-26, 1.62, 50), "look": Vector3(-10, 3.0, 70)},
		{"id": "40_bird_bank", "at": Vector3(42.21, 60, -22.38), "look": Vector3(-30, 0, -81.3)},
		# редакция 5 (замечания владельца 2026-10-25)
		{"id": "41_tower_front", "at": Vector3(-44, 1.62, -2.04), "look": Vector3(-5, 8, 30)},
		{"id": "42_tower_shops_in", "at": Vector3(-32.5, 1.62, 22.5), "look": Vector3(-32.5, 1.4, 34)},
		{"id": "43_tower_courtyard", "at": Vector3(-36, 1.62, 60), "look": Vector3(4, 10, 32)},
		{"id": "44_station_front", "at": Vector3(-66, 1.62, 202.5), "look": Vector3(-116, 7, 222)},
		{"id": "45_station_hall", "at": Vector3(-116, 1.62, 216.5), "look": Vector3(-116, 5, 240)},
		{"id": "46_station_platform", "at": Vector3(-112, 9.2, 259.5), "look": Vector3(-140, 8.5, 262)},
		{"id": "47_site_pit", "at": Vector3(-96, 2.5, 160), "look": Vector3(-114, -3, 182)},
		{"id": "48_perimeter_north", "at": Vector3(-100, 1.62, -131.3), "look": Vector3(-60, 3, -142.3)},
		{"id": "49_parking_wrecks", "at": Vector3(-150, -5.68, -91.7), "look": Vector3(-120, -5.6, -91.7)},
		{"id": "51_dig_lights", "at": Vector3(-72, -5.68, -71.3), "look": Vector3(-50, -4.6, -77.3)},
		{"id": "52_bird_tower", "at": Vector3(-70, 70, 120), "look": Vector3(-5, 0, 60)},
		{"id": "53_bird_station", "at": Vector3(-40, 70, 170), "look": Vector3(-115, 0, 225)},
		# редакция 6 (владелец 2026-10-25): шесть путей и контактная сеть, провода в городе, спуски в паркинг в углах двора
		{"id": "54_rail_tracks", "at": Vector3(10, 8.3, 266), "look": Vector3(141.3, 10, 276)},
		{"id": "55_avenue_trolley", "at": Vector3(-185, 1.62, -42.58), "look": Vector3(-120, 6, -19.83)},
		{"id": "56_yard_ramp_w", "at": Vector3(-190, 1.62, -143.3), "look": Vector3(-208, 0, -131.3)},
		{"id": "57_yard_ramp_e", "at": Vector3(-64, 1.62, -150.3), "look": Vector3(-47, 0, -131.3)},
		{"id": "58_yard_lines", "at": Vector3(-130, 1.62, -129.3), "look": Vector3(-160, 7, -152.3)},
		{"id": "59_bird_rails", "at": Vector3(-40, 60, 220), "look": Vector3(40.42, 6, 275)},
		{"id": "60_bird_yard", "at": Vector3(-130, 70, -81.3), "look": Vector3(-130, 0, -136.3)},
		# модели Urban 95 вместо серых форм (2026-10-25)
		{"id": "61_models_cordon", "at": Vector3(-190, 1.62, -2.04), "look": Vector3(-206, 1.0, -33.97)},
		{"id": "62_models_lot", "at": Vector3(-150, 1.62, -69.3), "look": Vector3(-120, 0.8, -76.3)},
		{"id": "63_models_plaza", "at": Vector3(100.91, 1.62, 47.79), "look": Vector3(121.3, 2.0, -16.3)},
		{"id": "64_models_crossing", "at": Vector3(-140, 1.62, 16), "look": Vector3(-126, 2.5, -15.65)},
		# проспект вдвое шире (владелец 2026-11-07, вариант Б «магистраль»; docs/design/prospekt_map.md §20)
		{"id": "97_bank_lane", "at": Vector3(25.5, 1.62, -55.0), "look": Vector3(26.0, 2.0, -130.0)},
		{"id": "98_motor_pool", "at": Vector3(104.0, 1.62, 40.0), "look": Vector3(150.0, 2.0, 40.0)},
		{"id": "99_widen_bird", "at": Vector3(-120, 70, 60), "look": Vector3(-80, 0, -20)},
		{"id": "100_widen_across", "at": Vector3(-95, 1.62, 7.35), "look": Vector3(-60, 5, -56.3)}]
	# свои кадры (несколько — через «;») или имена готовых кадров вместо всего списка
	var picked: Array[Dictionary] = []
	for spec: String in OS.get_environment("PROSPEKT_VIEW").split(";", false):
		var custom: PackedStringArray = spec.split(":")
		if custom.size() == 7:
			picked.append({"id": custom[0], "at": Vector3(custom[1].to_float(), custom[2].to_float(), custom[3].to_float()),
				"look": Vector3(custom[4].to_float(), custom[5].to_float(), custom[6].to_float())})
		else:
			for view: Dictionary in views:
				if String(view.id) == spec:
					picked.append(view)
	if not picked.is_empty():
		views = picked
	if OS.get_environment("PROSPEKT_LIGHT") != "":
		await _light_stand(camera, views)
		get_tree().quit()
		return
	for view: Dictionary in views:
		camera.global_position = view.at
		camera.look_at(view.look, Vector3.UP)
		camera.fov = 62.0 if String(view.id).ends_with("overview") or String(view.id).ends_with("center") else Settings.fps_fov_v()
		await _frames(60)
		await RenderingServer.frame_post_draw
		var image: Image = get_viewport().get_texture().get_image()
		var path: String = output_dir.path_join(String(view.id) + ".png")
		print("prospekt_study: снимок ", path, " ошибка=", image.save_png(path))
	camera.position = Vector3(0, Balance.ADS_EYE.stand, 0)
	camera.rotation = Vector3.ZERO
	_jump_to(START)
	hud.show()
	map.show()
	map.queue_redraw()
	await _frames(10)
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(output_dir.path_join("50_map.png"))
	get_tree().quit()


## Стенд света (tools/prospekt_light_variants.gd): те же кадры в каждом варианте → <вариант>__<кадр>.png.
## PROSPEKT_LIGHT=all_variants — все по порядку, иначе имена через «,». Подписи мест на карте скрыты.
func _light_stand(camera: Camera3D, views: Array[Dictionary]) -> void:
	var variants: Array[String] = LightVariants.ORDER.duplicate()
	if OS.get_environment("PROSPEKT_LIGHT") != "all_variants":
		variants.assign(Array(OS.get_environment("PROSPEKT_LIGHT").split(",", false)))
	for label: Node in world.find_children("*", "Label3D", true, false):
		(label as Label3D).hide()
	var we: WorldEnvironment = world.get_node("WorldEnvironment") as WorldEnvironment
	var sun: DirectionalLight3D = world.get_node("EveningSun") as DirectionalLight3D
	var base_env: Environment = we.environment.duplicate(true) as Environment
	var base_sun: Array = [sun.light_energy, sun.light_color]
	for variant: String in variants:
		we.environment = base_env.duplicate(true) as Environment
		sun.light_energy = float(base_sun[0])
		sun.light_color = base_sun[1] as Color
		var overlay: CanvasLayer = LightVariants.apply(variant, we.environment, sun, self)
		var settle: int = LightVariants.settle_frames(variant)
		for view: Dictionary in views:
			camera.global_position = view.at
			camera.look_at(view.look, Vector3.UP)
			camera.fov = 62.0 if String(view.id).ends_with("overview") else Settings.fps_fov_v()
			await _frames(settle)
			await RenderingServer.frame_post_draw
			var path: String = output_dir.path_join("%s__%s.png" % [variant, String(view.id)])
			print("prospekt_study: свет ", variant, " снимок ", path, " ошибка=", get_viewport().get_texture().get_image().save_png(path))
		if overlay:
			overlay.queue_free()


## План (M): покрытия, постройки, укрытия, появления, выходы, пешеход.
class PlanMap extends Control:
	var plan: Dictionary
	var walker: Node3D

	func _draw() -> void:
		if plan.is_empty():
			return
		var b: Array = plan.bounds
		var world_rect: Rect2 = Rect2(float(b[0]), float(b[1]), float(b[2]) - float(b[0]), float(b[3]) - float(b[1]))
		var k: float = minf((size.x - 80.0) / world_rect.size.x, (size.y - 80.0) / world_rect.size.y)
		var origin: Vector2 = Vector2(40.0, 40.0)
		draw_rect(Rect2(Vector2.ZERO, size), Color(0.05, 0.06, 0.06, 0.92))
		draw_rect(Rect2(origin, world_rect.size * k), Color("3a3c37"))
		for s: Dictionary in plan.surfaces:
			var r: Array = s.rect
			var col: Color = {"road": Color("55595b"), "walk": Color("8a8577"), "grass": Color("4e5e3a"), "court": Color("5e6d55"), "parking": Color("63665f")}.get(String(s.mat), Color("6f6f6f"))
			draw_rect(Rect2(origin + (Vector2(float(r[0]), float(r[1])) - world_rect.position) * k, Vector2(float(r[2]) - float(r[0]), float(r[3]) - float(r[1])) * k), col)
		for bd: Dictionary in plan.buildings:
			var at: Array = bd.at
			var sz: Array = bd.size
			var c: Vector2 = origin + (Vector2(float(at[0]), float(at[1])) - world_rect.position) * k
			var half: Vector2 = Vector2(float(sz[0]), float(sz[1])) * 0.5 * k
			var yaw: float = deg_to_rad(float(bd.yaw))
			var pts: PackedVector2Array = PackedVector2Array()
			for corner: Vector2 in [Vector2(-half.x, -half.y), Vector2(half.x, -half.y), Vector2(half.x, half.y), Vector2(-half.x, half.y)]:
				pts.append(c + corner.rotated(yaw))
			var col: Color = Color("a56b4e") if String(bd.get("interior", "")) != "" or String(bd.kind) == "apartments" else Color("8c8984")
			if String(bd.kind) == "canopy":
				col = Color(0.6, 0.75, 0.85, 0.5)
			draw_colored_polygon(pts, col)
		for c: Array in (plan.filler as Dictionary).get("cover", []):
			draw_circle(origin + (Vector2(float(c[0]), float(c[1])) - world_rect.position) * k, 1.5, Color("2b2e33"))
		for s: Dictionary in plan.spawns:
			var at: Array = s.at
			draw_circle(origin + (Vector2(float(at[0]), float(at[1])) - world_rect.position) * k, 5.0, Color("2d6cc0"))
		for e: Dictionary in plan.exits:
			var at: Array = e.at
			draw_circle(origin + (Vector2(float(at[0]), float(at[1])) - world_rect.position) * k, 5.0, Color("1e9e4a") if bool(e.always) else Color("d68a00"))
		for loc: Dictionary in plan.locations:
			var at: Array = loc.at
			draw_string(ThemeDB.fallback_font, origin + (Vector2(float(at[0]), float(at[1])) - world_rect.position) * k + Vector2(6, 4),
				"%d %s" % [int(loc.id), String(loc.label)], HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color("f1ead8"))
		if walker:
			var p: Vector2 = origin + (Vector2(walker.global_position.x, walker.global_position.z) - world_rect.position) * k
			draw_circle(p, 6.0, Color("f0d070"))
			var dir: Vector2 = Vector2(-sin(walker.rotation.y), -cos(walker.rotation.y))
			draw_line(p, p + dir * 16.0, Color("f0d070"), 2.0)
		draw_string(ThemeDB.fallback_font, Vector2(48, size.y - 20), "«Проспект» · север вверху · синие — появление, зелёные — выходы, оранжевый — условный · M — закрыть", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color("e0e3d2"))
