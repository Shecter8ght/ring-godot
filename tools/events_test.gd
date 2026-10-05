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
	# главный рубильник в электрощитовой — поднять, свет вернулся
	var br := _level.find_child("MainBreaker", true, false) as MallBreaker
	br._use(1)
	br._use(1)
	await get_tree().process_frame
	lit = 0
	for l in get_tree().get_nodes_in_group("mall_lights"):
		if (l as Light3D).visible:
			lit += 1
	_check("рубильник в щитовой поднят — свет вернулся", String(RaidConditions.current.power) == "on" and lit > 0, "огней %d" % lit)
	# генератор ТЦ: стоит в мастерской и работает; авария → аварийный свет, дымит → починили → свет
	var gen := get_tree().get_first_node_in_group("mall_generator") as MallGenerator
	var gp := gen.global_position if gen else Vector3.ZERO
	var ga := rad_to_deg(atan2(gp.z, gp.x))
	var gr := Vector2(gp.x, gp.z).length()
	_check("генератор ТЦ — в мастерской, работает", gen != null and not gen.can_use() and ga > -162.5 and ga < -152.5 and gr > 109.0 and gr < 121.0, "a %.1f r %.1f" % [ga, gr])
	# к щитку можно подойти: перед ним навмеш (пропсов нет, корпус — препятствие)
	var front := gen.to_global(Vector3(-0.85, 0.0, -1.3)) if gen else Vector3.ZERO
	var nav := NavigationServer3D.map_get_closest_point(me.get_world_3d().navigation_map, front)
	var off := Vector2(nav.x - front.x, nav.z - front.z).length()
	_check("к генератору можно подойти", off < 0.3, "до навмеша %.2f м по полу" % off)
	ev.trigger("generator")
	await get_tree().process_frame
	_check("авария генератора — аварийный свет, чинить тот же генератор", ev.generator() == gen and gen.can_use() and String(RaidConditions.current.power) == "emergency", String(RaidConditions.current.power))
	me.global_position = front + Vector3(0, 0.1, 0)
	await get_tree().physics_frame
	gen._use(1)
	await get_tree().create_timer(float(Balance.RAID_EVENTS.repair_sec) + 0.5).timeout
	lit = 0
	for l in get_tree().get_nodes_in_group("mall_lights"):
		if (l as Light3D).visible:
			lit += 1
	_check("починил генератор — свет вернулся, генератор на месте", String(RaidConditions.current.power) == "on" and lit > 0 and is_instance_valid(gen) and not gen.can_use(), "огней %d" % lit)
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
	# Прежний жилец мог погибнуть от ЧВК в предыдущей проверке. Новый мирный
	# отряд вдали от места перестрелки проверяет реакцию живых, а не ragdoll.
	for actor: Node in get_tree().get_nodes_in_group("marauders"):
		actor.queue_free()
	await get_tree().process_frame
	await get_tree().process_frame
	var resident_home: Vector3 = SectorBuilder.polar(-160.0, 72.0)
	me.global_position = resident_home + Vector3(20.0, 0.1, 0)
	ev._spawn_residents(resident_home, 4.0, false)
	var r0: Marauder = get_tree().get_nodes_in_group("marauders")[0] as Marauder
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
	# пульт: подойти, F — через alarm_off_sec сирена молчит, шума больше нет
	var panel := az.get_node("Panel") as AlarmPanel
	me.global_position = panel.global_position + Vector3(0.6, 0.1, 0.0)
	await get_tree().physics_frame
	var can := panel.can_use()
	panel._use(1)
	await get_tree().create_timer(float(Balance.RAID_EVENTS.alarm_off_sec) + 0.5).timeout
	heard[0] = false
	await get_tree().create_timer(6.0).timeout
	_check("пульт: отключил сигнализацию — сирена молчит, шума нет", can and not az.sounding() and not heard[0] and not panel.can_use(), "")
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
