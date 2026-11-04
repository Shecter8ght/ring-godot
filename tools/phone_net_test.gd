extends Node3D
## Three real ENet peers: owner state, host inventory, remote model, stow and corpse.
var role: String
var failures: int = 0
var actors: Dictionary = {}
var ready_peers: Dictionary = {}
var finished: bool = false
var _equipped: bool = false

func _enter_tree() -> void:
	set_meta(Net.SCENE_META, "raid")

func check(ok: bool, title: String) -> void:
	print("PHONE NET ", role, " ", "PASS " if ok else "FAIL ", title)
	if not ok: failures += 1

func wait_for(test: Callable, seconds: float = 20.0) -> bool:
	var end := Time.get_ticks_msec() + int(seconds * 1000)
	while Time.get_ticks_msec() < end:
		if test.call(): return true
		await get_tree().process_frame
	return false

func _ready() -> void:
	role = String(OS.get_cmdline_user_args()[0])
	Profile.use_file("user://phone_net_" + role + ".json", true)
	Net.enter_scene("raid")
	if role == "host":
		check(Net.host("Phone host", 17798) == "", "host started")
		if await wait_for(func() -> bool: return multiplayer.get_peers().size() == 2):
			spawn.rpc(multiplayer.get_peers())
			check(await wait_for(func() -> bool: return ready_peers.size() == 2), "both guests ready")
			for actor: Player in actors.values(): actor.inventory.items = [ItemDb.make(PhoneGear.ID, 1)]
			equip.rpc(true)
			check(await wait_for(all_equipped), "both owner flags reach host")
			check(await wait_for(all_models_visible), "both remote wrist models visible")
			equip.rpc(false)
			check(await wait_for(all_stowed), "both phones stow remotely")
			for actor: Player in actors.values():
				var corpse := actor.inventory.take_all()
				check(corpse.filter(func(e: Dictionary) -> bool: return PhoneGear.personal(e)).is_empty(), "no phone in guest corpse")
			finish.rpc()
			await get_tree().create_timer(0.4).timeout
		else: check(false, "both guests connected")
	else:
		check(Net.join("127.0.0.1", "Phone " + role, 17798) == "", "joining")
		check(await wait_for(func() -> bool: return finished, 35), "host finished")
		await get_tree().create_timer(0.1).timeout
	print("PHONE NET ", role, " failures ", failures)
	Net.disconnect_all()
	await get_tree().process_frame
	get_tree().quit(1 if failures else 0)

@rpc("authority", "call_local", "reliable")
func spawn(peers: PackedInt32Array) -> void:
	for peer: int in peers:
		var actor := (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
		actor.name = "Actor_%d" % peer; actor.peer_id = peer
		actor.set_multiplayer_authority(peer); actor.get_node("Health").set_multiplayer_authority(1)
		actor.combat_enabled = false; add_child(actor)
		actor.set_process(false); actor.set_physics_process(false)
		actors[peer] = actor
	if not multiplayer.is_server(): announce.rpc_id(1)

@rpc("any_peer", "call_remote", "reliable")
func announce() -> void:
	ready_peers[multiplayer.get_remote_sender_id()] = true

@rpc("authority", "call_remote", "reliable")
func equip(on: bool) -> void:
	var actor: Player = actors.get(multiplayer.get_unique_id()) as Player
	if actor:
		if on: check(await wait_for(func() -> bool: return actor.inventory.has(PhoneGear.ID)), "host-issued personal item arrived")
		actor.phone_equipped = on
		_equipped = on

func all_equipped() -> bool:
	for actor: Player in actors.values():
		if not actor.phone_equipped: return false
	return actors.size() == 2

func all_models_visible() -> bool:
	for actor: Player in actors.values():
		var found := false
		for child: Node in actor.get_children():
			if child is PhoneWorldModel and is_instance_valid(child.model) and child.model.visible: found = true
		if not found: return false
	return true

func all_stowed() -> bool:
	for actor: Player in actors.values():
		if actor.phone_equipped: return false
	return true

@rpc("authority", "call_remote", "reliable")
func finish() -> void:
	check(not _equipped, "owner stowed")
	finished = true
