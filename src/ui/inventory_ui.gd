class_name InventoryUI
extends CanvasLayer
## Рюкзак и обыск — у каждого peer свой, для своего игрока. Tab — рюкзак; F у контейнера —
## обыск (полоска search_s, отошёл — сорвался), потом окно: «взять» по предмету или «взять всё».
## H — полечиться самым подходящим из рюкзака. Сами изменения делает хост (Raid.request_*),
## окно только показывает реплицированные списки и шлёт просьбы.

const PANEL_W := 460.0

var _backpack_open: bool = false
var _searching: LootContainer
var _search_t: float = 0.0
var _looting: LootContainer
## Уже обысканные этим игроком контейнеры — второй раз окно открывается сразу.
var _searched: Dictionary = {}
var _heal_t: float = 0.0
var _heal_total: float = 0.0

var _bp_panel: PanelContainer
var _bp_title: Label
var _bp_list: VBoxContainer
var _loot_panel: PanelContainer
var _loot_title: Label
var _loot_list: VBoxContainer
var _take_all: Button
var _bar: ProgressBar
var _bar_label: Label
var _bp_sig: String = ""
var _bp_grid: GridView
var _loot_sig: String = ""


## 34500 -> «34 500».
static func money(v: int) -> String:
	var s := str(absi(v))
	var out := ""
	while s.length() > 3:
		out = " " + s.substr(s.length() - 3) + out
		s = s.substr(0, s.length() - 3)
	return ("-" if v < 0 else "") + s + out


func _ready() -> void:
	layer = 12
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	var bp := _panel(root, -PANEL_W - 24.0, -24.0)
	_bp_panel = bp[0]
	_bp_title = bp[1]
	_bp_list = bp[2]
	var lp := _panel(root, -PANEL_W * 2.0 - 40.0, -PANEL_W - 40.0)
	_loot_panel = lp[0]
	_loot_title = lp[1]
	_loot_list = lp[2]
	_take_all = Button.new()
	_take_all.text = "Взять всё"
	_take_all.pressed.connect(func() -> void:
		if _looting:
			Raid.current.request_take_all(_looting))
	(_loot_panel.get_child(0) as VBoxContainer).add_child(_take_all)
	_bar = ProgressBar.new()
	_bar.show_percentage = false
	_bar.anchor_left = 0.5
	_bar.anchor_right = 0.5
	_bar.anchor_top = 0.5
	_bar.anchor_bottom = 0.5
	_bar.offset_left = -160
	_bar.offset_right = 160
	_bar.offset_top = 70
	_bar.offset_bottom = 82
	_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var fill := StyleBoxFlat.new()
	fill.bg_color = Color(1.0, 0.82, 0.45)
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0, 0, 0, 0.55)
	_bar.add_theme_stylebox_override("fill", fill)
	_bar.add_theme_stylebox_override("background", bg)
	root.add_child(_bar)
	_bar_label = Label.new()
	_bar_label.anchor_left = 0.5
	_bar_label.anchor_right = 0.5
	_bar_label.anchor_top = 0.5
	_bar_label.anchor_bottom = 0.5
	_bar_label.offset_left = -300
	_bar_label.offset_right = 300
	_bar_label.offset_top = 40
	_bar_label.offset_bottom = 66
	_bar_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_bar_label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	_bar_label.add_theme_constant_override("outline_size", 6)
	_bar_label.add_theme_font_size_override("font_size", 20)
	_bar_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(_bar_label)
	_refresh_visibility()


func is_open() -> bool:
	return _backpack_open or _looting != null


func is_looting() -> bool:
	return _searching != null or _looting != null


## F у контейнера: обыск (уже обысканный — сразу окно).
func start_search(c: LootContainer) -> void:
	if _searched.has(c.get_path()):
		_open_loot(c)
		return
	_searching = c
	_search_t = 0.0


func close_all() -> void:
	_backpack_open = false
	_searching = null
	_looting = null
	_refresh_visibility()


func _open_loot(c: LootContainer) -> void:
	_searching = null
	_looting = c
	_backpack_open = true
	_loot_sig = ""
	_refresh_visibility()


func _process(delta: float) -> void:
	var raid := Raid.current
	var me := raid.local_player() if raid else null
	if me == null or not me.is_alive() or raid.is_extracted(me.peer_id):
		if is_open() or _searching:
			close_all()
		_bar.visible = false
		_bar_label.visible = false
		return
	if Input.is_action_just_pressed("inventory"):
		_backpack_open = not _backpack_open
		if not _backpack_open:
			_looting = null
		_refresh_visibility()
	if Input.is_action_just_pressed("ui_cancel") and is_open():
		close_all()
	if Input.is_action_just_pressed("use_med"):
		_try_heal(me)
	_tick_search(me, delta)
	# отошёл от контейнера — окно закрывается
	if _looting and (not is_instance_valid(_looting) or _looting.global_position.distance_to(me.global_position) > Balance.INTERACT_RADIUS + 1.0):
		_looting = null
		_refresh_visibility()
	_tick_heal(delta)
	_refresh_lists(me)


func _tick_search(me: Player, delta: float) -> void:
	if _searching == null:
		if _heal_t <= 0.0:
			_bar.visible = false
			_bar_label.visible = false
		return
	if not is_instance_valid(_searching) or _searching.global_position.distance_to(me.global_position) > Balance.INTERACT_RADIUS + 0.5:
		_searching = null
		return
	_search_t += delta
	_bar.visible = true
	_bar_label.visible = true
	_bar.max_value = _searching.search_s
	_bar.value = _search_t
	_bar_label.text = "Обыск: " + _searching.display_name
	if _search_t >= _searching.search_s:
		_searched[_searching.get_path()] = true
		_open_loot(_searching)


## Самое подходящее лекарство: не больше, чем нужно (аптечка — если не хватает много).
func _try_heal(me: Player) -> void:
	if _heal_t > 0.0 or me.health.hp >= me.health.max_hp:
		return
	var missing := me.health.max_hp - me.health.hp
	var best := ""
	var best_score := INF
	for it in me.inventory.items:
		var use: Dictionary = ItemDb.item(String(it.id)).get("use", {})
		if use.is_empty():
			continue
		var score := absf(float(use.heal) - missing)
		if score < best_score:
			best_score = score
			best = String(it.id)
	if best == "":
		Raid.current.notify("Нечем лечиться")
		return
	var use: Dictionary = ItemDb.item(best).use
	Raid.current.request_use_med(best)
	_heal_total = float(use.time)
	_heal_t = _heal_total
	_bar_label.text = "Лечение: " + ItemDb.item_name(best)


func _tick_heal(delta: float) -> void:
	if _heal_t <= 0.0:
		return
	_heal_t -= delta
	if _searching == null:
		_bar.visible = true
		_bar_label.visible = true
		_bar.max_value = _heal_total
		_bar.value = _heal_total - _heal_t


func _refresh_visibility() -> void:
	_bp_panel.visible = _backpack_open
	_loot_panel.visible = _looting != null
	_bp_sig = ""
	_loot_sig = ""


## Сетки перестраиваются, только когда содержимое изменилось.
func _refresh_lists(me: Player) -> void:
	if _backpack_open:
		var sig := str(me.inventory.items) + str(me.inventory.equipment) + str(me.inventory.pocket)
		if sig != _bp_sig:
			_bp_sig = sig
			_bp_title.text = "Рюкзак   %d / %d ячеек   ·   %s ₽" % [me.inventory.cells_used(), Balance.BACKPACK_CELLS, money(me.inventory.value())]
			_clear(_bp_list)
			# снаряжение: в слот тащат из рюкзака (надеть / взять в руки)
			var slots := GridContainer.new()
			slots.columns = 2
			_bp_list.add_child(slots)
			for slot in Inventory.SLOTS:
				var sv := SlotView.new(String(slot))
				sv.custom_minimum_size = Vector2(3.0 * GridView.CELL, 1.5 * GridView.CELL)
				sv.set_entry(me.inventory.equipment.get(slot, {}))
				var ws := String(slot)
				sv.equip_from.connect(func(src: GridView, idx: int) -> void:
					if src.role == "backpack":
						Raid.current.request_equip(idx))
				# обвес прямо в рейде: бросил на оружие — поставил (что умеет твой верстак)
				sv.mod_from.connect(func(src: GridView, idx: int) -> void:
					if src.role not in ["backpack", "pocket"]:
						return
					var list: Array = me.inventory.pocket if src.role == "pocket" else me.inventory.items
					if idx >= list.size():
						return
					var why := Profile.mod_block(String(list[idx].id))
					if why != "":
						Raid.current.notify("Не поставить: " + why)
					else:
						Raid.current.request_install_mod(ws, src.role, idx))
				sv.context.connect(func(at: Vector2) -> void: _mods_menu(me, ws, at))
				slots.add_child(sv)
			_bp_grid = GridView.new(Balance.BACKPACK_GRID, "backpack")
			_bp_grid.set_items(me.inventory.items)
			_bp_list.add_child(_bp_grid)
			var hint := _row_label("Тащи мышью · R — повернуть · двойной клик — надеть / лечиться · правая кнопка — действия", Color(0.6, 0.62, 0.6))
			hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			hint.add_theme_font_size_override("font_size", 13)
			_bp_list.add_child(hint)
			var grids: Array[GridView] = [_bp_grid]
			# защищённый карман: что в нём — не выпадет при смерти
			if me.inventory.pocket_grid != Vector2i.ZERO:
				var pl := _row_label("Защищённый карман — не теряется при смерти", Color(0.95, 0.82, 0.6))
				pl.add_theme_font_size_override("font_size", 14)
				_bp_list.add_child(pl)
				var pk := GridView.new(me.inventory.pocket_grid, "pocket")
				pk.set_items(me.inventory.pocket)
				_bp_list.add_child(pk)
				grids.append(pk)
			for g in grids:
				var dst := g.role
				g.dropped.connect(func(src: GridView, idx: int, x: int, y: int, r: bool) -> void:
					if src.role == "loot" and _looting:
						Raid.current.request_take_to(_looting, idx, x, y, r, dst)
					elif src.role in ["backpack", "pocket"]:
						Raid.current.request_grid_move(src.role, idx, dst, x, y, r))
			_bp_grid.activated.connect(func(idx: int) -> void: _use_item(me, idx))
			_bp_grid.quick_move.connect(func(idx: int) -> void:
				if _looting:
					Raid.current.request_put(_looting, idx))
			_bp_grid.context.connect(func(idx: int, at: Vector2) -> void: _backpack_menu(me, idx, at))
	if _looting:
		var sig2 := str(_looting.items) + str(_looting.rolled)
		if sig2 != _loot_sig:
			_loot_sig = sig2
			_loot_title.text = _looting.display_name
			_clear(_loot_list)
			if not _looting.rolled:
				_loot_list.add_child(_row_label("…", Color(0.6, 0.6, 0.6)))
			elif _looting.items.is_empty():
				_loot_list.add_child(_row_label("пусто — сюда можно положить из рюкзака", Color(0.6, 0.6, 0.6)))
			var c := _looting
			var lg := GridView.new(Vector2i(Balance.BACKPACK_GRID.x, 2), "loot")
			lg.auto_layout = true
			lg.set_items(_looting.items)
			_loot_list.add_child(lg)
			lg.activated.connect(func(idx: int) -> void: _take_one(c, idx))
			lg.quick_move.connect(func(idx: int) -> void: _take_one(c, idx))
			lg.context.connect(func(idx: int, at: Vector2) -> void: _popup(at, ["Взять"], [func() -> void: _take_one(c, idx)]))
			# из рюкзака — в контейнер (спрятать, оставить напарнику)
			lg.dropped.connect(func(src: GridView, idx: int, _x: int, _y: int, _r: bool) -> void:
				if src.role == "backpack":
					Raid.current.request_put(c, idx))
			_take_all.disabled = _looting.items.is_empty()


func _take_one(c: LootContainer, idx: int) -> void:
	if idx < c.items.size():
		Raid.current.request_take(c, String(c.items[idx].id), int(c.items[idx].n))


## Двойной клик по предмету рюкзака: лечиться / надеть / взять в руки.
func _use_item(me: Player, idx: int) -> void:
	if idx >= me.inventory.items.size():
		return
	var id := String(me.inventory.items[idx].id)
	if ItemDb.item(id).has("use"):
		_try_heal_with(me, id)
	elif not ItemDb.equip(id).is_empty():
		Raid.current.request_equip(idx)


func _backpack_menu(me: Player, idx: int, at: Vector2) -> void:
	if idx >= me.inventory.items.size():
		return
	var it: Dictionary = me.inventory.items[idx]
	var id := String(it.id)
	var names: Array[String] = []
	var acts: Array[Callable] = []
	if ItemDb.item(id).has("use"):
		names.append("Лечиться")
		acts.append(func() -> void: _try_heal_with(me, id))
	if not ItemDb.equip(id).is_empty():
		names.append("В руки" if ItemDb.equip(id).has("weapon") else "Надеть")
		acts.append(func() -> void: Raid.current.request_equip(idx))
	if _looting:
		names.append("Положить в «%s»" % _looting.display_name)
		var c := _looting
		acts.append(func() -> void: Raid.current.request_put(c, idx))
	names.append("Выбросить")
	acts.append(func() -> void: Raid.current.request_drop(id, int(it.n)))
	_popup(at, names, acts)


## Правая кнопка по оружию в слоте: снять обвес (в рюкзак).
func _mods_menu(me: Player, weapon_slot: String, at: Vector2) -> void:
	var w: Dictionary = me.inventory.equipment.get(weapon_slot, {})
	var mods: Dictionary = w.get("mods", {})
	if mods.is_empty():
		Raid.current.notify("Обвесов нет — перетащи обвес из рюкзака на оружие")
		return
	var names: Array = []
	var acts: Array = []
	for ms in mods:
		var mslot := String(ms)
		names.append("Снять: " + ItemDb.item_name(String(mods[ms])))
		acts.append(func() -> void: Raid.current.request_remove_mod(weapon_slot, mslot))
	_popup(at, names, acts)


func _popup(at: Vector2, names: Array, acts: Array) -> void:
	var menu := PopupMenu.new()
	for t in names:
		menu.add_item(String(t))
	menu.id_pressed.connect(func(i: int) -> void: (acts[i] as Callable).call())
	menu.popup_hide.connect(menu.queue_free)
	add_child(menu)
	menu.popup(Rect2i(Vector2i(at), Vector2i.ZERO))


func _try_heal_with(me: Player, id: String) -> void:
	if _heal_t > 0.0 or me.health.hp >= me.health.max_hp:
		return
	var use: Dictionary = ItemDb.item(id).use
	Raid.current.request_use_med(id)
	_heal_total = float(use.time)
	_heal_t = _heal_total
	_bar_label.text = "Лечение: " + ItemDb.item_name(id)


# ---------------------------------------------------------------- вёрстка

## Панель у правого края: [контейнер, заголовок, список].
func _panel(root: Control, left: float, right: float) -> Array:
	var p := PanelContainer.new()
	p.anchor_left = 1.0
	p.anchor_right = 1.0
	p.anchor_top = 0.0
	p.offset_left = left
	p.offset_right = right
	p.offset_top = 90.0
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.06, 0.07, 0.08, 0.88)
	sb.border_color = Color(0.9, 0.82, 0.6, 0.35)
	sb.set_border_width_all(1)
	sb.set_content_margin_all(12)
	p.add_theme_stylebox_override("panel", sb)
	root.add_child(p)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	p.add_child(v)
	var title := Label.new()
	title.add_theme_font_size_override("font_size", 19)
	title.add_theme_color_override("font_color", Color(1.0, 0.88, 0.62))
	v.add_child(title)
	var list := VBoxContainer.new()
	list.add_theme_constant_override("separation", 4)
	v.add_child(list)
	return [p, title, list]


## Строка предмета с состоянием (прочность брони) и ценой экземпляра.
func _row_entry(e: Dictionary) -> HBoxContainer:
	var row := HBoxContainer.new()
	var n := int(e.n)
	var l := _row_label(ItemDb.label(e) + ("  ×%d" % n if n > 1 else ""), Color(0.92, 0.9, 0.85))
	l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(l)
	var v := _row_label("%s ₽" % money(ItemDb.entry_value(e)), Color(0.7, 0.85, 0.65))
	v.custom_minimum_size.x = 90
	v.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	row.add_child(v)
	return row


func _row(id: String, n: int) -> HBoxContainer:
	var row := HBoxContainer.new()
	var name := ItemDb.item_name(id) + ("  ×%d" % n if n > 1 else "")
	var l := _row_label(name, Color(0.92, 0.9, 0.85))
	l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(l)
	var v := _row_label("%s ₽" % money(ItemDb.value(id) * n), Color(0.7, 0.85, 0.65))
	v.custom_minimum_size.x = 90
	v.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	row.add_child(v)
	return row


func _row_label(text: String, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", 16)
	l.add_theme_color_override("font_color", color)
	return l


func _button(text: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.add_theme_font_size_override("font_size", 14)
	b.focus_mode = Control.FOCUS_NONE
	b.pressed.connect(cb)
	return b


func _clear(box: Container) -> void:
	for c in box.get_children():
		c.queue_free()
