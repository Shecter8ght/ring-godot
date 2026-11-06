extends Node3D
## Карта «Плотина» (на ней задание «Вертолёт») с настоящим игроком (владелец 2026-11-06: «добавим туда руки и оружие,
## функцию спавна ботов»): мир — серый стенд tools/heli_study.tscn без ходока (рельеф, плотина, вода, лес, места коробками, вертолёт по маршруту, общий свет
## рейдов), игрок с руками, оружием и скоростью игры; боты расставляются в свободном полёте, потом — в тело игрока, и боты
## оживают. Устроено как tools/dorm_play.gd.
##   tools/dam_play.cmd                  (HELI_PLAN=v04 — прежняя версия карты; HELI_TIME, HELI_WEATHER — как у стенда)
## Расстановка (полёт): WASD и мышь, Shift — быстрее, Space / C — вверх / вниз; ЛКМ — бот в точку под прицелом (смотрит
## туда же, куда камера), ПКМ — убрать бота под прицелом; 1–6 — кого ставить; R — что делает (обход места, обход рядом,
## пост); N / B — к следующему / прошлому месту карты; G — игрок сюда; Del — убрать всех; Backspace — заново (боты
## и игрок на местах расстановки, убитые встают); Enter — в тело игрока, игра.
## Игра: клавиши игры; Tab — окно со всем оружием игры и конструктор; Enter — обратно в полёт (боты замирают).
## Всегда: Esc — мышь и панель (бессмертие, поле зрения); F10 — без интерфейса.
## Навигация ботов — кусками 128 × 128 м по ходу игры: вокруг игрока и каждого бота (160 м) печётся сама; вся карта
## 2 × 3 км заранее — минуты, а ходят в одном её углу.
## Проверка: --headless res://tools/dam_play.tscn -- check (навигация у игрока и у дальнего бота, расстановка, боты
## оживают и идут на шум, оружие из окна, «заново»); с окном -- shots — снимки docs/screens/heli_v05/play_*.

const WORLD_SCENE: String = "res://tools/heli_study.tscn"
const PLAYER_SCENE: String = "res://scenes/player/player.tscn"
const RIG_SCENE: String = "res://scenes/player/camera_rig.tscn"
const MARAUDER_SCENE: String = "res://scenes/ai/marauder.tscn"
## Кого ставить (клавиши 1–6): типы Balance.AI_ARCHETYPES; "" — случайный мародёр. Снайпер — для открытой долины.
const BOT_TYPES: Array[String] = ["", "gunner", "heavy", "sniper", "pmc", "rival"]
## Что делает бот (R в полёте): обход места — ходит по точкам в PATROL_RADIUS от своей; обход рядом — бродит в
## AREA_RADIUS; пост — стоит и смотрит туда, куда смотрела камера. На шум и бой — как всегда.
const BEHAVIOURS: Array[String] = ["patrol", "area", "post"]
const BEHAVIOUR_NAMES: Dictionary = {"patrol": "обход места", "area": "обход рядом", "post": "пост"}
const PATROL_RADIUS: float = 90.0
const AREA_RADIUS: float = 15.0
## Старт игрока — двор лесопилки лицом к плотине (кадр стенда «01 · плотина над лесопилкой»): она над долиной сразу;
## N / B в полёте начинают с места START_PLACE (2 · Лесопилка) в plan.places.
const START_AT: Vector2 = Vector2(-300.0, 140.0)
const START_LOOK: Vector2 = Vector2(0.0, 450.0)
const START_PLACE: int = 1
const FLY_SPEED: float = 12.0
const FLY_FAST: float = 60.0
const LOOK_SENS: float = 0.0025
## Камера игрока видит плотину и горы через всю долину (у игры 900 м).
const VIEW_FAR: float = 4000.0
## Навигация кусками: сторона куска, сколько метров вокруг игрока и ботов держать испечённым, как часто проверять.
const NAV_TILE: float = 128.0
const NAV_REACH: float = 160.0
const NAV_CHECK_SEC: float = 0.5

var world: Node3D
var plan: Dictionary = {}
var y0: float = 0.0
var mode: String = "fly"
var run_mode: String = "play"
var player: Player
var rig: CameraRig
var fly_cam: Camera3D
var fly_yaw: float = 0.0
var fly_pitch: float = 0.0
var player_start: Vector3
var player_yaw: float = 0.0
var place_index: int = START_PLACE
## Расстановка: {"at", "yaw", "type", "behaviour", "node"}; node — живой бот этой точки.
var bots: Array[Dictionary] = []
var bot_type: int = 0
var behaviour: int = 0
var rng: RandomNumberGenerator = RandomNumberGenerator.new()
var god: bool = true
var picker: RangeWeaponPicker
var marker: Node3D
var marker_label: Label3D
var marker_mat: StandardMaterial3D
var hud: CanvasLayer
var help: Label
var status: Label
var panel: Control
var fov_label: Label
var hud_hidden: bool = false
var results: Array[Dictionary] = []
var rig_layers: Dictionary = {}
## Навигация: источник геометрии всей карты (разбирается один раз), испечённые куски {Vector2i: NavigationRegion3D},
## очередь на выпечку, вода (контуры и уровни) — многоугольники на дне озера и водохранилища убираются.
var nav_source: NavigationMeshSourceGeometryData3D
var nav_tiles: Dictionary = {}
var nav_queue: Array[Vector2i] = []
var nav_baking: bool = false
var nav_bake_done: bool = false
var nav_timer: float = 0.0
var nav_baked_ms: int = 0
var water: Array[Dictionary] = []


func _enter_tree() -> void:
	Profile.use_file("user://profile_dam_play_test.json", true)


func _ready() -> void:
	get_node("/root/Pause").set_process_input(false)
	get_node("/root/Quests").process_mode = Node.PROCESS_MODE_DISABLED
	get_node("/root/Contracts").process_mode = Node.PROCESS_MODE_DISABLED
	for arg: String in OS.get_cmdline_user_args():
		if arg in ["check", "shots"]:
			run_mode = arg
	rng.seed = 7
	world = (load(WORLD_SCENE) as PackedScene).instantiate() as Node3D
	world.set_meta("embedded", true)
	add_child(world)
	plan = world.get("plan") as Dictionary
	y0 = float(world.get("y0"))
	DisplayServer.window_set_title("RING · «Плотина» · игрок и боты")
	for body: Dictionary in plan.get("water", []):
		var outline: PackedVector2Array = PackedVector2Array()
		for q: Array in body.poly:
			outline.append(Vector2(float(q[0]), float(q[1])))
		water.append({"poly": outline, "level": y0 + float(body.level)})
	player_start = Vector3(START_AT.x, float(world.call("ground", START_AT.x, START_AT.y)), START_AT.y)
	player_yaw = atan2(START_LOOK.x - START_AT.x, START_LOOK.y - START_AT.y)
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


# ---------------------------------------------------------------- места карты

func _place_foot(i: int) -> Vector3:
	var target: Array = world.call("_place_at", posmod(i, (plan.places as Array).size()))
	var at: Vector3 = target[0]
	# места на гребне и мостиках заданы высотой глаз (_place_at опускает на 1,6 м) — там пол не земля; у остальных — земля
	var floor_y: float = _floor_below(Vector3(at.x, at.y + 2.0, at.z))
	return Vector3(at.x, floor_y if floor_y > -INF else at.y, at.z)


func _place_yaw(i: int) -> float:
	var target: Array = world.call("_place_at", posmod(i, (plan.places as Array).size()))
	var d: Vector3 = (target[1] as Vector3) - (target[0] as Vector3)
	return atan2(d.x, d.z)


func _place_name(i: int) -> String:
	return String(((plan.places as Array)[posmod(i, (plan.places as Array).size())] as Dictionary).name)


func _floor_below(from: Vector3) -> float:
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(from, from + Vector3.DOWN * 40.0, Hitscan.LAYER_WORLD)
	var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(query)
	return (hit.position as Vector3).y if not hit.is_empty() else -INF


# ---------------------------------------------------------------- игрок и камеры

func _spawn_player() -> void:
	player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	player.name = "Player_1"
	add_child(player)
	player.global_position = player_start + Vector3.UP * 0.05
	player.face(player_yaw)
	rig = (load(RIG_SCENE) as PackedScene).instantiate() as CameraRig
	rig.name = "CameraRig"
	rig.target_path = NodePath("../Player_1")
	add_child(rig)
	rig.set("_look_yaw", player_yaw)
	var cam: Camera3D = _play_camera()
	if cam != null:
		cam.far = VIEW_FAR
	player.set_god(god)
	# в полёте игрок стоит с первого кадра: иначе, пока печётся навигация, корпус поворачивается к курсору мыши
	if mode == "fly":
		player.process_mode = Node.PROCESS_MODE_DISABLED
		rig.process_mode = Node.PROCESS_MODE_DISABLED


func _despawn_player() -> void:
	if is_instance_valid(picker) and picker.is_open():
		picker.close_ui()
	for node: Node in [rig, player]:
		if is_instance_valid(node):
			remove_child(node)
			node.queue_free()
	rig = null
	player = null
	rig_layers.clear()


func _play_camera() -> Camera3D:
	return rig.get("_ads_cam") as Camera3D if is_instance_valid(rig) else null


func _set_mode(value: String) -> void:
	mode = value
	var play: bool = mode == "play"
	for bot: Dictionary in bots:
		if is_instance_valid(bot.node):
			(bot.node as Node).process_mode = Node.PROCESS_MODE_INHERIT if play else Node.PROCESS_MODE_DISABLED
			_bot_label(bot).visible = not play
	if is_instance_valid(player):
		if play:
			_hold_facing(player.body_yaw())
		player.process_mode = Node.PROCESS_MODE_INHERIT if play else Node.PROCESS_MODE_DISABLED
		rig.process_mode = player.process_mode
		# интерфейс камеры игрока (прицел, патроны, ранения) в полёте спрятан, потом — как был
		for layer: Node in rig.find_children("*", "CanvasLayer", true, false):
			if play:
				if rig_layers.has(layer):
					(layer as CanvasLayer).visible = bool(rig_layers[layer])
			elif not rig_layers.has(layer):
				rig_layers[layer] = (layer as CanvasLayer).visible
				(layer as CanvasLayer).visible = false
		if play:
			rig_layers.clear()
	marker.visible = not play
	if play:
		var cam: Camera3D = _play_camera()
		if cam != null:
			cam.current = true
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	else:
		var cam: Camera3D = _play_camera()
		if cam != null and cam.current:
			fly_cam.global_transform = cam.global_transform
			fly_yaw = cam.global_rotation.y
			fly_pitch = cam.global_rotation.x
			_apply_fly_rotation()
		fly_cam.current = true
		if run_mode == "play":
			Input.mouse_mode = Input.MOUSE_MODE_VISIBLE if panel.visible else Input.MOUSE_MODE_CAPTURED
	_update_help()


## В первом кадре игры корпус успевает повернуться к курсору мыши (вид сверху), пока камера не перешла в глаза, а захват
## мыши даёт рывок курсора к середине окна, — взгляд уходил в сторону на десятки градусов. Первые кадры (~0,1 с) держим
## курс, с которым игрок стоял.
func _hold_facing(yaw: float) -> void:
	for i: int in range(12):
		await get_tree().physics_frame
		if not is_instance_valid(player) or not is_instance_valid(rig):
			return
		player.face(yaw)
		rig.set("_look_yaw", yaw)


# ---------------------------------------------------------------- навигация ботов кусками

## Источник — статические коллайдеры мира (земля ядра, плотина, постройки, стволы, невидимые стенки у воды): разбор
## один раз, дальше из него печётся любой кусок. Клетка и агент — как у рейдовых карт (Balance.URBAN_WORLD).
func _prepare_navigation() -> void:
	var cfg: Dictionary = Balance.URBAN_WORLD
	var map: RID = get_world_3d().navigation_map
	NavigationServer3D.map_set_cell_size(map, float(cfg.nav_cell))
	NavigationServer3D.map_set_cell_height(map, float(cfg.nav_height))
	NavigationServer3D.map_set_merge_rasterizer_cell_scale(map, float(cfg.nav_merge_scale))
	# соседние куски сшиваются связями по краю
	NavigationServer3D.map_set_edge_connection_margin(map, 1.0)
	var started: int = Time.get_ticks_msec()
	nav_source = NavigationMeshSourceGeometryData3D.new()
	NavigationServer3D.parse_source_geometry_data(_nav_settings(), nav_source, world)
	print("dam_play: геометрия навигации разобрана за %.1f с" % ((Time.get_ticks_msec() - started) / 1000.0))


func _nav_settings() -> NavigationMesh:
	var cfg: Dictionary = Balance.URBAN_WORLD
	var mesh: NavigationMesh = NavigationMesh.new()
	mesh.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	mesh.geometry_collision_mask = Hitscan.LAYER_WORLD
	mesh.cell_size = float(cfg.nav_cell)
	mesh.cell_height = float(cfg.nav_height)
	mesh.agent_height = ceilf(float(cfg.nav_agent_height) / mesh.cell_height) * mesh.cell_height
	mesh.agent_radius = float(cfg.nav_radius)
	mesh.agent_max_climb = floorf(float(cfg.nav_climb) / mesh.cell_height) * mesh.cell_height
	mesh.agent_max_slope = float(cfg.nav_slope)
	mesh.edge_max_error = 1.0
	mesh.detail_sample_max_error = float(cfg.nav_detail_error)
	mesh.region_min_size = 4.0
	mesh.region_merge_size = 12.0
	return mesh


func _tile_of(at: Vector3) -> Vector2i:
	return Vector2i(int(floor(at.x / NAV_TILE)), int(floor(at.z / NAV_TILE)))


## Поставить в очередь куски в NAV_REACH от точки (ближние — первыми).
func _want_nav_around(at: Vector3) -> void:
	var c: Vector2i = _tile_of(at)
	var span: int = int(ceil(NAV_REACH / NAV_TILE))
	for dx: int in range(-span, span + 1):
		for dz: int in range(-span, span + 1):
			var t: Vector2i = c + Vector2i(dx, dz)
			if nav_tiles.has(t) or nav_queue.has(t):
				continue
			# ближайшая точка куска к месту — в пределах досягаемости
			var nx: float = clampf(at.x, float(t.x) * NAV_TILE, float(t.x + 1) * NAV_TILE)
			var nz: float = clampf(at.z, float(t.y) * NAV_TILE, float(t.y + 1) * NAV_TILE)
			if Vector2(nx - at.x, nz - at.z).length() <= NAV_REACH:
				nav_queue.append(t)
	nav_queue.sort_custom(func(a: Vector2i, b: Vector2i) -> bool:
		return Vector2(a - c).length_squared() < Vector2(b - c).length_squared())
	if not nav_baking:
		_nav_worker()


func _nav_worker() -> void:
	nav_baking = true
	while not nav_queue.is_empty():
		var t: Vector2i = nav_queue.pop_front()
		if nav_tiles.has(t):
			continue
		var started: int = Time.get_ticks_msec()
		var mesh: NavigationMesh = _nav_settings()
		var border: float = float(Balance.URBAN_WORLD.nav_border)
		mesh.border_size = border
		mesh.filter_baking_aabb = AABB(Vector3(float(t.x) * NAV_TILE - border, y0 - 400.0, float(t.y) * NAV_TILE - border),
			Vector3(NAV_TILE + border * 2.0, 1800.0, NAV_TILE + border * 2.0))
		nav_bake_done = false
		NavigationServer3D.bake_from_source_geometry_data_async(mesh, nav_source, func() -> void: nav_bake_done = true)
		while not nav_bake_done:
			await get_tree().process_frame
		_remove_underwater(mesh)
		var region: NavigationRegion3D = NavigationRegion3D.new()
		region.name = "Nav_%d_%d" % [t.x, t.y]
		region.navigation_mesh = mesh
		add_child(region)
		nav_tiles[t] = region
		nav_baked_ms += Time.get_ticks_msec() - started
	nav_baking = false
	_update_help()


## Дно озера и водохранилища — не дорога: многоугольник, середина которого в контуре воды ниже её уровня, убираем.
func _remove_underwater(mesh: NavigationMesh) -> void:
	if water.is_empty():
		return
	var vertices: PackedVector3Array = mesh.get_vertices()
	var kept: Array[PackedInt32Array] = []
	for index: int in range(mesh.get_polygon_count()):
		var polygon: PackedInt32Array = mesh.get_polygon(index)
		var mid: Vector3 = Vector3.ZERO
		for v: int in polygon:
			mid += vertices[v]
		mid /= float(polygon.size())
		var wet: bool = false
		for body: Dictionary in water:
			if mid.y < float(body.level) - 0.3 and Geometry2D.is_point_in_polygon(Vector2(mid.x, mid.z), body.poly):
				wet = true
				break
		if not wet:
			kept.append(polygon)
	if kept.size() == mesh.get_polygon_count():
		return
	mesh.clear_polygons()
	for polygon: PackedInt32Array in kept:
		mesh.add_polygon(polygon)


## Точка на испечённой навигации рядом с данной или INF (куска ещё нет / точка не на дороге ботов).
func _nav_point(at: Vector3) -> Vector3:
	if not nav_tiles.has(_tile_of(at)):
		return Vector3.INF
	var snapped: Vector3 = NavigationServer3D.map_get_closest_point(get_world_3d().navigation_map, at)
	return snapped if snapped.distance_to(at) < 1.2 else Vector3.INF


func _keep_nav_near_actors() -> void:
	if is_instance_valid(player):
		_want_nav_around(player.global_position)
	for bot: Dictionary in bots:
		if is_instance_valid(bot.node) and ((bot.node as Node).get_node("Health") as Health).alive:
			_want_nav_around((bot.node as Node3D).global_position)


# ---------------------------------------------------------------- боты

func _place_bot(at: Vector3, yaw: float, type: String, mode_name: String = "patrol") -> Dictionary:
	var bot: Dictionary = {"at": at, "yaw": yaw, "type": type, "behaviour": mode_name, "node": null}
	bots.append(bot)
	_spawn_bot(bot)
	_want_nav_around(at)
	return bot


func _spawn_bot(bot: Dictionary) -> void:
	var m: Marauder = (load(MARAUDER_SCENE) as PackedScene).instantiate() as Marauder
	m.name = "Bot_%d" % (bots.find(bot) + 1)
	if String(bot.type) != "":
		m.archetype = String(bot.type)
	var dir: Vector3 = Vector3(sin(float(bot.yaw)), 0.0, cos(float(bot.yaw)))
	var at: Vector3 = bot.at
	match String(bot.get("behaviour", "patrol")):
		"post":
			# держит место и смотрит туда, куда смотрела камера; шум и бой — как у всех, потом обратно
			m.home = at
			m.home_radius = 1.0
			m.stay = true
			m.watch_dir = dir
			m.watch_sector_deg = 90.0
		"area":
			m.home = at
			m.home_radius = AREA_RADIUS
		_:
			m.patrol_point_provider = func() -> Vector3: return _patrol_point(at)
	m.no_loot = true
	m.process_mode = Node.PROCESS_MODE_DISABLED if mode == "fly" else Node.PROCESS_MODE_INHERIT
	add_child(m)
	m.global_position = at + Vector3.UP * 0.05
	m.set("_facing", float(bot.yaw))
	var label: Label3D = Label3D.new()
	label.name = "PlaceLabel"
	label.text = _type_name(String(bot.type) if String(bot.type) != "" else m.archetype) + " · " + String(BEHAVIOUR_NAMES[String(bot.get("behaviour", "patrol"))])
	label.position = Vector3(0, 2.15, 0)
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.font_size = 40
	label.pixel_size = 0.004
	label.outline_size = 6
	label.no_depth_test = true
	# на открытой карте ботов ставят за десятки метров: подпись одного размера на экране
	label.fixed_size = true
	label.pixel_size = 0.0009
	label.visible = mode == "fly"
	m.add_child(label)
	bot.node = m


## Точка обхода: случайная точка навигации в PATROL_RADIUS от места расстановки (куски вокруг бота печёт _keep_nav_near_actors).
func _patrol_point(home: Vector3) -> Vector3:
	for attempt: int in range(8):
		var a: float = rng.randf() * TAU
		var r: float = sqrt(rng.randf()) * PATROL_RADIUS
		var probe: Vector3 = home + Vector3(cos(a) * r, 0.0, sin(a) * r)
		var g: float = float(world.call("ground", probe.x, probe.z))
		var on: Vector3 = _nav_point(Vector3(probe.x, g, probe.z))
		if on != Vector3.INF:
			return on
	return home


func _bot_label(bot: Dictionary) -> Label3D:
	return (bot.node as Node).get_node("PlaceLabel") as Label3D


func _remove_bot(bot: Dictionary) -> void:
	if is_instance_valid(bot.node):
		(bot.node as Node).queue_free()
	bots.erase(bot)


func _clear_bots() -> void:
	for bot: Dictionary in bots.duplicate():
		_remove_bot(bot)


## Заново: боты встают на места расстановки живыми, игрок — на старт с полным здоровьем и патронами.
func _restart() -> void:
	for bot: Dictionary in bots:
		if is_instance_valid(bot.node):
			(bot.node as Node).queue_free()
		bot.node = null
	for node: Node in get_children():
		if node is Marauder:
			node.queue_free()
	for bot: Dictionary in bots:
		_spawn_bot(bot)
	_despawn_player()
	_spawn_player()
	await _frames(2)
	_set_mode(mode)


func _type_name(type: String) -> String:
	if type == "":
		return "Мародёр (случайный)"
	return String((Balance.AI_ARCHETYPES[type] as Dictionary).get("name", type))


# ---------------------------------------------------------------- полёт и прицел расстановки

func _fly_look_at(target: Vector3) -> void:
	var d: Vector3 = target - fly_cam.global_position
	fly_yaw = atan2(-d.x, -d.z)
	fly_pitch = atan2(d.y, Vector2(d.x, d.z).length())
	_apply_fly_rotation()


func _apply_fly_rotation() -> void:
	fly_cam.global_rotation = Vector3(fly_pitch, fly_yaw, 0.0)


func _fly_to_place(i: int) -> void:
	place_index = posmod(i, (plan.places as Array).size())
	var foot: Vector3 = _place_foot(place_index)
	var yaw: float = _place_yaw(place_index)
	fly_cam.global_position = foot + Vector3(-sin(yaw) * 18.0, 9.0, -cos(yaw) * 18.0)
	_fly_look_at(foot + Vector3(sin(yaw), 0.0, cos(yaw)) * 25.0)
	_want_nav_around(foot)
	_update_help()


func _aim_ray(mask: int) -> Dictionary:
	var from: Vector3 = fly_cam.global_position
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(from, from - fly_cam.global_basis.z * 1500.0, mask)
	return get_world_3d().direct_space_state.intersect_ray(query)


## Куда встанет бот: на землю под прицелом; прицел в стену или ствол — на землю перед ними.
func _aim_floor() -> Vector3:
	var hit: Dictionary = _aim_ray(Hitscan.LAYER_WORLD)
	if hit.is_empty():
		return Vector3.INF
	var at: Vector3 = hit.position
	if (hit.normal as Vector3).y < 0.6:
		at += (hit.normal as Vector3) * 0.6
		var down: float = _floor_below(at + Vector3.UP * 0.2)
		if down == -INF:
			return Vector3.INF
		at.y = down
	return at


func _fly_yaw_dir() -> float:
	var f: Vector3 = -fly_cam.global_basis.z
	return atan2(f.x, f.z)


func _build_marker() -> void:
	marker = Node3D.new()
	marker.name = "BotMarker"
	add_child(marker)
	marker_mat = StandardMaterial3D.new()
	marker_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	marker_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	marker_mat.no_depth_test = true
	var body: MeshInstance3D = MeshInstance3D.new()
	var capsule: CapsuleMesh = CapsuleMesh.new()
	capsule.radius = 0.32
	capsule.height = 1.8
	body.mesh = capsule
	body.position = Vector3(0, 0.9, 0)
	body.material_override = marker_mat
	marker.add_child(body)
	var nose: MeshInstance3D = MeshInstance3D.new()
	var box: BoxMesh = BoxMesh.new()
	box.size = Vector3(0.12, 0.12, 0.7)
	nose.mesh = box
	nose.position = Vector3(0, 1.5, 0.5)
	nose.material_override = marker_mat
	marker.add_child(nose)
	marker_label = Label3D.new()
	marker_label.position = Vector3(0, 2.2, 0)
	marker_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	marker_label.font_size = 40
	marker_label.pixel_size = 0.004
	marker_label.outline_size = 6
	marker_label.no_depth_test = true
	marker.add_child(marker_label)


func _update_marker() -> void:
	var at: Vector3 = _aim_floor()
	marker.visible = at != Vector3.INF and not panel.visible
	if not marker.visible:
		return
	var baked: bool = nav_tiles.has(_tile_of(at))
	var on_nav: bool = _nav_point(at) != Vector3.INF
	marker.global_position = at
	marker.global_rotation = Vector3(0, _fly_yaw_dir(), 0)
	# дальний маркер — крупнее, чтобы его было видно с высоты
	marker.scale = Vector3.ONE * clampf(at.distance_to(fly_cam.global_position) / 40.0, 1.0, 12.0)
	marker_mat.albedo_color = Color(0.35, 1.0, 0.45, 0.45) if on_nav else Color(1.0, 0.6, 0.2, 0.45)
	var note: String = ""
	if not baked:
		note = " · навигация здесь ещё не испечена (испечётся, как поставишь)"
	elif not on_nav:
		note = " · сюда боту не пройти (круто, вода)"
	marker_label.text = _type_name(BOT_TYPES[bot_type]) + " · " + String(BEHAVIOUR_NAMES[BEHAVIOURS[behaviour]]) + note


func _bot_under_aim() -> Dictionary:
	var hit: Dictionary = _aim_ray(Hitscan.LAYER_WORLD | Hitscan.LAYER_MARAUDER)
	if hit.is_empty():
		return {}
	var best: Dictionary = {}
	var best_d: float = 1.6
	for bot: Dictionary in bots:
		if not is_instance_valid(bot.node):
			continue
		var p: Vector3 = (bot.node as Node3D).global_position
		var d: float = Vector2(p.x - (hit.position as Vector3).x, p.z - (hit.position as Vector3).z).length()
		if d < best_d and absf((hit.position as Vector3).y - p.y - 0.9) < 1.6:
			best = bot
			best_d = d
	return best


func _process(delta: float) -> void:
	if not is_instance_valid(fly_cam) or plan.is_empty():
		return
	if mode == "fly":
		if run_mode == "play" and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
			var move: Vector3 = Vector3.ZERO
			move.x = float(Input.is_physical_key_pressed(KEY_D)) - float(Input.is_physical_key_pressed(KEY_A))
			move.z = float(Input.is_physical_key_pressed(KEY_S)) - float(Input.is_physical_key_pressed(KEY_W))
			move.y = float(Input.is_physical_key_pressed(KEY_SPACE)) - float(Input.is_physical_key_pressed(KEY_C))
			var speed: float = FLY_FAST if Input.is_physical_key_pressed(KEY_SHIFT) else FLY_SPEED
			var basis: Basis = fly_cam.global_basis
			fly_cam.global_position += (basis.x * move.x + basis.z * move.z + Vector3.UP * move.y).limit_length(1.0) * speed * delta
		_update_marker()
	elif is_instance_valid(player):
		# окно оружия: «сдать ствол» возвращает снаряжение профиля, а в стенде его нет — обратно песочница
		if player.loadout_mode and not player.in_range_mode():
			player.loadout_mode = false
	nav_timer -= delta
	if nav_timer <= 0.0 and nav_source != null:
		nav_timer = NAV_CHECK_SEC
		if mode == "play":
			_keep_nav_near_actors()
	_update_status()


# ---------------------------------------------------------------- клавиши

func _unhandled_input(event: InputEvent) -> void:
	if run_mode != "play":
		return
	if mode == "fly" and event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		var motion: InputEventMouseMotion = event as InputEventMouseMotion
		fly_yaw -= motion.relative.x * LOOK_SENS
		fly_pitch = clampf(fly_pitch - motion.relative.y * LOOK_SENS, -1.5, 1.5)
		_apply_fly_rotation()
		return
	if mode == "fly" and event is InputEventMouseButton and (event as InputEventMouseButton).pressed and not panel.visible:
		var button: InputEventMouseButton = event as InputEventMouseButton
		if Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
			Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		elif button.button_index == MOUSE_BUTTON_LEFT:
			var at: Vector3 = _aim_floor()
			if at != Vector3.INF:
				var snapped: Vector3 = _nav_point(at)
				_place_bot(snapped if snapped != Vector3.INF else at, _fly_yaw_dir(), BOT_TYPES[bot_type], BEHAVIOURS[behaviour])
		elif button.button_index == MOUSE_BUTTON_RIGHT:
			var bot: Dictionary = _bot_under_aim()
			if not bot.is_empty():
				_remove_bot(bot)
		return
	if not (event is InputEventKey and (event as InputEventKey).pressed and not event.is_echo()):
		return
	var key: Key = (event as InputEventKey).physical_keycode
	if is_instance_valid(picker) and picker.is_open():
		return
	match key:
		KEY_ESCAPE:
			_toggle_panel()
			return
		KEY_F10:
			hud_hidden = not hud_hidden
			hud.visible = not hud_hidden
		KEY_ENTER, KEY_KP_ENTER:
			_set_mode("play" if mode == "fly" else "fly")
	if mode == "fly":
		match key:
			KEY_1, KEY_2, KEY_3, KEY_4, KEY_5, KEY_6:
				bot_type = key - KEY_1
				_update_help()
			KEY_R:
				behaviour = (behaviour + 1) % BEHAVIOURS.size()
				_update_help()
			KEY_N:
				_fly_to_place(place_index + 1)
			KEY_B:
				_fly_to_place(place_index - 1)
			KEY_G:
				var at: Vector3 = _aim_floor()
				if at != Vector3.INF:
					player_start = at
					player_yaw = _fly_yaw_dir()
					player.global_position = at + Vector3.UP * 0.05
					player.face(player_yaw)
					rig.set("_look_yaw", player_yaw)
					_want_nav_around(at)
			KEY_DELETE:
				_clear_bots()
			KEY_BACKSPACE:
				_restart()
	elif key == KEY_TAB and is_instance_valid(player) and not player.ui_blocked():
		# ствол в руках — стволом «стойки», чтобы конструктор окна собирал именно его
		if not player.in_range_mode() and player.sandbox_weapons.has(player.weapon_slot):
			player.set_range_weapon(player.sandbox_weapons[player.weapon_slot])
		if picker == null:
			picker = RangeWeaponPicker.new()
			picker.name = "WeaponPicker"
			add_child(picker)
		picker.open_for(player)


# ---------------------------------------------------------------- интерфейс

func _ui() -> void:
	hud = CanvasLayer.new()
	hud.name = "DamPlayUI"
	hud.layer = 5
	add_child(hud)
	var root: Control = Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(root)
	help = Label.new()
	help.position = Vector2(24, 18)
	help.add_theme_font_size_override("font_size", 17)
	help.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	help.add_theme_constant_override("outline_size", 6)
	root.add_child(help)
	status = Label.new()
	status.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	status.offset_left = 24
	status.offset_top = -44
	status.add_theme_font_size_override("font_size", 17)
	status.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	status.add_theme_constant_override("outline_size", 6)
	root.add_child(status)
	# Esc: бессмертие и поле зрения; пока панель открыта — персонаж стоит, мышь свободна (группа esc_windows)
	var layer: CanvasLayer = CanvasLayer.new()
	layer.name = "DamPlayPanel"
	layer.layer = 15
	layer.set_script(preload("res://tools/dorm_play_panel.gd"))
	add_child(layer)
	panel = Control.new()
	panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	panel.visible = false
	layer.add_child(panel)
	layer.set("panel", panel)
	var shade: ColorRect = ColorRect.new()
	shade.color = Color(0.03, 0.04, 0.05, 0.82)
	shade.position = Vector2(18, 140)
	shade.size = Vector2(1200, 70)
	panel.add_child(shade)
	var god_toggle: CheckButton = CheckButton.new()
	god_toggle.text = "Бессмертие игрока"
	god_toggle.position = Vector2(30, 158)
	god_toggle.button_pressed = god
	god_toggle.focus_mode = Control.FOCUS_NONE
	god_toggle.toggled.connect(func(on: bool) -> void:
		god = on
		if is_instance_valid(player):
			player.set_god(on))
	panel.add_child(god_toggle)
	# поле зрения игры (Settings.fov_h) — на время стенда, в настройки игры не записывается
	fov_label = Label.new()
	fov_label.position = Vector2(300, 162)
	panel.add_child(fov_label)
	var fov_slider: HSlider = HSlider.new()
	fov_slider.position = Vector2(560, 164)
	fov_slider.size = Vector2(320, 26)
	fov_slider.min_value = 60.0
	fov_slider.max_value = 110.0
	fov_slider.step = 1.0
	fov_slider.focus_mode = Control.FOCUS_NONE
	fov_slider.value = Settings.fov_h
	fov_slider.value_changed.connect(_set_fov)
	panel.add_child(fov_slider)
	for i: int in range(3):
		var preset: float = [80.0, 95.0, 110.0][i]
		var b: Button = Button.new()
		b.text = "%d°" % int(preset)
		b.position = Vector2(900 + i * 70, 160)
		b.focus_mode = Control.FOCUS_NONE
		b.pressed.connect(func() -> void: fov_slider.value = preset)
		panel.add_child(b)
	_set_fov(Settings.fov_h)


func _set_fov(value: float) -> void:
	Settings.fov_h = clampf(value, 60.0, 110.0)
	fov_label.text = "Поле зрения %d° по горизонтали" % int(Settings.fov_h)


func _toggle_panel() -> void:
	panel.visible = not panel.visible
	if mode == "fly":
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE if panel.visible else Input.MOUSE_MODE_CAPTURED
	_update_help()


func _update_help() -> void:
	if help == null:
		return
	var lines: PackedStringArray = []
	if mode == "fly":
		lines.append("РАССТАНОВКА · полёт: WASD и мышь, Shift быстрее, Space / C — вверх / вниз · N / B — к месту карты (%s)" % _place_name(place_index))
		lines.append("ЛКМ — поставить «%s», %s, под прицел (смотрит туда же, куда ты) · ПКМ — убрать · 1–6 — кого · R — что делает" % [_type_name(BOT_TYPES[bot_type]), String(BEHAVIOUR_NAMES[BEHAVIOURS[behaviour]])])
		lines.append("G — игрок сюда · Del — убрать всех · Backspace — заново (все на местах) · Enter — в тело игрока, игра")
	else:
		lines.append("ИГРА · клавиши игры · Tab — любое оружие и конструктор · Enter — обратно в полёт (боты замрут)")
	if nav_baking:
		lines.append("навигация ботов печётся: в очереди %d кусков" % nav_queue.size())
	lines.append("Esc — мышь, бессмертие, поле зрения · F10 — без интерфейса")
	help.text = "\n".join(lines)


func _update_status() -> void:
	var alive: int = 0
	for bot: Dictionary in bots:
		if is_instance_valid(bot.node) and ((bot.node as Node).get_node("Health") as Health).alive:
			alive += 1
	var text: String = "Ботов: %d (живы %d)   ·   навигация: %d кусков%s" % [bots.size(), alive, nav_tiles.size(), " (печётся)" if nav_baking else ""]
	if is_instance_valid(player):
		text += "   ·   HP %d%s" % [int(player.health.hp), " · бессмертие" if god else ""]
		if player.weapon_id != "":
			text += "   ·   в руках: " + ItemDb.item_name(player.weapon_id)
		if not player.is_alive():
			text += "   ·   убит — Enter, затем Backspace: заново"
	status.text = text


# ---------------------------------------------------------------- проверка и снимки

func _check(label: String, passed: bool, details: Variant = "") -> void:
	results.append({"check": label, "pass": passed})
	print("dam_play: %s · %s %s" % ["PASS" if passed else "FAIL", label, str(details)])


func _path(from: Vector3, to: Vector3) -> PackedVector3Array:
	var map: RID = get_world_3d().navigation_map
	return NavigationServer3D.map_get_path(map, NavigationServer3D.map_get_closest_point(map, from), NavigationServer3D.map_get_closest_point(map, to), true)


func _wait_nav(limit_sec: float) -> float:
	var waited: float = 0.0
	while (nav_baking or not nav_queue.is_empty()) and waited < limit_sec:
		await get_tree().process_frame
		waited += get_process_delta_time()
	# сервер навигации публикует новые куски на физическом кадре
	for i: int in range(10):
		await get_tree().physics_frame
	return waited


func _ground_at(x: float, z: float) -> Vector3:
	return Vector3(x, float(world.call("ground", x, z)), z)


func _check_run() -> void:
	_check("Игрок стоит на земле во дворе лесопилки", absf(player_start.y - float(world.call("ground", player_start.x, player_start.z))) < 1.0,
		str(player_start))
	_check("Камера игрока видит на %d м (плотина и горы через долину)" % int(VIEW_FAR), _play_camera() != null and is_equal_approx(_play_camera().far, VIEW_FAR))
	var waited: float = await _wait_nav(240.0)
	_check("Навигация вокруг игрока испечена", nav_tiles.has(_tile_of(player_start)) and not nav_baking,
		"%d кусков за %.1f с (выпечка %.1f с)" % [nav_tiles.size(), waited, nav_baked_ms / 1000.0])
	for i: int in range(30):
		await get_tree().physics_frame
	# путь по навигации от старта к точке навигации в ~100 м в сторону взгляда места (там может быть вода — берём берег)
	var ahead: Vector3 = player_start + Vector3(sin(player_yaw), 0.0, cos(player_yaw)) * 100.0
	ahead = NavigationServer3D.map_get_closest_point(get_world_3d().navigation_map, _ground_at(ahead.x, ahead.z))
	var path: PackedVector3Array = _path(player_start, ahead)
	var ok: bool = path.size() > 1 and path[path.size() - 1].distance_to(ahead) < 2.0 and ahead.distance_to(player_start) > 60.0
	_check("Путь ботов от старта на ~100 м вперёд", ok, "%d точек, цель %s, конец %s" % [path.size(), str(ahead),
		str(path[path.size() - 1]) if path.size() > 0 else "—"])
	# расстановка: обход места, обход рядом, пост — в 30–60 м от игрока
	var side: Vector3 = Vector3(cos(player_yaw), 0.0, -sin(player_yaw))
	var spots: Array[Vector3] = []
	for k: int in range(3):
		var probe: Vector3 = player_start + Vector3(sin(player_yaw), 0.0, cos(player_yaw)) * (30.0 + 12.0 * k) + side * (float(k) - 1.0) * 14.0
		var on: Vector3 = _nav_point(_ground_at(probe.x, probe.z))
		spots.append(on if on != Vector3.INF else _ground_at(probe.x, probe.z))
	var walker_bot: Dictionary = _place_bot(spots[0], player_yaw + PI, "gunner", "patrol")
	var area_bot: Dictionary = _place_bot(spots[1], player_yaw + PI, "", "area")
	var post_bot: Dictionary = _place_bot(spots[2], player_yaw + PI, "sniper", "post")
	var frozen_at: Vector3 = (area_bot.node as Node3D).global_position
	for i: int in range(60):
		await get_tree().physics_frame
	_check("В полёте боты замерли", (area_bot.node as Node3D).global_position.distance_to(frozen_at) < 0.05
		and (area_bot.node as Node).process_mode == Node.PROCESS_MODE_DISABLED)
	# игрок на открытом дворе — боты увидели бы его и начали бой вместо обхода: на время проверки он у посёлка (~400 м)
	var away: Vector3 = _place_foot(0)
	player.global_position = away + Vector3.UP * 0.05
	_set_mode("play")
	var noise: Vector3 = NavigationServer3D.map_get_closest_point(get_world_3d().navigation_map,
		_ground_at(spots[1].x + side.x * 25.0, spots[1].z + side.z * 25.0))
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
	# дальний бот (у подножия плотины, ~1 км): куски вокруг него пекутся сами, он ходит
	_set_mode("fly")
	var far_foot: Vector3 = _place_foot(6)
	var far_bot: Dictionary = _place_bot(far_foot, 0.0, "pmc", "area")
	waited = await _wait_nav(240.0)
	_check("Навигация у дальнего бота («%s») испеклась сама" % _place_name(6), nav_tiles.has(_tile_of(far_foot)) and _nav_point(far_foot) != Vector3.INF,
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
	_check("Камера игрока после «заново» снова видит далеко", _play_camera() != null and is_equal_approx(_play_camera().far, VIEW_FAR))
	var fails: int = results.filter(func(r: Dictionary) -> bool: return not bool(r.pass)).size()
	print("dam_play: проверок %d, провалов %d" % [results.size(), fails])
	get_tree().quit(mini(fails, 255))


func _shots() -> void:
	await _wait_nav(240.0)
	var ahead: Vector3 = Vector3(sin(player_yaw), 0.0, cos(player_yaw))
	var side: Vector3 = Vector3(cos(player_yaw), 0.0, -sin(player_yaw))
	for k: int in range(3):
		var probe: Vector3 = player_start + ahead * (18.0 + 6.0 * k) + side * (float(k) - 1.0) * 5.0
		_place_bot(_ground_at(probe.x, probe.z), player_yaw + PI, ["gunner", "pmc", "heavy"][k], "post")
	fly_cam.global_position = player_start + Vector3(0.0, 9.0, 0.0) - ahead * 14.0
	_fly_look_at(player_start + ahead * 24.0)
	await _frames(60)
	_save("play_fly")
	_set_mode("play")
	player.set_range_weapon(WeaponDb.make_weapon("AK12_BASE", RandomNumberGenerator.new(), [100, 100]))
	await _frames(120)
	var cam: Camera3D = _play_camera()
	var f: Vector3 = -cam.global_basis.z
	print("dam_play: курс игрока %.1f°, корпус %.1f°, взгляд камеры %.1f°" % [rad_to_deg(player_yaw), rad_to_deg(player.body_yaw()),
		rad_to_deg(atan2(f.x, f.z))])
	_save("play_body")
	get_tree().quit(0)


func _save(name: String) -> void:
	var dir: String = "res://docs/screens/heli_%s" % _env("HELI_PLAN", "v05")
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(dir))
	var path: String = ProjectSettings.globalize_path("%s/%s.jpg" % [dir, name])
	get_viewport().get_texture().get_image().save_jpg(path, 0.9)
	print("dam_play: снимок ", path)


func _env(key: String, fallback: String) -> String:
	var value: String = OS.get_environment(key)
	return value if value != "" else fallback


func _frames(count: int) -> void:
	for i: int in range(count):
		await get_tree().physics_frame
