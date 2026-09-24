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

@export_file("*.json") var sector_path: String = "res://data/sectors/f1_market.json":
	set(v):
		sector_path = v
		if Engine.is_editor_hint() and is_inside_tree():
			_build_editor_preview.call_deferred()

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
var _ring: Dictionary = {}
var _raid: Raid
## Перекрытия, спрятанные над игроком (паркинг, навесы): остаются только тенью.
var _decks_hidden: Dictionary = {}
## Где был свой игрок (задания «побывать в помещении»): проверка раз в полсекунды.
var _visit_t: float = 0.0
var _visited: Dictionary = {}

@onready var _camera_rig: CameraRig = $CameraRig
@onready var _hud: Control = $HUD/Root


func _ready() -> void:
	if Engine.is_editor_hint():
		_build_editor_preview()
		return
	_rng.randomize()
	var t0 := Time.get_ticks_msec()
	var builder := SectorBuilder.new()
	# узлы сцены, под которыми пропсов быть не должно (эскалаторы) — уже в дереве: дети готовы раньше
	for k in get_tree().get_nodes_in_group("prop_keepout"):
		if k.has_method("keepout_rect"):
			builder.keepouts.append(k.call("keepout_rect"))
	var sector := builder.build(sector_path)
	print("sector: собран за %d мс (пропсов %d, склеено в %d мешей)" % [Time.get_ticks_msec() - t0, int(sector.get_meta("prop_count", 0)), int(sector.get_meta("prop_batches", 0))])
	sector.add_to_group("nav_source")
	add_child(sector)
	move_child(sector, 0)
	_rooms = sector.get_meta("rooms", [])
	_spawn = sector.get_meta("spawn", Vector3.ZERO)
	_ring = sector.get_meta("ring", {})
	# карта этажа на M (только у кольца — у старого сектора плана нет)
	if not _ring.is_empty():
		var map := MapView.new()
		map.name = "Map"
		var ang: Array = SectorBuilder.load_def(sector_path).get("angle", [-180, 0])
		map.setup(_rooms, _ring, Vector2(float(ang[0]), float(ang[1])))
		add_child(map)
	# точка появления из сцены уровня (узлы SpawnPoint) — одна случайная на рейд
	var points := get_tree().get_nodes_in_group("spawn_points")
	if not points.is_empty():
		_spawn = (points[_rng.randi_range(0, points.size() - 1)] as Node3D).global_position
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
	_raid.register(1, "Ты")
	_local_player = p
	_apply_loadout(p)
	_camera_rig.set_target(p)
	_face_center(p.global_position)


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
	m.weapon = String(data.get("weapon", ""))
	m.archetype = String(data.get("arch", ""))
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
	_raid.register(peer_id, String(Net.player_names.get(peer_id, "Игрок %d" % peer_id)))


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
	_face_center(_local_player.global_position)
	_apply_loadout(_local_player)


## Рейд из убежища: снаряжение и рюкзак профиля уходят в рейд (на кону) — хост выдаёт их игроку.
func _apply_loadout(p: Player) -> void:
	if not Profile.pending_raid:
		return
	p.loadout_mode = true
	p.weapon_id = ""
	p.ammo = 0
	_raid.submit_loadout(Profile.take_loadout())


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
	await NavigationServer3D.map_changed
	await get_tree().physics_frame
	_nav_baked = true
	print("sector: навмеш готов, регионов %d" % NavigationServer3D.map_get_regions(get_world_3d().navigation_map).size())
	# Мародёров спавнит только хост (или синглплеер) — клиенты получат их репликацией.
	if not Net.is_networked() or multiplayer.is_server():
		_spawn_marauders()


## Отряды по AI_SQUAD_SIZE рядом друг с другом; оружие каждому — по долям AI_WEAPONS.
func _spawn_marauders() -> void:
	var placed := 0
	var tries := 0
	var squads := 0
	while placed < Balance.MARAUDER_COUNT and tries < 200:
		tries += 1
		var p := _random_room_point()
		if p.distance_to(_spawn) < Balance.MARAUDER_SPAWN_MIN_DIST:
			continue
		var snapped := NavigationServer3D.map_get_closest_point(get_world_3d().navigation_map, p)
		if snapped.distance_to(p) > 3.0:
			continue
		var size := mini(_rng.randi_range(int(Balance.AI_SQUAD_SIZE[0]), int(Balance.AI_SQUAD_SIZE[1])), Balance.MARAUDER_COUNT - placed)
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
			var wpn := Marauder.weapon_for(arch, _rng)
			var m: Marauder
			if _marauder_spawner:
				m = _marauder_spawner.spawn({"name": "Marauder%d" % placed, "pos": at + Vector3(0, 0.1, 0), "weapon": wpn, "arch": arch}) as Marauder
			else:
				m = MARAUDER_SCENE.instantiate() as Marauder
				m.name = "Marauder%d" % placed
				m.weapon = wpn
				m.archetype = arch
				_marauders_root.add_child(m)
				m.global_position = at + Vector3(0, 0.1, 0)
			m.patrol_point_provider = _random_room_point
			squad.add(m)
			placed += 1
	_marauders_spawned = placed
	print("sector: мародёров %d в %d отрядах, попыток %d" % [placed, squads, tries])


## Случайная точка внутри случайного «жилого» помещения сектора (с отступом от стен и полос).
func _random_room_point() -> Vector3:
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
	if Engine.is_editor_hint() or _local_player == null:
		return
	_update_decks()
	_track_visit(_delta)
	# оружие, патроны и гранаты — в HUD камеры (CameraRig), здесь — здоровье
	var status := "HP %d" % int(_local_player.health.hp)
	if not _nav_baked:
		status += "   (навмеш печётся)"
	(_hud.get_node("Status") as Label).text = status
	# смерть, эвакуация и «R — новый рейд» — в Raid
