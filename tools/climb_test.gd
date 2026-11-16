extends Node3D
## Залезть наверх и вертикальная лестница на пустом полигоне: игрок Пробелом залезает на машину (сбоку — на
## крышу, спереди — на капот), на ящик, на площадку под низким потолком — сидя; через тонкую стенку по-прежнему
## перелезает, на стену выше досягаемого — нет, с перегрузом высоко не подтянуться. Лестница на крышу дома:
## Пробел у низа — схватился, оружие убрано; W — до верха и шаг на крышу, оружие снова в руках; F у верха —
## на лестницу, S — вниз и сойти; Пробел на лестнице — спрыгнул; перекладины слышно (шум для мародёров).
## Мародёр идёт на звук на крышу — лезет по лестнице (связка навигации) и спускается обратно.
## С окном — снимки climb_*.png.
## godot --headless --path . res://tools/climb_test.tscn

const CAR := "res://assets/models/ring_vehicles/RING_sedan_worn.gltf"
## Дом с лестницей: крыша на 4 м, южная стена — z = 17.
const HOUSE := Vector3(0.0, 2.0, 20.0)
const HOUSE_SIZE := Vector3(6.0, 4.0, 6.0)

var _fails: int = 0
var _cam: Camera3D
var _noise: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	await get_tree().process_frame
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, 30, 0)
	sun.shadow_enabled = true
	add_child(sun)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.ambient_light_color = Color(0.5, 0.5, 0.55)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.55, 0.62, 0.7)
	add_child(env)
	var geo := StaticBody3D.new()
	geo.add_to_group("nav_source")
	add_child(geo)
	_box(geo, Vector3(0, -0.5, 0), Vector3(80, 1, 80), Color(0.4, 0.4, 0.38))
	# ящик 1.2 м, тонкая стенка по пояс, стена 2.6 м, площадка 1 м под потолком на 2.5 м
	_box(geo, Vector3(10, 0.6, 0), Vector3(1.2, 1.2, 1.2), Color(0.55, 0.45, 0.3))
	_box(geo, Vector3(16, 0.5, 0), Vector3(4.0, 1.0, 0.3), Color(0.6, 0.5, 0.4))
	_box(geo, Vector3(22, 1.3, 0), Vector3(4.0, 2.6, 3.0), Color(0.5, 0.5, 0.6))
	_box(geo, Vector3(-10, 0.5, 0), Vector3(3.0, 1.0, 3.0), Color(0.5, 0.55, 0.5))
	_box(geo, Vector3(-10, 2.6, 0.4), Vector3(3.0, 0.2, 3.0), Color(0.45, 0.45, 0.5))
	# ящик 1.8 м — с перегрузом не залезть
	_box(geo, Vector3(-18, 0.9, 0), Vector3(2.0, 1.8, 2.0), Color(0.5, 0.42, 0.35))
	# дом и лестница на его крышу: лестница перед южной стеной, лезут лицом к стене (+Z)
	_box(geo, HOUSE, HOUSE_SIZE, Color(0.62, 0.6, 0.55))
	var ladder := (load("res://scenes/world/ladder.tscn") as PackedScene).instantiate() as Ladder
	ladder.height = HOUSE_SIZE.y
	add_child(ladder)
	var wall_z := HOUSE.z - HOUSE_SIZE.z * 0.5
	ladder.global_position = Vector3(0.0, 0.0, wall_z - ladder.standoff - Ladder.STILE.y * 0.5)
	ladder.rotation_degrees.y = 180.0
	var car := (load(CAR) as PackedScene).instantiate() as Node3D
	add_child(car)
	car.global_position = Vector3(0, 0, -10)
	_cam = Camera3D.new()
	add_child(_cam)
	_cam.look_at_from_position(Vector3(9, 8, -18), Vector3(0, 1, -10))
	# навмеш с крышей дома — для мародёра
	var region := NavigationRegion3D.new()
	var nm := NavigationMesh.new()
	nm.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	nm.geometry_collision_mask = Hitscan.LAYER_WORLD
	nm.geometry_source_geometry_mode = NavigationMesh.SOURCE_GEOMETRY_GROUPS_WITH_CHILDREN
	nm.geometry_source_group_name = "nav_source"
	nm.cell_size = 0.25
	nm.cell_height = 0.25
	nm.agent_height = 1.8
	nm.agent_radius = 0.5
	nm.agent_max_climb = 0.4
	region.navigation_mesh = nm
	add_child(region)
	region.bake_navigation_mesh(false)
	var map := get_world_3d().navigation_map
	for i in range(120):
		await get_tree().physics_frame
		if NavigationServer3D.map_get_iteration_id(map) > 0 and NavigationServer3D.map_get_closest_point(map, Vector3(5, 0, 5)).distance_to(Vector3(5, 0, 5)) < 1.0:
			break
	NoiseBus.noise.connect(func(_p: Vector3, _r: float, kind: String) -> void:
		if kind == "step":
			_noise += 1)
	var pl := (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	pl.name = "Player_1"
	add_child(pl)
	pl.health.hp = 1e9
	await _frames(10)
	var link := ladder.get_node_or_null("NavLink") as NavigationLink3D
	_check("лестница: связка навигации включена (наверху площадка)", link != null and link.enabled, "")
	await _climb_cases(pl, car)
	await _ladder_cases(pl, ladder)
	await _marauder_case(pl, ladder)
	print("climb_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _climb_cases(pl: Player, car: Node3D) -> void:
	# на ровном месте Пробел — по-прежнему прыжок
	await _place(pl, Vector3(30, 0.05, -30), Vector3(0, 0, 1))
	await _press("vault", 2)
	var up := 0.0
	for i in range(30):
		await get_tree().physics_frame
		up = maxf(up, pl.global_position.y)
	_check("на ровном месте Пробел — прыжок", up > 0.3 and not pl.is_climbing() and not pl.is_vaulting(), "%.2f м" % up)
	await _wait(0.6)
	var hull := _car_box(car)
	var roof := hull.end.y
	# борт машины — поперёк длинной оси
	var long_x := hull.size.x > hull.size.z
	var side := Vector3(0, 0, 1) if long_x else Vector3(1, 0, 0)
	var half_w := (hull.size.z if long_x else hull.size.x) * 0.5
	var mid := car.to_global(hull.get_center())
	var at := mid - side * (half_w + 0.75)
	await _place(pl, Vector3(at.x, 0.05, at.z), side)
	await _press("vault", 3)
	await _wait(0.5)
	await _save("climb_car_mid", Vector3(-3.5, 2.6, -14.5), Vector3(0, 1.2, -10))
	await _wait(1.6)
	_check("сбоку на машину — на крыше", pl.global_position.y > roof - 0.25 and not pl.is_vaulting(),
		"крыша %.2f, ноги %s" % [roof, str(pl.global_position)])
	await _save("climb_car_roof", Vector3(-3.5, 2.6, -14.5), Vector3(0, 1.2, -10))
	# спереди — на капот
	var front := Vector3(1, 0, 0) if long_x else Vector3(0, 0, 1)
	var half_l := (hull.size.x if long_x else hull.size.z) * 0.5
	at = mid - front * (half_l + 0.75)
	await _place(pl, Vector3(at.x, 0.05, at.z), front)
	await _press("vault", 3)
	await _wait(2.0)
	_check("спереди на машину — на капоте", pl.global_position.y > 0.5, str(pl.global_position))
	# ящик 1.2 м
	await _place(pl, Vector3(10, 0.05, -1.4), Vector3(0, 0, 1))
	await _press("vault", 3)
	await _wait(1.8)
	_check("на ящик 1.2 м", absf(pl.global_position.y - 1.2) < 0.15 and absf(pl.global_position.z) < 0.6, str(pl.global_position))
	# тонкая стенка по пояс — по-прежнему через
	await _place(pl, Vector3(16, 0.05, -1.0), Vector3(0, 0, 1))
	await _press("vault", 3)
	await _wait(1.5)
	_check("тонкая стенка — перелез через, не встал на неё", pl.global_position.z > 0.4 and pl.global_position.y < 0.3, str(pl.global_position))
	# стена 2.6 м — нет
	await _place(pl, Vector3(22, 0.05, -2.0), Vector3(0, 0, 1))
	await _press("vault", 3)
	await _wait(1.5)
	_check("стена 2.6 м — не залезть", pl.global_position.y < 0.3 and pl.global_position.z < -1.4, str(pl.global_position))
	# площадка под низким потолком — сидя
	await _place(pl, Vector3(-10, 0.05, -2.0), Vector3(0, 0, 1))
	await _press("vault", 3)
	await _wait(1.6)
	_check("под низким потолком — залез сидя", pl.global_position.y > 0.85 and pl.stance == Player.Stance.CROUCH,
		"стойка %d, %s" % [pl.stance, str(pl.global_position)])
	pl.stance = Player.Stance.STAND
	pl.call("_apply_stance")
	# перегруз: предел высоты ниже (Balance.CLIMB.max_h_loaded)
	var space := get_world_3d().direct_space_state
	var p := Vector3(-18, 0.0, -1.6)
	var light := Climb.find(space, p, Vector3(0, 0, 1), [pl.get_rid()])
	var heavy := Climb.find(space, p, Vector3(0, 0, 1), [pl.get_rid()], float(Balance.CLIMB.max_h_loaded))
	_check("ящик 1.8 м: налегке залезть, с перегрузом — нет", not light.is_empty() and heavy.is_empty(), "")


func _ladder_cases(pl: Player, ladder: Ladder) -> void:
	await _place(pl, Vector3(0, 0.05, 15.6), Vector3(0, 0, 1))
	await _wait(0.4)
	var armed := pl.weapon_id != ""
	await _press("vault", 3)
	await _wait(0.5)
	_check("Пробел у низа лестницы — схватился, оружие убрано", pl.is_climbing() and pl.on_ladder and (not armed or pl.weapon_id == ""),
		"в руках было %s, сейчас «%s»" % [str(armed), pl.weapon_id])
	var n0 := _noise
	Input.action_press("move_forward")
	await _wait(1.6)
	await _save("climb_ladder_mid", Vector3(3.2, 2.4, 13.0), Vector3(0, 2.0, 16.8))
	var y_mid := pl.global_position.y
	_check("лезет вверх, перекладины слышно", y_mid > 1.0 and _noise - n0 >= 3, "%.2f м, шум %d" % [y_mid, _noise - n0])
	# W держим, пока не сойдёт наверх (дальше без камеры «вперёд» — это −Z, обратно к краю)
	var t := 0.0
	while (pl.is_climbing() or pl.is_vaulting()) and t < 8.0:
		await get_tree().physics_frame
		t += get_physics_process_delta_time()
	Input.action_release("move_forward")
	await _wait(0.5)
	_check("наверху — шагнул на крышу, оружие снова в руках", not pl.is_climbing() and absf(pl.global_position.y - HOUSE_SIZE.y) < 0.15
		and pl.global_position.z > 17.2 and (not armed or pl.weapon_id != ""), "%s, в руках «%s»" % [str(pl.global_position), pl.weapon_id])
	await _save("climb_ladder_roof", Vector3(3.5, 6.0, 13.0), Vector3(0, 3.8, 17.6))
	# сверху: F у верха — на лестницу, S — вниз до земли и сойти
	var top_point := ladder.get_node("Top") as LadderPoint
	_check("наверху подсказка «спуститься»", top_point.can_use() and top_point.global_position.distance_to(pl.global_position) < Balance.INTERACT_RADIUS,
		"%.2f м" % top_point.global_position.distance_to(pl.global_position))
	top_point.request_use()
	await _wait(1.4)
	_check("F у верха — на лестнице", pl.is_climbing() and pl.global_position.y > 3.0, str(pl.global_position))
	Input.action_press("move_back")
	await _wait(4.5)
	Input.action_release("move_back")
	await _wait(0.4)
	_check("S — спустился и сошёл", not pl.is_climbing() and pl.global_position.y < 0.2, str(pl.global_position))
	# спрыгнуть с середины
	var bottom := ladder.get_node("Bottom") as LadderPoint
	bottom.request_use()
	await _wait(0.5)
	Input.action_press("move_forward")
	await _wait(1.8)
	Input.action_release("move_forward")
	var high := pl.global_position.y
	await _press("vault", 3)
	await _wait(1.5)
	_check("Пробел на лестнице — спрыгнул и упал на землю", not pl.is_climbing() and high > 1.0 and pl.global_position.y < 0.2
		and pl.global_position.z < 16.6, "с %.2f м, %s" % [high, str(pl.global_position)])


func _marauder_case(pl: Player, _ladder: Ladder) -> void:
	# игрока мародёр не видит — идёт только на звук
	pl.global_position = Vector3(-35, 0.05, -35)
	pl.remove_from_group("players")
	var m := (load("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	m.name = "M1"
	add_child(m)
	m.global_position = Vector3(3, 0.1, 13)
	await _wait(1.0)
	m.investigate_at(Vector3(0.5, HOUSE_SIZE.y, 20.5))
	var t := 0.0
	var used := false
	while t < 20.0:
		await get_tree().physics_frame
		t += get_physics_process_delta_time()
		used = used or m.on_ladder
		if m.global_position.y > HOUSE_SIZE.y - 0.3 and not m.on_ladder:
			break
	_check("мародёр залез на крышу по лестнице", used and m.global_position.y > HOUSE_SIZE.y - 0.3, "%.1f с, %s" % [t, str(m.global_position)])
	await _save("climb_marauder", Vector3(3.5, 6.0, 13.0), Vector3(0, 3.8, 17.6))
	await _wait(2.5)
	m.investigate_at(Vector3(4, 0, 12))
	t = 0.0
	used = false
	while t < 20.0:
		await get_tree().physics_frame
		t += get_physics_process_delta_time()
		used = used or m.on_ladder
		if m.global_position.y < 0.3 and not m.on_ladder:
			break
	_check("мародёр спустился по лестнице", used and m.global_position.y < 0.3, "%.1f с, %s" % [t, str(m.global_position)])


## Габарит машины по всем статичным формам деталей в её осях.
func _car_box(car: Node3D) -> AABB:
	var box := AABB()
	var first := true
	for raw: Node in car.find_children("Collision_*", "CollisionShape3D", true, false):
		var cs := raw as CollisionShape3D
		for p: Vector3 in (cs.shape as ConcavePolygonShape3D).get_faces():
			var point := cs.transform * p
			box = AABB(point, Vector3.ZERO) if first else box.expand(point)
			first = false
	return box


func _place(pl: Player, at: Vector3, dir: Vector3) -> void:
	pl.global_position = at
	pl.velocity = Vector3.ZERO
	await _frames(6)
	pl.get_node("Body").rotation.y = atan2(dir.x, dir.z)
	pl.cursor_ground = pl.global_position + dir * 5.0
	await _frames(2)


func _box(body: StaticBody3D, c: Vector3, size: Vector3, col: Color) -> void:
	var cs := CollisionShape3D.new()
	var sh := BoxShape3D.new()
	sh.size = size
	cs.shape = sh
	cs.position = c
	body.add_child(cs)
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	var mat := StandardMaterial3D.new()
	mat.albedo_color = col
	mi.material_override = mat
	mi.position = c
	body.add_child(mi)


func _press(a: String, frames: int) -> void:
	Input.action_press(a)
	await _frames(frames)
	Input.action_release(a)


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().physics_frame


func _wait(sec: float) -> void:
	await get_tree().create_timer(sec).timeout


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])


func _save(n: String, from: Vector3, at: Vector3) -> void:
	if DisplayServer.get_name() == "headless":
		return
	_cam.look_at_from_position(from, at)
	_cam.current = true
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))
