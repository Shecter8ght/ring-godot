extends Node
## Кооп-убежище, клиент (в паре с coop_hideout_host): подключиться по IP — в убежище, видеть хоста,
## пройтись, телевизор включился и у меня, рейд хоста — и я в рейде.
## godot --path . res://tools/coop_hideout_client.tscn

var _fails: int = 0


func _ready() -> void:
	if name == "CoopClientRunner":
		_run()
		return
	var runner := Node.new()
	runner.name = "CoopClientRunner"
	runner.set_script(get_script())
	get_tree().root.add_child.call_deferred(runner)


func _run() -> void:
	Profile.use_file("user://profile_coop_client.json", true)
	Profile.ensure()
	await get_tree().create_timer(3.0).timeout
	_check("подключение", Net.join("127.0.0.1", "Друг") == "", "")
	await Net.joined
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	var t := 0.0
	while get_tree().get_nodes_in_group("players").size() < 2:
		await get_tree().process_frame
		t += get_process_delta_time()
		if t > 30.0:
			break
	_check("в убежище вижу хоста", get_tree().get_nodes_in_group("players").size() == 2, str(Net.peer_scene))
	# хост засекает, где я, через 2 с — иду после
	await get_tree().create_timer(2.6).timeout
	Input.action_press("move_forward")
	await get_tree().create_timer(1.2).timeout
	Input.action_release("move_forward")
	# телевизор включил хост
	var tv: HideoutActivity = null
	t = 0.0
	while t < 10.0:
		tv = get_tree().current_scene.get_node_or_null("Activities/Tv") as HideoutActivity if get_tree().current_scene else null
		if tv and tv.state != 0:
			break
		await get_tree().create_timer(0.2).timeout
		t += 0.2
	_check("телевизор включил хост — включён и у меня", tv != null and tv.state == 1, str(tv.state if tv else -1))
	# общение: хост написал и сказал — ответить тем же
	t = 0.0
	while not (_heard("привет из убежища") and int(Chat.voice_bytes.get(1, 0)) > 4000) and t < 12.0:
		await get_tree().create_timer(0.2).timeout
		t += 0.2
	_check("чат: сообщение хоста пришло", _heard("привет из убежища"), str(Chat.messages))
	_check("голос хоста пришёл", int(Chat.voice_bytes.get(1, 0)) > 4000, str(Chat.voice_bytes))
	var host_pl: Player = null
	for p in get_tree().get_nodes_in_group("players"):
		if (p as Player).peer_id == 1:
			host_pl = p
	_check("реплика хоста над головой", host_pl != null and host_pl.get_node_or_null("ChatBubble") != null, "")
	Chat.send("принял")
	var tone := PackedFloat32Array()
	for i in range(int(0.5 * float(Balance.VOICE.rate))):
		tone.append(0.3 * sin(TAU * 330.0 * float(i) / float(Balance.VOICE.rate)))
	Chat.debug_say(tone)
	t = 0.0
	while not (Raid.current and Raid.current.local_player()):
		await get_tree().process_frame
		t += get_process_delta_time()
		if t > 40.0:
			break
	await get_tree().create_timer(3.0).timeout
	_check("рейд хоста — и я в рейде, со своим снаряжением", Raid.current != null and Raid.current.local_player() != null and Raid.current.local_player().loadout_mode, "")
	# хост считает игроков в рейде позже — не уходить раньше него
	await get_tree().create_timer(12.0).timeout
	print("coop_client: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _heard(t: String) -> bool:
	for m in Chat.messages:
		if t in m:
			return true
	return false


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
