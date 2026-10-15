extends Node
## Реальные коллизии, доступ к добыче и связность первого игрового фрагмента.

var failures: int = 0
var checks: int = 0
var level: Node3D
var probe: Player
var map: RID


func _ready() -> void:
	Profile.use_file("user://zone01_nw_test.json", true)
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	level = (load("res://scenes/levels/zone01_mall.tscn") as PackedScene).instantiate() as Node3D
	level.set_script(null)
	add_child(level)
	await get_tree().physics_frame
	await get_tree().physics_frame
	probe = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	probe.name = "GeometryProbe"
	probe.position = Vector3(-216.8, 1, -129)
	add_child(probe)
	probe.set_physics_process(false)
	probe.set_process(false)
	await get_tree().physics_frame
	var containers: Array[Node] = get_tree().get_nodes_in_group("loot_containers")
	var regular: int = 0
	var loose: int = 0
	for node: Node in containers:
		var container := node as LootContainer
		if container is LooseLoot:
			loose += 1
			check("находка доступна: " + String(container.name), _has_standing_place(container))
			var support: Dictionary = ray(container.global_position + Vector3.UP * .12, container.global_position - Vector3.UP * .25)
			check("находка на опоре: " + String(container.name), not support.is_empty() and absf((support.position as Vector3).y - container.global_position.y) < .12)
		else:
			regular += 1
			check("есть место для обыска: " + String(container.name), _has_standing_place(container))
	check("18 тематических мест обыска", regular == 18)
	check("24 точки россыпи внутри фрагмента", loose == 24)
	for floor_index in range(5):
		var floor_y: float = .3731 + 1.1 + 2.8 * floor_index
		var hit: Dictionary = ray(Vector3(-216.8, floor_y + .6, -137.1), Vector3(-216.8, floor_y - .4, -137.1))
		check("плита площадки " + str(floor_index + 1), not hit.is_empty() and absf((hit.position as Vector3).y - floor_y) < .03)
	var cellar: Dictionary = ray(Vector3(-220, -.7, -140), Vector3(-220, -2.2, -140))
	check("грунт не закрывает пол подвала", not cellar.is_empty() and absf((cellar.position as Vector3).y + 1.3269) < .04)
	var panel_roof: Dictionary = ray(Vector3(-216.8,20,-135),Vector3(-216.8,14,-135))
	check("кровля закрывает верхнюю лестничную клетку от дождя", not panel_roof.is_empty() and (panel_roof.position as Vector3).y > 15.4)
	var hangar: Node3D = level.get_node("Blockout/Z06_Market/Architecture/Hangar") as Node3D
	var roof: Dictionary = ray(hangar.to_global(Vector3(1, 12, 0)), hangar.to_global(Vector3(1, 0, 0)))
	check("крыша ангара физическая, дождь её видит", not roof.is_empty() and (roof.position as Vector3).y > hangar.global_position.y + 8)
	var house: Node3D = level.get_node("Blockout/Z12_Ravine/Architecture/House_0") as Node3D
	roof = ray(house.to_global(Vector3(0, 10, 0)), house.to_global(Vector3(0, 0, 0)))
	check("крыша дома физическая", not roof.is_empty() and (roof.position as Vector3).y > house.global_position.y + 5.5)
	# Этот сундук нельзя достать сквозь стену между комнатами даже в радиусе взаимодействия.
	var kitchen: LootContainer = level.get_node("Blockout/Z12_Ravine/Architecture/House_0/HouseKitchenSearch") as LootContainer
	probe.global_position = house.to_global(Vector3(-2.25, .27, -2.5))
	check("кухню можно обыскать со своей стороны", kitchen.reachable_from(probe))
	probe.global_position = house.to_global(Vector3(.8, .27, -3.3))
	check("стена запрещает обыск соседней комнаты", not kitchen.reachable_from(probe))
	var navigation := UrbanNavigation.new()
	var atmosphere := RaidAtmosphere.new()
	level.add_child(atmosphere)
	var interior_lights: Array[Node] = get_tree().get_nodes_in_group("mall_lights")
	atmosphere.apply_power("off")
	check("новый интерьерный свет гаснет без питания", interior_lights.size() >= 32 and interior_lights.all(func(n: Node) -> bool: return not (n as Light3D).visible))
	atmosphere.apply_power("on")
	check("интерьерный свет возвращается с питанием", interior_lights.all(func(n: Node) -> bool: return (n as Light3D).visible))
	atmosphere.queue_free()
	navigation.definition = SectorBuilder.load_def("res://data/sectors/zone01_mall.json")
	level.get_node("Navigation").add_child(navigation)
	await navigation.ready_for_agents
	map = level.get_world_3d().navigation_map
	var start := Vector3(-216.8, .6, -129.8)
	_path("двор → пятый этаж", start, Vector3(-216.8, 12.6731, -137.1))
	_path("двор → подвал", start, Vector3(-220, -1.3269, -140))
	_path("двор → рынок", Vector3(-196, .5, -62), Vector3(-171, .5, 4))
	_path("ангар → контора", hangar.to_global(Vector3(0, 0, -18)), hangar.to_global(Vector3(-7.5, 3.61, 15)))
	_path("рынок → дома", Vector3(-230, .5, 35), house.to_global(Vector3(-2.1, .27, 3.2)))
	_path("дом → чердак", house.to_global(Vector3(-2.1, .27, 3.2)), house.to_global(Vector3(-.7, 3.1, .8)))
	_path("прихожая → лестничная комната", house.to_global(Vector3(-2.1,.27,3.2)), house.to_global(Vector3(2.6,.27,3.1)))
	_path("лестничная комната → начало марша", house.to_global(Vector3(2.6,.27,3.1)), house.to_global(Vector3(.85,.27,-3.9)))
	var second_house: Node3D = level.get_node("Blockout/Z12_Ravine/Architecture/House_1") as Node3D
	_path("второй дом → мансарда", second_house.to_global(Vector3(-2.1,.27,3.2)), second_house.to_global(Vector3(-.7,3.1,.8)))
	_path("дома → мост", Vector3(-305, .5, 35), Vector3(-360, .5, 36))
	_path("мост → эвакуация", Vector3(-360,.5,36), Vector3(-386,.3705,40))
	_path("двор → путепровод", Vector3(-196,.5,-62), Vector3(0,.32,-206))
	if OS.get_environment("NW_SKIP_WALK") == "1":
		print("zone01_nw_test: checks=", checks, " failures=", failures)
		get_tree().quit(1 if failures else 0)
		return
	# Настоящая капсула Player и его шаг без прыжка: вход и все пять этажей.
	var path := PackedVector3Array([start, Vector3(-216.8,.6731,-131.5),Vector3(-216.8,.6731,-133.0),
		Vector3(-216.03,.6731,-133.8),Vector3(-216.03,1.4731,-137.1)])
	for floor_index in range(4):
		var y: float = 1.4731+2.8*floor_index
		path.append_array(PackedVector3Array([Vector3(-217.57,y,-137.1),Vector3(-217.57,y+1.4,-133.2),
			Vector3(-216.03,y+1.4,-133.16),Vector3(-216.03,y+2.8,-137.1)]))
	await _walk(path)
	var house_path := PackedVector3Array()
	for point: Vector3 in [Vector3(-2.1,.27,3.2),Vector3(2.6,.27,3.1),Vector3(2.6,.27,-3.9),
		Vector3(.85,.27,-3.9),Vector3(.85,3.1,2.45),Vector3(-.7,3.1,2.45),Vector3(-.7,3.1,.8)]:
		house_path.append(house.to_global(point))
	await _walk(house_path,"игрок поднимается на чердак без прыжка")
	print("zone01_nw_test: checks=", checks, " failures=", failures)
	get_tree().quit(1 if failures else 0)


func ray(from: Vector3, to: Vector3) -> Dictionary:
	return level.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(from, to, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR))


func _has_standing_place(container: LootContainer) -> bool:
	var capsule := CapsuleShape3D.new()
	capsule.radius = .35
	capsule.height = 1.8
	for radius: float in [1.0, 1.35, 1.65]:
		for index in range(24):
			var angle: float = float(index) * TAU / 24.0
			var point: Vector3 = container.global_position + Vector3(cos(angle) * radius, .8, sin(angle) * radius)
			var hit: Dictionary = ray(point, point - Vector3.UP * 3)
			if hit.is_empty() or (hit.normal as Vector3).y < .8:
				continue
			var feet: Vector3 = hit.position + Vector3.UP * .025
			if absf(feet.y - container.global_position.y) > 1.4:
				continue
			var query := PhysicsShapeQueryParameters3D.new()
			query.shape = capsule
			query.transform = Transform3D(Basis.IDENTITY, feet + Vector3.UP * .91)
			query.collision_mask = Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR
			if not level.get_world_3d().direct_space_state.intersect_shape(query, 1).is_empty():
				continue
			probe.global_position = feet
			if container.reachable_from(probe):
				return true
	return false


func _path(title: String, from: Vector3, to: Vector3) -> void:
	var path: PackedVector3Array = NavigationServer3D.map_get_path(map, from, to, true)
	var reached: bool = not path.is_empty() and path[-1].distance_to(to) < .8
	check(title, reached)
	if not reached:
		print("NW_PATH ", title, " end=", path[-1] if not path.is_empty() else Vector3.INF, " target=", to)
		print("NW_CLOSEST target=", NavigationServer3D.map_get_closest_point(map, to))


func _walk(path: PackedVector3Array, title: String = "игрок проходит лестницу без прыжка") -> void:
	probe.global_position = path[0] + Vector3.UP * .03
	probe.velocity = Vector3.ZERO
	for index in range(1, path.size()):
		var goal: Vector3 = path[index]
		var arrived: bool = false
		for tick in range(400):
			await get_tree().physics_frame
			var delta: float = get_physics_process_delta_time()
			var dir: Vector3 = goal - probe.global_position
			dir.y = 0
			if dir.length() < .16 and absf(probe.global_position.y - goal.y) < .4:
				arrived = true
				break
			dir = dir.normalized()
			var before: Vector3 = probe.global_position
			probe.velocity = Vector3(dir.x * 2.0, 0 if probe.is_on_floor() else probe.velocity.y - 9.8 * delta, dir.z * 2.0)
			var intended: Vector3 = probe.velocity
			probe.move_and_slide()
			if probe.velocity.y <= .3:
				probe._step_up(delta, before, intended)
		if not arrived:
			check(title, false)
			print("NW_WALK blocked=", probe.global_position, " goal=", goal)
			for hit_index in range(probe.get_slide_collision_count()):
				var hit: KinematicCollision3D = probe.get_slide_collision(hit_index)
				print("NW_CONTACT ", hit.get_collider(), " shape=", hit.get_collider_shape_index(), " normal=", hit.get_normal())
			return
	check(title, true)


func check(title: String, passed: bool) -> void:
	checks += 1
	if not passed:
		failures += 1
	print("OK " if passed else "FAIL ", title)
