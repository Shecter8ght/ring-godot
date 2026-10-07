class_name TerminalUI
extends CanvasLayer
## Окно терминала связи в убежище: доска заказов (Contracts) в духе старой BBS — зелёный
## моноширинный текст на чёрном. Слева заказчики (ник, имя, репутация, сколько заказов), справа —
## заказы выбранного: текст от его лица, цели, награда, «Взять» / «Отказаться» / «Сдать».
## Окно локальное; в группе доска — хоста, действия гостя уходят хосту (Contracts). Esc — закрыть.

const GREEN := Color(0.45, 1.0, 0.55)
const DIM := Color(0.3, 0.62, 0.36)
const AMBER := Color(1.0, 0.78, 0.35)
const BG := Color(0.015, 0.03, 0.02, 0.97)

var _root: Control
var _givers_box: VBoxContainer
var _detail: VBoxContainer
var _status: Label
var _selected: String = ""
var _opened_frame: int = -1
var _font: SystemFont
var _dirty: bool = true


func _ready() -> void:
	# над трекером задания и подсказками (QuestHud), под паузой
	layer = 40
	add_to_group("esc_windows")
	_font = SystemFont.new()
	_font.font_names = PackedStringArray(["Consolas", "Lucida Console", "Courier New", "monospace"])
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.visible = false
	add_child(_root)
	var dim: ColorRect = ColorRect.new()
	dim.color = Color(0, 0, 0, 0.55)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(dim)
	var panel: PanelContainer = PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_FULL_RECT)
	panel.offset_left = 110
	panel.offset_right = -110
	panel.offset_top = 60
	panel.offset_bottom = -60
	var sb: StyleBoxFlat = StyleBoxFlat.new()
	sb.bg_color = BG
	sb.border_color = Color(GREEN, 0.5)
	sb.set_border_width_all(2)
	sb.set_content_margin_all(18)
	panel.add_theme_stylebox_override("panel", sb)
	_root.add_child(panel)
	var v: VBoxContainer = VBoxContainer.new()
	v.add_theme_constant_override("separation", 10)
	panel.add_child(v)
	var head: HBoxContainer = HBoxContainer.new()
	v.add_child(head)
	var title: Label = _label("ТЕРМИНАЛ СВЯЗИ  ::  ДОСКА ЗАКАЗОВ", 24, GREEN)
	title.autowrap_mode = TextServer.AUTOWRAP_OFF
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(title)
	_status = _label("", 16, DIM)
	_status.autowrap_mode = TextServer.AUTOWRAP_OFF
	head.add_child(_status)
	var close: Button = _button("[ ЗАКРЫТЬ — Esc ]", close_ui)
	head.add_child(close)
	v.add_child(_label("— — — — — — — — — — — — — — — — — — — — — — — — — — — — — — — — — — — —", 14, DIM))
	var body: HBoxContainer = HBoxContainer.new()
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.add_theme_constant_override("separation", 24)
	v.add_child(body)
	_givers_box = VBoxContainer.new()
	_givers_box.custom_minimum_size.x = 380
	_givers_box.add_theme_constant_override("separation", 6)
	body.add_child(_givers_box)
	var scroll: ScrollContainer = ScrollContainer.new()
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	body.add_child(scroll)
	_detail = VBoxContainer.new()
	_detail.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_detail.add_theme_constant_override("separation", 10)
	scroll.add_child(_detail)
	v.add_child(_label("Заказы обновляются после каждого рейда. Невзятый заказ висит три рейда. Сдать — здесь же, после эвакуации.", 14, DIM))
	Contracts.changed.connect(func() -> void: _dirty = true)
	Quests.changed.connect(func() -> void: _dirty = true)


func is_open() -> bool:
	return _root.visible


func open() -> void:
	Contracts.sync()
	if _selected == "" and not Contracts.givers().is_empty():
		_selected = String(Contracts.givers()[0].id)
	_root.visible = true
	_opened_frame = Engine.get_process_frames()
	_dirty = true
	Audio.play_ui("stash")


func close_ui() -> void:
	_root.visible = false
	Audio.play_ui("bag_close")


func _process(_delta: float) -> void:
	if not _root.visible:
		return
	if Engine.get_process_frames() != _opened_frame and (Input.is_action_just_pressed("pause") or Input.is_action_just_pressed("inventory")):
		close_ui()
		return
	if _dirty:
		_dirty = false
		_rebuild()


func _rebuild() -> void:
	for c: Node in _givers_box.get_children():
		c.queue_free()
	for c: Node in _detail.get_children():
		c.queue_free()
	_status.text = "активных: %d/%d   " % [Contracts.active_count(), Contracts.active_limit()]
	_givers_box.add_child(_label("ЗАКАЗЧИКИ", 16, DIM))
	for g: Dictionary in Contracts.givers():
		var gid := String(g.id)
		var n_active := Contracts.offers(gid).filter(func(o: Dictionary) -> bool: return String(o.state) == "ACTIVE").size()
		var n_all := Contracts.offers(gid).size()
		var mark := ">" if gid == _selected else " "
		var b := _button("%s %-15s %s  [%d%s]" % [mark, String(g.nick).to_upper(), _stars(Contracts.rep_level(gid)), n_all, " • взят" if n_active > 0 else ""],
			func() -> void:
				_selected = gid
				_dirty = true
				Audio.play_ui("ui_click"))
		b.add_theme_color_override("font_color", _giver_color(g) if gid == _selected else GREEN)
		_givers_box.add_child(b)
		_givers_box.add_child(_label("    %s — %s" % [String(g.name), String(g.role)], 13, DIM))
	_build_detail()


func _build_detail() -> void:
	var g := Contracts.giver(_selected)
	if g.is_empty():
		return
	_detail.add_child(_label("%s  //  %s, %s" % [String(g.nick).to_upper(), String(g.name), String(g.role)], 20, _giver_color(g)))
	_detail.add_child(_label("Репутация: %s" % _stars(Contracts.rep_level(_selected)), 15, DIM))
	var greet: Array = g.get("greet", [])
	if not greet.is_empty():
		_detail.add_child(_label("> " + String(greet[hash(_selected + str(Contracts.board().size())) % greet.size()]), 16, GREEN))
	var offers := Contracts.offers(_selected)
	if offers.is_empty():
		_detail.add_child(_label("Заказов нет. Загляни после рейда.", 16, DIM))
	for o: Dictionary in offers:
		_detail.add_child(_card(o))


func _card(o: Dictionary) -> Control:
	var d: Dictionary = o.def
	var qid := String((o.entry as Dictionary).id)
	var state := String(o.state)
	var box: PanelContainer = PanelContainer.new()
	var sb: StyleBoxFlat = StyleBoxFlat.new()
	sb.bg_color = Color(0.03, 0.08, 0.04, 0.9) if state == "ACTIVE" else Color(0.02, 0.05, 0.03, 0.8)
	sb.border_color = Color(AMBER if state == "ACTIVE" else DIM, 0.6)
	sb.set_border_width_all(1)
	sb.set_content_margin_all(12)
	box.add_theme_stylebox_override("panel", sb)
	var v: VBoxContainer = VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	box.add_child(v)
	var tag := "[ВЗЯТ]" if state == "ACTIVE" else "[НОВЫЙ]"
	v.add_child(_label("%s %s" % [tag, String(d.get("title", ""))], 18, AMBER if state == "ACTIVE" else GREEN))
	v.add_child(_label("«%s»" % String(d.get("summary", "")), 15, GREEN))
	var r: Dictionary = d.get("reward", {})
	v.add_child(_label("Награда: %s ₽ · репутация +%d   ·   группа: 1–3 игрока" % [_money(int(r.get("money", 0))), int((r.get("rep", {}) as Dictionary).get(_selected, 0))], 14, DIM))
	if state == "ACTIVE":
		var cur := Quests.objective(qid)
		v.add_child(_label("Сейчас: " + String(cur.get("text", "")), 15, AMBER))
		if String(cur.get("hint", "")) != "":
			v.add_child(_label(String(cur.hint), 13, DIM))
	var row: HBoxContainer = HBoxContainer.new()
	row.add_theme_constant_override("separation", 14)
	v.add_child(row)
	if state == "AVAILABLE":
		row.add_child(_button("[ ВЗЯТЬ ]", func() -> void: _act(Contracts.take(qid), "Заказ взят")))
		row.add_child(_button("[ ОТКАЗАТЬСЯ ]", func() -> void:
			Contracts.decline(qid)
			_dirty = true))
	elif state == "ACTIVE":
		var can := Contracts.can_turn_in(qid)
		var t := _button("[ СДАТЬ ]", func() -> void: _act(Contracts.turn_in(qid), "Сдано. Оплата прошла."))
		t.disabled = not can
		row.add_child(t)
		row.add_child(_button("[ ОТКАЗАТЬСЯ — репутация −1 ]", func() -> void:
			Contracts.decline(qid)
			_dirty = true))
	return box


func _act(err: String, ok_text: String) -> void:
	if err != "":
		_status.text = err + "   "
		Audio.play_ui("ui_deny")
	else:
		Audio.play_ui("ui_click")
		_status.text = ok_text + "   "
	_dirty = true


func _stars(n: int) -> String:
	return "■".repeat(n) + "□".repeat(5 - n)


func _money(v: int) -> String:
	var s := str(v)
	var out := ""
	while s.length() > 3:
		out = " " + s.substr(s.length() - 3) + out
		s = s.substr(0, s.length() - 3)
	return s + out


func _giver_color(g: Dictionary) -> Color:
	var c: Array = g.get("color", [0.45, 1.0, 0.55])
	return Color(float(c[0]), float(c[1]), float(c[2]))


func _label(text: String, size: int, color: Color) -> Label:
	var l: Label = Label.new()
	l.text = text
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.add_theme_font_override("font", _font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l


func _button(text: String, cb: Callable) -> Button:
	var b: Button = Button.new()
	b.text = text
	b.flat = true
	b.focus_mode = Control.FOCUS_NONE
	b.alignment = HORIZONTAL_ALIGNMENT_LEFT
	b.add_theme_font_override("font", _font)
	b.add_theme_font_size_override("font_size", 16)
	b.add_theme_color_override("font_color", GREEN)
	b.add_theme_color_override("font_hover_color", AMBER)
	b.add_theme_color_override("font_disabled_color", Color(DIM, 0.5))
	b.pressed.connect(cb)
	return b
