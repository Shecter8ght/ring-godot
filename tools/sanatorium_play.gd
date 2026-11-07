extends "res://tools/dam_play.gd"
## Карта «Санаторий» с настоящим игроком, оружием и ботами — как «Плотина» в tools/dam_play.gd (расстановка в
## свободном полёте, Enter — в тело игрока, навигация ботов кусками 128 м вокруг игрока и ботов). Мир — серый
## блокаут tools/sanatorium_study.tscn без ходока (рельеф, здания по принятым планам, каскад, тропы, мол, лес, плотина
## вдали, общий свет рейдов). Клавиши — как у dam_play: в полёте ЛКМ / ПКМ — поставить / убрать бота, 1–6 — кого,
## R — что делает, N / B — места карты, G — игрок сюда, Del, Backspace; в игре Tab — любое оружие и конструктор.
##   tools/sanatorium_play.cmd                       (SANATORIUM_TIME, SANATORIUM_WEATHER — как у стенда)
## Проверка: --headless res://tools/sanatorium_play.tscn -- check (навигация у игрока и дальнего бота, расстановка,
## боты оживают и идут на шум, оружие, «заново»); с окном -- shots — снимки docs/screens/sanatorium/play_*.

const SAN_WORLD: String = "res://tools/sanatorium_study.tscn"
## Старт — парадная терраса (место 6) лицом к озеру и плотине; дальний бот для проверки — у коттеджей (место 15).
const SAN_START_PLACE: int = 5
const SAN_FAR_PLACE: int = 14
const SAN_AWAY_PLACE: int = 2


func _enter_tree() -> void:
	Profile.use_file("user://profile_sanatorium_play_test.json", true)


func _ready() -> void:
	get_node("/root/Pause").set_process_input(false)
	get_node("/root/Quests").process_mode = Node.PROCESS_MODE_DISABLED
	get_node("/root/Contracts").process_mode = Node.PROCESS_MODE_DISABLED
	for arg: String in OS.get_cmdline_user_args():
		if arg in ["check", "shots"]:
			run_mode = arg
	rng.seed = 7
	world = (load(SAN_WORLD) as PackedScene).instantiate() as Node3D
	world.set_meta("embedded", true)
	add_child(world)
	plan = world.get("plan") as Dictionary
	y0 = float(world.get("y0"))
	DisplayServer.window_set_title("RING · «Санаторий» · игрок и боты")
	# дно озера — не дорога ботам; чаши бассейнов и фонтаны — тоже вода, но малые: навигация их и так обходит
	for body: Dictionary in plan.get("water", []):
		if not body.has("poly"):
			continue
		var outline: PackedVector2Array = PackedVector2Array()
		for q: Array in body.poly:
			outline.append(Vector2(float(q[0]), float(q[1])))
		water.append({"poly": outline, "level": y0 + float(body.level)})
	place_index = SAN_START_PLACE
	var start: Array = world.call("_place_at", SAN_START_PLACE)
	player_start = start[0]
	var look: Vector3 = start[1]
	player_yaw = atan2(look.x - player_start.x, look.z - player_start.z)
	fly_cam = Camera3D.new()
	fly_cam.name = "FlyCamera"
	fly_cam.near = 0.1
	fly_cam.far = VIEW_FAR
	add_child(fly_cam)
	_ui()
	_build_marker()
	_spawn_player()
	await _frames(3)
	_prepare_navigation()
	_set_mode("fly")
	fly_cam.global_position = player_start + Vector3(0.0, 14.0, 22.0)
	_fly_look_at(player_start + Vector3.UP * 1.5)
	_want_nav_around(player_start)
	if run_mode == "check":
		await _check_run()
	elif run_mode == "shots":
		await _shots()


func _check(label: String, passed: bool, details: Variant = "") -> void:
	results.append({"check": label, "pass": passed})
	print("sanatorium_play: %s · %s %s" % ["PASS" if passed else "FAIL", label, str(details)])


func _check_run() -> void:
	_check("Игрок стоит на парадной террасе (+32)", absf(player_start.y - 32.05) < 0.3, str(player_start))
	var waited: float = await _wait_nav(240.0)
	_check("Навигация вокруг игрока испечена", nav_tiles.has(_tile_of(player_start)) and not nav_baking,
		"%d кусков за %.1f с (выпечка %.1f с)" % [nav_tiles.size(), waited, nav_baked_ms / 1000.0])
	for i: int in range(30):
		await get_tree().physics_frame
	# путь ботов: с террасы через главный корпус к кругу с фонтаном (~85 м по прямой)
	var circle: Vector3 = NavigationServer3D.map_get_closest_point(get_world_3d().navigation_map, _ground_at(14.0, 2.0))
	var path: PackedVector3Array = _path(player_start, circle)
	var ok: bool = path.size() > 1 and path[path.size() - 1].distance_to(circle) < 2.0 and circle.distance_to(player_start) > 60.0
	_check("Путь ботов с террасы к кругу у входа", ok, "%d точек, цель %s, конец %s" % [path.size(), str(circle),
		str(path[path.size() - 1]) if path.size() > 0 else "—"])
	# расстановка: обход места, обход рядом, пост — на террасе и у главного корпуса
	var spots: Array[Vector3] = []
	for xz: Vector2 in [Vector2(-66.0, -2.0), Vector2(-60.0, 10.0), Vector2(-78.0, -12.0)]:
		var on: Vector3 = _nav_point(Vector3(xz.x, 32.0, xz.y))
		spots.append(on if on != Vector3.INF else Vector3(xz.x, 32.0, xz.y))
	var walker_bot: Dictionary = _place_bot(spots[0], player_yaw + PI, "gunner", "patrol")
	var area_bot: Dictionary = _place_bot(spots[1], player_yaw + PI, "", "area")
	var post_bot: Dictionary = _place_bot(spots[2], player_yaw + PI, "sniper", "post")
	var frozen_at: Vector3 = (area_bot.node as Node3D).global_position
	for i: int in range(60):
		await get_tree().physics_frame
	_check("В полёте боты замерли", (area_bot.node as Node3D).global_position.distance_to(frozen_at) < 0.05
		and (area_bot.node as Node).process_mode == Node.PROCESS_MODE_DISABLED)
	# игрок на открытой террасе — боты увидели бы его и начали бой вместо обхода: на время проверки он в «Ресторане и спа»
	var away: Vector3 = _place_foot(SAN_AWAY_PLACE)
	player.global_position = away + Vector3.UP * 0.05
	_set_mode("play")
	var noise: Vector3 = NavigationServer3D.map_get_closest_point(get_world_3d().navigation_map, Vector3(-72.0, 32.0, 14.0))
	(area_bot.node as Marauder).investigate_at(noise)
	var moved: float = 0.0
	var closest: float = INF
	for i: int in range(900):
		await get_tree().physics_frame
		moved = maxf(moved, (area_bot.node as Node3D).global_position.distance_to(frozen_at))
		closest = minf(closest, (area_bot.node as Node3D).global_position.distance_to(noise))
	_check("В игре бот ожил и пошёл на шум", moved > 3.0 and closest < 8.0, "отошёл на %.1f м, до места шума %.1f м" % [moved, closest])
	var walked: float = (walker_bot.node as Node3D).global_position.distance_to(walker_bot.at)
	_check("Бот «обход места» ходит", walked > 3.0, "%.1f м от места расстановки" % walked)
	_check("Бот «пост» стоит на месте", (post_bot.node as Node3D).global_position.distance_to(post_bot.at) < 2.0,
		str((post_bot.node as Node3D).global_position))
	# дальний бот (у коттеджей, ~250 м): куски вокруг него пекутся сами, он ходит
	_set_mode("fly")
	var far_foot: Vector3 = _place_foot(SAN_FAR_PLACE)
	var far_bot: Dictionary = _place_bot(far_foot, 0.0, "pmc", "area")
	waited = await _wait_nav(240.0)
	_check("Навигация у дальнего бота («%s») испеклась сама" % _place_name(SAN_FAR_PLACE),
		nav_tiles.has(_tile_of(far_foot)) and _nav_point(far_foot) != Vector3.INF,
		"%.1f с, кусков всего %d, бот %s" % [waited, nav_tiles.size(), (far_bot.node as Node).name])
	_set_mode("play")
	var entry: Dictionary = WeaponDb.make_weapon("AK12_BASE", RandomNumberGenerator.new(), [100, 100])
	player.set_range_weapon(entry)
	for i: int in range(30):
		await get_tree().physics_frame
	_check("Оружие из окна в руках", player.weapon_id != "" and player.in_range_mode(), player.weapon_id)
	_set_mode("fly")
	_restart()
	for i: int in range(10):
		await get_tree().physics_frame
	var restored: bool = true
	for bot: Dictionary in bots:
		restored = restored and is_instance_valid(bot.node) and (bot.node as Node3D).global_position.distance_to(bot.at) < 0.3
	_check("Заново: боты на местах расстановки, игрок на старте", restored and player.global_position.distance_to(player_start) < 0.3)
	_check("Камера игрока видит на %d м (плотина за озером)" % int(VIEW_FAR), _play_camera() != null and is_equal_approx(_play_camera().far, VIEW_FAR))
	var fails: int = results.filter(func(r: Dictionary) -> bool: return not bool(r.pass)).size()
	print("sanatorium_play: проверок %d, провалов %d" % [results.size(), fails])
	get_tree().quit(mini(fails, 255))


func _shots() -> void:
	await _wait_nav(240.0)
	var ahead: Vector3 = Vector3(sin(player_yaw), 0.0, cos(player_yaw))
	var side: Vector3 = Vector3(cos(player_yaw), 0.0, -sin(player_yaw))
	for k: int in range(3):
		var probe: Vector3 = player_start + ahead * (10.0 + 4.0 * k) + side * (float(k) - 1.0) * 4.0
		var on: Vector3 = _nav_point(Vector3(probe.x, 32.0, probe.z))
		_place_bot(on if on != Vector3.INF else Vector3(probe.x, 32.0, probe.z), player_yaw + PI, ["gunner", "pmc", "heavy"][k], "post")
	fly_cam.global_position = player_start + Vector3(0.0, 9.0, 0.0) - ahead * 14.0
	_fly_look_at(player_start + ahead * 24.0)
	await _frames(60)
	_save("play_fly")
	_set_mode("play")
	player.set_range_weapon(WeaponDb.make_weapon("AK12_BASE", RandomNumberGenerator.new(), [100, 100]))
	await _frames(120)
	_save("play_body")
	get_tree().quit(0)


func _save(shot: String) -> void:
	var dir: String = "res://docs/screens/sanatorium"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(dir))
	var path: String = ProjectSettings.globalize_path("%s/%s.jpg" % [dir, shot])
	var image: Image = get_viewport().get_texture().get_image()
	if image:
		image.save_jpg(path, 0.9)
	print("sanatorium_play: снимок ", path)
