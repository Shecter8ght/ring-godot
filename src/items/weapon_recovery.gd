class_name WeaponRecovery
extends Node
## Журнал мира хоста: потеря фиксируется после исхода рейда, вынос закрывает запись сразу.
## UUID переживает обвесы и смену владельца; peer_id нужен только для текущего рейда.

var raid: Raid
var owners: Dictionary = {}
var journal: Dictionary = {}
var _elapsed: float = 0.0
var _finished: bool = false
var _attempted: Dictionary = {}


func _ready() -> void:
	if Quests.is_client():
		set_process(false)
		return
	Profile.ensure()
	journal = Profile.weapon_world.duplicate(true)
	journal.get_or_add("lost", {})
	journal.get_or_add("pending", {})
	# Незавершённый рейд после аварии: уже выданный врагу ствол не получает новое окно.
	settle(journal)
	_commit()


static func settle(book: Dictionary) -> void:
	var lost: Dictionary = book.get_or_add("lost", {})
	for uid: String in book.get("pending", {}):
		var row: Dictionary = book.pending[uid]
		if not bool(row.get("returning", false)):
			var result: Dictionary = row.duplicate(true)
			result["remaining"] = int(Balance.WEAPON_RECOVERY.raids)
			lost[uid] = result
	book["pending"] = {}


static func eligible(book: Dictionary, owner: String, zone: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for uid: String in book.get("lost", {}):
		var row: Dictionary = book.lost[uid]
		if String(row.owner) == owner and String(row.zone) == zone and int(row.remaining) > 0:
			out.append(row)
	return out


func register_owner(peer: int, owner: String) -> void:
	if owner == "" or Quests.is_client():
		return
	owners[peer] = owner
	_scan()
	_commit()
	_attempt.call_deferred(owner)


func _zone() -> String:
	return raid.quest_world.level if raid != null and raid.quest_world != null else ""


func _attempt(owner: String) -> void:
	if not is_inside_tree() or _zone() == "" or _attempted.has(owner):
		return
	var candidates: Array[Dictionary] = eligible(journal, owner, _zone())
	if candidates.is_empty():
		_attempted[owner] = true
		return
	var all_enemies: Array[Node] = get_tree().get_nodes_in_group("marauders")
	var spawned: Variant = raid.get_parent().get("_marauders_spawned")
	# Навигация ещё печётся: рейд не тратит окно до появления обычного населения.
	if all_enemies.is_empty() and (spawned == null or int(spawned) == 0):
		return
	var enemies: Array[Marauder] = []
	for node: Node in all_enemies:
		var enemy: Marauder = node as Marauder
		if enemy != null and enemy.state != Marauder.State.DEAD and enemy._health.alive and enemy.recovered_weapon.is_empty() and enemy.faction in ["marauder", "pmc"]:
			enemies.append(enemy)
	_attempted[owner] = true
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.randomize()
	var before: Dictionary = journal.duplicate(true)
	var chosen: Dictionary = draw(journal, owner, _zone(), rng)
	if enemies.is_empty() and not chosen.is_empty():
		# Уже перебили всех / заняли подходящих NPC: попытка состоялась, выдавать некому.
		journal.pending.erase(String(chosen.weapon.uid))
	# Решение сохраняется до выдачи оружия. Перезапуск не позволяет перебросить шанс.
	if not _commit():
		journal = before
		Profile.weapon_world = before.duplicate(true)
		_attempted.erase(owner)
		return
	if chosen.is_empty() or enemies.is_empty():
		return
	var enemy: Marauder = enemies[rng.randi_range(0, enemies.size() - 1)]
	enemy.recovered_weapon = chosen.weapon.duplicate(true)


static func draw(book: Dictionary, owner: String, zone: String, rng: RandomNumberGenerator) -> Dictionary:
	# Один возвращённый ствол на владельца за рейд. Окно остальных тоже стареет.
	var chosen: Dictionary = {}
	for row: Dictionary in eligible(book, owner, zone):
		row.remaining = int(row.remaining) - 1
		if chosen.is_empty() and rng.randf() < float(Balance.WEAPON_RECOVERY.chance):
			chosen = row
	if not chosen.is_empty():
		var uid: String = String(chosen.weapon.uid)
		var pending: Dictionary = chosen.duplicate(true)
		pending["returning"] = true
		book.pending[uid] = pending
	for uid: String in book.lost.keys():
		if int(book.lost[uid].remaining) <= 0:
			book.lost.erase(uid)
	return chosen


func _remember(entry: Dictionary, owner: String = "") -> void:
	if (entry.get("engraving", {}) as Dictionary).is_empty():
		return
	var uid: String = String(entry.get("uid", ""))
	if uid == "":
		return
	var row: Dictionary = journal.pending.get(uid, {})
	if row.is_empty():
		if owner == "":
			return
		row = {"owner": owner, "zone": _zone(), "returning": false}
		# Реальный вход со стволом отменяет прежнюю запись потери того же экземпляра.
		journal.lost.erase(uid)
	var copy: Dictionary = entry.duplicate(true)
	for transient: String in ["x", "y", "r", "rev", "_equip_generation"]:
		copy.erase(transient)
	row["weapon"] = copy
	journal.pending[uid] = row


func _scan() -> void:
	if raid == null:
		return
	for peer: int in owners:
		if raid.is_extracted(peer):
			continue
		var pl: Player = raid.player_of(peer)
		if pl == null or pl.inventory == null:
			continue
		for entry: Dictionary in pl.equipment_state().values() + pl.inventory.items + pl.inventory.buffer:
			_remember(entry, String(owners[peer]))
		# Защищённый карман возвращается даже при смерти. Перекладывание туда — спасение.
		for entry: Dictionary in pl.inventory.pocket:
			var uid: String = String(entry.get("uid", ""))
			journal.pending.erase(uid)
			journal.lost.erase(uid)
	for enemy: Node in get_tree().get_nodes_in_group("marauders"):
		var npc: Marauder = enemy as Marauder
		# Мёртвый NPC хранит старую equipment: настоящий экземпляр уже в ящике или у игрока.
		if npc == null or npc.state == Marauder.State.DEAD:
			continue
		for entry: Dictionary in npc.equipment.values() + npc.pack:
			if journal.pending.has(String(entry.get("uid", ""))):
				_remember(entry)
	for box: Node in get_tree().get_nodes_in_group("loot_containers"):
		for entry: Dictionary in (box as LootContainer).items:
			if journal.pending.has(String(entry.get("uid", ""))):
				_remember(entry)


func escaped(entries: Array) -> void:
	if Quests.is_client():
		return
	for entry: Dictionary in entries:
		var uid: String = String(entry.get("uid", ""))
		journal.pending.erase(uid)
		journal.lost.erase(uid)
	_commit()


func finish() -> void:
	if _finished or Quests.is_client():
		return
	_finished = true
	_scan()
	settle(journal)
	_commit()


func _exit_tree() -> void:
	finish()


func _process(delta: float) -> void:
	if _finished:
		return
	_elapsed += delta
	if _elapsed >= float(Balance.WEAPON_RECOVERY.checkpoint_sec):
		_elapsed = 0.0
		_scan()
		_commit()
		for peer: int in owners:
			if raid != null and raid.player_of(peer) != null:
				_attempt(String(owners[peer]))


func _commit() -> bool:
	Profile.weapon_world = journal.duplicate(true)
	return Profile.save()
