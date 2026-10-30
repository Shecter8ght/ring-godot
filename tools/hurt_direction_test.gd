extends Node3D
## Направление входящего урона через настоящий Player/Health/CameraRig; без загрузки карты.
## --headless res://tools/hurt_direction_test.tscn — стороны, поворот, несколько ударов, затухание.
## Та же сцена -- host / -- client: два ENet-процесса, порт 17797; -- shots — снимки с окном.

var _fails: int = 0
var _role: String = "solo"
var _rig: CameraRig
var _fx: HurtFx
var _players: Dictionary = {}
var _client: int = 0
var _ready_peer: bool = false
var _finished: bool = false
var _shots: bool = false


func _enter_tree() -> void:
	set_meta(Net.SCENE_META, "raid")


func _ready() -> void:
	Engine.max_fps = 60
	RaidEvents.enabled = false
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if not args.is_empty():
		_role = args[0]
	_shots = _role == "shots"
	Profile.use_file("user://profile_hurt_direction_%s.json" % _role, true)
	Profile.ensure()
	Profile.pending_raid = false
	get_tree().create_timer(40.0).timeout.connect(func() -> void: get_tree().quit(99))
	if _role == "host":
		Net.enter_scene("raid")
		_check("ENet хост", Net.host("Урон хост", 17797) == "")
		if not await _wait(func() -> bool: return not multiplayer.get_peers().is_empty(), 15.0):
			get_tree().quit(3)
			return
		_client = multiplayer.get_peers()[0]
		_spawn.rpc(_client)
		_check("сцена гостя готова", await _wait(func() -> bool: return _ready_peer, 15.0))
		await _network_host()
	elif _role == "client":
		Net.enter_scene("raid")
		_check("ENet гость", Net.join("127.0.0.1", "Урон гость", 17797) == "")
		_check("получен итог", await _wait(func() -> bool: return _finished, 30.0))
	else:
		_spawn(1)
		await _solo()
	print("hurt_direction_test[%s]: провалено %d" % [_role, _fails])
	await _cleanup()
	get_tree().quit(1 if _fails else 0)


@rpc("authority", "call_local", "reliable")
func _spawn(client: int) -> void:
	_client = client
	_rig = (load("res://scenes/player/camera_rig.tscn") as PackedScene).instantiate() as CameraRig
	add_child(_rig)
	_rig.set_process(false)
	_fx = _rig._hurt
	_fx.set_process(false)
	_fx.camera_basis = Basis.IDENTITY
	var peers: Array[int] = [1]
	if client != 1:
		peers.append(client)
	for peer: int in peers:
		var player: Player = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
		player.name = "Player_%d" % peer
		player.peer_id = peer
		player.set_multiplayer_authority(peer, true)
		player.get_node("Health").set_multiplayer_authority(1, true)
		player.loadout_mode = true
		player.position = Vector3(12.0, 1.0, 20.0)
		add_child(player)
		player.set_process(false)
		player.set_physics_process(false)
		player.inventory.equipment = {}
		_players[peer] = player
	if Net.is_networked() and not multiplayer.is_server():
		_peer_ready.rpc_id(1)


func _solo() -> void:
	var player: Player = _players[1] as Player
	var directions: Array[Vector3] = [Vector3.FORWARD, Vector3.RIGHT, Vector3.BACK, Vector3.LEFT]
	var expected: Array[Vector2] = [Vector2.UP, Vector2.RIGHT, Vector2.DOWN, Vector2.LEFT]
	var labels: Array[String] = ["спереди", "справа", "сзади", "слева"]
	for i: int in range(directions.size()):
		_fx._directions.clear()
		player.health.hp = player.health.max_hp
		player.health.take_damage(5.0, player.global_position + directions[i] * 10.0)
		_check(labels[i] + " — верная сторона", _fx._directions.size() == 1 and _fx.direction_on_screen(_fx._directions[0].direction).is_equal_approx(expected[i]))
		_check("урон снят один раз", is_equal_approx(player.health.hp, player.health.max_hp - 5.0))
	_fx.camera_basis = Basis(Vector3.UP, PI * 0.5)
	_check("повернулся к левому источнику — дуга спереди", _fx.direction_on_screen(Vector3.LEFT).is_equal_approx(Vector2.UP))
	_fx.camera_basis = Basis.from_euler(Vector3(1.2, 0.0, 0.4))
	_check("наклон взгляда не меняет сторону", _fx.direction_on_screen(Vector3.FORWARD).is_equal_approx(Vector2.UP))
	_fx.camera_basis = Basis.IDENTITY
	_fx._directions.clear()
	player.health.invulnerable = true
	player.health.take_damage(50.0, player.global_position + Vector3.RIGHT * 10.0)
	_fx._process(0.7)
	player.health.take_damage(50.0, player.global_position + Vector3.RIGHT * 10.0)
	_check("очередь обновляет одну дугу", _fx._directions.size() == 1 and is_zero_approx(float(_fx._directions[0].age)))
	player.health.take_damage(50.0, player.global_position + Vector3.LEFT * 10.0)
	_check("две стороны видны одновременно", _fx._directions.size() == 2)
	_check("попадания в бессмертии видны без потери hp", is_equal_approx(player.health.hp, player.health.max_hp - 5.0))
	_fx._process(float(Balance.HURT_FX.fade_sec) + 0.01)
	_check("дуги живут дольше виньетки", not _fx._rect.visible and _fx._indicator.visible)
	_fx._process(float(Balance.HURT_DIRECTION.hold_sec) + float(Balance.HURT_DIRECTION.fade_sec))
	_check("дуги исчезают сами", _fx._directions.is_empty() and not _fx._indicator.visible)
	_fx.hit(10.0)
	_fx.hit(10.0, Vector3.INF, Vector3.ZERO)
	_fx.hit(10.0, player.global_position, player.global_position)
	_check("неизвестный или нулевой источник без ложной стороны", _fx._directions.is_empty())
	_fx.hit(10.0, Vector3.ZERO, Vector3.RIGHT * 10.0)
	_check("источник в начале координат действителен", _fx._directions.size() == 1 and _fx.direction_on_screen(_fx._directions[0].direction).is_equal_approx(Vector2.LEFT))
	_fx._directions.clear()
	for i: int in range(10):
		_fx.hit(10.0, Vector3(sin(i * TAU / 10.0), 0.0, cos(i * TAU / 10.0)), Vector3.ZERO)
	_check("число дуг ограничено", _fx._directions.size() == int(Balance.HURT_DIRECTION.max_hits))
	if _shots:
		await _screenshots(player)


func _network_host() -> void:
	var guest: Player = _players[_client] as Player
	guest.health.take_damage(15.0, guest.global_position + Vector3.RIGHT * 10.0)
	await get_tree().create_timer(0.3).timeout
	_check("попадание гостю не показывает дугу хосту", _fx._directions.is_empty())
	_check("хост снял гостю hp один раз", is_equal_approx(guest.health.hp, guest.health.max_hp - 15.0))
	_check_guest.rpc_id(_client)
	_check("гость проверил направление", await _wait(func() -> bool: return _finished, 10.0))
	var host: Player = _players[1] as Player
	host.health.take_damage(10.0, host.global_position + Vector3.BACK * 10.0)
	_check("свой удар хост видит сзади", _fx._directions.size() == 1 and _fx.direction_on_screen(_fx._directions[0].direction).is_equal_approx(Vector2.DOWN))
	_finish.rpc_id(_client)
	await get_tree().create_timer(0.3).timeout


@rpc("authority", "call_remote", "reliable")
func _check_guest() -> void:
	var guest: Player = _players[_client] as Player
	_check("гость получил дугу справа", _fx._directions.size() == 1 and _fx.direction_on_screen(_fx._directions[0].direction).is_equal_approx(Vector2.RIGHT))
	_check("гость получил hp хоста без повторного урона", is_equal_approx(guest.health.hp, guest.health.max_hp - 15.0))
	_check("источник дошёл до владельца", guest._last_hit_from.is_equal_approx(guest.global_position + Vector3.RIGHT * 10.0))
	# Гость владеет Player, но подтверждать попадание может только хост.
	await get_tree().process_frame
	_fx._directions.clear()
	guest._rpc_hurt(99.0, guest.global_position + Vector3.LEFT, guest.global_position)
	_check("событие без отправителя-хоста отвергнуто", _fx._directions.is_empty())
	_peer_checked.rpc_id(1)


@rpc("any_peer", "call_remote", "reliable")
func _peer_ready() -> void:
	if multiplayer.is_server() and multiplayer.get_remote_sender_id() == _client:
		_ready_peer = true


@rpc("any_peer", "call_remote", "reliable")
func _peer_checked() -> void:
	if multiplayer.is_server() and multiplayer.get_remote_sender_id() == _client:
		_finished = true


@rpc("authority", "call_remote", "reliable")
func _finish() -> void:
	_finished = true


func _screenshots(player: Player) -> void:
	var background: CanvasLayer = CanvasLayer.new()
	background.layer = -1
	add_child(background)
	var rect: ColorRect = ColorRect.new()
	rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	rect.color = Color(0.3, 0.34, 0.36)
	background.add_child(rect)
	var cases: Dictionary = {"front": [Vector3.FORWARD], "back": [Vector3.BACK], "sides": [Vector3.LEFT, Vector3.RIGHT]}
	for key: String in cases:
		_fx._directions.clear()
		for direction: Vector3 in cases[key]:
			player.health.take_damage(10.0, player.global_position + direction * 10.0)
		_fx._process(0.0)
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://tools/_probe/hurt_direction_%s.png" % key))


func _wait(predicate: Callable, seconds: float) -> bool:
	var deadline: int = Time.get_ticks_msec() + int(seconds * 1000.0)
	while not bool(predicate.call()) and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	return bool(predicate.call())


func _check(label: String, ok: bool) -> void:
	if not ok:
		_fails += 1
	print("[%s][%s] %s" % [_role, "ok" if ok else "ПРОВАЛ", label])


func _cleanup() -> void:
	if Net.is_networked():
		var peer: MultiplayerPeer = multiplayer.multiplayer_peer
		Net._keep_own_scene(OfflineMultiplayerPeer.new())
		Net._active = false
		peer.close()
	_players.clear()
	for child: Node in get_children():
		child.queue_free()
	for frame: int in range(4):
		await get_tree().process_frame
