class_name PauseMenu
extends CanvasLayer
## Меню на Esc (autoload `Pause`): продолжить, управление, покинуть рейд / в убежище, выйти из игры.
## Соло — игра на паузе; в коопе мир идёт дальше (меню только закрывает экран и глушит ввод игрока).
## Esc открывает меню, только если не открыто другое окно (рюкзак, окно убежища, карта) — те
## закрываются своим Esc. Список клавиш собирается из InputMap: переназначат клавишу — список
## покажет новую.

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
	["weapon_1", "Пистолет"],
	["weapon_2", "Основное оружие"],
	["weapon_3|weapon_4", "Дробовик / винтовка — только на полигоне"],
	["grenade", "Граната (держать — прицел броска)"],
	["flashlight", "Фонарь и ЛЦУ на оружии, подсветка сетки оптики — вкл / выкл"],
	["interact", "Двери, обыск, рубильники, подобрать"],
	["inventory", "Рюкзак"],
	["use_med", "Лечиться (из рюкзака)"],
	["camera_left|camera_right", "Изометрия — повернуть камеру; от первого лица — наклон"],
	["view_toggle", "Вид: изометрия / от первого лица"],
	["map", "Карта"],
	["pause", "Меню"],
]
## То, что не действие InputMap.
const EXTRA := [
	["СКМ + мышь", "Повернуть камеру"],
	["Enter", "После рейда — в убежище"],
]

var _root: Control
var _main: VBoxContainer
var _controls: VBoxContainer
var _leave: Button
var _view_btn: Button
var _mouse_before: Input.MouseMode = Input.MOUSE_MODE_VISIBLE


func _ready() -> void:
	layer = 50
	process_mode = Node.PROCESS_MODE_ALWAYS
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
	_main.add_child(_button("Управление", func() -> void: _controls.visible = not _controls.visible))
	_view_btn = _button("", func() -> void:
		CameraRig.set_first_person_mode(not CameraRig.first_person_mode)
		_view_btn.text = _view_text())
	_main.add_child(_view_btn)
	_leave = _button("Покинуть рейд", _on_leave)
	_main.add_child(_leave)
	_main.add_child(_button("Выйти из игры", func() -> void: get_tree().quit()))
	_controls = VBoxContainer.new()
	_controls.add_theme_constant_override("separation", 4)
	_controls.visible = false
	h.add_child(_controls)
	_fill_controls()


func _button(text: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = Vector2(260, 40)
	b.add_theme_font_size_override("font_size", 18)
	b.focus_mode = Control.FOCUS_NONE
	b.pressed.connect(cb)
	return b


func _fill_controls() -> void:
	var head := Label.new()
	head.text = "Управление"
	head.add_theme_font_size_override("font_size", 22)
	head.add_theme_color_override("font_color", Color(1.0, 0.86, 0.6))
	_controls.add_child(head)
	var grid := GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 22)
	grid.add_theme_constant_override("v_separation", 5)
	_controls.add_child(grid)
	var rows: Array = []
	for a in ACTIONS:
		var keys: Array[String] = []
		for act in String(a[0]).split("|"):
			var k := key_name(act)
			if k != "":
				keys.append(k)
		if not keys.is_empty():
			rows.append([" ".join(keys), String(a[1])])
	rows.append_array(EXTRA)
	for r in rows:
		var k := Label.new()
		k.text = String(r[0])
		k.add_theme_color_override("font_color", Color(1.0, 0.9, 0.7))
		k.add_theme_font_size_override("font_size", 16)
		grid.add_child(k)
		var d := Label.new()
		d.text = String(r[1])
		d.add_theme_color_override("font_color", Color(0.86, 0.86, 0.84))
		d.add_theme_font_size_override("font_size", 16)
		grid.add_child(d)


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
	return ""


func _input(event: InputEvent) -> void:
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
	CameraRig.load_settings()
	_view_btn.text = _view_text()
	_mouse_before = Input.mouse_mode
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	var scene := get_tree().current_scene
	var in_raid := Raid.current != null
	var in_hideout := scene != null and scene.scene_file_path == Balance.HIDEOUT_SCENE
	_leave.visible = in_raid or not in_hideout
	# со снаряжением из профиля уход = потеря всего, что взял с собой (как смерть)
	_leave.text = "Покинуть рейд (снаряжение останется там)" if Profile.pending_raid else "В убежище"
	if not Net.is_networked():
		get_tree().paused = true


func _view_text() -> String:
	return "Вид: от первого лица (V)" if CameraRig.first_person_mode else "Вид: изометрия (V)"


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
		get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
