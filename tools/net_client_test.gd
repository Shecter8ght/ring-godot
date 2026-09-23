extends Node
## Клиент для сетевого прогона: подключается к 127.0.0.1, ждёт перехода в сектор (RPC от хоста),
## печатает, что видит (свой peer_id, чужого игрока, мародёров, HP мародёра после выстрела хоста).
## godot --path . res://tools/net_client_test.tscn

var _level: Node = null


## Net.start_level меняет current_scene — раннер живёт прямо под root, переживает смену сцены
## (см. подробный комментарий в net_host_test.gd).
func _ready() -> void:
	if name == "ClientTestRunner":
		_run()
		return
	var runner := Node.new()
	runner.name = "ClientTestRunner"
	runner.set_script(get_script())
	get_tree().root.add_child.call_deferred(runner)


func _run() -> void:
	await get_tree().create_timer(0.8).timeout
	print("[client] подключаюсь…")
	var err := Net.join("127.0.0.1", "Клиент")
	if err != "":
		print("[client] ОШИБКА: ", err)
		get_tree().quit(1)
		return
	var t := 0.0
	while not (get_tree().current_scene and get_tree().current_scene.has_method("_spawn_marauders")):
		await get_tree().process_frame
		t += get_process_delta_time()
		if t > 40.0:
			print("[client] сцена не загрузилась за 40с")
			get_tree().quit(1)
			return
	_level = get_tree().current_scene
	print("[client] сцена сектора загружена, мой id=%d" % multiplayer.get_unique_id())
	await get_tree().create_timer(1.5).timeout
	_report("после спавна")
	var my_player := _find_local()
	var before := my_player.global_position if my_player else Vector3.ZERO
	Input.action_press("move_left")
	await get_tree().create_timer(1.0).timeout
	Input.action_release("move_left")
	print("[client] сам сдвинулся на %.2f м" % before.distance_to(my_player.global_position))
	await get_tree().create_timer(1.5).timeout
	_report("после движения хоста")
	await get_tree().create_timer(1.5).timeout
	_report("финал (должен увидеть урон по мародёру)")
	var host_pl := Raid.current.player_of(1)
	print("[client] рейд: рубильники %s, рюкзак хоста (вижу) %s" % [Raid.current.switches, host_pl.inventory.items if host_pl else []])
	# просим хост подобрать карту-ключ (как по F) и идём к остановке
	# лут по сети: подойти к сейфу, попросить хост бросить содержимое, забрать всё
	var safe := _level.get_node("Interactables/JewelrySafe") as LootContainer
	my_player.global_position = safe.global_position + safe.global_basis.z * -1.2 + Vector3(0, 0.1, 0)
	await get_tree().create_timer(0.4).timeout
	safe.request_use()
	await get_tree().create_timer(0.6).timeout
	print("[client] сейф: брошен %s, вижу %s" % [safe.rolled, safe.items])
	Raid.current.request_take_all(safe)
	await get_tree().create_timer(0.6).timeout
	print("[client] после «взять всё»: сейф %s, мой рюкзак %s ₽" % [safe.items, my_player.inventory.value()])
	var card := _level.get_node("Interactables/KeycardSecurity") as KeyPickup
	my_player.global_position = card.global_position + Vector3(0.6, 0.1, 0)
	await get_tree().create_timer(0.4).timeout
	card.request_use()
	await get_tree().create_timer(0.5).timeout
	print("[client] карта-ключ в моём рюкзаке: %s" % my_player.inventory.has("keycard_security"))
	var bus := _level.get_node("Extractions/Bus") as ExtractionPoint
	my_player.global_position = bus.global_position + Vector3(0, 0.1, 0)
	await get_tree().create_timer(bus.channel_s + 2.0).timeout
	print("[client] я эвакуирован: %s, итог виден: %s" % [Raid.current.is_extracted(multiplayer.get_unique_id()), Raid.current.extracted])
	get_tree().quit(0)


func _find_local() -> Player:
	var my_id := multiplayer.get_unique_id()
	for p in get_tree().get_nodes_in_group("players"):
		if (p as Player).peer_id == my_id:
			return p
	return null


func _report(label: String) -> void:
	var players := get_tree().get_nodes_in_group("players")
	var marauders_node := _level.get_node_or_null("Marauders")
	var mcount := marauders_node.get_child_count() if marauders_node else 0
	print("[client] %s: игроков вижу %d, мародёров %d" % [label, players.size(), mcount])
	for p in players:
		var pl := p as Player
		print("    peer_id=%d pos=%s hp=%d local=%s" % [pl.peer_id, pl.global_position, int(pl.health.hp), pl.is_local()])
	if mcount > 0:
		var m: Marauder = marauders_node.get_child(0)
		var h: Health = m.get_node("Health")
		print("    мародёр0 HP=%d pos=%s" % [int(h.hp), m.global_position])
