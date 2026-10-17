extends Node3D
## Прогулка по серому черновику территории ТЦ (scenes/levels/mall_study.tscn) в настоящем масштабе.
## Не рейд: без добычи, ИИ, эвакуации и сети; основной профиль не трогается.
##   прогулка:  tools/godot.cmd --windowed --resolution 1600x900 res://tools/mall_study.tscn
##   проверка:  tools/godot.cmd --headless res://tools/mall_study.tscn -- verify
##   снимки:    tools/godot.cmd --windowed --resolution 1600x900 res://tools/mall_study.tscn -- shots
## Папка отчёта и снимков — MALL_STUDY_OUTPUT (иначе docs/screens/mall_study).

const Walker = preload("res://src/blockout/study_walker.gd")
const MallLandscape = preload("res://src/blockout/mall_landscape.gd")
const PlanMap = preload("res://src/blockout/mall_study_map.gd")
const LEVEL: String = "res://scenes/levels/mall_study.tscn"
## С чего начинается прогулка — главная площадь.
const START: int = 2

var world: Node3D
var landscape: MallLandscape
var walker: Walker
var plan: Dictionary
var hud: CanvasLayer
var title: Label
var status: Label
## Мышь не захвачена (Esc, игра во вкладке «Game» редактора) — как вернуть обзор.
var hint: Label
var map: PlanMap
var output_dir: String
var results: Array[Dictionary] = []
var mode: String = "walk"
var current: int = START


func _enter_tree() -> void:
	if world == null:
		Profile.use_file("user://profile_mall_study_test.json", true)


func _ready() -> void:
	DisplayServer.window_set_title("RING · ТЦ «РИНГ» · территория · черновик 1:1")
	# Esc здесь освобождает мышь; общее меню и сюжет в исследовании не нужны
	get_node("/root/Pause").set_process_input(false)
	get_node("/root/Quests").process_mode = Node.PROCESS_MODE_DISABLED
	get_node("/root/Contracts").process_mode = Node.PROCESS_MODE_DISABLED
	for arg: String in OS.get_cmdline_user_args():
		if arg in ["verify", "shots"]:
			mode = arg
	output_dir = OS.get_environment("MALL_STUDY_OUTPUT")
	if output_dir.is_empty():
		output_dir = ProjectSettings.globalize_path("res://docs/screens/mall_study")
	if world == null:
		world = (load(LEVEL) as PackedScene).instantiate() as Node3D
		add_child(world)
	landscape = world.get_node("Landscape") as MallLandscape
	plan = landscape.plan
	walker = Walker.new()
	walker.name = "StudyWalker"
	add_child(walker)
	_ui()
	# здание собирается при запуске — ждём его коллизию, потом ставим пешехода
	await _frames(4)
	_jump_to(START)
	if mode == "walk":
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		print("mall_study: прогулка; WASD, Shift, M — план, 1–9/0 и N/B — места, F — полёт, Esc — мышь")
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
	shade.position = Vector2(18, 18)
	shade.size = Vector2(680, 82)
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
	controls.text = "WASD — идти   Shift — бежать   Space — прыжок   C — присесть\nM — план   1–9, 0 — места 1–10   N / B — следующее / прошлое из 15   F — полёт   R — сначала\nEsc — освободить мышь · щелчок — продолжить · ПКМ — осмотр без захвата · это черновик для замера, не рейд"
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
	map.plan = plan
	map.walker = walker
	map.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	map.hide()
	root.add_child(map)


func _process(_delta: float) -> void:
	if not is_instance_valid(walker) or plan.is_empty():
		return
	var nearest: Dictionary = plan.locations[0]
	var distance: float = INF
	for loc: Dictionary in plan.locations:
		var p: Array = loc.at
		var d: float = Vector2(walker.global_position.x - float(p[0]), walker.global_position.z - float(p[1])).length()
		if d < distance:
			distance = d
			nearest = loc
	title.text = "%d · %s  |  ЧЕРНОВИК 1:1" % [int(nearest.id), String(nearest.label)]
	var speed_m: float = Vector2(walker.velocity.x, walker.velocity.z).length()
	var to_mall: float = maxf(0.0, Vector2(walker.global_position.x, walker.global_position.z).length() - float((plan.mall as Dictionary).r))
	status.text = "%s · %.2f м/с · путь %.0f м · %d:%02d · высота %.1f м · до ТЦ %.0f м · %d к/с" % [
		"ПОЛЁТ" if walker.flight else "ПЕШКОМ", speed_m, walker.travelled_m, int(walker.walking_sec) / 60,
		int(walker.walking_sec) % 60, walker.global_position.y, to_mall, Engine.get_frames_per_second()]
	if map.visible:
		map.queue_redraw()
	hint.visible = mode == "walk" and not map.visible and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED \
		and not Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT)


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
	var target: int = 0
	if key >= KEY_1 and key <= KEY_9:
		target = key - KEY_0
	elif key == KEY_0:
		target = 10
	elif key == KEY_N:
		target = current % plan.locations.size() + 1
	elif key == KEY_B:
		target = (current + plan.locations.size() - 2) % plan.locations.size() + 1
	if target > 0:
		_jump_to(target)
		map.hide()
		walker.blocked_input = false
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	if key == KEY_R:
		_jump_to(START)
		walker.travelled_m = 0.0
		walker.walking_sec = 0.0


func _jump_to(index: int) -> void:
	current = index
	var loc: Dictionary = plan.locations[index - 1]
	var p: Array = loc.spawn
	var target: Array = loc.look
	var at: Vector3 = Vector3(float(p[0]), landscape.ground(float(p[0]), float(p[1])) + 0.08, float(p[1]))
	walker.teleport(at, Vector3(float(target[0]), at.y, float(target[1])))


func _frames(count: int) -> void:
	for i: int in range(count):
		await get_tree().physics_frame


func _check(label: String, passed: bool, details: Dictionary = {}) -> void:
	results.append({"check": label, "pass": passed, "details": details})
	print("mall_study: %s · %s %s" % ["PASS" if passed else "FAIL", label, JSON.stringify(details)])


func _ray_y(x: float, z: float) -> float:
	var from: Vector3 = Vector3(x, 40.0, z)
	var hit: Dictionary = walker.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(from, from - Vector3.UP * 80.0, 1))
	return (hit.position as Vector3).y if not hit.is_empty() else INF


func _verify() -> void:
	_check("15 участков схемы, подходы A–D и галерея автостанции", plan.locations.size() == 15 and plan.probe_routes.size() == 5, {"area_m2": plan.boundary_area_m2})
	_check("Габариты и скорость из Balance", is_equal_approx((walker.capsule.shape as CapsuleShape3D).height, Balance.STANCE_HEIGHT.stand),
		{"walk_m_s": Balance.PLAYER_WALK_SPEED, "sprint_m_s": Balance.PLAYER_SPRINT_SPEED})
	var sector: Node = world.get_node_or_null("Mall/Sector")
	var doors: int = sector.find_children("*", "Door", true, false).size() if sector else 0
	_check("В центре — серый 1-й этаж ТЦ Ø200 (без своего забора)", sector != null and doors > 50, {"doors": doors})
	# рельеф: уровни схемы
	var t: Dictionary = plan.terraces
	var levels: Array[float] = [_ray_y(0.0 + 30.0, 160.0), _ray_y(30.0, 190.0), _ray_y(30.0, 225.0)]
	_check("Южная парковка террасами 0 / −2 / −4 м", absf(levels[0]) < 0.3 and absf(levels[1] + 2.0) < 0.3 and absf(levels[2] + 4.0) < 0.3, {"y": levels})
	var y: Dictionary = plan.yard
	var yard_at: Vector2 = MallLandscape.polar(float(y.ramp_a) - 12.0, 180.0)
	var yard_y: float = _ray_y(yard_at.x, yard_at.y)
	_check("Разгрузочный двор в выемке −4 м", absf(yard_y - float(y.floor)) < 0.3, {"y": yard_y})
	var north_y: float = _ray_y(-200.0, -300.0)
	var hw: Dictionary = plan.highway
	# по полосе, а не по оси: посередине трассы — бетонный разделитель
	var hw_y: float = _ray_y(150.0, float(hw.z) + 6.0)
	_check("Север выше, трасса ниже всего", north_y > 2.5 and absf(hw_y - float(hw.y)) < 0.3, {"north_y": north_y, "highway_y": hw_y})
	# рельеф: горка, речка, утёсы (tools/mall_study_relief.py)
	var relief: Dictionary = plan.get("relief", {}) as Dictionary
	var hill: Array = (relief.get("hills", []) as Array)[0]
	var top_y: float = _ray_y(float(hill[0]), float(hill[1]))
	var hill_rise: float = top_y - landscape.base_height(float(hill[0]), float(hill[1]))
	_check("Западная горка за речкой: вершина выше окрестной земли", hill_rise > 6.0, {"rise_m": snappedf(hill_rise, 0.1)})
	var river: Dictionary = relief.get("river", {}) as Dictionary
	var rpts: PackedVector2Array = MallLandscape.poly(river.get("points", []))
	var mid: Vector2 = (rpts[4] + rpts[5]) * 0.5
	var flow: Vector2 = (rpts[5] - rpts[4]).normalized()
	var bed_y: float = _ray_y(mid.x, mid.y)
	var bank_y: float = _ray_y(mid.x - flow.y * 24.0, mid.y + flow.x * 24.0)
	var water: bool = not landscape.find_children("Mesh_water", "", true, false).is_empty()
	_check("Речка: русло ниже берегов, вода есть", water and bank_y - bed_y > 1.5, {"bank_m": snappedf(bank_y - bed_y, 0.1)})
	for cliff: Dictionary in relief.get("cliffs", []):
		var edge: PackedVector2Array = MallLandscape.poly(cliff.points)
		var c: Vector2 = edge[1]
		var along: Vector2 = (edge[2] - edge[0]).normalized()
		var up: Vector2 = Vector2(-along.y, along.x) * float(cliff.side)
		var drop: float = _ray_y(c.x + up.x * 4.0, c.y + up.y * 4.0) - _ray_y(c.x - up.x * 6.0, c.y - up.y * 6.0)
		_check("Утёс «%s»: обрыв не меньше 4 м" % String(cliff.name), drop > 4.0, {"drop_m": snappedf(drop, 0.1)})
	for loc: Dictionary in plan.locations:
		_jump_to(int(loc.id))
		await _frames(8)
		var query: PhysicsShapeQueryParameters3D = PhysicsShapeQueryParameters3D.new()
		query.shape = walker.capsule.shape
		query.transform = Transform3D(Basis.IDENTITY, walker.global_position + Vector3.UP * (Balance.STANCE_HEIGHT.stand * 0.5 + 0.04))
		query.collision_mask = 1
		var clear: bool = walker.get_world_3d().direct_space_state.intersect_shape(query, 1).is_empty()
		_check("Безопасная точка: " + String(loc.label), clear and walker.is_on_floor(), {"position": str(walker.global_position)})
	# подходы схемы: от края карты до здания пешком (капсула идёт по физике)
	for route: Dictionary in plan.probe_routes:
		var path: Array[Vector3] = []
		for p: Array in route.points:
			path.append(Vector3(float(p[0]), landscape.ground(float(p[0]), float(p[1])) + 0.04, float(p[1])))
		var before: float = walker.travelled_m
		var t0: float = walker.walking_sec
		var passed: bool = await _walk_path(path, true)
		_check("Подход " + String(route.id), passed, {"walked_m": snappedf(walker.travelled_m - before, 0.1),
			"sprint_sec": snappedf(walker.walking_sec - t0, 0.1), "position": str(walker.global_position)})
	# наполнение пустых мест (tools/mall_study_filler.py): пачки, коллизия укрытий, ЛЭП, теплотрасса, истории
	var filler_node: Node3D = world.get_node_or_null("Filler") as Node3D
	var fstats: Dictionary = filler_node.get_meta("stats", {}) as Dictionary if filler_node else {}
	var filler: Dictionary = plan.get("filler", {}) as Dictionary
	_check("Наполнение: укрытия, природа, ЛЭП, теплотрасса, истории", int(fstats.get("instances", 0)) > 5000
		and (filler.get("stories", []) as Array).size() >= 10 and filler_node.find_children("Mesh_steel", "", true, false).size() > 0, fstats)
	# ритм: на подходах нет открытого куска длиннее 60 м, где до укрытия дальше 15 м
	for route: Dictionary in plan.probe_routes:
		var longest: float = _open_stretch(route.points)
		_check("Подход %s: открытый кусок не длиннее 60 м" % String(route.id), longest <= 60.0, {"longest_open_m": snappedf(longest, 1.0)})
	# речку пешком: вброд на колее и по мостику у АЗС (мост на западной дороге проходит подход B)
	for ford: Dictionary in river.get("fords", []):
		var across: Vector2 = _across_river(rpts, Vector2(float(ford.at[0]), float(ford.at[1])))
		var at: Vector2 = Vector2(float(ford.at[0]), float(ford.at[1]))
		var ford_path: Array[Vector3] = []
		for q: Vector2 in [at - across * 18.0, at + across * 18.0]:
			ford_path.append(Vector3(q.x, landscape.ground(q.x, q.y) + 0.04, q.y))
		var waded: bool = await _walk_path(ford_path, false)
		_check("Брод на колее: перейти речку пешком", waded, {"position": str(walker.global_position)})
	for bridge: Dictionary in river.get("bridges", []):
		if String(bridge.kind) != "foot":
			continue
		var bat: Vector2 = Vector2(float(bridge.at[0]), float(bridge.at[1]))
		var bacross: Vector2 = _across_river(rpts, bat)
		var bridge_path: Array[Vector3] = []
		for q: Vector2 in [bat + bacross * (float(bridge.half_left) + 5.0), bat - bacross * (float(bridge.half_right) + 5.0)]:
			bridge_path.append(Vector3(q.x, landscape.ground(q.x, q.y) + 0.04, q.y))
		var crossed: bool = await _walk_path(bridge_path, false)
		_check("Пешеходный мостик у АЗС: через речку по настилу", crossed and walker.global_position.y > float(bridge.deck) - 1.5,
			{"position": str(walker.global_position)})
	# паркинг: лестница на 2-й ярус и мост к фасаду ТЦ на высоте 2-го этажа
	var garage: Node3D = world.get_node("Garage/Parking_Garage") as Node3D
	var story: float = float(garage.get("story_height"))
	var origin: Vector2 = garage.get("stair_origin") as Vector2
	var gpath: Array[Vector3] = [garage.to_global(Vector3(origin.x - 1.05, 0.14, 3.45))]
	for level: int in range(2):
		var ly: float = 0.1 + float(level) * story
		gpath.append(garage.to_global(Vector3(origin.x - 1.05, ly + story * 0.5, -3.45)))
		gpath.append(garage.to_global(Vector3(origin.x + 1.05, ly + story * 0.5, -3.45)))
		gpath.append(garage.to_global(Vector3(origin.x + 1.05, ly + story, 3.45)))
		gpath.append(garage.to_global(Vector3(origin.x - 1.05, ly + story, 3.45)))
	# с площадки — в сторону на перекрытие яруса: прямо вперёд — снова марш вверх, под плиту следующего
	gpath.append(garage.to_global(Vector3(origin.x - 3.2, 0.1 + 2.0 * story, 3.45)))
	var gb: Dictionary = plan.garage_bridge
	var bridge_y: float = float(gb.y)
	gpath.append(Vector3(float(gb.from[0]) + 2.0, bridge_y, float(gb.from[1])))
	gpath.append(Vector3(float(gb.to[0]) + 2.5, bridge_y, float(gb.to[1])))
	var gpass: bool = await _walk_path(gpath, false)
	_check("Паркинг → 2-й ярус → мост к фасаду на высоте 2-го этажа", gpass and absf(walker.global_position.y - bridge_y) < 0.4, {"y": walker.global_position.y})
	# пешеходный мост через трассу: с севера по лестнице, по настилу, на юг
	var fb: Dictionary = plan.foot_bridge
	var fx: float = float(fb.x)
	var z0: float = float(fb.z[0]) + 1.6
	var z1: float = float(fb.z[1]) - 1.6
	var fpath: Array[Vector3] = [Vector3(fx - 24.0, landscape.ground(fx - 24.0, z0) + 0.04, z0), Vector3(fx - 1.0, float(fb.y), z0),
		Vector3(fx - 1.0, float(fb.y), z1), Vector3(fx - 24.0, landscape.ground(fx - 24.0, z1) + 0.04, z1)]
	var fpass: bool = await _walk_path(fpath, false)
	_check("Пешеходный мост через трассу", fpass, {"position": str(walker.global_position)})
	# двор: с платформы доков по лестнице наверх, к пожарному проезду
	var dock: Array = y.dock
	var ds: Dictionary = landscape.dock_stair()
	var yard_low: Vector2 = MallLandscape.polar(float(y.a[0]) + 12.0, float(dock[1]) + 6.0)
	var dock_low: Vector2 = MallLandscape.polar(float(y.a[0]) + 12.0, float(dock[1]) - 1.0)
	var s0: Vector2 = ds.s0
	var s1: Vector2 = ds.s1
	var landing: Vector2 = ds.landing
	var top: Vector2 = ds.top
	# к началу марша — чуть раньше его низа, наверх — до самой верхней ступени
	var before: Vector2 = s0 + (s0 - s1).normalized() * 0.6
	var dpath: Array[Vector3] = [Vector3(yard_low.x, float(y.floor) + 0.04, yard_low.y), Vector3(dock_low.x, float(y.dock_top), dock_low.y),
		Vector3(before.x, float(y.dock_top), before.y), Vector3(s1.x, 0.0, s1.y), Vector3(landing.x, 0.0, landing.y), Vector3(top.x, 0.04, top.y)]
	var dpass: bool = await _walk_path(dpath, false)
	_check("Двор → платформа доков → лестница к пожарному проезду", dpass and walker.global_position.y > -0.4, {"position": str(walker.global_position)})
	var visual_count: int = 0
	var triangle_count: int = 0
	for mesh: Node in world.find_children("*", "MeshInstance3D", true, false):
		var visual: MeshInstance3D = mesh as MeshInstance3D
		visual_count += 1
		if visual.mesh:
			triangle_count += visual.mesh.get_faces().size() / 3
	var fails: int = 0
	for result: Dictionary in results:
		if not bool(result["pass"]):
			fails += 1
	DirAccess.make_dir_recursive_absolute(output_dir)
	var report: Dictionary = {"scene": LEVEL, "checks": results, "fails": fails, "mesh_batches": visual_count,
		"mesh_triangles_excluding_multimesh": triangle_count, "buildings": plan.buildings.size(),
		"limitations": ["Добыча, ИИ, эвакуация и сеть этим черновиком не проверяются",
			"Условные серые формы и цвета; нет итоговых PBR-ассетов", "Скорости без выносливости, снаряжения и перегруза"]}
	var file: FileAccess = FileAccess.open(output_dir.path_join("validation.json"), FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "\t"))
	file.close()
	print("mall_study: DONE checks=%d fails=%d" % [results.size(), fails])
	get_tree().quit(fails)


## Поперёк речки у точки: влево от хода русла (как «слева» у берегов в данных рельефа).
func _across_river(line: PackedVector2Array, p: Vector2) -> Vector2:
	var best: float = INF
	var dir: Vector2 = Vector2.RIGHT
	for i: int in range(line.size() - 1):
		var d: float = p.distance_to(Geometry2D.get_closest_point_to_segment(p, line[i], line[i + 1]))
		if d < best:
			best = d
			dir = (line[i + 1] - line[i]).normalized()
	return Vector2(-dir.y, dir.x)


## Самый длинный кусок ломаной (шаг 2 м), на котором до ближайшего укрытия дальше 15 м: укрытия наполнения,
## машины, стенки и фонтан рельефа, постройки, стена ТЦ.
func _open_stretch(points: Array) -> float:
	var spots: PackedVector2Array = landscape.cover_spots.duplicate()
	for c: Array in (plan.get("filler", {}) as Dictionary).get("cover", []):
		spots.append(Vector2(float(c[0]), float(c[1])))
	var line: PackedVector2Array = MallLandscape.poly(points)
	var longest: float = 0.0
	var run: float = 0.0
	for i: int in range(line.size() - 1):
		var steps: int = maxi(1, ceili(line[i].distance_to(line[i + 1]) / 2.0))
		var step_m: float = line[i].distance_to(line[i + 1]) / float(steps)
		for k: int in range(steps):
			var p: Vector2 = line[i].lerp(line[i + 1], float(k) / float(steps))
			var covered: bool = p.length() < float((plan.mall as Dictionary).r) + 15.0
			for b: Dictionary in plan.buildings:
				if covered:
					break
				var c: Array = b.at
				var span: Array = b.size
				var local: Vector2 = (p - Vector2(float(c[0]), float(c[1]))).rotated(deg_to_rad(float(b.yaw)))
				var outside: Vector2 = (local.abs() - Vector2(float(span[0]), float(span[1])) * 0.5).max(Vector2.ZERO)
				covered = outside.length() < 15.0
			for q: Vector2 in spots:
				if covered:
					break
				covered = p.distance_squared_to(q) < 225.0
			run = 0.0 if covered else run + step_m
			longest = maxf(longest, run)
	return longest


func _walk_path(path: Array[Vector3], sprint: bool) -> bool:
	walker.probe_direction = Vector3.ZERO
	walker.probe_sprint = sprint
	walker.teleport(path[0], path[0] + Vector3.FORWARD)
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
			if delta.length() < 0.2:
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
			# упёрся (ствол, машина) — шаг вбок, как обошёл бы игрок; стенку так не пройти
			if stalled > 45:
				for k: int in range(25):
					walker.probe_direction = delta.normalized().cross(Vector3.UP) * side
					await get_tree().physics_frame
				side = -side
				stalled = 0
				previous = INF
			walker.probe_direction = delta.normalized()
			await get_tree().physics_frame
		walker.probe_direction = Vector3.ZERO
		walker.velocity.x = 0.0
		walker.velocity.z = 0.0
		if not reached:
			print("mall_study: застрял в %s на пути к %s" % [str(walker.global_position), str(target)])
			return false
	return true


func _shots() -> void:
	walker.set_physics_process(false)
	hud.hide()
	DirAccess.make_dir_recursive_absolute(output_dir)
	var views: Array[Dictionary] = [
		{"id": "01_overview", "at": Vector3(0, 720, 430), "look": Vector3(0, 0, -10)},
		{"id": "02_plaza_eye", "at": Vector3(22, 1.62, 150), "look": Vector3(0, 4, 100)},
		{"id": "03_terraces", "at": Vector3(-150, 18, 290), "look": Vector3(-60, -2, 190)},
		{"id": "04_yard", "at": Vector3(220, 24, -220), "look": Vector3(110, -4, -115)},
		{"id": "05_gas_checkpoint", "at": Vector3(-180, 30, -120), "look": Vector3(-300, 0, -110)},
		{"id": "06_tech_garage", "at": Vector3(330, 40, 80), "look": Vector3(220, 5, -60)},
		{"id": "07_gallery_stairs", "at": Vector3(-104, 0, 196), "look": Vector3(-82, -2, 185.5)},
		{"id": "08_construction", "at": Vector3(30, 26, -228), "look": Vector3(40, 0, -292)},
		{"id": "09_field_eye", "at": Vector3(-262, 1.7, 40), "look": Vector3(-300, 1.0, 200)},
		{"id": "10_convoy", "at": Vector3(-270, 16, 190), "look": Vector3(-320, 0, 238)},
		{"id": "11_heat_main", "at": Vector3(215, 7, -18), "look": Vector3(150, 1, -46)},
		{"id": "12_garages", "at": Vector3(298, 9, 92), "look": Vector3(332, 1, 55)},
		{"id": "13_highway", "at": Vector3(165, 9, 268), "look": Vector3(122, 0, 298)},
		{"id": "15_river_bridge", "at": Vector3(-268, 8, 8), "look": Vector3(-295, -1, -22)},
		{"id": "16_cliff_river", "at": Vector3(-290, 6, 150), "look": Vector3(-345, 2, 150)},
		{"id": "17_west_hill_view", "at": Vector3(-385, 11.5, 150), "look": Vector3(0, 5, 0)},
		{"id": "18_pond_cliff", "at": Vector3(-110, 4, -250), "look": Vector3(-110, 3, -326)},
		{"id": "19_ford", "at": Vector3(-308, 7, 248), "look": Vector3(-331, -2, 227)},
		{"id": "20_forest_eye", "at": Vector3(-372, 9.7, 160), "look": Vector3(-300, 6, 150)},
		# вторая очередь (владелец, 2026-10-17): галерея с переходом, аллея к площади, перекрёсток, уплотнение, гора
		{"id": "22_gallery_crossing", "at": Vector3(-70, 14, 290), "look": Vector3(-115, 0, 225)},
		{"id": "23_alley_eye", "at": Vector3(3, 1.7, 236), "look": Vector3(0, 3, 150)},
		{"id": "24_junction", "at": Vector3(205, 18, -205), "look": Vector3(150, -4, -140)},
		{"id": "25_east_field", "at": Vector3(250, 30, 160), "look": Vector3(320, 0, 80)},
		{"id": "26_dachas_kpp", "at": Vector3(-320, 22, 60), "look": Vector3(-400, 0, 0)},
		{"id": "27_mountain", "at": Vector3(-300, 30, -170), "look": Vector3(-400, 10, -250)},
		# поля, сценки (tools/mall_study_scenery.py): высокая трава с уровня глаз, пшеница с трактором, сбитый вертолёт
		{"id": "28_meadow_eye", "at": Vector3(300, 1.7, 110), "look": Vector3(300, 1, 170)},
		{"id": "29_wheat", "at": Vector3(235, 12, -228), "look": Vector3(285, 0, -275)},
		{"id": "30_heli", "at": Vector3(255, 9, 135), "look": Vector3(288, 1, 168)}]
	# свои кадры вместо набора: MALL_STUDY_VIEW=имя:x:y:z:куда_x:куда_y:куда_z[;имя:…] (без плана)
	var custom_views: Array[Dictionary] = []
	for spec: String in OS.get_environment("MALL_STUDY_VIEW").split(";", false):
		var custom: PackedStringArray = spec.split(":")
		if custom.size() == 7:
			custom_views.append({"id": custom[0], "at": Vector3(custom[1].to_float(), custom[2].to_float(), custom[3].to_float()),
				"look": Vector3(custom[4].to_float(), custom[5].to_float(), custom[6].to_float())})
	if not custom_views.is_empty():
		views = custom_views
	for view: Dictionary in views:
		var environment: Environment = (world.get_node("WorldEnvironment") as WorldEnvironment).environment
		environment.fog_enabled = view.id != "01_overview"
		walker.camera.global_position = view.at
		walker.camera.look_at(view.look, Vector3.UP)
		walker.camera.fov = 62.0 if view.id == "01_overview" else Settings.fps_fov_v()
		await _frames(20)
		await RenderingServer.frame_post_draw
		var image: Image = get_viewport().get_texture().get_image()
		var path: String = output_dir.path_join(String(view.id) + ".png")
		print("mall_study: снимок ", path, " ошибка=", image.save_png(path))
	if not custom_views.is_empty():
		get_tree().quit()
		return
	walker.camera.position = Vector3(0, Balance.ADS_EYE.stand, 0)
	walker.camera.rotation = Vector3.ZERO
	_jump_to(START)
	hud.show()
	map.show()
	map.queue_redraw()
	await _frames(10)
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(output_dir.path_join("21_map.png"))
	get_tree().quit()
