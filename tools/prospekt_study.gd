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
	_check("Открытые здания собраны: кофейня, цветы, аптека, одежда, пекарня, подъезд, «Ярус», минимаркет",
		halls >= 8, {"enterable": open_kinds})
	var filler: Node = world.get_node_or_null("Filler")
	var stats: Dictionary = filler.get_meta("stats", {}) if filler else {}
	_check("Наполнение: машины, ларьки, ограждения, фонари — больше 300 экземпляров", int(stats.get("instances", 0)) > 300, stats)
	_check("Габариты и скорость из Balance", is_equal_approx(((walker.get("capsule") as CollisionShape3D).shape as CapsuleShape3D).height, Balance.STANCE_HEIGHT.stand),
		{"walk_m_s": Balance.PLAYER_WALK_SPEED, "sprint_m_s": Balance.PLAYER_SPRINT_SPEED})
	# уровни: паркинг −1 под плитой двора, переход под дорогой
	var yard_y: float = _ray_y(-60.0, -60.0)
	var pit_y: float = _ray_y(-60.0, -60.0, -1.0, 6.0)
	_check("Паркинг −1: плита двора на нуле, пол на −3,2", absf(yard_y) < 0.2 and absf(pit_y + 3.2) < 0.2, {"yard_y": yard_y, "pit_y": pit_y})
	var road_y: float = _ray_y(-44.0, 0.0)
	var tunnel_y: float = _ray_y(-44.0, 0.0, -0.6, 6.0)
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
		if route.has("min_y"):
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
	var blocked: bool = not await _walk_path([Vector3(-110.0, 0.1, 0.0), Vector3(-126.0, 0.1, 0.0)], true)
	_check("Кордон: плиты через проспект не пройти", blocked and walker.global_position.x > -121.5, {"x": walker.global_position.x})
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
		{"id": "01_overview", "at": Vector3(-10, 300, 170), "look": Vector3(-10, 0, 0)},
		{"id": "02_cordon_eye", "at": Vector3(-104, 1.62, 0), "look": Vector3(-60, 2, -8)},
		{"id": "03_coffee_eye", "at": Vector3(-92, 1.62, -11), "look": Vector3(-92, 1.5, -22)},
		{"id": "04_avenue_east", "at": Vector3(-70, 1.62, -12), "look": Vector3(40, 2, -6)},
		{"id": "05_underpass", "at": Vector3(-36, 1.62, -9.5), "look": Vector3(-46, -2.5, -13)},
		{"id": "06_tunnel_eye", "at": Vector3(-44, -1.7, -8), "look": Vector3(-44, -2, 12)},
		{"id": "07_parking_lot", "at": Vector3(-44, 1.62, 18), "look": Vector3(-20, 2, 56)},
		{"id": "08_supermarket_hall", "at": Vector3(-26, 1.62, 58), "look": Vector3(-20, 1.5, 90)},
		{"id": "09_dock_yard", "at": Vector3(-20, 1.62, 97), "look": Vector3(20, 1.5, 99)},
		{"id": "10_yard_zhk", "at": Vector3(-20, 1.62, -78), "look": Vector3(-70, 2, -42)},
		{"id": "11_parking_minus1", "at": Vector3(-35, -1.6, -44), "look": Vector3(-60, -2, -70)},
		{"id": "12_ramp", "at": Vector3(-25, 1.62, -14), "look": Vector3(-35, -1, -38)},
		{"id": "13_square", "at": Vector3(60, 1.62, -16), "look": Vector3(85, 2, -45)},
		{"id": "14_east_jam", "at": Vector3(60, 1.62, -6), "look": Vector3(105, 2, 0)},
		{"id": "15_towers", "at": Vector3(-20, 1.62, 14), "look": Vector3(-40, 40, -40)},
		{"id": "16_flat_floor3", "at": Vector3(-80, 6.4, -34), "look": Vector3(-50, 6.0, -34)},
		{"id": "17_bird_center", "at": Vector3(-30, 90, 60), "look": Vector3(-30, 0, -20)}]
	for spec: String in OS.get_environment("PROSPEKT_VIEW").split(";", false):
		var custom: PackedStringArray = spec.split(":")
		if custom.size() == 7:
			views = [{"id": custom[0], "at": Vector3(custom[1].to_float(), custom[2].to_float(), custom[3].to_float()),
				"look": Vector3(custom[4].to_float(), custom[5].to_float(), custom[6].to_float())}]
	for view: Dictionary in views:
		camera.global_position = view.at
		camera.look_at(view.look, Vector3.UP)
		camera.fov = 62.0 if String(view.id).ends_with("overview") or String(view.id).ends_with("center") else Settings.fps_fov_v()
		await _frames(20)
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
	get_viewport().get_texture().get_image().save_png(output_dir.path_join("20_map.png"))
	get_tree().quit()


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
