class_name QuestHud
extends CanvasLayer
## Интерфейс сюжета (создаёт Quests): компактная цель справа сверху (квест, этап, что делать,
## подсказка), всплывающие сообщения («Найдена улика», «Задание обновлено»), реплики на экране
## (осмотр места, раненый), разговор в убежище (Enter / клик — дальше), журнал улик (J), полоса
## обыска, подсказка «несёшь раненого», кадр видоискателя на снимке места (photo_flash).
## Читы открываются отдельным пунктом меню Esc.

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
## Подсказка-обучение (QuestCoach): одна строка с клавишей из текущих привязок, пока действие нужно.
var _coach: Label
var _journal: PanelContainer
var _journal_text: Label
## Тестовые инструкции (Balance.QUEST_TEST_HINTS): что делать на текущем шаге — слева, после смены
## цели; ключ «квест:этап:цель» последней показанной у каждого квеста.
var _test_box: PanelContainer
var _test_title: Label
var _test_text: Label
var _test_t: float = 0.0
var _test_seen: Dictionary = {}
## Снимок места: рамка видоискателя и вспышка поверх экрана, секунду.
var _photo: Control
var _photo_flash: ColorRect
var _photo_t: float = 0.0
const PHOTO_SEC := 0.9


func _ready() -> void:
	layer = 12
	process_mode = Node.PROCESS_MODE_ALWAYS
	add_to_group("esc_windows")
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
	Quests.changed.connect(_update_test_hint)


func is_open() -> bool:
	return _dlg.visible or _journal.visible


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


## Тест: цель сменилась у любого активного квеста — показать её test_hint (последняя — сверху).
func _update_test_hint() -> void:
	if not Balance.QUEST_TEST_HINTS:
		return
	for qid in Quests.ids():
		if Quests.state(qid) != "ACTIVE":
			_test_seen.erase(qid)
			continue
		var key := "%d:%d" % [int(Quests.qstate(qid).get("stage", 0)), int(Quests.qstate(qid).get("obj", 0))]
		if String(_test_seen.get(qid, "")) == key:
			continue
		_test_seen[qid] = key
		var hint := String(Quests.objective(qid).get("test_hint", ""))
		if hint == "":
			continue
		_test_title.text = "ТЕСТ — что делать · %s" % String(Quests.def(qid).get("title", qid))
		_test_text.text = hint
		_test_t = Balance.QUEST_TEST_HINT_SEC


## Снимок места (точка съёмки): рамка видоискателя, щелчок и короткая вспышка — только у того,
## кто снимает; сам снимок засчитывает хост (Quests.request_site).
func photo_flash() -> void:
	_photo_t = PHOTO_SEC
	_photo.visible = true
	_photo_flash.color.a = 0.85
	Audio.play_ui("tac_click")


func toast(text: String) -> void:
	Audio.play_ui("quest", -3.0)
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


## Реплики в очереди и на экране — прочь (пролог заново после гибели: прошлая рация не доигрывается).
func clear_subtitles() -> void:
	_sub_queue.clear()
	_sub_t = 0.0
	_subs.visible = false


## Подсказка-обучение: «{reload}» в тексте — клавиша действия reload по текущим привязкам; "" — погасить.
func coach(text: String) -> void:
	_coach.text = coach_text(text)
	_coach.visible = _coach.text != "" and _in_game() and not PauseMenu.shown


## Текущий текст подсказки (тесты).
func coach_shown() -> String:
	return _coach.text if _coach.visible else ""


static func coach_text(text: String) -> String:
	var out := text
	var re := RegEx.create_from_string("\\{([a-z_]+)\\}")
	for m in re.search_all(text):
		var key := PauseMenu.key_name(m.get_string(1))
		out = out.replace(m.get_string(0), key if key != "" else m.get_string(1))
	return out


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
	if not me:
		Audio.play_ui("anton" if "Антон" in String(l[0]) else "trader")
	_dlg_who.text = PLAYER_WHO if me else String(l[0])
	_dlg_text.text = String(l[1]) if l.size() > 1 else ""
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
		if not me:
			Audio.play_ui("anton" if "Антон" in String(e[0]) else "trader")
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
		_coach.visible = false
	if not _bar_seen:
		_bar.visible = false
		_bar_label.visible = false
	_bar_seen = false
	if _test_t > 0.0:
		_test_t -= delta
	_test_box.visible = _test_t > 0.0 and game and not PauseMenu.shown and not _journal.visible
	if _photo_t > 0.0:
		_photo_t -= delta
		_photo_flash.color.a = maxf(0.0, _photo_flash.color.a - delta * 3.0)
		_photo.visible = _photo_t > 0.0


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
	if event.is_action_pressed("journal") and not event.is_echo() and _in_game() and not PauseMenu.shown and not UiTheme.typing():
		_journal.visible = not _journal.visible
		if _journal.visible:
			_fill_journal()
		get_viewport().set_input_as_handled()
		return
	if _journal.visible and event.is_action_pressed("pause"):
		_journal.visible = false
		get_viewport().set_input_as_handled()
		return



func _fill_journal() -> void:
	var lines: Array[String] = []
	# тест: инструкции текущих шагов — сверху журнала
	if Balance.QUEST_TEST_HINTS:
		for qid in Quests.ids():
			var th := String(Quests.objective(qid).get("test_hint", "")) if Quests.state(qid) == "ACTIVE" else ""
			if th != "":
				lines.append("ТЕСТ · %s: %s" % [String(Quests.def(qid).get("title", qid)), th])
		if not lines.is_empty():
			lines.append("")
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

	_coach = _label("", 19, Color(0.86, 0.95, 0.78))
	_coach.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_coach.offset_left = -420
	_coach.offset_right = 420
	_coach.offset_top = -340
	_coach.offset_bottom = -310
	_coach.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_coach.visible = false
	_root.add_child(_coach)

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

	_test_box = PanelContainer.new()
	_test_box.anchor_top = 0.5
	_test_box.anchor_bottom = 0.5
	_test_box.offset_left = 24
	_test_box.offset_right = 24 + 460
	_test_box.offset_top = -170
	_test_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var tsb := StyleBoxFlat.new()
	tsb.bg_color = Color(0.05, 0.05, 0.03, 0.82)
	tsb.border_color = Color(1.0, 0.8, 0.3, 0.7)
	tsb.set_border_width_all(2)
	tsb.set_content_margin_all(12)
	_test_box.add_theme_stylebox_override("panel", tsb)
	var tv := VBoxContainer.new()
	_test_box.add_child(tv)
	_test_title = _label("", 15, Color(1.0, 0.8, 0.3))
	tv.add_child(_test_title)
	_test_text = _label("", 16, Color(0.95, 0.93, 0.86))
	_test_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_test_text.custom_minimum_size.x = 436
	tv.add_child(_test_text)
	tv.add_child(_label("J — журнал: инструкция там же", 13, Color(0.7, 0.68, 0.6)))
	_test_box.visible = false
	_root.add_child(_test_box)

	_photo = ViewfinderFrame.new()
	_photo.set_anchors_preset(Control.PRESET_FULL_RECT)
	_photo.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_photo.visible = false
	_root.add_child(_photo)
	_photo_flash = ColorRect.new()
	_photo_flash.set_anchors_preset(Control.PRESET_FULL_RECT)
	_photo_flash.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_photo_flash.color = Color(1, 1, 1, 0)
	_photo.add_child(_photo_flash)


## Рамка видоискателя: уголки кадра и перекрестие по центру.
class ViewfinderFrame extends Control:
	func _draw() -> void:
		var r := Rect2(size * 0.12, size * 0.76)
		var c := Color(1, 1, 1, 0.8)
		var l := minf(size.x, size.y) * 0.07
		for corner: Vector2 in [r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)]:
			var sx := 1.0 if corner.x < size.x * 0.5 else -1.0
			var sy := 1.0 if corner.y < size.y * 0.5 else -1.0
			draw_line(corner, corner + Vector2(l * sx, 0), c, 3.0)
			draw_line(corner, corner + Vector2(0, l * sy), c, 3.0)
		var m := size * 0.5
		draw_line(m - Vector2(14, 0), m + Vector2(14, 0), c, 2.0)
		draw_line(m - Vector2(0, 14), m + Vector2(0, 14), c, 2.0)




func _label(text: String, size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	l.add_theme_constant_override("outline_size", 5)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l
