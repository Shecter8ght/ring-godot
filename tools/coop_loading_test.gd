extends Node
## Долгая загрузка зоны 1 не должна выкидывать друга в убежище.
## Два процесса: -- host client 17780 и через 3 с -- client client 17780.
## Второй аргумент — чью загрузку остановить на 35 с (client или host), третий — порт.
## Отдельный порт позволяет проверять, не закрывая игру владельца на 7777.

const ROUTE: String = "res://scenes/levels/zone01_mall.tscn"
const STALL_MS: int = 35000
const WAIT_MS: int = 110000
var _role: String = "host"
var _stall_role: String = "client"
var _port: int = 17780
var _stalled: bool = false
var _lost: bool = false
var _fails: int = 0
var _ready_peers: Dictionary = {}
var _hideout_peers: Dictionary = {}
var _results: Dictionary = {}
var _exercise: bool = false
var _finished: bool = false


func _ready() -> void:
	if name != "CoopLoadingRunner":
		var runner: Node = Node.new()
		runner.name = "CoopLoadingRunner"
		runner.set_script(get_script())
		get_tree().root.add_child.call_deferred(runner)
		return
	_run()


func _run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if not args.is_empty():
		_role = String(args[0])
	if args.size() > 1:
		_stall_role = String(args[1])
	if args.size() > 2:
		_port = int(args[2])
	Profile.use_file("user://profile_coop_loading_%s_test.json" % _role, true)
	Profile.floor = "zone01"
	RaidEvents.enabled = false
	get_tree().node_added.connect(_on_added)
	multiplayer.server_disconnected.connect(func() -> void: _lost = true)
	multiplayer.peer_disconnected.connect(func(_id: int) -> void:
		if not _finished:
			_lost = true)
	var error: String = Net.host("Хост", _port) if _role == "host" else Net.join("127.0.0.1", "Друг", _port)
	if error != "":
		_check("соединение", false, error)
		get_tree().quit(1)
		return
	if _role == "client":
		await Net.joined
	Net.change_scene(Balance.HIDEOUT_SCENE, "Загрузка общего убежища")
	await _wait(func() -> bool:
		return not Loading.active and _players().size() == 2 and Net.peer_scene.values().count("hideout") == 2)
	_check("оба в убежище", not _lost and _players().size() == 2, str(Net.peer_scene))
	if not _lost:
		_hideout_ready.rpc_id(1)
	await _wait(func() -> bool:
		return not Loading.active and get_tree().current_scene != null and get_tree().current_scene.scene_file_path == ROUTE and _players().size() == 2 and Net.peer_scene.values().count("raid") == 2)
	_check("оба в рейде после задержки", not _lost and Net.is_networked() and _players().size() == 2 and Net.peer_scene.values().count("raid") == 2, str(Net.peer_scene))
	if not _lost and Net.is_networked() and Raid.current != null:
		_mark_ready.rpc_id(1)
		await _wait(func() -> bool: return _exercise)
		if _exercise:
			var remote: Player = null
			for p: Node in _players():
				if (p as Player).peer_id != multiplayer.get_unique_id():
					remote = p as Player
			var first: Vector3 = remote.global_position
			await get_tree().create_timer(0.5).timeout
			Raid.current.local_player().global_position += Vector3(3.0, 0.0, 0.0)
			await get_tree().create_timer(3.0).timeout
			_check("движение напарника доходит", remote.global_position.distance_to(first) > 1.0, str(remote.global_position.distance_to(first)))
		_check("связь сохранена", not _lost and Net.player_names.size() == 2, str(Net.player_names))
		_result.rpc_id(1, _fails)
		await _wait(func() -> bool: return _finished)
		_check("оба закончили проверки", _finished, "")
	if _role == _stall_role:
		_check("задержка была", _stalled, "")
	# Хост закрывается после клиента, чтобы штатный конец теста не выглядел потерей связи.
	if _role == "host":
		await get_tree().create_timer(2.0).timeout
	print("coop_loading[%s/%s]: провалов %d" % [_role, _stall_role, _fails])
	get_tree().quit(1 if _fails > 0 else 0)


func _process(_delta: float) -> void:
	if name != "CoopLoadingRunner" or Raid.current == null:
		return
	for p: Node in _players():
		(p as Player).health.invulnerable = true


func _players() -> Array[Node]:
	return get_tree().get_nodes_in_group("players")


func _wait(predicate: Callable) -> void:
	var began: int = Time.get_ticks_msec()
	while not predicate.call() and not _lost and Time.get_ticks_msec() - began < WAIT_MS:
		await get_tree().process_frame


func _check(label: String, okay: bool, detail: String) -> void:
	print("%s[%s] %s %s" % ["OK" if okay else "FAIL", _role, label, detail])
	if not okay:
		_fails += 1


func _on_added(node: Node) -> void:
	if _role == _stall_role and not _stalled and node.scene_file_path == ROUTE:
		_stalled = true
		print("coop_loading: главный поток %s остановлен на %d мс" % [_role, STALL_MS])
		OS.delay_msec(STALL_MS)
		print("coop_loading: главный поток продолжает загрузку")


@rpc("any_peer", "call_local", "reliable")
func _hideout_ready() -> void:
	if not Net.is_host():
		return
	var sender: int = multiplayer.get_remote_sender_id()
	_hideout_peers[sender if sender != 0 else multiplayer.get_unique_id()] = true
	if _hideout_peers.size() == 2:
		Net.start_level.rpc(ROUTE, RaidConditions.DEFAULT)


@rpc("any_peer", "call_local", "reliable")
func _mark_ready() -> void:
	if not Net.is_host():
		return
	var sender: int = multiplayer.get_remote_sender_id()
	_ready_peers[sender if sender != 0 else multiplayer.get_unique_id()] = true
	if _ready_peers.size() == 2:
		_begin.rpc()


@rpc("authority", "call_local", "reliable")
func _begin() -> void:
	_exercise = true


@rpc("any_peer", "call_local", "reliable")
func _result(count: int) -> void:
	if not Net.is_host():
		return
	var sender: int = multiplayer.get_remote_sender_id()
	_results[sender if sender != 0 else multiplayer.get_unique_id()] = count
	if _results.size() == 2:
		_finish.rpc()


@rpc("authority", "call_local", "reliable")
func _finish() -> void:
	_finished = true
