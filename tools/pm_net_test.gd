extends Node3D
## Сквозной ПМ по настоящему ENet: два отдельных процесса, клиент просит хост изменить вещи.
## tools/godot.cmd --headless res://tools/pm_net_test.tscn -- host
## tools/godot.cmd --headless res://tools/pm_net_test.tscn -- client  (через несколько секунд)
## Порт тот же, что у игры; не запускать одновременно с coop_raid_test.
## -- compile загружает скрипт с автозагрузками, не открывая сетевой порт.

const PM_ID: String = "wpn_hg_01"
const SUP_ID: String = "muzzle_supp_pm_01"
const CASES: Array[String] = ["reload_partial", "reload_empty", "suppressor_install", "suppressor_remove", "reload_cancel", "suppressor_cancel", "injury_cancel", "last_shot",
	"hand_mag_out", "hand_mag_in", "hand_mag_swap"]

var _role: String = ""
var _client_id: int = 0
var _ready_peer: bool = false
var _remote_ready: bool = false
var _finished: bool = false
var _fails: int = 0
var _checks: int = 0
var _case: String = ""
var _case_rev: int = 0
var _done_case: String = ""
var _seen: Dictionary = {}
var _players: Dictionary = {}
var _raid: Raid
var _incoming: Array[Dictionary] = []
var _abort: bool = false


func _enter_tree() -> void:
	set_meta(Net.SCENE_META, "raid")


func _ready() -> void:
	Engine.max_fps = 120
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if "compile" in args:
		print("pm_net_test: компиляция с автозагрузками завершена")
		await _cleanup()
		get_tree().quit(0)
		return
	if args.is_empty() or not String(args[0]) in ["host", "client"]:
		push_error("pm_net_test: передай роль host или client после --")
		get_tree().quit(1)
		return
	_role = String(args[0])
	Profile.use_file("user://profile_pm_net_%s.json" % _role, true)
	Profile.ensure()
	Profile.pending_raid = false
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	_build_floor()
	Net.enter_scene("raid")
	if _role == "host":
		await _host()
	else:
		await _client()
	print("pm_net_test[%s]: проверок %d, провалено %d" % [_role, _checks, _fails])
	await _cleanup()
	# При выходе движок закрывает ENet; сначала close(), затем get_unique_id() уже недопустим.
	get_tree().quit(1 if _fails > 0 else 0)


## Сначала освобождаем реальные Player и их риги, затем завершаем дерево без висящих ресурсов.
func _cleanup() -> void:
	set_process(false)
	# Отключаем приём ENet до удаления Sync; id читается перед close(), пока пир активен.
	if Net.is_networked():
		var peer: MultiplayerPeer = multiplayer.multiplayer_peer
		Net._keep_own_scene(OfflineMultiplayerPeer.new())
		Net._active = false
		peer.close()
	# Dummy-аудиодрайвер удерживает loop playback на выходе: останавливаем звук стенда явно.
	for sound: Node in Audio.get_children():
		if sound is AudioStreamPlayer:
			(sound as AudioStreamPlayer).stop()
			(sound as AudioStreamPlayer).stream = null
		elif sound is AudioStreamPlayer3D:
			(sound as AudioStreamPlayer3D).stop()
			(sound as AudioStreamPlayer3D).stream = null
	for peer: int in _players:
		var person: Player = _players[peer] as Player
		person.cancel_weapon_action()
		person.set_process(false)
		person.set_physics_process(false)
	_players.clear()
	_raid = null
	for child: Node in get_children():
		child.queue_free()
	for frame: int in range(3):
		await get_tree().process_frame
	await get_tree().create_timer(0.12).timeout


func _build_floor() -> void:
	var body: StaticBody3D = StaticBody3D.new()
	body.name = "Floor"
	var collision: CollisionShape3D = CollisionShape3D.new()
	var shape: BoxShape3D = BoxShape3D.new()
	shape.size = Vector3(30.0, 0.3, 30.0)
	collision.shape = shape
	collision.position.y = -0.15
	body.add_child(collision)
	add_child(body)


func _host() -> void:
	var error: String = Net.host("ПМ тест хост")
	_check("сервер ENet поднят", error == "", error)
	if error != "":
		return
	if not await _wait(func() -> bool: return not multiplayer.get_peers().is_empty(), 40.0):
		_check("клиент подключился за ограниченное время", false)
		return
	_client_id = int(multiplayer.get_peers()[0])
	_spawn.rpc(_client_id)
	if not await _wait(func() -> bool: return _remote_ready, 20.0):
		_check("одинаковые пути Player готовы у клиента", false)
		return
	await get_tree().create_timer(0.5).timeout
	for case_name: String in CASES:
		_case = case_name
		_seen.clear()
		_done_case = ""
		_seed_case(case_name)
		var person: Player = _players[_client_id] as Player
		var before: String = JSON.stringify([person.inventory.equipment, person.inventory.items, person.inventory.buffer])
		var total_before: int = _total_rounds(person.inventory)
		var injury: bool = case_name == "injury_cancel"
		_case_rev = int((person.inventory.equipment.secondary as Dictionary).rev)
		_request_case.rpc_id(_client_id, case_name, _case_rev)
		if injury:
			if await _wait(func() -> bool: return bool(_seen.get("action_reload", false)), 8.0):
				await get_tree().create_timer(0.35).timeout
				person.health.take_damage(10000.0, Vector3(0.0, 1.0, 5.0), "thorax")
				_check("тяжёлое ранение считает хост", person.health.downed)
		if not await _wait(func() -> bool: return _done_case == case_name, 20.0):
			_check(case_name + ": клиент закончил за ограниченное время", false)
			_abort = true
			break
		await get_tree().create_timer(0.3).timeout
		var equipped: Dictionary = person.inventory.equipment.secondary
		var suppressed: bool = bool(WeaponStats.compute(equipped).suppressed)
		var total_after: int = _total_rounds(person.inventory)
		var rig: WeaponRig = person._weapon_rig
		_check(case_name + ": суммарный боезапас на хосте сохранён", total_after == total_before - (1 if case_name == "last_shot" else 0), "%d → %d" % [total_before, total_after])
		_check(case_name + ": глушитель не потерян и не размножен", _total_suppressors(person.inventory) == 1)
		match case_name:
			"reload_partial", "reload_empty":
				_check(case_name + ": хост подтвердил 8+1 / 8", Gear.total_rounds(equipped) == (9 if case_name == "reload_partial" else 8))
				_check(case_name + ": чужой WeaponRig показал магазин и цель кисти", bool(_seen.get("action_reload", false)) and bool(_seen.get("mag_moved", false)) and bool(_seen.get("hand_target", false)))
				_check(case_name + ": затвор после досыла закрыт", rig != null and not rig.is_slide_locked())
				_check(case_name + ": событие pistol_reload реплицировано", bool(_seen.get("pistol_reload", false)))
			"suppressor_install", "suppressor_remove":
				_check(case_name + ": хост подтвердил состояние глушителя", suppressed == (case_name == "suppressor_install"))
				_check(case_name + ": чужой риг показал накручивание", bool(_seen.get("action_suppressor", false)) and bool(_seen.get("hand_target", false)))
				_check(case_name + ": видимость чужого глушителя совпадает", rig != null and rig.part("Suppressor").visible == suppressed,
					"видно %s, риг считает %s, действие «%s», обвес у копии %s" % [str(rig.part("Suppressor").visible), str(rig._suppressed), rig.action, str(person.weapon_mods)] if rig else "рига нет")
			"reload_cancel", "suppressor_cancel", "injury_cancel":
				_check(case_name + ": прерывание не меняло вещи хоста", before == JSON.stringify([person.inventory.equipment, person.inventory.items, person.inventory.buffer]))
				_check(case_name + ": отмена дошла до чужого рига", rig == null or (rig.action == "" and not rig.is_busy()))
			"hand_mag_out", "hand_mag_in", "hand_mag_swap":
				# обойма из окна рюкзака: предметы переносит хост по окончании движения рук клиента
				var spare: Array = []
				for raw_item: Dictionary in person.inventory.items:
					if raw_item.has("rounds"):
						spare.append(int(raw_item.rounds))
				spare.sort()
				var standing: Dictionary = equipped.get("mag", {})
				if case_name == "hand_mag_out":
					_check("вынуть: у хоста шахта пуста, магазин с остатком в рюкзаке, патрон в стволе", String(standing.get("id", "")) == "" and int(equipped.chamber) == 1 and spare == [3, 8, 8], str(spare))
				elif case_name == "hand_mag_in":
					_check("вставить: у хоста магазин на 8 в оружии, патрон в стволе тот же", String(standing.get("id", "")) == "mag_918_8" and int(standing.rounds) == 8 and int(equipped.chamber) == 1 and spare == [8], str(spare))
				else:
					_check("сменить: у хоста выбранный магазин в оружии, прежний с остатком в рюкзаке", int(standing.get("rounds", -1)) == 8 and int(equipped.chamber) == 1 and spare == [3, 8], str(spare))
				_check(case_name + ": чужой WeaponRig показал движение магазина и руки", bool(_seen.get("action_reload", false)) and bool(_seen.get("mag_moved", false)) and bool(_seen.get("hand_target", false)), str(_seen.keys()))
				_check(case_name + ": у чужого рига действие закончено", rig == null or not rig.is_busy())
			"last_shot":
				_check("последний выстрел: расход подтверждён хостом", Gear.total_rounds(equipped) == 0)
				_check("хост считает износ оружия", is_equal_approx(float(equipped.dur), 100.0 - float(WeaponDb.weapon(PM_ID).stats.wear)))
				_check("хост считает отдельный износ глушителя", is_equal_approx(float(equipped.mods.muzzle.dur), 20.0 - float(Balance.CONDITION.shot_wear.SUPPRESSOR)))
				_check("последний выстрел: чужой затвор на задержке", rig != null and rig.is_slide_locked() and person.weapon_rounds == 0)
	_case = ""
	_finish.rpc_id(_client_id, _abort)
	# Клиент успевает напечатать свой результат до закрытия ENet сервером.
	await get_tree().create_timer(2.0).timeout


func _client() -> void:
	var error: String = Net.join("127.0.0.1", "ПМ тест клиент")
	_check("клиент ENet подключается", error == "", error)
	if error != "":
		return
	if not await _wait(func() -> bool: return multiplayer.multiplayer_peer.get_connection_status() == MultiplayerPeer.CONNECTION_CONNECTED and _ready_peer, 40.0):
		_check("подключение и сцена готовы за ограниченное время", false)
		return
	while not _finished:
		if not _incoming.is_empty():
			var incoming: Dictionary = _incoming.pop_front()
			await _run_case(String(incoming.name), int(incoming.rev))
		else:
			if not await _wait(func() -> bool: return not _incoming.is_empty() or _finished, 30.0):
				_check("следующий сценарий хоста получен за ограниченное время", false)
				break


@rpc("authority", "call_local", "reliable")
func _spawn(client_peer: int) -> void:
	_client_id = client_peer
	Net.enter_scene("raid")
	_raid = Raid.new()
	_raid.name = "Raid"
	add_child(_raid)
	_raid.set_process(false)
	_raid.set_physics_process(false)
	var parent: Node3D = Node3D.new()
	parent.name = "Players"
	add_child(parent)
	for peer: int in [1, client_peer]:
		var person: Player = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
		person.name = "Player_%d" % peer
		person.peer_id = peer
		person.set_multiplayer_authority(peer, true)
		person.get_node("Health").set_multiplayer_authority(1, true)
		person.loadout_mode = true
		person.position = Vector3(-4.0 if peer == 1 else 4.0, 0.05, 0.0)
		parent.add_child(person)
		_players[peer] = person
		person.inventory.set_multiplayer_authority(1)
		_raid.register(peer, "PM_%d" % peer)
		if multiplayer.is_server():
			person.inventory.equipment = {"secondary": _entry(3, 1, 1)}
			person.inventory.loadout_ready = true
		_check("Player/Health/Inventory: авторитеты раздельны", person.get_multiplayer_authority() == peer and person.health.get_multiplayer_authority() == 1 and person.inventory.get_multiplayer_authority() == 1)
	_ready_peer = true
	if not multiplayer.is_server():
		_client_ready.rpc_id(1)


@rpc("any_peer", "call_remote", "reliable")
func _client_ready() -> void:
	if multiplayer.is_server() and multiplayer.get_remote_sender_id() == _client_id:
		_remote_ready = true


func _seed_case(case_name: String) -> void:
	var person: Player = _players[_client_id] as Player
	person.cancel_weapon_action()
	person.health.alive = true
	person.health.downed = false
	person.health.hp = person.health.max_hp
	person.health.bleed_t = 0.0
	person.health.invulnerable = false
	var previous: Dictionary = person.inventory.equipment.get("secondary", {}) as Dictionary
	var entry: Dictionary = _entry(0 if case_name in ["reload_empty", "last_shot"] else 3, 0 if case_name == "reload_empty" else 1, int(previous.get("rev", 0)) + 1)
	if case_name in ["suppressor_remove", "last_shot"]:
		entry.mods = {"muzzle": {"id": SUP_ID, "dur": 20.0}}
	if case_name == "hand_mag_in":
		entry.mag = {"id": "", "ammo": "ammo_918_pst", "rounds": 0}
	var items: Array = []
	ItemDb.add_to(items, WeaponDb.make_mag("mag_918_8", "ammo_918_pst", 8), Balance.BACKPACK_GRID)
	ItemDb.add_to(items, WeaponDb.make_mag("mag_918_8", "ammo_918_pst", 8), Balance.BACKPACK_GRID)
	if case_name not in ["suppressor_remove", "last_shot"]:
		ItemDb.add_to(items, ItemDb.make(SUP_ID, 1), Balance.BACKPACK_GRID)
	person.inventory.equipment = {"secondary": entry}
	person.inventory.items = items
	person.inventory.buffer = []
	person.inventory.loadout_ready = true


@rpc("authority", "call_remote", "reliable")
func _request_case(case_name: String, revision: int) -> void:
	_incoming.append({"name": case_name, "rev": revision})


func _run_case(case_name: String, revision: int) -> void:
	var person: Player = _players[_client_id] as Player
	if not await _wait(func() -> bool: return int((person.inventory.equipment.get("secondary", {}) as Dictionary).get("rev", -1)) == revision and not person.health.downed, 8.0):
		_check(case_name + ": хостовая запись дошла до клиента", false)
		_case_done.rpc_id(1, case_name)
		return
	person.cancel_weapon_action()
	person._ws.clear()
	person._pm_entries.clear()
	person.weapon_slot = ""
	person._switch("secondary", false)
	person._update_hand()
	_check(case_name + ": реальный ПМ в руке клиента", person._weapon_rig != null and person.weapon_id == PM_ID)
	# Сначала реплицируется выбранное оружие, затем начинается проверяемое действие.
	await get_tree().create_timer(0.35).timeout
	var total: int = _total_rounds(person.inventory)
	var snapshot: String = JSON.stringify([person.inventory.equipment, person.inventory.items])
	match case_name:
		"reload_partial", "reload_empty":
			if case_name == "reload_empty":
				_check("пустой ПМ до перезарядки на задержке", person._weapon_rig != null and person._weapon_rig.is_slide_locked())
			person._start_reload(person.spec())
			_check(case_name + ": запущено штатное действие", not person._pm_action.is_empty() and String(person._pm_action.kind) == "reload")
			var began: int = Time.get_ticks_msec()
			if not await _wait(func() -> bool: return person._pm_action.is_empty() and person.reload_timer <= 0.0, 10.0):
				_check(case_name + ": ответ хоста получен", false)
			_check(case_name + ": клиент получил 8+1 / 8", person.ammo == (9 if case_name == "reload_partial" else 8))
			print("pm_net_test: ", case_name, " заняла ", float(Time.get_ticks_msec() - began) / 1000.0, " с")
		"suppressor_install", "suppressor_remove":
			_check(case_name + ": штатное действие запускается", person.toggle_suppressor())
			if not await _wait(func() -> bool: return person._pm_action.is_empty(), 10.0):
				_check(case_name + ": ответ хоста получен", false)
			_check(case_name + ": характеристики пересчитаны", bool(person.spec().suppressed) == (case_name == "suppressor_install"))
		"reload_cancel", "suppressor_cancel":
			if case_name == "reload_cancel":
				person._start_reload(person.spec())
			else:
				_check("прерываемая установка запустилась", person.toggle_suppressor())
			await get_tree().create_timer(0.7).timeout
			# Смена оружия вызывает настоящий cancel_weapon_action и отправляет его наблюдателям.
			person._switch("primary", false)
			await get_tree().create_timer(0.3).timeout
			_check(case_name + ": смена оружия прервала действие", person._pm_action.is_empty() and person.reload_timer <= 0.0)
			_check(case_name + ": копия вещей клиента цела", snapshot == JSON.stringify([person.inventory.equipment, person.inventory.items]))
		"hand_mag_out", "hand_mag_in", "hand_mag_swap":
			# как из окна рюкзака: «Вынуть обойму» / магазин брошен на оружие в руках
			person.weapon_mag = WeaponMods.mag_state(person.weapon_entry())
			var why: String = person.hand_mag_eject() if case_name == "hand_mag_out" else person.hand_mag_insert("backpack", 0)
			_check(case_name + ": движение рук начато", why == "" and String(person._pm_action.get("kind", "")) == ("mag_out" if case_name == "hand_mag_out" else "mag_in"), why)
			await get_tree().create_timer(0.3).timeout
			_check(case_name + ": посреди движения вещи клиента на месте", snapshot == JSON.stringify([person.inventory.equipment, person.inventory.items]))
			if not await _wait(func() -> bool: return person._pm_action.is_empty(), 10.0):
				_check(case_name + ": ответ хоста получен", false)
			await get_tree().create_timer(0.3).timeout
			var now: Dictionary = person.weapon_entry()
			var now_mag: Dictionary = now.get("mag", {})
			if case_name == "hand_mag_out":
				_check("вынуть: у клиента шахта пуста, в оружии один патрон", String(now_mag.get("id", "")) == "" and person.ammo == 1, "в оружии %d" % person.ammo)
			else:
				_check(case_name + ": у клиента в оружии магазин на 8 и патрон в стволе", String(now_mag.get("id", "")) == "mag_918_8" and person.ammo == 9, "в оружии %d" % person.ammo)
		"injury_cancel":
			person._start_reload(person.spec())
			if not await _wait(func() -> bool: return person.health.downed and person._pm_action.is_empty(), 8.0):
				_check("ранение с хоста прервало клиентское действие", false)
			else:
				_check("ранение с хоста прервало клиентское действие", true)
		"last_shot":
			await get_tree().physics_frame
			person.cursor_ground = Vector3(4.0, 0.0, 10.0)
			person._fire(person.spec())
			person.flush_weapon_state()
			await get_tree().create_timer(0.5).timeout
			_check("последний выстрел у клиента оставил затвор на задержке", person.ammo == 0 and person._weapon_rig != null and person._weapon_rig.is_slide_locked())
			_check("износ оружия совпал с подтверждением хоста", is_equal_approx(float(person.inventory.equipment.secondary.dur), float(person.weapon_entry().dur)))
			_check("износ глушителя дошёл обратно до клиента", is_equal_approx(float(person.inventory.equipment.secondary.mods.muzzle.dur), 20.0 - float(Balance.CONDITION.shot_wear.SUPPRESSOR)))
	await get_tree().create_timer(0.25).timeout
	_check(case_name + ": боезапас копии клиента сохранён", _total_rounds(person.inventory) == total - (1 if case_name == "last_shot" else 0))
	_case_done.rpc_id(1, case_name)


@rpc("any_peer", "call_remote", "reliable")
func _case_done(case_name: String) -> void:
	if multiplayer.is_server() and multiplayer.get_remote_sender_id() == _client_id:
		_done_case = case_name


@rpc("authority", "call_remote", "reliable")
func _finish(aborted: bool) -> void:
	_finished = true
	if aborted:
		_check("хост завершил все сценарии", false)


func _process(_delta: float) -> void:
	for peer: int in _players:
		var person: Player = _players[peer] as Player
		person._update_hand()
	if _role != "host" or _case == "" or not _players.has(_client_id):
		return
	var person: Player = _players[_client_id] as Player
	var rig: WeaponRig = person._weapon_rig
	if rig == null:
		return
	if not _seen.has("mag_rest"):
		_seen["mag_rest"] = rig.part("Magazine").position
	if rig.action != "":
		_seen["action_" + rig.action] = true
	if rig.part("Magazine").position.distance_to(_seen["mag_rest"] as Vector3) > 0.015:
		_seen["mag_moved"] = true
	if rig.get_hand_weight() > 0.2:
		_seen["hand_target"] = true
	if person.animation_event == "pistol_reload":
		_seen["pistol_reload"] = true


static func _entry(rounds: int, chamber: int, revision: int) -> Dictionary:
	return {"id": PM_ID, "n": 1, "dur": 100.0, "rev": revision, "mods": {}, "sight": "primary", "mag": {"id": "mag_918_8", "ammo": "ammo_918_pst", "rounds": rounds}, "chamber": chamber, "chamber_ammo": "ammo_918_pst" if chamber > 0 else ""}


static func _total_rounds(inventory: Inventory) -> int:
	var total: int = Gear.total_rounds(inventory.equipment.get("secondary", {}) as Dictionary)
	for raw: Dictionary in inventory.items + inventory.buffer:
		if raw.has("rounds"):
			total += int(raw.rounds)
		elif WeaponDb.ammo_fits(PM_ID, String(raw.id)):
			total += int(raw.n)
	return total


static func _total_suppressors(inventory: Inventory) -> int:
	var entry: Dictionary = inventory.equipment.get("secondary", {}) as Dictionary
	var total: int = 1 if WeaponDb.mod_id((entry.get("mods", {}) as Dictionary).get("muzzle", {})) == SUP_ID else 0
	for raw: Dictionary in inventory.items + inventory.buffer:
		if String(raw.id) == SUP_ID:
			total += int(raw.n)
	return total


func _wait(condition: Callable, timeout: float) -> bool:
	var start: int = Time.get_ticks_msec()
	while not bool(condition.call()) and float(Time.get_ticks_msec() - start) / 1000.0 < timeout:
		await get_tree().process_frame
	return bool(condition.call())


func _check(label: String, passed: bool, detail: String = "") -> void:
	_checks += 1
	if not passed:
		_fails += 1
	print("  [%s][%s] %s %s" % ["ok" if passed else "FAIL", _role, label, detail])
