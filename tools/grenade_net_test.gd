extends Node3D
## Два настоящих ENet-процесса: гость готовит/бросает, хост расходует вещи и считает урон.
## --headless res://tools/grenade_net_test.tscn -- host|client, порт 17796.

var _role: String = ""
var _client: int = 0
var _players: Dictionary = {}
var _raid: Raid
var _ready_peer: bool = false
var _done: bool = false
var _finished: bool = false
var _fails: int = 0
var _seen: Dictionary = {}
var _spawned: int = 0
var _held: bool = false
var _pulled: bool = false


func _enter_tree() -> void:
	set_meta(Net.SCENE_META, "raid")


func _ready() -> void:
	Engine.max_fps = 60
	get_tree().create_timer(45.0).timeout.connect(func() -> void: get_tree().quit(99))
	var args: PackedStringArray = OS.get_cmdline_user_args()
	_role = args[0] if not args.is_empty() else ""
	if _role not in ["host", "client"]:
		get_tree().quit(2)
		return
	Profile.use_file("user://profile_grenade_net_%s.json" % _role, true)
	Profile.ensure()
	Profile.pending_raid = false
	RaidEvents.enabled = false
	Net.enter_scene("raid")
	if _role == "host":
		_check("ENet хост", Net.host("Граната хост", 17796) == "")
		if not await _wait(func() -> bool: return not multiplayer.get_peers().is_empty(), 20.0):
			get_tree().quit(3)
			return
		_client = multiplayer.get_peers()[0]
		_spawn.rpc(_client)
		_check("гость подготовил сцену", await _wait(func() -> bool: return _ready_peer, 15.0))
		_begin.rpc_id(_client)
		_check("гость завершил оба броска", await _wait(func() -> bool: return _done, 20.0))
		var player: Player = _players[_client] as Player
		_check("напарник видел гранату в руке", _held)
		_check("напарник видел извлечение чеки", _pulled)
		_check("хост создал ровно две гранаты", _spawned == 2, str(_spawned))
		_check("хост списал две гранаты из Inventory гостя", player.inventory.count("grenade") == 0)
		_finish.rpc_id(_client)
		await get_tree().create_timer(0.8).timeout
	else:
		_check("ENet гость", Net.join("127.0.0.1", "Граната гость", 17796) == "")
		_check("получен итог хоста", await _wait(func() -> bool: return _finished, 35.0))
	print("grenade_net_test[%s]: провалено %d" % [_role, _fails])
	await _cleanup()
	get_tree().quit(1 if _fails else 0)


@rpc("authority", "call_local", "reliable")
func _spawn(client: int) -> void:
	_client = client
	Net.enter_scene("raid")
	_raid = Raid.new()
	_raid.name = "Raid"
	add_child(_raid)
	_raid.set_process(false)
	_raid.set_physics_process(false)
	for peer: int in [1, client]:
		var player: Player = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
		player.name = "Player_%d" % peer
		player.peer_id = peer
		player.set_multiplayer_authority(peer, true)
		player.get_node("Health").set_multiplayer_authority(1, true)
		player.loadout_mode = true
		player.position = Vector3(0, 1, 0)
		add_child(player)
		player.set_physics_process(false)
		player.health.invulnerable = true
		player.inventory.set_multiplayer_authority(1)
		_players[peer] = player
		_raid.register(peer, "Grenade_%d" % peer)
		if multiplayer.is_server():
			player.inventory.equipment = {}
			player.inventory.items = [ItemDb.make("grenade", 2)]
			player.inventory.loadout_ready = true
	if not multiplayer.is_server():
		_peer_ready.rpc_id(1)


@rpc("any_peer", "call_remote", "reliable")
func _peer_ready() -> void:
	if multiplayer.is_server() and multiplayer.get_remote_sender_id() == _client:
		_ready_peer = true


@rpc("authority", "call_remote", "reliable")
func _begin() -> void:
	var player: Player = _players[_client] as Player
	_check("гость получил две гранаты хоста", await _wait(func() -> bool: return player.inventory.count("grenade") == 2, 5.0))
	player.ads = true
	player.look_yaw = PI
	player._equip_grenade()
	player._combat(0.5)
	player._combat(0.01)
	for action: String in ["fire", "aim"]:
		await get_tree().process_frame
		Input.action_press(action)
		player._combat(0.02)
		player._combat(0.5)
		await get_tree().create_timer(0.35).timeout
		Input.action_release(action)
		player._combat(0.01)
		_check(action + ": хост подтвердил бросок", await _wait(func() -> bool: return not player._grenade_pending, 5.0))
		# Тот же пакет ещё раз: ни второго снаряда, ни второго расхода.
		player._rpc_grenade_request.rpc_id(1, player._grenade_seq, 1.0, false, Vector3.FORWARD, "grenade")
		await get_tree().create_timer(0.8).timeout
		player._combat(1.0)
		player._combat(0.01)
	_check("после двух бросков запас гостя пуст", player.inventory.count("grenade") == 0)
	# Даже прямой третий запрос без предмета не создаёт снаряд.
	player._grenade_seq += 1
	player._grenade_pending = true
	player._rpc_grenade_request.rpc_id(1, player._grenade_seq, 1.0, false, Vector3.FORWARD, "grenade")
	_check("пустой запас получил отказ хоста", await _wait(func() -> bool: return not player._grenade_pending, 5.0))
	_check("гость видел ровно две визуальные гранаты", _spawned == 2, str(_spawned))
	_completed.rpc_id(1)


func _process(_delta: float) -> void:
	for node: Node in get_tree().get_nodes_in_group("thrown_grenades"):
		var grenade: Grenade = node as Grenade
		var id: int = grenade.get_instance_id()
		if _seen.has(id):
			continue
		_seen[id] = true
		_spawned += 1
		_check("урон гранаты считает только хост", grenade._damage == multiplayer.is_server())
		_check("автор броска сохранён", grenade._attacker == _client and int(grenade.src.peer) == _client)
	if _players.has(_client) and is_instance_valid(_players[_client]):
		var player: Player = _players[_client] as Player
		_held = _held or (player.grenade_equipped and player._weapon_model is GrenadeModel)
		_pulled = _pulled or player.grenade_pin > 0.9


@rpc("any_peer", "call_remote", "reliable")
func _completed() -> void:
	if multiplayer.is_server() and multiplayer.get_remote_sender_id() == _client:
		_done = true


@rpc("authority", "call_remote", "reliable")
func _finish() -> void:
	_finished = true


func _wait(predicate: Callable, seconds: float) -> bool:
	var deadline: int = Time.get_ticks_msec() + int(seconds * 1000.0)
	while not bool(predicate.call()) and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	return bool(predicate.call())


func _check(label: String, ok: bool, note: String = "") -> void:
	if not ok:
		_fails += 1
	print("[%s][%s] %s %s" % [_role, "ok" if ok else "ПРОВАЛ", label, note])


func _cleanup() -> void:
	Input.action_release("fire")
	Input.action_release("aim")
	set_process(false)
	for sound: Node in Audio.get_children():
		if sound is AudioStreamPlayer:
			(sound as AudioStreamPlayer).stop()
			(sound as AudioStreamPlayer).stream = null
		elif sound is AudioStreamPlayer3D:
			(sound as AudioStreamPlayer3D).stop()
			(sound as AudioStreamPlayer3D).stream = null
	var peer: MultiplayerPeer = multiplayer.multiplayer_peer
	Net._keep_own_scene(OfflineMultiplayerPeer.new())
	Net._active = false
	peer.close()
	_players.clear()
	for child: Node in get_children():
		child.queue_free()
	for frame: int in range(4):
		await get_tree().process_frame
