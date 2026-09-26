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
## Меню «чем лечиться» (H): кнопки по видам лекарств в рюкзаке, 1…N — выбрать, Esc — закрыть.
var _med_menu: PanelContainer
var _med_ids: Array[String] = []
var _bp_grid: GridView
var _loot_sig: String = ""
## Буфер посередине (рюкзак + ящик / труп): сетка Inventory.buffer.
var _buf_panel: PanelContainer
var _buf_list: VBoxContainer
var _buf_sig: String = ""


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
	var bp := _panel(root, -PANEL_W - 24.0, -24.0)
	_bp_panel = bp[0]
	_bp_title = bp[1]
	_bp_list = bp[2]
	# буфер — между ящиком и рюкзаком
	var buf_w := float(Balance.BUFFER_GRID.x) * GridView.CELL + 26.0
	var bf := _panel(root, -PANEL_W - 40.0 - buf_w, -PANEL_W - 40.0)
	_buf_panel = bf[0]
	(bf[1] as Label).text = "Буфер"
	_buf_list = bf[2]
	var lp := _panel(root, -PANEL_W * 2.0 - 56.0 - buf_w, -PANEL_W - 56.0 - buf_w)
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


func close_all() -> void:
	if _med_menu:
		_med_menu.visible = false
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
	if me == null or not me.is_alive() or raid.has_left(me.peer_id):
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
	# Esc закрыл окно описания — рюкзак остаётся
	if Input.is_action_just_pressed("ui_cancel") and is_open() and not ItemInfo.blocking():
		close_all()
	if Input.is_action_just_pressed("use_med"):
		if _med_menu and _med_menu.visible:
			_med_menu.visible = false
		else:
			_open_med_menu(me)
	if _med_menu and _med_menu.visible:
		for i in range(_med_ids.size()):
			if Input.is_action_just_pressed("weapon_%d" % (i + 1)):
				_pick_med(me, _med_ids[i])
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
	_buf_panel.visible = _looting != null
	_bp_sig = ""
	_loot_sig = ""
	_buf_sig = ""
	# окно ящика закрыто — буфер в рюкзак (что не влезло — рядом мешком)
	var me := Raid.current.local_player() if Raid.current else null
	if _looting == null and me and not me.inventory.buffer.is_empty():
		Raid.current.request_flush_buffer()
	if not _backpack_open and _looting == null:
		close_popups()


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
				# прямо в рейде: бросил на оружие обвес или магазин, в плитоносец — плиту; обвес — что
				# умеет твой верстак
				sv.mod_from.connect(func(src: GridView, idx: int) -> void:
					if src.role != "backpack":
						Raid.current.notify("Сначала переложи в рюкзак")
						return
					if idx >= me.inventory.items.size():
						return
					var iid := String(me.inventory.items[idx].id)
					if not WeaponDb.attachment(iid).is_empty():
						var mount := WeaponDb.free_mount_for(me.inventory.equipment.get(ws, {}), iid)
						var why := Profile.mod_block(iid, mount)
						if why != "":
							Raid.current.notify("Не поставить: " + why)
							return
					Raid.current.request_fit("equip:" + ws, -1, idx, ""))
				# двойной клик — снять в рюкзак; ПКМ — снять, выбросить, снять обвес / магазин / плиту
				sv.unequip_requested.connect(func() -> void: Raid.current.request_unequip(ws))
				sv.context.connect(func(at: Vector2) -> void: _slot_menu(me, ws, at))
				slots.add_child(sv)
			# разложить по порядку — освободить место
			_bp_list.add_child(InventoryUI.sort_button(func() -> void: Raid.current.request_sort("backpack")))
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
			# из слота — в клетку рюкзака
			_bp_grid.slot_dropped.connect(func(slot: String, x: int, y: int, r: bool) -> void: Raid.current.request_unequip(slot, x, y, r))
			for g in grids:
				_wire_grid(g)
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
			# с трупа и из ящика: взять целиком или снять только ценное (прицел, плиту, магазин)
			lg.context.connect(func(idx: int, at: Vector2) -> void:
				if idx >= c.items.size():
					return
				var names: Array = ["Взять"]
				var acts: Array = [func() -> void: _take_one(c, idx)]
				for p in Gear.parts(c.items[idx]):
					var part := String(p[1])
					names.append(String(p[0]))
					acts.append(func() -> void: Raid.current.request_strip("loot", idx, part, c))
				_popup(at, names, acts))
			# из рюкзака и буфера — в контейнер (спрятать, оставить напарнику)
			lg.dropped.connect(func(src: GridView, idx: int, _x: int, _y: int, _r: bool) -> void:
				if src.role in ["backpack", "buffer"]:
					Raid.current.request_put(c, idx, src.role))
			_take_all.disabled = _looting.items.is_empty()
		_refresh_buffer(me)


## Буфер 3×3 посередине: переложить сюда из ящика и рюкзака, разрядить магазин (патроны падают
## сюда), патроны отсюда — на магазин. Закрыл окно ящика — всё уходит в рюкзак.
func _refresh_buffer(me: Player) -> void:
	var sig := str(me.inventory.buffer)
	if sig == _buf_sig:
		return
	_buf_sig = sig
	_clear(_buf_list)
	var g := GridView.new(Balance.BUFFER_GRID, "buffer")
	g.set_items(me.inventory.buffer)
	_buf_list.add_child(g)
	var hint := _row_label("Сюда — из ящика и рюкзака. Разрядить магазин: ПКМ. Патроны на магазин — снарядить. Закрыл ящик — всё в рюкзак.", Color(0.6, 0.62, 0.6))
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.add_theme_font_size_override("font_size", 12)
	hint.custom_minimum_size.x = float(Balance.BUFFER_GRID.x) * GridView.CELL
	_buf_list.add_child(hint)
	_wire_grid(g)
	g.activated.connect(func(idx: int) -> void: Raid.current.request_grid_move("buffer", idx, "backpack", -1, -1, false))
	g.quick_move.connect(func(idx: int) -> void: Raid.current.request_grid_move("buffer", idx, "backpack", -1, -1, false))
	g.context.connect(func(idx: int, at: Vector2) -> void: _buffer_menu(me, idx, at))


## Сетка рюкзака / кармана / буфера: принять из ящика и из соседних сеток; патроны на магазин —
## снарядить.
func _wire_grid(g: GridView) -> void:
	var dst := g.role
	g.dropped.connect(func(src: GridView, idx: int, x: int, y: int, r: bool) -> void:
		if src.role == "loot" and _looting:
			Raid.current.request_take_to(_looting, idx, x, y, r, dst)
		elif src.role in ["backpack", "pocket", "buffer"]:
			Raid.current.request_grid_move(src.role, idx, dst, x, y, r))
	g.dropped_on.connect(func(src: GridView, si: int, di: int) -> void:
		if src.role in ["backpack", "pocket", "buffer"]:
			Raid.current.request_fill(src.role, si, dst, di))


## Куда высыпать патроны при разрядке: открыт буфер — туда, иначе в ту же сетку.
func _unload_into(role: String) -> String:
	return "buffer" if _looting else role


func _buffer_menu(me: Player, idx: int, at: Vector2) -> void:
	if idx >= me.inventory.buffer.size():
		return
	var it: Dictionary = me.inventory.buffer[idx]
	var e := it.duplicate(true)
	var names: Array = ["Описание", "В рюкзак"]
	var acts: Array = [func() -> void: ItemInfo.open(self, e), func() -> void: Raid.current.request_grid_move("buffer", idx, "backpack", -1, -1, false)]
	if it.has("rounds"):
		names.append("Проверить патроны")
		acts.append(func() -> void: _check_mag(it))
		names.append("Разрядить магазин")
		acts.append(func() -> void: Raid.current.request_unload("buffer", idx, "buffer"))
	if it.has("rounds") or not WeaponDb.ammo(String(it.id)).is_empty():
		names.append("Снарядить магазины")
		acts.append(func() -> void: Raid.current.request_load_mags())
	if _looting:
		names.append("Положить в «%s»" % _looting.display_name)
		var c := _looting
		acts.append(func() -> void: Raid.current.request_put(c, idx, "buffer"))
	names.append("Выбросить")
	acts.append(func() -> void: Raid.current.request_drop_entry("buffer", idx))
	_popup(at, names, acts)


## Проверить магазин в сетке: у пистолетных и болтовочных — точно, у остальных — словами.
func _check_mag(it: Dictionary) -> void:
	var cap := int(WeaponDb.magazine(String(it.id)).get("capacity", 0))
	var est := Gear.ammo_estimate(int(it.get("rounds", 0)), cap, Gear.mag_exact(String(it.id)))
	Raid.current.notify("%s: %s" % [ItemDb.item_name(String(it.id)), est])


func _take_one(c: LootContainer, idx: int) -> void:
	if idx < c.items.size():
		Raid.current.request_take_idx(c, idx)


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
	var names: Array[String] = ["Описание"]
	var e := it.duplicate(true)
	var acts: Array[Callable] = [func() -> void: ItemInfo.open(self, e)]
	if ItemDb.item(id).has("use"):
		names.append("Лечиться")
		acts.append(func() -> void: _try_heal_with(me, id))
	if not ItemDb.equip(id).is_empty():
		names.append("В руки" if ItemDb.equip(id).has("weapon") else "Надеть")
		acts.append(func() -> void: Raid.current.request_equip(idx))
	# оружие, жилет: снять обвес, магазин, плиту — в рюкзак
	for p in Gear.parts(it):
		var part := String(p[1])
		names.append(String(p[0]))
		acts.append(func() -> void: Raid.current.request_strip("backpack", idx, part))
	if it.has("rounds"):
		names.append("Проверить патроны")
		acts.append(func() -> void: _check_mag(it))
		names.append("Разрядить магазин" + (" в буфер" if _looting else ""))
		var into := _unload_into("backpack")
		acts.append(func() -> void: Raid.current.request_unload("backpack", idx, into))
	if it.has("rounds") or not WeaponDb.ammo(id).is_empty():
		names.append("Снарядить магазины")
		acts.append(func() -> void: Raid.current.request_load_mags())
	if _looting:
		names.append("Положить в «%s»" % _looting.display_name)
		var c := _looting
		acts.append(func() -> void: Raid.current.request_put(c, idx))
		names.append("В буфер")
		acts.append(func() -> void: Raid.current.request_grid_move("backpack", idx, "buffer", -1, -1, false))
	names.append("Выбросить")
	acts.append(func() -> void: Raid.current.request_drop_entry("backpack", idx))
	_popup(at, names, acts)


## Правая кнопка по слоту: снять в рюкзак, выбросить, снять обвес / магазин / плиты.
func _slot_menu(me: Player, slot: String, at: Vector2) -> void:
	var e: Dictionary = me.inventory.equipment.get(slot, {})
	if e.is_empty():
		return
	var names: Array = ["Описание", "Снять в рюкзак", "Выбросить"]
	var info := e.duplicate(true)
	var acts: Array = [func() -> void: ItemInfo.open(self, info), func() -> void: Raid.current.request_unequip(slot), func() -> void: Raid.current.request_drop_entry("equip:" + slot, -1)]
	for p in Gear.parts(e):
		var part := String(p[1])
		names.append(String(p[0]))
		acts.append(func() -> void: Raid.current.request_strip("equip:" + slot, -1, part))
	_popup(at, names, acts)


## Правая кнопка по предмету в слоте: что с него можно снять (обвес, магазин, плиты) — в рюкзак.
func _parts_menu(e: Dictionary, at: Vector2, strip: Callable) -> void:
	var parts := Gear.parts(e)
	if parts.is_empty():
		Raid.current.notify("Снимать нечего — перетащи обвес, магазин или плиту из рюкзака сюда")
		return
	var names: Array = []
	var acts: Array = []
	for p in parts:
		var part := String(p[1])
		names.append(String(p[0]))
		acts.append(func() -> void: strip.call(part))
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
