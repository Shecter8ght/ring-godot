class_name RoadmapWindow
extends CanvasLayer
## Окно «Дорожная карта»: что осталось сделать до демоверсии. Слева — разделы или этапы со счётом
## «сделано / всего», справа — пункты по порядку; щелчок по отметке меняет статус по кругу
## (не начато → в работе → готово), правый щелчок — назад. Список и отметки — RoadmapData
## (data/roadmap.json). Открывается из меню по Esc, из главного меню и от доски в убежище; Esc — закрыть.

const C_HEAD := Color(1.0, 0.86, 0.6)
const C_DIM := Color(0.74, 0.72, 0.66)
const C_WARN := Color(1.0, 0.62, 0.4)
const STATUS_COLORS: Dictionary = {
	"todo": Color(0.62, 0.6, 0.56),
	"doing": Color(1.0, 0.8, 0.45),
	"done": Color(0.55, 0.85, 0.5),
}

var data: RoadmapData
## По чему сгруппирован левый столбец: "sections" — разделы, "stages" — этапы (порядок работ).
var mode: String = "sections"
## Выбранная группа: "" — всё, id раздела или этапа, "later" — что отложено за рамки демоверсии.
var group: String = ""
var only_open: bool = false

var _root: Control
var _total: Label
var _bar: ProgressBar
var _groups: VBoxContainer
var _list: VBoxContainer
var _scroll: ScrollContainer
var _note: Label
var _mode_buttons: Dictionary = {}
var _mouse_before: Input.MouseMode = Input.MOUSE_MODE_VISIBLE


## Открыть окно поверх всего; уже открытое — вернуть его же.
static func open_in(tree: SceneTree, source: RoadmapData = null) -> RoadmapWindow:
	for n: Node in tree.get_nodes_in_group("roadmap_window"):
		return n as RoadmapWindow
	var w: RoadmapWindow = RoadmapWindow.new()
	w.data = source
	tree.root.add_child(w)
	return w


func _ready() -> void:
	layer = 80
	process_mode = Node.PROCESS_MODE_ALWAYS
	add_to_group("esc_windows")
	add_to_group("roadmap_window")
	UiTheme.apply()
	if data == null:
		data = RoadmapData.new()
	_mouse_before = Input.mouse_mode
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_build()
	refresh()


func is_open() -> bool:
	return true


## Esc закрывает только это окно: меню паузы под ним остаётся как было.
func _input(event: InputEvent) -> void:
	if event.is_action_pressed("pause") and not event.is_echo():
		get_viewport().set_input_as_handled()
		close_ui()


func close_ui() -> void:
	Input.mouse_mode = _mouse_before
	queue_free()


func _build() -> void:
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(_root)
	var dim: ColorRect = ColorRect.new()
	dim.color = Color(0.0, 0.0, 0.0, 0.6)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(dim)
	var panel: PanelContainer = PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_FULL_RECT)
	panel.offset_left = 60
	panel.offset_right = -60
	panel.offset_top = 40
	panel.offset_bottom = -40
	var sb: StyleBoxFlat = StyleBoxFlat.new()
	sb.bg_color = Color(0.07, 0.065, 0.06, 0.97)
	sb.border_color = Color(0.95, 0.78, 0.5, 0.4)
	sb.set_border_width_all(1)
	sb.set_content_margin_all(20)
	panel.add_theme_stylebox_override("panel", sb)
	_root.add_child(panel)
	var v: VBoxContainer = VBoxContainer.new()
	v.add_theme_constant_override("separation", 10)
	panel.add_child(v)

	var head: HBoxContainer = HBoxContainer.new()
	head.add_theme_constant_override("separation", 18)
	v.add_child(head)
	head.add_child(_label(data.title(), 26, C_HEAD))
	_total = _label("", 18, Color(0.93, 0.91, 0.86))
	_total.name = "Total"
	head.add_child(_total)
	_bar = ProgressBar.new()
	_bar.show_percentage = false
	_bar.custom_minimum_size = Vector2(220, 14)
	_bar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var bar_back: StyleBoxFlat = StyleBoxFlat.new()
	bar_back.bg_color = Color(0.17, 0.165, 0.155)
	bar_back.set_corner_radius_all(6)
	var bar_fill: StyleBoxFlat = StyleBoxFlat.new()
	bar_fill.bg_color = STATUS_COLORS["done"]
	bar_fill.set_corner_radius_all(6)
	_bar.add_theme_stylebox_override("background", bar_back)
	_bar.add_theme_stylebox_override("fill", bar_fill)
	head.add_child(_bar)
	var close: Button = _button("Закрыть (Esc)", close_ui)
	head.add_child(close)

	if data.summary() != "":
		var about: Label = _label(data.summary(), 15, C_DIM)
		about.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		v.add_child(about)

	var tools: HBoxContainer = HBoxContainer.new()
	tools.add_theme_constant_override("separation", 10)
	v.add_child(tools)
	for m: Array in [["sections", "По разделам"], ["stages", "По порядку работ"]]:
		var b: Button = _button(String(m[1]), set_mode.bind(String(m[0])))
		b.toggle_mode = true
		_mode_buttons[String(m[0])] = b
		tools.add_child(b)
	var open_only: CheckButton = CheckButton.new()
	open_only.name = "OnlyOpen"
	open_only.text = "Только не сделанное"
	open_only.focus_mode = Control.FOCUS_NONE
	open_only.toggled.connect(func(on: bool) -> void:
		only_open = on
		refresh())
	tools.add_child(open_only)
	var reread: Button = _button("Перечитать файл", func() -> void:
		data.reload()
		refresh())
	reread.tooltip_text = "Если список правили руками или агент, пока игра открыта."
	tools.add_child(reread)
	_note = _label("", 13, C_DIM)
	_note.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_note.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	tools.add_child(_note)

	var body: HBoxContainer = HBoxContainer.new()
	body.add_theme_constant_override("separation", 18)
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	v.add_child(body)
	var left: ScrollContainer = ScrollContainer.new()
	left.custom_minimum_size.x = 380
	left.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	body.add_child(left)
	_groups = VBoxContainer.new()
	_groups.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_groups.add_theme_constant_override("separation", 6)
	left.add_child(_groups)
	_scroll = ScrollContainer.new()
	_scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	body.add_child(_scroll)
	_list = VBoxContainer.new()
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_list.add_theme_constant_override("separation", 8)
	_scroll.add_child(_list)


func set_mode(new_mode: String) -> void:
	mode = new_mode
	group = ""
	refresh()


func set_group(new_group: String) -> void:
	group = new_group
	_scroll.scroll_vertical = 0
	refresh()


## Сменить статус пункта (step: +1 — дальше по кругу, −1 — назад) и сохранить.
func cycle(id: String, step: int = 1) -> void:
	var st: String = data.status(id)
	var next: String = RoadmapData.next_status(st)
	if step < 0:
		next = RoadmapData.next_status(next)
	if not data.set_status(id, next):
		_note.text = "Не удалось сохранить отметку — файл списка занят или закрыт для записи."
		_note.add_theme_color_override("font_color", C_WARN)
		return
	refresh()


## Пересобрать счёт, левый столбец и список по текущим режиму, группе и фильтру.
func refresh() -> void:
	var all: Vector2i = data.count()
	_total.text = "Сделано %d из %d · осталось %d" % [all.x, all.y, all.y - all.x]
	_bar.max_value = maxf(1.0, float(all.y))
	_bar.value = float(all.x)
	_note.remove_theme_color_override("font_color")
	_note.add_theme_color_override("font_color", C_DIM if data.problems.is_empty() else C_WARN)
	_note.text = data.saves_to() if data.problems.is_empty() else "В файле списка есть ошибки: " + " ".join(data.problems)
	for m: String in _mode_buttons:
		(_mode_buttons[m] as Button).set_pressed_no_signal(m == mode)
	_fill_groups()
	_fill_list()


func _group_rows() -> Array[Array]:
	var rows: Array[Array] = [["", "Весь список"]]
	if mode == "stages":
		for st: Variant in data.stages():
			rows.append([String((st as Dictionary).get("id", "")), String((st as Dictionary).get("name", ""))])
	else:
		for sec: Dictionary in data.sections():
			rows.append([String(sec.get("id", "")), String(sec.get("name", ""))])
	return rows


func _fill_groups() -> void:
	_clear(_groups)
	for row: Array in _group_rows():
		var gid: String = String(row[0])
		var c: Vector2i = data.count(gid)
		var b: Button = _button("%s    %d / %d" % [String(row[1]), c.x, c.y], set_group.bind(gid))
		b.name = "Group_" + (gid if gid != "" else "all")
		b.toggle_mode = true
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.clip_text = true
		b.set_pressed_no_signal(gid == group)
		if c.y > 0 and c.x == c.y:
			b.add_theme_color_override("font_color", STATUS_COLORS["done"])
		_groups.add_child(b)
	if not data.later().is_empty():
		var gap: Control = Control.new()
		gap.custom_minimum_size.y = 10
		_groups.add_child(gap)
		var later: Button = _button("Отложено — не для демоверсии    %d" % data.later().size(), set_group.bind("later"))
		later.name = "Group_later"
		later.toggle_mode = true
		later.alignment = HORIZONTAL_ALIGNMENT_LEFT
		later.clip_text = true
		later.set_pressed_no_signal(group == "later")
		_groups.add_child(later)


func _fill_list() -> void:
	_clear(_list)
	if group == "later":
		_list.add_child(_label("Что сознательно отложено: в демоверсию не входит", 20, C_HEAD))
		for e: Variant in data.later():
			_list.add_child(_later_row(e as Dictionary))
		return
	if mode == "stages":
		for st: Variant in data.stages():
			var sid: String = String((st as Dictionary).get("id", ""))
			if group == "" or group == sid:
				_add_block(String((st as Dictionary).get("name", "")), String((st as Dictionary).get("goal", "")), sid)
	else:
		for sec: Dictionary in data.sections():
			var sec_id: String = String(sec.get("id", ""))
			if group == "" or group == sec_id:
				_add_block(String(sec.get("name", "")), String(sec.get("note", "")), sec_id)
	if _list.get_child_count() == 0:
		_list.add_child(_label("Здесь всё сделано.", 18, STATUS_COLORS["done"]))


## Заголовок группы со счётом и её пункты (с учётом фильтра «только не сделанное»).
func _add_block(block_title: String, block_note: String, gid: String) -> void:
	var rows: Array[Dictionary] = []
	for it: Dictionary in data.items(gid):
		if not only_open or data.status(String(it.get("id", ""))) != "done":
			rows.append(it)
	if rows.is_empty():
		return
	var c: Vector2i = data.count(gid)
	_list.add_child(_label("%s  ·  %d из %d" % [block_title, c.x, c.y], 20, C_HEAD))
	if block_note != "":
		var n: Label = _label(block_note, 14, C_DIM)
		n.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		_list.add_child(n)
	for it: Dictionary in rows:
		_list.add_child(_item_row(it))
	var gap: Control = Control.new()
	gap.custom_minimum_size.y = 8
	_list.add_child(gap)


func _item_row(it: Dictionary) -> Control:
	var id: String = String(it.get("id", ""))
	var st: String = data.status(id)
	var row: HBoxContainer = HBoxContainer.new()
	row.name = "Item_" + id.replace(".", "_")
	row.add_theme_constant_override("separation", 14)
	var mark: Button = Button.new()
	mark.name = "Mark"
	mark.text = String(RoadmapData.STATUS_NAMES[st])
	mark.custom_minimum_size = Vector2(124, 36)
	mark.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	mark.focus_mode = Control.FOCUS_NONE
	mark.button_mask = MOUSE_BUTTON_MASK_LEFT | MOUSE_BUTTON_MASK_RIGHT
	mark.tooltip_text = "Щелчок — следующий статус, правый щелчок — предыдущий."
	mark.add_theme_color_override("font_color", STATUS_COLORS[st])
	mark.add_theme_color_override("font_hover_color", STATUS_COLORS[st])
	mark.gui_input.connect(func(ev: InputEvent) -> void:
		var mb: InputEventMouseButton = ev as InputEventMouseButton
		if mb and mb.pressed and mb.button_index == MOUSE_BUTTON_RIGHT:
			cycle(id, -1))
	mark.pressed.connect(func() -> void:
		if not Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
			cycle(id, 1))
	row.add_child(mark)
	var text: VBoxContainer = VBoxContainer.new()
	text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	text.add_theme_constant_override("separation", 1)
	row.add_child(text)
	var name_label: Label = _label(String(it.get("title", "")), 17, Color(0.6, 0.6, 0.58) if st == "done" else Color(0.95, 0.93, 0.88))
	name_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	text.add_child(name_label)
	var ready_when: Label = _label("Готово, когда: " + String(it.get("done_when", "")), 14, C_DIM)
	ready_when.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	text.add_child(ready_when)
	# в списке по разделам видно этап, в списке по этапам — раздел; кто делает — если указано
	var tags: PackedStringArray = []
	if mode == "stages":
		tags.append(String(data.section_of(id).get("name", "")))
	else:
		tags.append(data.stage_name(String(it.get("stage", ""))))
	if String(it.get("who", "")) != "":
		tags.append("делает: " + String(it.get("who", "")))
	text.add_child(_label("  ·  ".join(tags), 13, Color(0.56, 0.55, 0.52)))
	var wait: Array[String] = data.blockers(id)
	if st != "done" and not wait.is_empty():
		var blocked: Label = _label("Сначала: " + "; ".join(PackedStringArray(wait)), 13, C_WARN)
		blocked.name = "Blocked"
		blocked.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		text.add_child(blocked)
	return row


func _later_row(e: Dictionary) -> Control:
	var box: VBoxContainer = VBoxContainer.new()
	box.add_theme_constant_override("separation", 1)
	var t: Label = _label(String(e.get("title", "")), 17, Color(0.9, 0.88, 0.84))
	t.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(t)
	if String(e.get("why", "")) != "":
		var w: Label = _label(String(e.get("why", "")), 14, C_DIM)
		w.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		box.add_child(w)
	return box


func _clear(box: Control) -> void:
	for c: Node in box.get_children():
		box.remove_child(c)
		c.queue_free()


func _label(text: String, size: int, color: Color) -> Label:
	var l: Label = Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l


func _button(text: String, action: Callable) -> Button:
	var b: Button = Button.new()
	b.text = text
	b.custom_minimum_size.y = 36
	b.focus_mode = Control.FOCUS_NONE
	b.add_theme_font_size_override("font_size", 16)
	b.pressed.connect(action)
	return b
