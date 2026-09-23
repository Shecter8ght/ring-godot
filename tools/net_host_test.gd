extends Node
## Хост для сетевого прогона: поднимает сервер, ждёт клиента, запускает сектор, стреляет в
## мародёра (проверка репликации урона), двигается вперёд (проверка репликации позиции игрока
## клиенту). Печатает состояние каждую секунду. godot --path . res://tools/net_host_test.tscn

var _level: Node = null
var _t: float = 0.0


## Net.start_level меняет current_scene — если тестовая логика жила бы в НЕМ, она обрубилась бы
## вместе со сценой. Поэтому настоящий узел-раннер живёт прямо под root, переживает смену сцены.
func _ready() -> void:
	if name == "HostTestRunner":
		_run()
		return
	var runner := Node.new()
	runner.name = "HostTestRunner"
	runner.set_script(get_script())
	get_tree().root.add_child.call_deferred(runner)


func _run() -> void:
	print("[host] запускаю сервер")
	var err := Net.host("Хост")
	if err != "":
		print("[host] ОШИБКА: ", err)
		get_tree().quit(1)
		return
	print("[host] сервер поднят, жду клиента…")
	while multiplayer.get_peers().is_empty():
		await get_tree().process_frame
	print("[host] клиент подключился: id=%s" % str(multiplayer.get_peers()))
	Profile.use_file("user://profile_net_host.json", true)
	await get_tree().create_timer(0.3).timeout
	Net.grant_money(multiplayer.get_peers()[0], 12345)   # панель админа: деньги клиенту
	Net.start_level.rpc(Net.LEVEL_SCENE)
	while not (get_tree().current_scene and get_tree().current_scene.has_method("_spawn_marauders")):
		await get_tree().process_frame
	_level = get_tree().current_scene
	print("[host] сцена сектора загружена")
	while _level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	print("[host] мародёры на месте")
	await get_tree().create_timer(1.0).timeout
	_report("после спавна")
	# Проверка репликации урона: стреляем в первого мародёра.
	var m: Marauder = _level.get_node("Marauders").get_child(0)
	var h: Health = m.get_node("Health")
	print("[host] стреляю в мародёра, HP до: %d" % int(h.hp))
	h.apply_or_request_damage(25.0, m.global_position + Vector3(0, 1, 5))
	# Двигаем своего игрока вперёд — клиент должен увидеть, как я сдвинулся.
	var my_player := _find_player(1)
	var before := my_player.global_position
	Input.action_press("move_forward")
	await get_tree().create_timer(1.0).timeout
	Input.action_release("move_forward")
	print("[host] игрок сдвинулся на %.2f м (host: %s -> %s)" % [before.distance_to(my_player.global_position), before, my_player.global_position])
	# рейд: хост включает рубильник и берёт ключ — клиент должен это увидеть
	Raid.current.set_switch("dock_gate", true)
	my_player.inventory.add("key_server", 1)
	print("[host] рубильник включён, ключ от серверной в рюкзаке хоста")
	await get_tree().create_timer(1.0).timeout
	_report("финал")
	print("[host] мародёр HP после урона: %d" % int(h.hp))
	# клиент подбирает карту-ключ (просьбой к хосту) и уходит через остановку — ждём эвакуацию
	var client_id: int = multiplayer.get_peers()[0]
	var waited := 0.0
	while not Raid.current.is_extracted(client_id) and waited < 25.0:
		await get_tree().process_frame
		waited += get_process_delta_time()
	await get_tree().create_timer(0.3).timeout
	var cp := Raid.current.player_of(client_id)
	print("[host] рейд: участники %s, рюкзак клиента %s, эвакуированы %s, вынес %s" % [Raid.current.participants, cp.inventory.items if cp else [], Raid.current.extracted, Raid.current.loot_value])
	print("[host] клиент эвакуирован: %s, игроков в мире %d" % [Raid.current.is_extracted(client_id), get_tree().get_nodes_in_group("players").size()])
	# Не гасим сервер раньше клиента — иначе он получит server_disconnected и уйдёт в лобби
	# посреди своих же проверок (так и вскрылась опечатка в путях lobby.tscn).
	await get_tree().create_timer(3.0).timeout
	get_tree().quit(0)


func _find_player(peer_id: int) -> Player:
	for p in get_tree().get_nodes_in_group("players"):
		if (p as Player).peer_id == peer_id:
			return p
	return null


func _report(label: String) -> void:
	var players := get_tree().get_nodes_in_group("players")
	var mnode := _level.get_node("Marauders")
	print("[host] %s: игроков %d, мародёров %d" % [label, players.size(), mnode.get_child_count()])
	for p in players:
		var pl := p as Player
		print("    peer_id=%d pos=%s hp=%d" % [pl.peer_id, pl.global_position, int(pl.health.hp)])
	if mnode.get_child_count() > 0:
		var h: Health = mnode.get_child(0).get_node("Health")
		print("    мародёр0 HP=%d" % int(h.hp))
