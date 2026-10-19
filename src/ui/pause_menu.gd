class_name PauseMenu
extends CanvasLayer
## Меню на Esc (autoload `Pause`): продолжить, управление, покинуть рейд / в убежище, выйти из игры.
## Соло — игра на паузе; в коопе мир идёт дальше (меню только закрывает экран и глушит ввод игрока).
## Esc открывает меню, только если не открыто другое окно (рюкзак, окно убежища, карта) — те
## закрываются своим Esc. «Управление» — список из InputMap, у каждого действия кнопка с клавишей:
## нажал — нажми новую клавишу или кнопку мыши (Esc — отмена); занятую другим действием — видно
## сразу. Сохраняется в Settings (раздел keys), «Вернуть по умолчанию» — как в проекте.

## Открыто ли меню — игрок в коопе не стреляет и не ходит, пока оно открыто.
static var shown: bool = false

## Подписи действий в порядке показа; клавиши берутся из InputMap.
const ACTIONS := [
	["move_forward|move_left|move_back|move_right", "Ходьба"],
	["sprint", "Бег"],
	["crouch", "Присесть / встать"],
	["prone", "Лечь / встать"],
	["aim", "Прицелиться — вид из глаз (мышь — взгляд)"],
	["fire", "Огонь"],
	["reload", "Перезарядка"],
	["fire_mode", "Режим огня по кругу (у ВЕРАС-54: АВ → 2 → ОД)"],
	["toggle_suppressor", "Глушитель — снять в рюкзак / установить из рюкзака"],
	["weapon_1", "Оружие 1 (крупное)"],
	["weapon_2", "Оружие 2 (крупное)"],
	["weapon_3", "Пистолет"],
	["weapon_4", "Ракетница (на полигоне — винтовка)"],
	["grenade", "Взять / убрать гранату"],
	["throw_flare", "Ракетница в руки (из слота оружия; в руках — красный / зелёный патрон); дважды быстро — красный фальшфейер в руку, бросок как граната (горит минуту)"],
	["throw_chem", "Зелёный химсвет в руку — бросок как граната (тихая метка)"],
	["nvg", "ПНВ вкл / выкл (надет в слоте «Глаза»)"],
	["flashlight", "Фонарь на оружии, подсветка сетки оптики — вкл / выкл"],
	["laser", "ЛЦУ на оружии — вкл / выкл"],
	["toggle_sight", "Прицел: основной / угловой (если стоят оба; от первого лица — и СКМ)"],
	["sight_menu", "Настройка прицела ЛУМАР: форма, цвет и толщина метки, ночной режим окна"],
	["zero_up|zero_down|zero_left|zero_right", "Пристрелка (в прицеле): щелчок барабанчика вверх / вниз / влево / вправо"],
	["interact", "Двери, обыск, рубильники, подобрать; над раненым напарником — держать: поднять (аптечка)"],
	["inventory", "Рюкзак"],
	["use_med", "Лечиться: выбрать чем (лёжа раненым — аптечка: подняться, бинт: +время)"],
	["drag", "Тащить раненого напарника / отпустить; лёжа раненым — держать: сдаться"],
	["camera_left|camera_right", "Наклон влево / вправо"],
	["vault", "Прыжок / перелезть через преграду впереди (стоя)"],
	["dive", "Бросок на землю в сторону движения (только на ходу, с WASD), дальше — лёжа"],
	["voice", "Голос своим (держать; кооп)"],
	["map", "Карта"],
	["journal", "Журнал улик"],
	["pause", "Меню"],
]
## То, что не действие InputMap.
const EXTRA := [
	["С гранатой, химсветом, фальшфейером: ЛКМ / ПКМ", "Верхняя дуга / подброс снизу; держать — сильнее, отпустить — бросить"],
	["Колесо в прицеле", "Кратность регулируемой оптики: вверх — больше, вниз — меньше"],
	["СКМ + мышь", "Повернуть камеру (изометрия)"],
	["СКМ", "От первого лица — основной / угловой прицел"],
	["Бег в прицеле", "Задержать дыхание: прицел почти стоит, пока хватает воздуха"],
	["Enter", "Кооп — чат своим (Enter — отправить, Esc — закрыть)"],
	["Enter / пробел", "После рейда — в убежище (в коопе — пробел)"],
]

var _root: Control
var _main: VBoxContainer
var _controls: VBoxContainer
var _settings: VBoxContainer
var _leave: Button
var _to_menu: Button
var _cheats: VBoxContainer
var _mouse_before: Input.MouseMode = Input.MOUSE_MODE_VISIBLE
## Ждём новую клавишу для этого действия (кнопка — чтобы показать «нажмите…»).
var _capture: String = ""
var _capture_btn: Button
var _keys_note: Label


func _ready() -> void:
	layer = 50
	process_mode = Node.PROCESS_MODE_ALWAYS
	# общий вид кнопок и полей на всю игру; курсор-«рука» — каждой новой кнопке
	UiTheme.apply()
	get_tree().node_added.connect(UiTheme.on_node_added)
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.visible = false
	add_child(_root)
	var dim := ColorRect.new()
	dim.color = Color(0.02, 0.02, 0.025, 0.72)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(center)
	var panel := PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.07, 0.065, 0.06, 0.96)
	sb.border_color = Color(0.95, 0.78, 0.5, 0.4)
	sb.set_border_width_all(1)
	sb.set_content_margin_all(26)
	panel.add_theme_stylebox_override("panel", sb)
	center.add_child(panel)
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 36)
	panel.add_child(h)
	_main = VBoxContainer.new()
	_main.add_theme_constant_override("separation", 10)
	_main.custom_minimum_size.x = 280
	h.add_child(_main)
	var title := Label.new()
	title.text = "RING"
	title.add_theme_font_size_override("font_size", 34)
	title.add_theme_color_override("font_color", Color(1.0, 0.86, 0.6))
	_main.add_child(title)
	_main.add_child(_button("Продолжить", close_menu))
	_main.add_child(_button("Управление", func() -> void: _show_side(_controls)))
	_main.add_child(_button("Настройки", func() -> void: _show_side(_settings)))
	_main.add_child(_button("Читы", open_cheats))
	_leave = _button("Покинуть рейд", _on_leave)
	_main.add_child(_leave)
	# из убежища — в главное меню (собрание распускается)
	_to_menu = _button("В главное меню", func() -> void:
		close_menu()
		Net.disconnect_all()
		Profile.pending_raid = false
		Net.change_scene(Balance.MAIN_MENU_SCENE, "Возвращение в главное меню"))
	_main.add_child(_to_menu)
	_main.add_child(_button("Выйти из игры", func() -> void: get_tree().quit()))
	_controls = VBoxContainer.new()
	_controls.add_theme_constant_override("separation", 4)
	_controls.visible = false
	h.add_child(_controls)
	_fill_controls()
	_cheats = (load("res://src/ui/cheats_panel.gd") as Script).new() as VBoxContainer
	_cheats.visible = false
	h.add_child(_cheats)
	_build_settings(h)


func _button(text: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = Vector2(260, 40)
	b.add_theme_font_size_override("font_size", 18)
	b.focus_mode = Control.FOCUS_NONE
	b.pressed.connect(cb)
	return b


func _fill_controls() -> void:
	for c in _controls.get_children():
		c.queue_free()
	var head := Label.new()
	head.text = "Управление — нажми на клавишу, чтобы сменить"
	head.add_theme_font_size_override("font_size", 22)
	head.add_theme_color_override("font_color", Color(1.0, 0.86, 0.6))
	_controls.add_child(head)
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(760, 520)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_controls.add_child(scroll)
	var grid := GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 18)
	grid.add_theme_constant_override("v_separation", 4)
	scroll.add_child(grid)
	for a in ACTIONS:
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 4)
		for act in String(a[0]).split("|"):
			if InputMap.has_action(act):
				row.add_child(_key_button(act))
		if row.get_child_count() == 0:
			row.queue_free()
			continue
		grid.add_child(row)
		grid.add_child(_desc(String(a[1])))
	for r in EXTRA:
		var k := Label.new()
		k.text = String(r[0])
		k.add_theme_color_override("font_color", Color(0.75, 0.72, 0.62))
		k.add_theme_font_size_override("font_size", 15)
		grid.add_child(k)
		grid.add_child(_desc(String(r[1])))
	_keys_note = Label.new()
	_keys_note.add_theme_font_size_override("font_size", 15)
	_keys_note.add_theme_color_override("font_color", Color(1.0, 0.55, 0.4))
	_keys_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_keys_note.custom_minimum_size.x = 720
	_controls.add_child(_keys_note)
	var reset := Button.new()
	reset.text = "Вернуть все клавиши по умолчанию"
	reset.focus_mode = Control.FOCUS_NONE
	reset.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	reset.pressed.connect(func() -> void:
		Settings.reset_keys()
		_fill_controls.call_deferred())
	_controls.add_child(reset)
	_show_conflicts()


func _desc(text: String) -> Label:
	var d := Label.new()
	d.text = text
	d.add_theme_color_override("font_color", Color(0.86, 0.86, 0.84))
	d.add_theme_font_size_override("font_size", 15)
	d.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	d.custom_minimum_size.x = 520
	return d


func _key_button(action: String) -> Button:
	var b := Button.new()
	b.text = key_name(action)
	b.custom_minimum_size = Vector2(54, 28)
	b.focus_mode = Control.FOCUS_NONE
	b.add_theme_font_size_override("font_size", 15)
	b.tooltip_text = "Нажми и затем нужную клавишу или кнопку мыши (Esc — отмена)"
	b.set_meta("action", action)
	b.pressed.connect(func() -> void:
		if _capture_btn and is_instance_valid(_capture_btn):
			_capture_btn.text = key_name(_capture)
		_capture = action
		_capture_btn = b
		b.text = "…")
	return b


## Занятые двумя действиями клавиши — красным и строкой под списком.
func _show_conflicts() -> void:
	var lines: Array[String] = []
	var seen: Dictionary = {}
	for n in _controls.find_children("*", "Button", true, false):
		if not n.has_meta("action"):
			continue
		var act := String(n.get_meta("action"))
		var others := Settings.key_conflicts(act)
		(n as Button).add_theme_color_override("font_color", Color(1.0, 0.45, 0.35) if not others.is_empty() else Color(1.0, 0.9, 0.7))
		if not others.is_empty() and not seen.has(key_name(act)):
			seen[key_name(act)] = true
			lines.append("%s — сразу у нескольких действий: %s" % [key_name(act), ", ".join(PackedStringArray([_action_title(act)] + others.map(func(o: String) -> String: return _action_title(o))))])
	_keys_note.text = "\n".join(lines)


static func _action_title(action: String) -> String:
	for a in ACTIONS:
		if action in String(a[0]).split("|"):
			return "«%s»" % String(a[1]).get_slice(" (", 0).get_slice(" —", 0)
	return action


## Клавиша действия по-человечески: «W», «Shift», «ПКМ».
static func key_name(action: String) -> String:
	if not InputMap.has_action(action):
		return ""
	for ev in InputMap.action_get_events(action):
		if ev is InputEventKey:
			var k := ev as InputEventKey
			var code := k.physical_keycode if k.physical_keycode != 0 else k.keycode
			return OS.get_keycode_string(code)
		if ev is InputEventMouseButton:
			match (ev as InputEventMouseButton).button_index:
				MOUSE_BUTTON_LEFT:
					return "ЛКМ"
				MOUSE_BUTTON_RIGHT:
					return "ПКМ"
				MOUSE_BUTTON_MIDDLE:
					return "СКМ"
				MOUSE_BUTTON_XBUTTON1:
					return "Мышь 4"
				MOUSE_BUTTON_XBUTTON2:
					return "Мышь 5"
	return ""


## Ждём новую клавишу: клавиша или кнопка мыши (не колесо) — назначить; Esc — отмена.
func _capture_input(event: InputEvent) -> bool:
	if _capture == "":
		return false
	var assign: InputEvent = null
	if event is InputEventKey and event.pressed and not event.is_echo():
		var k := event as InputEventKey
		if k.keycode == KEY_ESCAPE or k.physical_keycode == KEY_ESCAPE:
			if is_instance_valid(_capture_btn):
				_capture_btn.text = key_name(_capture)
			_capture = ""
			return true
		assign = k
	elif event is InputEventMouseButton and event.pressed:
		var mb := event as InputEventMouseButton
		if mb.button_index in [MOUSE_BUTTON_LEFT, MOUSE_BUTTON_RIGHT, MOUSE_BUTTON_MIDDLE, MOUSE_BUTTON_XBUTTON1, MOUSE_BUTTON_XBUTTON2]:
			assign = mb
	if assign == null:
		return false
	Settings.set_key(_capture, assign)
	if is_instance_valid(_capture_btn):
		_capture_btn.text = key_name(_capture)
	_capture = ""
	_show_conflicts()
	return true


func _input(event: InputEvent) -> void:
	if shown and _capture_input(event):
		get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("dev_console") and not event.is_echo() and not UiTheme.typing() and not Loading.visible:
		if shown:
			open_cheats()
		elif not _other_ui_open():
			open_cheats()
		get_viewport().set_input_as_handled()
		return
	if not event.is_action_pressed("pause") or event.is_echo():
		return
	if shown:
		close_menu()
		get_viewport().set_input_as_handled()
	elif not _other_ui_open():
		open_menu()
		get_viewport().set_input_as_handled()


## Другие окна закрываются своим Esc — меню тогда не открываем.
func _other_ui_open() -> bool:
	if Raid.current and Raid.current.ui_open():
		return true
	for n in get_tree().get_nodes_in_group("esc_windows"):
		if n.has_method("is_open") and bool(n.call("is_open")):
			return true
	return false


func open_menu() -> void:
	shown = true
	_root.visible = true
	_controls.visible = false
	_cheats.visible = false
	_settings.visible = false
	_mouse_before = Input.mouse_mode
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	var scene := get_tree().current_scene
	var in_raid := Raid.current != null
	var in_hideout := scene != null and scene.scene_file_path == Balance.HIDEOUT_SCENE
	var in_menu := scene != null and scene.scene_file_path == Balance.MAIN_MENU_SCENE
	_leave.visible = (in_raid or not in_hideout) and not in_menu
	_to_menu.visible = in_hideout
	# со снаряжением из профиля уход = потеря всего, что взял с собой (как смерть)
	_leave.text = "Покинуть рейд (снаряжение останется там)" if Profile.pending_raid else "В убежище"
	if not Net.is_networked():
		get_tree().paused = true


## Справа от кнопок — одна панель за раз (управление, настройки, читы); повторное нажатие — закрыть.
func _show_side(panel: Control) -> void:
	_capture = ""
	if panel == _controls:
		_fill_controls()
	var was := panel.visible
	for p in [_controls, _settings, _cheats]:
		(p as Control).visible = false
	panel.visible = not was


## Настройки: графика, мышь, громкость — применяются сразу (Settings).
func _build_settings(h: HBoxContainer) -> void:
	_settings = VBoxContainer.new()
	_settings.add_theme_constant_override("separation", 8)
	_settings.custom_minimum_size.x = 460
	_settings.visible = false
	h.add_child(_settings)
	_settings.add_child(_head("Настройки"))
	var grid := GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 18)
	grid.add_theme_constant_override("v_separation", 8)
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(540, 470)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_settings.add_child(scroll)
	scroll.add_child(grid)
	grid.add_child(_label("Графика"))
	var q := OptionButton.new()
	q.focus_mode = Control.FOCUS_NONE
	for k in Settings.QUALITY:
		q.add_item(String(Settings.QUALITY_NAMES[k]))
	q.selected = Settings.QUALITY.find(Settings.quality)
	q.item_selected.connect(func(i: int) -> void: Settings.set_quality(String(Settings.QUALITY[i])))
	grid.add_child(q)
	grid.add_child(_label("Экран (Alt+Enter)"))
	var wm := OptionButton.new()
	wm.focus_mode = Control.FOCUS_NONE
	for k in Settings.WINDOW_MODES:
		wm.add_item(String(Settings.WINDOW_NAMES[k]))
	wm.selected = Settings.WINDOW_MODES.find(Settings.window_mode)
	wm.item_selected.connect(func(i: int) -> void: Settings.set_window_mode(String(Settings.WINDOW_MODES[i])))
	# Alt+Enter переключил — выпадающий список показывает то же
	Settings.changed.connect(func() -> void:
		if is_instance_valid(wm):
			wm.selected = Settings.WINDOW_MODES.find(Settings.window_mode))
	grid.add_child(wm)
	grid.add_child(_label("Эффекты камеры"))
	var lens := CheckButton.new()
	lens.focus_mode = Control.FOCUS_NONE
	lens.button_pressed = Settings.lens_fx
	lens.tooltip_text = "Глаз привыкает к свету, объектив, зерно, цветокоррекция, оружие у лица в прицеле мягче."
	lens.toggled.connect(func(on: bool) -> void: Settings.set_lens_fx(on))
	grid.add_child(lens)
	grid.add_child(_label("Размытие в движении"))
	var blur := CheckButton.new()
	blur.focus_mode = Control.FOCUS_NONE
	blur.button_pressed = Settings.motion_blur
	blur.toggled.connect(func(on: bool) -> void: Settings.set_motion_blur(on))
	grid.add_child(blur)
	grid.add_child(_label("Хит-маркер"))
	var hitmarker: CheckButton = CheckButton.new()
	hitmarker.name = "HitmarkerToggle"
	hitmarker.focus_mode = Control.FOCUS_NONE
	hitmarker.button_pressed = Settings.hitmarker
	hitmarker.tooltip_text = "Показывать крестик при попадании и убийстве."
	hitmarker.toggled.connect(Settings.set_hitmarker)
	Settings.changed.connect(func() -> void: hitmarker.set_pressed_no_signal(Settings.hitmarker))
	grid.add_child(hitmarker)
	grid.add_child(_label("Клавиши"))
	var keys_btn := Button.new()
	keys_btn.text = "Сменить клавиши…"
	keys_btn.focus_mode = Control.FOCUS_NONE
	keys_btn.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	keys_btn.pressed.connect(func() -> void: _show_side(_controls))
	grid.add_child(keys_btn)
	grid.add_child(_label("Мышь от первого лица"))
	grid.add_child(_sens_row(Settings.sens_fps, func(v: float) -> void: Settings.set_sens(v, Settings.sens_iso)))
	grid.add_child(_label("Мышь в прицеле (ПКМ)"))
	grid.add_child(_sens_row(Settings.sens_ads, func(v: float) -> void: Settings.set_sens_ads(v)))
	grid.add_child(_label("Поворот камеры (СКМ)"))
	grid.add_child(_sens_row(Settings.sens_iso, func(v: float) -> void: Settings.set_sens(Settings.sens_fps, v)))
	grid.add_child(_label("Инвертировать мышь по вертикали"))
	var inv := CheckButton.new()
	inv.focus_mode = Control.FOCUS_NONE
	inv.button_pressed = Settings.invert_y
	inv.toggled.connect(func(on: bool) -> void: Settings.set_invert_y(on))
	grid.add_child(inv)
	grid.add_child(_label("Поле зрения (по горизонтали)"))
	var fov := _slider(Settings.FOV_H_RANGE[0], Settings.FOV_H_RANGE[1], 1.0, Settings.fov_h, "%.0f°",
		func(v: float) -> void: Settings.set_fov_h(v))
	fov.tooltip_text = "От первого лица, как на экране 16:9. Руки и оружие — со своим полем зрения, прицелы увеличивают так же."
	grid.add_child(fov)
	grid.add_child(_label("Покачивание камеры"))
	var bob := _slider(0.0, 1.0, 0.05, Settings.camera_motion, "%.0f%%",
		func(v: float) -> void: Settings.set_camera_motion(v), 100.0)
	bob.name = "CameraMotionSlider"
	bob.tooltip_text = "Шаги, бег, остановка и приземление: камера передаёт вес тела. 0 % — камера стоит ровно, оружие в руках качается как прежде."
	grid.add_child(bob)
	for b in Settings.BUSES:
		var bus := String(b)
		grid.add_child(_label("Громкость: " + String(Settings.BUSES[b]).to_lower()))
		grid.add_child(_slider(0.0, 1.0, 0.05, float(Settings.volume[bus]), "%.0f%%",
			func(v: float) -> void: Settings.set_volume(bus, v), 100.0))
	var hint := Label.new()
	hint.text = "«Низко» — если тормозит: без глобального освещения, тумана и SSAO, рендер в 77 %."
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.custom_minimum_size.x = 440
	hint.add_theme_font_size_override("font_size", 14)
	hint.add_theme_color_override("font_color", Color(0.7, 0.7, 0.68))
	_settings.add_child(hint)


func _head(text: String) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", 22)
	l.add_theme_color_override("font_color", Color(1.0, 0.86, 0.6))
	return l


func _label(text: String) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", 16)
	l.add_theme_color_override("font_color", Color(0.86, 0.86, 0.84))
	return l


## Ползунок с подписью значения справа; show_mult — множитель для подписи (доли → проценты).
## Чувствительность: ползунок по экспоненте (тонко внизу, быстро вверху) + поле для точного числа;
## друг за другом следят.
func _sens_row(value: float, cb: Callable) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	var s := HSlider.new()
	s.min_value = Settings.SENS_RANGE[0]
	s.max_value = Settings.SENS_RANGE[1]
	s.step = 0.01
	s.exp_edit = true
	s.value = value
	s.custom_minimum_size = Vector2(190, 24)
	s.focus_mode = Control.FOCUS_NONE
	var box := SpinBox.new()
	box.min_value = Settings.SENS_RANGE[0]
	box.max_value = Settings.SENS_RANGE[1]
	box.step = 0.01
	box.prefix = "×"
	box.value = value
	box.custom_minimum_size.x = 96
	s.value_changed.connect(func(x: float) -> void:
		box.set_value_no_signal(x)
		cb.call(x))
	box.value_changed.connect(func(x: float) -> void:
		s.set_value_no_signal(x)
		cb.call(x))
	row.add_child(s)
	row.add_child(box)
	var reset := Button.new()
	reset.text = "×1"
	reset.tooltip_text = "Сбросить на обычную"
	reset.focus_mode = Control.FOCUS_NONE
	reset.pressed.connect(func() -> void:
		s.set_value_no_signal(1.0)
		box.set_value_no_signal(1.0)
		cb.call(1.0))
	row.add_child(reset)
	return row


func _slider(lo: float, hi: float, step: float, value: float, fmt: String, cb: Callable, show_mult: float = 1.0) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	var s := HSlider.new()
	s.min_value = lo
	s.max_value = hi
	s.step = step
	s.value = value
	s.custom_minimum_size = Vector2(190, 24)
	s.focus_mode = Control.FOCUS_NONE
	var v := Label.new()
	v.custom_minimum_size.x = 56
	v.text = fmt % (value * show_mult)
	s.value_changed.connect(func(x: float) -> void:
		v.text = fmt % (x * show_mult)
		cb.call(x))
	row.add_child(s)
	row.add_child(v)
	return row


## Главное меню: сразу настройки.
func open_settings() -> void:
	if not shown:
		open_menu()
	_controls.visible = false
	_cheats.visible = false
	_settings.visible = true


func open_cheats() -> void:
	if not shown:
		open_menu()
	_capture = ""
	_controls.visible = false
	_settings.visible = false
	_cheats.visible = true
	_cheats.call("refresh")


func close_menu() -> void:
	shown = false
	_root.visible = false
	get_tree().paused = false
	Input.mouse_mode = _mouse_before


func _on_leave() -> void:
	close_menu()
	if Raid.current:
		Raid.current.go_hideout()
	else:
		Net.disconnect_all()
		Profile.pending_raid = false
		Net.change_scene(Balance.HIDEOUT_SCENE)
