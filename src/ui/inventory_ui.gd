class_name InventoryUI
extends CanvasLayer
## Рюкзак и обыск — у каждого peer свой, для своего игрока. Tab — рюкзак; F у контейнера —
## обыск (полоска search_s, отошёл — сорвался), потом окно. H — полечиться самым подходящим из
## рюкзака. Сами изменения делает хост (Raid.request_*), окно только показывает реплицированные
## списки и шлёт просьбы.
##
## Окно — на весь экран с полями от краёв, колонками слева направо: ящик / труп (сетка с клетками),
## буфер 3×3, снаряжение (слоты), рюкзак и карман. Буфер живёт, только пока открыт ящик: закрыть с
## вещами в буфере — спросить «пропадут?». Магазины и плиты — поштучно (MagOps на хосте): снарядить
## один магазин, разрядить, вынуть плиты — с кругом заполненности на предмете.

## Поля от краёв экрана: сверху — под компасом, снизу — над строкой оружия.
const MARGIN := {"left": 36, "right": 36, "top": 78, "bottom": 74}

var _backpack_open: bool = false
var _searching: LootContainer
var _search_t: float = 0.0
var _looting: LootContainer
## Уже обысканные этим игроком контейнеры — второй раз окно открывается сразу.
var _searched: Dictionary = {}
var _heal_t: float = 0.0
var _heal_total: float = 0.0

var _dim: ColorRect
var _cols: HBoxContainer
var _eq_panel: PanelContainer
var _eq_list: VBoxContainer
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
## Меню «чем лечиться» (H): кнопки по видам лекарств в рюкзаке, 1…N — выбрать, Esc — закрыть.
var _med_menu: PanelContainer
var _med_ids: Array[String] = []
var _bp_grid: GridView
var _loot_sig: String = ""
var _loot_state: Label
## Буфер посередине (рюкзак + ящик / труп): сетка Inventory.buffer.
var _buf_panel: PanelContainer
var _buf_list: VBoxContainer
var _buf_sig: String = ""
## Вопрос «вещи в буфере пропадут — закрыть?»; кадр, когда закрыли (тот же Esc не закрывает окно).
var _confirm: ConfirmationDialog
var _confirm_frame: int = -10


## 34500 -> «34 500».
## «Сортировать» — заметная кнопка над сеткой (тайник в убежище, рюкзак в рейде): янтарная, с
## иконкой. Раскладывает по ячейкам: крупное — в начало, стопки добираются, место освобождается.
static func sort_button(cb: Callable) -> Button:
	var b := Button.new()
	b.text = "Сортировать"
	b.icon = _sort_icon()
	b.tooltip_text = "Разложить по ячейкам: крупное — в начало, стопки добираются, свободное место — одним куском"
	b.focus_mode = Control.FOCUS_NONE
	b.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	b.custom_minimum_size = Vector2(170, 34)
	b.add_theme_font_size_override("font_size", 16)
	for st in [["normal", Color(0.86, 0.62, 0.2)], ["hover", Color(0.98, 0.74, 0.3)], ["pressed", Color(0.7, 0.48, 0.14)]]:
		var box := StyleBoxFlat.new()
		box.bg_color = st[1]
		box.set_corner_radius_all(5)
		box.content_margin_left = 10
		box.content_margin_right = 12
		box.content_margin_top = 4
		box.content_margin_bottom = 4
		b.add_theme_stylebox_override(String(st[0]), box)
	for c in ["font_color", "font_hover_color", "font_pressed_color"]:
		b.add_theme_color_override(c, Color(0.1, 0.08, 0.05))
	b.pressed.connect(cb)
	return b


## Иконка сортировки — рисуется кодом (без файлов): полоски по убыванию и стрелка вниз.
static func _sort_icon() -> Texture2D:
	var img := Image.create(22, 22, false, Image.FORMAT_RGBA8)
	var ink := Color(0.1, 0.08, 0.05)
	for bar in [[4, 15], [10, 11], [16, 7]]:
		img.fill_rect(Rect2i(1, int(bar[0]), int(bar[1]), 3), ink)
	img.fill_rect(Rect2i(18, 3, 2, 14), ink)
	for i in range(4):
		img.fill_rect(Rect2i(15 + i, 14 + i, 8 - i * 2, 1), ink)
	return ImageTexture.create_from_image(img)


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
	# окно — на весь экран: мир притенён, колонки от края до края с полями
	_dim = ColorRect.new()
	_dim.color = Color(0.02, 0.022, 0.026, 0.7)
	_dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(_dim)
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	margin.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for side in MARGIN:
		margin.add_theme_constant_override("margin_" + String(side), int(MARGIN[side]))
	root.add_child(margin)
	_cols = HBoxContainer.new()
	_cols.add_theme_constant_override("separation", 14)
	_cols.mouse_filter = Control.MOUSE_FILTER_IGNORE
	margin.add_child(_cols)
	var lp := _panel(1.15)
	_loot_panel = lp[0]
	_loot_title = lp[1]
	_loot_list = lp[2]
	var bf := _panel(0.0, float(Balance.BUFFER_GRID.x) * GridView.CELL + 34.0)
	_buf_panel = bf[0]
	(bf[1] as Label).text = "Буфер"
	_buf_list = bf[2]
	var eq := _panel(0.8)
	_eq_panel = eq[0]
	(eq[1] as Label).text = "Снаряжение"
	_eq_list = eq[2]
	var bp := _panel(1.0)
	_bp_panel = bp[0]
	_bp_title = bp[1]
	_bp_list = bp[2]
	_take_all = Button.new()
	_take_all.text = "Взять всё"
	_take_all.focus_mode = Control.FOCUS_NONE
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
	return _backpack_open or _looting != null or (_med_menu != null and _med_menu.visible)


func is_looting() -> bool:
	return _searching != null or _looting != null


## F у контейнера: обыск (уже обысканный — сразу окно).
func start_search(c: LootContainer) -> void:
	if _searched.has(c.get_path()):
		_open_loot(c)
		return
	_searching = c
	_search_t = 0.0
	Audio.play(_loot_sound(c), c.global_position)


## Закрыть всё — уже решено (игрок согласился, погиб, отошёл): идущая операция прерывается, буфер
## (был открыт ящик) пропадает.
func close_all() -> void:
	var had_loot := _looting != null
	var was_open := is_open()
	if _med_menu:
		_med_menu.visible = false
	if _confirm and is_instance_valid(_confirm):
		_confirm.queue_free()
	_confirm = null
	_backpack_open = false
	_searching = null
	_looting = null
	_refresh_visibility()
	var raid := Raid.current
	var me := raid.local_player() if raid else null
	if raid and was_open:
		raid.request_cancel_op()
	if raid and had_loot and me and not me.inventory.buffer.is_empty():
		raid.request_clear_buffer()
	if was_open:
		Audio.play_ui("bag_close")


## Игрок закрывает окно (Tab, Esc): в буфере что-то осталось — спросить.
func request_close() -> void:
	var me := Raid.current.local_player() if Raid.current else null
	if _looting and me and not me.inventory.buffer.is_empty():
		_ask_buffer_loss()
		return
	close_all()


func _ask_buffer_loss() -> void:
	if _confirm and is_instance_valid(_confirm):
		return
	var d := ConfirmationDialog.new()
	d.name = "BufferLoss"
	d.title = "Буфер"
	d.dialog_text = "Все предметы, оставшиеся в буфере, будут потеряны. Закрыть окно?"
	d.ok_button_text = "Закрыть"
	d.cancel_button_text = "Остаться"
	d.confirmed.connect(func() -> void:
		_confirm = null
		close_all())
	d.visibility_changed.connect(func() -> void:
		if not d.visible:
			_confirm_frame = Engine.get_process_frames()
			if _confirm == d:
				_confirm = null
			d.queue_free())
	add_child(d)
	_confirm = d
	d.popup_centered()


func _open_loot(c: LootContainer) -> void:
	_searching = null
	_looting = c
	_backpack_open = true
	_loot_sig = ""
	_refresh_visibility()


func _process(delta: float) -> void:
	var raid := Raid.current
	var me := raid.local_player() if raid else null
	if me == null or not me.is_alive() or raid.has_left(me.peer_id):
		if is_open() or _searching:
			close_all()
		_bar.visible = false
		_bar_label.visible = false
		return
	# пока открыт вопрос про буфер (и кадр после) — клавиши его, не окна
	var asking := (_confirm != null and is_instance_valid(_confirm)) or Engine.get_process_frames() - _confirm_frame <= 1
	if Input.is_action_just_pressed("inventory") and not asking and not UiTheme.typing():
		if _backpack_open or _looting:
			request_close()
		else:
			_backpack_open = true
			_refresh_visibility()
			Audio.play_ui("bag_open")
	# Esc закрыл окно описания — рюкзак остаётся
	if Input.is_action_just_pressed("ui_cancel") and is_open() and not ItemInfo.blocking() and not asking:
		request_close()
	if Input.is_action_just_pressed("use_med") and not UiTheme.typing():
		if _med_menu and _med_menu.visible:
			_med_menu.visible = false
		else:
			_open_med_menu(me)
	if _med_menu and _med_menu.visible:
		for i in range(_med_ids.size()):
			if Input.is_action_just_pressed("weapon_%d" % (i + 1)):
				_pick_med(me, _med_ids[i])
	_tick_search(me, delta)
	# ящик пропал или отнесло от него — окно закрывается (буфер пропадает)
	if _looting and (not is_instance_valid(_looting) or _looting.global_position.distance_to(me.global_position) > Balance.INTERACT_RADIUS + 1.0):
		close_all()
	_tick_heal(delta)
	if is_open():
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
	var open := _backpack_open or _looting != null
	_dim.visible = open
	_eq_panel.visible = open
	_bp_panel.visible = open
	_loot_panel.visible = _looting != null
	_buf_panel.visible = _looting != null
	_bp_sig = ""
	_loot_sig = ""
	_buf_sig = ""
	if not open:
		close_popups()


func _loot_sound(c: LootContainer) -> String:
	match c.look:
		LootContainer.Look.SAFE:
			return "loot_safe"
		LootContainer.Look.RACK:
			return "loot_shelf"
		LootContainer.Look.BODY:
			return "loot_body"
		LootContainer.Look.BAG:
			return "loot_bag"
		LootContainer.Look.CRATE:
			return "loot_box"
	var n := c.display_name.to_lower()
	if "шкаф" in n:
		return "loot_locker"
	if "ящик" in n:
		return "loot_drawer"
	return "loot_box"


## Окно закрыли — закрыть и то, что открыто поверх: меню правой кнопки, описание предмета
## (меню — отдельное окошко, само с рюкзаком не прячется).
func close_popups() -> void:
	for c in get_children():
		if c is PopupMenu:
			(c as PopupMenu).hide()
		elif c is ItemInfo:
			(c as ItemInfo)._close()


## Сетки перестраиваются, только когда содержимое изменилось.
func _refresh_lists(me: Player) -> void:
	var sig := str(me.inventory.items) + str(me.inventory.equipment) + str(me.inventory.pocket)
	if sig != _bp_sig:
		_bp_sig = sig
		_bp_title.text = ("Рюкзак" if me.inventory.equipment.has("backpack") else "Карманы (рюкзака нет)") + "   %d / %d ячеек   ·   %s ₽" % [me.inventory.cells_used(), me.inventory.capacity(), money(me.inventory.value())]
		_build_equipment(me)
		_build_backpack(me)
	if _looting:
		var sig2 := str(_looting.items) + str(_looting.rolled) + str(_looting.grid)
		if sig2 != _loot_sig:
			_loot_sig = sig2
			_build_loot(me)
		_refresh_buffer(me)


## Слоты: в слот тащат из любой сетки (рюкзак, карман, буфер, ящик) — надеть / взять в руки; на
## оружие — обвес или магазин, в плитоносец — плиту.
func _build_equipment(me: Player) -> void:
	# Изменение патронов не должно уничтожать источник/приёмник текущего перетаскивания.
	for child: Node in _eq_list.get_children():
		if child is GridContainer and not child.is_queued_for_deletion():
			for slot_view: Node in child.get_children():
				if slot_view is SlotView:
					slot_view.set_entry(me.inventory.equipment.get(slot_view.slot, {}))
			return
	_clear(_eq_list)
	var slots := GridContainer.new()
	slots.columns = 2
	slots.add_theme_constant_override("h_separation", 8)
	slots.add_theme_constant_override("v_separation", 8)
	slots.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_eq_list.add_child(slots)
	for slot in Inventory.SLOTS:
		var sv := SlotView.new(String(slot))
		sv.custom_minimum_size = Vector2(3.0 * GridView.CELL, 1.7 * GridView.CELL)
		sv.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		sv.set_entry(me.inventory.equipment.get(slot, {}))
		var ws := String(slot)
		sv.equip_from.connect(func(src: GridView, idx: int) -> void:
			Raid.current.request_equip_from(src.role, idx, _looting if src.role == "loot" else null, ws))
		# прямо в рейде: бросил на оружие обвес или магазин, в плитоносец — плиту; обвес — что умеет
		# твой верстак
		sv.mod_from.connect(func(src: GridView, idx: int) -> void:
			var list := _list_of(me, src.role)
			if idx >= list.size():
				return
			var iid := String(list[idx].id)
			if not WeaponDb.attachment(iid).is_empty():
				var mount := WeaponDb.free_mount_for(me.inventory.equipment.get(ws, {}), iid)
				var why := Profile.mod_block(iid, mount)
				if why != "":
					Raid.current.notify("Не поставить: " + why)
					return
			Raid.current.request_fit_grid(src.role, idx, "equip:" + ws, -1, _looting if src.role == "loot" else null))
		# двойной клик — снять в рюкзак; ПКМ — снять, выбросить, снять обвес / магазин / плиту
		sv.unequip_requested.connect(func() -> void: Raid.current.request_unequip(ws))
		sv.context.connect(func(at: Vector2) -> void: _slot_menu(me, ws, at))
		slots.add_child(sv)
	var hint := _row_label("В слот — из рюкзака, ящика, буфера: перетащи. Двойной клик — снять. Правая кнопка — снять обвес, магазин, плиту.", Color(0.6, 0.62, 0.6))
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.add_theme_font_size_override("font_size", 13)
	_eq_list.add_child(hint)


func _build_backpack(me: Player) -> void:
	var existing: GridView = _existing_grid(_bp_list, "backpack")
	var pocket: GridView = _existing_grid(_bp_list, "pocket")
	var pocket_matches: bool = (pocket == null and me.inventory.pocket_grid == Vector2i.ZERO) or (pocket != null and pocket.grid == me.inventory.pocket_grid)
	if existing != null and pocket_matches:
		existing.set_items(me.inventory.items)
		if pocket != null:
			pocket.set_items(me.inventory.pocket)
		return
	_clear(_bp_list)
	# разложить по порядку — освободить место
	_bp_list.add_child(InventoryUI.sort_button(func() -> void: Raid.current.request_sort("backpack")))
	_bp_grid = GridView.new(me.inventory.backpack_grid(), "backpack")
	_bp_grid.set_items(me.inventory.items)
	_bp_list.add_child(_bp_grid)
	var hint := _row_label("Тащи мышью · R — повернуть · двойной клик — надеть / лечиться · правая кнопка — действия · патроны на магазин — снарядить", Color(0.6, 0.62, 0.6))
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
	# из слота — в клетку рюкзака
	_bp_grid.slot_dropped.connect(func(slot: String, x: int, y: int, r: bool) -> void: Raid.current.request_unequip(slot, x, y, r))
	for g in grids:
		_wire_grid(g)
		var role := g.role
		g.context.connect(func(idx: int, at: Vector2) -> void: _item_menu(me, role, idx, at))
	_bp_grid.activated.connect(func(idx: int) -> void: _use_item(me, idx))
	_bp_grid.quick_move.connect(func(idx: int) -> void:
		if _looting:
			Raid.current.request_put(_looting, idx))


## Ящик / труп: сетка с клетками (LootContainer.grid) — класть в нужную клетку, двигать внутри.
func _build_loot(me: Player) -> void:
	var c := _looting
	var g := c.grid if c.grid != Vector2i.ZERO else Vector2i(Balance.LOOT_GRID_W, int(Balance.LOOT_ROWS.get("NONE", 3)))
	var used := ItemDb.cells_of(c.items)
	_loot_title.text = "%s   %d / %d ячеек" % [c.display_name, used, g.x * g.y]
	var existing: GridView = _existing_grid(_loot_list, "loot")
	if existing != null and existing.grid == g and int(existing.get_meta("container_id", 0)) == c.get_instance_id():
		existing.set_items(c.items)
		_loot_state.text = "…" if not c.rolled else "пусто — сюда можно положить из рюкзака"
		_loot_state.visible = not c.rolled or c.items.is_empty()
		_take_all.disabled = c.items.is_empty()
		return
	_clear(_loot_list)
	_loot_state = _row_label("…" if not c.rolled else "пусто — сюда можно положить из рюкзака", Color(0.6, 0.6, 0.6))
	_loot_state.visible = not c.rolled or c.items.is_empty()
	_loot_list.add_child(_loot_state)
	var lg := GridView.new(g, "loot")
	lg.set_meta("container_id", c.get_instance_id())
	lg.set_items(c.items)
	_loot_list.add_child(lg)
	var hint := _row_label("Двойной клик — в рюкзак · правая кнопка — разрядить, вынуть плиты, снять часть (в этот ящик или в буфер) · тащи прямо в слот, в рюкзак, на магазин", Color(0.6, 0.62, 0.6))
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.add_theme_font_size_override("font_size", 13)
	_loot_list.add_child(hint)
	lg.activated.connect(func(idx: int) -> void: _take_one(c, idx))
	lg.quick_move.connect(func(idx: int) -> void: _take_one(c, idx))
	lg.context.connect(func(idx: int, at: Vector2) -> void: _item_menu(me, "loot", idx, at))
	# в ящик — из рюкзака, кармана, буфера в клетку; внутри ящика — передвинуть
	lg.dropped.connect(func(src: GridView, idx: int, x: int, y: int, r: bool) -> void:
		if src == lg:
			Raid.current.request_loot_move(c, idx, x, y, r)
		elif src.role in ["backpack", "buffer", "pocket"]:
			Raid.current.request_put(c, idx, src.role, x, y, r))
	lg.dropped_on.connect(func(src: GridView, si: int, di: int) -> void: _drop_into(me, src.role, si, "loot", di))
	_take_all.disabled = c.items.is_empty()


## Буфер 3×3 посередине: переложить сюда из ящика и рюкзака, разрядить магазин (патроны падают
## сюда), патроны отсюда — на магазин. Живёт, пока открыт ящик.
func _refresh_buffer(me: Player) -> void:
	var sig := str(me.inventory.buffer)
	if sig == _buf_sig:
		return
	_buf_sig = sig
	var existing: GridView = _existing_grid(_buf_list, "buffer")
	if existing != null:
		existing.set_items(me.inventory.buffer)
		return
	_clear(_buf_list)
	var g := GridView.new(Balance.BUFFER_GRID, "buffer")
	g.set_items(me.inventory.buffer)
	_buf_list.add_child(g)
	var hint := _row_label("Сюда — из ящика и рюкзака; разряженное из ящика, если в нём нет места. Закроешь ящик — что здесь останется, пропадёт.", Color(0.6, 0.62, 0.6))
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.add_theme_font_size_override("font_size", 12)
	hint.custom_minimum_size.x = float(Balance.BUFFER_GRID.x) * GridView.CELL
	_buf_list.add_child(hint)
	_wire_grid(g)
	g.activated.connect(func(idx: int) -> void: Raid.current.request_grid_move("buffer", idx, "backpack", -1, -1, false))
	g.quick_move.connect(func(idx: int) -> void: Raid.current.request_grid_move("buffer", idx, "backpack", -1, -1, false))
	g.context.connect(func(idx: int, at: Vector2) -> void: _item_menu(me, "buffer", idx, at))


## Сетка рюкзака / кармана / буфера: принять из ящика и из соседних сеток; патроны на магазин —
## снарядить, плиту на жилет — вставить.
func _wire_grid(g: GridView) -> void:
	var dst := g.role
	g.dropped.connect(func(src: GridView, idx: int, x: int, y: int, r: bool) -> void:
		if src.role == "loot" and _looting:
			Raid.current.request_take_to(_looting, idx, x, y, r, dst)
		elif src.role in ["backpack", "pocket", "buffer"]:
			Raid.current.request_grid_move(src.role, idx, dst, x, y, r))
	g.dropped_on.connect(func(src: GridView, si: int, di: int) -> void:
		var me := Raid.current.local_player() if Raid.current else null
		if me:
			_drop_into(me, src.role, si, dst, di))


## Бросили патроны на магазин — снарядить этими патронами (поштучно, сколько влезет); плиту на
## жилет — вставить.
func _drop_into(me: Player, src: String, si: int, dst: String, di: int) -> void:
	var from := _list_of(me, src)
	if si < 0 or si >= from.size():
		return
	var c := _looting if (src == "loot" or dst == "loot") else null
	var sid := String(from[si].id)
	if not WeaponDb.ammo(sid).is_empty():
		Raid.current.request_item_op("load", dst, di, c, sid, src)
	else:
		Raid.current.request_fit_grid(src, si, dst, di, c)


## Сетка по имени: ящик ("loot") — открытый контейнер, остальное — у игрока.
func _list_of(me: Player, role: String) -> Array:
	if role == "loot":
		return _looting.items if _looting else []
	return me.inventory.list_of(role)


## Правая кнопка по предмету в сетке role ("backpack", "pocket", "buffer", "loot"): что с ним можно.
func _item_menu(me: Player, role: String, idx: int, at: Vector2) -> void:
	var list := _list_of(me, role)
	if idx < 0 or idx >= list.size():
		return
	var it: Dictionary = list[idx]
	var id := String(it.id)
	var c := _looting
	var box := c if role == "loot" else null
	var info := it.duplicate(true)
	var names: Array = ["Описание"]
	var acts: Array = [func() -> void: ItemInfo.open(self, info)]
	if role == "loot":
		names.append("Взять")
		acts.append(func() -> void: _take_one(c, idx))
	elif role == "buffer":
		names.append("В рюкзак")
		acts.append(func() -> void: Raid.current.request_grid_move("buffer", idx, "backpack", -1, -1, false))
	if role == "backpack" and ItemDb.item(id).has("use"):
		names.append("Лечиться")
		acts.append(func() -> void: _try_heal_with(me, id))
	if role == "backpack" and Balance.LOOT_PACKS.has(id):
		names.append("Вскрыть упаковку")
		acts.append(func() -> void: Raid.current.request_unpack(idx, id))
	if role == "backpack" and id == "signal_launcher":
		names.append("Вызвать самолёт снабжения")
		acts.append(func() -> void: Raid.current.request_supply_signal())
	if role == "backpack" and id in ["signal_launcher", "flare"] and me.inventory.has("signal_launcher"):
		names.append("Запустить осветительную ракету")
		acts.append(func() -> void: me.launch_sky_flare())
	if not ItemDb.equip(id).is_empty():
		names.append("В руки" if ItemDb.equip(id).has("weapon") else "Надеть")
		acts.append(func() -> void: Raid.current.request_equip_from(role, idx, box))
	if role == "backpack" and WeaponDb.is_weapon(id):
		names.append("Собрать…")
		acts.append(func() -> void: WeaponBuilder.open_raid(self, me, "backpack", idx))
	# оружие, жилет: снять обвес, магазин — сразу; плиты — по одной (в ту же сетку, из ящика — в
	# ящик или буфер)
	for p in Gear.parts(it):
		var part := String(p[1])
		if part.begins_with("plate:"):
			names.append(String(p[0]).replace("Снять", "Вынуть"))
			acts.append(func() -> void: Raid.current.request_item_op("plates", role, idx, c, "", "", part.trim_prefix("plate:")))
		else:
			names.append(String(p[0]))
			acts.append(func() -> void: Raid.current.request_strip(role, idx, part, box))
	if it.has("plates") and (it.plates as Dictionary).size() > 1:
		names.append("Вынуть все плиты")
		acts.append(func() -> void: Raid.current.request_item_op("plates", role, idx, c))
	if it.has("rounds"):
		names.append("Проверить патроны")
		acts.append(func() -> void: _check_mag(role, idx, it))
		names.append("Снарядить")
		acts.append(func() -> void: _load_mag(me, role, idx))
		names.append("Разрядить")
		acts.append(func() -> void: Raid.current.request_item_op("unload", role, idx, c))
	if c and role != "loot":
		names.append("Положить в «%s»" % c.display_name)
		acts.append(func() -> void: Raid.current.request_put(c, idx, role))
	if c and role != "buffer":
		names.append("В буфер")
		acts.append(func() -> void:
			if role == "loot":
				Raid.current.request_take_to(c, idx, -1, -1, false, "buffer")
			else:
				Raid.current.request_grid_move(role, idx, "buffer", -1, -1, false))
	if role != "loot":
		names.append("Выбросить")
		acts.append(func() -> void: Raid.current.request_drop_entry(role, idx))
	_popup(at, names, acts)


## «Снарядить» по одному магазину: любыми подходящими патронами игрока (буфер, рюкзак, карман). Нет
## подходящих — пункт всё равно есть, но сказать, каких не хватает и какие есть.
func _load_mag(me: Player, role: String, idx: int) -> void:
	var list := _list_of(me, role)
	if idx < 0 or idx >= list.size():
		return
	var mag: Dictionary = list[idx]
	var mine: Array = me.inventory.buffer + me.inventory.items + me.inventory.pocket
	if int(mag.rounds) >= MagOps.capacity(mag):
		Raid.current.notify("Магазин и так полный")
		return
	var ammo := MagOps.pick_ammo(mag, mine)
	if ammo == "" or MagOps.count_of(mine, ammo) <= 0:
		Raid.current.notify(MagOps.no_ammo_text(mag, mine))
		return
	Raid.current.request_item_op("load", role, idx, _looting if role == "loot" else null)


## Проверить магазин в сетке: у пистолетных и болтовочных — точно, у остальных — словами; сетка
## запомнит (пока в нём столько же — видна метка).
func _check_mag(role: String, idx: int, it: Dictionary) -> void:
	var cap := int(WeaponDb.magazine(String(it.id)).get("capacity", 0))
	var est := Gear.ammo_estimate(int(it.get("rounds", 0)), cap, Gear.mag_exact(String(it.id)))
	# патроны вперемешку — проверка показывает и какие лежат сверху
	var types := Gear.mag_types_text(it)
	Raid.current.notify("%s: %s%s" % [ItemDb.item_name(String(it.id)), est, " · " + types if types != "" else ""])
	Raid.current.request_check_mag(role, idx, _looting if role == "loot" else null)


func _take_one(c: LootContainer, idx: int) -> void:
	if idx < c.items.size():
		Raid.current.request_take_idx(c, idx)


## Двойной клик по предмету рюкзака: лечиться / надеть / взять в руки.
func _use_item(me: Player, idx: int) -> void:
	if idx >= me.inventory.items.size():
		return
	var id := String(me.inventory.items[idx].id)
	if Balance.LOOT_PACKS.has(id):
		Raid.current.request_unpack(idx, id)
	elif id == "signal_launcher":
		Raid.current.request_supply_signal()
	elif ItemDb.item(id).has("use"):
		_try_heal_with(me, id)
	elif not ItemDb.equip(id).is_empty():
		Raid.current.request_equip(idx)


## Правая кнопка по слоту: снять в рюкзак, выбросить, снять обвес / магазин / плиты.
func _slot_menu(me: Player, slot: String, at: Vector2) -> void:
	var e: Dictionary = me.inventory.equipment.get(slot, {})
	if e.is_empty():
		return
	var names: Array = ["Описание", "Снять в рюкзак", "Выбросить"]
	var info := e.duplicate(true)
	var acts: Array = [func() -> void: ItemInfo.open(self, info), func() -> void: Raid.current.request_unequip(slot), func() -> void: Raid.current.request_drop_entry("equip:" + slot, -1)]
	if WeaponDb.is_weapon(String(e.id)):
		names.append("Собрать…")
		acts.append(func() -> void: WeaponBuilder.open_raid(self, me, "equip:" + slot, -1))
	for p in Gear.parts(e):
		var part := String(p[1])
		names.append(String(p[0]))
		acts.append(func() -> void: Raid.current.request_strip("equip:" + slot, -1, part))
	_popup(at, names, acts)


func _popup(at: Vector2, names: Array, acts: Array) -> void:
	var menu := PopupMenu.new()
	for t in names:
		menu.add_item(String(t))
	menu.id_pressed.connect(func(i: int) -> void: (acts[i] as Callable).call())
	menu.popup_hide.connect(menu.queue_free)
	add_child(menu)
	menu.popup(Rect2i(Vector2i(at), Vector2i.ZERO))


## H: чем лечиться — лекарства из рюкзака по видам. Лёжа раненым: аптечка — подняться, бинт —
## остановить кровь (+DOWN_BANDAGE_SEC), остальное не поможет.
func _open_med_menu(me: Player) -> void:
	var down := me.is_downed()
	if _heal_t > 0.0:
		return
	if not down and me.health.hp >= me.health.max_hp:
		Raid.current.notify("Ты цел — лечиться не нужно")
		return
	var counts := {}
	for it in me.inventory.items:
		if not ItemDb.item(String(it.id)).get("use", {}).is_empty():
			counts[String(it.id)] = int(counts.get(String(it.id), 0)) + int(it.n)
	if counts.is_empty():
		Raid.current.notify("Нечем лечиться")
		return
	if _med_menu == null:
		_med_menu = PanelContainer.new()
		_med_menu.set_anchors_preset(Control.PRESET_CENTER)
		var sb := StyleBoxFlat.new()
		sb.bg_color = Color(0.06, 0.06, 0.06, 0.94)
		sb.border_color = Color(0.9, 0.3, 0.25, 0.5)
		sb.set_border_width_all(1)
		sb.set_content_margin_all(14)
		_med_menu.add_theme_stylebox_override("panel", sb)
		add_child(_med_menu)
	for c in _med_menu.get_children():
		c.queue_free()
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	_med_menu.add_child(box)
	var head := Label.new()
	head.text = "Лёжа: чем помочь себе" if down else "Чем лечиться"
	head.add_theme_font_size_override("font_size", 18)
	head.add_theme_color_override("font_color", Color(1.0, 0.8, 0.7))
	box.add_child(head)
	_med_ids.clear()
	for id in counts:
		var sid := String(id)
		var use: Dictionary = ItemDb.item(sid).use
		var what := "+%d, %.0f с" % [int(use.heal), float(use.time)]
		var ok := true
		if down:
			if sid == "medkit":
				what = "подняться, %.0f с" % Balance.REVIVE_SELF_SEC
			elif sid == "bandage":
				what = "перевязать: +%.0f с до смерти" % Balance.DOWN_BANDAGE_SEC
			else:
				what = "лёжа не поможет"
				ok = false
		_med_ids.append(sid)
		var b := Button.new()
		b.text = "%d   %s × %d   —   %s" % [_med_ids.size(), ItemDb.item_name(sid), int(counts[id]), what]
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.disabled = not ok
		b.focus_mode = Control.FOCUS_NONE
		b.custom_minimum_size = Vector2(420, 34)
		b.pressed.connect(func() -> void: _pick_med(me, sid))
		box.add_child(b)
	var hint := Label.new()
	hint.text = "1–%d или мышью · H / Esc — закрыть" % _med_ids.size()
	hint.add_theme_font_size_override("font_size", 13)
	hint.add_theme_color_override("font_color", Color(0.65, 0.65, 0.62))
	box.add_child(hint)
	_med_menu.visible = true
	_med_menu.reset_size()
	_med_menu.position = (get_viewport().get_visible_rect().size - _med_menu.get_combined_minimum_size()) * 0.5


func _pick_med(me: Player, id: String) -> void:
	_med_menu.visible = false
	_try_heal_with(me, id)
	_bar_label.text = ("Поднимаюсь: " if me.is_downed() and id == "medkit" else "Лечение: ") + ItemDb.item_name(id)


func _try_heal_with(me: Player, id: String) -> void:
	var down := me.is_downed()
	# обезболивающее и при полном здоровье — унять дрожь (стресс)
	var calm := id == "painkillers" and me.stress > 20.0
	if _heal_t > 0.0 or (not down and me.health.hp >= me.health.max_hp and not calm):
		return
	if down and id != "medkit" and id != "bandage":
		Raid.current.notify("Лёжа поможет только аптечка (подняться) или бинт")
		return
	var use: Dictionary = ItemDb.item(id).use
	Raid.current.request_use_med(id)
	if id == "painkillers":
		me.add_stress(-float(Balance.STRESS.painkillers))
	_heal_total = Balance.REVIVE_SELF_SEC if down and id == "medkit" else float(use.time)
	_heal_t = _heal_total
	_bar_label.text = "Лечение: " + ItemDb.item_name(id)


# ---------------------------------------------------------------- вёрстка

## Колонка окна: во всю высоту, ширина — доля ratio (0 — ровно min_w); внутри — заголовок и список
## с прокруткой. [колонка, заголовок, список].
func _panel(ratio: float, min_w: float = 0.0) -> Array:
	var p := PanelContainer.new()
	p.size_flags_horizontal = Control.SIZE_EXPAND_FILL if ratio > 0.0 else Control.SIZE_SHRINK_BEGIN
	p.size_flags_stretch_ratio = maxf(ratio, 0.01)
	p.size_flags_vertical = Control.SIZE_EXPAND_FILL
	p.custom_minimum_size.x = min_w
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.06, 0.07, 0.08, 0.92)
	sb.border_color = Color(0.9, 0.82, 0.6, 0.35)
	sb.set_border_width_all(1)
	sb.set_content_margin_all(12)
	p.add_theme_stylebox_override("panel", sb)
	_cols.add_child(p)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	p.add_child(v)
	var title := Label.new()
	title.add_theme_font_size_override("font_size", 19)
	title.add_theme_color_override("font_color", Color(1.0, 0.88, 0.62))
	title.clip_text = true
	v.add_child(title)
	var sc := ScrollContainer.new()
	sc.size_flags_vertical = Control.SIZE_EXPAND_FILL
	sc.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	v.add_child(sc)
	var list := VBoxContainer.new()
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.add_theme_constant_override("separation", 6)
	sc.add_child(list)
	return [p, title, list]


func _row_label(text: String, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", 16)
	l.add_theme_color_override("font_color", color)
	return l


## При изменении содержимого обновляем данные, а не удаляем узел, на который ссылается drag.
func _existing_grid(box: Container, role: String) -> GridView:
	for child: Node in box.get_children():
		if child is GridView and not child.is_queued_for_deletion() and child.role == role:
			return child
	return null


func _clear(box: Container) -> void:
	for c in box.get_children():
		c.queue_free()
