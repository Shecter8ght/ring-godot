class_name UiTheme
extends RefCounted
## Общий вид всего, на что нажимают (кнопки, галочки, списки, поля ввода): правится умалчиваемая тема
## движка, поэтому действует во всех окнах сразу — и в тех, что собраны кодом под CanvasLayer.
## Кнопка «выпуклая»: светлая кромка сверху, тень снизу; под курсором — ярче и с золотой рамкой;
## нажатая — утоплена (тень пропадает, подпись уходит на пиксель вниз); включённая (вкладка, фильтр) —
## залита золотым. Курсор над кнопкой — «рука». Окно со своим стилем (конструктор) берёт цвета отсюда.

const C_TEXT := Color(0.93, 0.91, 0.86)
const C_ACCENT := Color(1.0, 0.8, 0.45)
const C_FACE := Color(0.2, 0.19, 0.175)
const C_FACE_HOVER := Color(0.29, 0.265, 0.225)
const C_FACE_DOWN := Color(0.13, 0.12, 0.105)
const C_ON := Color(0.62, 0.44, 0.16)
const C_ON_HOVER := Color(0.72, 0.52, 0.2)
const C_FIELD := Color(0.05, 0.05, 0.052)

static var _done: bool = false


## Грань кнопки: face — заливка, edge — рамка, lift — насколько приподнята (0 — утоплена).
static func face(col: Color, edge: Color, lift: int, radius: int = 5) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = col
	sb.border_color = edge
	sb.set_border_width_all(1)
	sb.border_width_bottom = 1 + lift
	sb.set_corner_radius_all(radius)
	sb.content_margin_left = 10
	sb.content_margin_right = 10
	# утопленная кнопка: подпись ниже на высоту кромки — видно, что нажата (высота кнопки та же)
	sb.content_margin_top = 4 + (2 - lift)
	sb.content_margin_bottom = 4 + lift
	if lift > 0:
		sb.shadow_color = Color(0, 0, 0, 0.45)
		sb.shadow_size = 2 + lift
		sb.shadow_offset = Vector2(0, 1 + lift)
	return sb


static func apply() -> void:
	if _done:
		return
	_done = true
	var t: Theme = ThemeDB.get_default_theme()
	if t == null:
		return
	var edge := Color(0.62, 0.54, 0.4, 0.75)
	var edge_dim := Color(0.4, 0.37, 0.32, 0.45)
	var normal := face(C_FACE, edge, 2)
	var hover := face(C_FACE_HOVER, C_ACCENT, 2)
	var pressed := face(C_ON, C_ACCENT, 0)
	var hover_pressed := face(C_ON_HOVER, Color(1.0, 0.9, 0.65), 0)
	var disabled := face(Color(0.115, 0.113, 0.11, 0.85), edge_dim, 0)
	for type: String in ["Button", "OptionButton", "MenuButton"]:
		t.set_stylebox("normal", type, normal)
		t.set_stylebox("hover", type, hover)
		t.set_stylebox("pressed", type, pressed)
		t.set_stylebox("hover_pressed", type, hover_pressed)
		t.set_stylebox("disabled", type, disabled)
		t.set_stylebox("focus", type, StyleBoxEmpty.new())
		t.set_color("font_color", type, C_TEXT)
		t.set_color("font_hover_color", type, Color(1.0, 0.95, 0.82))
		t.set_color("font_pressed_color", type, Color(1.0, 0.96, 0.86))
		t.set_color("font_hover_pressed_color", type, Color(1, 1, 1))
		t.set_color("font_focus_color", type, C_TEXT)
		t.set_color("font_disabled_color", type, Color(0.47, 0.46, 0.44))
	# галочки и переключатели: без плашки, но строка подсвечивается под курсором
	var row_hover := StyleBoxFlat.new()
	row_hover.bg_color = Color(1.0, 0.8, 0.45, 0.1)
	row_hover.set_corner_radius_all(4)
	row_hover.set_content_margin_all(4)
	var row_idle := StyleBoxEmpty.new()
	row_idle.set_content_margin_all(4)
	for type: String in ["CheckBox", "CheckButton"]:
		for state: String in ["normal", "pressed", "disabled", "focus"]:
			t.set_stylebox(state, type, row_idle)
		for state: String in ["hover", "hover_pressed"]:
			t.set_stylebox(state, type, row_hover)
		t.set_color("font_hover_color", type, Color(1.0, 0.95, 0.82))
		t.set_color("font_pressed_color", type, C_ACCENT)
		t.set_color("font_hover_pressed_color", type, Color(1.0, 0.9, 0.65))
	# поле ввода: тёмный «колодец», в работе — золотая рамка
	var field := StyleBoxFlat.new()
	field.bg_color = C_FIELD
	field.border_color = edge_dim
	field.set_border_width_all(1)
	field.set_corner_radius_all(4)
	field.content_margin_left = 9
	field.content_margin_right = 9
	field.content_margin_top = 5
	field.content_margin_bottom = 5
	var field_focus := field.duplicate() as StyleBoxFlat
	field_focus.border_color = C_ACCENT
	field_focus.bg_color = Color(0.075, 0.07, 0.06)
	for type: String in ["LineEdit", "TextEdit"]:
		t.set_stylebox("normal", type, field)
		t.set_stylebox("focus", type, field_focus)
		t.set_color("caret_color", type, C_ACCENT)
		t.set_color("font_placeholder_color", type, Color(0.55, 0.54, 0.5))
	# выпадающие списки и меню правой кнопки: строка под курсором — золотая
	var item_hover := StyleBoxFlat.new()
	item_hover.bg_color = Color(0.62, 0.44, 0.16, 0.85)
	item_hover.set_corner_radius_all(3)
	t.set_stylebox("hover", "PopupMenu", item_hover)
	var menu := StyleBoxFlat.new()
	menu.bg_color = Color(0.085, 0.08, 0.075, 0.98)
	menu.border_color = edge
	menu.set_border_width_all(1)
	menu.set_corner_radius_all(5)
	menu.set_content_margin_all(6)
	menu.shadow_color = Color(0, 0, 0, 0.5)
	menu.shadow_size = 6
	t.set_stylebox("panel", "PopupMenu", menu)
	t.set_color("font_hover_color", "PopupMenu", Color(1, 1, 1))
	t.set_constant("v_separation", "PopupMenu", 8)


## Новая кнопка в дереве: курсор-«рука» (в теме его нет — ставится узлу).
static func on_node_added(node: Node) -> void:
	var b := node as BaseButton
	if b and b.mouse_default_cursor_shape == Control.CURSOR_ARROW:
		b.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND


## Набирают ли сейчас текст (курсор в поле ввода): клавиши-действия — журнал, карта, рюкзак, фонарь —
## в это время не срабатывают, буква идёт в поле.
static func typing() -> bool:
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null or tree.root == null:
		return false
	var f: Control = tree.root.gui_get_focus_owner()
	if f is LineEdit:
		return (f as LineEdit).editable and f.is_visible_in_tree()
	return f is TextEdit and (f as TextEdit).editable and f.is_visible_in_tree()
