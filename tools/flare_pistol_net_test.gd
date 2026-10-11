extends Node3D
## Два настоящих ENet-процесса: владелец ведёт клип, хост ведёт патрон и вызов груза.
const CASES := ["cancel", "reload_red", "red_shot", "reload_green", "roof", "green_shot", "duplicate"]
const PORT := 17796
var role: String
var fails: int = 0
var client_id: int = 0
var ready_remote: bool = false
var actors: Dictionary = {}
var raid: Raid
var incoming: Array[Dictionary] = []
var completed: String = ""
var finished: bool = false
var saw_open: bool = false
var seed_rev: int = 0
var roof: StaticBody3D


func _enter_tree() -> void:
	set_meta(Net.SCENE_META, "raid")


func _ready() -> void:
	Engine.max_fps = 120
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.is_empty() or not args[0] in ["host", "client"]:
		get_tree().quit(1)
		return
	role = args[0]
	Profile.use_file("user://profile_flare_net_%s.json" % role, true)
	Profile.ensure()
	RaidEvents.enabled = false
	var floor_body := StaticBody3D.new()
	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(30, .3, 30)
	collision.shape = shape
	collision.position.y = -.15
	floor_body.add_child(collision)
	add_child(floor_body)
	Net.enter_scene("raid")
	if role == "host":
		await _host()
	else:
		await _client()
	print("flare_pistol_net_test[%s]: провалено %d" % [role, fails])
	set_process(false)
	Net.disconnect_all()
	Raid.current = null
	for sound: Node in Audio.get_children():
		if sound is AudioStreamPlayer:
			(sound as AudioStreamPlayer).stop()
			(sound as AudioStreamPlayer).stream = null
		elif sound is AudioStreamPlayer3D:
			(sound as AudioStreamPlayer3D).stop()
			(sound as AudioStreamPlayer3D).stream = null
	await get_tree().create_timer(.2).timeout
	get_tree().quit(1 if fails else 0)


func check(label: String, ok: bool) -> void:
	print("[%s:%s] %s" % [role, "ok" if ok else "FAIL", label])
	if not ok:
		fails += 1


func until(condition: Callable, seconds: float = 12.0) -> bool:
	var deadline: int = Time.get_ticks_msec() + int(seconds * 1000)
	while not condition.call() and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	return bool(condition.call())


func _host() -> void:
	check("сервер на отдельном порту", Net.host("Flare host", PORT) == "")
	if not await until(func() -> bool: return not multiplayer.get_peers().is_empty(), 40.0):
		check("клиент подключился", false)
		return
	client_id = int(multiplayer.get_peers()[0])
	_spawn.rpc(client_id)
	if not await until(func() -> bool: return ready_remote):
		check("одинаковые пути узлов", false)
		return
	var person: Player = actors[client_id]
	for label: String in CASES:
		seed_rev += 10
		var aid: String = "supply_signal" if label in ["roof", "green_shot", "duplicate"] else "flare"
		var n: int = 0 if label in ["cancel", "reload_red"] else 1
		var entry: Dictionary = ItemDb.make("signal_launcher", 1)
		entry["rev"] = seed_rev
		entry["mag"] = {"id": "", "ammo": aid, "rounds": n}
		person.inventory.equipment = {"secondary": entry, "backpack": ItemDb.make(Balance.BACKPACK_START, 1)}
		person.inventory.items = [ItemDb.make("flare", 2), ItemDb.make("supply_signal", 2)]
		person.inventory.loadout_ready = true
		person._signal_host_fire_ms = -10000
		completed = ""
		saw_open = false
		if label == "roof":
			roof = (get_child(0) as StaticBody3D).duplicate() as StaticBody3D
			add_child(roof)
			roof.position.y = 3.0
			await get_tree().physics_frame
		_request.rpc_id(client_id, label, seed_rev)
		check(label + " выполнен клиентом", await until(func() -> bool: return completed == label, 20.0))
		await get_tree().create_timer(.3).timeout
		entry = person.inventory.equipment.secondary
		match label:
			"cancel": check("отмена не затронула вещи хоста", Gear.total_rounds(entry) == 0 and person.inventory.count("flare") == 2)
			"reload_red": check("хост зарядил один красный, наблюдал перелом", Gear.total_rounds(entry) == 1 and person.inventory.count("flare") == 1 and saw_open)
			"red_shot": check("один красный выстрел на хосте", Gear.total_rounds(entry) == 0 and person.inventory.count("flare") == 2 and get_tree().get_nodes_in_group("sky_flares").size() == 1)
			"reload_green": check("смена типа сохранила живой красный", Gear.mag_top(entry.mag) == "supply_signal" and person.inventory.count("flare") == 3 and person.inventory.count("supply_signal") == 1)
			"roof":
				check("отказ под крышей сохранил зелёный", Gear.total_rounds(entry) == 1 and raid.supply_state.is_empty())
				roof.queue_free()
				await get_tree().physics_frame
			"green_shot": check("один вызов без двойного расхода", Gear.total_rounds(entry) == 0 and person.inventory.count("supply_signal") == 2 and not raid.supply_state.is_empty() and get_tree().get_nodes_in_group("supply_signals").size() == 1)
			"duplicate": check("второй вызов сохранил патрон", Gear.total_rounds(entry) == 1 and get_tree().get_nodes_in_group("supply_signals").size() == 1)
	_finish.rpc_id(client_id)
	await get_tree().create_timer(.6).timeout


func _client() -> void:
	check("клиент подключается", Net.join("127.0.0.1", "Flare client", PORT) == "")
	while not finished:
		if incoming.is_empty():
			if not await until(func() -> bool: return not incoming.is_empty() or finished, 40.0):
				check("получен сценарий", false)
				return
		else:
			var request: Dictionary = incoming.pop_front()
			await _case(String(request.label), int(request.rev))


@rpc("authority", "call_local", "reliable")
func _spawn(peer: int) -> void:
	client_id = peer
	Net.enter_scene("raid")
	raid = Raid.new()
	raid.name = "Raid"
	add_child(raid)
	raid.set_process(false)
	var parent := Node3D.new()
	parent.name = "Players"
	add_child(parent)
	for id: int in [1, peer]:
		var person: Player = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
		person.name = "Player_%d" % id
		person.peer_id = id
		person.set_multiplayer_authority(id, true)
		person.get_node("Health").set_multiplayer_authority(1, true)
		person.loadout_mode = true
		person.position = Vector3(-4.0 if id == 1 else 4.0, .05, 0)
		parent.add_child(person)
		person.health.invulnerable = true
		person.inventory.set_multiplayer_authority(1)
		actors[id] = person
		raid.register(id, "Flare_%d" % id)
	if not multiplayer.is_server():
		_ready_remote.rpc_id(1)


@rpc("any_peer", "call_remote", "reliable")
func _ready_remote() -> void:
	if multiplayer.get_remote_sender_id() == client_id:
		ready_remote = true


@rpc("authority", "call_remote", "reliable")
func _request(label: String, rev: int) -> void:
	incoming.append({"label": label, "rev": rev})


func _case(label: String, rev: int) -> void:
	var person: Player = actors[client_id]
	if not await until(func() -> bool: return int((person.inventory.equipment.get("secondary", {}) as Dictionary).get("rev", -1)) == rev):
		check("репликация снаряжения " + label, false)
		_done.rpc_id(1, label)
		return
	person.cancel_weapon_action()
	person._ws.clear()
	person._pm_entries.clear()
	person.weapon_slot = ""
	person.signal_reload_ammo = "supply_signal" if label == "reload_green" else "flare"
	person._switch("secondary", false)
	person._update_hand()
	await get_tree().create_timer(.85).timeout
	if label in ["cancel", "reload_red", "reload_green"]:
		person._start_reload(person.spec())
		check(label + " запустил штатную перезарядку", person.reload_timer > 5.0)
		if label == "cancel":
			await get_tree().create_timer(.7).timeout
			person._switch("primary", false)
		else:
			check(label + " получил ответ хоста", await until(func() -> bool: return person._pm_action.is_empty() and person.ammo == 1))
	else:
		person._fire(person.spec())
		var repeated: Dictionary = person._pm_action.duplicate(true)
		if label == "green_shot" and not repeated.is_empty():
			person._rpc_pm_commit.rpc_id(1, repeated)
		check(label + " получил ответ", await until(func() -> bool: return person._pm_action.is_empty()))
		await get_tree().create_timer(.2).timeout
		check(label + " локальный расход совпал", person.ammo == (1 if label in ["roof", "duplicate"] else 0))
	_done.rpc_id(1, label)


@rpc("any_peer", "call_remote", "reliable")
func _done(label: String) -> void:
	if multiplayer.get_remote_sender_id() == client_id:
		completed = label


@rpc("authority", "call_remote", "reliable")
func _finish() -> void:
	finished = true


func _process(_delta: float) -> void:
	if role != "host" or not actors.has(client_id):
		return
	if not is_instance_valid(actors[client_id]):
		return
	var rig: WeaponRig = (actors[client_id] as Player)._weapon_rig
	if rig and rig.part("Barrel") and absf(rig.part("Barrel").rotation.x) > .3:
		saw_open = true
