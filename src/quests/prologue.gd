class_name Prologue
extends Node
## Пролог «Первый выход» на карте рейда (docs/design/prologue.md, данные — data/quests/prologue.json → raid):
## режим карты — свой заход у ворот кордона, один выход, население выключено (кроме поста ЧВК у ворот), трое
## руками (узлы группы prologue_marauders: двое в зале «Яруса», один на складе у рампы), роллета рампы
## опущена; сумка на каждого участника и пакет Михалычу на группу — в подсобке кофейни (опоздавшему, если
## группа прошла кофейню, — у рампы); рация Михалыча субтитрами у мест и по событиям, раз на рейд; контрольная
## точка у кофейни: набор каждого снимается, когда группа вышла в зал одетой, — погибла вся группа, пролог
## заново у выхода из кофейни, уже одетыми; вступительный экран «Закрытый район»; в итоге — донесён ли пакет.
## Создаёт SectorLevel (Prologue.attach), если квест пролога идёт и это его карта. Решает хост; у гостя —
## свой набор, своя сумка, свой экран и подсказки.

static var current: Prologue
## Свой набор на контрольной точке (снял хост): {equipment, backpack}; пусто — нет.
static var checkpoint_kit: Dictionary = {}
## Вступительный экран закрыт в этой сессии (гость со своей кампанией — его профиль не трогаем).
static var intro_seen: bool = false

var qid: String = ""
## Режим рейда из данных квеста (raid).
var spec: Dictionary = {}
var level: Node3D
var _rivals_was: bool = true
var _events_was: bool = true
## Хост: что уже сказано по рации (id) — раз на рейд.
var _said: Dictionary = {}
## Хост: кому сумка уже положена (peer).
var _bagged: Dictionary = {}
var _packet_placed: bool = false
var _cp_taken: bool = false
var _shots: bool = false
var _dock: Array[Marauder] = []
var _ai_spawned: bool = false
var _tick: float = 0.0
var _start_said: bool = false
var _intro: CanvasLayer
var _died_noted: bool = false
var _grenade_said: bool = false
## Рейд начат с контрольной точки (после гибели всей группы).
var _restart_run: bool = false
var _initial_seen: bool = false


## Пролог на этом уровне: квест идёт, рейд настоящий, карта — его; иначе null.
static func attach(lvl: Node3D) -> Prologue:
	var q := String(Balance.PROLOGUE.quest)
	if Quests.state(q) != "ACTIVE" or not Profile.pending_raid:
		return null
	var rd := Quests.raid_def(q)
	if rd.is_empty() or String(rd.get("level", "")) != lvl.scene_file_path.get_file().get_basename():
		return null
	var p := Prologue.new()
	p.name = "Prologue"
	p.qid = q
	p.spec = rd
	p.level = lvl
	lvl.add_child(p)
	return p


## Убежище после пролога (QuestWorld): свой игрок погиб, а группа пролог прошла — стартовый набор заново в
## тайник, один раз (пролог — исключение из «всё на кону», §7).
static func settle() -> void:
	if not bool(Profile.flags.get("prologue_died", false)):
		return
	if Quests.state(String(Balance.PROLOGUE.quest)) != "COMPLETED":
		return
	for e in Profile.start_kit():
		ItemDb.add_to(Profile.stash, e, Profile.stash_grid())
	if not Profile.equipment.has("backpack"):
		Profile.equipment["backpack"] = ItemDb.make(Balance.BACKPACK_START, 1)
	Profile.flags.erase("prologue_died")
	Profile.save()
	Quests.notice.emit("Михалыч вернул стартовый набор — в тайнике")


## Новая игра или «Продолжить» с идущим прологом: в рейд «Проспекта» (с контрольной точки, если она была).
static func launch(prepare: Callable = Callable()) -> void:
	Net.change_scene(String(Balance.PROLOGUE.scene), "Первый выход", func() -> void:
		if prepare.is_valid():
			prepare.call()
		Profile.pending_raid = true
		Profile.next_conditions = (Balance.PROLOGUE.conditions as Dictionary).duplicate())


func _enter_tree() -> void:
	current = self


func _ready() -> void:
	# рация прошлой попытки (погибли — заново) не доигрывается в новой
	if Quests.hud:
		Quests.hud.clear_subtitles()
	# ни чужих отрядов, ни событий карты (сброс, ЧВК у вокзала) — своё у пролога; после рейда — как было
	_restart_run = at_checkpoint()
	_rivals_was = RivalRaids.enabled
	_events_was = RaidEvents.enabled
	RivalRaids.enabled = false
	RaidEvents.enabled = false
	NoiseBus.noise.connect(_on_noise)
	for n in get_tree().get_nodes_in_group("gate_wardens"):
		(n as GateWarden).escalated.connect(_on_gate)
	# выход один: остальные точки на карте не показаны (§8)
	var allowed: Array = spec.get("exits", [])
	for n in get_tree().get_nodes_in_group("extractions"):
		var ext := n as ExtractionPoint
		if ext == null or not level.is_ancestor_of(ext):
			continue
		var keep := false
		for a in allowed:
			keep = keep or ext.display_name.begins_with(String(a))
		if not keep:
			ext.remove_from_group("extractions")
			ext.visible = false
			ext.process_mode = Node.PROCESS_MODE_DISABLED
	if _is_host():
		for path in spec.get("close_gates", []):
			var g := level.get_node_or_null(NodePath(String(path))) as RollGate
			if g:
				g.close()
	_show_intro()


func _exit_tree() -> void:
	RivalRaids.enabled = _rivals_was
	RaidEvents.enabled = _events_was
	if NoiseBus.noise.is_connected(_on_noise):
		NoiseBus.noise.disconnect(_on_noise)
	if current == self:
		current = null


func _is_host() -> bool:
	return not Net.is_networked() or multiplayer.is_server()


## Население: только посты ворот (keep_posts), ни патрулей, ни подхода (§8).
func setup_population(pop: AIPopulation) -> void:
	pop.posts_only = String(spec.get("population", "")) == "none"
	pop.keep_posts = (spec.get("keep_posts", []) as Array).duplicate()


## Профиль этого игрока — новая игра с прологом: его снаряжение на кону и итог записывается. Гость со своей
## кампанией идёт прологом хоста, его профиль не трогается (§6).
func owns_profile() -> bool:
	return bool(Profile.flags.get("prologue", false))


## Контрольная точка пройдена (флаг кампании хоста; у гостя — из снимка).
func at_checkpoint() -> bool:
	return Quests.flag("prologue_cp") == true


## Где появляется группа: у ворот, после контрольной точки — у выхода из кофейни.
func spawn_at(fallback: Vector3) -> Vector3:
	var path := String(spec.get("checkpoint" if at_checkpoint() else "entry", ""))
	var n := level.get_node_or_null(NodePath(path)) as Node3D
	return n.global_position if n else fallback


## Куда смотреть на появлении (look / look_cp — точка [x, z]): у ворот — вдоль проспекта, у кофейни — к переходу.
func spawn_yaw(at: Vector3) -> float:
	var t: Array = spec.get("look_cp" if at_checkpoint() else "look", [])
	if t.size() < 2:
		return 0.0
	return atan2(float(t[0]) - at.x, float(t[1]) - at.z)


## Опоздавший появляется у группы — у первого живого игрока.
func late_spawn(fallback: Vector3) -> Vector3:
	for n in get_tree().get_nodes_in_group("players"):
		var pl := n as Player
		if pl and pl.is_alive():
			return pl.global_position + Vector3(1.2, 0.05, 0.0)
	return fallback


## Свой набор на вход: с контрольной точки — как был снят у кофейни; иначе с собой через кордон — рюкзак и
## немного медицины (остальное в закладке). Свой профиль — на кону, как в любом рейде.
func loadout() -> Dictionary:
	var lo := {"pocket": Profile.pocket.duplicate(true), "pocket_grid": Profile.pocket_grid(), "profile_id": Profile.profile_id}
	if owns_profile():
		Profile.take_loadout()
		if checkpoint_kit.is_empty():
			var saved: Variant = Profile.flags.get("prologue_kit", {})
			checkpoint_kit = (saved as Dictionary).duplicate(true) if saved is Dictionary else {}
	if at_checkpoint() and not checkpoint_kit.is_empty():
		lo["equipment"] = (checkpoint_kit.get("equipment", {}) as Dictionary).duplicate(true)
		lo["backpack"] = (checkpoint_kit.get("backpack", []) as Array).duplicate(true)
		return lo
	var eq := {"backpack": ItemDb.make(Balance.BACKPACK_START, 1)}
	var items: Array = []
	for pair in Balance.PROLOGUE.carry:
		ItemDb.add_to(items, ItemDb.make(String(pair[0]), int(pair[1])), ItemDb.bag_grid(eq))
	lo["equipment"] = eq
	lo["backpack"] = items
	return lo


# ---------------------------------------------------------------- хост: мир пролога

## Хост, навигация готова: трое руками — по узлам группы prologue_marauders (роль, тип, куда смотрит / маршрут).
func spawn_marauders() -> void:
	if _ai_spawned or not _is_host():
		return
	_ai_spawned = true
	var map: RID = level.get_world_3d().navigation_map
	var squads: Dictionary = {}
	for n in get_tree().get_nodes_in_group("prologue_marauders"):
		var mk := n as Node3D
		if mk == null or not level.is_ancestor_of(mk):
			continue
		var role := String(mk.get_meta("role", ""))
		var at := NavigationServer3D.map_get_closest_point(map, mk.global_position)
		var m := level.call("spawn_marauder", at, String(mk.get_meta("arch", "gunner")), {"name": "Prologue_" + String(mk.name)}) as Marauder
		if m == null:
			continue
		m.no_loot = true
		var route := PackedVector3Array()
		for c in mk.get_children():
			if c is Marker3D:
				route.append(NavigationServer3D.map_get_closest_point(map, (c as Marker3D).global_position))
		if not route.is_empty():
			m.route = route
		else:
			m.home = at
			m.home_radius = 1.5
			m.stay = true
			m.watch_dir = mk.get_meta("watch", Vector3.FORWARD) as Vector3
			m.watch_sector_deg = 30.0
		# двое в зале — один отряд (окликают друг друга), склад — сам по себе
		var key := "dock" if role == "dock" else "hall"
		if not squads.has(key):
			squads[key] = Squad.new()
		(squads[key] as Squad).add(m)
		if role == "dock":
			_dock.append(m)
	print("prologue: руками %d (склад %d)" % [get_tree().get_nodes_in_group("prologue_marauders").size(), _dock.size()])


func _process(delta: float) -> void:
	_local(delta)
	if not _is_host() or Raid.current == null:
		return
	_tick -= delta
	if _tick > 0.0:
		return
	_tick = 0.2
	_place_bags()
	_start_lines()
	_radio_zones()
	_areas()
	_dock_check()
	_checkpoint()
	_burst()


## Сумка с биркой на каждого участника: в подсобке кофейни, пока группа её не прошла; потом — у рампы склада
## (опоздавший, §6). Пакет Михалычу — один, на первой сумке; после контрольной точки он уже в рюкзаке.
func _place_bags() -> void:
	var raid := Raid.current
	var past := _restart_run or _cp_taken
	for peer in raid.participants:
		if _bagged.has(peer):
			continue
		# пришли с контрольной точки одетыми — сумки им не нужны (опоздавшему — у рампы)
		if _restart_run and not _initial_seen:
			_bagged[peer] = true
			continue
		var mk := level.get_node_or_null(NodePath(String(spec.get("late_bags" if past else "bags", "")))) as Node3D
		if mk == null:
			_bagged[peer] = true
			continue
		var i := _bagged.size()
		var at := mk.global_position + Vector3(0.0, 0.0, (float(i % 3) - 1.0) * 0.95)
		var who := Profile.profile_name if not Net.is_networked() or int(peer) == multiplayer.get_unique_id() else String(Net.player_names.get(peer, raid.participants[peer]))
		if who == "":
			who = String(raid.participants[peer])
		raid.spawn_drop(at, "%s · %s" % [String(Balance.PROLOGUE.bag_name), who], Profile.start_kit(Balance.PROLOGUE.carry), LootContainer.Look.BAG)
		_bagged[peer] = true
		if not _packet_placed and not past:
			_packet_placed = true
			raid.spawn_item(at + Vector3(0.55, 0.05, 0.0), ItemDb.make(String(Balance.PROLOGUE.packet), 1), 0.4)
	# кто был в рейде с самого начала — учтён; дальше приходят только опоздавшие
	if not raid.participants.is_empty():
		_initial_seen = true


## Рация на старте: текущая цель — её реплики (первый раз — у ворот; после гибели — у кофейни).
func _start_lines() -> void:
	if _start_said or Raid.current.local_player() == null or (_intro and _intro.visible):
		return
	_start_said = true
	var lines: Array = Quests.objective(qid).get("say_start", [])
	if not lines.is_empty():
		Quests.say(lines)


## Реплики у мест (radio.zones): цель — текущая, кто-то из группы рядом; раз на рейд.
func _radio_zones() -> void:
	var oid := String(Quests.objective(qid).get("id", ""))
	for z: Dictionary in (spec.get("radio", {}) as Dictionary).get("zones", []):
		var id := String(z.get("id", ""))
		if _said.has(id) or String(z.get("objective", "")) != oid:
			continue
		var at: Array = z.get("at", [0, 0])
		for n in get_tree().get_nodes_in_group("players"):
			var pl := n as Player
			if pl == null or not pl.is_alive():
				continue
			if z.has("y_min") and pl.global_position.y < float(z.y_min):
				continue
			if Vector2(pl.global_position.x - float(at[0]), pl.global_position.z - float(at[1])).length() <= float(z.get("r", 4.0)):
				_say_once(id, z.get("lines", []))
				break


## Цель «войти в помещение» прямоугольником (areas: склад «Яруса» — вошёл любым путём). Прошёл тихо —
## Михалыч сначала хвалит, потом — про того, кто у ворот.
func _areas() -> void:
	var o := Quests.objective(qid)
	for a: Dictionary in spec.get("areas", []):
		var sid := String(a.get("site", ""))
		if String(o.get("site", "")) != sid:
			continue
		var b: Array = a.get("box", [])
		for n in get_tree().get_nodes_in_group("players"):
			var pl := n as Player
			if pl == null or not pl.is_alive():
				continue
			var p := pl.global_position
			if p.x >= float(b[0]) and p.z >= float(b[1]) and p.x <= float(b[2]) and p.z <= float(b[3]) and absf(p.y) < 3.0:
				var quiet: Dictionary = (spec.get("radio", {}) as Dictionary).get("quiet", {})
				if not _shots and String(quiet.get("objective", "")) == String(o.get("id", "")):
					_say_once("quiet", quiet.get("lines", []))
				Quests.event("site", {"site": sid})
				return


## Цель «разобраться с тем, кто у ворот»: тот, кто сидел на складе, мёртв (где бы ни был).
func _dock_check() -> void:
	var o := Quests.objective(qid)
	if String(o.get("type", "")) != "clear_site" or not _ai_spawned:
		return
	for m in _dock:
		if is_instance_valid(m) and m.state != Marauder.State.DEAD:
			return
	Quests.event("cleared", {"site": String(o.get("site", ""))})


## Контрольная точка (§7): группа вышла в зал одетой — сделанное до неё засчитано и после гибели, набор
## каждого снят (как взят из сумки), пакет — в рюкзаке у кого-то; дальше погибнуть всей группой — заново отсюда.
func _checkpoint() -> void:
	if _cp_taken or at_checkpoint():
		return
	var after := String(spec.get("checkpoint_after", ""))
	if after == "" or not _passed(after):
		return
	_cp_taken = true
	var done: Array = []
	for st in Quests.def(qid).get("stages", []):
		for ob: Dictionary in (st as Dictionary).get("objectives", []):
			done.append(String(ob.get("id", "")))
			if String(ob.get("id", "")) == after:
				break
		if done.has(after):
			break
	Quests.mark_durable(qid, done)
	var raid := Raid.current
	var kits: Dictionary = {}
	var packet := String(Balance.PROLOGUE.packet)
	var has_packet := false
	for peer in raid.participants:
		var pl := raid.player_of(int(peer))
		if pl == null or not pl.is_alive():
			continue
		var kit := {"equipment": pl.equipment_state(), "backpack": pl.inventory.items.duplicate(true)}
		for e: Dictionary in kit.backpack:
			has_packet = has_packet or String(e.get("id", "")) == packet
		kits[int(peer)] = kit
	# пакет оставили в подсобке — после гибели он всё равно в рюкзаке (у первого)
	if not has_packet and not kits.is_empty():
		var first: Dictionary = kits[kits.keys()[0]]
		ItemDb.add_to(first.backpack, ItemDb.make(packet, 1), ItemDb.bag_grid(first.equipment))
	for peer: int in kits:
		if not Net.is_networked() or peer == multiplayer.get_unique_id():
			_store_kit(kits[peer])
		elif peer in multiplayer.get_peers():
			_rpc_kit.rpc_id(peer, kits[peer])
	Profile.flags["prologue_cp"] = true
	Profile.save()
	Quests.set_flag("prologue_cp", true)
	print("prologue: контрольная точка у кофейни, наборов %d" % kits.size())


@rpc("authority", "call_remote", "reliable")
func _rpc_kit(kit: Dictionary) -> void:
	_store_kit(kit)


func _store_kit(kit: Dictionary) -> void:
	checkpoint_kit = kit.duplicate(true)
	if owns_profile():
		_own_flag("prologue_kit", checkpoint_kit.duplicate(true))


## Свой флаг профиля: сразу в профиль (переживёт гибель) и, у хоста, в копию рейда — иначе фиксация
## вынесенного (Quests._commit_host) перезапишет флаги профиля копией без него.
func _own_flag(name: String, value: Variant) -> void:
	if value == null:
		Profile.flags.erase(name)
	else:
		Profile.flags[name] = value
	Profile.save()
	if not Quests.is_client() and Quests.in_raid():
		Quests.set_flag(name, value)


## Цель oid уже позади (текущая — дальше по списку или квест пройден).
func _passed(oid: String) -> bool:
	if Quests.state(qid) == "COMPLETED":
		return true
	var i := 0
	var at := -1
	var cur := -1
	var s := Quests.qstate(qid)
	for si in range((Quests.def(qid).get("stages", []) as Array).size()):
		var st: Dictionary = Quests.def(qid).stages[si]
		for oi in range((st.get("objectives", []) as Array).size()):
			if String((st.objectives[oi] as Dictionary).get("id", "")) == oid:
				at = i
			if si == int(s.get("stage", 0)) and oi == int(s.get("obj", 0)):
				cur = i
			i += 1
	return at >= 0 and cur > at


## Где-то у «Вершины» глухо бьёт очередь — ЧВК, не к игроку (§4.7): звук далёких выстрелов у всех, без пуль.
func _burst() -> void:
	var b: Dictionary = (spec.get("radio", {}) as Dictionary).get("burst", {})
	if b.is_empty() or _said.has("burst") or String(Quests.objective(qid).get("id", "")) != String(b.get("objective", "")):
		return
	_said["burst"] = true
	var at: Array = b.get("at", [0, 0, 0])
	var pos := Vector3(float(at[0]), float(at[1]), float(at[2]))
	var sound := String(WeaponStats.compute(ItemDb.make(String(b.get("weapon", "")), 1)).get("sound", ""))
	if Net.is_networked():
		_rpc_burst.rpc(pos, sound, int(b.get("shots", 5)), float(b.get("every", 0.1)))
	_play_burst(pos, sound, int(b.get("shots", 5)), float(b.get("every", 0.1)))


@rpc("authority", "call_remote", "reliable")
func _rpc_burst(pos: Vector3, sound: String, shots: int, every: float) -> void:
	_play_burst(pos, sound, shots, every)


func _play_burst(pos: Vector3, sound: String, shots: int, every: float) -> void:
	if sound == "":
		return
	for i in range(shots):
		get_tree().create_timer(every * float(i)).timeout.connect(func() -> void: Audio.play(sound, pos))


func _say_once(id: String, lines: Array) -> void:
	if _said.has(id) or lines.is_empty():
		return
	_said[id] = true
	Quests.say(lines)


func _on_noise(pos: Vector3, _radius_m: float, kind: String) -> void:
	if not _is_host() or not kind.begins_with("shot"):
		return
	var sh: Dictionary = (spec.get("radio", {}) as Dictionary).get("shots", {})
	var b: Array = sh.get("box", [])
	if b.size() < 4 or String(Quests.objective(qid).get("id", "")) != String(sh.get("objective", "")):
		return
	if pos.x >= float(b[0]) and pos.z >= float(b[1]) and pos.x <= float(b[2]) and pos.z <= float(b[3]):
		_shots = true
		_say_once("shots", sh.get("lines", []))
		# третий на складе слышит бой в зале и идёт проверять (§4.5–4.6: встреча раньше и не на условиях игрока)
		for m in _dock:
			if is_instance_valid(m) and m.state == Marauder.State.PATROL:
				m.investigate_at.call_deferred(pos)


## Ворота кордона открыли огонь — Михалыч: «Я же сказал».
func _on_gate(stage: int) -> void:
	if stage >= 3 and _is_host():
		_say_once("cordon", ((spec.get("radio", {}) as Dictionary).get("cordon", {}) as Dictionary).get("lines", []))


# ---------------------------------------------------------------- у каждого: экран, гибель, итог

func _local(_delta: float) -> void:
	var raid := Raid.current
	var me: Player = raid.local_player() if raid else null
	if me == null:
		return
	# граната в руке — «гранаты побереги» (себе)
	if me.grenade_in_hand and not _grenade_said:
		_grenade_said = true
		Quests.subtitles.emit(((spec.get("radio", {}) as Dictionary).get("grenade", {}) as Dictionary).get("lines", []))
	# свой игрок погиб: если группа пролог пройдёт — набор вернут в тайник (settle), если вынесет сам — нет
	if not me.is_alive() and not _died_noted and owns_profile():
		_died_noted = true
		_own_flag("prologue_died", true)
	if raid.is_extracted(me.peer_id) and Profile.flags.has("prologue_died") and owns_profile():
		_own_flag("prologue_died", null)
	if not (not me.is_alive() or raid.has_left(me.peer_id)):
		return
	if _group_lost():
		raid.summary_note = ""
		var from := "от кофейни" if at_checkpoint() else "от ворот"
		if Net.is_networked() and not multiplayer.is_server():
			raid.end_hint = "Погибла вся группа — ждём хоста: пролог заново %s" % from
		else:
			raid.end_hint = ("Пробел — заново %s   ·   Enter — чат" if Net.is_networked() else "Enter — заново %s") % from
	elif not raid.extracted.is_empty():
		var ok: bool = Quests.flag("packet_delivered") == true
		raid.summary_note = "Пакет Михалычу — донесён" if ok else "Пакет Михалычу — не донесён"
		raid.summary_note_bad = not ok
		raid.end_hint = ""


## Рейд кончился, никто не вышел — вся группа погибла.
func _group_lost() -> bool:
	var raid := Raid.current
	return raid != null and raid.over and raid.extracted.is_empty()


## Рейд окончен, игрок жмёт «дальше»: погибла вся группа — пролог заново (хост; гость ждёт хоста); true —
## решено здесь. Кто-то вышел — false: в убежище, как после любого рейда.
func after_end() -> bool:
	if not _group_lost():
		return false
	if Net.is_networked() and not multiplayer.is_server():
		return true
	restart()
	return true


func restart() -> void:
	var cond: Dictionary = (Balance.PROLOGUE.conditions as Dictionary).duplicate()
	Profile.next_conditions = cond.duplicate()
	Profile.pending_raid = true
	if Net.is_networked():
		Net.start_level.rpc(String(Balance.PROLOGUE.scene), cond)
	else:
		Net.change_scene(String(Balance.PROLOGUE.scene), "Первый выход — заново")


# ---------------------------------------------------------------- вступительный экран (§3)

## «Закрытый район»: один экран, кнопка «Начать», без автозакрытия; в коопе — у каждого свой. Только в
## самом начале пролога (не после гибели).
func _show_intro() -> void:
	var intro: Dictionary = spec.get("intro", {})
	if intro.is_empty() or intro_seen or at_checkpoint() or bool(Profile.flags.get("prologue_intro", false)):
		return
	if int(Quests.qstate(qid).get("stage", 0)) != 0 or int(Quests.qstate(qid).get("obj", 0)) != 0:
		return
	_intro = IntroScreen.new()
	_intro.name = "Intro"
	(_intro as IntroScreen).setup(String(intro.get("title", "")), intro.get("text", []), func() -> void:
		intro_seen = true
		if owns_profile():
			Profile.flags["prologue_intro"] = true
			Profile.save())
	add_child(_intro)


## Экран вводной: текст на тёмном, кнопка «Начать»; пока открыт — персонаж стоит (группа esc_windows).
class IntroScreen:
	extends CanvasLayer

	var _done: Callable
	var _title: String = ""
	var _text: Array = []

	func setup(title: String, text: Array, done: Callable) -> void:
		_title = title
		_text = text
		_done = done

	func is_open() -> bool:
		return visible

	func _ready() -> void:
		layer = 30
		add_to_group("esc_windows")
		var bg := ColorRect.new()
		bg.color = Color(0.02, 0.022, 0.026, 0.97)
		bg.set_anchors_preset(Control.PRESET_FULL_RECT)
		add_child(bg)
		var box := VBoxContainer.new()
		box.set_anchors_preset(Control.PRESET_CENTER)
		box.offset_left = -430
		box.offset_right = 430
		box.offset_top = -330
		box.offset_bottom = 330
		box.add_theme_constant_override("separation", 14)
		add_child(box)
		var t := Label.new()
		t.text = _title
		t.add_theme_font_size_override("font_size", 34)
		t.add_theme_color_override("font_color", Color(1.0, 0.84, 0.58))
		box.add_child(t)
		for para in _text:
			var l := Label.new()
			l.text = String(para)
			l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			l.add_theme_font_size_override("font_size", 17)
			l.add_theme_color_override("font_color", Color(0.9, 0.89, 0.85))
			box.add_child(l)
		var start := Button.new()
		start.text = "Начать"
		start.focus_mode = Control.FOCUS_NONE
		start.custom_minimum_size = Vector2(200, 44)
		start.add_theme_font_size_override("font_size", 20)
		start.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
		start.pressed.connect(close)
		box.add_child(start)

	func close() -> void:
		visible = false
		if _done.is_valid():
			_done.call()
