extends Node
## Реальный ENet на отдельном порту: груз у одного носителя, общий зачёт,
## UUID клиента у хоста, возвращённый ствол виден клиенту, вынос напарником без копии.
const PORT: int = 17786
var role: String = "host"
var fails: int = 0
var client_ready: bool = false
var client_uid: String = ""
var phase: int = 0
var result: int = -1


func _ready() -> void:
	if name != "EngravingNetRunner":
		var runner: Node = Node.new()
		runner.name = "EngravingNetRunner"
		runner.set_script(get_script())
		get_tree().root.add_child.call_deferred(runner)
		return
	_run()


func _run() -> void:
	role = String(OS.get_cmdline_user_args()[0])
	Profile.use_file("user://engraving_net_%s.json" % role, true)
	Profile.equipment["primary"] = ItemDb.make("wpn_ar_01", 1)
	Profile.equipment.primary["engraving"] = WeaponMark.make(Profile.equipment.primary, role, "left_2")
	Profile.from_hideout = true
	Profile.save()
	RaidEvents.enabled = false
	if role == "host":
		Quests.start("own_mark")
		Quests.finish_talk("own_mark", "trader", "intro")
	check("соединение", (Net.host("Хост", PORT) if role == "host" else Net.join("127.0.0.1", "Друг", PORT)) == "")
	if role == "client":
		await Net.joined
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	await until(func() -> bool: return get_tree().get_nodes_in_group("players").size() == 2)
	if role == "host":
		Net.start_level.rpc("res://scenes/levels/f1_ring.tscn", {"time":"day", "weather":"clear", "power":"on"})
	await until(func() -> bool: return Raid.current != null and Raid.current.local_player() != null and get_tree().get_nodes_in_group("players").size() == 2 and Raid.current.local_player().inventory.loadout_ready)
	var me: Player = Raid.current.local_player()
	if me == null:
		get_tree().quit(1)
		return
	me.health.hp = 1e9
	var site: QuestSite = null
	await until(func() -> bool: return get_tree().current_scene.find_child("Quest_engraver_frame", true, false) != null)
	site = get_tree().current_scene.find_child("Quest_engraver_frame", true, false) as QuestSite
	if role == "client":
		me.global_position = site.global_position + Vector3(0.8, 0.1, 0)
		await get_tree().create_timer(0.6).timeout
		_ready_client.rpc_id(1, String(me.inventory.equipment.primary.uid))
		Quests.request_site("engraver_frame")
		await until(func() -> bool: return me.inventory.has("engraver_frame"))
		check("клиент получает физическую раму", me.inventory.has("engraver_frame"))
		await until(func() -> bool: return phase >= 1)
		var recovered: bool = false
		for enemy: Node in get_tree().get_nodes_in_group("marauders"):
			if String((enemy as Marauder).recovered_weapon.get("uid", "")) == String(me.inventory.equipment.primary.uid):
				recovered = true
		check("выданный врагу экземпляр реплицируется", recovered)
		await until(func() -> bool: return phase >= 2)
		check("общий вынос рамы записан клиенту", String(Quests.objective("own_mark").get("id", "")) == "frame_report")
		await until(func() -> bool: return phase >= 3)
		check("подтверждение эвакуации пришло надёжным сообщением", not Raid.current._exit_receipt.is_empty())
		_result.rpc_id(1, fails)
		await get_tree().create_timer(1).timeout
		print("engraving_net_client: failures=", fails)
		get_tree().quit(1 if fails else 0)
		return
	await until(func() -> bool: return client_ready)
	var peer: int = 0
	for id: int in Raid.current.participants:
		if id != 1:
			peer = id
	var friend: Player = Raid.current.player_of(peer)
	check("постоянный владелец клиента зарегистрирован", friend != null and String(Raid.current.recovery.owners.get(peer, "")) != "")
	await until(func() -> bool: return friend != null and friend.inventory.has("engraver_frame"))
	me.global_position = site.global_position + Vector3(-.8,.1,0)
	Quests.request_site("engraver_frame")
	check("второй игрок не получает копию рамы", not me.inventory.has("engraver_frame"))
	var gun: Dictionary = friend.inventory.equipment.primary.duplicate(true)
	check("метка и выбранное место клиента дошли с комплектом", String(gun.get("uid", "")) == client_uid and String(gun.engraving.text) == "client" and String(gun.engraving.site) == "left_2")
	# Кэш гостя на хосте мог быть создан раньше последнего пакета состояния.
	friend.equipment_state()
	var updated: Dictionary = friend.inventory.equipment.duplicate(true)
	updated.primary.mag.rounds = 7
	updated.primary.dur = 61.0
	friend.inventory.equipment = updated
	check("снимок гостя читает свежий боезапас и износ хоста", int(friend.equipment_state().primary.mag.rounds) == 7 and float(friend.equipment_state().primary.dur) == 61.0)
	await until(func() -> bool: return not get_tree().get_nodes_in_group("marauders").is_empty())
	var enemy: Marauder = get_tree().get_nodes_in_group("marauders")[0] as Marauder
	enemy.recovered_weapon = gun
	await get_tree().create_timer(1).timeout
	_set_phase.rpc(1)
	await get_tree().create_timer(1).timeout
	# Груз переносится обычным инвентарём: друг умирает / отдаёт, выносит другой.
	var cargo: Dictionary = {}
	var keep: Array = friend.inventory.items.duplicate(true)
	for idx: int in range(keep.size()-1,-1,-1):
		if String(keep[idx].id) == "engraver_frame":
			cargo = keep[idx]
			keep.remove_at(idx)
	friend.inventory.items = keep
	me.inventory.add_entry(cargo)
	me.inventory.add_entry(gun)
	friend.inventory.equipment = {}
	enemy.equipment.erase("primary")
	var ext: ExtractionPoint = get_tree().get_nodes_in_group("extractions")[0] as ExtractionPoint
	Raid.current._extract(me, ext)
	check("вынос груза другим игроком засчитан", String(Quests.objective("own_mark").get("id", "")) == "frame_report")
	check("рама передана и не вернулась в рюкзак", not me.inventory.has("engraver_frame"))
	check("вынос ствола закрывает обе записи журнала", not Raid.current.recovery.journal.pending.has(client_uid) and not Raid.current.recovery.journal.lost.has(client_uid))
	_set_phase.rpc(2)
	await get_tree().create_timer(1).timeout
	Raid.current._extract(friend, ext)
	_set_phase.rpc(3)
	await until(func() -> bool: return result >= 0)
	print("engraving_net_host: failures=", fails + maxi(result, 0))
	get_tree().quit(1 if fails > 0 or result > 0 else 0)


@rpc("any_peer", "call_remote", "reliable")
func _ready_client(uid: String) -> void:
	client_uid = uid
	client_ready = true


@rpc("authority", "call_local", "reliable")
func _set_phase(value: int) -> void:
	phase = value


@rpc("any_peer", "call_remote", "reliable")
func _result(count: int) -> void:
	result = count


func check(label: String, value: bool) -> void:
	print("%s: %s" % ["PASS" if value else "FAIL", label])
	if not value:
		fails += 1


func until(condition: Callable) -> void:
	var end: int = Time.get_ticks_msec() + 60000
	while not condition.call() and Time.get_ticks_msec() < end:
		await get_tree().create_timer(.2).timeout
	if not condition.call():
		check("ожидание условия", false)
