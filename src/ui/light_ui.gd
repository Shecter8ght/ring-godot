class_name LightUi
extends RefCounted
## Светлый вид окон (владелец 2026-10-30, макет «Б1 — витрина светлая»): тёплый светло-серый фон, белые панели,
## почти чёрный текст, один акцент — кирпично-оранжевый на главном действии и выбранной вкладке. Заголовки и
## подписи разделов — узкий гротеск капсом (Bahnschrift из Windows, иначе — шрифт движка), цифры и цены —
## моноширинные. Тема (theme()) ставится корню окна: кнопки, поля и надписи внутри берут её вместо тёмной
## умалчиваемой (UiTheme).

const BG := Color("eeece7")
const SURFACE := Color("ffffff")
const PLATE := Color("e7e4dd")
const STAGE := Color("e2dfd8")
const LINE := Color("dedad2")
const TRACK := Color("e8e5de")
const TEXT := Color("17181a")
const TEXT2 := Color("3d3e42")
const MUTED := Color("6d6e72")
const ACCENT := Color("c94e12")
const ACCENT_DARK := Color("a63e0b")
const ACCENT_SOFT := Color("fff3ea")
const LOCK := Color("a85a12")
const BAR := Color("2a2b2e")

## Сетки, слоты и фигура снаряжения в светлом окне (GridView, SlotView, EquipDoll, PouchPlaces, BodySilhouette)
const CELL_BG := Color("f7f6f3")
const CELL_LINE := Color(0, 0, 0, 0.07)
const ITEM := Color("ebe8e1")
const ITEM_EDGE := Color(0, 0, 0, 0.16)
const HALO := Color(1, 1, 1, 0.85)
const DIM := Color(0.96, 0.95, 0.93, 0.72)
const SLOT_EDGE := Color("cfcbc2")
const GOOD := Color("2e7d32")
const BAD := Color("b3361e")
const BLUE := Color("2f5f8f")
## Мета корня светлого окна: виджеты под ним рисуются светлыми.
const META := "light_ui"

static var _theme: Theme
static var _head: Font
static var _mono: Font


## Стоит ли узел в светлом окне (у кого-то из предков мета META).
static func inside(n: Node) -> bool:
	var p: Node = n
	while p != null:
		if p.has_meta(META):
			return bool(p.get_meta(META))
		p = p.get_parent()
	return false


## Цвет надписи прежнего тёмного окна → светлого: золото и оранжевое — акцент, красноватое — предупреждение,
## зелёное — «хорошо», синее — синее, светлое — основной текст, серое — приглушённый.
static func tone(c: Color) -> Color:
	var l := 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b
	if c.r > 0.85 and c.g > 0.6 and c.b < 0.75 and c.r - c.b > 0.2:
		return ACCENT_DARK
	if c.r > 0.75 and c.g < 0.62 and c.b < 0.6:
		return BAD
	if c.g > c.r + 0.1 and c.g > c.b:
		return GOOD
	if c.b > c.r + 0.15:
		return BLUE
	return TEXT if l > 0.8 else (TEXT2 if l > 0.65 else MUTED)


## Узкий гротеск для заголовков и подписей капсом.
static func head_font() -> Font:
	if _head == null:
		var f := SystemFont.new()
		f.font_names = PackedStringArray(["Bahnschrift", "Roboto Condensed", "Arial Narrow"])
		f.font_weight = 700
		f.font_stretch = 75
		_head = f
	return _head


## Моноширинный — цены, числа, счётчики.
static func mono_font() -> Font:
	if _mono == null:
		var f := SystemFont.new()
		f.font_names = PackedStringArray(["Consolas", "Roboto Mono", "DejaVu Sans Mono"])
		_mono = f
	return _mono


static func box(bg: Color, radius: int = 6, margin: int = 0, border: Color = Color(0, 0, 0, 0), border_w: int = 0) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.set_corner_radius_all(radius)
	sb.set_content_margin_all(margin)
	if border_w > 0:
		sb.border_color = border
		sb.set_border_width_all(border_w)
	return sb


## Тема светлого окна: обычная кнопка — белая с тонкой рамкой, под курсором — рамка акцентом, нажатая и
## включённая — залита акцентом; поле ввода — белое, в работе — рамка акцентом; надписи — тёмные.
static func theme() -> Theme:
	if _theme:
		return _theme
	var t := Theme.new()
	var normal := box(SURFACE, 6, 0, Color("c9c5bc"), 1)
	normal.content_margin_left = 14
	normal.content_margin_right = 14
	normal.content_margin_top = 6
	normal.content_margin_bottom = 6
	var hover := normal.duplicate() as StyleBoxFlat
	hover.border_color = ACCENT
	var pressed := normal.duplicate() as StyleBoxFlat
	pressed.bg_color = ACCENT
	pressed.border_color = ACCENT
	var hover_pressed := pressed.duplicate() as StyleBoxFlat
	hover_pressed.bg_color = ACCENT_DARK
	var disabled := normal.duplicate() as StyleBoxFlat
	disabled.bg_color = Color("f1efea")
	disabled.border_color = LINE
	for type: String in ["Button", "OptionButton", "MenuButton"]:
		t.set_stylebox("normal", type, normal)
		t.set_stylebox("hover", type, hover)
		t.set_stylebox("pressed", type, pressed)
		t.set_stylebox("hover_pressed", type, hover_pressed)
		t.set_stylebox("disabled", type, disabled)
		t.set_stylebox("focus", type, StyleBoxEmpty.new())
		t.set_color("font_color", type, TEXT)
		t.set_color("font_hover_color", type, TEXT)
		t.set_color("font_focus_color", type, TEXT)
		t.set_color("font_pressed_color", type, Color.WHITE)
		t.set_color("font_hover_pressed_color", type, Color.WHITE)
		t.set_color("font_disabled_color", type, Color("a3a29d"))
	var field := box(SURFACE, 6, 0, Color("c9c5bc"), 1)
	field.content_margin_left = 12
	field.content_margin_right = 12
	field.content_margin_top = 6
	field.content_margin_bottom = 6
	var field_focus := field.duplicate() as StyleBoxFlat
	field_focus.border_color = ACCENT
	for type: String in ["LineEdit", "TextEdit"]:
		t.set_stylebox("normal", type, field)
		t.set_stylebox("focus", type, field_focus)
		t.set_color("font_color", type, TEXT)
		t.set_color("caret_color", type, ACCENT)
		t.set_color("font_placeholder_color", type, Color("8d8e92"))
		t.set_color("selection_color", type, Color(0.79, 0.31, 0.07, 0.25))
	t.set_color("font_color", "Label", TEXT)
	t.set_color("default_color", "RichTextLabel", TEXT2)
	# полоса прокрутки: тонкая серая на светлом
	var grab := box(Color("c4c0b7"), 4)
	var grab_hi := box(Color("a9a59c"), 4)
	var track := box(Color(0, 0, 0, 0), 4)
	t.set_stylebox("scroll", "VScrollBar", track)
	t.set_stylebox("grabber", "VScrollBar", grab)
	t.set_stylebox("grabber_highlight", "VScrollBar", grab_hi)
	t.set_stylebox("grabber_pressed", "VScrollBar", grab_hi)
	_theme = t
	return t


static func label(text: String, size: int, color: Color = TEXT, font: Font = null) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	if font:
		l.add_theme_font_override("font", font)
	return l


## Подпись капсом узким гротеском (разделы, вкладки, надзаголовки).
static func caps(text: String, size: int, color: Color = MUTED) -> Label:
	return label(text.to_upper(), size, color, head_font())


static func mono(text: String, size: int, color: Color = TEXT) -> Label:
	return label(text, size, color, mono_font())


## Кнопка: primary — залита акцентом, белая подпись; secondary — рамка; pill / pill_on — вкладка-«пилюля»
## шапки; tab / tab_on — вкладка с чертой снизу.
static func button(text: String, kind: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.focus_mode = Control.FOCUS_NONE
	b.pressed.connect(cb)
	match kind:
		"primary":
			var sb := box(ACCENT, 6)
			var sh := box(ACCENT_DARK, 6)
			var sd := box(Color("d9c3b5"), 6)
			for st: String in ["normal", "pressed", "focus"]:
				b.add_theme_stylebox_override(st, sb)
			b.add_theme_stylebox_override("hover", sh)
			b.add_theme_stylebox_override("hover_pressed", sh)
			b.add_theme_stylebox_override("disabled", sd)
			for c: String in ["font_color", "font_hover_color", "font_pressed_color", "font_hover_pressed_color", "font_focus_color", "font_disabled_color"]:
				b.add_theme_color_override(c, Color.WHITE)
			b.add_theme_font_override("font", head_font())
		"pill", "pill_on":
			var on := kind == "pill_on"
			var sb := box(ACCENT if on else Color(0, 0, 0, 0), 18)
			sb.content_margin_left = 18
			sb.content_margin_right = 18
			var sh := box(ACCENT_DARK if on else Color(0, 0, 0, 0.06), 18)
			sh.content_margin_left = 18
			sh.content_margin_right = 18
			for st: String in ["normal", "pressed", "focus", "disabled"]:
				b.add_theme_stylebox_override(st, sb)
			b.add_theme_stylebox_override("hover", sh)
			b.add_theme_stylebox_override("hover_pressed", sh)
			var fc := Color.WHITE if on else TEXT2
			for c: String in ["font_color", "font_hover_color", "font_pressed_color", "font_hover_pressed_color", "font_focus_color"]:
				b.add_theme_color_override(c, fc)
			b.add_theme_font_override("font", head_font())
		"tab", "tab_on":
			var on := kind == "tab_on"
			var sb := StyleBoxFlat.new()
			sb.bg_color = Color(0, 0, 0, 0)
			sb.border_color = ACCENT
			sb.border_width_bottom = 3 if on else 0
			sb.content_margin_left = 2
			sb.content_margin_right = 2
			sb.content_margin_top = 8
			sb.content_margin_bottom = 8 - (3 if on else 0) + 3
			var sh := sb.duplicate() as StyleBoxFlat
			if not on:
				sh.border_color = Color("b9b5ac")
				sh.border_width_bottom = 3
				sh.content_margin_bottom = 8
			for st: String in ["normal", "pressed", "focus", "disabled"]:
				b.add_theme_stylebox_override(st, sb)
			b.add_theme_stylebox_override("hover", sh)
			b.add_theme_stylebox_override("hover_pressed", sh)
			var fc := TEXT if on else Color("55565a")
			for c: String in ["font_color", "font_hover_color", "font_pressed_color", "font_hover_pressed_color", "font_focus_color"]:
				b.add_theme_color_override(c, fc)
			b.add_theme_font_override("font", head_font())
	return b
