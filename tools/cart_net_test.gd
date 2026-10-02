extends Node3D
## Настоящий ENet: клиент телом толкает тележку, хост считает движение, стекло и травму.
## tools/godot.cmd --headless res://tools/cart_net_test.tscn -- host (затем -- client).

const CART_SCENE: PackedScene = preload("res://scenes/props/shopping_cart.tscn")
const PLAYER_SCENE: PackedScene = preload("res://scenes/player/player.tscn")
var _role: String = ""
var _fails: int = 0
var _client: int = 0
var _ready_peer: bool = false
var _client_done: bool = false
var _finished: bool = false
var _placed: bool = false
var _drive: Vector3 = Vector3.ZERO
var _player: Player
var _cart: ShoppingCart
var _glass: GlassPanes
var _max_shove: float = 0.0


func _enter_tree() -> void:
	set_meta(Net.SCENE_META, "raid")


func _ready() -> void:
	Engine.max_fps = 120
	_role = "host" if "host" in OS.get_cmdline_user_args() else "client"
	RaidEvents.enabled = false
	Profile.use_file("user://profile_cart_net_%s_test.json" % _role, true)
	Profile.pending_raid = false
	Net.enter_scene("raid")
	if _role == "host":
		await _host()
	else:
		await _client_run()
	print("cart_net_test[%s]: провалено %d" % [_role, _fails])
	set_physics_process(false)
	# Закрываем сеть раньше Sync, чтобы не отправлять пакеты удалённым узлам на выходе.
	if Net.is_networked():
		var peer: MultiplayerPeer = multiplayer.multiplayer_peer
		Net._keep_own_scene(OfflineMultiplayerPeer.new())
		Net._active = false
		peer.close()
	for sound: Node in Audio.get_children():
		if sound is AudioStreamPlayer3D:
			(sound as AudioStreamPlayer3D).stop()
	for child: Node in get_children():
		child.queue_free()
	await get_tree().process_frame
	await get_tree().process_frame
	get_tree().quit(_fails)


func _physics_process(delta: float) -> void:
	if _role != "client" or not is_instance_valid(_player):
		return
	_player.velocity = _drive
	if not _player.is_on_floor():
		_player.velocity.y -= 9.8 * delta
	var contact: CartContact = _player.get_node("CartContact") as CartContact
	contact.move_character(delta)
	_max_shove = maxf(_max_shove, contact.shove_velocity.length())


func _host() -> void:
	var error: String = Net.host("Тележки хост")
	_check("сервер запущен", error == "", error)
	if error != "" or not await _wait(func() -> bool: return not multiplayer.get_peers().is_empty(), 60.0):
		_check("клиент подключился", false)
		return
	_client = int(multiplayer.get_peers()[0])
	_spawn.rpc(_client)
	if not await _wait(func() -> bool: return _ready_peer, 15.0):
		_check("узлы клиента готовы", false)
		return
	_go.rpc_id(_client)
	_check("толкание от клиента принято хостом", await _wait(func() -> bool: return _cart.position.z > 1.0, 8.0), str(_cart.position))
	_check("витрину разбивает хост", await _wait(func() -> bool: return bool(_glass.panes[0].broken), 8.0))
	_check("клиент видит положение и разбитое стекло", await _wait(func() -> bool: return _client_done, 10.0))
	# Второй контакт: хост разгоняет тележку на неподвижного клиента, его движение остаётся у него.
	_place.rpc_id(_client)
	if not await _wait(func() -> bool: return _placed, 10.0):
		_check("клиент готов к удару", false)
		return
	_impact_cart.rpc()
	await get_tree().create_timer(0.3).timeout
	_cart.sleeping = false
	_cart.apply_central_impulse(Vector3.BACK * _cart.mass * 5.0)
	_check("урон клиенту считает хост", await _wait(func() -> bool: return _player.health.hp < _player.health.max_hp, 5.0), "HP %.1f, cart=%s, player=%s" % [_player.health.hp, _cart.position, _player.position])
	await get_tree().create_timer(0.5).timeout
	_result.rpc_id(_client, _cart.global_position, _player.health.hp)
	_check("итог клиента доставлен хосту", await _wait(func() -> bool: return _finished, 10.0))
	await get_tree().create_timer(0.4).timeout


func _client_run() -> void:
	var error: String = Net.join("127.0.0.1", "Тележки клиент")
	_check("подключение запрошено", error == "", error)
	if error != "":
		return
	_check("проверки хоста завершились", await _wait(func() -> bool: return _finished, 45.0))
	await get_tree().create_timer(0.1).timeout


@rpc("authority", "call_local", "reliable")
func _spawn(peer: int) -> void:
	_client = peer
	var floor: StaticBody3D = StaticBody3D.new()
	floor.name = "Floor"
	var collision: CollisionShape3D = CollisionShape3D.new()
	var shape: BoxShape3D = BoxShape3D.new()
	shape.size = Vector3(30.0, 0.3, 60.0)
	collision.shape = shape
	collision.position.y = -0.15
	floor.add_child(collision)
	add_child(floor)
	_player = PLAYER_SCENE.instantiate() as Player
	_player.name = "Player_%d" % peer
	_player.peer_id = peer
	_player.set_multiplayer_authority(peer)
	_player.get_node("Health").set_multiplayer_authority(1)
	_player.position = Vector3(0.0, 0.03, -1.3)
	_player.combat_enabled = false
	add_child(_player)
	_player.set_physics_process(false)
	_player.set_process(false)
	_cart = CART_SCENE.instantiate() as ShoppingCart
	_cart.name = "Cart"
	_cart.position.y = 0.01
	add_child(_cart)
	_glass = GlassPanes.new()
	_glass.setup([{"xf": Transform3D(Basis.IDENTITY, Vector3(0.0, 1.6, 4.5)), "size": Vector2(4.0, 3.0), "floor_y": 0.0, "sill": Vector3(4.0, 0.1, 0.12), "broken": false}])
	add_child(_glass)
	if _role == "client":
		_check("клиент не симулирует тележку", _cart.freeze)
		_announce_ready.rpc_id(1)


@rpc("any_peer", "call_remote", "reliable")
func _announce_ready() -> void:
	_ready_peer = multiplayer.get_remote_sender_id() == _client


@rpc("authority", "call_remote", "reliable")
func _go() -> void:
	_drive = Vector3.BACK * 4.0
	await get_tree().create_timer(1.6).timeout
	_drive = Vector3.ZERO
	_check("клиент видит катящуюся тележку", _cart.position.z > 1.0)
	_check("стекло реплицируется клиенту", await _wait(func() -> bool: return bool(_glass.panes[0].broken), 10.0))
	_done.rpc_id(1)


@rpc("any_peer", "call_remote", "reliable")
func _done() -> void:
	_client_done = multiplayer.get_remote_sender_id() == _client


@rpc("authority", "call_remote", "reliable")
func _place() -> void:
	_player.global_position = Vector3(0.0, 0.01, 17.0)
	(_player.get_node("CartContact") as CartContact).shove_velocity = Vector3.ZERO
	_max_shove = 0.0
	await get_tree().create_timer(0.3).timeout
	_placed_ack.rpc_id(1)


@rpc("authority", "call_local", "reliable")
func _impact_cart() -> void:
	_cart.queue_free()
	_cart = CART_SCENE.instantiate() as ShoppingCart
	_cart.name = "CartImpact"
	_cart.position = Vector3(0.0, 0.015, 14.0)
	add_child(_cart)


@rpc("any_peer", "call_remote", "reliable")
func _placed_ack() -> void:
	_placed = multiplayer.get_remote_sender_id() == _client


@rpc("authority", "call_remote", "reliable")
func _result(at: Vector3, hp: float) -> void:
	_check("положение тележки совпадает", _cart.global_position.distance_to(at) < 0.5, "client=%s, host=%s" % [_cart.position, at])
	_check("здоровье совпадает с хостом", absf(_player.health.hp - hp) < 0.1 and hp < _player.health.max_hp, "HP %.1f" % _player.health.hp)
	_check("владелец клиента получил физическое отталкивание", _max_shove > 0.1 and _player.position.z > 17.01, "импульс %.2f, z %.2f" % [_max_shove, _player.position.z])
	_finished = true
	_finish_ack.rpc_id(1, _fails)


@rpc("any_peer", "call_remote", "reliable")
func _finish_ack(fails: int) -> void:
	if multiplayer.get_remote_sender_id() == _client:
		_fails += fails
		_finished = true


func _wait(predicate: Callable, sec: float) -> bool:
	var deadline: int = Time.get_ticks_msec() + int(sec * 1000.0)
	while Time.get_ticks_msec() < deadline:
		if bool(predicate.call()):
			return true
		await get_tree().process_frame
	return bool(predicate.call())


func _check(what: String, ok: bool, info: String = "") -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
