extends CanvasLayer
## Обмен вещами между игроками в убежище (autoload `Trade`). Подошёл к напарнику, подержал «действие» —
## у обоих открывается окно: слева свои вещи (рюкзак и тайник), посередине большой буфер обмена из двух
## половин — «ты отдаёшь» и «тебе отдают». Каждый кладёт в свою половину что хочет и жмёт «Передать»;
## когда нажали оба — вещи меняются хозяевами. Любая правка буфера снимает готовность у обоих: отдать
## «не то, что видел» нельзя (перед обменом сверяется отпечаток обеих половин).
##
## Вещи в убежище — в профиле у каждого своего игрока, поэтому обмен идёт между двумя peer напрямую,
## без хоста: каждый убирает своё и принимает чужое. Пока вещь лежит в буфере, она вынута из рюкзака в
## Profile.trade_hold (сохраняется): закрыл окно, вылетел, напарник ушёл — возвращается в тайник.
## В рейде обмена нет: там вещь выбрасывают из рюкзака, и напарник её подбирает.

signal changed

## Сетка одной половины буфера.
const GRID := Vector2i(8, 5)

var partner: int = 0
var _offer: Array = []
var _their: Array = []
var _ready_me: bool = false
var _ready_them: bool = false
## Ведущий отправил «меняемся» и ждёт подтверждения: буфер заперт.
var _committing: bool = false
var _root: Control
var _mine_grid: GridView
var _their_grid: GridView
var _bp_grid: GridView
var _stash_grid: GridView
var _title: Label
var _state: Label
var _give: Button
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


## Можно ли начать обмен с peer: оба в убежище, окно не занято.
func can_trade(peer: int) -> bool:
	return Net.is_networked() and partner == 0 and peer != multiplayer.get_unique_id() and Net.visible_in(peer, "hideout") \
		and Net.visible_in(multiplayer.get_unique_id(), "hideout")


## Предложить обмен игроку peer: окно открывается у обоих.
func request(peer: int) -> void:
	if not can_trade(peer):
		return
	_open(peer)
	_rpc_invite.rpc_id(peer)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_invite() -> void:
	var from := multiplayer.get_remote_sender_id()
	if partner != 0 or not Net.visible_in(multiplayer.get_unique_id(), "hideout") or _busy_elsewhere():
		_rpc_cancel.rpc_id(from, "Напарник занят")
		return
	_open(from)


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
	_ready_me = false
	_ready_them = false
	_committing = false
	Profile.ensure()
	_build()
	_root.visible = true
	_sig = ""
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	Audio.play_ui("bag_open")
	changed.emit()


func close_ui() -> void:
	_close(true, "")


## Закрыть: своё из буфера — обратно в рюкзак (не влезло — в тайник); tell — сказать напарнику.
func _close(tell: bool, why: String) -> void:
	if partner == 0:
		return
	var other := partner
	partner = 0
	_return_offer()
	_root.visible = false
	for c in _root.get_children():
		c.queue_free()
	if tell and Net.is_networked() and other in multiplayer.get_peers():
		_rpc_cancel.rpc_id(other, "Напарник закрыл обмен")
	if why != "":
		_notify(why)
	Audio.play_ui("bag_close")
	changed.emit()


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
	var level := get_tree().get_first_node_in_group("hideout_level")
	if level and level.has_method("notify"):
		level.call("notify", text)


# ---------------------------------------------------------------- окно

func _build() -> void:
	for c in _root.get_children():
		c.queue_free()
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
	# слева — свои вещи
	var left_scroll := ScrollContainer.new()
	left_scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	cols.add_child(left_scroll)
	var left := VBoxContainer.new()
	left.add_theme_constant_override("separation", 6)
	left_scroll.add_child(left)
	left.add_child(_label("Твой рюкзак", 18, Color(0.95, 0.82, 0.6)))
	_bp_grid = GridView.new(Profile.grid_of("backpack"), "backpack")
	left.add_child(_bp_grid)
	left.add_child(_label("Твой тайник", 18, Color(0.95, 0.82, 0.6)))
	_stash_grid = GridView.new(Profile.stash_grid(), "stash")
	left.add_child(_stash_grid)
	# посередине — буфер обмена: две половины
	var mid := VBoxContainer.new()
	mid.add_theme_constant_override("separation", 6)
	cols.add_child(mid)
	mid.add_child(_label("Ты отдаёшь", 18, Color(1.0, 0.86, 0.6)))
	_mine_grid = GridView.new(GRID, "offer")
	mid.add_child(_mine_grid)
	mid.add_child(_label("Тебе отдают", 18, Color(0.6, 0.85, 1.0)))
	_their_grid = GridView.new(GRID, "their")
	_their_grid.drag_enabled = false
	mid.add_child(_their_grid)
	_state = _label("", 16, Color(0.8, 0.82, 0.78))
	_state.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_state.custom_minimum_size.x = float(GRID.x) * GridView.CELL
	mid.add_child(_state)
	_give = Button.new()
	_give.focus_mode = Control.FOCUS_NONE
	_give.toggle_mode = true
	_give.custom_minimum_size.y = 44
	_give.add_theme_font_size_override("font_size", 20)
	_give.toggled.connect(_set_ready)
	mid.add_child(_give)
	var hint := _label("Тащи вещи мышью в верхнюю половину. Двойной клик — туда и обратно. Обмен пройдёт, когда «Передать» нажали оба. Поменял что-то — готовность снимается у обоих.", 13, Color(0.6, 0.62, 0.6))
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.custom_minimum_size.x = float(GRID.x) * GridView.CELL
	mid.add_child(hint)
	# перетаскивание: между своими сетками и своей половиной буфера
	for g: GridView in [_bp_grid, _stash_grid, _mine_grid]:
		var dst: String = g.role
		g.dropped.connect(func(src: GridView, idx: int, x: int, y: int, r: bool) -> void: _move(src.role, idx, dst, x, y, r))
		g.quick_move.connect(func(idx: int) -> void: _quick(dst, idx))
		g.activated.connect(func(idx: int) -> void: _quick(dst, idx))
	_refresh()


func _label(text: String, size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l


func _list(role: String) -> Array:
	return _offer if role == "offer" else Profile.list_of(role)


func _grid(role: String) -> Vector2i:
	return GRID if role == "offer" else Profile.grid_of(role)


## Перенести запись между своими сетками (рюкзак, тайник, своя половина буфера).
func _move(src: String, idx: int, dst: String, x: int, y: int, r: bool) -> void:
	var from := _list(src)
	if _committing or idx < 0 or idx >= from.size() or not src in ["backpack", "stash", "offer"] or not dst in ["backpack", "stash", "offer"]:
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


## Двойной клик: из рюкзака / тайника — в буфер, из буфера — в рюкзак (нет места — в тайник).
func _quick(role: String, idx: int) -> void:
	if role == "offer":
		var before := _offer.size()
		_move("offer", idx, "backpack", -1, -1, false)
		if _offer.size() == before:
			_move("offer", idx, "stash", -1, -1, false)
	else:
		_move(role, idx, "offer", -1, -1, false)


## Что-то переложили: сохранить; если тронули буфер — готовность снята у обоих, напарнику — новая половина.
func _touched(offer_changed: bool) -> void:
	Profile.trade_hold = _offer.duplicate(true)
	Profile.save()
	if offer_changed:
		_ready_me = false
		_ready_them = false
		if partner in multiplayer.get_peers():
			_rpc_offer.rpc_id(partner, _offer)
	_refresh()


@rpc("any_peer", "call_remote", "reliable")
func _rpc_offer(list: Array) -> void:
	if multiplayer.get_remote_sender_id() != partner:
		return
	_their = list.duplicate(true)
	_ready_me = false
	_ready_them = false
	_committing = false
	_refresh()


func _set_ready(on: bool) -> void:
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
		_rpc_offer.rpc_id(partner, _offer)
	else:
		_ready_them = on
	_refresh()
	_try_commit()


## Оба готовы — обмен ведёт тот, у кого номер peer меньше: говорит второму «меняемся», тот меняет у
## себя и подтверждает, и только тогда ведущий меняет у себя (второй передумал — вместо подтверждения
## придёт его новая половина, и всё начнётся заново).
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
		_rpc_offer.rpc_id(from, _offer)
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


## Обмен: моя половина уходит (она уже вынута из вещей), чужая — в рюкзак, не влезло — в тайник.
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
	_root.visible = false
	for c in _root.get_children():
		c.queue_free()
	_notify("Обмен с %s: отдал %d, получил %d%s" % [String(Net.player_names.get(other, "напарником")), gave, got.size(), (" — " + ", ".join(got.slice(0, 3))) if not got.is_empty() else ""])
	changed.emit()


func _refresh() -> void:
	if partner == 0 or not _root.visible or _mine_grid == null or not is_instance_valid(_mine_grid):
		return
	_title.text = "Обмен с игроком %s" % String(Net.player_names.get(partner, "Игрок %d" % partner))
	_bp_grid.set_items(Profile.backpack)
	_stash_grid.set_items(Profile.stash)
	_mine_grid.set_items(_offer)
	_their_grid.set_items(_their)
	_give.set_pressed_no_signal(_ready_me)
	_give.text = "Готов — ждём напарника…" if _ready_me else "Передать"
	_give.disabled = _offer.is_empty() and _their.is_empty()
	_state.text = "Напарник: %s   ·   Ты: %s" % ["готов ✓" if _ready_them else "ещё выбирает", "готов ✓" if _ready_me else "ещё выбираешь"]
	_state.add_theme_color_override("font_color", Color(0.5, 0.95, 0.6) if _ready_them else Color(0.8, 0.82, 0.78))


func _process(_delta: float) -> void:
	if partner == 0 or not _root.visible:
		return
	if Input.is_action_just_pressed("ui_cancel") and not ItemInfo.blocking():
		close_ui()
		return
	# напарник ушёл из убежища или его не стало — обмен отменяется
	if not partner in multiplayer.get_peers() or not Net.visible_in(partner, "hideout"):
		_close(false, "Напарник ушёл — обмен отменён")
