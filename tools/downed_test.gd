extends Node
## Тяжёлое ранение: в корпус — лёг (не умер), лежащего добивают за 1–3 попадания, в голову без
## шлема и граната под ногами — сразу смерть, третье ранение — смерть, кровотечение убивает;
## поднять себя аптечкой, бинт продлевает; напарник поднимает (аптечка) и тащит, дотащил до
## эвакуации — уходят оба; мародёр лёг — товарищ спасает; лежащего игрока мародёр добивает
## только в тишине. Печатает [ok]/[FAIL] и итог. godot --path . res://tools/downed_test.tscn (--headless)

const TEST_PROFILE := "user://profile_downed_test.json"

var _fails: int = 0
var _level: Node


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	Profile.use_file(TEST_PROFILE, true)
	await get_tree().process_frame
	_level = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	while _level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in _level.get_node("Marauders").get_children():
		m.queue_free()
	await get_tree().physics_frame
	var me := get_tree().get_first_node_in_group("players") as Player
	await _player_rules(me)
	await _mate_rules(me)
	await _marauder_rules()
	await _finish_rule()
	print("downed_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _fresh(h: Health) -> void:
	h.alive = true
	h.downed = false
	h.downs = 0
	h.hp = h.max_hp


func _player_rules(me: Player) -> void:
	var h := me.health
	me.inventory.equipment = {}
	# в корпус — лёг
	h.take_damage(150.0, Vector3.ZERO, "body")
	_check("в корпус насмерть — лёг раненым", h.alive and h.downed and is_equal_approx(h.down_hp, Balance.DOWN_HP), "hp %.0f, запас %.0f" % [h.hp, h.down_hp])
	# лежащего добивают: 11 (автомат мародёра) — 3 попадания
	h.take_damage(11.0, Vector3.ZERO, "body")
	h.take_damage(11.0, Vector3.ZERO, "body")
	var two := h.alive
	h.take_damage(11.0, Vector3.ZERO, "body")
	_check("лежащего добивают за 3 попадания автомата", two and not h.alive, "")
	# в голову без шлема — не сразу: ранение с быстрым кровотечением; второе такое — добивает
	_fresh(h)
	h.take_damage(30.0, Vector3.ZERO, "head")
	var fast := h.downed and h.alive and h.bleed_t <= float(Balance.DOWN_BLEED_SEC[0]) * Balance.DOWN_LETHAL_BLEED_K + 0.01
	h.take_damage(80.0, Vector3.ZERO, "head")
	_check("в голову без шлема — тяжёлое ранение (кровь быстрее), лежащего — добивает", fast and not h.alive, "")
	# в шлеме: пуля остановлена — контузия, лёг (шлем закрывает не всю голову — несколько попыток)
	var saved := false
	for i in range(12):
		_fresh(h)
		me.inventory.equipment = {"helmet": ItemDb.make("helmet_top", 1)}
		h.take_damage(900.0, Vector3.ZERO, "head", Vector3.INF, {"pen": 2.0, "armor_dmg": 2.0})
		if h.alive and h.downed:
			saved = true
			break
	_check("в голову в шлеме (пуля остановлена) — лёг", saved, "")
	me.inventory.equipment = {}
	# граната под ногами
	_fresh(h)
	h.take_damage(150.0, Vector3.ZERO, "blast_close")
	_check("граната под ногами — тяжёлое ранение, не смерть", h.alive and h.downed, "")
	# третье ранение за рейд — смерть
	_fresh(h)
	h.take_damage(150.0, Vector3.ZERO, "body")
	h.revive(Balance.REVIVE_HP)
	h.take_damage(150.0, Vector3.ZERO, "body")
	var second_bleed := h.bleed_t
	h.revive(Balance.REVIVE_HP)
	h.take_damage(150.0, Vector3.ZERO, "body")
	_check("второе ранение — меньше времени, третье — смерть", not h.alive and is_equal_approx(second_bleed, float(Balance.DOWN_BLEED_SEC[1])), "второе: %.0f с" % second_bleed)
	# кровотечение
	_fresh(h)
	h.take_damage(150.0, Vector3.ZERO, "body")
	h.bleed_t = 0.3
	await _wait(0.6)
	_check("истёк кровью — смерть", not h.alive, "")
	# бинт лёжа — дольше; аптечка — встать
	_fresh(h)
	me.health.alive = true
	h.take_damage(150.0, Vector3.ZERO, "body")
	me.inventory.add("bandage", 1)
	me.inventory.add("medkit", 1)
	var b0 := h.bleed_t
	Raid.current.request_use_med("bandage")
	await _wait(float(ItemDb.item("bandage").use.time) + 0.2)
	_check("бинт лёжа — дольше до смерти", h.bleed_t > b0 + Balance.DOWN_BANDAGE_SEC - float(ItemDb.item("bandage").use.time) - 1.0 and not me.inventory.has("bandage"), "%.0f → %.0f с" % [b0, h.bleed_t])
	Raid.current.request_use_med("medkit")
	await _wait(Balance.REVIVE_SELF_SEC + 0.3)
	_check("аптечка лёжа — встал с 30 %", h.alive and not h.downed and is_equal_approx(h.hp, h.max_hp * Balance.REVIVE_HP) and not me.inventory.has("medkit"), "hp %.0f" % h.hp)
	# зона попадания: голова стоя (поднятый остаётся лёжа — встаёт сам)
	me.stance = Player.Stance.STAND
	_check("зона: голова / корпус по высоте", me.hit_zone(me.global_position + Vector3.UP * 1.7) == "head" and me.hit_zone(me.global_position + Vector3.UP * 1.3) == "thorax", me.hit_zone(me.global_position + Vector3.UP * 1.3))
	_fresh(h)


## Напарник: второй игрок (peer 2) лежит — поднять аптечкой, тащить, дотащить до эвакуации.
func _mate_rules(me: Player) -> void:
	var mate := (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	mate.name = "Player_2"
	mate.peer_id = 2
	_level.get_node("Players").add_child(mate)
	mate.global_position = me.global_position + Vector3(1.0, 0.1, 0.0)
	await get_tree().physics_frame
	mate.health.take_damage(150.0, Vector3.ZERO, "body")
	me.inventory.equipment = {}
	while me.inventory.has("medkit"):
		me.inventory.remove("medkit", 1)
	Raid.current._revive(1, 2)
	_check("без аптечки не поднять", mate.is_downed(), "")
	me.inventory.add("medkit", 1)
	Raid.current._revive(1, 2)
	_check("напарник поднял (аптечка ушла)", not mate.is_downed() and mate.health.alive and not me.inventory.has("medkit"), "")
	mate.health.take_damage(150.0, Vector3.ZERO, "body")
	Raid.current._drag(1, 2, true)
	_check("тащит раненого", Raid.current.dragger_of(2) == me and me.is_dragging() and me.allowed_weapons().size() <= 1, str(Raid.current.drags))
	var ext := get_tree().get_nodes_in_group("extractions")[0] as ExtractionPoint
	Raid.current._extract(me, ext)
	_check("дотащил до эвакуации — ушли оба", Raid.current.is_extracted(1) and Raid.current.is_extracted(2), str(Raid.current.extracted))
	# вернуть рейд как был
	Raid.current.extracted = {}
	Raid.current.over = false
	me.add_to_group("players")
	me.visible = true
	me.set_physics_process(true)
	me.collision_layer = 2
	me.collision_mask = 13
	mate.queue_free()
	await get_tree().physics_frame


## Мародёр лёг — пистолет, товарищ бежит, тащит/поднимает; в голову без шлема — смерть.
func _marauder_rules() -> void:
	var scene := preload("res://scenes/ai/marauder.tscn")
	var squad := Squad.new()
	var a := scene.instantiate() as Marauder
	a.name = "DownA"
	a.archetype = "gunner"
	# у бывалого всегда есть пистолет — лёжа стреляет из него
	a.loadout_id = "scav_veteran"
	a.weapon = "rifle"
	var b := scene.instantiate() as Marauder
	b.name = "MedicB"
	b.archetype = "gunner"
	b.weapon = "rifle"
	for m in [a, b]:
		_level.get_node("Marauders").add_child(m)
		squad.add(m)
		(m as Marauder).patrol_point_provider = func() -> Vector3: return (m as Marauder).global_position
	a.global_position = SectorBuilder.polar(-100.0, 72.0) + Vector3(0, 0.1, 0)
	b.global_position = SectorBuilder.polar(-108.0, 72.0) + Vector3(0, 0.1, 0)
	await _wait(1.0)
	a.last_known = SectorBuilder.polar(-90.0, 100.0)
	(a.get_node("Health") as Health).take_damage(300.0, a.last_known, "body")
	await get_tree().physics_frame
	_check("мародёр лёг раненым — пистолет", a.state == Marauder.State.DOWNED and String(a._spec["class"]) == "PISTOL", Marauder.State.keys()[a.state])
	_check("товарищ идёт спасать", b.state == Marauder.State.RESCUE and a.rescuer == b, Marauder.State.keys()[b.state])
	# лежит клипом падения, не «ногами вверх» (наклон корпуса поверх клипа переворачивал тело)
	await _wait(2.6)
	var sk := a.get_node("Body/Persona").find_children("*", "Skeleton3D", true, false)[0] as Skeleton3D
	var high := 0.0
	for bone in ["mixamorig_LeftToeBase", "mixamorig_RightToeBase", "mixamorig_Head", "mixamorig_Hips"]:
		high = maxf(high, (sk.global_transform * sk.get_bone_global_pose(sk.find_bone(bone))).origin.y - a.global_position.y)
	_check("раненый мародёр лежит (ноги и голова у пола)", not (a.get_node("Health") as Health).downed or high < 0.6, "выше всего %.2f м, лежит %s" % [high, (a.get_node("Health") as Health).downed])
	var up := false
	for i in range(50):
		await _wait(0.5)
		if not (a.get_node("Health") as Health).downed:
			up = true
			break
	_check("товарищ поднял раненого", up and a.state == Marauder.State.COMBAT and b.state != Marauder.State.RESCUE,
		"%s / %s" % [Marauder.State.keys()[a.state], Marauder.State.keys()[b.state]])
	var ah := a.get_node("Health") as Health
	ah.take_damage(10.0, Vector3.ZERO, "head")
	_check("мародёру в голову без шлема — смерть", not ah.alive, "")
	# в шлеме пуля остановлена — лёг (шлем закрывает не всю голову — несколько попыток)
	var helm: Array = []
	var saved := false
	for i in range(6):
		var hv := scene.instantiate() as Marauder
		hv.name = "HelmetH%d" % i
		hv.archetype = "heavy"
		_level.get_node("Marauders").add_child(hv)
		helm.append(hv)
		hv.global_position = SectorBuilder.polar(-130.0 - 2.0 * i, 72.0) + Vector3(0, 0.1, 0)
		await get_tree().physics_frame
		hv.equipment["helmet"] = ItemDb.make("helmet_top", 1)
		(hv.get_node("Health") as Health).take_damage(900.0, Vector3.ZERO, "head", Vector3.INF, {"pen": 2.0, "armor_dmg": 2.0})
		if (hv.get_node("Health") as Health).downed:
			saved = true
			break
	_check("тяжёлому в шлеме в голову — лёг", saved, "")
	for m in [b] + helm:
		(m as Node).queue_free()
	if is_instance_valid(a):
		a.queue_free()
	await get_tree().physics_frame


## Лежащего игрока мародёр добивает, только если другие не стреляют.
func _finish_rule() -> void:
	var me := get_tree().get_first_node_in_group("players") as Player
	var ppos := SectorBuilder.polar(-100.0, 72.0)
	me.global_position = ppos + Vector3(0, 0.1, 0)
	_fresh(me.health)
	me.health.take_damage(150.0, Vector3.ZERO, "body")
	var c := (preload("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	c.name = "FinisherC"
	c.archetype = "gunner"
	c.weapon = "rifle"
	c.patrol_point_provider = func() -> Vector3: return c.global_position
	_level.get_node("Marauders").add_child(c)
	c.global_position = SectorBuilder.polar(-108.0, 72.0) + Vector3(0, 0.1, 0)
	c._facing = atan2(ppos.x - c.global_position.x, ppos.z - c.global_position.z)
	# кто-то другой стреляет в стороне
	var hp0 := me.health.down_hp
	for i in range(6):
		NoiseBus.emit(ppos + Vector3(25, 0, 0), 80.0, "shot")
		await _wait(0.5)
	_check("пока стреляют другие — лежащего не добивает", me.health.alive and is_equal_approx(me.health.down_hp, hp0) and c._mag == int(c._spec.mag),
		"патронов %d, запас %.0f" % [c._mag, me.health.down_hp])
	# ушёл смотреть, кто стрелял; стихло — вернули лицом к лежащему
	await _wait(Balance.AI_FINISH_QUIET_SEC)
	c.global_position = SectorBuilder.polar(-108.0, 72.0) + Vector3(0, 0.1, 0)
	c._face(ppos)
	c.state = Marauder.State.PATROL
	c._agent.target_position = c.global_position
	await _wait(4.0)
	_check("тишина — добивает", c._mag < int(c._spec.mag), "патронов %d, жив %s" % [c._mag, me.health.alive])
	c.queue_free()


func _wait(s: float) -> void:
	await get_tree().create_timer(s).timeout


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
