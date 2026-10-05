extends Node
## Реальный рейд на городской карте: физика, маршруты AI, взаимодействия, лут и эвакуация.

var _fails: int = 0
var _level: Node3D
var _player: Player
var _definition: Dictionary


func _ready() -> void:
	Profile.use_file("user://profile_zone02_world_test.json", true)
	Profile.pending_raid = false
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	_definition = SectorBuilder.load_def("res://data/sectors/zone02_urban_belt.json")
	_level = (load("res://scenes/levels/zone02_urban_belt.tscn") as PackedScene).instantiate() as Node3D
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	var start_ms: int = Time.get_ticks_msec()
	while not bool(_level.get("_nav_baked")):
		if Time.get_ticks_msec() - start_ms > 120000:
			_check("навмеш готов за ограниченное время", false)
			get_tree().quit(1)
			return
		await get_tree().process_frame
	_player = Raid.current.local_player()
	_player.health.invulnerable = true
	CameraRig.first_person_mode = false
	Input.action_release("aim")
	for enemy in _level.get_node("Marauders").get_children():
		enemy.set_physics_process(false)
	_check("существующий Player в масштабе 1:1", _player != null and _player.scale == Vector3.ONE)
	var bounds: Array = _definition.bounds
	_check("границы 1500 × 1250 м, площадь 1.85–1.95 км²", float(bounds[2]) - float(bounds[0]) == 1500 and float(bounds[3]) - float(bounds[1]) == 1250 and float(_definition.area_m2) >= 1850000.0 and float(_definition.area_m2) <= 1950000.0)
	_check("основные районы существуют отдельными сценами", _level.get_node("Districts").get_child_count() == 7)
	_check("12 тестовых AI-точек", get_tree().get_nodes_in_group("ai_spawn_points").size() == 12)
	_check("существующий AI заселил карту", _level.get_node("Marauders").get_child_count() == Balance.MARAUDER_COUNT)
	_check("погода, свет, события и квестовая инфраструктура существуют", RaidWeather.current != null and RaidAtmosphere.current != null and RaidEvents.current != null and Quests.world != null)
	_check("карта M подключена", _level.get_node_or_null("Map") is MapView)
	var nav_map: RID = _level.get_world_3d().navigation_map
	_check("30 навигационных районов", NavigationServer3D.map_get_regions(nav_map).size() == 30)
	_test_street_clearance()
	_test_perimeter()
	_test_power()
	_test_conditions()
	await _test_indoor()
	var origin: Vector3 = NavigationServer3D.map_get_closest_point(nav_map, _player.global_position)
	for marker in get_tree().get_nodes_in_group("ai_spawn_points"):
		_check_route(nav_map, origin, (marker as Node3D).global_position, String(marker.name))
	var extractions: Array[Node] = get_tree().get_nodes_in_group("extractions")
	_check("три штатных выхода", extractions.size() == 3)
	for extraction in extractions:
		var point := extraction as ExtractionPoint
		_check_route(nav_map, origin, point.global_position, point.display_name)
		_check("выход открыт: " + point.display_name, Raid.current.extraction_block_reason(point) == "")
	for sample in [Vector2(0, -560), Vector2(-540, -365), Vector2(-512, -140), Vector2(20, -100), Vector2(0, 170), Vector2(400, 240), Vector2(410, -280), Vector2(560, 20), Vector2(-20, 535)]:
		var hit: Dictionary = _floor_hit(sample)
		_check("физический пол в %s" % str(sample), not hit.is_empty() and (hit.normal as Vector3).y > 0.7)
		if not hit.is_empty():
			var point: Vector3 = hit.position
			var snapped: Vector3 = NavigationServer3D.map_get_closest_point(nav_map, point)
			_check("физика совпадает с навигацией в %s" % str(sample), snapped.distance_to(point) < 2.0)
	await _test_ai_movement(nav_map)
	await _test_player_movement()
	await _test_interactions()
	await _test_extraction(extractions.back() as ExtractionPoint)
	print("zone02_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _test_street_clearance() -> void:
	var overlaps: Array[String] = []
	for building: Dictionary in _definition.buildings:
		if String(building.category) == "checkpoint":
			continue
		var center := Vector2(float(building.center[0]), float(building.center[1]))
		var size := Vector2(float(building.size[0]), float(building.size[1]))
		for road: Dictionary in _definition.roads:
			var margin: float = float(road.width) * 0.5 + float(road.sidewalk)
			var rect := Rect2(center - size * 0.5, size).grow(margin)
			var corners := PackedVector2Array([rect.position, Vector2(rect.end.x, rect.position.y), rect.end, Vector2(rect.position.x, rect.end.y)])
			for index: int in range(road.points.size() - 1):
				var from := Vector2(float(road.points[index][0]), float(road.points[index][1]))
				var to := Vector2(float(road.points[index + 1][0]), float(road.points[index + 1][1]))
				var crossed: bool = rect.has_point(from) or rect.has_point(to)
				for edge: int in range(4):
					crossed = crossed or Geometry2D.segment_intersects_segment(from, to, corners[edge], corners[(edge + 1) % 4]) != null
				if crossed:
					overlaps.append(String(building.name) + "/" + String(road.id))
					break
	_check("улицы и тротуары не пересекают корпуса зданий", overlaps.is_empty())
	if not overlaps.is_empty():
		print("    пересечения: ", overlaps)


func _test_perimeter() -> void:
	var terrain: UrbanTerrain = _level.get_node("World/Terrain") as UrbanTerrain
	var gaps: Array[String] = []
	for node: Node in _level.get_node("World/Perimeter/Props").get_children():
		var wall: UrbanProps = node as UrbanProps
		if wall == null or not String(wall.name).begins_with("Wall_"):
			continue
		for piece: Dictionary in wall.pieces:
			if not bool(piece.get("collision", false)):
				continue
			var center: Vector3 = wall.to_global(UrbanProps.vec(piece.at))
			var normal: Vector3 = wall.global_basis.z.normalized()
			var from: Vector3 = center - normal * 1.5
			var to: Vector3 = center + normal * 1.5
			# На береговом откосе луч должен идти над обеими сторонами земли, не внутри HeightMap.
			center.y = maxf(terrain.sample_height(from.x, from.z), terrain.sample_height(to.x, to.z)) + 0.2
			var query := PhysicsRayQueryParameters3D.create(center - normal * 1.5, center + normal * 1.5, Hitscan.LAYER_WORLD)
			var hit: Dictionary = _level.get_world_3d().direct_space_state.intersect_ray(query)
			if hit.is_empty() or not wall.is_ancestor_of(hit.collider as Node):
				gaps.append(String(wall.name))
	_check("периметр закрыт у земли на наклонном рельефе", gaps.is_empty())
	if not gaps.is_empty():
		print("    щели: ", gaps)


func _test_power() -> void:
	var lights: Array[Node] = get_tree().get_nodes_in_group("mall_lights")
	_check("уличные и внутренние светильники подключены к штатному питанию", lights.size() >= 40)
	RaidAtmosphere.current.apply_power("off")
	var all_off: bool = true
	for node: Node in lights:
		all_off = all_off and not (node as Light3D).visible
	_check("отключение питания гасит все светильники района", all_off)
	RaidAtmosphere.current.apply_power("on")
	var all_on: bool = true
	for node: Node in lights:
		all_on = all_on and (node as Light3D).visible
	_check("возвращение питания зажигает все светильники района", all_on)


func _test_conditions() -> void:
	var conditions: Dictionary = RaidConditions.current.duplicate(true)
	var day_energy: float = (_level.get_node("Sun") as DirectionalLight3D).light_energy
	RaidConditions.current = {"time": "night", "weather": "rain", "power": "on"}
	RaidAtmosphere.current.apply()
	RaidWeather.current._apply_static()
	_check("штатная ночь меняет свет на городской карте", (_level.get_node("Sun") as DirectionalLight3D).light_energy < day_energy)
	_check("штатный дождь создаёт RainFx на городской карте", RaidWeather.current.is_raining() and RaidWeather.current._rain != null)
	RaidConditions.current.weather = "fog"
	RaidWeather.current._apply_static()
	_check("штатный туман меняет видимость и прекращает дождь", not RaidWeather.current.is_raining() and RaidWeather.current._fog_target > 0.006)
	RaidConditions.current = conditions
	RaidAtmosphere.current.apply()
	RaidWeather.current._apply_static()


func _test_indoor() -> void:
	var building: BlockoutBuilding = _level.get_node("Districts/Residential/Buildings/R01") as BlockoutBuilding
	var position: Vector3 = building.global_position + Vector3.UP * 0.1
	_check("перекрытие жилого дома распознаётся штатной погодой как помещение", RaidAtmosphere.current.is_indoor(position))
	var before: Vector3 = _player.global_position
	_player.global_position = position
	_player.velocity = Vector3.ZERO
	await get_tree().physics_frame
	_level._update_decks()
	var ceiling: Node3D = building.get_node("Facade/_Generated/FirstFloorCeiling") as Node3D
	var hidden: bool = true
	for child: Node in ceiling.get_children():
		if child is MeshInstance3D:
			hidden = hidden and (child as MeshInstance3D).cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
	_check("потолок над игроком скрыт в штатной изометрии", hidden)
	_player.global_position = before
	_player.velocity = Vector3.ZERO
	await get_tree().physics_frame


func _test_ai_movement(map: RID) -> void:
	var enemy: Marauder = _level.get_node("Marauders").get_child(0) as Marauder
	var squad: Squad = enemy.squad
	enemy.squad = null
	var floor: Dictionary = _floor_hit(Vector2(0, -520))
	if floor.is_empty():
		_check("пол для движения AI существует", false)
		return
	enemy.global_position = floor.position
	var before: Vector3 = enemy.global_position
	var agent: NavigationAgent3D = enemy.get_node("NavigationAgent3D") as NavigationAgent3D
	agent.target_position = NavigationServer3D.map_get_closest_point(map, before + Vector3(22, 0, 0))
	enemy.pause_timer = 20.0
	enemy.set_physics_process(true)
	for index: int in range(180):
		await get_tree().physics_frame
	enemy.set_physics_process(false)
	enemy.squad = squad
	var moved: float = Vector2(enemy.global_position.x - before.x, enemy.global_position.z - before.z).length()
	_check("штатный AI идёт по навмешу и пересекает бордюр: %.2f м" % moved, moved > 3.0 and enemy.is_on_floor())


func _check_route(map: RID, from: Vector3, target: Vector3, title: String) -> void:
	var end: Vector3 = NavigationServer3D.map_get_closest_point(map, target)
	var path: PackedVector3Array = NavigationServer3D.map_get_path(map, from, end, true)
	var ok: bool = end.distance_to(target) < 3.0 and path.size() > 1 and path[path.size() - 1].distance_to(end) < 1.0
	_check("сквозной маршрут: " + title, ok)
	if not ok:
		print("    начало %s, цель %s, привязка %s, конец %s" % [str(from), str(target), str(end), str(path[path.size() - 1]) if not path.is_empty() else "пусто"])


func _floor_hit(xz: Vector2) -> Dictionary:
	var query := PhysicsRayQueryParameters3D.create(Vector3(xz.x, 9, xz.y), Vector3(xz.x, -15, xz.y), Hitscan.LAYER_WORLD)
	return _level.get_world_3d().direct_space_state.intersect_ray(query)


func _put_player(position: Vector3) -> void:
	_player.global_position = position + Vector3.UP * 0.15
	_player.velocity = Vector3.ZERO
	for index in range(15):
		await get_tree().physics_frame


func _test_player_movement() -> void:
	var hit: Dictionary = _floor_hit(Vector2(0, -560))
	if hit.is_empty():
		return
	await _put_player(hit.position)
	(_level.get_node("CameraRig") as Node3D).rotation.y = 0.0
	var before: Vector3 = _player.global_position
	Input.action_press("move_forward")
	for index in range(120):
		await get_tree().physics_frame
	Input.action_release("move_forward")
	var distance: float = Vector2(_player.global_position.x - before.x, _player.global_position.z - before.z).length()
	_check("штатная ходьба в метрах: %.2f м за 2 с" % distance, distance > Balance.PLAYER_WALK_SPEED * 1.6 and distance < Balance.PLAYER_WALK_SPEED * 2.4)
	_check("игрок стоит на наклонной улице", _player.is_on_floor())


func _test_interactions() -> void:
	var doors: Array[Node] = _level.find_children("*", "Door", true, false)
	_check("штатные двери присутствуют", doors.size() > 40)
	if not doors.is_empty():
		var door := doors[0] as Door
		door.toggle(door.global_position + Vector3(0, 0, -1))
		_check("существующая дверь открывается", door.is_open)
	var containers: Array[Node] = get_tree().get_nodes_in_group("loot_containers")
	_check("штатные контейнеры во всех основных районах", containers.size() >= 17)
	if not containers.is_empty():
		var container := containers[0] as LootContainer
		container.roll()
		_check("лут использует существующие таблицы и сетку", container.rolled and container.grid.x > 0)
		if container.items.is_empty():
			container.items = [{"id": "bandage", "n": 1, "x": 0, "y": 0, "r": false}]
		await _put_player(container.global_position + Vector3(1.4, 0, 0))
		var item_id: String = String(container.items[0].id)
		var before: int = _player.inventory.count(item_id)
		Raid.current.request_take(container, item_id, 1)
		_check("взятие лута идёт через Raid в Inventory", _player.inventory.count(item_id) == before + 1)
	var breaker: Node = _level.find_child("GridBreaker", true, false)
	breaker.call("_use", 1)
	_check("существующий рубильник меняет свет района", RaidEvents.current.breaker == "off")


func _test_extraction(point: ExtractionPoint) -> void:
	await _put_player(point.global_position)
	var start_ms: int = Time.get_ticks_msec()
	while not Raid.current.is_extracted(1) and Time.get_ticks_msec() - start_ms < 15000:
		await get_tree().physics_frame
	_check("тестовый рейд завершился через существующую эвакуацию", Raid.current.is_extracted(1) and Raid.current.over)
	_check("хроника рейда сформирована штатной системой", Raid.current.chronicle != null)


func _check(title: String, ok: bool) -> void:
	print("%s zone02: %s" % ["OK" if ok else "FAIL", title])
	if not ok:
		_fails += 1
