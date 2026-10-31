class_name QuestCoach
extends Node
## Обучение по ходу дела (docs/design/prologue.md §1, §9.4–9.5): следит за своим игроком — что он сейчас
## делает (бег, присед, наклон, перелез, оружие в слоте и в руках, броня, проверка магазина, перезарядка,
## прицел, выстрел, фонарь, граната, рюкзак, обыск, карта) — и сообщает факты квестам: цель action
## засчитывается и заранее (сделал раньше подсказки — повторять не нужно; действие любого — всей группе).
## Подсказка — одна строка с клавишей из текущих привязок («{reload}» в тексте): у текущей цели (coach)
## или из списка этапа (stage.coach: рядом с точкой, при условии when), пока своё действие не сделано;
## гаснет по факту. Личная — у каждого игрока своя. Создаёт QuestWorld (рейд и убежище).
##
## Пункт stage.coach: {what — действие, которое гасит подсказку насовсем ("" — нет), fresh — действие, которое
## гасит её, если сделано на этом этапе (присесть за газоном, хоть и приседал раньше), after — показывать только
## после этого действия на этапе (перезарядка — после первых выстрелов), text, at — [x, z] и r — только рядом
## с точкой, when — условие (см. _when)}.

## Сделанное своим игроком (личное): what -> true.
var done: Dictionary = {}
## Когда действие было в последний раз, мс: what -> ticks.
var last: Dictionary = {}
## Сейчас показанная строка (тесты).
var shown: String = ""
var _poll: float = 0.0
var _stage_key: String = ""
var _stage_since: int = 0


func _process(delta: float) -> void:
	_poll -= delta
	if _poll > 0.0:
		return
	_poll = 0.1
	var me := _me()
	if me == null or not me.is_inside_tree():
		_show("")
		return
	var now := Time.get_ticks_msec()
	for what: String in happening(me):
		last[what] = now
		if not done.has(what):
			done[what] = true
		# цель ждёт действие — сообщить (в т. ч. повторно: в новом рейде факты свои)
		if Quests.wants_action(what):
			Quests.action_seen(what)
	var qid := Quests.tracked()
	var key := "%s:%d" % [qid, int(Quests.qstate(qid).get("stage", 0))]
	if key != _stage_key:
		_stage_key = key
		_stage_since = now
	_show(_hint(me))


## Что свой игрок делает прямо сейчас (имена действий целей action и подсказок).
func happening(p: Player) -> Array[String]:
	var out: Array[String] = []
	if not p.is_alive():
		return out
	var flat := Vector2(p.velocity.x, p.velocity.z).length()
	if flat > 0.4:
		out.append("move")
	if p.stance == Player.Stance.STAND and p.sprint_held() and flat > Balance.PLAYER_WALK_SPEED + 0.3:
		out.append("sprint")
	if p.stance == Player.Stance.CROUCH:
		out.append("crouch")
	if absf(p.lean) > 0.3:
		out.append("lean")
	if p.is_vaulting():
		out.append("vault")
	var eq: Dictionary = p.inventory.equipment if p.inventory else {}
	if eq.get("primary") is Dictionary:
		out.append("equip_weapon")
	if eq.get("armor") is Dictionary and eq.get("helmet") is Dictionary:
		out.append("wear_armor")
	if p.weapon_id != "" and not p.hands_free():
		out.append("weapon_ready")
	if p.ammo_check_t > 0.0 and p.ammo_check_text != "" and p.reload_timer <= 0.0:
		out.append("check_mag")
	if p.reload_timer > 0.0:
		out.append("reload")
	# прицел — ПКМ (aiming); ads — лишь вид из глаз, он включён и без прицела
	if p.aiming:
		out.append("aim")
	if Time.get_ticks_msec() - p.last_shot_ms < 400:
		out.append("fire")
	if p.light_on:
		out.append("light")
	if p.grenade_in_hand:
		out.append("grenade")
	var raid := Raid.current
	if raid and raid.ui:
		if raid.ui.is_open():
			out.append("inventory")
		var c: LootContainer = raid.ui.looting()
		if c != null:
			out.append("loot")
			if c.display_name.begins_with(String(Balance.PROLOGUE.bag_name) + " · "):
				out.append("search_bag")
	var map := _map()
	if map and map.is_open():
		out.append("map")
	return out


## Строка подсказки сейчас: срочное на любом этапе (coach_urgent квеста: упал напарник, лежишь, ранен, граната
## в руке), иначе текущая цель отслеживаемого квеста (coach), иначе пункты её этапа.
func _hint(me: Player) -> String:
	if not me.is_alive():
		return ""
	var qid := Quests.tracked()
	if qid == "":
		return ""
	for item: Dictionary in Quests.def(qid).get("coach_urgent", []):
		if _fits(me, item):
			return String(item.get("text", ""))
	var o := Quests.objective(qid)
	var text := String(o.get("coach", ""))
	var what := String(o.get("what", "")) if String(o.get("type", "")) == "action" else ""
	if text != "" and not done.has(what):
		return text
	for item: Dictionary in Quests.stage(qid).get("coach", []):
		if _fits(me, item):
			return String(item.get("text", ""))
	return ""


func _fits(me: Player, item: Dictionary) -> bool:
	var what := String(item.get("what", ""))
	if what != "" and done.has(what):
		return false
	var fresh := String(item.get("fresh", ""))
	if fresh != "" and int(last.get(fresh, -1)) >= _stage_since:
		return false
	var after := String(item.get("after", ""))
	if after != "" and int(last.get(after, -1)) < _stage_since:
		return false
	var at: Array = item.get("at", [])
	if at.size() == 2 and Vector2(me.global_position.x - float(at[0]), me.global_position.z - float(at[1])).length() > float(item.get("r", 8.0)):
		return false
	return _when(me, String(item.get("when", "")))


## Условия подсказок этапа: dark — темно вокруг, hurt — ранен (стоя), downed — лежит, grenade — граната в
## руке, mate_down — рядом лежит раненый напарник, door_closed — рядом закрытая дверь, looting — открыт
## ящик или тело, armed — оружие в руках.
func _when(me: Player, cond: String) -> bool:
	match cond:
		"":
			return true
		"dark":
			return RaidAtmosphere.current != null and RaidAtmosphere.current.is_dark(me.global_position)
		"hurt":
			return not me.is_downed() and me.health.hp < me.health.max_hp * 0.95
		"downed":
			return me.is_downed()
		"grenade":
			return me.grenade_in_hand
		"mate_down":
			return Raid.current != null and Raid.current.downed_mate_near(me) != null
		"door_closed":
			for n in get_tree().get_nodes_in_group("doors"):
				var d := n as Door
				if d and not d.is_open and d.global_position.distance_to(me.global_position) < 4.0:
					return true
			return false
		"looting":
			return Raid.current != null and Raid.current.ui != null and Raid.current.ui.looting() != null
		"armed":
			return me.weapon_id != "" and not me.hands_free()
	return false


func _show(text: String) -> void:
	if text == shown:
		return
	shown = text
	if Quests.hud:
		Quests.hud.coach(text)


func _me() -> Player:
	if Raid.current:
		return Raid.current.local_player()
	return get_tree().get_first_node_in_group("players") as Player


func _map() -> MapView:
	var lvl: Node = Raid.current.get_parent() if Raid.current else null
	return lvl.get_node_or_null("Map") as MapView if lvl else null


func _exit_tree() -> void:
	if Quests.hud:
		Quests.hud.coach("")
