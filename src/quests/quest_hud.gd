class_name QuestHud
extends CanvasLayer
## Интерфейс сюжета (создаёт Quests): компактная цель справа сверху (квест, этап, что делать,
## подсказка), всплывающие сообщения («Найдена улика», «Задание обновлено»), реплики на экране
## (осмотр места, раненый), разговор в убежище (Enter / клик — дальше), журнал улик (J), полоса
## обыска, подсказка «несёшь раненого». Консоль разработчика (`) — только при запуске из
## проекта (res://project.godot есть), в сборке для игроков её нет.

const TOAST_SEC := 3.2
const SUB_SEC := 2.6
## Реплики игрока (кто = "player") — своим цветом и подписью «Я»; собеседник — янтарный;
## строка без «кто» в субтитрах — описание (что видишь), светлая.
const PLAYER_WHO := "Я"
const PLAYER_COLOR := Color(0.62, 0.84, 0.95)
const NPC_COLOR := Color(1.0, 0.78, 0.45)
const DESC_COLOR := Color(0.95, 0.93, 0.86)

var _root: Control
var _tracker: VBoxContainer
var _t_title: Label
var _t_stage: Label
var _t_goal: Label
var _t_hint: Label
var _toasts: VBoxContainer
var _subs: Label
var _sub_queue: Array = []
var _sub_t: float = 0.0
var _dlg: PanelContainer
var _dlg_who: Label
var _dlg_text: Label
var _dlg_lines: Array = []
var _dlg_i: int = 0
var _dlg_done: Callable
var _bar: ProgressBar
var _bar_label: Label
var _bar_seen: bool = false
var _carry: Label
var _journal: PanelContainer
var _journal_text: Label
var _console: LineEdit
var _console_out: Label
var _dev: bool = false


func _ready() -> void:
	layer = 12
	process_mode = Node.PROCESS_MODE_ALWAYS
	add_to_group("esc_windows")
	_dev = FileAccess.file_exists("res://project.godot")
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_root)
	_build()
	Quests.notice.connect(toast)
	Quests.subtitles.connect(func(lines: Array) -> void:
		_sub_queue.append_array(lines)
		if _sub_t <= 0.0:
			_next_sub())
	Quests.changed.connect(_update_tracker)


func is_open() -> bool:
	return _dlg.visible or _journal.visible or _console.visible


func _in_game() -> bool:
	return Raid.current != null or get_tree().get_first_node_in_group("hideout_level") != null


# ---------------------------------------------------------------- что делать сейчас

func _update_tracker() -> void:
	var qid := Quests.tracked()
	_tracker.visible = qid != "" and _in_game()
	if qid == "":
		return
	var o := Quests.objective(qid)
	_t_title.text = String(Quests.def(qid).get("title", qid))
	_t_stage.text = "Этап %d · %s" % [int(Quests.qstate(qid).get("stage", 0)) + 1, String(Quests.stage(qid).get("title", ""))]
	_t_goal.text = String(o.get("text", ""))
	_t_hint.text = String(o.get("hint", ""))
	_t_hint.visible = _t_hint.text != ""


func toast(text: String) -> void:
	var l := _label(text, 20, Color(1.0, 0.86, 0.55))
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_toasts.add_child(l)
	var tw := l.create_tween()
	tw.tween_interval(TOAST_SEC)
	tw.tween_property(l, "modulate:a", 0.0, 0.6)
	tw.tween_callback(l.queue_free)
	_update_tracker()


func progress(text: String, frac: float) -> void:
	_bar_seen = text != ""
	_bar.visible = _bar_seen
	_bar_label.visible = _bar_seen
	_bar_label.text = text
	_bar.value = clampf(frac, 0.0, 1.0)


func carry_hint(text: String) -> void:
	_carry.text = text
	_carry.visible = text != ""


# ---------------------------------------------------------------- разговор

## Разговор (убежище): реплики [[кто, текст], …]; дочитал — done.
func start_dialogue(lines: Array, done: Callable) -> void:
	if lines.is_empty():
		done.call()
		return
	_dlg_lines = lines
	_dlg_i = 0
	_dlg_done = done
	_dlg.visible = true
	_show_line()


func _show_line() -> void:
	var l: Array = _dlg_lines[_dlg_i]
	var me := String(l[0]) == "player"
	_dlg_who.text = PLAYER_WHO if me else String(l[0])
	_dlg_who.add_theme_color_override("font_color", PLAYER_COLOR if me else NPC_COLOR)
	_dlg_text.add_theme_color_override("font_color", PLAYER_COLOR.lerp(Color.WHITE, 0.55) if me else Color(0.95, 0.94, 0.9))


func _advance() -> void:
	_dlg_i += 1
	if _dlg_i >= _dlg_lines.size():
		_dlg.visible = false
		var cb := _dlg_done
		_dlg_done = Callable()
		if cb.is_valid():
			cb.call()
		return
	_show_line()


func _next_sub() -> void:
	if _sub_queue.is_empty():
		_subs.visible = false
		_sub_t = 0.0
		return
	var e: Variant = _sub_queue.pop_front()
	var color := DESC_COLOR
	if e is Array and (e as Array).size() >= 2:
		var me := String(e[0]) == "player"
		_subs.text = "%s: %s" % [PLAYER_WHO if me else String(e[0]), String(e[1])]
		color = PLAYER_COLOR if me else NPC_COLOR
	else:
		_subs.text = String(e)
	_subs.add_theme_color_override("font_color", color)
	_subs.visible = true
	# длинную фразу — дольше
	_sub_t = maxf(SUB_SEC, _subs.text.length() * 0.055)


# ---------------------------------------------------------------- кадр и ввод

func _process(delta: float) -> void:
	if _sub_t > 0.0:
		_sub_t -= delta
		if _sub_t <= 0.0:
			_next_sub()
	var game := _in_game()
	_tracker.visible = game and Quests.tracked() != "" and not PauseMenu.shown
	if not game:
		_journal.visible = false
		_carry.visible = false
	if not _bar_seen:
		_bar.visible = false
		_bar_label.visible = false
	_bar_seen = false


func _input(event: InputEvent) -> void:
	if _dlg.visible:
		var mb := event as InputEventMouseButton
		if (mb and mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT) or event.is_action_pressed("ui_accept") \
				or (event is InputEventKey and (event as InputEventKey).pressed and (event as InputEventKey).keycode == KEY_SPACE):
			_advance()
			get_viewport().set_input_as_handled()
			return
		if event.is_action_pressed("pause"):
			_dlg.visible = false
			_dlg_done = Callable()
			get_viewport().set_input_as_handled()
			return
	if event.is_action_pressed("journal") and not event.is_echo() and _in_game() and not _console.visible:
		_journal.visible = not _journal.visible
		if _journal.visible:
			_fill_journal()
		get_viewport().set_input_as_handled()
		return
	if _journal.visible and event.is_action_pressed("pause"):
		_journal.visible = false
		get_viewport().set_input_as_handled()
		return
	if _dev and event.is_action_pressed("dev_console") and not event.is_echo():
		_console.visible = not _console.visible
		_console_out.visible = _console.visible
		if _console.visible:
			_console.grab_focus()
			_console.text = ""
		get_viewport().set_input_as_handled()


func _fill_journal() -> void:
	var lines: Array[String] = []
	for qid in Quests.ids():
		var st := Quests.state(qid)
		if st == "LOCKED" or st == "AVAILABLE":
			continue
		var d := Quests.def(qid)
		lines.append("%s   [%s]" % [String(d.title), "выполнено" if st == "COMPLETED" else ("провалено" if st == "FAILED" else "идёт")])
		lines.append("   " + String(d.get("summary", "")))
		for c in Quests.clues(qid):
			lines.append("   • %s — %s" % [String((c as Dictionary).get("title", "")), String((c as Dictionary).get("text", ""))])
	_journal_text.text = "\n".join(lines) if not lines.is_empty() else "Сюжетных заданий пока нет."


# ---------------------------------------------------------------- консоль разработчика

func _run(cmd: String) -> void:
	var a := cmd.strip_edges().split(" ", false)
	var out := ""
	if a.size() >= 2 and a[0] == "quest":
		var fallback := Quests.tracked() if Quests.tracked() != "" else (Quests.ids()[0] if not Quests.ids().is_empty() else "")
		var qid := a[2] if a.size() > 2 and not a[2].is_valid_int() else fallback
		match a[1]:
			"start":
				out = Quests.dev_start(qid)
			"stage":
				out = Quests.dev_stage(qid, int(a[a.size() - 1]))
			"reset":
				out = Quests.dev_reset(qid)
			"completeObjective", "obj":
				out = Quests.dev_complete_objective(a[2] if a.size() > 2 else "")
			"list", "state":
				out = Quests.dev_describe()
			_:
				out = "quest start|stage|reset|completeObjective|list <id> [n]"
	elif a.size() >= 1 and a[0] == "help":
		out = "quest start missing_anton · quest stage missing_anton 3 · quest completeObjective · quest reset missing_anton · quest list"
	else:
		out = "неизвестно: " + cmd + " (help)"
	_console_out.text = out
	_update_tracker()


# ---------------------------------------------------------------- построение

func _build() -> void:
	_tracker = VBoxContainer.new()
	_tracker.anchor_left = 1.0
	_tracker.anchor_right = 1.0
	_tracker.offset_left = -440
	_tracker.offset_right = -24
	_tracker.offset_top = 96
	_tracker.add_theme_constant_override("separation", 2)
	_tracker.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.add_child(_tracker)
	_t_title = _label("", 20, Color(1.0, 0.78, 0.45))
	_t_stage = _label("", 14, Color(0.78, 0.74, 0.66))
	_t_goal = _label("", 17, Color(0.95, 0.94, 0.9))
	_t_hint = _label("", 14, Color(0.7, 0.7, 0.68))
	for l in [_t_title, _t_stage, _t_goal, _t_hint]:
		(l as Label).horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		(l as Label).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		_tracker.add_child(l)
	_tracker.visible = false

	_toasts = VBoxContainer.new()
	_toasts.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_toasts.offset_left = -400
	_toasts.offset_right = 400
	_toasts.offset_top = 160
	_toasts.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.add_child(_toasts)

	_subs = _label("", 20, Color(0.95, 0.93, 0.86))
	_subs.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_subs.offset_left = -520
	_subs.offset_right = 520
	_subs.offset_top = -200
	_subs.offset_bottom = -150
	_subs.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_subs.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_subs.visible = false
	_root.add_child(_subs)

	_dlg = PanelContainer.new()
	_dlg.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_dlg.offset_left = -520
	_dlg.offset_right = 520
	_dlg.offset_top = -230
	_dlg.offset_bottom = -60
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.05, 0.05, 0.05, 0.92)
	sb.border_color = Color(1.0, 0.78, 0.45, 0.4)
	sb.set_border_width_all(1)
	sb.set_content_margin_all(18)
	_dlg.add_theme_stylebox_override("panel", sb)
	var dv := VBoxContainer.new()
	dv.add_theme_constant_override("separation", 8)
	_dlg.add_child(dv)
	_dlg_who = _label("", 18, Color(1.0, 0.78, 0.45))
	_dlg_text = _label("", 21, Color(0.95, 0.94, 0.9))
	_dlg_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var dh := _label("Enter / пробел / клик — дальше · Esc — отложить", 13, Color(0.6, 0.6, 0.58))
	dv.add_child(_dlg_who)
	dv.add_child(_dlg_text)
	dv.add_child(dh)
	_dlg.visible = false
	_root.add_child(_dlg)

	_bar = ProgressBar.new()
	_bar.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_bar.offset_left = -160
	_bar.offset_right = 160
	_bar.offset_top = -270
	_bar.offset_bottom = -256
	_bar.max_value = 1.0
	_bar.show_percentage = false
	_bar.visible = false
	_root.add_child(_bar)
	_bar_label = _label("", 16, Color(0.95, 0.9, 0.8))
	_bar_label.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_bar_label.offset_left = -200
	_bar_label.offset_right = 200
	_bar_label.offset_top = -296
	_bar_label.offset_bottom = -272
	_bar_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_bar_label.visible = false
	_root.add_child(_bar_label)

	_carry = _label("", 17, Color(1.0, 0.75, 0.65))
	_carry.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_carry.offset_left = -300
	_carry.offset_right = 300
	_carry.offset_top = -140
	_carry.offset_bottom = -116
	_carry.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_carry.visible = false
	_root.add_child(_carry)

	_journal = PanelContainer.new()
	_journal.set_anchors_preset(Control.PRESET_CENTER)
	_journal.offset_left = -420
	_journal.offset_right = 420
	_journal.offset_top = -240
	_journal.offset_bottom = 240
	_journal.add_theme_stylebox_override("panel", sb)
	var jv := VBoxContainer.new()
	_journal.add_child(jv)
	jv.add_child(_label("Журнал — сюжет и улики   (J — закрыть)", 20, Color(1.0, 0.78, 0.45)))
	_journal_text = _label("", 16, Color(0.9, 0.9, 0.86))
	_journal_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	jv.add_child(_journal_text)
	_journal.visible = false
	_root.add_child(_journal)

	_console = LineEdit.new()
	_console.set_anchors_preset(Control.PRESET_TOP_WIDE)
	_console.offset_top = 4
	_console.offset_bottom = 36
	_console.offset_left = 300
	_console.offset_right = -300
	_console.placeholder_text = "quest start missing_anton · quest stage missing_anton 3 · quest completeObjective · quest reset missing_anton · quest list"
	_console.visible = false
	_console.text_submitted.connect(func(t: String) -> void:
		_run(t)
		_console.text = "")
	_root.add_child(_console)
	_console_out = _label("", 14, Color(0.7, 1.0, 0.7))
	_console_out.set_anchors_preset(Control.PRESET_TOP_WIDE)
	_console_out.offset_top = 40
	_console_out.offset_left = 300
	_console_out.offset_right = -300
	_console_out.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_console_out.visible = false
	_root.add_child(_console_out)


func _label(text: String, size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	l.add_theme_constant_override("outline_size", 5)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l
