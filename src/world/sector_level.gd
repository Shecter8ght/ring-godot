extends Node3D
## Сцена сектора: строит геометрию из данных, печёт навмеш, спавнит игроков и мародёров.
## Свет и атмосферу задаёт WorldEnvironment/Sun в самой сцене — их можно крутить руками в редакторе.
##
## Сеть: без активного MultiplayerPeer (запуск из редактора, tools/*.tscn) спавнится один
## локальный игрок как раньше — все тестовые сцены и smoke-прогоны продолжают работать без
## изменений. С сетью — хост создаёт по Player на каждый peer (см. Net.PORT/MAX_PLAYERS) через
## MultiplayerSpawner, чтобы узел реплицировался остальным; мародёров хост спавнит так же.
## Авторитет см. в AGENTS.md: у Player — владеющий peer (кроме Health), у Marauder/Door — хост.

const PLAYER_SCENE := preload("res://scenes/player/player.tscn")
const MARAUDER_SCENE := preload("res://scenes/ai/marauder.tscn")
## В каких помещениях мародёры появляются и патрулируют.
const AI_ROOM_TYPES := ["retail", "storage", "corridor", "gallery", "office", "security", "utility", "yard"]

@export_file("*.json") var sector_path: String = "res://data/sectors/f1_market.json"

var _rooms: Array = []
var _spawn: Vector3 = Vector3.ZERO
var _rng := RandomNumberGenerator.new()
var _nav_baked: bool = false
var _local_player: Player = null
var _players_root: Node3D
var _marauders_root: Node3D
var _player_spawner: MultiplayerSpawner
var _marauder_spawner: MultiplayerSpawner
var _marauders_spawned: int = 0

@onready var _camera_rig: CameraRig = $CameraRig
@onready var _hud: Control = $HUD/Root


func _ready() -> void:
	_rng.randomize()
	var builder := SectorBuilder.new()
	var sector := builder.build(sector_path)
	sector.add_to_group("nav_source")
	add_child(sector)
	move_child(sector, 0)
	_rooms = sector.get_meta("rooms", [])
	_spawn = sector.get_meta("spawn", Vector3.ZERO)
	# Камера смотрит от атриума наружу: так витрины галереи обращены к камере, а не спиной.
	if _camera_rig and sector.has_meta("camera_yaw"):
		_camera_rig.rotation_degrees.y = float(sector.get_meta("camera_yaw"))

	# Контейнеры существуют всегда (offline-инструменты ищут "Marauders" по имени) — спавнеры
	# навешиваются на них только при активной сети.
	_players_root = Node3D.new()
	_players_root.name = "Players"
	add_child(_players_root)
	_marauders_root = Node3D.new()
	_marauders_root.name = "Marauders"
	add_child(_marauders_root)

	if not Net.is_networked():
		_spawn_offline_player()
	else:
		_setup_spawners()
		if multiplayer.is_server():
			_spawn_networked_players()
			multiplayer.peer_connected.connect(_on_peer_connected_late)
		multiplayer.peer_disconnected.connect(_on_peer_disconnected)
		_find_local_player_when_ready()
	_bake_navmesh()


## Без сети — один игрок на месте спавна, как раньше (для tools/*.tscn и запуска из редактора).
func _spawn_offline_player() -> void:
	var p := PLAYER_SCENE.instantiate() as Player
	p.name = "Player_1"
	p.peer_id = 1
	_players_root.add_child(p)
	p.global_position = _spawn + Vector3(0, 0.05, 0)
	p.health.died.connect(_on_player_died)
	_local_player = p
	_camera_rig.set_target(p)


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
	return m


## Хост: по игроку на каждый уже подключённый peer (себя и остальных из лобби).
func _spawn_networked_players() -> void:
	var ids: Array = [1]
	for id in multiplayer.get_peers():
		ids.append(id)
	for i in range(ids.size()):
		_spawn_one_player(int(ids[i]), i)


func _spawn_one_player(peer_id: int, index: int) -> void:
	var offset := Vector3(cos(index * TAU / 3.0), 0.0, sin(index * TAU / 3.0)) * 1.3
	var pos := _spawn + offset + Vector3(0, 0.05, 0)
	var node := _player_spawner.spawn({"peer_id": peer_id, "pos": pos}) as Player
	node.health.died.connect(_on_player_died)


## Присоединился уже во время рейда (лобби этого не предполагает, но не должно ломаться).
func _on_peer_connected_late(id: int) -> void:
	if not multiplayer.is_server():
		return
	var count := _players_root.get_child_count()
	_spawn_one_player(id, count)


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
		for p in get_tree().get_nodes_in_group("players"):
			if (p as Player).peer_id == my_id:
				_local_player = p
				break
		if _local_player == null:
			await get_tree().process_frame
	_camera_rig.set_target(_local_player)


## Навмеш печётся из коллайдеров и мешей сектора (двери не считаются — их AI открывает сам),
## в фоне; мародёры появляются, когда он готов.
func _bake_navmesh() -> void:
	var region := NavigationRegion3D.new()
	region.name = "NavRegion"
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
	nm.agent_max_slope = 40.0
	nm.region_min_size = 4.0
	nm.filter_baking_aabb = AABB(Vector3(-6, -1, -95), Vector3(140, 10, 190))
	region.navigation_mesh = nm
	add_child(region)
	region.bake_finished.connect(_on_nav_baked)
	region.bake_navigation_mesh(true)


func _on_nav_baked() -> void:
	# Испечённый меш попадает в карту на следующей синхронизации сервера — ждём её, иначе
	# map_get_closest_point вернёт мусор.
	await NavigationServer3D.map_changed
	await get_tree().physics_frame
	_nav_baked = true
	print("sector: навмеш готов, регионов %d" % NavigationServer3D.map_get_regions(get_world_3d().navigation_map).size())
	# Мародёров спавнит только хост (или синглплеер) — клиенты получат их репликацией.
	if not Net.is_networked() or multiplayer.is_server():
		_spawn_marauders()


func _spawn_marauders() -> void:
	var placed := 0
	var tries := 0
	while placed < Balance.MARAUDER_COUNT and tries < 200:
		tries += 1
		var p := _random_room_point()
		if p.distance_to(_spawn) < Balance.MARAUDER_SPAWN_MIN_DIST:
			continue
		var snapped := NavigationServer3D.map_get_closest_point(get_world_3d().navigation_map, p)
		if snapped.distance_to(p) > 3.0:
			continue
		var m: Marauder
		if _marauder_spawner:
			m = _marauder_spawner.spawn({"name": "Marauder%d" % placed, "pos": snapped + Vector3(0, 0.1, 0)}) as Marauder
		else:
			m = MARAUDER_SCENE.instantiate() as Marauder
			m.name = "Marauder%d" % placed
			_marauders_root.add_child(m)
			m.global_position = snapped + Vector3(0, 0.1, 0)
		m.patrol_point_provider = _random_room_point
		placed += 1
	_marauders_spawned = placed
	print("sector: мародёров %d, попыток %d" % [placed, tries])


## Случайная точка внутри случайного «жилого» помещения сектора (полярные границы с отступом).
func _random_room_point() -> Vector3:
	var candidates: Array = []
	for room in _rooms:
		if bool(room.get("locked", false)):
			continue
		if String(room.get("type", "")) in AI_ROOM_TYPES:
			candidates.append(room)
	if candidates.is_empty():
		return _spawn
	var room: Dictionary = candidates[_rng.randi_range(0, candidates.size() - 1)]
	var r := _rng.randf_range(float(room.r[0]) + 1.5, float(room.r[1]) - 1.5)
	var pad := rad_to_deg(1.5 / maxf(r, 1.0))
	var a := _rng.randf_range(float(room.a[0]) + pad, float(room.a[1]) - pad)
	return SectorBuilder.polar(a, r)


func _on_player_died() -> void:
	if _local_player and not _local_player.is_alive():
		_hud.get_node("Dead").visible = true


func _process(_delta: float) -> void:
	if _local_player == null:
		return
	# оружие, патроны и гранаты — в HUD камеры (CameraRig), здесь — здоровье
	var status := "HP %d" % int(_local_player.health.hp)
	if not _nav_baked:
		status += "   (навмеш печётся)"
	(_hud.get_node("Status") as Label).text = status
	if not _local_player.is_alive() and Input.is_action_just_pressed("reload") and not Net.is_networked():
		get_tree().reload_current_scene()
