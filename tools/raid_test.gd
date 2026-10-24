extends Node
## Прогон цикла рейда без рук на f1_ring: двор без питания закрыт → рубильник → отсчёт идёт;
## серверная заперта → ключ из ЦПУ → открывается; съезд паркинга без карты закрыт → карта →
## эвакуация → итог рейда. Печатает проверки, сохраняет docs/screens/raid_*.png.
## godot --path . res://tools/raid_test.tscn

var _player: Player
var _raid: Raid
var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var inst: Node = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	for i in range(30):
		await get_tree().physics_frame
	_player = get_tree().get_first_node_in_group("players") as Player
	_raid = Raid.current
	_player.health.hp = 1e9
	# мародёры не мешают проверке (появляются после навмеша — дождаться и убрать)
	while inst.get_node("Marauders").get_child_count() == 0:
		await get_tree().physics_frame
	for m in get_tree().get_nodes_in_group("marauders"):
		(m as Node).queue_free()
	var dock := inst.get_node("Extractions/Dock") as ExtractionPoint
	var garage := inst.get_node("Extractions/GarageExit") as ExtractionPoint

	# 1. двор без питания
	await _teleport(dock.global_position)
	await _wait(1.5)
	_check("двор без питания закрыт", not _raid.channel.has(1) and _raid.extraction_block_reason(dock) != "", _raid.extraction_block_reason(dock))
	_save("raid_dock_locked")

	# 2. рубильник
	var sw := inst.get_node("Interactables/DockGateSwitch") as PowerSwitch
	await _teleport(sw.global_position + sw.global_basis.z * -1.0)
	await _press("interact")
	_check("рубильник включён", bool(_raid.switches.get("dock_gate", false)), str(_raid.switches))
	await _teleport(dock.global_position)
	await _wait(1.2)
	var ch: Array = _raid.channel.get(1, [])
	_check("у ворот идёт отсчёт", ch.size() == 2 and float(ch[1]) > 0.5, str(ch))
	_save("raid_dock_channel")
	await _teleport(dock.global_position + Vector3(20, 0, 0))
	await _wait(0.3)
	_check("вышел из зоны — сброс", not _raid.channel.has(1), "")

	# 3. серверная заперта, ключ из ЦПУ открывает
	var door: Door = null
	for d in inst.find_children("*", "Door", true, false):
		if (d as Door).required_key == "key_server":
			door = d
			break
	_check("у серверной запертая дверь", door != null, "")
	if door:
		var front := door.global_position + door.global_basis.x * (door.width * 0.5) + door.global_basis.z * 1.0
		await _teleport(front)
		await _press("interact")
		await _wait(0.4)
		_check("без ключа не открывается", not door.is_open, "")
		var key := inst.get_node("Interactables/KeyServer") as KeyPickup
		await _teleport(key.global_position + Vector3(0.6, 0, 0))
		await _press("interact")
		_check("ключ от серверной в рюкзаке", _player.inventory.has("key_server"), str(_player.inventory.items))
		await _teleport(front)
		await _press("interact")
		await _wait(0.4)
		_check("с ключом открывается", door.is_open, "")

	# 4. съезд паркинга: без карты закрыт, с картой — эвакуация
	await _teleport(garage.global_position)
	await _wait(1.0)
	_check("съезд без карты закрыт", not _raid.channel.has(1), _raid.extraction_block_reason(garage))
	var card := inst.get_node("Interactables/KeycardSecurity") as KeyPickup
	await _teleport(card.global_position + Vector3(0.6, 0, 0))
	await _press("interact")
	_check("карта-ключ в рюкзаке", _player.inventory.has("keycard_security"), "")
	# лут: сейф ювелирного (дверь сейфовой заперта — телепорт внутрь), обыск и «взять всё»
	var safe := inst.get_node("Interactables/JewelrySafe") as LootContainer
	await _teleport(safe.global_position + safe.global_basis.z * -1.2)
	await _press("interact")
	await _wait(safe.search_s + 0.4)
	_check("сейф обыскан — окно открыто", _raid.ui.is_looting() and safe.rolled and not safe.items.is_empty(), str(safe.items))
	var before := _player.inventory.value()
	_raid.request_take_all(safe)
	await _frames(3)
	_check("лут из сейфа в рюкзаке", _player.inventory.value() > before and safe.items.is_empty(), "%d ₽" % _player.inventory.value())
	_save("raid_loot")
	# лечение: ранить и дать бинт
	_player.inventory.add("bandage", 1)
	_player.health.hp = 50.0
	_raid.ui.close_all()
	await _press("use_med")
	# H открывает меню «чем лечиться» — 1: бинт
	await _press("weapon_1")
	await _wait(float(ItemDb.item("bandage").use.time) + 0.3)
	_check("бинт лечит", _player.health.hp > 50.0 and not _player.inventory.has("bandage"), "hp=%d" % int(_player.health.hp))
	_player.health.hp = 1e9
	await _teleport(garage.global_position)
	await _wait(garage.channel_s + 1.0)
	_check("эвакуирован", _raid.is_extracted(1), str(_raid.extracted))
	_check("в итоге — ценность вынесенного", int(_raid.loot_value.get(1, 0)) > 0, str(_raid.loot_value))
	_check("рейд окончен", _raid.over, "")
	_check("игрок ушёл из мира", not _player.visible and not _player.is_in_group("players"), "")
	await _frames(5)
	_save("raid_over")
	print("raid_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _teleport(p: Vector3) -> void:
	_player.global_position = p + Vector3(0, 0.1, 0)
	_player.velocity = Vector3.ZERO
	# зоны (двери, выходы) замечают тело только на физическом шаге
	for i in range(3):
		await get_tree().physics_frame
	await _frames(2)


func _press(action: String) -> void:
	Input.action_press(action)
	await get_tree().process_frame
	await get_tree().process_frame
	Input.action_release(action)
	await _frames(3)


func _wait(sec: float) -> void:
	await get_tree().create_timer(sec).timeout


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])


func _save(n: String) -> void:
	if DisplayServer.get_name() != "headless":
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))
