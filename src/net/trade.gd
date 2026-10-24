extends CanvasLayer
## Обмен вещами между игроками (autoload `Trade`) — в убежище и в рейде. Подошёл к напарнику, подержал
## «действие» — у обоих открывается окно: слева рюкзак напарника (только смотреть), справа свой, посередине
## буфер обмена из двух половин — «отдаёт напарник» и «отдаёшь ты». Каждый кладёт в свою половину что
## хочет и жмёт «Передать»; нажали оба — вещи меняются хозяевами. Любая правка буфера снимает готовность
## у обоих: отдать «не то, что видел» нельзя.
##
## В рейде вещи считает хост: буфер — сетка "trade" в Inventory игрока, сделку ведёт Raid (trades,
## request_trade…), окно только показывает и просит. В убежище вещи — в профиле у каждого своего игрока,
## поэтому обмен идёт между двумя peer напрямую: каждый убирает своё и принимает чужое; пока вещь лежит
## в буфере, она вынута из рюкзака в Profile.trade_hold (сохраняется): закрыл окно, вылетел, напарник
## ушёл — возвращается в тайник.

signal changed

## Напарник по обмену в убежище (0 — обмена нет); в рейде — из Raid.trades.
var partner: int = 0
var _offer: Array = []
var _their: Array = []
## Рюкзак напарника в убежище (он присылает его вместе со своей половиной буфера).
var _their_bp: Array = []
var _their_bp_grid: Vector2i = Vector2i(5, 4)
## Подсумки разгрузки напарника в убежище: {"rig": [список, сетка], "dump": […]}.
var _their_rig: Dictionary = {}
## Сетки разгрузки в окне: свои (тащить можно) и напарника (смотреть).
var _own_rig_grids: Dictionary = {}
var _mate_rig_grids: Dictionary = {}
var _ready_me: bool = false
var _ready_them: bool = false
## Ведущий отправил «меняемся» и ждёт подтверждения: буфер заперт.
var _committing: bool = false
var _root: Control
var _mine_grid: GridView
var _their_grid: GridView
var _bp_grid: GridView
var _stash_grid: GridView
var _mate_grid: GridView
var _title: Label
var _mate_title: Label
var _state: Label
var _give: Button
## Окно собрано для этого напарника и этих размеров сеток (сменились — пересобрать).
var _built: String = ""
var _sig: String = ""


func _ready() -> void:
	layer = 22
	add_to_group("esc_windows")
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.visible = false
	add_child(_root)
	multiplayer.peer_disconnected.connect(func(id: int) -> void:
		if id == partner:
			_close(false, "Напарник отключился — обмен отменён"))


func is_open() -> bool:
	return _root.visible


static func grid() -> Vector2i:
	return Vector2i(int(Balance.TRADE.grid[0]), int(Balance.TRADE.grid[1]))


func _raid() -> Raid:
	return Raid.current


## С кем сейчас обмен: в рейде — по записи хоста, в убежище — свой.
func _mate() -> int:
	var raid := _raid()
	if raid:
		var rec: Array = raid.trades.get(multiplayer.get_unique_id(), [])
		return int(rec[0]) if rec.size() >= 2 else 0
	return partner


## Можно ли начать обмен с peer в убежище: оба там, окно не занято.
func can_trade(peer: int) -> bool:
	return Net.is_networked() and partner == 0 and peer != multiplayer.get_unique_id() and Net.visible_in(peer, "hideout") \
		and Net.visible_in(multiplayer.get_unique_id(), "hideout")


## Убежище: предложить обмен игроку peer — окно открывается у обоих. (В рейде — Raid.request_trade.)
func request(peer: int) -> void:
	if not can_trade(peer):
		return
	_open(peer)
	_rpc_invite.rpc_id(peer)
	_send_offer()


@rpc("any_peer", "call_remote", "reliable")
func _rpc_invite() -> void:
	var from := multiplayer.get_remote_sender_id()
	if partner != 0 or not Net.visible_in(multiplayer.get_unique_id(), "hideout") or _busy_elsewhere():
		_rpc_cancel.rpc_id(from, "Напарник занят")
		return
	_open(from)
	_send_offer()


## Открыто другое окно (тайник, торговец, меню) — обмен сейчас не к месту.
func _busy_elsewhere() -> bool:
	if PauseMenu.shown:
		return true
	for n in get_tree().get_nodes_in_group("esc_windows"):
		if n != self and n.has_method("is_open") and bool(n.call("is_open")):
			return true
	return false


func _open(peer: int) -> void:
	partner = peer
	_offer = []
	_their = []
	_their_bp = []
	_ready_me = false
	_ready_them = false
	_committing = false
	Profile.ensure()
	_show()


## Показать окно (обмен уже идёт): собрать и обновить.
func _show() -> void:
	_built = ""
	_sig = ""
	_root.visible = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	Audio.play_ui("bag_open")
	_refresh()
	changed.emit()


func close_ui() -> void:
	if _raid():
		_raid().request_trade_close()
		return
	_close(true, "")


## Убежище: закрыть — своё из буфера обратно в рюкзак (не влезло — в тайник); tell — сказать напарнику.
func _close(tell: bool, why: String) -> void:
	if partner == 0:
		return
	var other := partner
	partner = 0
	_return_offer()
	_hide()
	if tell and Net.is_networked() and other in multiplayer.get_peers():
		_rpc_cancel.rpc_id(other, "Напарник закрыл обмен")
	if why != "":
		_notify(why)
	changed.emit()


func _hide() -> void:
	_root.visible = false
	_built = ""
	for c in _root.get_children():
		c.queue_free()
	Audio.play_ui("bag_close")


@rpc("any_peer", "call_remote", "reliable")
func _rpc_cancel(why: String) -> void:
	if multiplayer.get_remote_sender_id() == partner:
		_close(false, why)


func _return_offer() -> void:
	for e: Dictionary in _offer:
		var one: Dictionary = e.duplicate(true)
		for k in ["x", "y", "r"]:
			one.erase(k)
		if ItemDb.add_to(Profile.backpack, one, Profile.grid_of("backpack")) <= 0:
			ItemDb.add_to(Profile.stash, one, Profile.stash_grid())
	_offer = []
	Profile.trade_hold = []
	Profile.save()


func _notify(text: String) -> void:
	if _raid():
		_raid().notify(text)
		return
	var level := get_tree().get_first_node_in_group("hideout_level")
	if level and level.has_method("notify"):
		level.call("notify", text)


# ---------------------------------------------------------------- данные: рейд (у хоста) или убежище (профиль)

func _my_inv() -> Inventory:
	var me := _raid().local_player() if _raid() else null
	return me.inventory if me else null


func _mate_inv() -> Inventory:
	var pl := _raid().player_of(_mate()) if _raid() else null
	return pl.inventory if pl else null


## Свои сетки: "backpack", "stash" (только убежище), "rig" и "dump" (надетая разгрузка: подсумки и сумка
## сброса), "offer" — своя половина буфера.
func _list(role: String) -> Array:
	if _raid():
		var inv := _my_inv()
		if inv == null:
			return []
		return inv.list_of("trade" if role == "offer" else role)
	return _offer if role == "offer" else Profile.list_of(role)


func _grid(role: String) -> Vector2i:
	if role == "offer":
		return grid()
	if _raid():
		return _my_inv().grid_of(role) if _my_inv() else Vector2i(5, 4)
	return Profile.grid_of(role)


## Разгрузка напарника: что лежит в подсумках / сумке сброса и какая у них сетка (ZERO — нет).
func _their_rig_list(part: String) -> Array:
	if _raid():
		return _mate_inv().list_of(part) if _mate_inv() else []
	return (_their_rig.get(part, [[], Vector2i.ZERO]) as Array)[0]


func _their_rig_grid(part: String) -> Vector2i:
	if _raid():
		return _mate_inv().grid_of(part) if _mate_inv() else Vector2i.ZERO
	return (_their_rig.get(part, [[], Vector2i.ZERO]) as Array)[1]


func _their_offer() -> Array:
	if _raid():
		return _mate_inv().trade if _mate_inv() else []
	return _their


func _their_backpack() -> Array:
	if _raid():
		return _mate_inv().items if _mate_inv() else []
	return _their_bp


func _their_backpack_grid() -> Vector2i:
	if _raid():
		return _mate_inv().backpack_grid() if _mate_inv() else Vector2i(5, 4)
	return _their_bp_grid


func _ready_of(mine: bool) -> bool:
	if _raid():
		var rec: Array = _raid().trades.get(multiplayer.get_unique_id() if mine else _mate(), [])
		return rec.size() >= 2 and bool(rec[1])
	return _ready_me if mine else _ready_them


# ---------------------------------------------------------------- окно

func _build() -> void:
	for c in _root.get_children():
		c.queue_free()
	var raid := _raid() != null
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.5)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(dim)
	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_FULL_RECT)
	panel.offset_left = 50
	panel.offset_right = -50
	panel.offset_top = 50
	panel.offset_bottom = -50
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.07, 0.065, 0.06, 0.95)
	sb.border_color = Color(0.95, 0.78, 0.5, 0.35)
	sb.set_border_width_all(1)
	sb.set_content_margin_all(18)
	panel.add_theme_stylebox_override("panel", sb)
	_root.add_child(panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 10)
	panel.add_child(v)
	var head := HBoxContainer.new()
	v.add_child(head)
	_title = _label("", 26, Color(1.0, 0.86, 0.6))
	_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(_title)
	var close := Button.new()
	close.text = "Отменить обмен (Esc)"
	close.focus_mode = Control.FOCUS_NONE
	close.pressed.connect(close_ui)
	head.add_child(close)
	var cols := HBoxContainer.new()
	cols.add_theme_constant_override("separation", 22)
	cols.size_flags_vertical = Control.SIZE_EXPAND_FILL
	v.add_child(cols)
	# слева — рюкзак напарника: только смотреть
	var left := _side(cols)
	_mate_title = _label("", 18, Color(0.6, 0.85, 1.0))
	left.add_child(_mate_title)
	_mate_grid = GridView.new(_their_backpack_grid(), "mate")
	_mate_grid.drag_enabled = false
	left.add_child(_mate_grid)
	# его разгрузка: подсумки с магазинами и сумка сброса
	_mate_rig_grids = {}
	for part: Array in [["rig", "Его подсумки"], ["dump", "Его сброс пустых"]]:
		var g1: Vector2i = _their_rig_grid(String(part[0]))
		if g1 == Vector2i.ZERO:
			continue
		left.add_child(_label(String(part[1]), 15, Color(0.6, 0.85, 1.0)))
		var gv1 := GridView.new(g1, "mate_" + String(part[0]))
		gv1.drag_enabled = false
		left.add_child(gv1)
		_mate_rig_grids[String(part[0])] = gv1
	var look := _label("Чужие вещи — только посмотреть. Напарник сам кладёт в буфер то, что отдаёт.", 13, Color(0.6, 0.62, 0.6))
	look.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	left.add_child(look)
	# посередине — буфер обмена: половина напарника сверху, своя снизу
	var mid := VBoxContainer.new()
	mid.add_theme_constant_override("separation", 6)
	cols.add_child(mid)
	mid.add_child(_label("Отдаёт напарник", 18, Color(0.6, 0.85, 1.0)))
	_their_grid = GridView.new(grid(), "their")
	_their_grid.drag_enabled = false
	mid.add_child(_their_grid)
	mid.add_child(_label("Отдаёшь ты", 18, Color(1.0, 0.86, 0.6)))
	_mine_grid = GridView.new(grid(), "offer")
	mid.add_child(_mine_grid)
	_state = _label("", 16, Color(0.8, 0.82, 0.78))
	_state.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_state.custom_minimum_size.x = float(grid().x) * GridView.CELL
	mid.add_child(_state)
	_give = Button.new()
	_give.focus_mode = Control.FOCUS_NONE
	_give.toggle_mode = true
	_give.custom_minimum_size.y = 44
	_give.add_theme_font_size_override("font_size", 20)
	_give.toggled.connect(_set_ready)
	mid.add_child(_give)
	var hint := _label("Тащи свои вещи мышью в нижнюю половину. Двойной клик — туда и обратно. Обмен пройдёт, когда «Передать» нажали оба. Поменял что-то — готовность снимается у обоих.", 13, Color(0.6, 0.62, 0.6))
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.custom_minimum_size.x = float(grid().x) * GridView.CELL
	mid.add_child(hint)
	# справа — свои вещи
	var right := _side(cols)
	right.add_child(_label("Твой рюкзак", 18, Color(0.95, 0.82, 0.6)))
	_bp_grid = GridView.new(_grid("backpack"), "backpack")
	right.add_child(_bp_grid)
	var own: Array[GridView] = [_bp_grid, _mine_grid]
	# своя разгрузка: магазины из подсумков отдаются прямо отсюда
	_own_rig_grids = {}
	for part: Array in [["rig", "Твои подсумки — магазины"], ["dump", "Твой сброс пустых"]]:
		var g2: Vector2i = _grid(String(part[0]))
		if g2 == Vector2i.ZERO:
			continue
		right.add_child(_label(String(part[1]), 15, Color(0.95, 0.82, 0.6)))
		var gv2 := GridView.new(g2, String(part[0]))
		right.add_child(gv2)
		own.append(gv2)
		_own_rig_grids[String(part[0])] = gv2
	_stash_grid = null
	if not raid:
		right.add_child(_label("Твой тайник", 18, Color(0.95, 0.82, 0.6)))
		_stash_grid = GridView.new(Profile.stash_grid(), "stash")
		right.add_child(_stash_grid)
		own.append(_stash_grid)
	# перетаскивание: между своими сетками и своей половиной буфера
	for g: GridView in own:
		var dst: String = g.role
		g.dropped.connect(func(src: GridView, idx: int, x: int, y: int, r: bool) -> void: _move(src.role, idx, dst, x, y, r))
		g.quick_move.connect(func(idx: int) -> void: _quick(dst, idx))
		g.activated.connect(func(idx: int) -> void: _quick(dst, idx))


## Боковая колонка с прокруткой; возвращает список, куда класть строки.
func _side(cols: HBoxContainer) -> VBoxContainer:
	var scroll := ScrollContainer.new()
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	cols.add_child(scroll)
	var box := VBoxContainer.new()
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_theme_constant_override("separation", 6)
	scroll.add_child(box)
	return box


func _label(text: String, size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l


## Перенести запись между своими сетками (рюкзак, тайник, своя половина буфера).
func _move(src: String, idx: int, dst: String, x: int, y: int, r: bool) -> void:
	var from := _list(src)
	var roles := ["backpack", "stash", "offer", "rig", "dump"]
	if idx < 0 or idx >= from.size() or not src in roles or not dst in roles:
		return
	if dst in ["rig", "dump"] and not ItemDb.grid_accepts(dst, from[idx]):
		_notify("В подсумки — только магазины")
		return
	if _raid():
		# в рейде перекладывает хост (сетка "trade" рюкзака игрока, подсумки — "rig" / "dump")
		var role := {"offer": "trade", "backpack": "backpack", "rig": "rig", "dump": "dump"}
		if role.has(src) and role.has(dst):
			_raid().request_grid_move(String(role[src]), idx, String(role[dst]), x, y, r)
		return
	if _committing:
		return
	if src == dst:
		if ItemDb.move_in(from, _grid(src), idx, x, y, r):
			_touched(src == "offer")
		return
	var e: Dictionary = (from[idx] as Dictionary).duplicate(true)
	var k := ItemDb.put_at(_list(dst), e, _grid(dst), x, y, r) if x >= 0 else ItemDb.add_to(_list(dst), _bare(e), _grid(dst))
	if k <= 0:
		_notify("Сюда не влезает")
		return
	ItemDb.remove_at(from, idx, k)
	_touched(src == "offer" or dst == "offer")


func _bare(e: Dictionary) -> Dictionary:
	for k in ["x", "y", "r"]:
		e.erase(k)
	return e


## Двойной клик: из рюкзака / тайника / подсумков — в буфер, из буфера — в рюкзак (в убежище нет места — в тайник).
func _quick(role: String, idx: int) -> void:
	if role == "offer":
		var before := _list("offer").size()
		_move("offer", idx, "backpack", -1, -1, false)
		if not _raid() and _offer.size() == before:
			_move("offer", idx, "stash", -1, -1, false)
	else:
		_move(role, idx, "offer", -1, -1, false)


## Убежище: что-то переложили — сохранить; напарнику — новая половина и рюкзак; тронули буфер —
## готовность снята у обоих.
func _touched(offer_changed: bool) -> void:
	Profile.trade_hold = _offer.duplicate(true)
	Profile.save()
	if offer_changed:
		_ready_me = false
		_ready_them = false
	_send_offer()
	_refresh()


## Убежище: своя половина буфера, свой рюкзак и разгрузка — напарнику (он видит их слева).
func _send_offer() -> void:
	if partner in multiplayer.get_peers():
		var rig := {}
		for part: String in ["rig", "dump"]:
			if Profile.grid_of(part) != Vector2i.ZERO:
				rig[part] = [Profile.list_of(part), Profile.grid_of(part)]
		_rpc_offer.rpc_id(partner, _offer, Profile.backpack, Profile.grid_of("backpack"), rig)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_offer(list: Array, backpack: Array = [], backpack_grid: Vector2i = Vector2i(5, 4), rig: Dictionary = {}) -> void:
	if multiplayer.get_remote_sender_id() != partner:
		return
	if str(_stripped(list)) != str(_stripped(_their)):
		_ready_me = false
		_ready_them = false
		_committing = false
	_their = list.duplicate(true)
	_their_bp = backpack.duplicate(true)
	_their_bp_grid = backpack_grid
	_their_rig = rig.duplicate(true)
	_refresh()


func _set_ready(on: bool) -> void:
	if _raid():
		if on != _ready_of(true):
			_raid().request_trade_ready(on)
		return
	if on == _ready_me or partner == 0 or _committing:
		_refresh()
		return
	if on and _room_for(_their) < _their.size():
		_notify("Не поместится: освободи место в рюкзаке или тайнике")
		_refresh()
		return
	_ready_me = on
	if partner in multiplayer.get_peers():
		_rpc_ready.rpc_id(partner, on, _print(_offer, _their))
	_refresh()
	_try_commit()


## Отпечаток сделки глазами одного игрока: (что отдаю, что получаю).
func _print(give: Array, take: Array) -> String:
	return str(_stripped(give)).md5_text() + ":" + str(_stripped(take)).md5_text()


## Записи без места в сетке (у каждого своя раскладка) — для сверки.
func _stripped(list: Array) -> Array:
	var out: Array = []
	for e: Dictionary in list:
		out.append(_bare(e.duplicate(true)))
	return out


@rpc("any_peer", "call_remote", "reliable")
func _rpc_ready(on: bool, their_print: String) -> void:
	if multiplayer.get_remote_sender_id() != partner:
		return
	# напарник видит сделку так же, как я: его «отдаю» — моё «получаю»
	if on and their_print != _print(_their, _offer):
		_ready_them = false
		_send_offer()
	else:
		_ready_them = on
	_refresh()
	_try_commit()


## Убежище: оба готовы — обмен ведёт тот, у кого номер peer меньше: говорит второму «меняемся», тот
## меняет у себя и подтверждает, и только тогда ведущий меняет у себя (второй передумал — вместо
## подтверждения придёт его новая половина, и всё начнётся заново).
func _try_commit() -> void:
	if not (_ready_me and _ready_them) or partner == 0 or _committing or multiplayer.get_unique_id() > partner:
		return
	_committing = true
	_rpc_commit.rpc_id(partner, _print(_offer, _their))


@rpc("any_peer", "call_remote", "reliable")
func _rpc_commit(their_print: String) -> void:
	var from := multiplayer.get_remote_sender_id()
	if from != partner:
		return
	if not _ready_me or their_print != _print(_their, _offer):
		# уже передумал или видим сделку по-разному — заново
		_ready_me = false
		_ready_them = false
		_send_offer()
		_refresh()
		return
	_commit()
	_rpc_committed.rpc_id(from)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_committed() -> void:
	if multiplayer.get_remote_sender_id() == partner and _committing:
		_commit()


## Сколько записей из list поместится в рюкзак и тайник.
func _room_for(list: Array) -> int:
	var bp: Array = Profile.backpack.duplicate(true)
	var st: Array = Profile.stash.duplicate(true)
	var n := 0
	for e: Dictionary in list:
		var one := _bare(e.duplicate(true))
		if ItemDb.add_to(bp, one, Profile.grid_of("backpack")) >= int(one.get("n", 1)) or ItemDb.add_to(st, one, Profile.stash_grid()) >= int(one.get("n", 1)):
			n += 1
	return n


## Убежище, обмен: моя половина уходит (она уже вынута из вещей), чужая — в рюкзак, не влезло — в тайник.
func _commit() -> void:
	var got: Array[String] = []
	for e: Dictionary in _their:
		var one := _bare(e.duplicate(true))
		var left := int(one.get("n", 1)) - ItemDb.add_to(Profile.backpack, one, Profile.grid_of("backpack"))
		if left > 0:
			one["n"] = left
			ItemDb.add_to(Profile.stash, one, Profile.stash_grid())
		got.append(ItemDb.label(e))
	var gave := _offer.size()
	_committing = false
	_offer = []
	_their = []
	Profile.trade_hold = []
	Profile.save()
	Audio.play_ui("cash")
	var other := partner
	partner = 0
	_hide()
	_notify("Обмен с %s: отдал %d, получил %d%s" % [String(Net.player_names.get(other, "напарником")), gave, got.size(), (" — " + ", ".join(got.slice(0, 3))) if not got.is_empty() else ""])
	changed.emit()


func _refresh() -> void:
	var mate := _mate()
	if mate == 0 or not _root.visible:
		return
	# сетки поменяли размер (другой рюкзак) или другой напарник — окно собирается заново
	var shape := "%d|%s|%s|%s" % [mate, str(_their_backpack_grid()), str(_grid("backpack")), str(_raid() != null)]
	for part: String in ["rig", "dump"]:
		shape += "|%s|%s" % [str(_grid(part)), str(_their_rig_grid(part))]
	if shape != _built or _mine_grid == null or not is_instance_valid(_mine_grid):
		_built = shape
		_build()
	var who := String(Net.player_names.get(mate, "Игрок %d" % mate))
	_title.text = "Обмен с игроком %s" % who
	_mate_title.text = "Рюкзак: %s" % who
	_mate_grid.set_items(_their_backpack())
	_bp_grid.set_items(_list("backpack"))
	if _stash_grid:
		_stash_grid.set_items(Profile.stash)
	_mine_grid.set_items(_list("offer"))
	_their_grid.set_items(_their_offer())
	for part: String in _own_rig_grids:
		(_own_rig_grids[part] as GridView).set_items(_list(part))
	for part: String in _mate_rig_grids:
		(_mate_rig_grids[part] as GridView).set_items(_their_rig_list(part))
	var me_ready := _ready_of(true)
	var mate_ready := _ready_of(false)
	_give.set_pressed_no_signal(me_ready)
	_give.text = "Готов — ждём напарника…" if me_ready else "Передать"
	_give.disabled = _list("offer").is_empty() and _their_offer().is_empty()
	_state.text = "Напарник: %s   ·   Ты: %s" % ["готов ✓" if mate_ready else "ещё выбирает", "готов ✓" if me_ready else "ещё выбираешь"]
	_state.add_theme_color_override("font_color", Color(0.5, 0.95, 0.6) if mate_ready else Color(0.8, 0.82, 0.78))


func _process(_delta: float) -> void:
	# убежище: сам ушёл (начался рейд, вышел в меню) посреди обмена — своё вернуть, напарнику сказать
	if partner != 0 and not Net.visible_in(multiplayer.get_unique_id(), "hideout"):
		_close(true, "")
	var raid := _raid()
	if raid:
		# рейд: окно следует за записью хоста — появилась сделка, открыть; пропала — закрыть
		var mate := _mate()
		if mate != 0 and not _root.visible:
			_show()
		elif mate == 0 and _root.visible:
			_hide()
			changed.emit()
		if mate == 0:
			return
		if Input.is_action_just_pressed("ui_cancel") and not ItemInfo.blocking():
			close_ui()
			return
		var inv := _my_inv()
		var other := _mate_inv()
		var sig := "%s|%s|%s|%s|%s" % [str(inv.items) if inv else "", str(inv.trade) if inv else "", str(other.items) if other else "", str(other.trade) if other else "", str(raid.trades)]
		# подсумки обоих — на броне в снаряжении
		sig += "|%s|%s" % [str(inv.equipment.get("armor", {})) if inv else "", str(other.equipment.get("armor", {})) if other else ""]
		if sig != _sig:
			_sig = sig
			_refresh()
		return
	if partner == 0 or not _root.visible:
		return
	if Input.is_action_just_pressed("ui_cancel") and not ItemInfo.blocking():
		close_ui()
		return
	# напарник ушёл из убежища или его не стало — обмен отменяется
	if not partner in multiplayer.get_peers() or not Net.visible_in(partner, "hideout"):
		_close(false, "Напарник ушёл — обмен отменён")
