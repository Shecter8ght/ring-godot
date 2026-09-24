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
##
## Реплики: в диалогах [кто, текст], кто = "player" — герой (подпись «Я», свой цвет); в lines
## мест и say / say_start целей — строка (описание) или [кто, текст]. say — цель выполнена,
## say_start — цель стала текущей: герой говорит сам, без этого квест «немой».

signal changed
## Короткое сообщение на экране («Найдена улика», «Задание обновлено»).
signal notice(text: String)
## Реплики на экране (осмотр места, раненый NPC) — сами по очереди.
signal subtitles(lines: Array)

const INDEX := "res://data/quests/index.json"

var _defs: Dictionary = {}
var _order: Array[String] = []
## В рейде: копия состояния {quests, flags, rewards}; вне рейда пусто.
var _live: Dictionary = {}
## Интерфейс: цель, сообщения, разговоры, журнал, консоль разработчика.
var hud: QuestHud


func _ready() -> void:
	_load_defs()
	hud = QuestHud.new()
	hud.name = "QuestHud"
	add_child(hud)


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


# ---------------------------------------------------------------- чтение

func ids() -> Array[String]:
	return _order


func def(qid: String) -> Dictionary:
	return _defs.get(qid, {})


func in_raid() -> bool:
	return not _live.is_empty()


func _quests() -> Dictionary:
	Profile.ensure()
	return _live.quests if in_raid() else Profile.quests


func _flags() -> Dictionary:
	Profile.ensure()
	return _live.flags if in_raid() else Profile.flags


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
	if Profile.trust_level() < int(req.get("trust_level", 1)):
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


## Разговор дочитан: доступный квест начинается, цель «поговорить» засчитывается.
func finish_talk(qid: String, npc: String, did: String) -> void:
	if state(qid) == "AVAILABLE":
		start(qid)
	event("talk", {"npc": npc, "dialogue": did})


# ---------------------------------------------------------------- ход квеста

func start(qid: String) -> bool:
	if def(qid).is_empty() or state(qid) != "AVAILABLE":
		return false
	_quests()[qid] = {"state": "ACTIVE", "stage": 0, "obj": 0, "clues": [], "count": 0}
	notice.emit("Новое задание: " + String(def(qid).title))
	_commit_if_home()
	return true


## Событие мира: засчитать совпавшие цели активных квестов. true — хоть одна засчитана.
func event(type: String, params: Dictionary = {}) -> bool:
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
		changed.emit()
	return any


func _matches(qid: String, o: Dictionary, type: String, p: Dictionary) -> bool:
	match String(o.get("type", "")):
		"talk":
			return type == "talk" and String(p.get("npc", "")) == String(o.get("npc", "")) \
				and (String(o.get("dialogue", "")) == "" or String(p.get("dialogue", "")) == String(o.dialogue))
		"interact", "find_clue", "search_location", "enter_zone":
			return type == "site" and String(p.get("site", "")) == String(o.get("site", ""))
		"pickup_item":
			return type == "have_item" and String(p.get("item", "")) == String(o.get("item", ""))
		"reach_extraction", "survive":
			return type == "extracted"
		"extract_with_item":
			return type == "extracted" and String(o.get("item", "")) in (p.get("items", []) as Array)
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
		notice.emit("Найдена улика: " + String(o.clue.get("title", "")))
	var fl: Dictionary = o.get("set_flags", {})
	for k in fl:
		_flags()[String(k)] = fl[k]
	if o.has("toast"):
		notice.emit(String(o.toast))
	# что говорит / думает игрок, когда цель выполнена
	if not (o.get("say", []) as Array).is_empty():
		subtitles.emit(o.say)
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
		subtitles.emit(nxt.say_start)
	var t := String(nxt.get("type", ""))
	if t in ["reach_extraction", "extract_with_item", "extract_with_npc", "survive"]:
		notice.emit("Нужно эвакуироваться")
	else:
		notice.emit("Задание обновлено")


func _complete_quest(qid: String) -> void:
	var s := qstate(qid)
	s["state"] = "COMPLETED"
	var d := def(qid)
	var fl: Dictionary = d.get("flags_on_complete", {})
	for k in fl:
		_flags()[String(k)] = fl[k]
	var reward: Dictionary = d.get("reward", {})
	if in_raid():
		(_live.rewards as Array).append(reward)
	else:
		_give_reward(reward)
	notice.emit("Задание выполнено: " + String(d.title))


func _give_reward(r: Dictionary) -> void:
	Profile.money += int(r.get("money", 0))
	Profile.trust += int(r.get("trust", 0))
	for pair in r.get("items", []):
		ItemDb.add_to(Profile.stash, ItemDb.make(String(pair[0]), int(pair[1])), Profile.stash_grid())
	for id in r.get("unlock_stock", []):
		if not String(id) in Profile.unlocked_stock:
			Profile.unlocked_stock.append(String(id))


func _commit_if_home() -> void:
	if not in_raid():
		Profile.save()


# ---------------------------------------------------------------- рейд

## Начало рейда: дальше всё — в копии, до эвакуации.
func begin_raid() -> void:
	Profile.ensure()
	_live = {"quests": Profile.quests.duplicate(true), "flags": Profile.flags.duplicate(true), "rewards": []}
	changed.emit()


## Конец рейда. Эвакуировался — событие «эвакуация» и всё сделанное — в профиль; иначе забыто.
func end_raid(extracted: bool, params: Dictionary = {}) -> void:
	if not in_raid():
		return
	if extracted:
		event("extracted", params)
		Profile.quests = _live.quests
		Profile.flags = _live.flags
		for r in _live.rewards:
			_give_reward(r)
		_live = {}
		Profile.save()
	else:
		var lost := false
		for qid in _order:
			if JSON.stringify(_live.quests.get(qid, {})) != JSON.stringify(Profile.quests.get(qid, {})):
				lost = true
		_live = {}
		if lost:
			notice.emit("Не эвакуировался — найденное в этом рейде не засчитано")
	changed.emit()


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
					wanted[sid] = sid == cur
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
			out.append({"quest": qid, "site": String(g.site), "n": int(g.get("n", 3)), "radius": float(g.get("radius", 8.0))})
	return out


# ---------------------------------------------------------------- отладка (консоль разработчика)
## Команды разработчика меняют сразу профиль (и копию рейда, если идёт рейд) — не теряются.

func _dev_sync() -> void:
	if in_raid():
		Profile.quests = _live.quests.duplicate(true)
		Profile.flags = _live.flags.duplicate(true)
	Profile.save()
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
