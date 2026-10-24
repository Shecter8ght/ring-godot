extends Node
## Во что упирается процессор на уровне: средние «обработка узлов» и «физика» за кадр, затем то же,
## по очереди выключая подозреваемых (ИИ мародёров, их анимацию, тележки, двери…) — разница и есть цена.
## tools/godot.cmd --disable-vsync res://tools/cpu_probe.tscn [-- res://scenes/levels/xxx.tscn]

const FRAMES := 150


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var scene := args[0] if args.size() > 0 else "res://scenes/levels/mall_map.tscn"
	RaidEvents.enabled = false
	await get_tree().process_frame
	var inst: Node = load(scene).instantiate()
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	for i in range(600):
		await get_tree().process_frame
		if get_tree().get_nodes_in_group("marauders").size() > 0 and i > 200:
			break
	var player := get_tree().get_first_node_in_group("players") as Player
	player.health.hp = 1e9
	print("cpu_probe: %s — мародёров %d, узлов %d" % [scene, get_tree().get_nodes_in_group("marauders").size(), int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT))])
	await _row("как есть")
	# счёт узлов с обработкой по скриптам — кто вообще работает каждый кадр
	var by: Dictionary = {}
	for n in inst.find_children("*", "", true, false):
		if n.get_script() and (n.is_processing() or n.is_physics_processing()):
			var k := (n.get_script() as Script).resource_path.get_file()
			by[k] = int(by.get(k, 0)) + 1
	var keys: Array = by.keys()
	keys.sort_custom(func(a: String, b: String) -> bool: return int(by[a]) > int(by[b]))
	var line := ""
	for i in range(mini(18, keys.size())):
		line += "%s×%d  " % [String(keys[i]), int(by[keys[i]])]
	print("  работают каждый кадр: " + line)
	# по очереди выключаем подозреваемых — разница со строкой выше и есть их цена
	var bodies := 0
	for n in inst.find_children("*", "RigidBody3D", true, false):
		(n as RigidBody3D).freeze = true
		bodies += 1
	await _row("твёрдые тела заморожены (%d)" % bodies)
	_off(inst, "marauder.gd", true, true)
	await _row("и без ИИ мародёров")
	_off(inst, "character_animator.gd", true, true)
	for n in inst.find_children("*", "AnimationPlayer", true, false):
		(n as AnimationPlayer).active = false
	await _row("и без анимации персонажей")
	for name: String in ["support_hand_ik.gd", "weapon_collision_ik.gd", "footsteps.gd", "cart_contact.gd", "shopping_cart.gd", "shopping_cart_visuals.gd"]:
		_off(inst, name, true, true)
	await _row("и без IK, шагов, тележек")
	for name: String in ["door.gd", "lamp_head.gd", "street_lamp.gd", "obstruction_light.gd", "health.gd"]:
		_off(inst, name, true, true)
	await _row("и без дверей, ламп, здоровья")
	var player_node := get_tree().get_first_node_in_group("players")
	player_node.set_process(false)
	player_node.set_physics_process(false)
	await _row("и без скрипта игрока")
	for n in inst.find_children("*", "Skeleton3D", true, false):
		(n as Node3D).visible = false
	await _row("и скелеты скрыты")
	for n in inst.get_children():
		if n is Node3D and not n is Camera3D and n.name != "CameraRig":
			(n as Node3D).visible = false
	await _row("и весь мир скрыт (остался пустой кадр)")
	get_tree().quit(0)


func _row(label: String) -> void:
	for i in range(40):
		await get_tree().process_frame
	var proc := 0.0
	var phys := 0.0
	var nav := 0.0
	var t0 := Time.get_ticks_usec()
	for i in range(FRAMES):
		await get_tree().process_frame
		proc += Performance.get_monitor(Performance.TIME_PROCESS)
		phys += Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS)
		nav += Performance.get_monitor(Performance.TIME_NAVIGATION_PROCESS)
	var sec := float(Time.get_ticks_usec() - t0) / 1e6
	print("  %-34s %6.1f к/с   узлы %6.2f мс   физика %6.2f мс   навигация %5.2f мс" % [label, FRAMES / sec, proc / FRAMES * 1000.0, phys / FRAMES * 1000.0, nav / FRAMES * 1000.0])


func _off(root: Node, script_file: String, physics: bool, process: bool) -> void:
	for n in root.find_children("*", "", true, false):
		if n.get_script() and (n.get_script() as Script).resource_path.get_file() == script_file:
			if physics:
				n.set_physics_process(false)
			if process:
				n.set_process(false)
