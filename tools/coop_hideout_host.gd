extends Node
## Кооп-убежище, хост (в паре с coop_hideout_client): созвать в убежище, дождаться друга, увидеть
## его, включить телевизор (у друга тоже), «Рейд всем» — оба в рейде со своим снаряжением.
## godot --path . res://tools/coop_hideout_host.tscn

var _fails: int = 0


func _ready() -> void:
	if name == "CoopHostRunner":
		_run()
		return
	var runner := Node.new()
	runner.name = "CoopHostRunner"
	runner.set_script(get_script())
	get_tree().root.add_child.call_deferred(runner)


func _run() -> void:
	Profile.use_file("user://profile_coop_host.json", true)
	Profile.ensure()
	_check("сервер поднят", Net.host("Хост") == "", "")
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	var t := 0.0
	while not _both_here():
		await get_tree().process_frame
		t += get_process_delta_time()
		if t > 40.0:
			break
	_check("в убежище двое (свой и друг)", _both_here(), str(Net.peer_scene))
	await get_tree().create_timer(2.0).timeout
	var friend := _friend()
	var p0 := friend.global_position if friend else Vector3.ZERO
	await get_tree().create_timer(2.5).timeout
	_check("друг ходит — у меня видно", friend != null and friend.global_position.distance_to(p0) > 0.5, "сдвинулся на %.2f" % (friend.global_position.distance_to(p0) if friend else -1.0))
	var tv := get_tree().current_scene.get_node_or_null("Activities/Tv") as HideoutActivity
	tv.request_use()
	await get_tree().create_timer(1.5).timeout
	Net.start_level.rpc(Floors.scene(Profile.floor), Profile.next_conditions)
	t = 0.0
	while not (Raid.current and Raid.current.local_player()):
		await get_tree().process_frame
		t += get_process_delta_time()
		if t > 40.0:
			break
	t = 0.0
	while get_tree().get_nodes_in_group("players").size() < 2 and t < 15.0:
		await get_tree().create_timer(0.25).timeout
		t += 0.25
	var n := get_tree().get_nodes_in_group("players").size()
	var names: Array = []
	var root := get_tree().current_scene.get_node_or_null("Players")
	if root:
		for c in root.get_children():
			names.append("%s(%s)" % [c.name, (c as Player).is_alive() if c is Player else "?"])
	_check("рейд всем: хост в рейде, игроков двое, снаряжение из профиля", Raid.current != null and n == 2 and Raid.current.local_player().loadout_mode,
		"игроков %d, Players: %s, сцены %s" % [n, str(names), str(Net.peer_scene)])
	await get_tree().create_timer(6.0).timeout
	print("coop_host: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _both_here() -> bool:
	return get_tree().current_scene != null and get_tree().current_scene.scene_file_path == Balance.HIDEOUT_SCENE \
		and get_tree().get_nodes_in_group("players").size() == 2


func _friend() -> Player:
	for p in get_tree().get_nodes_in_group("players"):
		if not (p as Player).is_local():
			return p
	return null


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
