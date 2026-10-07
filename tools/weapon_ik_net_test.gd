extends Node3D
## Три процесса ENet: владелец отводит оружие, остальные получают величину и сторону позы.

var _role: String
var _ready_peers: Dictionary = {}
var _reports: Dictionary = {}
var _players: Array[Player] = []
var _camera: CameraRig
var _fails: int = 0
var _checks: int = 0


func _ready() -> void:
	Engine.max_fps = 90
	_role = OS.get_cmdline_user_args()[0]
	Profile.use_file("user://weapon_ik_net_%s_test.json" % _role, true)
	set_meta(Net.SCENE_META, "raid")
	RaidEvents.enabled = false
	_box(Vector3(16, .2, 16), Vector3(0, -.1, 0))
	_box(Vector3(16, 3, .2), Vector3(0, 1.5, .62))
	if _role == "host":
		_check("host starts", Net.host("IK Host") == "")
		if not await _wait(func() -> bool: return multiplayer.get_peers().size() == 2, 30.0):
			_check("two guests connected", false)
			get_tree().quit(1)
			return
		_spawn.rpc([1, multiplayer.get_peers()[0], multiplayer.get_peers()[1]])
		if not await _wait(func() -> bool: return _ready_peers.size() == 2, 20.0):
			_check("guests spawned", false)
			_finish.rpc(_fails)
			return
		for stage: String in ["free", "wall", "prone_wall", "return"]:
			_reports.clear()
			_move.rpc(stage)
			await get_tree().create_timer(1.5).timeout
			var expected: Dictionary = {}
			for player: Player in _players: expected[player.peer_id] = [player.weapon_obstruction, player.weapon_ready_up]
			_inspect.rpc(stage, expected)
			await _wait(func() -> bool: return _reports.size() == 2, 10.0)
			_check(stage + " guest reports", _reports.size() == 2)
			for peer: int in _reports:
				_check(stage + " guest %d" % peer, int(_reports[peer]) == 0)
		_finish.rpc(_fails)
	else:
		await get_tree().create_timer(1.0 if _role == "c1" else 2.0).timeout
		_check("guest joins", Net.join("127.0.0.1", _role) == "")
		# Ограничить зависание стенда при недоступном хосте.
		await get_tree().create_timer(70.0).timeout
		get_tree().quit(1)


@rpc("authority", "call_local", "reliable")
func _spawn(peers: Array) -> void:
	Net.enter_scene("raid")
	for i: int in range(peers.size()):
		var peer: int = int(peers[i])
		var player: Player = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
		player.name = "Player_%d" % peer
		player.peer_id = peer
		player.set_multiplayer_authority(peer, true)
		player.get_node("Health").set_multiplayer_authority(1, true)
		player.position = Vector3((i - 1) * 3, .02, -2)
		add_child(player)
		_players.append(player)
		if player.is_local():
			player._switch("AK12_BASE", false)
			_camera = (load("res://scenes/player/camera_rig.tscn") as PackedScene).instantiate() as CameraRig
			_camera.name = "CameraRig"
			add_child(_camera)
			_camera.set_target(player)
			player._camera_rig = _camera
			CameraRig._settings_loaded = true
			CameraRig.first_person_mode = true
	if _role != "host": _peer_ready.rpc_id(1)


@rpc("any_peer", "call_remote", "reliable")
func _peer_ready() -> void:
	_ready_peers[multiplayer.get_remote_sender_id()] = true


@rpc("authority", "call_local", "reliable")
func _move(stage: String) -> void:
	for player: Player in _players:
		if not player.is_local(): continue
		player.velocity = Vector3.ZERO
		player.position.z = .05 if stage.ends_with("wall") else -2.0
		player.stance = Player.Stance.PRONE if stage == "prone_wall" else Player.Stance.STAND
		player._apply_stance()
		_camera._look_yaw = 0.0
		_camera._look_pitch = 0.0


@rpc("authority", "call_local", "reliable")
func _inspect(stage: String, expected: Dictionary) -> void:
	var before: int = _fails
	var blocked: bool = stage.ends_with("wall")
	for player: Player in _players:
		var label: String = "%s peer %d" % [stage, player.peer_id]
		_check(label + " obstruction replicated", player.weapon_obstruction > .12 if blocked else player.weapon_obstruction < .001)
		_check(label + " owner weight and direction agree", absf(player.weapon_obstruction - float(expected[player.peer_id][0])) < .04 and player.weapon_ready_up == bool(expected[player.peer_id][1]))
		print("NET_IK_POSE ", label, " stance=", player.stance, " eye=", player.eye_position(), " obstruction=", player.weapon_obstruction, " up=", player.weapon_ready_up)
		_check(label + " authority preserved", player.get_multiplayer_authority() == player.peer_id and player.health.get_multiplayer_authority() == 1)
		var animator: CharacterAnimator = player.get_node("CharacterAnimator") as CharacterAnimator
		if not player.is_local() and blocked:
			_check(label + " remote skeleton folds", animator._collision_ik.clearance.weight >= .12)
		if player.is_local() and blocked:
			_check(label + " visible pose available", _camera.weapon_clearance.valid and _camera._viewmodel.visible)
			var ammo: int = player.ammo
			player._fire(player.spec())
			_check(label + " blocked shot keeps ammo", player.ammo == ammo)
	if _role != "host": _report.rpc_id(1, _fails - before)


@rpc("any_peer", "call_remote", "reliable")
func _report(failures: int) -> void:
	_reports[multiplayer.get_remote_sender_id()] = failures


@rpc("authority", "call_local", "reliable")
func _finish(host_failures: int) -> void:
	print("WEAPON_IK_NET %s checks=%d failures=%d host_failures=%d" % [_role, _checks, _fails, host_failures])
	for player: Player in _players:
		player.process_mode = Node.PROCESS_MODE_DISABLED
	_camera.process_mode = Node.PROCESS_MODE_DISABLED
	# Сначала остановить визуальные обработчики, затем закрывать peer и удалять скелеты.
	# Выход со стенда не вызывает игровой возврат в меню при разрыве связи.
	if multiplayer.peer_disconnected.is_connected(Net._on_peer_disconnected): multiplayer.peer_disconnected.disconnect(Net._on_peer_disconnected)
	if multiplayer.server_disconnected.is_connected(Net._on_server_disconnected): multiplayer.server_disconnected.disconnect(Net._on_server_disconnected)
	Net.enter_scene("menu")
	# Закрыть фильтр сцены и дать последним delta прийти, пока их узлы ещё существуют.
	await get_tree().create_timer(.5 if _role == "host" else .9).timeout
	Net.disconnect_all()
	_players.clear()
	for child: Node in get_children():
		remove_child(child)
		child.free()
	get_tree().quit(1 if _fails + host_failures > 0 else 0)


func _wait(condition: Callable, seconds: float) -> bool:
	var elapsed: float = 0.0
	while elapsed < seconds:
		if bool(condition.call()): return true
		await get_tree().create_timer(.1).timeout
		elapsed += .1
	return false


func _box(size: Vector3, position: Vector3) -> void:
	var body: StaticBody3D = StaticBody3D.new()
	body.position = position
	var shape: BoxShape3D = BoxShape3D.new()
	shape.size = size
	var collision: CollisionShape3D = CollisionShape3D.new()
	collision.shape = shape
	body.add_child(collision)
	add_child(body)


func _check(label: String, ok: bool) -> void:
	_checks += 1
	if not ok: _fails += 1
	print("[%s] %s %s" % ["ok" if ok else "FAIL", _role, label])
