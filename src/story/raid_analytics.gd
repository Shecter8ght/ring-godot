class_name RaidAnalytics
extends Node
## Хроника рейда, шаг 1: что было со СВОИМ игроком за рейд. У каждого peer — своя (создаёт Raid,
## узел «Analytics»). Сама следит за игроком (оружие в руках, здоровье, ранения, у выхода ли);
## остальное ей сообщают: свои выстрелы — Player, убийства, попадания по тебе и причину смерти —
## хост через Raid (story_*), лечение и задания — рейд. Итог — RaidSummary.from(self).
## Только факты: рассказ строится из них и не выдумывает того, чего не было.

## Рейд начался (свой игрок появился и получил снаряжение), с — Time.
var started_ms: int = -1
var ended_ms: int = -1
## Снаряжение на входе: оружие (id), стоимость всего взятого, стоимость рюкзака.
var start_weapons: Array[String] = []
var start_kit_value: int = 0
var start_pack_value: int = 0
var loadout: bool = false
## Оружие в руках по ходу: сколько раз меняли, чем пользовались.
var weapons_used: Array[String] = []
var weapon_switches: int = 0
## Убийства: [{t, arch, faction, weapon, grenade, leader}] — t в секундах от начала.
var kills: Array = []
## Выстрелы, попадания по людям.
var shots: int = 0
var hits: int = 0
## Урон по мародёрам (засчитал хост).
var damage_dealt: float = 0.0
## Урон по тебе: сколько, попаданий, от своих (кооп).
var damage_taken: float = 0.0
var hits_taken: int = 0
var friendly_hits: int = 0
## Критические моменты: ложился раненым, здоровье ниже четверти; самое низкое здоровье (доля).
var downs: int = 0
var low_hp_moments: int = 0
var min_hp_frac: float = 1.0
var heals: Array[String] = []
## Мир: мародёры подорвали себя / своих гранатой (видели все игроки).
var enemy_self_grenades: int = 0
var enemy_ally_grenades: int = 0
## У точки эвакуации провёл, с.
var near_extract_sec: float = 0.0
## Итог: "extract" / "death" / "stranded" (не успел к эвакуации группы) / "" (ещё в рейде).
var outcome: String = ""
var extract_name: String = ""
## Смерть: {cause, arch, faction, weapon, attacker} от хоста; где умер; далеко ли выход.
var death: Dictionary = {}
var death_pos: Vector3 = Vector3.ZERO
var death_extract_dist: float = INF
## Задания: выполненные за рейд (id) и что осталось.
var missions_before: Dictionary = {}
## Что в конце: оружие у тебя, найденное в рейде, стоимость вынесенного.
var end_weapons: Array[String] = []
var end_value: int = 0
var found_value: int = 0
var found_items: int = 0
var best_find: Dictionary = {}
var missions_done: Array[String] = []
var missions_left: Array[String] = []

var _last_weapon: String = ""
var _was_downed: bool = false
var _low: bool = false
var _alive: bool = true


func _process(delta: float) -> void:
	var me := Raid.current.local_player() if Raid.current else null
	if me == null or outcome != "":
		return
	if started_ms < 0:
		# снаряжение из профиля выдаёт хост — ждём его; песочница — пока в руках не появится ствол
		if me.loadout_mode and not me.inventory.loadout_ready:
			return
		if not me.loadout_mode and me.weapon_id == "":
			return
		_begin(me)
	var w := me.weapon_id
	if w != _last_weapon:
		if _last_weapon != "" and w != "":
			weapon_switches += 1
		if w != "" and not w in weapons_used:
			weapons_used.append(w)
		_last_weapon = w
	var h := me.health
	if h.alive:
		var frac := h.hp / maxf(h.max_hp, 1.0)
		min_hp_frac = minf(min_hp_frac, 0.0 if h.downed else frac)
		var low := h.downed or frac < float(Balance.RAID_STORY.low_hp)
		if low and not _low:
			low_hp_moments += 1
		_low = low
		if h.downed and not _was_downed:
			downs += 1
		_was_downed = h.downed
		if _near_extract(me.global_position) <= 0.0:
			near_extract_sec += delta


func _begin(me: Player) -> void:
	started_ms = Time.get_ticks_msec()
	loadout = me.loadout_mode
	for slot in ItemDb.WEAPON_SLOTS:
		var e: Dictionary = me.inventory.equipment.get(slot, {})
		if WeaponDb.is_weapon(String(e.get("id", ""))):
			start_weapons.append(String(e.id))
	if start_weapons.is_empty() and me.weapon_id != "":
		start_weapons.append(me.weapon_id)
	start_kit_value = me.inventory.value()
	start_pack_value = ItemDb.value_of(me.inventory.items)
	missions_before = Profile.missions_active.duplicate()


## Секунды от начала рейда.
func now() -> float:
	return float(Time.get_ticks_msec() - started_ms) / 1000.0 if started_ms >= 0 else 0.0


## Сколько до ближайшей точки эвакуации за её радиусом, м (≤ 0 — внутри).
func _near_extract(p: Vector3) -> float:
	var best := INF
	for n in get_tree().get_nodes_in_group("extractions"):
		var ep := n as ExtractionPoint
		if ep:
			best = minf(best, Vector2(p.x - ep.global_position.x, p.z - ep.global_position.z).length() - ep.radius)
	return best


# ---------------------------------------------------------------- сообщают снаружи

## Свой выстрел (Player._fire): попал ли в человека.
func on_shot(hit_person: bool) -> void:
	if outcome != "":
		return
	shots += 1
	if hit_person:
		hits += 1


## Хост засчитал тебе убийство: кого (arch, faction), гранатой ли; чем — что было в руках.
func on_kill(arch: String, info: Dictionary) -> void:
	if outcome != "":
		return
	var me := Raid.current.local_player() if Raid.current else null
	kills.append({"t": now(), "arch": arch, "faction": String(info.get("faction", "marauder")),
		"weapon": me.weapon_id if me else "", "grenade": bool(info.get("grenade", false)),
		"leader": bool(info.get("leader", false))})


## Хост: ты ранил мародёра.
func on_dealt(amount: float) -> void:
	if outcome == "":
		damage_dealt += amount


## Хост: по тебе попали — сколько и кто (attacker — peer игрока, 0 — ИИ; src — чем).
func on_hit(amount: float, attacker: int, src: Dictionary) -> void:
	if outcome != "":
		return
	damage_taken += amount
	hits_taken += 1
	var me := Raid.current.local_player() if Raid.current else null
	if attacker > 0 and me and attacker != me.peer_id and String(src.get("kind", "")) != "ai":
		friendly_hits += 1


func on_heal(id: String) -> void:
	heals.append(id)


## Всё, что видели все: «enemy_self_grenade» — мародёр подорвал себя или своего.
func on_world(kind: String, data: Dictionary) -> void:
	if kind == "enemy_self_grenade":
		if bool(data.get("self", false)):
			enemy_self_grenades += 1
		else:
			enemy_ally_grenades += 1


## Хост: ты погиб — причина ({cause, arch, faction, weapon, attacker}).
func on_death(cause: Dictionary) -> void:
	if outcome != "":
		return
	death = cause
	var me := Raid.current.local_player() if Raid.current else null
	if me:
		death_pos = me.global_position
		death_extract_dist = maxf(0.0, _near_extract(death_pos))
	_finish("death", me)


## Не успел к эвакуации: группа ушла через точку name, взятое потеряно.
func on_stranded(name: String) -> void:
	if outcome != "":
		return
	extract_name = name
	_finish("stranded", Raid.current.local_player() if Raid.current else null)


func on_extracted(name: String) -> void:
	if outcome != "":
		return
	extract_name = name
	_finish("extract", Raid.current.local_player() if Raid.current else null)


func _finish(how: String, me: Player) -> void:
	outcome = how
	ended_ms = Time.get_ticks_msec()
	if started_ms < 0:
		started_ms = ended_ms
	if me == null:
		return
	for slot in ItemDb.WEAPON_SLOTS:
		var e: Dictionary = me.inventory.equipment.get(slot, {})
		if WeaponDb.is_weapon(String(e.get("id", ""))):
			end_weapons.append(String(e.id))
	for it in me.inventory.items:
		if WeaponDb.is_weapon(String(it.id)):
			end_weapons.append(String(it.id))
		# найденное в рейде (метка «из рейда»): сколько стоит, самое дорогое
		if bool((it as Dictionary).get("fir", false)):
			var v := ItemDb.entry_value(it)
			found_value += v
			found_items += 1
			if v > int(best_find.get("value", 0)):
				best_find = {"id": String(it.id), "value": v}
	end_value = me.inventory.value()
	for id in missions_before:
		if Missions.done(String(id)) and not (int(missions_before[id]) >= Missions.goal(Missions.find(String(id)))):
			missions_done.append(String(id))
		elif not Missions.done(String(id)):
			missions_left.append(String(id))
