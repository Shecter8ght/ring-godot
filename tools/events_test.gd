extends Node
## События и фракции: жильцы и сигнализация на уровне, отключение света (ворота закрыты),
## авария генератора и починка, сброс груза, ЧВК приезжают, ЧВК и мародёры воюют между собой
## (игроку не засчитывается), жильцы не трогают, пока не полезешь, сирена, задание по рации.
## godot --path . res://tools/events_test.tscn (можно --headless)

var _fails: int = 0
var _level: Node


func _ready() -> void:
	Profile.use_file("user://profile_events_test.json", true)
	Profile.ensure()
	await get_tree().process_frame
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	_level = load("res://scenes/levels/f1_ring.tscn").instantiate()
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	while _level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	await get_tree().create_timer(1.5).timeout
	var me := Raid.current.local_player()
	me.health.hp = 1e9
	me.health.head_protected = func() -> bool: return true
	var ev := RaidEvents.current
	var residents: Array = []
	for m in get_tree().get_nodes_in_group("marauders"):
		if (m as Marauder).faction == "resident":
			residents.append(m)
	_check("жильцы в магазинах и магазины на сигнализации", residents.size() >= 2 and ev._alarms.size() == 2, "жильцов %d, сигнализаций %d" % [residents.size(), ev._alarms.size()])
	# остальных мародёров убираем — мешают проверкам
	for m in get_tree().get_nodes_in_group("marauders"):
		if (m as Marauder).faction == "marauder":
			(m as Node).queue_free()
	await get_tree().physics_frame
	# отключение света
	ev.trigger("outage")
	await get_tree().process_frame
	var lit := 0
	for l in get_tree().get_nodes_in_group("mall_lights"):
		if (l as Light3D).visible:
			lit += 1
	var dock := _level.get_node("Extractions/Dock") as ExtractionPoint
	Raid.current.set_switch("dock_gate", true)
	_check("свет погас — ворота на электричестве закрыты", lit == 0 and Raid.current.extraction_block_reason(dock).contains("электричества"), Raid.current.extraction_block_reason(dock))
	# генератор: авария → аварийный свет → починили → свет
	RaidConditions.current["power"] = "on"
	ev.trigger("generator")
	await get_tree().process_frame
	var gen := ev._generator as GeneratorPanel
	_check("авария генератора — аварийный свет, генератор дымит", gen != null and String(RaidConditions.current.power) == "emergency", "")
	me.global_position = gen.global_position + Vector3(1.0, 0.1, 0.0)
	await get_tree().physics_frame
	gen._use(1)
	await get_tree().create_timer(float(Balance.RAID_EVENTS.repair_sec) + 0.5).timeout
	lit = 0
	for l in get_tree().get_nodes_in_group("mall_lights"):
		if (l as Light3D).visible:
			lit += 1
	_check("починил генератор — свет вернулся", String(RaidConditions.current.power) == "on" and lit > 0, "огней %d" % lit)
	# сброс груза и ЧВК
	ev.trigger("drop")
	await get_tree().create_timer(5.0).timeout
	var crate := false
	for c in get_tree().get_nodes_in_group("loot_containers"):
		if (c as LootContainer).display_name == "Сброшенный груз" and not (c as LootContainer).items.is_empty():
			crate = true
	_check("сброс: груз в атриуме", crate, "")
	ev.trigger("pmc")
	await get_tree().create_timer(1.0).timeout
	var pmc: Array = []
	for m in get_tree().get_nodes_in_group("marauders"):
		if (m as Marauder).faction == "pmc":
			pmc.append(m)
	_check("ЧВК приехали группой", pmc.size() == Balance.PMC_SQUAD, str(pmc.size()))
	# ЧВК против мародёра: друг друга видят и стреляют, игроку не засчитано
	var credited := [0]
	Raid.current.kill_credited.connect(func() -> void: credited[0] += 1)
	var mar := (preload("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	mar.name = "Duelist"
	mar.archetype = "gunner"
	mar.weapon = "rifle"
	_level.get_node("Marauders").add_child(mar)
	var p0 := SectorBuilder.polar(-100.0, 150.0)
	mar.global_position = p0 + Vector3(0, 0.1, 0)
	var foe := pmc[0] as Marauder
	foe.global_position = p0 + Vector3(14, 0.1, 0)
	mar._facing = PI * 0.5
	foe._facing = -PI * 0.5
	me.global_position = SectorBuilder.polar(-160.0, 72.0) + Vector3(0, 0.1, 0)
	var hurt := false
	for i in range(40):
		await get_tree().create_timer(0.25).timeout
		if not is_instance_valid(mar) or not is_instance_valid(foe):
			hurt = true
			break
		if (mar.get_node("Health") as Health).hp < (mar.get_node("Health") as Health).max_hp or (foe.get_node("Health") as Health).hp < (foe.get_node("Health") as Health).max_hp:
			hurt = true
			break
	_check("ЧВК и мародёр воюют между собой", hurt, "")
	await get_tree().create_timer(4.0).timeout
	_check("убийства ИИ — не игроку", credited[0] == 0, str(credited[0]))
	# жильцы: рядом — не трогают; полез к ним — враждебны
	var r0 := residents[0] as Marauder
	if is_instance_valid(r0):
		r0.hostile_to_players = false
		for m in (r0.squad.alive() if r0.squad else [r0]):
			# забываем прошлые встречи (игрока по ходу теста таскало по уровню)
			(m as Marauder).hostile_to_players = false
			(m as Marauder)._target_player = null
		me.global_position = r0.home + Vector3(float(Balance.RESIDENTS.trespass_m) + r0.home_radius + 5.0, 0.1, 0.0)
		await get_tree().create_timer(2.0).timeout
		var calm := r0.state != Marauder.State.COMBAT or r0._target_player == null
		r0.provoke()
		_check("жильцы: не трогают, пока не полез; полез — враждебны", calm and r0.hostile_to_players, "")
	# сигнализация
	var az := ev._alarms[0] as AlarmZone
	var heard := [false]
	NoiseBus.noise.connect(func(_p: Vector3, _r: float, k: String) -> void:
		if k == "alarm":
			heard[0] = true)
	me.global_position = az.global_position + Vector3(0, 0.1, 0)
	await get_tree().create_timer(1.0).timeout
	_check("зашёл в магазин на сигнализации — сирена, слышно округе", az.triggered and heard[0], "")
	# задание по рации
	ev._radio = {"id": "laptop", "at": 0.0, "shown": false, "reward": 54000}
	for i in range(3):
		await get_tree().process_frame
	me.inventory.add("laptop", 1)
	var m0 := Profile.money
	ev.on_local_extracted(me)
	_check("рация: вынес вещь — Михалыч заплатил", Profile.money == m0 + 54000, "+%d" % (Profile.money - m0))
	print("events_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
