extends Node
## Контракты терминала. Autoload `Contracts`. Заказчики — data/contracts/givers.json, шаблоны —
## data/contracts/templates.json (docs/design/contracts_and_map.md).
##
## Доска (Profile.contracts.board) — записи {id, tpl, giver, seed, born}: шаблон + зерно однозначно
## задают заказ (места, предмет, текст), поэтому у всей группы он одинаковый без пересылки самого
## заказа. Каждый заказ — квест-экземпляр в Quests (build → описание квеста, Quests.set_extra):
## взятый заказ живёт там же, где сюжет — общий прогресс группы у хоста, места в рейде, журнал,
## награда каждому (в т.ч. гостю). Квест-экземпляр кончается целью «сдать через терминал»
## (talk с id заказчика) или сдачей предметов (hand_in).
##
## Доска пополняется до OFFERS_PER_GIVER заказов у каждого заказчика; невзятый заказ живёт
## OFFER_RAIDS рейдов. Взять можно не больше active_limit() сразу. Репутация у заказчика
## (Profile.contracts.rep) растёт за сданные заказы, падает на ступень за отказ от взятого.
## В группе доска — хоста (как и сюжет): гость видит её из снимка и просит хост взять/сдать.

signal changed

const GIVERS := "res://data/contracts/givers.json"
const TEMPLATES := "res://data/contracts/templates.json"
const OFFERS_PER_GIVER := 2
const OFFER_RAIDS := 3
const ACTIVE_LIMIT := 3
## Очков репутации на ступень (ступени 1–5).
const REP_STEP := 3

var _givers: Array = []
var _templates: Dictionary = {}
## Клиент: доска хоста из снимка Quests.
var _remote_board: Array = []
var _has_remote: bool = false


func _ready() -> void:
	var g: Variant = JSON.parse_string(FileAccess.get_file_as_string(GIVERS))
	_givers = (g as Dictionary).get("givers", []) if g is Dictionary else []
	var t: Variant = JSON.parse_string(FileAccess.get_file_as_string(TEMPLATES))
	if t is Dictionary:
		for tpl: Dictionary in (t as Dictionary).get("templates", []):
			_templates[String(tpl.id)] = tpl
	Quests.changed.connect(_on_quests_changed)
	sync.call_deferred()


# ---------------------------------------------------------------- чтение

func givers() -> Array:
	return _givers


func giver(gid: String) -> Dictionary:
	for g: Dictionary in _givers:
		if String(g.id) == gid:
			return g
	return {}


func is_contract(qid: String) -> bool:
	return qid.begins_with("ct_")


## Доска: своя (соло и хост) или хоста (гость в сети).
func board() -> Array:
	if Quests.is_client():
		return _remote_board
	return _store().get("board", [])


func rep_points(gid: String) -> int:
	return int((_store().get("rep", {}) as Dictionary).get(gid, 0))


## Ступень 1–5.
func rep_level(gid: String) -> int:
	return clampi(1 + rep_points(gid) / REP_STEP, 1, 5)


func active_limit() -> int:
	return ACTIVE_LIMIT


## Записи доски заказчика gid: [{entry, def, state}] — сначала взятые.
func offers(gid: String) -> Array:
	var out: Array = []
	for e: Dictionary in board():
		if String(e.giver) != gid:
			continue
		var qid := String(e.id)
		out.append({"entry": e, "def": Quests.def(qid), "state": Quests.state(qid)})
	out.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return String(a.state) == "ACTIVE" and String(b.state) != "ACTIVE")
	return out


func active_count() -> int:
	var n := 0
	for e: Dictionary in board():
		if Quests.state(String(e.id)) == "ACTIVE":
			n += 1
	return n


## Можно ли сдать через терминал прямо сейчас (текущая цель — сдача и она выполнима).
func can_turn_in(qid: String) -> bool:
	if Quests.state(qid) != "ACTIVE":
		return false
	var o := Quests.objective(qid)
	match String(o.get("type", "")):
		"talk":
			return true
		"hand_in":
			return Profile.stash_count(String(o.item), true) >= int(o.get("n", 1))
	return false


# ---------------------------------------------------------------- доска

func _store() -> Dictionary:
	Profile.ensure()
	if not Profile.contracts.has("board"):
		Profile.contracts["board"] = []
	if not Profile.contracts.has("rep"):
		Profile.contracts["rep"] = {}
	return Profile.contracts


## Хост и соло: доска полна (у каждого заказчика OFFERS_PER_GIVER заказов), квесты-экземпляры
## зарегистрированы; выполненные и брошенные — убраны.
func sync() -> void:
	if Quests.is_client():
		_register(_remote_board)
		return
	var st := _store()
	var b: Array = st.board
	var raids := int(st.get("raids", 0))
	var keep: Array = []
	for e: Dictionary in b:
		var qid := String(e.id)
		var s := String(Quests.qstate(qid).get("state", ""))
		# выполнен и награда выдана — с доски и из профиля прочь
		if s == "COMPLETED" and bool(Quests.qstate(qid).get("rewarded", false)):
			Profile.quests.erase(qid)
			continue
		if s == "FAILED":
			Profile.quests.erase(qid)
			continue
		# невзятый заказ устарел
		if s == "" and raids - int(e.get("born", 0)) >= OFFER_RAIDS:
			continue
		keep.append(e)
	for g: Dictionary in _givers:
		var gid := String(g.id)
		var have := keep.filter(func(e: Dictionary) -> bool: return String(e.giver) == gid).size()
		while have < OFFERS_PER_GIVER:
			var e := _new_offer(gid, keep)
			if e.is_empty():
				break
			keep.append(e)
			have += 1
	st.board = keep
	_register(keep)
	Profile.save()
	changed.emit()


## Новый заказ заказчику gid: лучше шаблон, которого у него сейчас нет на доске.
func _new_offer(gid: String, current: Array) -> Dictionary:
	var st := _store()
	var used: Array = current.filter(func(e: Dictionary) -> bool: return String(e.giver) == gid).map(func(e: Dictionary) -> String: return String(e.tpl))
	var pool: Array = []
	var any: Array = []
	for tid in _templates:
		if gid in (_templates[tid].givers as Array):
			any.append(String(tid))
			if not String(tid) in used:
				pool.append(String(tid))
	# шаблонов у заказчика меньше, чем мест на доске, — тот же шаблон с другим зерном (другое место)
	if pool.is_empty():
		pool = any
	if pool.is_empty():
		return {}
	var seq := int(st.get("seq", 0)) + 1
	st["seq"] = seq
	var rng := RandomNumberGenerator.new()
	rng.seed = hash("%s|%d|%s" % [Profile.own_campaign(), seq, gid])
	var e := {"id": "ct_%d" % seq, "tpl": String(pool[rng.randi_range(0, pool.size() - 1)]), "giver": gid,
		"seed": rng.randi(), "born": int(st.get("raids", 0))}
	# тот же шаблон у заказчика — другой предмет или место, не копия соседнего заказа
	var titles: Array = current.filter(func(x: Dictionary) -> bool: return String(x.giver) == gid).map(func(x: Dictionary) -> String: return String(build(x).get("title", "")))
	for attempt: int in range(8):
		if not String(build(e).get("title", "")) in titles:
			break
		e.seed = rng.randi()
	return e


## Заказы доски → квесты-экземпляры в Quests.
func _register(b: Array) -> void:
	var defs := {}
	for e: Dictionary in b:
		var d := build(e)
		if not d.is_empty():
			defs[String(e.id)] = d
	Quests.set_extra(defs)


## Хост: рейд закончился — доска стареет и пополняется.
func on_raid_end() -> void:
	if Quests.is_client():
		return
	var st := _store()
	st["raids"] = int(st.get("raids", 0)) + 1
	sync()


func _on_quests_changed() -> void:
	# заказ выполнен вне рейда (сдан) — убрать с доски и выставить новый
	if Quests.is_client() or Quests.in_raid():
		return
	for e: Dictionary in board():
		var s := Quests.qstate(String(e.id))
		if String(s.get("state", "")) == "COMPLETED" and bool(s.get("rewarded", false)):
			sync.call_deferred()
			return


# ---------------------------------------------------------------- действия (терминал)

## Взять заказ: соло и хост — сразу, гость — просит хост.
func take(qid: String) -> String:
	if Quests.state(qid) != "AVAILABLE":
		return "заказ уже недоступен"
	if active_count() >= active_limit():
		return "взято максимум заказов (%d)" % active_limit()
	if Quests.is_client():
		_rpc_take.rpc_id(1, qid)
		return ""
	Quests.start(qid)
	return ""


@rpc("any_peer", "call_remote", "reliable")
func _rpc_take(qid: String) -> void:
	if multiplayer.is_server() and active_count() < active_limit():
		Quests.start(qid)


## Отказаться: невзятый — убрать с доски; взятый — репутация у заказчика вниз на ступень.
func decline(qid: String) -> void:
	if Quests.is_client():
		_rpc_decline.rpc_id(1, qid)
		return
	var st := _store()
	for e: Dictionary in st.board:
		if String(e.id) != qid:
			continue
		if Quests.state(qid) == "ACTIVE":
			var rep: Dictionary = st.rep
			rep[String(e.giver)] = maxi(0, int(rep.get(String(e.giver), 0)) - REP_STEP)
		Quests.drop_extra(qid)
		st.board.erase(e)
		break
	sync()


@rpc("any_peer", "call_remote", "reliable")
func _rpc_decline(qid: String) -> void:
	if multiplayer.is_server():
		decline(qid)


## Сдать через терминал: цель «сдать» (talk) или предметы (hand_in — из своего тайника, только
## найденное в рейде). Пусто — успех, иначе причина.
func turn_in(qid: String) -> String:
	if not can_turn_in(qid):
		return "сдавать пока нечего"
	var o := Quests.objective(qid)
	var e: Dictionary = {}
	for x: Dictionary in board():
		if String(x.id) == qid:
			e = x
	if String(o.type) == "hand_in":
		Profile.take_from_stash(String(o.item), int(o.get("n", 1)), true)
		Profile.save()
		if Quests.is_client():
			_rpc_handed.rpc_id(1, qid, String(o.item))
		else:
			Quests.event("hand_in", {"item": String(o.item)})
		return ""
	Quests.finish_talk(qid, String(e.get("giver", "")), "")
	return ""


@rpc("any_peer", "call_remote", "reliable")
func _rpc_handed(qid: String, item: String) -> void:
	if multiplayer.is_server() and Quests.state(qid) == "ACTIVE":
		Quests.event("hand_in", {"item": item})


## Гость: доска хоста пришла в снимке Quests.
func on_snapshot(b: Array) -> void:
	_remote_board = b.duplicate(true)
	_has_remote = true
	_register(_remote_board)
	changed.emit()


# ---------------------------------------------------------------- заказ из шаблона

## Описание квеста-экземпляра по записи доски (детерминированно: шаблон + зерно).
func build(e: Dictionary) -> Dictionary:
	var tpl: Dictionary = _templates.get(String(e.get("tpl", "")), {})
	if tpl.is_empty():
		return {}
	var rng := RandomNumberGenerator.new()
	rng.seed = int(e.seed)
	var gid := String(e.giver)
	var g := giver(gid)
	var texts: Array = (tpl.get("texts", {}) as Dictionary).get(gid, [""])
	var text := String(texts[rng.randi_range(0, texts.size() - 1)])
	var d := {"id": String(e.id), "contract": true, "giver": gid, "title": String(tpl.title),
		"from": String(g.get("nick", gid)), "offer": "заказ", "requires": {}, "stages": [], "sites": {}}
	match String(tpl.kind):
		"hand_in":
			var it: Array = tpl.items[rng.randi_range(0, (tpl.items as Array).size() - 1)]
			var item_name := ItemDb.item_name(String(it[0]))
			var n := int(it[1])
			var value := ItemDb.value(String(it[0]))
			d.summary = text.replace("{item}", item_name).replace("{n}", str(n))
			d.title = "%s: %s" % [String(tpl.title), item_name]
			d.stages = [{"id": "s1", "title": String(tpl.title), "objectives": [
				{"id": "hand", "type": "hand_in", "item": String(it[0]), "n": n,
					"text": String(tpl.objective_text).replace("{item}", item_name).replace("{n}", str(n)),
					"hint": "Сдаётся через терминал в убежище, из тайника; покупное не принимается."}]}]
			d.reward = {"money": int(round(value * n * float(tpl.get("pay_k", 1.5)) / 100.0)) * 100, "rep": {gid: int(tpl.get("rep", 1))}}
		"sites", "clear":
			var pool: Array = (tpl.sites as Array).duplicate()
			var chosen: Array = []
			for i: int in range(mini(int(tpl.get("pick", 1)), pool.size())):
				chosen.append(pool.pop_at(rng.randi_range(0, pool.size() - 1)))
			var places := ", ".join(chosen.map(func(s: Dictionary) -> String: return String(s.place)))
			var first: Dictionary = chosen[0]
			d.summary = text.replace("{places}", places).replace("{place}", String(first.place)).replace("{thing}", String(first.get("thing", "")))
			d.title = "%s: %s" % [String(tpl.title), String(first.place) if chosen.size() == 1 else "%d точки" % chosen.size()]
			var objs: Array = []
			var stage := {"id": "s1", "title": String(tpl.title)}
			for s: Dictionary in chosen:
				var sid := "%s_%s" % [String(e.id), String(s.key)]
				var site := {"level": "f1_ring", "anchor": s.anchor, "yaw": rng.randf_range(0.0, 360.0),
					"radius": float(tpl.get("radius", 2.2)), "props": tpl.get("props", [])}
				if String(tpl.kind) == "clear":
					site["zone"] = float(tpl.get("radius", 8.0))
					stage["guards"] = {"site": sid, "n": int(tpl.get("guards", 4)), "radius": float(tpl.get("guard_radius", 9.0))}
				else:
					site["prompt"] = String(tpl.prompt)
					site["search_s"] = float(tpl.get("search_s", 0.0))
				d.sites[sid] = site
				var o := {"id": String(s.key), "type": String(tpl.objective), "site": sid,
					"text": String(tpl.objective_text).replace("{place}", String(s.place)).replace("{thing}", String(s.get("thing", "")))}
				if String(tpl.kind) != "clear":
					o["say"] = tpl.get("say", [])
				if s.has("thing"):
					o["clue"] = {"title": String(s.thing).capitalize(), "text": "Найдено: %s (%s)." % [String(s.thing), String(s.place)]}
				objs.append(o)
				if String(tpl.kind) == "clear":
					objs.append({"id": "clear", "type": "kill_targets", "n": int(tpl.get("guards", 4)),
						"text": String(tpl.kill_text).replace("{place}", String(s.place)), "say": tpl.get("say", [])})
			objs.append({"id": "extract", "type": "reach_extraction", "text": "Эвакуироваться."})
			objs.append({"id": "report", "type": "talk", "npc": gid, "text": "Отчитаться через терминал в убежище."})
			stage["objectives"] = objs
			d.stages = [stage]
			d.reward = {"money": int(tpl.get("money", 20000)), "rep": {gid: int(tpl.get("rep", 1))}}
	return d
