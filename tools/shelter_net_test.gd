extends Node
## Три настоящих ENet процесса: поздний вход, общие каналы/питание, движение и рейд всем.

var _mode: String
var _fails: int = 0
var _reports: Dictionary = {}

func _ready() -> void:
	if name == &"ShelterNetRunner":
		_run()
	else:
		var runner: Node = Node.new()
		runner.name = "ShelterNetRunner"
		runner.set_script(get_script())
		get_tree().root.add_child.call_deferred(runner)

func _run() -> void:
	_mode = OS.get_cmdline_user_args()[0]
	Profile.use_file("user://shelter_net_%s_test.json" % _mode, true)
	Profile.hideout_media = {"tv":3,"radio":2,"power":true} if _mode == "c2" else {}
	if _mode != "host":
		await get_tree().create_timer(12.0 if _mode == "c2" else 2.0).timeout
		_check("connect", Net.join("127.0.0.1", _mode) == "")
		await Net.joined
	else:
		_check("host", Net.host("ShelterHost") == "")
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	if _mode != "host":
		return
	await _players(2)
	await get_tree().create_timer(1.0).timeout
	_tv()._switch(2)
	_radio()._switch(3)
	_power()._use(1)
	await _players(3)
	await get_tree().create_timer(1.5).timeout
	_check("three players replicated", get_tree().get_nodes_in_group("players").size() == 3)
	var actors: Array[Node] = get_tree().get_nodes_in_group("players")
	for i: int in range(actors.size()):
		for j: int in range(i+1,actors.size()):
			_check("spawns do not overlap", (actors[i] as Node3D).global_position.distance_to((actors[j] as Node3D).global_position)>1.1)
	await _phase("late_join",2,3,false)
	_command.rpc("guest_switch",3,0,true)
	await get_tree().create_timer(2.5).timeout
	await _phase("guest_switch_result",3,0,true)
	for channel: int in range(4):
		_tv()._switch(channel)
		_radio()._switch(channel)
		await get_tree().create_timer(.5).timeout
		await _phase("channels_%d" % channel,channel,channel,true)
	var before: Dictionary = {}
	for actor: Node in actors:
		before[(actor as Player).peer_id] = (actor as Node3D).global_position
	_command.rpc("move",0,0,true)
	await _command("move",0,0,true)
	await get_tree().create_timer(1.5).timeout
	for actor: Node in actors:
		_check("movement replicated peer %d" % (actor as Player).peer_id,(actor as Node3D).global_position.distance_to(before[(actor as Player).peer_id])>.8)
	# Частичный возврат из рейда: досуг двух клиентов работает без root убежища у хоста.
	Net.change_scene(Floors.scene(Profile.floor))
	await get_tree().create_timer(4.0).timeout
	_reports.clear()
	_command.rpc("without_host",0,0,true)
	await _wait_reports("without_host")
	Net.change_scene(Balance.HIDEOUT_SCENE)
	await _players(3)
	await get_tree().create_timer(2.0).timeout
	await _phase("host_return",0,0,true)
	Net.start_level.rpc(Floors.scene(Profile.floor),Profile.next_conditions)
	await _players(3,true)
	await get_tree().create_timer(2.0).timeout
	# Детерминированное будущее расписание: обеим копиям Weather оно должно прийти.
	RaidWeather.current._rpc_schedule(120.0,180.0)
	RaidWeather.current._known.clear()
	RaidWeather.current._share_schedule()
	await get_tree().create_timer(.35).timeout
	await _phase("raid",0,0,true)
	await get_tree().create_timer(3.0).timeout
	print("SHELTER_NET host failures=%d" % _fails)
	_finish.rpc(_fails)
	await Net.change_scene("res://tools/shelter_net_end.tscn")
	Net.enter_scene("menu")
	await get_tree().create_timer(.4).timeout
	Net.disconnect_all()
	get_tree().current_scene.queue_free()
	await get_tree().create_timer(.4).timeout
	get_tree().quit(1 if _fails>0 else 0)

func _players(count: int, raid: bool = false) -> void:
	var elapsed: float = 0
	while elapsed<45:
		if get_tree().current_scene and get_tree().get_nodes_in_group("players").size()>=count and (not raid or Raid.current != null):
			return
		await get_tree().create_timer(.25).timeout
		elapsed += .25
	_check("players ready count=%d raid=%s" % [count,raid],false)

func _phase(label: String,tv: int,radio: int,power: bool) -> void:
	_reports.clear()
	_command.rpc(label,tv,radio,power)
	await _command(label,tv,radio,power)
	await _wait_reports(label)

func _wait_reports(label: String) -> void:
	var elapsed: float = 0
	while _reports.size()<2 and elapsed<10:
		await get_tree().create_timer(.1).timeout
		elapsed+=.1
	_check("%s guest reports" % label,_reports.size()==2)
	for id: int in _reports:
		_check("%s peer %d" % [label,id],int(_reports[id])==0)

@rpc("authority","call_remote","reliable")
func _command(label: String,tv: int,radio: int,power: bool) -> void:
	var previous: int = _fails
	if label == "without_host":
		if _mode == "c1":
			_tv().request_use()
			_radio().request_use()
		await get_tree().create_timer(1.0).timeout
		_check("without host TV/radio shared",_tv().state==0 and _radio().state==0)
		_check("power request waits for authority",not _power().can_use())
		_report.rpc_id(1,_fails-previous)
		return
	if label == "guest_switch":
		if _mode == "c1":
			_tv().request_use()
			_radio().request_use()
			var player: Player = get_tree().current_scene.get("_player") as Player
			player.global_position = _power().global_position + Vector3(0,0,1)
			await get_tree().create_timer(.35).timeout
			_power().request_use()
			await get_tree().create_timer(.4).timeout
			player.global_position = Vector3(0,0,9.55)
		return
	if label == "move":
		Input.action_press("move_forward")
		await get_tree().create_timer(1.0).timeout
		Input.action_release("move_forward")
		return
	if label == "raid":
		await _players(3,true)
		await get_tree().create_timer(1.0).timeout
		_check("raid with own equipment",Raid.current != null and Raid.current.local_player()!=null and Raid.current.local_player().loadout_mode)
		_check("raid future weather schedule received",RaidWeather.current._rain_at != INF and RaidWeather.current._fog_lift_at != INF)
		_check("raid event setup received",not RaidEvents.current._alarms.is_empty())
	else:
		_check(label+" TV",_tv().state==tv)
		_check(label+" radio",_radio().state==radio)
		_check(label+" generator",_power().enabled==power)
		_check(label+" light state",((_level().get_node("Lights/HubWest") as Light3D).light_energy>0)==power)
		_check(label+" profile",int(Profile.hideout_media.get("tv",-1))==tv and int(Profile.hideout_media.get("radio",-1))==radio and bool(Profile.hideout_media.get("power",true))==power)
		if label == "host_return" and _mode != "host":
			_check("host return does not teleport guests",(_level().get("_player") as Player).global_position.z<9.0)
	if _mode != "host":
		_report.rpc_id(1,_fails-previous)

@rpc("any_peer","call_remote","reliable")
func _report(failures: int) -> void:
	if Net.is_host():
		_reports[multiplayer.get_remote_sender_id()] = failures

@rpc("authority","call_remote","reliable")
func _finish(host_fails: int) -> void:
	print("SHELTER_NET %s failures=%d host_failures=%d" % [_mode,_fails,host_fails])
	await Net.change_scene("res://tools/shelter_net_end.tscn")
	Net.enter_scene("menu")
	await get_tree().create_timer(.4).timeout
	Net.disconnect_all()
	get_tree().current_scene.queue_free()
	await get_tree().create_timer(.4).timeout
	get_tree().quit(1 if _fails+host_fails>0 else 0)

func _level() -> Node:
	return get_tree().current_scene
func _tv() -> HideoutActivity:
	return _level().get_node("Activities/Tv") as HideoutActivity
func _radio() -> HideoutActivity:
	return _level().get_node("Activities/Radio") as HideoutActivity
func _power() -> ShelterPower:
	return _level().get_node("Gameplay/GeneratorPower") as ShelterPower
func _check(label: String,ok: bool) -> void:
	if not ok: _fails+=1
	print("[%s] %s %s" % ["ok" if ok else "FAIL",_mode,label])
