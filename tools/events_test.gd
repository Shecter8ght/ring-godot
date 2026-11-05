extends Node
## События и фракции (RaidEvents). Две карты:
##   серый черновик 1-го этажа ТЦ Ø200 (mall_1f, SectorBuilder — магазины с данными «retail»): жильцы и сигнализация
##   в магазинах; главный рубильник и ворота на электричестве — свои (на нынешних картах их нет: были на кольце Ø250,
##   удалённом 2026-10-24); жильцы не трогают, пока не полезешь; сирена и пульт; задание по рации;
##   рейдовая карта ТЦ (mall_map): своего рубильника нет — «свет погас» не выпадает; генератора нет — авария ставит
##   его у техкомплекса, к нему можно подойти и починить; сброс груза в атриум, ЧВК приезжают, ЧВК и мародёры воюют
##   между собой (игроку не засчитывается).
## godot --path . res://tools/events_test.tscn (можно --headless)

## Площадь к югу от ТЦ на карте ТЦ: ровная земля, вдоль ±X свободно 80 м.
const OPEN := Vector2(90.0, 150.0)
## Свои ворота на электричестве (как ворота двора разгрузки на прежнем кольце).
const GATE_SWITCH := "dock_gate"

var _fails: int = 0
var _level: Node


func _ready() -> void:
	Profile.use_file("user://profile_events_test.json", true)
	Profile.ensure()
	await get_tree().process_frame
	await _floor_draft()
	await _raid_map()
	print("events_test: провалено %d" % _fails)
	get_tree().quit(_fails)


## Черновик 1-го этажа: магазины (жильцы, сигнализация), рубильник и ворота на электричестве, рация.
func _floor_draft() -> void:
	await _load("res://scenes/levels/mall_1f.tscn")
	await get_tree().create_timer(1.5).timeout
	var me := Raid.current.local_player()
	var ev := RaidEvents.current
	var residents: Array = []
	for m in get_tree().get_nodes_in_group("marauders"):
		if (m as Marauder).faction == "resident":
			residents.append(m)
	_check("жильцы в магазинах и магазины на сигнализации", residents.size() >= 2 and ev._alarms.size() == int(Balance.RAID_EVENTS.alarm_shops),
		"жильцов %d, сигнализаций %d" % [residents.size(), ev._alarms.size()])
	# остальных убираем — мешают проверкам
	for m in get_tree().get_nodes_in_group("marauders"):
		if (m as Marauder).faction != "resident":
			(m as Node).queue_free()
	await get_tree().physics_frame
	# главный рубильник: без него «свет погас» в расписание не попадает (поднять свет было бы нечем)
	_check("без главного рубильника «свет погас» не выпадает", not ev.has_breaker(), "")
	var br := MallBreaker.new()
	br.name = "MainBreaker"
	_level.add_child(br)
	br.global_position = SectorBuilder.polar(-60.0, 100.0)
	var gate := _level.get_node("Extractions/Yard") as ExtractionPoint
	gate.required_switch = GATE_SWITCH
	_check("рубильник на карте — событие возможно", ev.has_breaker(), "")
	# отключение света: огни ТЦ гаснут, ворота на электричестве не открыть и со включённым рубильником ворот
	ev.trigger("outage")
	await get_tree().process_frame
	var lit := _lit()
	Raid.current.set_switch(GATE_SWITCH, true)
	_check("свет погас — ворота на электричестве закрыты", lit.x == 0 and lit.y > 0 and Raid.current.extraction_block_reason(gate).contains("электричества"),
		"огней %d из %d, %s" % [lit.x, lit.y, Raid.current.extraction_block_reason(gate)])
	# главный рубильник: выкл → аварийный → весь свет
	br._use(1)
	br._use(1)
	await get_tree().process_frame
	lit = _lit()
	_check("рубильник поднят — свет вернулся, ворота открыты", String(RaidConditions.current.power) == "on" and lit.x > 0
		and Raid.current.extraction_block_reason(gate) == "", "огней %d, %s" % [lit.x, Raid.current.extraction_block_reason(gate)])
	# жильцы: рядом — не трогают; полез к ним — враждебны
	var r0: Marauder = residents[0] as Marauder if not residents.is_empty() else null
	if r0 != null and is_instance_valid(r0):
		for m in (r0.squad.alive() if r0.squad else [r0]):
			# забываем прошлые встречи (игрока по ходу теста таскало по уровню); враждебные сразу — тоже успокоены
			(m as Marauder).hostile_to_players = false
			(m as Marauder)._target_player = null
		me.global_position = r0.home + Vector3(float(Balance.RESIDENTS.trespass_m) + r0.home_radius + 5.0, 0.1, 0.0)
		await get_tree().create_timer(2.0).timeout
		var calm := r0.state != Marauder.State.COMBAT or r0._target_player == null
		r0.provoke()
		_check("жильцы: не трогают, пока не полез; полез — враждебны", calm and r0.hostile_to_players, "")
	# сигнализация: жильцы больше не нужны
	for m in get_tree().get_nodes_in_group("marauders"):
		(m as Node).queue_free()
	await get_tree().process_frame
	if ev._alarms.is_empty():
		_check("зашёл в магазин на сигнализации — сирена, слышно округе", false, "сигнализаций нет")
	else:
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


## Рейдовая карта ТЦ: генератор у техкомплекса, сброс, ЧВК и их бой с мародёрами.
func _raid_map() -> void:
	await _load("res://scenes/levels/mall_map.tscn")
	await get_tree().create_timer(1.5).timeout
	var me := Raid.current.local_player()
	var ev := RaidEvents.current
	for m in get_tree().get_nodes_in_group("marauders"):
		(m as Node).queue_free()
	await get_tree().physics_frame
	_check("карта ТЦ: своего главного рубильника нет — «свет погас» не выпадает", not ev.has_breaker(), "")
	# генератор: своего на карте нет — авария ставит его у техкомплекса; чинить там же
	_check("карта ТЦ: своего генератора нет", get_tree().get_first_node_in_group("mall_generator") == null, "")
	ev.trigger("generator")
	await get_tree().process_frame
	var gen := ev.generator()
	_check("авария генератора — аварийный свет, генератор у техкомплекса, чинить его", gen != null and gen.can_use() and String(RaidConditions.current.power) == "emergency",
		"%s, %s" % [String(RaidConditions.current.power), str(gen.global_position.snapped(Vector3.ONE)) if gen else "нет"])
	# к щитку можно подойти: перед ним навмеш (корпус — препятствие)
	var front := gen.to_global(Vector3(-0.85, 0.0, -1.3)) if gen else Vector3.ZERO
	var nav := NavigationServer3D.map_get_closest_point(me.get_world_3d().navigation_map, front)
	var off := Vector2(nav.x - front.x, nav.z - front.z).length()
	_check("к генератору можно подойти", gen != null and off < 0.3 and absf(nav.y - front.y) < 1.0, "до навмеша %.2f м по полу, %.2f м по высоте" % [off, nav.y - front.y])
	if gen:
		me.global_position = nav + Vector3(0, 0.1, 0)
		await get_tree().physics_frame
		gen._use(1)
		await get_tree().create_timer(float(Balance.RAID_EVENTS.repair_sec) + 0.5).timeout
		var lit := _lit()
		_check("починил генератор — свет вернулся, генератор на месте", String(RaidConditions.current.power) == "on" and lit.x > 0 and is_instance_valid(gen) and not gen.can_use(),
			"%s, огней %d" % [String(RaidConditions.current.power), lit.x])
	# сброс груза и ЧВК
	ev.trigger("drop")
	await get_tree().create_timer(5.0).timeout
	var crate := false
	for c in get_tree().get_nodes_in_group("loot_containers"):
		if (c as LootContainer).display_name == "Сброшенный груз" and not (c as LootContainer).items.is_empty() \
				and Vector2((c as Node3D).global_position.x, (c as Node3D).global_position.z).length() < 30.0:
			crate = true
	_check("сброс: груз в атриуме", crate, "")
	ev.trigger("pmc")
	await get_tree().create_timer(1.0).timeout
	var pmc: Array = []
	for m in get_tree().get_nodes_in_group("marauders"):
		if (m as Marauder).faction == "pmc":
			pmc.append(m)
	_check("ЧВК приехали группой", pmc.size() == AIPopulation.pmc_size(), str(pmc.size()))
	if pmc.is_empty():
		return
	# ЧВК против мародёра на открытой площади: друг друга видят и стреляют, игроку не засчитано
	var credited := [0]
	Raid.current.kill_credited.connect(func() -> void: credited[0] += 1)
	var mar := (preload("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	mar.name = "Duelist"
	mar.archetype = "gunner"
	mar.weapon = "rifle"
	_level.get_node("Marauders").add_child(mar)
	var p0 := _ground(OPEN)
	mar.global_position = p0 + Vector3(0, 0.1, 0)
	var foe := pmc[0] as Marauder
	foe.global_position = p0 + Vector3(14, 0.1, 0)
	mar._facing = PI * 0.5
	foe._facing = -PI * 0.5
	# игрок далеко и под землёй: ни те ни другие его не видят
	me.set_physics_process(false)
	me.global_position = Vector3(0, -80, 0)
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


## Сколько огней ТЦ горит (x) из скольких (y).
func _lit() -> Vector2i:
	var lit := 0
	var total := 0
	for l in get_tree().get_nodes_in_group("mall_lights"):
		total += 1
		if (l as Light3D).visible:
			lit += 1
	return Vector2i(lit, total)


## Точка карты по углу и радиусу (SectorBuilder.polar) — на земле: рельеф территории не на нуле.
func _ground(ar: Vector2) -> Vector3:
	var p := SectorBuilder.polar(ar.x, ar.y)
	var hit := get_viewport().get_world_3d().direct_space_state.intersect_ray(
		PhysicsRayQueryParameters3D.create(p + Vector3.UP * 60.0, p + Vector3.DOWN * 60.0, 1))
	return hit.position as Vector3 if not hit.is_empty() else p


func _load(path: String) -> void:
	if _level:
		_level.queue_free()
		await get_tree().process_frame
		await get_tree().process_frame
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	_level = load(path).instantiate()
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	while _level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	var me := Raid.current.local_player()
	me.health.hp = 1e9
	me.health.head_protected = func() -> bool: return true


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
