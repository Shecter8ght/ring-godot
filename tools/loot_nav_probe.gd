extends Node
## «Проспект»: сколько контейнеров с телом-коллизией выступают в проходимую навигацию. Для каждого тела берётся коробка (у стены
## спинкой): точки её основания шагом 0,1 м; если навигационная сетка есть внутри коробки глубже 0,3 м от грани — контейнер
## «выступает» (бот пойдёт на него и упрётся). Печатает число и список. Запускать до и после перепечи навигации.
##   tools/godot.cmd --headless res://tools/loot_nav_probe.tscn

const LEVEL := "res://scenes/levels/prospekt.tscn"
const STEP := 0.1
const DEEP := 0.3


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "dusk", "weather": "clear", "power": "on"}
	Profile.use_file("user://profile_loot_nav_probe.json", true)
	await get_tree().process_frame
	var level: Node = load(LEVEL).instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	var t0: int = Time.get_ticks_msec()
	while int(level.get("_marauders_spawned")) <= 0 and Time.get_ticks_msec() - t0 < 180000:
		await get_tree().process_frame
	for i in range(30):
		await get_tree().physics_frame
	var map: RID = (level as Node3D).get_world_3d().navigation_map
	var total: int = 0
	var bad: Array[String] = []
	var worst: Array[String] = []
	var near_nav: int = 0
	for n: Node in get_tree().get_nodes_in_group("loot_containers"):
		var c: LootContainer = n as LootContainer
		var body: StaticBody3D = c.find_child(LootContainerVisual.BODY_NAME, true, false) as StaticBody3D
		if body == null:
			continue
		total += 1
		var shape: CollisionShape3D = body.get_child(0) as CollisionShape3D
		var size: Vector3 = (shape.shape as BoxShape3D).size
		var xf: Transform3D = shape.global_transform
		var deepest: float = 0.0
		var cn: Vector3 = NavigationServer3D.map_get_closest_point(map, xf.origin)
		if Vector2(cn.x - xf.origin.x, cn.z - xf.origin.z).length() < 1.2:
			near_nav += 1
		var x: float = -size.x * 0.5 + STEP * 0.5
		while x < size.x * 0.5:
			var z: float = -size.z * 0.5 + STEP * 0.5
			while z < size.z * 0.5:
				var p: Vector3 = xf * Vector3(x, -size.y * 0.5 + 0.05, z)
				var q: Vector3 = NavigationServer3D.map_get_closest_point(map, p)
				if Vector2(q.x - p.x, q.z - p.z).length() < 0.06 and absf(q.y - p.y) < 0.6:
					# глубина от ближайшей грани коробки по плану
					var edge: float = minf(size.x * 0.5 - absf(x), size.z * 0.5 - absf(z))
					deepest = maxf(deepest, edge)
				z += STEP
			x += STEP
		if deepest > DEEP:
			bad.append("%s (%s) %.2f м" % [c.name, c.kind, deepest])
		elif deepest > 0.0:
			worst.append("%s %.2f" % [c.name, deepest])
	print("loot_nav_probe: контейнеров с телом %d, выступают в навигацию глубже %.1f м: %d" % [total, DEEP, bad.size()])
	for b: String in bad:
		print("  ", b)
	print("  мельче: ", worst.size(), "; сетка навигации ближе 1,2 м от центра коробки у ", near_nav, " (проверка, что сетка загружена)")
	print("  ", ", ".join(worst))
	get_tree().quit(0)
