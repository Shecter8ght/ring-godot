class_name InventoryUI
extends CanvasLayer
## Рюкзак и обыск — у каждого peer свой, для своего игрока. Tab — рюкзак; F у контейнера —
## обыск (полоска search_s, отошёл — сорвался), потом окно: «взять» по предмету или «взять всё».
## H — полечиться самым подходящим из рюкзака. Сами изменения делает хост (Raid.request_*),
## окно только показывает реплицированные списки и шлёт просьбы.

const PANEL_W := 440.0

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


## Списки перестраиваются, только когда содержимое изменилось.
func _refresh_lists(me: Player) -> void:
	if _backpack_open:
		var sig := str(me.inventory.items) + str(me.inventory.equipment)
		if sig != _bp_sig:
			_bp_sig = sig
			_bp_title.text = "Рюкзак   %d / %d ячеек   ·   %s ₽" % [me.inventory.cells_used(), Balance.BACKPACK_CELLS, money(me.inventory.value())]
			_clear(_bp_list)
			# снаряжение — сверху, приглушённо
			for slot in Inventory.SLOTS:
				var e: Dictionary = me.inventory.equipment.get(slot, {})
				var text := "%s:  %s" % [Inventory.SLOT_NAMES[slot], ItemDb.label(e) if not e.is_empty() else "—"]
				_bp_list.add_child(_row_label(text, Color(0.75, 0.8, 0.85)))
			_bp_list.add_child(HSeparator.new())
			if me.inventory.items.is_empty():
				_bp_list.add_child(_row_label("пусто", Color(0.6, 0.6, 0.6)))
			for i in range(me.inventory.items.size()):
				var it: Dictionary = me.inventory.items[i]
				var id := String(it.id)
				var idx := i
				var row := _row_entry(it)
				if ItemDb.item(id).has("use"):
					row.add_child(_button("Лечиться", func() -> void: _try_heal_with(me, id)))
				if not ItemDb.equip(id).is_empty():
					var verb := "В руки" if ItemDb.equip(id).has("weapon") else "Надеть"
					row.add_child(_button(verb, func() -> void: Raid.current.request_equip(idx)))
				row.add_child(_button("Выбросить", func() -> void: Raid.current.request_drop(id, int(it.n))))
				_bp_list.add_child(row)
	if _looting:
		var sig2 := str(_looting.items) + str(_looting.rolled)
		if sig2 != _loot_sig:
			_loot_sig = sig2
			_loot_title.text = _looting.display_name
			_clear(_loot_list)
			if not _looting.rolled:
				_loot_list.add_child(_row_label("…", Color(0.6, 0.6, 0.6)))
			elif _looting.items.is_empty():
				_loot_list.add_child(_row_label("пусто", Color(0.6, 0.6, 0.6)))
			var c := _looting
			for it in _looting.items:
				var id := String(it.id)
				var row := _row_entry(it)
				row.add_child(_button("Взять", func() -> void: Raid.current.request_take(c, id, int(it.n))))
				_loot_list.add_child(row)
			_take_all.disabled = _looting.items.is_empty()


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
