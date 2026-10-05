extends "res://tools/coop_raid_test.gd"
## Тот же штатный кооп-прогон на троих, но через маршрут Зоны 2 и её собственные двери/КПП.

var _urban_ready_peers: Dictionary = {}


func _run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if not args.is_empty() and String(args[0]) in ROLES:
		_role = String(args[0])
	Profile.use_file("user://profile_zone02_coop_%s_test.json" % _role, true)
	RaidEvents.enabled = false
	_gear_up()
	_check("Зона 2 доступна как штатный маршрут", Floors.select("zone02"), "")
	match _role:
		"host":
			await _host()
		_:
			await _client()
	print("zone02_coop[%s]: провалено %d" % [_role, _fails])
	# ENet успевает завершить уход первого клиента до закрытия второго.
	if _role == "c2":
		await get_tree().create_timer(1.0).timeout
	Net.disconnect_all()
	get_tree().quit(1 if _fails > 0 else 0)


func _raid() -> void:
	var ready: Callable = func() -> bool: return Raid.current != null and Raid.current.local_player() != null and _players().size() == 3 and bool(get_tree().current_scene.get("_nav_baked"))
	await _wait(ready, 60.0)
	_check("все загрузили маршрут Зоны 2", Profile.floor == "zone02"
		and get_tree().current_scene.scene_file_path == Floors.scene("zone02"), "")
	var enemies: Node = get_tree().current_scene.get_node("Marauders")
	await _wait(func() -> bool: return enemies.get_child_count() == Balance.MARAUDER_COUNT, 15.0)
	_check("AI хоста реплицирован", enemies.get_child_count() == Balance.MARAUDER_COUNT, "мародёров %d" % enemies.get_child_count())
	for enemy: Node in enemies.get_children():
		enemy.set_physics_process(false)
	Raid.current.local_player().health.invulnerable = true
	_urban_ready.rpc()
	await _wait(func() -> bool: return _urban_ready_peers.size() == 3, 20.0)
	_check("трое готовы до начала действий", _urban_ready_peers.size() == 3, str(_urban_ready_peers))
	await super._raid()


@rpc("any_peer", "call_local", "reliable")
func _urban_ready() -> void:
	var peer: int = multiplayer.get_remote_sender_id()
	if peer == 0:
		peer = multiplayer.get_unique_id()
	_urban_ready_peers[peer] = true


func _test_door() -> Door:
	var building: Node = get_tree().current_scene.get_node("Districts/Commercial/Buildings/Supermarket")
	var doors: Array[Node] = building.find_children("*", "Door", true, false)
	doors.sort_custom(func(a: Node, b: Node) -> bool: return str(a.get_path()) < str(b.get_path()))
	return doors[0] as Door if not doors.is_empty() else null


func _test_extraction() -> ExtractionPoint:
	return get_tree().current_scene.get_node("Checkpoints/WestCheckpoint/Extraction_West") as ExtractionPoint
