extends Node
## Брод в болоте зоны 1 (владелец 2026-10-18: по пояс): глубина над ступнями, скорость по пояс и на суше,
## бег и «лечь» в воде запрещены, шаг по воде — плеск. tools/godot.cmd --headless res://tools/water_wade_test.tscn

var failures: int = 0


func _ready() -> void:
	Profile.use_file("user://water_wade_test.json", true)
	var level := (load("res://scenes/levels/zone01_mall.tscn") as PackedScene).instantiate() as Node3D
	level.set_script(null)
	add_child(level)
	await get_tree().physics_frame
	await get_tree().physics_frame
	var terrain: Node = level.get_node("World/Terrain")
	var layout: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/zone01_layout.json"))
	var poly := PackedVector2Array()
	for q: Array in layout.swamp:
		poly.append(Vector2(float(q[0]), float(q[1])))
	# место в болоте по пояс и место на сухом (северная улица)
	var wade := Vector3.INF
	var deepest: float = 0.0
	var wet: int = 0
	var total: int = 0
	for z in range(-275, -100, 3):
		for x in range(-235, 10, 3):
			if not Geometry2D.is_point_in_polygon(Vector2(x, z), poly):
				continue
			var g: float = float(terrain.call("height_at", float(x), float(z)))
			var d: float = WaterBody.depth_at(Vector3(x, g, z))
			total += 1
			wet += 1 if d > 0.12 else 0
			deepest = maxf(deepest, d)
			if wade == Vector3.INF and d > 0.75 and d < 0.95:
				wade = Vector3(x, g, z)
	check("в болоте больше половины — вода", total > 0 and float(wet) / float(total) > 0.5, "%d из %d" % [wet, total])
	check("нигде не глубже, чем по грудь (≤ 1,25 м)", deepest <= 1.25, "%.2f" % deepest)
	check("нашлось место по пояс", wade != Vector3.INF, "")
	var dry := Vector3(-128.0, float(terrain.call("height_at", -128.0, -86.0)), -86.0)
	check("на улице сухо", WaterBody.depth_at(dry) == 0.0, "%.2f" % WaterBody.depth_at(dry))

	var probe := (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	probe.name = "WadeProbe"
	add_child(probe)
	probe.set_physics_process(false)
	probe.set_process(false)
	await get_tree().physics_frame
	probe.global_position = dry
	await get_tree().physics_frame
	var dry_speed: float = probe._stance_speed()
	check("на суше бег возможен", probe._can_sprint(), "")
	probe.global_position = wade
	await get_tree().physics_frame
	var depth: float = probe._water_depth()
	var wet_speed: float = probe._stance_speed()
	check("игрок видит глубину по пояс", depth > 0.7, "%.2f" % depth)
	check("по пояс медленнее (×0,55–0,7)", wet_speed / dry_speed > 0.5 and wet_speed / dry_speed < 0.72, "%.2f" % (wet_speed / dry_speed))
	check("по пояс бежать нельзя", not probe._can_sprint(), "")
	probe.stance = Player.Stance.PRONE
	probe._apply_stance()
	check("в воде лечь нельзя — на колено", probe.stance == Player.Stance.CROUCH, str(probe.stance))
	var heard: Array[String] = []
	Audio.stepped.connect(func(_kind: String, surf: String, _pos: Vector3) -> void: heard.append(surf))
	Audio.step(wade, false, false, 0.0, true)
	# шаг дальше слышимости звук пропускает — слушатель (игрок) сначала переходит на улицу
	probe.global_position = dry
	await get_tree().physics_frame
	Audio.step(dry, false, false, 0.0, true)
	check("шаг в воде — плеск, на улице — нет", heard.size() == 2 and heard[0] == "water" and heard[1] != "water", str(heard))
	print("water_wade_test: failures=", failures)
	get_tree().quit(1 if failures else 0)


func check(title: String, ok: bool, info: String) -> void:
	if not ok:
		failures += 1
	print("OK   " if ok else "FAIL ", title, ("  — " + info) if info != "" else "")
