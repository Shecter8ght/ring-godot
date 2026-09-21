extends Node3D
## Сцена сектора: строит геометрию из данных, печёт навмеш, спавнит мародёров, ставит игрока.
## Свет и атмосферу задаёт WorldEnvironment/Sun в самой сцене — их можно крутить руками в редакторе.

const MARAUDER_SCENE := preload("res://scenes/ai/marauder.tscn")
## В каких помещениях мародёры появляются и патрулируют.
const AI_ROOM_TYPES := ["retail", "storage", "corridor", "gallery", "office", "security", "utility", "yard"]

@export_file("*.json") var sector_path: String = "res://data/sectors/f1_market.json"

var _rooms: Array = []
var _spawn: Vector3 = Vector3.ZERO
var _rng := RandomNumberGenerator.new()
var _nav_baked: bool = false

@onready var _player: Player = $Player
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
	if _player:
		_player.global_position = _spawn + Vector3(0, 0.05, 0)
		_player.health.died.connect(_on_player_died)
	_bake_navmesh()


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
	_spawn_marauders()


func _spawn_marauders() -> void:
	var holder := Node3D.new()
	holder.name = "Marauders"
	add_child(holder)
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
		var m := MARAUDER_SCENE.instantiate() as Marauder
		m.name = "Marauder%d" % placed
		m.patrol_point_provider = _random_room_point
		holder.add_child(m)
		m.global_position = snapped + Vector3(0, 0.1, 0)
		placed += 1
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
	_hud.get_node("Dead").visible = true


func _process(_delta: float) -> void:
	if _player == null:
		return
	var status := "HP %d   Патроны %d/%d" % [int(_player.health.hp), _player.ammo, int(Balance.PISTOL.mag)]
	if _player.reload_timer > 0.0:
		status += "   перезарядка…"
	if not _nav_baked:
		status += "   (навмеш печётся)"
	(_hud.get_node("Status") as Label).text = status
	if not _player.is_alive() and Input.is_action_just_pressed("reload"):
		get_tree().reload_current_scene()
