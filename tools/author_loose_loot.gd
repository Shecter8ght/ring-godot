extends Node
## Авторские точки находок городских карт: опора измеряется лучом по реальной коллизии.
## Главные сцены не меняются; отдельный редактируемый слой подключается через extras JSON.

const LOOSE: PackedScene = preload("res://scenes/world/loose_loot.tscn")


func _ready() -> void:
	# с 2026-11-08 «Пригород» правится руками (docs/level_editing.md): слой находок zone01_loose_loot.tscn — тоже,
	# перезапись стёрла бы ручные правки
	if OS.get_environment("ZONE01_OVERWRITE") != "1":
		print("author_loose_loot: «Пригород» правится руками — слой находок не перезаписываю (ZONE01_OVERWRITE=1 — всё же)")
		get_tree().quit(1)
		return
	Profile.use_file("user://author_loose_loot.json", true)
	await _author("zone01", "res://scenes/levels/zone01_mall.tscn")
	get_tree().quit(0)


func _author(zone: String, path: String) -> void:
	var level: Node3D = (load(path) as PackedScene).instantiate() as Node3D
	level.set_script(null)
	add_child(level)
	await get_tree().physics_frame
	await get_tree().physics_frame
	var candidates: Array[Dictionary] = []
	if zone == "zone01":
		# Скамейки двора, площадка мусорных баков, прачечные и фасады существующих гаражей.
		for point: Vector3 in [Vector3(-214.2, 1.2, -127), Vector3(-201.4, 1.3, -127),
			Vector3(-165.4, 1.3, -110.2), Vector3(-165.4, 1.3, -81.4), Vector3(-227.2, 1.3, -77.5)]:
			candidates.append({"pos": point, "table": "home"})
		for point: Vector3 in [Vector3(-180.3, 1.3, -69.6), Vector3(-180.3, 1.3, -66.4),
			Vector3(-176, 1.3, -61.9), Vector3(-214, 1.3, -68.3), Vector3(-214, 1.3, -102.3)]:
			candidates.append({"pos": point, "table": "storage"})
		# Дворовые находки теперь внутри доступных квартир; отдельный слой хранит только гаражи.
		if ResourceLoader.exists("res://scenes/levels/zone01/zone01_yard05_gameplay.tscn"):
			candidates.clear()
		# гаражный ряд двора хрущёвок — на новом месте двора (сдвиг +24, +97, зона 1 — квадрат 2026-10-17)
		for point: Vector3 in [Vector3(-240.5, 1.4, -60), Vector3(-240.5, 1.4, -49.8),
			Vector3(-240.5, 1.4, -40.2), Vector3(-240.5, 1.4, -30),
			Vector3(-240.5, 1.4, -20.4), Vector3(-240.5, 1.4, -10.2)]:
			candidates.append({"pos": point, "table": "workshop"})
	else:
		# Уже доступные места обыска: вещь рядом с ящиком, а не новая комната карты.
		for node: Node in level.find_children("*", "LootContainer", true, false):
			var container: LootContainer = node as LootContainer
			var theme: String = container.table
			if "Garage" in String(container.name):
				theme = "workshop"
			elif "Residential" in String(container.name):
				theme = "home"
			candidates.append({"pos": container.global_position + Vector3(0.9, 0.8, 0.45), "table": theme})
	var root: Node3D = Node3D.new()
	root.name = zone.capitalize() + "LooseLoot"
	var index: int = 0
	for candidate: Dictionary in candidates:
		var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(candidate.pos, (candidate.pos as Vector3) - Vector3.UP * 5.0, 1)
		var hit: Dictionary = level.get_world_3d().direct_space_state.intersect_ray(query)
		if hit.is_empty() or (hit.normal as Vector3).y < 0.7:
			push_warning("Нет опоры: " + str(candidate.pos))
			continue
		var found: LooseLoot = LOOSE.instantiate() as LooseLoot
		found.name = "Found_%02d" % index
		found.position = hit.position
		found.table = String(candidate.table)
		root.add_child(found)
		found.owner = root
		index += 1
	var packed: PackedScene = PackedScene.new()
	packed.pack(root)
	var out: String = "res://scenes/levels/%s/%s_loose_loot.tscn" % [zone, zone]
	ResourceSaver.save(packed, out)
	print("author_loose_loot: ", zone, " точек ", index)
	root.free()
	level.queue_free()
	await get_tree().process_frame
