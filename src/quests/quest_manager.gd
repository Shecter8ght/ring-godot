extends Node
## Сюжетные квесты. Autoload `Quests`. Описание — data/quests/<id>.json (список — index.json):
## этапы (stages), цели по порядку (objectives), диалоги, места в мире (sites), награда, флаги.
## Здесь нет ни одного конкретного квеста — только общие правила:
##
## Состояние квеста — в профиле (Profile.quests: id -> {state, stage, obj, clues, count}),
## флаги мира — Profile.flags. Квест: LOCKED (не выполнены requires) → AVAILABLE (можно взять у
## того, кто даёт) → ACTIVE → COMPLETED (или FAILED). Статус текущей цели — status():
## OBJECTIVE / WAITING_FOR_EXTRACTION (найдено — теперь уйти живым) / RETURN_TO_NPC (поговорить).
##
## Рейд: всё, что сделано в рейде, живёт в копии (_live) и попадает в профиль только при
## эвакуации; погиб или ушёл в убежище без эвакуации — копия выбрасывается, этап повторяется в
## следующем рейде (улика снова лежит на месте, раненый NPC снова ждёт).
##
## Мир сообщает события — event(тип, параметры); цель засчитывается, если совпала:
##   talk {npc, dialogue}    — разговор в убежище (talk)
##   site {site}             — место: осмотрел / обыскал / вошёл в зону (interact, find_clue,
##                              search_location, enter_zone)
##   have_item {item}        — предмет в рюкзаке (pickup_item)
##   extracted {items, npcs} — эвакуация (reach_extraction, extract_with_item, extract_with_npc, survive)
##   kill {arch}             — добил мародёра (kill_targets, n штук, arch — тип или пусто)
##   hand_in {item}          — сдал предметы через терминал (контракт «Под заказ», hand_in)
##
## Реплики: в диалогах [кто, текст], кто = "player" — герой (подпись «Я», свой цвет); в lines
## мест и say / say_start целей — строка (описание) или [кто, текст]. say — цель выполнена,
## say_start — цель стала текущей: герой говорит сам, без этого квест «немой».
##
## Группа (кооп на 1–3, docs/design/new_game_intro.md §11): одно состояние сюжета на группу — у
## хоста; соло — группа из одного. Клиент ничего не засчитывает сам: просит хост (осмотр места,
## разговор, поднять/положить раненого), хост проверяет (кто, где, текущая ли цель) и рассылает
## снимок состояния всем (и подключившимся позже). Убийства, «предмет в рюкзаке» и эвакуацию хост
## считает сам за любого участника. Сделанное в рейде засчитывается всем, если хоть один из группы
## эвакуировался (_delivered); не вынес никто — попытка не в счёт. Награда за квест — один раз на
## профиль (отметка rewarded). Группа идёт по кампании хоста: у гостя она хранится отдельно от
## своей (Profile.guest_campaigns) и не смешивается с ней.

signal changed
## Короткое сообщение на экране («Найдена улика», «Задание обновлено»).
signal notice(text: String)
## Реплики на экране (осмотр места, раненый NPC) — сами по очереди.
signal subtitles(lines: Array)

const INDEX := "res://data/quests/index.json"

var _defs: Dictionary = {}
var _order: Array[String] = []
## Квесты-экземпляры контрактов терминала (Contracts) — добавлены поверх сюжетных.
var _extra_ids: Array[String] = []
## В рейде (хост и соло): копия состояния {quests, flags}; вне рейда пусто.
var _live: Dictionary = {}
## Рейд: кто-то из группы эвакуировался — сделанное засчитано всем (хост).
var _delivered: bool = false
## Раненые NPC мест (хост решает, все знают): site -> peer, кто несёт (0 — никто); где положили:
## site -> [x, y, z].
var _carry: Dictionary = {}
var _npc_pos: Dictionary = {}
## Клиент: последний снимок от хоста {campaign, quests, flags, raid, delivered, carry, npc_pos,
## trust_level}; не в сети — пусто.
var _remote: Dictionary = {}
var _cargo_claims: Dictionary = {}


func campaign_modules() -> Dictionary:
	if Settings.unlocked():
		return Upgrades.max_levels()
	return _remote.get("modules", {}) if is_client() else Profile.modules


func modules_changed() -> void:
	_broadcast()
	changed.emit()


## Гость: хост включил чит «открыть всё» — он действует на всю группу (Settings.unlocked).
func host_unlock() -> bool:
	return is_client() and bool(_remote.get("unlock_all", false))


func cargo_claimed(sid: String) -> bool:
	return bool((_remote.get("cargo_claims", {}) if is_client() else _cargo_claims).get(sid, false))


## Совместимый узел из обычного ящика тоже годится. Купленные / незавершённые головки — нет.
func cargo_site_for(entry: Dictionary) -> String:
	if not bool(entry.get("fir", false)) or int(entry.get("n", 0)) < 1:
		return ""
	for qid: String in _order:
		var o: Dictionary = objective(qid)
		if state(qid) != "ACTIVE" or String(o.get("type", "")) != "extract_cargo" or String(o.get("item", "")) != String(entry.get("id", "")):
			continue
		if String(entry.id) == "laser_head" and int(entry.get("charges", 0)) != int(Balance.ENGRAVING.charges):
			continue
		return String(o.site)
	return ""

## Мир уровня (места, раненые) — регистрируется сам; хост сверяет по нему, рядом ли просящий.
var world: QuestWorld
## Интерфейс: цель, сообщения, разговоры, журнал, консоль разработчика.
var hud: QuestHud


func _ready() -> void:
	_load_defs()
	hud = QuestHud.new()
	hud.name = "QuestHud"
	add_child(hud)
	# кто-то пришёл / ушёл в другую сцену — хост рассылает снимок (и новенькому)
	Net.scenes_changed.connect(func() -> void:
		if _is_host_net():
			_broadcast())


func _load_defs() -> void:
	_defs.clear()
	_order.clear()
	var idx: Variant = JSON.parse_string(FileAccess.get_file_as_string(INDEX)) if FileAccess.file_exists(INDEX) else null
	if not idx is Dictionary:
		return
	for qid in (idx as Dictionary).get("quests", []):
		var path := "res://data/quests/%s.json" % String(qid)
		var d: Variant = JSON.parse_string(FileAccess.get_file_as_string(path)) if FileAccess.file_exists(path) else null
		if d is Dictionary:
			_defs[String(qid)] = d
			_order.append(String(qid))


## Контракты терминала: заменить набор квестов-экземпляров (сюжетные не трогаются).
func set_extra(defs: Dictionary) -> void:
	for qid in _extra_ids:
		_defs.erase(qid)
		_order.erase(qid)
	_extra_ids.clear()
	for qid in defs:
		_defs[String(qid)] = defs[qid]
		_order.append(String(qid))
		_extra_ids.append(String(qid))
	_broadcast()
	changed.emit()


## Контракт снят (отказ): его состояние — прочь из профиля (или копии рейда).
func drop_extra(qid: String) -> void:
	if is_client() or not qid in _extra_ids:
		return
	_quests().erase(qid)
	_commit_if_home()


# ---------------------------------------------------------------- чтение

func ids() -> Array[String]:
	return _order


func def(qid: String) -> Dictionary:
	return _defs.get(qid, {})


func in_raid() -> bool:
	if is_client():
		return bool(_remote.get("raid", false))
	return not _live.is_empty()


## Клиент в сети: состояние — снимок хоста, засчитывает хост.
func is_client() -> bool:
	return Net.is_networked() and not multiplayer.is_server()


func _is_host_net() -> bool:
	return Net.is_networked() and multiplayer.is_server()


func _quests() -> Dictionary:
	if is_client():
		if not _remote.has("quests"):
			_remote["quests"] = {}
		return _remote.quests
	Profile.ensure()
	return _live.quests if not _live.is_empty() else Profile.quests


func _flags() -> Dictionary:
	if is_client():
		if not _remote.has("flags"):
			_remote["flags"] = {}
		return _remote.flags
	Profile.ensure()
	return _live.flags if not _live.is_empty() else Profile.flags


func flag(name: String) -> Variant:
	return _flags().get(name, null)


func qstate(qid: String) -> Dictionary:
	return _quests().get(qid, {})


## LOCKED / AVAILABLE / ACTIVE / COMPLETED / FAILED.
func state(qid: String) -> String:
	var s := qstate(qid)
	if not s.is_empty():
		return String(s.get("state", "ACTIVE"))
	return "AVAILABLE" if _requirements_met(qid) else "LOCKED"


func _requirements_met(qid: String) -> bool:
	var req: Dictionary = def(qid).get("requires", {})
	# в группе — доверие хоста (группа идёт по его кампании)
	var tl := int(_remote.get("trust_level", Profile.trust_level())) if is_client() else Profile.trust_level()
	if tl < int(req.get("trust_level", 1)):
		return false
	var fl: Dictionary = req.get("flags", {})
	for k in fl:
		if flag(String(k)) != fl[k]:
			return false
	for q in req.get("quests", []):
		if state(String(q)) != "COMPLETED":
			return false
	return true


func stage(qid: String) -> Dictionary:
	var stages: Array = def(qid).get("stages", [])
	var i := int(qstate(qid).get("stage", 0))
	return stages[i] if i >= 0 and i < stages.size() else {}


## Текущая цель активного квеста (или первая цель, если квест ещё только доступен).
func objective(qid: String) -> Dictionary:
	var st := stage(qid)
	var objs: Array = st.get("objectives", [])
	var i := int(qstate(qid).get("obj", 0))
	return objs[i] if i >= 0 and i < objs.size() else {}


## Что сейчас надо сделать — для журнала и отладки.
func status(qid: String) -> String:
	var s := state(qid)
	if s != "ACTIVE":
		return s
	var o := objective(qid)
	match String(o.get("type", "")):
		"talk":
			return "RETURN_TO_NPC"
		"reach_extraction", "extract_with_item", "extract_with_npc", "survive":
			return "WAITING_FOR_EXTRACTION"
		"extract_cargo":
			return "WAITING_FOR_EXTRACTION" if cargo_claimed(String(o.site)) else "OBJECTIVE"
	return "OBJECTIVE"


## Отслеживаемый квест: первый активный.
func tracked() -> String:
	for qid in _order:
		if state(qid) == "ACTIVE":
			return qid
	return ""


## Найденные улики [{title, text}] — для журнала.
func clues(qid: String) -> Array:
	return qstate(qid).get("clues", [])


# ---------------------------------------------------------------- разговоры (убежище)

## Что можно обсудить с npc: [{quest, dialogue, label}] — взять квест или отчитаться по нему.
func talk_options(npc: String) -> Array:
	var out: Array = []
	for qid in _order:
		var d := def(qid)
		var st := state(qid)
		if st == "AVAILABLE" and String(d.get("giver", "")) == npc:
			var first: Dictionary = (d.stages[0].objectives as Array)[0] if not (d.get("stages", []) as Array).is_empty() else {}
			out.append({"quest": qid, "dialogue": String(first.get("dialogue", "")), "label": "%s — %s" % [String(d.title), String(d.get("offer", "поговорить"))]})
		elif st == "ACTIVE":
			var o := objective(qid)
			if String(o.get("type", "")) == "talk" and String(o.get("npc", "")) == npc:
				out.append({"quest": qid, "dialogue": String(o.get("dialogue", "")), "label": "%s — %s" % [String(d.title), String(o.get("text", "поговорить"))]})
	return out


func dialogue(qid: String, did: String) -> Array:
	return (def(qid).get("dialogues", {}) as Dictionary).get(did, [])


## Разговор дочитан: доступный квест начинается, цель «поговорить» засчитывается (клиент — просит хост).
func finish_talk(qid: String, npc: String, did: String) -> void:
	if is_client():
		_rpc_talk.rpc_id(1, qid, npc, did)
		return
	if state(qid) == "AVAILABLE":
		start(qid)
	event("talk", {"npc": npc, "dialogue": did})


@rpc("any_peer", "call_remote", "reliable")
func _rpc_talk(qid: String, npc: String, did: String) -> void:
	if multiplayer.is_server():
		finish_talk(qid, npc, did)


# ---------------------------------------------------------------- ход квеста

func start(qid: String) -> bool:
	if is_client() or def(qid).is_empty() or state(qid) != "AVAILABLE":
		return false
	_quests()[qid] = {"state": "ACTIVE", "stage": 0, "obj": 0, "clues": [], "count": 0}
	_tell("Новое задание: " + String(def(qid).title))
	_commit_if_home()
	_broadcast()
	changed.emit()
	return true


## Событие мира: засчитать совпавшие цели активных квестов. true — хоть одна засчитана. Считает
## хост (соло — сам); клиент события не шлёт — просит через request_site / finish_talk / carry.
func event(type: String, params: Dictionary = {}) -> bool:
	if is_client():
		return false
	var any := false
	for qid in _order:
		if state(qid) != "ACTIVE":
			continue
		# одно событие может закрыть несколько целей подряд (эвакуация закрывает «уйти» и следующую)
		var guard := 0
		while guard < 8 and state(qid) == "ACTIVE" and _matches(qid, objective(qid), type, params):
			_complete_objective(qid)
			any = true
			guard += 1
			if type != "extracted":
				break
	if any:
		_commit_if_home()
		if _delivered:
			_commit_host()
		_broadcast()
		changed.emit()
	return any


## Осмотр / обыск / зона места sid своим игроком: соло и хост — сразу, клиент — просит хост.
func request_site(sid: String) -> void:
	if is_client():
		_rpc_site.rpc_id(1, sid)
	else:
		_use_site(multiplayer.get_unique_id() if Net.is_networked() else 1, sid)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_site(sid: String) -> void:
	if not multiplayer.is_server():
		return
	# хост сверяет: место есть, просящий рядом с ним (текущая ли цель — проверит event)
	var peer := multiplayer.get_remote_sender_id()
	if world == null or not world.near_site(peer, sid):
		return
	_use_site(peer, sid)


func _use_site(peer: int, sid: String) -> void:
	for qid: String in _order:
		var o: Dictionary = objective(qid)
		if state(qid) == "ACTIVE" and String(o.get("type", "")) == "extract_cargo" and String(o.get("site", "")) == sid:
			if world != null and not cargo_claimed(sid) and world.give_cargo(peer, sid, String(o.item)):
				_cargo_claims[sid] = true
				_broadcast()
			changed.emit()
			return
	event("site", {"site": sid})


func _matches(qid: String, o: Dictionary, type: String, p: Dictionary) -> bool:
	match String(o.get("type", "")):
		"talk":
			return type == "talk" and String(p.get("npc", "")) == String(o.get("npc", "")) \
				and (String(o.get("dialogue", "")) == "" or String(p.get("dialogue", "")) == String(o.dialogue))
		"interact", "find_clue", "search_location", "enter_zone":
			return type == "site" and String(p.get("site", "")) == String(o.get("site", ""))
		"pickup_item":
			return type == "have_item" and String(p.get("item", "")) == String(o.get("item", ""))
		"hand_in":
			# сдача предметов через терминал (контракт «Под заказ»): предметы уже сняты с тайника
			return type == "hand_in" and String(p.get("item", "")) == String(o.get("item", ""))
		"reach_extraction", "survive":
			return type == "extracted"
		"extract_with_item":
			return type == "extracted" and String(o.get("item", "")) in (p.get("items", []) as Array)
		"extract_cargo":
			return type == "extracted" and String(o.get("site", "")) in (p.get("cargo", []) as Array)
		"extract_with_npc":
			return type == "extracted" and String(o.get("npc", "")) in (p.get("npcs", []) as Array)
		"kill_targets":
			if type != "kill" or (String(o.get("arch", "")) != "" and String(p.get("arch", "")) != String(o.arch)):
				return false
			var s := qstate(qid)
			s["count"] = int(s.get("count", 0)) + 1
			return int(s.count) >= int(o.get("n", 1))
	return false


func _complete_objective(qid: String) -> void:
	var s := qstate(qid)
	var o := objective(qid)
	if o.has("clue"):
		var cl: Array = s.get("clues", [])
		cl.append(o.clue)
		s["clues"] = cl
		_tell("Найдена улика: " + String(o.clue.get("title", "")))
	var fl: Dictionary = o.get("set_flags", {})
	for k in fl:
		_flags()[String(k)] = fl[k]
	if o.has("toast"):
		_tell(String(o.toast))
	# что говорит / думает игрок, когда цель выполнена
	if not (o.get("say", []) as Array).is_empty():
		_say(o.say)
	s["count"] = 0
	s["obj"] = int(s.get("obj", 0)) + 1
	var objs: Array = stage(qid).get("objectives", [])
	if int(s.obj) >= objs.size():
		s["obj"] = 0
		s["stage"] = int(s.get("stage", 0)) + 1
		if stage(qid).is_empty():
			_complete_quest(qid)
			return
	var nxt := objective(qid)
	# и когда новая цель стала текущей
	if not (nxt.get("say_start", []) as Array).is_empty():
		_say(nxt.say_start)
	var t := String(nxt.get("type", ""))
	if t in ["reach_extraction", "extract_with_item", "extract_with_npc", "survive"]:
		_tell("Нужно эвакуироваться")
	else:
		_tell("Задание обновлено")


func _complete_quest(qid: String) -> void:
	var s := qstate(qid)
	s["state"] = "COMPLETED"
	var d := def(qid)
	var fl: Dictionary = d.get("flags_on_complete", {})
	for k in fl:
		_flags()[String(k)] = fl[k]
	# награда — при фиксации (вне рейда — сразу; в рейде — когда группа что-то вынесла)
	if _live.is_empty():
		_reward_completed(Profile.quests)
	_tell("Задание выполнено: " + String(d.title))


## Выдать награды за выполненные квесты списка, ещё не выданные этому профилю (отметка rewarded
## в записи квеста): повторная фиксация, переподключение и снимки награду не удваивают.
func _reward_completed(qs: Dictionary) -> void:
	for qid in qs:
		var s: Dictionary = qs[qid]
		if String(s.get("state", "")) == "COMPLETED" and not bool(s.get("rewarded", false)):
			s["rewarded"] = true
			_give_reward(def(String(qid)).get("reward", {}))


func _give_reward(r: Dictionary) -> void:
	Profile.money += int(r.get("money", 0))
	Profile.trust += int(r.get("trust", 0))
	for pair in r.get("items", []):
		ItemDb.add_to(Profile.stash, ItemDb.make(String(pair[0]), int(pair[1])), Profile.stash_grid())
	for id in r.get("unlock_stock", []):
		if not String(id) in Profile.unlocked_stock:
			Profile.unlocked_stock.append(String(id))
	# репутация у заказчиков терминала
	var rep: Dictionary = r.get("rep", {})
	if not rep.is_empty():
		if not Profile.contracts.has("rep"):
			Profile.contracts["rep"] = {}
		for gid in rep:
			Profile.contracts.rep[String(gid)] = int(Profile.contracts.rep.get(String(gid), 0)) + int(rep[gid])


func _commit_if_home() -> void:
	if _live.is_empty() and not is_client():
		Profile.save()


# ---------------------------------------------------------------- рейд

## Начало рейда (хост и соло): дальше всё — в копии, пока кто-то из группы не эвакуируется.
func begin_raid() -> void:
	if is_client():
		changed.emit()
		return
	Profile.ensure()
	_live = {"quests": Profile.quests.duplicate(true), "flags": Profile.flags.duplicate(true)}
	_delivered = false
	_carry = {}
	_npc_pos = {}
	_cargo_claims = {}
	_broadcast()
	changed.emit()


## Хост: участник эвакуировался с тем, что вынес (items — id предметов, npcs — раненые). Событие
## «эвакуация» — общей цели, и с этого момента сделанное в рейде засчитано всем.
func on_extracted(params: Dictionary) -> void:
	if is_client() or _live.is_empty():
		return
	event("extracted", params)
	_delivered = true
	_commit_host()
	_broadcast()
	changed.emit()


## Конец рейда (хост — когда сам уходит из рейда; соло — так же). Кто-то вынес — всё в профиль,
## не вынес никто — попытка не в счёт.
func end_raid() -> void:
	if is_client():
		changed.emit()
		return
	if _live.is_empty():
		return
	if _delivered:
		_commit_host()
	else:
		var lost := false
		for qid in _order:
			if JSON.stringify(_live.quests.get(qid, {})) != JSON.stringify(Profile.quests.get(qid, {})):
				lost = true
		if lost:
			_tell("Никто не эвакуировался — найденное в этом рейде не засчитано")
	_live = {}
	_delivered = false
	_carry = {}
	_npc_pos = {}
	# доска контрактов стареет и пополняется (рассылает снимок сама)
	Contracts.on_raid_end()
	_broadcast()
	changed.emit()


## Хост / соло: копия рейда — в свой профиль, награды за выполненное.
func _commit_host() -> void:
	if _live.is_empty():
		return
	Profile.quests = _live.quests.duplicate(true)
	Profile.flags = _live.flags.duplicate(true)
	_reward_completed(Profile.quests)
	# отметки наград — и в копию, чтобы следующая фиксация их не повторяла
	_live.quests = Profile.quests.duplicate(true)
	Profile.save()


# ---------------------------------------------------------------- группа: снимок и сообщения

func _snapshot() -> Dictionary:
	return {"campaign": Profile.own_campaign(), "quests": _quests(), "flags": _flags(), "raid": not _live.is_empty(),
		"delivered": _delivered, "carry": _carry, "npc_pos": _npc_pos, "trust_level": Profile.trust_level(),
		"contracts": Contracts.board(), "modules": Profile.modules, "cargo_claims": _cargo_claims,
		"unlock_all": Settings.unlock_all}


func _broadcast() -> void:
	if _is_host_net():
		_rpc_state.rpc(_snapshot())


@rpc("authority", "call_remote", "reliable")
func _rpc_state(snap: Dictionary) -> void:
	_remote = snap.duplicate(true)
	Profile.grow_unlocked()
	# заказы хоста — квесты-экземпляры и у гостя (награда за них — по их описанию)
	Contracts.on_snapshot(snap.get("contracts", []))
	# вне рейда хоста или группа уже что-то вынесла — это засчитано: в свой профиль
	if not bool(snap.get("raid", false)) or bool(snap.get("delivered", false)):
		_commit_guest(snap)
	changed.emit()


## Гость: состояние кампании хоста — в своё сохранение (отдельно от своей кампании), награды —
## себе, по одному разу.
func _commit_guest(snap: Dictionary) -> void:
	var cid := String(snap.get("campaign", ""))
	if cid == "":
		return
	Profile.ensure()
	var store: Dictionary = Profile.guest_campaigns.get(cid, {"quests": {}, "flags": {}, "rewarded": []})
	var rewarded: Array = store.get("rewarded", [])
	var qs: Dictionary = (snap.get("quests", {}) as Dictionary).duplicate(true)
	var changed_any := JSON.stringify(qs) != JSON.stringify(store.get("quests", {}))
	for qid in qs:
		if String((qs[qid] as Dictionary).get("state", "")) == "COMPLETED" and not String(qid) in rewarded:
			rewarded.append(String(qid))
			_give_reward(def(String(qid)).get("reward", {}))
			changed_any = true
	if not changed_any:
		return
	Profile.guest_campaigns[cid] = {"quests": qs, "flags": (snap.get("flags", {}) as Dictionary).duplicate(true), "rewarded": rewarded}
	Profile.save()


## Сообщение («Задание обновлено», «Найдена улика») — себе и всей группе.
func _tell(text: String) -> void:
	notice.emit(text)
	if _is_host_net():
		_rpc_tell.rpc(text)


func _say(lines: Array) -> void:
	subtitles.emit(lines)
	if _is_host_net():
		_rpc_say.rpc(lines)


@rpc("authority", "call_remote", "reliable")
func _rpc_tell(text: String) -> void:
	notice.emit(text)


@rpc("authority", "call_remote", "reliable")
func _rpc_say(lines: Array) -> void:
	subtitles.emit(lines)


# ---------------------------------------------------------------- раненые NPC (несут игроки)

## Кто несёт раненого места sid (0 — никто).
func carrier_of(sid: String) -> int:
	var c: Dictionary = _remote.get("carry", {}) if is_client() else _carry
	return int(c.get(sid, 0))


## Где положили (Vector3.INF — на своём месте).
func npc_pos(sid: String) -> Vector3:
	var p: Dictionary = _remote.get("npc_pos", {}) if is_client() else _npc_pos
	var a: Array = p.get(sid, [])
	return Vector3(float(a[0]), float(a[1]), float(a[2])) if a.size() == 3 else Vector3.INF


## Свой игрок поднимает (on) / кладёт раненого места sid; at — куда положил.
func request_carry(sid: String, on: bool, at: Vector3 = Vector3.ZERO) -> void:
	if is_client():
		_rpc_carry.rpc_id(1, sid, on, at)
	else:
		_set_carry(multiplayer.get_unique_id() if Net.is_networked() else 1, sid, on, at)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_carry(sid: String, on: bool, at: Vector3) -> void:
	if not multiplayer.is_server():
		return
	var peer := multiplayer.get_remote_sender_id()
	if on and (world == null or not world.near_site(peer, sid)):
		return
	_set_carry(peer, sid, on, at)


## Хост: поднять — если никто не несёт; положить — только тот, кто несёт (peer -1 — хост за упавшего).
func _set_carry(peer: int, sid: String, on: bool, at: Vector3) -> void:
	var cur := int(_carry.get(sid, 0))
	if on:
		if cur != 0 and cur != peer:
			return
		_carry[sid] = peer
	else:
		if cur == 0 or (cur != peer and peer != -1):
			return
		_carry[sid] = 0
		_npc_pos[sid] = [at.x, at.y, at.z]
	_broadcast()
	changed.emit()


## Хост: несущий упал или ушёл — раненый остаётся там, где он был.
func drop_carried(sid: String, at: Vector3) -> void:
	if not is_client():
		_set_carry(-1, sid, false, at)


# ---------------------------------------------------------------- места в мире

## Места уровня level, которые сейчас нужны: все места текущего этапа активных квестов (сцена
## остаётся, пока идёт этап; осмотреть можно только место текущей цели) + постоянные места
## по флагам (when_flags). [{quest, site, def, active}]
func sites_for(level: String) -> Array:
	var out: Array = []
	for qid in _order:
		var d := def(qid)
		var sites: Dictionary = d.get("sites", {})
		var wanted := {}
		if state(qid) == "ACTIVE":
			var cur := String(objective(qid).get("site", ""))
			for o in stage(qid).get("objectives", []):
				var sid := String((o as Dictionary).get("site", ""))
				if sid != "":
					wanted[sid] = sid == cur and not cargo_claimed(sid)
			# NPC, которого надо вынести, — его место остаётся
			var npc := String(objective(qid).get("npc", ""))
			for sid in sites:
				if String((sites[sid] as Dictionary).get("npc", "")) == npc and npc != "":
					wanted[String(sid)] = false
		for sid in sites:
			var sd: Dictionary = sites[sid]
			var wf: Dictionary = sd.get("when_flags", {})
			if not wf.is_empty():
				var ok := true
				for k in wf:
					ok = ok and flag(String(k)) == wf[k]
				if ok:
					wanted[String(sid)] = true
		for sid in wanted:
			var sd: Dictionary = sites.get(sid, {})
			if String(sd.get("level", "")) == level:
				out.append({"quest": qid, "site": String(sid), "def": sd, "active": bool(wanted[sid])})
	return out


## Охрана этапа (stage.guards): {site, n, radius} или пусто.
func guards_for(level: String) -> Array:
	var out: Array = []
	for qid in _order:
		if state(qid) != "ACTIVE":
			continue
		var g: Dictionary = stage(qid).get("guards", {})
		if g.is_empty():
			continue
		var sd: Dictionary = (def(qid).get("sites", {}) as Dictionary).get(String(g.site), {})
		if String(sd.get("level", "")) == level:
			# охраны больше с группой: соло ×1, двое ×1.4, трое ×1.8 (docs/design/contracts_and_map.md §3)
			var group := clampi(Net.player_names.size() if Net.is_networked() else 1, 1, 3)
			var count: int = int(Balance.ENGRAVING.guards) if String(g.get("balance", "")) == "engraving" else int(g.get("n", 3))
			var radius: float = float(Balance.ENGRAVING.guard_radius) if String(g.get("balance", "")) == "engraving" else float(g.get("radius", 8.0))
			var n := ceili(count * [1.0, 1.4, 1.8][group - 1])
			out.append({"quest": qid, "site": String(g.site), "n": n, "radius": radius})
	return out


# ---------------------------------------------------------------- отладка (консоль разработчика)
## Команды разработчика меняют сразу профиль (и копию рейда, если идёт рейд) — не теряются.

func _dev_sync() -> void:
	if not _live.is_empty():
		Profile.quests = _live.quests.duplicate(true)
		Profile.flags = _live.flags.duplicate(true)
	Profile.save()
	_broadcast()
	changed.emit()


func dev_start(qid: String) -> String:
	if def(qid).is_empty():
		return "нет квеста " + qid
	_quests()[qid] = {"state": "ACTIVE", "stage": 0, "obj": 0, "clues": [], "count": 0}
	_dev_sync()
	return "начат " + qid


## Этап n (с 1), первая цель этапа.
func dev_stage(qid: String, n: int) -> String:
	var stages: Array = def(qid).get("stages", [])
	if n < 1 or n > stages.size():
		return "этапы 1–%d" % stages.size()
	var s: Dictionary = _quests().get(qid, {"clues": [], "count": 0})
	s["state"] = "ACTIVE"
	s["stage"] = n - 1
	s["obj"] = 0
	_quests()[qid] = s
	_dev_sync()
	return "%s: этап %d — %s" % [qid, n, String(stage(qid).get("title", ""))]


func dev_complete_objective(qid: String) -> String:
	if qid == "":
		qid = tracked()
	if state(qid) != "ACTIVE":
		return "нет активного квеста"
	var was := String(objective(qid).get("id", ""))
	_complete_objective(qid)
	_dev_sync()
	return "засчитана цель " + was


func dev_reset(qid: String) -> String:
	_quests().erase(qid)
	var d := def(qid)
	for k in (d.get("flags_on_complete", {}) as Dictionary):
		_flags().erase(k)
	for st in d.get("stages", []):
		for o in (st as Dictionary).get("objectives", []):
			for k in ((o as Dictionary).get("set_flags", {}) as Dictionary):
				_flags().erase(k)
	_dev_sync()
	return "сброшен " + qid


func dev_describe() -> String:
	var lines: Array[String] = []
	for qid in _order:
		lines.append("%s: %s, этап %d, цель %s — %s" % [qid, state(qid), int(qstate(qid).get("stage", 0)) + 1,
			String(objective(qid).get("id", "-")), status(qid)])
	lines.append("флаги: " + JSON.stringify(_flags()))
	return "\n".join(lines)
