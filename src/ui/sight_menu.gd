class_name SightMenu
extends CanvasLayer
## Настройка голографического прицела ЛУМАР в руках (клавиша «sight_menu», по умолчанию P): форма
## метки, её цвет и толщина, ночной режим окна прицела (кнопка NV на самом прицеле). Выбор виден
## сразу — окно небольшое, прицел рядом. Форма, цвет и толщина — привычка игрока (Settings.reticle,
## сохраняются); ночной режим — состояние прицела в руках (CameraRig.sight_nv).

## Формы метки: номер в шейдере (lumar_reticle.gdshader) и подпись.
const SHAPES := [[1, "Кольцо с точкой"], [0, "Точка"], [2, "Шеврон"], [3, "Крест"], [4, "Кольцо с перекрестием"]]
const COLORS := [["Красная", Color(1.0, 0.12, 0.05)], ["Зелёная", Color(0.2, 1.0, 0.3)], ["Янтарная", Color(1.0, 0.62, 0.1)],
	["Голубая", Color(0.3, 0.8, 1.0)], ["Белая", Color(0.95, 0.95, 0.9)]]
const BOLDS := [[1.0, "Тонкая"], [1.7, "Обычная"], [2.6, "Жирная"]]

var rig: CameraRig
var _root: Control
var _box: VBoxContainer
var _opened_frame: int = -1


func _ready() -> void:
	layer = 21
	add_to_group("esc_windows")
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.visible = false
	_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_root)
	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER_RIGHT)
	panel.offset_left = -470
	panel.offset_right = -40
	panel.offset_top = -230
	panel.offset_bottom = 230
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.07, 0.065, 0.06, 0.93)
	sb.border_color = Color(0.95, 0.78, 0.5, 0.4)
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(5)
	sb.set_content_margin_all(16)
	panel.add_theme_stylebox_override("panel", sb)
	_root.add_child(panel)
	_box = VBoxContainer.new()
	_box.add_theme_constant_override("separation", 8)
	panel.add_child(_box)


func is_open() -> bool:
	return _root.visible


func open() -> void:
	_root.visible = true
	_opened_frame = Engine.get_process_frames()
	Audio.play_ui("tac_click")
	_fill()


func close_ui() -> void:
	_root.visible = false


func _process(_delta: float) -> void:
	if not _root.visible or Engine.get_process_frames() == _opened_frame:
		return
	if Input.is_action_just_pressed("ui_cancel") or Input.is_action_just_pressed("sight_menu"):
		close_ui()


func _label(text: String, size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return l


func _fill() -> void:
	for c in _box.get_children():
		_box.remove_child(c)
		c.queue_free()
	_box.add_child(_label("ЛУМАР H1 — настройка прицела", 20, Color(1.0, 0.86, 0.6)))
	_box.add_child(_label("Форма", 14, Color(0.7, 0.7, 0.66)))
	var shapes := HFlowContainer.new()
	shapes.add_theme_constant_override("h_separation", 6)
	shapes.add_theme_constant_override("v_separation", 6)
	_box.add_child(shapes)
	for row: Array in SHAPES:
		var id := int(row[0])
		shapes.add_child(_pick(String(row[1]), int(Settings.reticle.shape) == id, func() -> void: Settings.set_reticle("shape", id)))
	_box.add_child(_label("Цвет", 14, Color(0.7, 0.7, 0.66)))
	var colors := HFlowContainer.new()
	colors.add_theme_constant_override("h_separation", 6)
	colors.add_theme_constant_override("v_separation", 6)
	_box.add_child(colors)
	for i: int in range(COLORS.size()):
		var idx := i
		var b := _pick(String(COLORS[i][0]), int(Settings.reticle.color) == i, func() -> void: Settings.set_reticle("color", idx))
		b.add_theme_color_override("font_color", COLORS[i][1])
		b.add_theme_color_override("font_hover_color", COLORS[i][1])
		colors.add_child(b)
	_box.add_child(_label("Толщина", 14, Color(0.7, 0.7, 0.66)))
	var bolds := HBoxContainer.new()
	bolds.add_theme_constant_override("separation", 6)
	_box.add_child(bolds)
	for i: int in range(BOLDS.size()):
		var idx := i
		bolds.add_child(_pick(String(BOLDS[i][1]), int(Settings.reticle.bold) == i, func() -> void: Settings.set_reticle("bold", idx)))
	_box.add_child(HSeparator.new())
	_box.add_child(_label("Режим окна", 14, Color(0.7, 0.7, 0.66)))
	var modes := HBoxContainer.new()
	modes.add_theme_constant_override("separation", 6)
	_box.add_child(modes)
	var night: bool = rig != null and rig.sight_nv
	for mode: Array in [[false, "Обычный"], [true, "Ночной (NV)"]]:
		var on: bool = mode[0]
		modes.add_child(_pick(String(mode[1]), night == on, func() -> void:
			if rig:
				rig.sight_nv = on))
	_box.add_child(_label("Ночной: в окне прицела — усиленная зелёная картинка, видно в темноте без ПНВ и фонаря, но только в этом окошке. С ПНВ на голове не нужен.", 13, Color(0.6, 0.62, 0.6)))
	_box.add_child(_label("%s или Esc — закрыть" % PauseMenu.key_name("sight_menu"), 13, Color(0.6, 0.62, 0.6)))


## Кнопка-вариант: выбранная — нажата.
func _pick(text: String, chosen: bool, action: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.focus_mode = Control.FOCUS_NONE
	b.toggle_mode = true
	b.button_pressed = chosen
	b.add_theme_font_size_override("font_size", 14)
	b.pressed.connect(func() -> void:
		action.call()
		Audio.play_ui("tac_click")
		_fill())
	return b
