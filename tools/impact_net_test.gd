extends Node3D
## Два процесса: -- host, затем -- client. Косметика в обе стороны и отсечение другой сцены.

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	set_meta(Net.SCENE_META, "impact_test")
	Net.enter_scene("impact_test")
	var is_host: bool = "host" in OS.get_cmdline_user_args()
	var error: String = Net.host("impact_host") if is_host else Net.join("127.0.0.1", "impact_client")
	if error != "":
		push_error(error)
		get_tree().quit(1)
		return
	if is_host:
		await _host()
	else:
		await _client()
	print("impact_net_test %s: провалено %d" % ["host" if is_host else "client", _fails])
	multiplayer.multiplayer_peer = OfflineMultiplayerPeer.new()
	get_tree().quit(_fails)


func _host() -> void:
	var connected: bool = false
	for attempt: int in range(300):
		for peer: int in multiplayer.get_peers():
			connected = connected or Net.visible_in(peer, "impact_test")
		if connected:
			break
		await get_tree().create_timer(0.1).timeout
	_check(connected, "клиент в той же сцене")
	_hit("metal")
	await _wait_decals(2)
	_check(ImpactFx._decals.size() == 2, "хост получил бетон клиента без повторов")
	await get_tree().create_timer(0.6).timeout
	_hit("metal")
	await get_tree().create_timer(0.7).timeout


func _client() -> void:
	await _wait_decals(1)
	_check(ImpactFx._decals.size() == 1, "клиент получил металл хоста")
	_hit("concrete")
	await get_tree().create_timer(0.3).timeout
	set_meta(Net.SCENE_META, "other")
	Net.enter_scene("other")
	await get_tree().create_timer(1.0).timeout
	_check(ImpactFx._decals.size() == 2, "другая сцена не получила второе попадание")


func _hit(kind: String) -> void:
	var body: StaticBody3D = StaticBody3D.new()
	body.set_meta("surface", kind)
	add_child(body)
	ImpactFx.spawn_hit({"collider": body, "position": Vector3.ZERO, "normal": Vector3.UP}, Vector3.DOWN)


func _wait_decals(count: int) -> void:
	for attempt: int in range(100):
		if ImpactFx._decals.size() >= count:
			return
		await get_tree().create_timer(0.1).timeout


func _check(ok: bool, label: String) -> void:
	if not ok:
		_fails += 1
		push_error(label)
