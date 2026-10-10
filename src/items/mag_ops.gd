class_name MagOps
extends RefCounted
## Поштучные операции с предметом в сетке — не мгновенно, по шагу (Balance.MAG_OPS):
##   "load"   — снарядить ОДИН магазин: по патрону из sources — заданным ammo (бросили патроны на
##              магазин), иначе тем же, что сверху в магазине, а нет его — тем, которого больше всего.
##              Типы можно мешать: новый патрон ложится сверху и уйдёт в ствол первым (Gear.mag_layers);
##   "unload" — разрядить магазин: по патрону сверху — в первую сетку из dests, где есть место;
##   "plates" — вынуть плиты из жилета: по одной — туда же (only_side — только эту).
## Прервали — что сделано, то сделано. Кончилось само — полный / пустой / патронов нет / места нет
## (reason).
##
## Предмет помечается полем "op" ({id — чья операция, k — вид, s — сколько было, known — снаряжают
## заведомо пустой}): по пометке он находится после каждого шага (индексы сдвигаются — стопки
## кончаются, появляются новые) и по ней сетка рисует круговой индикатор (GridView).
##
## Сетки даёт хозяин операции — тремя функциями: get_list(role) -> рабочая копия сетки,
## commit(role, list) — записать (у хоста — переприсвоить для синхронизатора, в убежище — в профиль),
## grid_of(role) -> Vector2i. Хозяева: Raid на хосте (рюкзак, карман, буфер игрока, «loot» — ящик) и
## окно убежища (тайник, рюкзак, карман профиля).

var get_list: Callable
var commit: Callable
var grid_of: Callable

## Чья операция (peer; в убежище — 1): на один ящик могут смотреть двое.
var owner_id: int = 1
var kind: String = ""
## Где лежит предмет.
var role: String = ""
## Откуда брать патроны (load) и куда класть вынутое (unload, plates), по порядку.
var sources: Array[String] = []
var dests: Array[String] = []
## load: каким патроном («» — выбрать самому); plates: только эту сторону («» — все).
var ammo: String = ""
var only_side: String = ""
## Почему закончилась: full, empty, no_ammo, no_room, gone, busy, cancel.
var reason: String = ""
## Все сетки хозяина: предмет могли переложить — пометку снимаем, где бы он ни оказался.
var all_roles: Array[String] = []
## Чьи операции сейчас идут (у хоста — несколько игроков): чужая пометка без операции — забытая.
var active_ids: Array = []
## Сколько шагов сделано (звук на каждый).
var steps: int = 0
## Снаряжают с ускорителем (Balance.MAG_OPS.loader_item лежит в одной из сеток хозяина) — быстрее.
var fast: bool = false

var _t: float = 0.0
var _lists: Dictionary = {}
var _dirty: Dictionary = {}


static func make(p_kind: String, p_role: String, p_owner: int, p_get: Callable, p_commit: Callable, p_grid: Callable) -> MagOps:
	var op := MagOps.new()
	op.kind = p_kind
	op.role = p_role
	op.owner_id = p_owner
	op.get_list = p_get
	op.commit = p_commit
	op.grid_of = p_grid
	return op


## Секунд на шаг.
func step_sec() -> float:
	match kind:
		"load":
			return 1.0 / float(Balance.MAG_OPS.loader_rate) if fast else float(Balance.MAG_OPS.load_sec)
		"unload":
			return float(Balance.MAG_OPS.unload_sec)
	return float(Balance.MAG_OPS.plate_sec)


## Есть ли у хозяина ускоритель снаряжения: в любой его сетке (ящик с добычей не в счёт — он чужой).
func _has_loader() -> bool:
	var want := String(Balance.MAG_OPS.loader_item)
	for r: String in all_roles:
		if r == "loot":
			continue
		for e: Dictionary in _list(r):
			if String(e.get("id", "")) == want:
				return true
	return false


## Начать с предмета idx в сетке role: проверить, что есть что делать, и пометить. false — нечего
## (reason — почему).
func start(idx: int) -> bool:
	_lists.clear()
	_dirty.clear()
	var list := _list(role)
	if idx < 0 or idx >= list.size():
		reason = "gone"
		return false
	var e: Dictionary = list[idx]
	if e.get("op") is Dictionary:
		var who := int((e.op as Dictionary).get("id", -1))
		# чужая идущая операция — занято; своя прежняя или забытая — перезаписать
		if who != owner_id and who in active_ids:
			reason = "busy"
			return false
	var s := 0
	match kind:
		"load":
			fast = _has_loader()
			if not e.has("rounds"):
				reason = "gone"
				return false
			if int(e.rounds) >= capacity(e):
				reason = "full"
				return false
			if ammo == "" or not ammo_fits(e, ammo):
				ammo = pick_ammo(e, _all(sources))
			if ammo == "" or count_of(_all(sources), ammo) <= 0:
				reason = "no_ammo"
				return false
			s = int(e.rounds)
		"unload":
			if not e.has("rounds") or int(e.rounds) <= 0 or Gear.mag_top(e) == "":
				reason = "empty"
				return false
			if not _room_for({"id": Gear.mag_top(e), "n": 1}):
				reason = "no_room"
				return false
			s = int(e.rounds)
		"plates":
			var side := _next_side(e)
			if side == "":
				reason = "empty"
				return false
			var p: Dictionary = e.plates[side]
			if not _room_for({"id": String(p.id), "n": 1, "dur": float(p.dur)}):
				reason = "no_room"
				return false
			s = (e.plates as Dictionary).size()
		_:
			reason = "gone"
			return false
	e["op"] = {"id": owner_id, "k": kind, "s": s, "known": kind == "load" and s == 0}
	_dirty[role] = true
	_flush()
	return true


## Время идёт: шаги по step_sec. false — закончилась (пометка снята).
func tick(delta: float) -> bool:
	_t += delta
	var per := step_sec()
	while _t >= per:
		_t -= per
		_lists.clear()
		_dirty.clear()
		var more := _step()
		_flush()
		steps += 1
		if not more:
			finish()
			return false
	return true


## Снять пометку: закончилась или прервали — что сделано, остаётся. Предмет могли переложить в
## другую сетку — ищем во всех.
func finish() -> void:
	_lists.clear()
	_dirty.clear()
	var roles: Array[String] = [role]
	for r in all_roles:
		if not r in roles:
			roles.append(r)
	for r in roles:
		var list := _list(r)
		var i := _find(list)
		if i >= 0:
			(list[i] as Dictionary).erase("op")
			_dirty[r] = true
	_flush()


func cancel() -> void:
	reason = "cancel"
	finish()


# ---------------------------------------------------------------- шаг

func _step() -> bool:
	var list := _list(role)
	var i := _find(list)
	if i < 0:
		reason = "gone"
		return false
	var e: Dictionary = list[i]
	match kind:
		"load":
			return _load_one(e)
		"unload":
			return _unload_one(e)
		"plates":
			return _plate_one(e)
	return false


func _load_one(e: Dictionary) -> bool:
	var cap := capacity(e)
	if int(e.rounds) >= cap:
		reason = "full"
		return false
	var want := ammo
	for r in sources:
		var src := _list(r)
		for j in range(src.size()):
			var it: Dictionary = src[j]
			if String(it.id) == want and not it.has("rounds"):
				ItemDb.remove_at(src, j, 1)
				Gear.mag_push(e, want)
				_dirty[r] = true
				_dirty[role] = true
				if int(e.rounds) >= cap:
					reason = "full"
					return false
				return true
	reason = "no_ammo"
	return false


func _unload_one(e: Dictionary) -> bool:
	if int(e.rounds) <= 0:
		reason = "empty"
		return false
	var one := {"id": Gear.mag_top(e), "n": 1}
	if bool(e.get("fir", false)):
		one["fir"] = true
	for r in dests:
		if ItemDb.add_to(_list(r), one, grid_of.call(r)) > 0:
			Gear.mag_pop(e)
			_dirty[r] = true
			_dirty[role] = true
			if int(e.rounds) <= 0:
				reason = "empty"
				return false
			return true
	reason = "no_room"
	return false


func _plate_one(e: Dictionary) -> bool:
	var side := _next_side(e)
	if side == "":
		reason = "empty"
		return false
	var plates: Dictionary = e.plates
	var p: Dictionary = plates[side]
	var got := {"id": String(p.id), "n": 1, "dur": float(p.dur)}
	for r in dests:
		if ItemDb.add_to(_list(r), got, grid_of.call(r)) > 0:
			plates.erase(side)
			e["plates"] = plates
			_dirty[r] = true
			_dirty[role] = true
			if _next_side(e) == "":
				reason = "empty"
				return false
			return true
	reason = "no_room"
	return false


func _next_side(e: Dictionary) -> String:
	var plates: Dictionary = e.get("plates", {}) if e.get("plates") is Dictionary else {}
	if only_side != "":
		return only_side if plates.has(only_side) else ""
	for s in ["front", "back"]:
		if plates.has(s):
			return s
	return ""


func _room_for(entry: Dictionary) -> bool:
	for r in dests:
		if ItemDb.room_in(_list(r), entry, grid_of.call(r)) > 0:
			return true
	return false


# ---------------------------------------------------------------- сетки

## Рабочая копия сетки (одна на шаг: сетка-источник и сетка предмета бывают одной и той же).
func _list(r: String) -> Array:
	if not _lists.has(r):
		_lists[r] = get_list.call(r)
	return _lists[r]


func _all(roles: Array[String]) -> Array:
	var out: Array = []
	for r in roles:
		out.append_array(_list(r))
	return out


func _flush() -> void:
	for r in _dirty:
		commit.call(String(r), _lists[r])
	_dirty.clear()


func _find(list: Array) -> int:
	for i in range(list.size()):
		var op: Variant = (list[i] as Dictionary).get("op")
		if op is Dictionary and int((op as Dictionary).get("id", -1)) == owner_id:
			return i
	return -1


# ---------------------------------------------------------------- справки (и для окон)

static func capacity(mag: Dictionary) -> int:
	return int(WeaponDb.magazine(String(mag.id)).get("capacity", 0))


## Патрон подходит к магазину: свой калибр. Тип — любой: в магазине их можно мешать.
static func ammo_fits(mag: Dictionary, ammo_id: String) -> bool:
	if WeaponDb.ammo(ammo_id).is_empty():
		return false
	return String(WeaponDb.ammo(ammo_id).get("caliber", "")) == WeaponDb.mag_caliber(String(mag.id))


## Каким патроном снаряжать: тем, что сверху в магазине, если он есть в lists; иначе (и в пустой) —
## подходящим, которого больше всего.
static func pick_ammo(mag: Dictionary, lists: Array) -> String:
	if int(mag.get("rounds", 0)) > 0 and count_of(lists, Gear.mag_top(mag)) > 0:
		return Gear.mag_top(mag)
	var best := ""
	var most := 0
	var counts := {}
	for it in lists:
		var iid := String(it.id)
		if not (it as Dictionary).has("rounds") and ammo_fits(mag, iid):
			counts[iid] = int(counts.get(iid, 0)) + int(it.n)
	for iid in counts:
		if int(counts[iid]) > most:
			most = int(counts[iid])
			best = String(iid)
	return best


static func count_of(lists: Array, ammo_id: String) -> int:
	var n := 0
	for it in lists:
		if String(it.id) == ammo_id and not (it as Dictionary).has("rounds"):
			n += int(it.n)
	return n


## «Нет подходящих патронов. Требуются: … В наличии: …» — lists: всё, что у игрока с собой.
static func no_ammo_text(mag: Dictionary, lists: Array) -> String:
	var need := "патроны %s" % WeaponDb.caliber_name(WeaponDb.mag_caliber(String(mag.id)))
	var have := {}
	for it in lists:
		var iid := String(it.id)
		if not (it as Dictionary).has("rounds") and not WeaponDb.ammo(iid).is_empty():
			have[iid] = int(have.get(iid, 0)) + int(it.n)
	var parts: Array[String] = []
	for iid in have:
		parts.append("%s — %d" % [ItemDb.item_name(String(iid)), int(have[iid])])
	return "Нет подходящих патронов. Требуются: %s. В наличии: %s." % [need, ", ".join(parts) if not parts.is_empty() else "патронов нет"]


## Короткая причина остановки для игрока ("" — сказать нечего: полный / пустой / прервали).
static func reason_text(r: String) -> String:
	match r:
		"no_ammo":
			return "Патроны кончились"
		"no_room":
			return "Некуда класть — нет места ни в ящике, ни в буфере"
		"busy":
			return "С этим уже что-то делают"
	return ""


## Убрать пометки операций (сохранение профиля, вынесенное из рейда).
static func clean(list: Array) -> void:
	for e in list:
		if e is Dictionary:
			(e as Dictionary).erase("op")
