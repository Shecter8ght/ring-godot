extends Node
## Пролог «Первый выход» (docs/design/prologue.md, data/quests/prologue.json) на настоящей карте «Проспект».
##   tools/godot.cmd --headless res://tools/prologue_test.tscn                — соло целиком
##   tools/godot.cmd --headless res://tools/prologue_test.tscn -- host        — кооп: хост
##   tools/godot.cmd --headless res://tools/prologue_test.tscn -- client      — кооп: гость, через 3 с после хоста
## С окном (--windowed --resolution 1600x900) — ещё снимки docs/screens/prologue_*.png.
## Соло: новая игра с прологом — тайник пуст, с собой рюкзак и медицина; режим карты (заход у ворот, один выход,
## население выключено, ЧВК у ворот мирные, трое руками, роллета рампы опущена); вводный экран; сумка с биркой
## и пакет; вернулся к воротам — окрик, предупредительный, огонь, «Я же сказал», гибель — заново от ворот;
## цели по порядку, ранние действия (оружие в руках и проверка магазина раньше подсказки) засчитаны, контрольная
## точка у кофейни; бой в зале — Михалыч «позвал всех», третий со склада идёт на шум; гибель — заново от кофейни
## одетым и с пакетом; обход служебным коридором — в зале тихо, Михалыч хвалит; склад, засов, двор, сквер,
## тоннель, выход без пакета — пролог зачтён, в итоге «не донесён», в убежище Михалыч ворчит и полки нет.
## Кооп (двое): сумка каждому, пакет один — его берёт и выносит гость, зачёт всем; гостю приходит его набор
## контрольной точки; гость упал — хосту подсказка «напарник упал», тащит, гостю — «перевязаться», бинт даёт время,
## хост поднимает аптечкой; оба выходят — пролог зачтён, пакет засчитан всем, вынесенное — в профиле гостя.
## Код выхода — число провалов.

const Q := "prologue"
const PORT := 17797

var _role: String = "solo"
var _fails: int = 0
var _said: Array[String] = []
var _shots_on: bool = false
var _last_raid_id: int = 0


func _ready() -> void:
	if name == "PrologueRunner":
		_run()
		return
	var runner := Node.new()
	runner.name = "PrologueRunner"
	runner.set_script(get_script())
	get_tree().root.add_child.call_deferred(runner)


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	if not args.is_empty() and String(args[0]) in ["host", "client"]:
		_role = String(args[0])
	_shots_on = DisplayServer.get_name() != "headless"
	Quests.subtitles.connect(func(lines: Array) -> void:
		for l in lines:
			_said.append(String(l[1]) if l is Array and (l as Array).size() > 1 else String(l)))
	match _role:
		"host":
			await _host()
		"client":
			await _client()
		_:
			await _solo()
	print("prologue_test[%s]: провалено %d" % [_role, _fails])
	get_tree().quit(_fails)


# ---------------------------------------------------------------- соло

func _new_profile(file: String, who: String) -> void:
	Profile.use_file(file, true)
	Profile.profile_name = who
	Profile.flags["new_game"] = true
	Profile.prologue_start()
	Profile.save()
	Quests.start(Q)


func _solo() -> void:
	_new_profile("user://prologue_test.json", "Тест")
	_check("новая игра: пролог идёт, тайник пуст, с собой рюкзак и медицина", Quests.state(Q) == "ACTIVE" and Profile.stash.is_empty()
		and Profile.equipment.has("backpack") and Profile.backpack.size() == 2, "%s, тайник %d, рюкзак %s" % [Quests.state(Q), Profile.stash.size(), str(Profile.backpack.map(func(e: Dictionary) -> String: return String(e.id)))])
	_check("обучение в убежище ждёт пролога", Quests.state("tutorial_basics") == "LOCKED", Quests.state("tutorial_basics"))
	var kit := Profile.start_kit()
	var rifle: Dictionary = kit.filter(func(e: Dictionary) -> bool: return String(e.id) == "wpn_ar_01")[0]
	_check("стартовый набор: на автомате тактический фонарь", _has_light(rifle), str(rifle.mods))
	# ---- первый заход: у ворот
	Prologue.launch()
	await _level_ready()
	await _start_checks()
	await _gate_and_die()
	# ---- заново от ворот: кофейня, ранние действия, контрольная точка, бой в зале, гибель
	await _level_ready()
	var me := _me()
	_check("после гибели у ворот — снова у ворот", me != null and me.global_position.distance_to(Vector3(-200, 0, -15.65)) < 4.0, str(me.global_position if me else Vector3.INF))
	await _wait(func() -> bool: return not _bags().is_empty(), 5.0)
	_check("ЧВК у ворот снова мирные", _pmc().all(func(m: Marauder) -> bool: return not m.hostile_to_players), "")
	_check("сумки снова в подсобке", not _bags().is_empty())
	_close_intro()
	await _coffee()
	await _hall_fight_and_die()
	# ---- заново от кофейни: одетые, с пакетом; коридор, склад, двор, тоннель — без пакета
	await _level_ready()
	await _from_checkpoint()
	await _to_extraction(true)
	_after_extraction_solo()


func _start_checks() -> void:
	var lvl := get_tree().current_scene
	_check("пролог на карте", Prologue.current != null and Prologue.current.get_parent() == lvl)
	var me := _me()
	_check("заход — у ворот кордона", me != null and me.global_position.distance_to(Vector3(-200, 0, -15.65)) < 4.0, str(me.global_position if me else Vector3.INF))
	var ext: Array = get_tree().get_nodes_in_group("extractions")
	_check("выход один — «Тоннель на юг»", ext.size() == 1 and (ext[0] as ExtractionPoint).display_name.begins_with("Тоннель на юг"), str(ext.map(func(e: Node) -> String: return (e as ExtractionPoint).display_name)))
	var pop := lvl.get_node_or_null("Population") as AIPopulation
	_check("население выключено: только пост у ворот", pop != null and pop.placed.get("posts", []) == ["Cordon_PMC"] and (pop.placed.get("routes", []) as Array).is_empty()
		and (pop.placed.get("nests", []) as Array).is_empty(), str(pop.placed if pop else {}))
	await _wait(func() -> bool: return _pmc().size() >= 2, 10.0)
	_check("ЧВК у ворот стоят и не трогают ушедших", _pmc().size() >= 2 and _pmc().all(func(m: Marauder) -> bool: return not m.hostile_to_players and m.has_meta("gate_warden")), "ЧВК %d" % _pmc().size())
	var names: Array = _hand_ai().map(func(m: Marauder) -> String: return String(m.name))
	_check("трое руками: двое в зале, один на складе", names.size() == 3 and "Prologue_Dock" in names and "Prologue_Hall_Cart" in names and "Prologue_Hall_Till" in names, str(names))
	_check("кроме них и ЧВК — никого", get_tree().get_nodes_in_group("marauders").size() == _pmc().size() + 3, "%d" % get_tree().get_nodes_in_group("marauders").size())
	var gate := lvl.get_node_or_null("Gameplay/Yarus_RampGate") as RollGate
	_check("роллета рампы опущена", gate != null and not gate.is_open)
	_check("чужих отрядов и событий нет", not RivalRaids.enabled and not RaidEvents.enabled)
	_check("вводный экран «Закрытый район» открыт, персонаж стоит", Prologue.current._intro != null and Prologue.current._intro.visible and me.ui_blocked())
	_check("на старте — лицом вдоль проспекта (на восток)", absf(wrapf(me.body_yaw() - PI * 0.5, -PI, PI)) < 0.5, "%.2f" % me.body_yaw())
	await _wait(func() -> bool: return not Loading.active, 20.0)
	await get_tree().create_timer(1.0).timeout
	await _shot("prologue_intro")
	_close_intro()
	await _wait(func() -> bool: return _heard("Слышу тебя"), 5.0)
	_check("рация: «Слышу тебя. Ворота за тобой закрыли…»", _heard("Слышу тебя"))
	await _wait(func() -> bool: return not _bags().is_empty(), 5.0)
	var bags := _bags()
	_check("сумка с биркой на имя профиля — в подсобке кофейни", bags.size() == 1 and (bags[0] as LootContainer).display_name == "Сумка · Тест"
		and (bags[0] as Node3D).global_position.distance_to(Vector3(-178.3, 0, -53.8)) < 2.5, str(bags.map(func(b: Node) -> String: return (b as LootContainer).display_name)))
	_check("пакет Михалычу лежит рядом", _packet() != null)
	_check("цель: «Дойти до кофейни «Зерно»»", _oid() == "coffee" and String(Quests.objective(Q).text).contains("Зерно"))
	await _frames(4)
	_check("подсказка: осмотреться и идти — с клавишами", _coach().contains("мышь") and _coach().contains("W"), _coach())
	_check("в прологе списка выходов на старте нет", Raid.current.exits_note == "", Raid.current.exits_note)
	await get_tree().create_timer(1.5).timeout
	await _shot("prologue_cordon")


## Вернулся к воротам: окрик, предупредительный, огонь; Михалыч «Я же сказал»; погиб — заново от ворот.
func _gate_and_die() -> void:
	var me := _me()
	var warden := get_tree().get_first_node_in_group("gate_wardens") as GateWarden
	await _tp(Vector3(-205.0, 0.1, -14.65))
	await _wait(func() -> bool: return warden.stage >= 1, 3.0)
	_check("у ворот: окрик", warden.stage >= 1, "этап %d" % warden.stage)
	await _wait(func() -> bool: return warden.stage >= 2, 6.0)
	_check("потом предупредительный в воздух", warden.stage >= 2)
	_check("до огня ЧВК по игроку не стреляют", me.is_alive() and not me.is_downed() and me.health.hp >= me.health.max_hp - 0.1)
	await _wait(func() -> bool: return warden.stage >= 3, 8.0)
	_check("потом огонь: ЧВК враждебны", warden.hostile and _pmc().all(func(m: Marauder) -> bool: return m.hostile_to_players))
	await _wait(func() -> bool: return _heard("Я же сказал"), 3.0)
	_check("Михалыч: «Я же сказал»", _heard("Я же сказал"))
	await _die()
	_check("итог: «заново от ворот»", Raid.current.end_hint.contains("от ворот"), Raid.current.end_hint)
	_check("контрольной точки ещё нет", Quests.flag("prologue_cp") != true)
	Prologue.current.after_end()


## Кофейня: цели по порядку; оружие в руках и проверка магазина — раньше подсказки; контрольная точка.
func _coffee() -> void:
	var me := _me()
	await _tp(Vector3(-184.0, 0.1, -49.9))
	await _wait(func() -> bool: return _oid() == "search", 4.0)
	_check("вошёл в кофейню — цель «обыскать сумку»", _oid() == "search", _oid())
	_check("рация: «За стойкой подсобка…»", _heard("За стойкой подсобка"))
	var bag := _bags()[0] as LootContainer
	await _tp(bag.global_position + Vector3(-0.9, 0.1, 0.0))
	await _frames(4)
	_check("подсказка у сумки: обыскать — F", _coach().contains("F"), _coach())
	Raid.current.ui.start_search(bag)
	await _wait(func() -> bool: return _oid() == "equip", 12.0)
	_check("обыскал сумку — цель «автомат в слот»", _oid() == "equip", _oid())
	_look_at(bag.global_position)
	_check("в сумке весь набор и фонарь на автомате", _idx(bag, "wpn_ar_01") >= 0 and _idx(bag, "armor_mid") >= 0 and _idx(bag, "helmet_simple") >= 0 and _idx(bag, "grenade") >= 0
		and _has_light(bag.items[_idx(bag, "wpn_ar_01")] as Dictionary))
	await _shot("prologue_bag")
	Raid.current.request_equip_from("loot", _idx(bag, "wpn_ar_01"), bag)
	await _wait(func() -> bool: return _oid() == "armor", 4.0)
	_check("автомат в слоте — цель «жилет и шлем»", _oid() == "armor", _oid())
	# раньше подсказки: оружие в руках и проверка магазина
	Raid.current.ui.close_all()
	me._switch("primary")
	await _wait(func() -> bool: return me.weapon_id != "", 3.0)
	me.ammo_check_text = "полный"
	me.ammo_check_t = 2.0
	await _wait(func() -> bool: return "act:weapon_ready" in Quests.facts(Q) and "act:check_mag" in Quests.facts(Q), 2.0)
	_check("ранние действия — факты квеста", "act:weapon_ready" in Quests.facts(Q) and "act:check_mag" in Quests.facts(Q), str(Quests.facts(Q)))
	Raid.current.ui.start_search(bag)
	await _frames(30)
	for id in ["armor_mid", "helmet_simple"]:
		Raid.current.request_equip_from("loot", _idx(bag, id), bag)
		await _frames(3)
	for id in ["mag_545_30", "ammo_545_std", "grenade"]:
		if _idx(bag, id) >= 0:
			Raid.current.request_take_to(bag, _idx(bag, id), -1, -1, false, "backpack")
			await _frames(3)
	await _wait(func() -> bool: return _oid() == "hall", 4.0)
	_check("надел броню; «взять в руки» засчитано заранее — цель «выйти в зал»", _oid() == "hall", _oid())
	var pk := _packet()
	if pk:
		Raid.current.request_take_to(pk, 0, -1, -1, false, "backpack")
		await _frames(4)
	_check("пакет — в рюкзаке", me.inventory.has("tutorial_packet"))
	Raid.current.ui.close_all()
	await _tp(Vector3(-181.9, 0.1, -53.8))
	await _wait(func() -> bool: return _oid() == "underpass", 4.0)
	_check("вышел в зал: проверка магазина засчитана заранее — цель «через переход»", _oid() == "underpass", _oid())
	_check("рация: «Прежде чем идти — проверь магазин…»", _heard("Прежде чем идти"))
	await _wait(func() -> bool: return Quests.flag("prologue_cp") == true, 3.0)
	var cp: Dictionary = Prologue.checkpoint_kit
	_check("контрольная точка: набор снят, пакет в нём", Quests.flag("prologue_cp") == true and (cp.get("equipment", {}) as Dictionary).has("primary")
		and (cp.get("backpack", []) as Array).any(func(e: Dictionary) -> bool: return String(e.id) == "tutorial_packet"), str((cp.get("equipment", {}) as Dictionary).keys()))
	_check("сделанное до кофейни переживёт гибель", "hall" in Quests.durable(Q) and "search" in (Profile.quests.get(Q, {}) as Dictionary).get("durable", []))
	# переход
	await _tp(Vector3(-161.0, 0.1, -38.6))
	await _wait(func() -> bool: return _heard("Тише по стеклу"), 3.0)
	_check("стекло под козырьком: «Тише по стеклу»", _heard("Тише по стеклу"))
	await _tp(Vector3(-156.0, -3.2, -15.65))
	await _frames(10)
	_check("в переходе темно — подсказка фонаря", _coach().contains("Фонарь") or RaidAtmosphere.current == null or not RaidAtmosphere.current.is_dark(me.global_position), _coach())
	await _tp(Vector3(-148.0, 0.1, 12.93))
	await _wait(func() -> bool: return _oid() == "warehouse", 4.0)
	_check("на южной стороне — цель «через «Ярус» на склад»", _oid() == "warehouse", _oid())
	_check("рация: «Выходишь за автобусом…»", _heard("Выходишь за автобусом"))


## Зал «Яруса»: шумнул — двое в бой, Михалыч «позвал всех», третий со склада идёт на шум; погиб — заново от кофейни.
func _hall_fight_and_die() -> void:
	var me := _me()
	await _tp(Vector3(-96.0, 0.1, 50.0))
	await _wait(func() -> bool: return _heard("Вот они"), 3.0)
	_check("тамбур: «Вот они. Слева от тамбура дверь…»", _heard("Вот они"))
	_look_at(Vector3(-114.0, 1.0, 66.0))
	await get_tree().create_timer(1.0).timeout
	await _shot("prologue_tambour")
	me.health.invulnerable = true
	var dock := _ai("Prologue_Dock")
	var dock_home := dock.global_position
	await _tp(Vector3(-114.0, 0.1, 55.0))
	for i in range(3):
		NoiseBus.emit(me.global_position, 60.0, "shot")
		await get_tree().create_timer(0.4).timeout
	await _wait(func() -> bool: return _heard("позвал всех"), 3.0)
	_check("стрельба в зале — «Ну вот, позвал всех»", _heard("позвал всех"))
	await _wait(func() -> bool: return _hand_ai().any(func(m: Marauder) -> bool: return m.name.begins_with("Prologue_Hall") and m.state == Marauder.State.COMBAT), 15.0)
	_check("двое в зале — в бой", _hand_ai().any(func(m: Marauder) -> bool: return m.name.begins_with("Prologue_Hall") and m.state == Marauder.State.COMBAT))
	await _wait(func() -> bool: return dock.state != Marauder.State.PATROL or dock.global_position.distance_to(dock_home) > 4.0, 25.0)
	_check("третий со склада слышит бой и идёт проверять", dock.state != Marauder.State.PATROL or dock.global_position.distance_to(dock_home) > 4.0, "%s, %.1f м" % [str(dock.state), dock.global_position.distance_to(dock_home)])
	me.health.invulnerable = false
	await _die()
	_check("итог: «заново от кофейни»", Raid.current.end_hint.contains("от кофейни"), Raid.current.end_hint)
	Prologue.current.after_end()


## С контрольной точки: одетые, с пакетом, сумок нет; проверка магазина заново.
func _from_checkpoint() -> void:
	var me := _me()
	_check("после гибели — у выхода из кофейни", me.global_position.distance_to(Vector3(-184.0, 0, -41.75)) < 4.0, str(me.global_position))
	await _wait(func() -> bool: return me.inventory.equipment.has("primary"), 5.0)
	_check("одет: автомат с фонарём, жилет, шлем", me.inventory.equipment.has("primary") and me.inventory.equipment.has("armor") and me.inventory.equipment.has("helmet")
		and _has_light(me.inventory.equipment.primary as Dictionary), str(me.inventory.equipment.keys()))
	_check("пакет в рюкзаке", me.inventory.has("tutorial_packet"))
	_check("цели до кофейни засчитаны — «проверить магазин»", _oid() == "check", _oid())
	_check("вводного экрана нет", Prologue.current._intro == null)
	await _frames(20)
	_check("сумок в подсобке нет", _bags().is_empty())
	await _frames(4)
	_check("подсказка: проверить магазин — держать R", _coach().contains("R"), _coach())
	me._switch("primary")
	me.ammo_check_text = "полный"
	me.ammo_check_t = 2.0
	await _wait(func() -> bool: return _oid() == "underpass", 3.0)
	_check("проверил магазин — «через переход»", _oid() == "underpass", _oid())
	await _tp(Vector3(-148.0, 0.1, 12.93))
	await _wait(func() -> bool: return _oid() == "warehouse", 4.0)


## Обход служебным коридором, склад, засов, двор, сквер, тоннель, эвакуация. no_packet — пакет оставлен.
func _to_extraction(no_packet: bool) -> void:
	var me := _me()
	var space := me.get_world_3d().direct_space_state
	var ray := PhysicsRayQueryParameters3D.create(Vector3(-66.0, 1.5, 62.0), Vector3(-62.6, 1.5, 62.0), Hitscan.LAYER_WORLD)
	_check("коридор «Только для персонала» отгорожен от зала стеной", not space.intersect_ray(ray).is_empty())
	var door := get_tree().get_nodes_in_group("doors").filter(func(d: Node) -> bool: return String(d.name) == "StaffDoor")
	_check("дверь в коридор — у тамбура", not door.is_empty() and (door[0] as Node3D).global_position.distance_to(Vector3(-64.3, 0, 51.2)) < 2.0,
		str((door[0] as Node3D).global_position if not door.is_empty() else Vector3.INF))
	for p: Vector3 in [Vector3(-96, 0.1, 50), Vector3(-67, 0.1, 50.6), Vector3(-63.2, 0.1, 53), Vector3(-63.2, 0.1, 60), Vector3(-63.2, 0.1, 67),
			Vector3(-63.2, 0.1, 74), Vector3(-63.2, 0.1, 80.5)]:
		await _tp(p)
		await get_tree().create_timer(0.6).timeout
	_look_at(Vector3(-63.2, 1.0, 84.0))
	await get_tree().create_timer(0.5).timeout
	await _shot("prologue_corridor")
	await _tp(Vector3(-63.2, 0.1, 83.4))
	await _wait(func() -> bool: return _oid() == "dock", 4.0)
	_check("вошёл в склад коридором — цель «у ворот рампы»", _oid() == "dock", _oid())
	_check("в зале тихо: двое не в бою", _hand_ai().all(func(m: Marauder) -> bool: return not m.name.begins_with("Prologue_Hall") or m.state != Marauder.State.COMBAT))
	_check("Михалыч: «Прошёл. Нормально…», потом «Кто-то у ворот…»", _heard("Прошёл. Нормально") and _heard("Кто-то у ворот")
		and _said.find_custom(func(s: String) -> bool: return s.contains("Прошёл")) < _said.find_custom(func(s: String) -> bool: return s.contains("Кто-то у ворот")))
	var dock := _ai("Prologue_Dock")
	_check("тот, кто у ворот, сидит на месте спиной к залу", dock != null and dock.stay and dock.watch_dir.z > 0.5)
	_look_at(dock.global_position)
	await get_tree().create_timer(0.8).timeout
	await _shot("prologue_dock")
	while dock and dock.state != Marauder.State.DEAD:
		dock.get_node("Health").call("take_damage", 400.0, dock.global_position + Vector3.BACK * 5.0)
		await _frames(3)
	await _wait(func() -> bool: return _oid() == "gate", 4.0)
	_check("убит — цель «во двор через рампу»", _oid() == "gate", _oid())
	_check("рация: «Жив? Забери, что у него есть…»", _heard("Жив?"))
	var gate := get_tree().current_scene.get_node("Gameplay/Yarus_RampGate") as RollGate
	await _tp(Vector3(-102.0, 0.1, 86.6))
	await _frames(3)
	_check("засов — только изнутри", gate.can_use())
	gate.request_use()
	await _wait(func() -> bool: return gate.is_open, 3.0)
	_check("ворота рампы поднялись", gate.is_open)
	await get_tree().create_timer(2.5).timeout
	if no_packet:
		var i := me.inventory.items.find_custom(func(e: Dictionary) -> bool: return String(e.id) == "tutorial_packet")
		if i >= 0:
			Raid.current.request_drop_entry("backpack", i)
		await _frames(4)
		_check("пакет бросил", not me.inventory.has("tutorial_packet"))
	await _tp(Vector3(-102.0, 0.1, 92.0))
	await _wait(func() -> bool: return _oid() == "calitka", 4.0)
	_check("во дворе — «через калитку»", _oid() == "calitka", _oid())
	await _tp(Vector3(-58.5, 0.1, 97.5))
	await _wait(func() -> bool: return _oid() == "wagons", 4.0)
	_check("калитка — «сквером к путям», рация", _oid() == "wagons" and _heard("Иди сквером к путям"))
	await _tp(Vector3(36.5, 0.2, 205.0))
	await _wait(func() -> bool: return _oid() == "tunnel", 4.0)
	_check("вагоны — «к тоннелю», «На насыпь не лезь»", _oid() == "tunnel" and _heard("На насыпь не лезь"))
	await _tp(Vector3(77.19, 0.2, 244.0))
	await _wait(func() -> bool: return _oid() == "extract", 4.0)
	_check("тоннель — «Вижу тебя…», цель — эвакуация", _oid() == "extract" and _heard("Вижу тебя"))
	var ext := get_tree().get_nodes_in_group("extractions")[0] as ExtractionPoint
	await _tp(ext.global_position + Vector3(0, 0.2, 0))
	await _wait(func() -> bool: return Raid.current.is_extracted(me.peer_id), 30.0)
	_check("эвакуировался через «Тоннель на юг»", Raid.current.is_extracted(me.peer_id))
	await _frames(20)


func _after_extraction_solo() -> void:
	_check("пролог зачтён", Quests.state(Q) == "COMPLETED" and Quests.flag("prologue_done") == true, Quests.state(Q))
	_check("без пакета: флаг не выставлен", Quests.flag("packet_delivered") != true)
	await _wait(func() -> bool: return Raid.current.summary_note != "", 5.0)
	_check("итог: «Пакет Михалычу — не донесён» красным", Raid.current.summary_note.contains("не донесён") and Raid.current.summary_note_bad, Raid.current.summary_note)
	await _wait(func() -> bool: return Profile.equipment.has("primary"), 5.0)
	_check("набор вынесен — в профиле", Profile.equipment.has("primary") and Profile.equipment.has("armor"), str(Profile.equipment.keys()))
	await _shot("prologue_summary")
	var t := "tutorial_basics"
	_check("обучение в убежище доступно", Quests.state(t) == "AVAILABLE", Quests.state(t))
	var objs: Array = Quests.def(t).stages[0].objectives
	var by: Dictionary = {}
	for o: Dictionary in objs:
		by[String(o.id)] = o
	_check("Михалыч без пакета ворчит", Quests.talk_dialogue(t, by.talk) == "greet_nopacket" and String(Quests.dialogue(t, "greet_nopacket")[0][1]).contains("Пакет где?"))
	_check("шаги «пакет с ящиков», «рюкзак» и «полка» пропускаются", Quests._already_done(t, by.box) and Quests._already_done(t, by.bag) and Quests._already_done(t, by.shelf))
	_check("тайник и терминал — нужны", not Quests._already_done(t, by.stash) and not Quests._already_done(t, by.terminal))


# ---------------------------------------------------------------- кооп

func _host() -> void:
	_new_profile("user://prologue_test_host.json", "Хост")
	_check("сервер поднят", Net.host("Хост", PORT) == "")
	await _wait(func() -> bool: return multiplayer.get_peers().size() == 1, 30.0)
	await get_tree().create_timer(2.0).timeout
	Profile.from_hideout = true
	Net.start_level.rpc(String(Balance.PROLOGUE.scene), (Balance.PROLOGUE.conditions as Dictionary).duplicate())
	await _level_ready()
	await _wait(func() -> bool: return get_tree().get_nodes_in_group("players").size() == 2, 30.0)
	_close_intro()
	await _wait(func() -> bool: return _bags().size() == 2, 10.0)
	var names: Array = _bags().map(func(b: Node) -> String: return (b as LootContainer).display_name)
	_check("кооп: по сумке каждому", _bags().size() == 2 and "Сумка · Хост" in names, str(names))
	var packs := get_tree().get_nodes_in_group("loot_containers").filter(func(c: Node) -> bool: return (c as LootContainer).items.any(func(e: Dictionary) -> bool: return String(e.id) == "tutorial_packet"))
	_check("кооп: пакет один на группу", packs.size() == 1, "%d" % packs.size())
	var me := _me()
	var bag := _bags().filter(func(b: Node) -> bool: return (b as LootContainer).display_name == "Сумка · Хост")[0] as LootContainer
	await _tp(Vector3(-184.0, 0.1, -49.9))
	await _wait(func() -> bool: return _oid() == "search", 6.0)
	await _tp(bag.global_position + Vector3(-0.9, 0.1, 0.0))
	Raid.current.ui.start_search(bag)
	await _wait(func() -> bool: return _oid() == "equip", 12.0)
	for id in ["wpn_ar_01", "armor_mid", "helmet_simple"]:
		Raid.current.request_equip_from("loot", _idx(bag, id), bag)
		await _frames(4)
	Raid.current.ui.close_all()
	me._switch("primary")
	await _wait(func() -> bool: return _oid() == "hall", 6.0)
	# гость тем временем берёт пакет
	await _wait(func() -> bool: return _client_player() != null and _client_player().inventory.has("tutorial_packet"), 30.0)
	_check("кооп: пакет взял гость", _client_player() != null and _client_player().inventory.has("tutorial_packet"))
	await _tp(Vector3(-181.9, 0.1, -53.8))
	await _wait(func() -> bool: return Quests.flag("prologue_cp") == true, 6.0)
	_check("кооп: контрольная точка, пакет — в наборе гостя", Quests.flag("prologue_cp") == true)
	# гость упал — подсказка хосту, тащить
	var mate := _client_player()
	await _tp(mate.global_position + Vector3(1.0, 0.0, 0.0))
	while mate.is_alive() and not mate.is_downed():
		mate.health.take_damage(150.0, mate.global_position + Vector3.BACK * 3.0, "torso")
		await _frames(2)
	await _frames(6)
	_check("кооп: гость упал", mate.is_downed())
	await _wait(func() -> bool: return _coach().contains("Напарник упал"), 3.0)
	_check("подсказка хосту: «Напарник упал: поднять — держать F…, тащить — X»", _coach().contains("Напарник упал"), _coach())
	await _shot("prologue_mate_down")
	Raid.current.request_drag(mate.peer_id, true)
	await _frames(6)
	_check("кооп: хост тащит упавшего", Raid.current.drag_target_of(me.peer_id) == mate.peer_id)
	Raid.current.request_drag(mate.peer_id, false)
	await _wait(func() -> bool: return mate.inventory.count("bandage") <= 1, 15.0)
	_check("кооп: упавший гость перевязался сам (бинт даёт время)", mate.inventory.count("bandage") <= 1, "%d" % mate.inventory.count("bandage"))
	# поднять: аптечки в наборе нет — хосту её даёт тест
	me.inventory.add("medkit", 1)
	Raid.current.request_revive(mate.peer_id)
	await _wait(func() -> bool: return not mate.is_downed(), 5.0)
	_check("кооп: поднял напарника аптечкой", mate.is_alive() and not mate.is_downed())
	# дальше хост ведёт группу: склад, засов, тоннель (гость идёт следом сам)
	await _tp(Vector3(-148.0, 0.1, 12.93))
	me.ammo_check_text = "полный"
	me.ammo_check_t = 2.0
	await _wait(func() -> bool: return _oid() == "warehouse", 6.0)
	await _tp(Vector3(-63.2, 0.1, 83.4))
	await _wait(func() -> bool: return _oid() == "dock", 6.0)
	var dock := _ai("Prologue_Dock")
	while dock and dock.state != Marauder.State.DEAD:
		dock.get_node("Health").call("take_damage", 400.0, dock.global_position + Vector3.BACK * 5.0)
		await _frames(3)
	await _wait(func() -> bool: return _oid() == "gate", 6.0)
	var gate := get_tree().current_scene.get_node("Gameplay/Yarus_RampGate") as RollGate
	gate._use(1)
	for p: Vector3 in [Vector3(-102, 0.1, 92), Vector3(-58.5, 0.1, 97.5), Vector3(36.5, 0.2, 205), Vector3(77.19, 0.2, 244)]:
		await _tp(p)
		await get_tree().create_timer(1.5).timeout
	_check("кооп: цели до эвакуации пройдены хостом", _oid() == "extract", _oid())
	var ext := get_tree().get_nodes_in_group("extractions")[0] as ExtractionPoint
	await _tp(ext.global_position + Vector3(1.0, 0.2, 0))
	await _wait(func() -> bool: return Raid.current.is_extracted(me.peer_id) and Raid.current.is_extracted(mate.peer_id), 40.0)
	_check("кооп: оба эвакуировались", Raid.current.is_extracted(me.peer_id) and Raid.current.is_extracted(mate.peer_id), str(Raid.current.extracted))
	await _frames(20)
	_check("кооп: пролог зачтён, пакет вынес гость — засчитан всем", Quests.state(Q) == "COMPLETED" and Quests.flag("packet_delivered") == true)
	# гость досматривает свои проверки, пока связь есть
	await get_tree().create_timer(12.0).timeout


func _client() -> void:
	await get_tree().create_timer(3.0).timeout
	_new_profile("user://prologue_test_client.json", "Друг")
	Profile.from_hideout = true
	_check("подключение", Net.join("127.0.0.1", "Друг", PORT) == "")
	await Net.joined
	# как из главного меню: хост узнаёт, где гость, и шлёт снимок кампании (пролог идёт)
	Net.enter_scene("menu")
	await _wait(func() -> bool: return Quests.state(Q) == "ACTIVE", 20.0)
	_check("гость видит пролог кампании хоста", Quests.state(Q) == "ACTIVE", Quests.state(Q))
	await _level_ready()
	_close_intro()
	var me := _me()
	await _wait(func() -> bool: return _packet() != null, 20.0)
	await _tp(_packet().global_position + Vector3(-0.7, 0.1, 0.0))
	# хост сверяет, рядом ли гость: позиция гостя доходит до него не сразу — просим ещё раз, пока не отдаст
	for i in range(10):
		await get_tree().create_timer(0.6).timeout
		if me.inventory.has("tutorial_packet") or _packet() == null:
			break
		Raid.current.request_take_to(_packet(), 0, -1, -1, false, "backpack")
	await _wait(func() -> bool: return me.inventory.has("tutorial_packet"), 6.0)
	_check("гость взял пакет", me.inventory.has("tutorial_packet"))
	await _wait(func() -> bool: return not Prologue.checkpoint_kit.is_empty(), 40.0)
	_check("гостю пришёл его набор контрольной точки с пакетом", (Prologue.checkpoint_kit.get("backpack", []) as Array).any(func(e: Dictionary) -> bool: return String(e.id) == "tutorial_packet"))
	await _wait(func() -> bool: return me.is_downed(), 30.0)
	_check("гость упал", me.is_downed())
	await _wait(func() -> bool: return _coach().contains("Перевязаться"), 3.0)
	_check("гостю подсказка: «Перевязаться лёжа — …»", _coach().contains("Перевязаться"), _coach())
	await get_tree().create_timer(1.5).timeout
	Raid.current.request_use_med("bandage")
	await _wait(func() -> bool: return not me.is_downed(), 30.0)
	# идёт за хостом к тоннелю
	var host_pl: Player = null
	await _wait(func() -> bool: return Quests.objective(Q).get("id", "") == "extract", 60.0)
	for n in get_tree().get_nodes_in_group("players"):
		if (n as Player).peer_id == 1:
			host_pl = n as Player
	var ext := get_tree().get_nodes_in_group("extractions")[0] as ExtractionPoint
	await _tp(ext.global_position + Vector3(-1.0, 0.2, 0))
	await _wait(func() -> bool: return Raid.current.is_extracted(me.peer_id), 40.0)
	_check("гость эвакуировался", Raid.current.is_extracted(me.peer_id))
	await _wait(func() -> bool: return Quests.state(Q) == "COMPLETED", 10.0)
	_check("у гостя пролог зачтён (кампания хоста)", Quests.state(Q) == "COMPLETED")
	await _wait(func() -> bool: return Profile.equipment.has("primary") or Profile.backpack.any(func(e: Dictionary) -> bool: return String(e.id) == "tutorial_packet"), 10.0)
	_check("свой профиль гостя: вынесенное с пакетом — у него", Profile.backpack.any(func(e: Dictionary) -> bool: return String(e.id) == "tutorial_packet"), str(Profile.backpack.map(func(e: Dictionary) -> String: return String(e.id))))
	await get_tree().create_timer(2.0).timeout


# ---------------------------------------------------------------- помощники

## Уровень пролога загружен (после перезапуска — новый, не тот, что был), навигация готова, население стоит.
func _level_ready() -> void:
	var prev := _last_raid_id
	await _wait(func() -> bool: return Raid.current != null and Raid.current.get_instance_id() != prev and Raid.current.is_inside_tree() and Raid.current.local_player() != null and Prologue.current != null, 180.0)
	_last_raid_id = Raid.current.get_instance_id() if Raid.current else 0
	var lvl := get_tree().current_scene
	# население расставляет хост — гость ждёт своего игрока и готовой навигации
	if _role == "client":
		await _wait(func() -> bool: return lvl != null and bool(lvl.get("_nav_baked")), 180.0)
	else:
		await _wait(func() -> bool: return lvl != null and int(lvl.get("_marauders_spawned")) > 0, 180.0)
	await _frames(10)
	_check("уровень пролога готов", Raid.current != null and Prologue.current != null and (_role == "client" or int(lvl.get("_marauders_spawned")) > 0))


func _close_intro() -> void:
	if Prologue.current and Prologue.current._intro and Prologue.current._intro.visible:
		(Prologue.current._intro as Prologue.IntroScreen).close()


func _die() -> void:
	var me := _me()
	me.health.invulnerable = false
	while me.is_alive():
		me.health.take_damage(300.0, me.global_position + Vector3.BACK * 3.0, "torso")
		await _frames(2)
		if me.is_downed():
			Raid.current.request_give_up()
			await _frames(2)
	await _wait(func() -> bool: return Raid.current.over, 6.0)
	await _frames(10)


## Снимки: взгляд из глаз — на точку (камера игрока; в игре так поворачивает мышь).
func _look_at(p: Vector3) -> void:
	var me := _me()
	var rig := get_tree().current_scene.get_node_or_null("CameraRig")
	if me == null or rig == null:
		return
	rig.set("_look_yaw", atan2(p.x - me.global_position.x, p.z - me.global_position.z))
	rig.set("_look_pitch", 0.0)


func _me() -> Player:
	return Raid.current.local_player() if Raid.current else null


func _client_player() -> Player:
	for n in get_tree().get_nodes_in_group("players"):
		var p := n as Player
		if p and p.peer_id != multiplayer.get_unique_id():
			return p
	return null


func _oid() -> String:
	return String(Quests.objective(Q).get("id", ""))


func _coach() -> String:
	return Quests.hud.coach_shown() if Quests.hud else ""


func _heard(part: String) -> bool:
	return _said.any(func(s: String) -> bool: return s.contains(part))


func _pmc() -> Array:
	return get_tree().get_nodes_in_group("marauders").filter(func(n: Node) -> bool:
		var m := n as Marauder
		return m != null and m.faction == "pmc" and m.state != Marauder.State.DEAD)


func _hand_ai() -> Array:
	return get_tree().get_nodes_in_group("marauders").filter(func(n: Node) -> bool: return String(n.name).begins_with("Prologue_"))


func _ai(nm: String) -> Marauder:
	for n in _hand_ai():
		if String(n.name) == nm:
			return n as Marauder
	return null


func _bags() -> Array:
	return get_tree().get_nodes_in_group("loot_containers").filter(func(c: Node) -> bool:
		return c is LootContainer and (c as LootContainer).display_name.begins_with(String(Balance.PROLOGUE.bag_name) + " · "))


func _packet() -> LootContainer:
	for c in get_tree().get_nodes_in_group("loot_containers"):
		var lc := c as LootContainer
		if lc and lc.items.size() == 1 and String((lc.items[0] as Dictionary).id) == "tutorial_packet":
			return lc
	return null


## Тактический фонарь на оружии в любой точке: в стартовом наборе он на креплении ДОЗОР-П справа
## (точка «side_right/light»), прямо на планку его больше не ставят.
func _has_light(weapon: Dictionary) -> bool:
	for v in (weapon.get("mods", {}) as Dictionary).values():
		if WeaponDb.mod_id(v) == "tac_flashlight_01":
			return true
	return false


func _idx(c: LootContainer, id: String) -> int:
	return c.items.find_custom(func(e: Dictionary) -> bool: return String(e.id) == id)


func _tp(p: Vector3) -> void:
	var me := _me()
	if me == null:
		return
	me.global_position = p
	me.velocity = Vector3.ZERO
	await _frames(3)


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().physics_frame


func _wait(cond: Callable, sec: float) -> void:
	var end := Time.get_ticks_msec() + int(sec * 1000.0)
	while Time.get_ticks_msec() < end:
		if cond.call():
			return
		await get_tree().process_frame


func _shot(nm: String) -> void:
	if not _shots_on:
		return
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://docs/screens"))
	img.save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % nm))


func _check(what: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_fails += 1
	print("%s %s%s" % ["  ок " if ok else "ПРОВАЛ", what, ("  [" + detail + "]") if detail != "" and not ok else ""])
