@tool
extends Node3D
## Сцена сектора: строит геометрию из данных, печёт навмеш, спавнит игроков и мародёров.
## Свет и атмосферу задаёт WorldEnvironment/Sun в самой сцене — их можно крутить руками в редакторе.
##
## Сеть: без активного MultiplayerPeer (запуск из редактора, tools/*.tscn) спавнится один
## локальный игрок как раньше — все тестовые сцены и smoke-прогоны продолжают работать без
## изменений. С сетью — хост создаёт по Player на каждый peer (см. Net.PORT/MAX_PLAYERS) через
## MultiplayerSpawner, чтобы узел реплицировался остальным; мародёров хост спавнит так же.
## Авторитет см. в AGENTS.md: у Player — владеющий peer (кроме Health), у Marauder/Door — хост.
##
## Руками в сцене уровня: постройки (Buildings/*, BlockoutBuilding), точки появления (SpawnPoints/*)
## и эвакуации (Extractions/*). Кольцо — из JSON; в редакторе видно превью (@tool), в сцену оно
## не сохраняется.

const PLAYER_SCENE := preload("res://scenes/player/player.tscn")
const MARAUDER_SCENE := preload("res://scenes/ai/marauder.tscn")
## В каких помещениях мародёры появляются и патрулируют.
const AI_ROOM_TYPES := ["retail", "storage", "corridor", "gallery", "office", "security", "utility", "yard"]

@export_file("*.json") var sector_path: String = "res://data/sectors/mall_map.json":
	set(v):
		sector_path = v
		if Engine.is_editor_hint() and is_inside_tree():
			_build_editor_preview.call_deferred()

var _rooms: Array = []
var _spawn: Vector3 = Vector3.ZERO
## Когда начался рейд (мс) — безопасный старт (SPAWN_SAFE).
var _start_ms: int = Time.get_ticks_msec()
var _rng := RandomNumberGenerator.new()
var _nav_baked: bool = false
var _local_player: Player = null
var _players_root: Node3D
var _marauders_root: Node3D
var _player_spawner: MultiplayerSpawner
var _marauder_spawner: MultiplayerSpawner
var _marauders_spawned: int = 0
## Номер следующего мародёра (имя «MarauderN» одно у всех peer — его передаёт спавнер).
var _marauder_seq: int = 0
## Население слоями (точки AIPost/AIRoute/AINest/AIArrival на карте) и счётчик стычек.
var _population: AIPopulation
## Охрана сюжетного места, заказанная до готовности навмеша: [[точка, сколько, радиус], …].
var _pending_guards: Array = []
var _pending_squads: Array = []
var _guard_count: int = 0
var _ring: Dictionary = {}
var _raid: Raid
## Перекрытия, спрятанные над игроком (паркинг, навесы): остаются только тенью.
var _decks_hidden: Dictionary = {}
## Где был свой игрок (задания «побывать в помещении»): проверка раз в полсекунды.
var _visit_t: float = 0.0
var _visited: Dictionary = {}
var _sector_def: Dictionary = {}
## Пролог «Первый выход» на этой карте (Prologue.attach): свой заход, один выход, население выключено.
var _prologue: Prologue

@onready var _camera_rig: CameraRig = $CameraRig
@onready var _hud: Control = $HUD/Root


func _ready() -> void:
	if Engine.is_editor_hint():
		_build_editor_preview()
		return
	if Loading.active:
		Loading.hold_scene(self)
		await Loading.stage("Подготовка локации", float(Balance.LOADING_PROGRESS.geometry))
	_rng.randomize()
	_sector_def = SectorBuilder.load_def(sector_path)
	# сеть: всё, что синхронизируется в рейде, — только тем, кто в рейде (ушедший в убежище не
	# получает поток; спавн игрока придёт клиенту, когда его рейд загрузится)
	get_tree().node_added.connect(_on_node_added)
	# условия рейда — до всего остального (от них зависит свет и зрение мародёров)
	RaidConditions.current = RaidConditions.for_new_raid()
	RaidConditions.from_host = {}
	# пролог — до событий и чужих отрядов: он их выключает (docs/design/prologue.md §8)
	_prologue = Prologue.attach(self)
	# доп. сцены из данных сектора ("extras"): улица — фонари, подстанция, спуски в убежище (правятся
	# в редакторе отдельно от сцены уровня). До сборки: спуски вырезают землю, точки появления — их
	for path in SectorBuilder.load_def(sector_path).get("extras", []):
		if ResourceLoader.exists(String(path)):
			add_child((load(String(path)) as PackedScene).instantiate())
	var t0 := Time.get_ticks_msec()
	var builder := SectorBuilder.new()
	for h in get_tree().get_nodes_in_group("ground_holes"):
		if h.has_method("hole_rect"):
			builder.holes.append(h.call("hole_rect"))
	# узлы сцены, под которыми пропсов быть не должно (эскалаторы) — уже в дереве: дети готовы раньше
	for k in get_tree().get_nodes_in_group("prop_keepout"):
		if k.has_method("keepout_rect"):
			builder.keepouts.append(k.call("keepout_rect"))
	var sector := builder.build(sector_path)
	print("sector: собран за %d мс (пропсов %d, склеено в %d мешей)" % [Time.get_ticks_msec() - t0, int(sector.get_meta("prop_count", 0)), int(sector.get_meta("prop_batches", 0))])
	sector.add_to_group("nav_source")
	add_child(sector)
	move_child(sector, 0)
	# потолки и купол — не источник навмеша (иначе крыша станет «полом» для мародёров)
	var ceil := sector.get_node_or_null("Ceilings")
	if ceil:
		ceil.reparent(self)
	if Loading.active:
		await Loading.stage("Подготовка света и погоды", float(Balance.LOADING_PROGRESS.atmosphere))
	var atmo := RaidAtmosphere.new()
	atmo.name = "Atmosphere"
	add_child(atmo)
	atmo.apply()
	var weather := RaidWeather.new()
	weather.name = "Weather"
	add_child(weather)
	var events := RaidEvents.new()
	events.name = "Events"
	add_child(events)
	# чужие отряды — «другие игроки» рейда (узел есть у всех: по нему хост шлёт рацию)
	var rivals := RivalRaids.new()
	rivals.name = "Rivals"
	rivals.sector_id = String(_sector_def.get("id", ""))
	add_child(rivals)
	# население слоями (если на карте есть точки) и счётчик стычек — считает хост
	_population = AIPopulation.new()
	_population.name = "Population"
	_population.definition = _sector_def
	add_child(_population)
	if _prologue:
		_prologue.setup_population(_population)
	var contacts := RaidContacts.new()
	contacts.name = "Contacts"
	add_child(contacts)
	_rooms = sector.get_meta("rooms", [])
	_spawn = sector.get_meta("spawn", Vector3.ZERO)
	_ring = sector.get_meta("ring", {})
	if String(_sector_def.get("layout", "")) == "cartesian_scene":
		(_camera_rig.get_node("Pivot/Camera3D") as Camera3D).far = float(Balance.URBAN_WORLD.view_distance)
		for extraction: Node in get_tree().get_nodes_in_group("extractions"):
			if is_ancestor_of(extraction):
				(extraction as ExtractionPoint).channel_s = float(Balance.URBAN_WORLD.extract_seconds)
		for batch_root in get_tree().get_nodes_in_group("urban_prop_batches"):
			if is_ancestor_of(batch_root):
				PropBatcher.batch(batch_root as Node3D, float(Balance.URBAN_WORLD.batch_cell), float(Balance.URBAN_WORLD.prop_distance))
		var urban_map := MapView.new()
		urban_map.name = "Map"
		urban_map.setup_urban(_sector_def)
		add_child(urban_map)
	# карта этажа на M (только у кольца — у старого сектора плана нет)
	if not _ring.is_empty():
		var map := MapView.new()
		map.name = "Map"
		var ang: Array = SectorBuilder.load_def(sector_path).get("angle", [-180, 0])
		map.setup(_rooms, _ring, Vector2(float(ang[0]), float(ang[1])))
		add_child(map)
	# точка появления из сцены уровня (узлы SpawnPoint) — одна случайная на рейд
	var points := get_tree().get_nodes_in_group("spawn_points")
	# точки захода с периметра: есть такие — только они
	var entries := points.filter(func(p: Node) -> bool: return p is SpawnPoint and (p as SpawnPoint).entry)
	if not entries.is_empty():
		points = entries
	if not points.is_empty():
		_spawn = (points[_rng.randi_range(0, points.size() - 1)] as Node3D).global_position
	if _prologue:
		_spawn = _prologue.spawn_at(_spawn)
	if _camera_rig and _ring.is_empty() and sector.has_meta("camera_yaw"):
		# старый сектор: камера от атриума наружу — витрины галереи обращены к камере
		_camera_rig.rotation_degrees.y = float(sector.get_meta("camera_yaw"))

	# Контейнеры существуют всегда (offline-инструменты ищут "Marauders" по имени) — спавнеры
	# навешиваются на них только при активной сети.
	_players_root = Node3D.new()
	_players_root.name = "Players"
	add_child(_players_root)
	_marauders_root = Node3D.new()
	_marauders_root.name = "Marauders"
	add_child(_marauders_root)
	# состояние рейда (ключи, рубильники, эвакуация, итог) — одно имя у всех peer
	_raid = Raid.new()
	_raid.name = "Raid"
	add_child(_raid)
	# выходы этого рейда (сторона захода, «не каждый рейд») и открытые схроны — бросает хост
	if not Net.is_networked() or multiplayer.is_server():
		var roll := RandomNumberGenerator.new()
		roll.randomize()
		# пролог: выход один и Михалыч сам скажет, куда идти — списка выходов на старте нет
		var near_m := float(Balance.EXIT_RULES.near_spawn_m) if bool(_sector_def.get("exits_by_side", false)) and _prologue == null else 0.0
		_raid.roll_exits(_spawn, near_m, roll)
		_raid.roll_stashes(roll)

	if Loading.active:
		await Loading.stage("Подготовка игроков", float(Balance.LOADING_PROGRESS.player))
	if not Net.is_networked():
		_spawn_offline_player()
	else:
		_setup_spawners()
		if multiplayer.is_server():
			_spawn_networked_players()
			multiplayer.peer_connected.connect(_on_peer_connected_late)
		multiplayer.peer_disconnected.connect(_on_peer_disconnected)
		_find_local_player_when_ready()
	if Loading.active:
		await Loading.stage("Подготовка мира", float(Balance.LOADING_PROGRESS.equipment))
	_bake_navmesh()
	# Только после создания спавнеров, Weather и Events можно получать пакеты рейда.
	Net.enter_scene("raid")


## Раньше детей: их синхронизаторы (Net.scope_sync) сразу знают, что они — в рейде.
func _enter_tree() -> void:
	if not Engine.is_editor_hint():
		set_meta(Net.SCENE_META, "raid")


func _exit_tree() -> void:
	if get_tree().node_added.is_connected(_on_node_added):
		get_tree().node_added.disconnect(_on_node_added)


## Страховка для синхронизатора, созданного без Net.scope_sync (фильтр — с опозданием на кадр).
func _on_node_added(n: Node) -> void:
	if n is MultiplayerSynchronizer and is_ancestor_of(n):
		Net.filter_sync(n as MultiplayerSynchronizer, "raid")


## Без сети — один игрок на месте спавна, как раньше (для tools/*.tscn и запуска из редактора).
func _spawn_offline_player() -> void:
	var p := PLAYER_SCENE.instantiate() as Player
	p.name = "Player_1"
	p.peer_id = 1
	_players_root.add_child(p)
	p.global_position = _spawn + Vector3(0, 0.05, 0)
	_raid.register(1, "Ты")
	_local_player = p
	_apply_loadout(p)
	_camera_rig.set_target(p)
	_face_center(p.global_position)
	if _prologue:
		p.face(_prologue.spawn_yaw(p.global_position))


## У кольца камера на старте смотрит от игрока к центру — здание перед глазами. Считается у
## каждого peer по своему игроку (точку появления выбирает хост).
func _face_center(pos: Vector3) -> void:
	if _camera_rig == null or _ring.is_empty():
		return
	var to_center := -Vector2(pos.x, pos.z)
	_camera_rig.rotation.y = -atan2(to_center.x, -to_center.y)


func _setup_spawners() -> void:
	_player_spawner = MultiplayerSpawner.new()
	_player_spawner.name = "PlayerSpawner"
	add_child(_player_spawner)
	_player_spawner.spawn_path = _players_root.get_path()
	_player_spawner.spawn_function = _spawn_player_node

	_marauder_spawner = MultiplayerSpawner.new()
	_marauder_spawner.name = "MarauderSpawner"
	add_child(_marauder_spawner)
	_marauder_spawner.spawn_path = _marauders_root.get_path()
	_marauder_spawner.spawn_function = _spawn_marauder_node


## Тот же callable вызывается сетевым слоем на КАЖДОМ peer с одинаковыми data — здесь и только
## здесь можно безопасно выставлять authority/позицию так, чтобы совпало у всех.
func _spawn_player_node(data: Dictionary) -> Node:
	var peer_id: int = data.peer_id
	var p := PLAYER_SCENE.instantiate() as Player
	p.name = "Player_%d" % peer_id
	p.peer_id = peer_id
	p.set_multiplayer_authority(peer_id)
	(p.get_node("Health") as Health).set_multiplayer_authority(1, false)
	p.position = data.pos
	return p


func _spawn_marauder_node(data: Dictionary) -> Node:
	var m := MARAUDER_SCENE.instantiate() as Marauder
	m.name = String(data.name)
	m.position = data.pos
	m.loadout_id = String(data.get("loadout", ""))
	m.archetype = String(data.get("arch", ""))
	if data.has("home"):
		m.home = data.home
		m.home_radius = float(data.get("home_r", 0.0))
	if bool(data.get("hostile", false)):
		m.set_meta("hostile", true)
	return m


## Форма стоящего бойца из той же сцены, из которой создаются отряды.
func squad_spawn_clearance() -> PhysicsShapeQueryParameters3D:
	var prototype := MARAUDER_SCENE.instantiate() as Marauder
	var capsule := prototype.get_node("Capsule") as CollisionShape3D
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = capsule.shape
	query.transform = capsule.transform
	query.collision_mask = prototype.collision_mask
	prototype.free()
	return query


## Хост: отряд из archs (типы AI_ARCHETYPES) у точки at. opts: home + home_r — держатся у места
## (жильцы, охрана), hostile — жильцы враждебны сразу, target — сразу идут проверить точку (ЧВК к
## грузу), loadout — выкладка всем (data/loadouts.json). До готовности навмеша — в очередь.
## can_spawn — проверка каждой позиции. Если хотя бы одна не подходит, весь отряд ждёт.
## spread_inward — разброс от входа только в сторону центра карты, чтобы не встать на заборе.
## Возвращает отряд или null: навигация ещё не готова либо позиции не прошли проверку.
func spawn_squad(at: Vector3, archs: Array, opts: Dictionary = {}) -> Squad:
	if _marauders_spawned == 0:
		_pending_squads.append([at, archs, opts])
		return null
	var map := get_world_3d().navigation_map
	var squad := Squad.new()
	var n := archs.size()
	var can_spawn: Callable = opts.get("can_spawn", Callable())
	var spread_inward: bool = bool(opts.get("spread_inward", false))
	var inward := Vector2.ZERO
	if spread_inward:
		var bounds: Array = _sector_def.bounds
		var center := Vector2((float(bounds[0]) + float(bounds[2])) * 0.5, (float(bounds[1]) + float(bounds[3])) * 0.5)
		inward = (center - Vector2(at.x, at.z)).normalized()
	var members: Array[Dictionary] = []
	for k in range(n):
		var a := TAU * float(k) / float(maxi(n, 1)) + _rng.randf() * 0.5
		var dir := Vector2(cos(a), sin(a))
		if spread_inward and dir.dot(inward) < 0.0:
			dir = dir.reflect(Vector2(-inward.y, inward.x))
		var p := NavigationServer3D.map_get_closest_point(map, at + Vector3(dir.x, 0.0, dir.y) * _rng.randf_range(1.5, 3.5))
		p += Vector3.UP * 0.1
		if can_spawn.is_valid() and not bool(can_spawn.call(p)):
			return null
		var arch := String(archs[k])
		var wpn := Marauder.loadout_for(arch, _rng)
		# «Периметр» — группа по ролям: командир, стрелок, штурмовик, марксман
		if arch == "pmc" and not WeaponDb.pmc_squad().is_empty():
			wpn = String(WeaponDb.pmc_squad()[k % WeaponDb.pmc_squad().size()])
		# выкладка задана явно (консоль разработчика, события)
		if opts.has("loadout"):
			wpn = String(opts.loadout)
		var data := {"pos": p, "loadout": wpn, "arch": arch}
		if opts.has("home"):
			data["home"] = opts.home
			data["home_r"] = float(opts.get("home_r", 6.0))
		if bool(opts.get("hostile", false)):
			data["hostile"] = true
		members.append(data)
	var first: Marauder = null
	for data: Dictionary in members:
		data["name"] = "%s%d" % [String(data.arch).capitalize(), _guard_count]
		_guard_count += 1
		var m: Marauder
		if _marauder_spawner:
			m = _marauder_spawner.spawn(data) as Marauder
		else:
			m = _spawn_marauder_node(data) as Marauder
			_marauders_root.add_child(m)
			m.global_position = data.pos
		m.patrol_point_provider = _random_room_point
		squad.add(m)
		if first == null:
			first = m
	var target: Vector3 = opts.get("target", Vector3.INF)
	if first and target != Vector3.INF:
		first.investigate_at.call_deferred(target)
	return squad


## Хост: отряд, который держится у точки (сюжетное место — «здесь их много»): n бойцов, не
## уходят грабить дальше radius. До готовности навмеша — в очередь.
func spawn_guards(at: Vector3, n: int, radius: float) -> void:
	if _marauders_spawned == 0:
		_pending_guards.append([at, n, radius])
		return
	var map := get_world_3d().navigation_map
	var squad := Squad.new()
	for k in range(n):
		var a := TAU * float(k) / float(maxi(n, 1)) + _rng.randf() * 0.5
		var p := NavigationServer3D.map_get_closest_point(map, at + Vector3(cos(a), 0.0, sin(a)) * _rng.randf_range(2.0, radius * 0.6))
		var arch := "heavy" if k == 0 else ("gunner" if k % 2 == 1 else "scout")
		var wpn := Marauder.loadout_for(arch, _rng)
		var nm := "Guard%d" % _guard_count
		_guard_count += 1
		var m: Marauder
		if _marauder_spawner:
			m = _marauder_spawner.spawn({"name": nm, "pos": p + Vector3(0, 0.1, 0), "loadout": wpn, "arch": arch, "home": at, "home_r": radius}) as Marauder
		else:
			m = MARAUDER_SCENE.instantiate() as Marauder
			m.name = nm
			m.loadout_id = wpn
			m.archetype = arch
			m.home = at
			m.home_radius = radius
			_marauders_root.add_child(m)
			m.global_position = p + Vector3(0, 0.1, 0)
		m.patrol_point_provider = _random_room_point
		squad.add(m)
	print("sector: охрана у %s — %d" % [at, n])


## Хост: по игроку на каждый уже подключённый peer (себя и остальных из лобби).
func _spawn_networked_players() -> void:
	var ids: Array = [1]
	for id in multiplayer.get_peers():
		ids.append(id)
	for i in range(ids.size()):
		_spawn_one_player(int(ids[i]), i)


func _spawn_one_player(peer_id: int, index: int, at: Vector3 = Vector3.INF) -> void:
	var offset := Vector3(cos(index * TAU / 3.0), 0.0, sin(index * TAU / 3.0)) * 1.3
	var pos := (_spawn if at == Vector3.INF else at) + offset + Vector3(0, 0.05, 0)
	var node := _player_spawner.spawn({"peer_id": peer_id, "pos": pos}) as Player
	_raid.register(peer_id, String(Net.player_names.get(peer_id, "Игрок %d" % peer_id)))


## Присоединился уже во время рейда (лобби этого не предполагает, но не должно ломаться).
func _on_peer_connected_late(id: int) -> void:
	if not multiplayer.is_server():
		return
	var count := _players_root.get_child_count()
	# пролог: подключившийся позже появляется у группы (§6)
	_spawn_one_player(id, count, _prologue.late_spawn(_spawn) if _prologue else Vector3.INF)


func _on_peer_disconnected(id: int) -> void:
	if not multiplayer.is_server() or _players_root == null:
		return
	var node := _players_root.get_node_or_null("Player_%d" % id)
	if node:
		node.queue_free()


## Игрок появляется у клиента чуть позже (после первой репликации) — ждём и наводим камеру.
func _find_local_player_when_ready() -> void:
	var my_id := multiplayer.get_unique_id()
	while _local_player == null:
		if not is_inside_tree():
			return
		for p in get_tree().get_nodes_in_group("players"):
			if (p as Player).peer_id == my_id:
				_local_player = p
				break
		if _local_player == null:
			await get_tree().process_frame
	_camera_rig.set_target(_local_player)
	_face_center(_local_player.global_position)
	if _prologue:
		_local_player.face(_prologue.spawn_yaw(_local_player.global_position))
	_apply_loadout(_local_player)


## Рейд из убежища: снаряжение и рюкзак профиля уходят в рейд (на кону) — хост выдаёт их игроку.
func _apply_loadout(p: Player) -> void:
	if not Profile.pending_raid:
		return
	p.loadout_mode = true
	p.weapon_id = ""
	p.weapon_slot = ""
	p.ammo = 0
	# пролог: с собой через кордон — рюкзак и медицина; после гибели группы — набор с контрольной точки
	_raid.submit_loadout(_prologue.loadout() if _prologue else Profile.take_loadout())


## Навмеш печётся из коллайдеров и мешей сектора (двери не считаются — их AI открывает сам),
## в фоне; мародёры появляются, когда он готов.
func _bake_navmesh() -> void:
	if String(_sector_def.get("layout", "")) == "cartesian_scene":
		var urban_nav := UrbanNavigation.new()
		urban_nav.name = "NavRegion"
		urban_nav.definition = _sector_def
		urban_nav.ready_for_agents.connect(_on_nav_baked)
		get_node("Navigation").add_child(urban_nav)
		return
	var region := NavigationRegion3D.new()
	region.name = "NavRegion"
	var nm := NavigationMesh.new()
	nm.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	# целое стекло — стена для навигации; выбитое — проём (GlassPanes ставит связку)
	nm.geometry_collision_mask = Hitscan.LAYER_WORLD | Hitscan.LAYER_GLASS
	nm.geometry_source_geometry_mode = NavigationMesh.SOURCE_GEOMETRY_GROUPS_WITH_CHILDREN
	nm.geometry_source_group_name = "nav_source"
	nm.cell_size = 0.25
	nm.cell_height = 0.25
	nm.agent_height = 1.8
	nm.agent_radius = 0.5
	nm.agent_max_climb = 0.4
	nm.agent_max_slope = 40.0
	nm.region_min_size = 4.0
	nm.filter_baking_aabb = AABB(Vector3(-6, -1, -95), Vector3(140, 10, 190))
	if not _ring.is_empty():
		# весь участок кольца; по высоте — до крыши паркинга
		var site := float(_ring.get("site_r", 300.0)) + 5.0
		nm.filter_baking_aabb = AABB(Vector3(-site, -1, -site), Vector3(site * 2.0, 16, site * 2.0))
	region.navigation_mesh = nm
	add_child(region)
	region.bake_finished.connect(_on_nav_baked)
	region.bake_navigation_mesh(true)


func _on_nav_baked() -> void:
	# Испечённый меш попадает в карту на следующей синхронизации сервера — ждём её, иначе
	# map_get_closest_point вернёт мусор.
	if String(_sector_def.get("layout", "")) != "cartesian_scene":
		await NavigationServer3D.map_changed
	await get_tree().physics_frame
	_nav_baked = true
	print("sector: навмеш готов, регионов %d" % NavigationServer3D.map_get_regions(get_world_3d().navigation_map).size())
	# точки укрытия карты (tools/bake_cover_points.tscn) — рядом с кэшем навигации; мародёр смотрит их первыми
	var cover_n: int = Marauder.CoverPoints.load_for(get_world_3d(), String(_sector_def.get("nav_cache", "")))
	if cover_n > 0:
		print("sector: точек укрытия %d" % cover_n)
	# Мародёров спавнит только хост (или синглплеер) — клиенты получат их репликацией. Связки
	# «перелезть» нужны только там, где думает ИИ.
	if not Net.is_networked() or multiplayer.is_server():
		# связки строятся понемногу за кадр (без заминки) и до мародёров: карта навигации, сменившаяся
		# посреди боя, сбивает им пути
		var region := get_node_or_null("NavRegion") as NavigationRegion3D
		if region:
			var t0 := Time.get_ticks_msec()
			var n: int = await Vault.build_links(region, region)
			if n > 0:
				await NavigationServer3D.map_changed
			print("sector: связок «перелезть» %d за %d мс" % [n, Time.get_ticks_msec() - t0])
		await _spawn_marauders()


## Хост, навмеш готов: население рейда. Есть на карте точки слоёв — AIPopulation (гарнизоны, патрули,
## гнёзда, подход); нет — отряды по AI_SQUAD_SIZE рядом друг с другом, всего MARAUDER_COUNT.
func _spawn_marauders() -> void:
	# навигация из кэша синхронизируется не сразу — точки спавна должны на неё встать
	await _population.wait_navigation()
	# пролог: трое руками — двое в зале «Яруса», один на складе у рампы
	if _prologue:
		_prologue.spawn_marauders()
	if AIPopulation.has_points(get_tree()):
		# хотя бы один — иначе ждущие «мародёры расставлены» (чужие отряды, охрана) не дождутся
		_marauders_spawned = maxi(1, _population.spawn_start())
		_spawn_pending()
		return
	var placed := 0
	var tries := 0
	var squads := 0
	while placed < Balance.MARAUDER_COUNT and tries < 200:
		tries += 1
		var p := _random_room_point()
		var markers: Array[Node] = get_tree().get_nodes_in_group("ai_spawn_points")
		if not markers.is_empty():
			p = (markers[(tries - 1) % markers.size()] as Node3D).global_position
		if p.distance_to(_spawn) < Balance.MARAUDER_SPAWN_MIN_DIST:
			continue
		var snapped := NavigationServer3D.map_get_closest_point(get_world_3d().navigation_map, p)
		if snapped.distance_to(p) > 3.0 or _sees_spawn(snapped):
			continue
		# состав: один, двое или трое — по весам Balance.AI_SQUAD_WEIGHTS
		var wsum := 0.0
		for w in Balance.AI_SQUAD_WEIGHTS:
			wsum += float(w)
		var roll := _rng.randf() * wsum
		var size := 1
		for i in Balance.AI_SQUAD_WEIGHTS.size():
			roll -= float(Balance.AI_SQUAD_WEIGHTS[i])
			if roll <= 0.0:
				size = i + 1
				break
		size = mini(size, Balance.MARAUDER_COUNT - placed)
		# тип ведущего; снайпер ходит один, в отрядах снайперов нет
		var lead_arch := Marauder.pick_archetype(_rng)
		if bool(Balance.AI_ARCHETYPES[lead_arch].holds):
			size = 1
		var squad := Squad.new()
		squads += 1
		for k in range(size):
			var at := snapped
			if k > 0:
				var a := _rng.randf() * TAU
				at = NavigationServer3D.map_get_closest_point(get_world_3d().navigation_map, snapped + Vector3(cos(a), 0.0, sin(a)) * (1.2 + k))
			var arch := lead_arch
			while k > 0 and (arch == lead_arch and _rng.randf() < 0.4 or bool(Balance.AI_ARCHETYPES[arch].holds)):
				arch = Marauder.pick_archetype(_rng)
			squad.add(spawn_marauder(at, arch))
			placed += 1
	_marauders_spawned = placed
	_spawn_pending()
	print("sector: мародёров %d в %d отрядах, попыток %d" % [placed, squads, tries])


## Охрана и отряды, заказанные до готовности навмеша.
func _spawn_pending() -> void:
	for g in _pending_guards:
		spawn_guards(g[0], int(g[1]), float(g[2]))
	_pending_guards.clear()
	for q in _pending_squads:
		spawn_squad(q[0], q[1], q[2])
	_pending_squads.clear()


## Хост: один мародёр типа arch у точки at (на навигации); снаряжение — по выкладке типа
## (opts.loadout — задать явно), opts.home / home_r — держится у места. Клиентам его реплицирует спавнер.
func spawn_marauder(at: Vector3, arch: String, opts: Dictionary = {}) -> Marauder:
	var data := {"name": String(opts.get("name", "Marauder%d" % _marauder_seq)), "pos": at + Vector3(0, 0.1, 0),
		"loadout": String(opts.get("loadout", Marauder.loadout_for(arch, _rng))), "arch": arch}
	_marauder_seq += 1
	if opts.has("home"):
		data["home"] = opts.home
		data["home_r"] = float(opts.get("home_r", 6.0))
	var m: Marauder
	if _marauder_spawner:
		m = _marauder_spawner.spawn(data) as Marauder
	else:
		m = _spawn_marauder_node(data) as Marauder
		_marauders_root.add_child(m)
		m.global_position = data.pos
	m.patrol_point_provider = _random_room_point
	return m


## Где появляются игроки (точка рейда, выбранная хостом).
func spawn_pos() -> Vector3:
	return _spawn


## Видно ли точку появления игроков отсюда (население не ставит бойцов на виду у неё).
func sees_spawn(p: Vector3) -> bool:
	return _sees_spawn(p)


## Видно ли точку появления игрока отсюда (открыто и ближе SPAWN_SAFE.los_m): там мародёра не ставим.
func _sees_spawn(p: Vector3) -> bool:
	if p.distance_to(_spawn) > float(Balance.SPAWN_SAFE.los_m):
		return false
	var q := PhysicsRayQueryParameters3D.create(p + Vector3.UP * 1.6, _spawn + Vector3.UP * 1.6, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR)
	return get_world_3d().direct_space_state.intersect_ray(q).is_empty()


## Случайная точка внутри случайного «жилого» помещения сектора (с отступом от стен и полос);
## в начале рейда — не у точки появления игрока (SPAWN_SAFE).
func _random_room_point() -> Vector3:
	var safe: Dictionary = Balance.SPAWN_SAFE
	var early := (Time.get_ticks_msec() - _start_ms) / 1000.0 < float(safe.sec)
	for i in range(6):
		var p := _room_point()
		if not early or p.distance_to(_spawn) >= float(safe.radius):
			return p
	return _room_point()


func _room_point() -> Vector3:
	var candidates: Array = []
	for room in _rooms:
		if bool(room.get("locked", false)):
			continue
		if String(room.get("type", "")) in AI_ROOM_TYPES:
			candidates.append(room)
	if candidates.is_empty():
		return _spawn
	for i in range(8):
		var room: Dictionary = candidates[_rng.randi_range(0, candidates.size() - 1)]
		var p := SectorBuilder.random_point(room, _rooms, _rng, 1.5)
		if p != Vector3.INF:
			return p
	return _spawn



## Редактор: кольцо из JSON как превью (без дверей, пропсов и игроков) — видно, куда ставить постройки.
func _build_editor_preview() -> void:
	var old := get_node_or_null("_EditorPreview")
	if old:
		old.free()
	var sector := SectorBuilder.new().build(sector_path)
	sector.name = "_EditorPreview"
	# без owner — превью не сохраняется в .tscn
	add_child(sector)
	move_child(sector, 0)


## Перекрытие выше игрока не рисуется, но отбрасывает тень: изометрия смотрит сверху, иначе
## вместо игрока на нижнем уровне паркинга видна крыша. В прицеле (от первого лица) видно всё.
func _update_decks() -> void:
	var ads := _camera_rig.ads_active
	var eye_y := _local_player.global_position.y
	for d in get_tree().get_nodes_in_group("decks"):
		var deck := d as Node3D
		var hide := not ads and float(deck.get_meta("deck_y", 0.0)) > eye_y + Balance.DECK_HIDE_ABOVE
		if deck.has_meta("urban_cover_size"):
			var cover: Vector2 = deck.get_meta("urban_cover_size")
			var local: Vector3 = deck.to_local(_local_player.global_position)
			hide = not ads and float(deck.get_meta("deck_y", 0.0)) > eye_y + float(Balance.URBAN_WORLD.deck_margin)
			hide = hide and absf(local.x) < cover.x * 0.5 and absf(local.z) < cover.y * 0.5
		if bool(_decks_hidden.get(deck, false)) == hide:
			continue
		_decks_hidden[deck] = hide
		for c in deck.get_children():
			var mi := c as MeshInstance3D
			if mi:
				mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY if hide else GeometryInstance3D.SHADOW_CASTING_SETTING_ON


func _track_visit(delta: float) -> void:
	_visit_t -= delta
	if _visit_t > 0.0 or not Profile.pending_raid or not _local_player.is_alive():
		return
	_visit_t = 0.5
	var id := String(SectorBuilder.owner_of(_rooms, _local_player.global_position).get("id", ""))
	if id != "" and not _visited.has(id):
		_visited[id] = true
		Missions.on_visit(id)


func _process(_delta: float) -> void:
	if Engine.is_editor_hint() or not is_instance_valid(_local_player) or not _local_player.is_inside_tree():
		return
	_update_decks()
	_track_visit(_delta)
	# оружие, патроны и гранаты — в HUD камеры (CameraRig), здесь — здоровье
	var status := "HP %d" % int(_local_player.health.hp)
	# игровое время (смена суток): «18:46»
	if DayCycle.current:
		status += "     " + DayCycle.current.clock_text()
	if not _nav_baked:
		status += "   (навмеш печётся)"
	(_hud.get_node("Status") as Label).text = status
	# смерть, эвакуация и «R — новый рейд» — в Raid
