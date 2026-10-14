class_name RaidContacts
extends Node
## Счётчик стычек рейда (Balance.RAID_CONTACTS): сколько их, сколько врагов в каждой, какие тяжёлые,
## паузы между ними — в лог по окончании рейда, чтобы метрики населения (enemy_population.md §2)
## снимались с плейтеста, а не на глаз. Считает хост по тому, что делают боты (Marauder.player_contact_ms:
## видит игрока или стреляет по нему); на игру не влияет.

static var current: RaidContacts

## Закрытые стычки: {start, end — с от начала рейда; enemies — сколько врагов; heavy; why — почему тяжёлая}.
var contacts: Array[Dictionary] = []
var _open: Dictionary = {}
var _start_ms: int = 0
var _tick: float = 0.0
var _reported: bool = false


func _enter_tree() -> void:
	current = self


func _exit_tree() -> void:
	report()
	if current == self:
		current = null


func _ready() -> void:
	_start_ms = Time.get_ticks_msec()


func _is_host() -> bool:
	return not Net.is_networked() or multiplayer.is_server()


func _process(delta: float) -> void:
	if not _is_host() or _reported:
		return
	_tick -= delta
	if _tick > 0.0:
		return
	_tick = float(Balance.RAID_CONTACTS.tick_sec)
	tick()
	if Raid.current and Raid.current.over:
		report()


## Один шаг: кто сейчас в стычке с игроками; открыть, дополнить или закрыть стычку.
func tick() -> void:
	var cfg: Dictionary = Balance.RAID_CONTACTS
	var now := Time.get_ticks_msec()
	var hold := int(float(cfg.hold_sec) * 1000.0)
	var active: Array[Marauder] = []
	for n in get_tree().get_nodes_in_group("marauders"):
		var m := n as Marauder
		if m and m.state != Marauder.State.DEAD and m.player_contact_ms > 0 and now - m.player_contact_ms <= hold:
			active.append(m)
	if active.is_empty():
		if not _open.is_empty():
			_track_players()
			if now - int(_open.last) > int(float(cfg.calm_sec) * 1000.0):
				_close()
		return
	if _open.is_empty():
		_open = {"start": now, "last": now, "enemies": {}, "factions": {}, "hp_start": {}, "hp_min": {}, "downed": false}
	_open.last = now
	for m in active:
		(_open.enemies as Dictionary)[m.get_instance_id()] = true
		(_open.factions as Dictionary)[m.faction] = true
	_track_players()


## Здоровье игроков за стычку: с чего начали, до скольких упало, падал ли кто.
func _track_players() -> void:
	for n in get_tree().get_nodes_in_group("players"):
		var p := n as Player
		if p == null or p.health == null or p.health.max_hp <= 0.0:
			continue
		var share := p.health.hp / p.health.max_hp
		var hs: Dictionary = _open.hp_start
		var hm: Dictionary = _open.hp_min
		if not hs.has(p.peer_id):
			hs[p.peer_id] = share
		hm[p.peer_id] = minf(float(hm.get(p.peer_id, share)), share)
		if p.is_downed() or not p.is_alive():
			_open.downed = true


func _close() -> void:
	var cfg: Dictionary = Balance.RAID_CONTACTS
	var n := (_open.enemies as Dictionary).size()
	var why := ""
	if n >= int(cfg.heavy_enemies):
		why = "врагов %d" % n
	elif (_open.factions as Dictionary).has("rival") or (_open.factions as Dictionary).has("pmc"):
		why = "чужой отряд" if (_open.factions as Dictionary).has("rival") else "ЧВК"
	elif bool(_open.downed):
		why = "игрок упал"
	else:
		for id in _open.hp_start:
			if float(_open.hp_start[id]) - float((_open.hp_min as Dictionary).get(id, 1.0)) >= float(cfg.heavy_hp):
				why = "ранение"
				break
	contacts.append({"start": float(int(_open.start) - _start_ms) / 1000.0, "end": float(int(_open.last) - _start_ms) / 1000.0,
		"enemies": n, "heavy": why != "", "why": why})
	_open = {}


## Итог по стычкам: сколько, тяжёлых, врагов в каждой, паузы между ними (с), длительность рейда (мин).
func summary() -> Dictionary:
	var sizes: Array[int] = []
	var gaps: Array[int] = []
	var heavy := 0
	for i in range(contacts.size()):
		var c: Dictionary = contacts[i]
		sizes.append(int(c.enemies))
		if bool(c.heavy):
			heavy += 1
		if i > 0:
			gaps.append(int(float(c.start) - float(contacts[i - 1].end)))
	return {"count": contacts.size(), "heavy": heavy, "sizes": sizes, "gaps": gaps,
		"minutes": snappedf(float(Time.get_ticks_msec() - _start_ms) / 60000.0, 0.1)}


## Закрыть идущую стычку и напечатать итог (один раз за рейд).
func report() -> void:
	if _reported or not _is_host():
		return
	_reported = true
	if not _open.is_empty():
		_close()
	var s := summary()
	var party := AIPopulation.party_size()
	print("contacts: рейд %.1f мин, игроков %d — стычек %d (тяжёлых %d), врагов в стычке %s, паузы %s с" % [
		float(s.minutes), party, int(s.count), int(s.heavy), s.sizes, s.gaps])
	for c in contacts:
		print("contacts:   %d–%d с, врагов %d%s" % [int(c.start), int(c.end), int(c.enemies), (" — тяжёлая: " + String(c.why)) if bool(c.heavy) else ""])
