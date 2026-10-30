class_name ItemCard
extends PanelContainer
## Плашка предмета для окон (торговец, схема оружия): иконка на подложке цвета категории, имя,
## строка подробностей, цена; снизу — ряд кнопок (controls). Без иконки — плашка цвета категории.
## В правом верхнем углу иконки — «i»: описание предмета простыми словами (ItemInfo).
## Ширина 0 — крупная карточка витрины (владелец 2026-10-30: «оружие мелкое, по 2–3 в строку»): тянется на
## колонку сетки, картинка — на нейтральном студийном фоне, высота картинки — доля ширины (BIG_ASPECT),
## предмет — свой снимок модели под этот кадр (ItemThumbs.card_texture).

const W := 200.0
const BIG_ASPECT := 0.42
## Кадр снимка предмета в крупной карточке (точки; пропорции — как у картинки карточки, BIG_ASPECT).
const BIG_FRAME := Vector2i(640, 268)
## Во сколько раз можно растянуть печёную иконку (96 точек на клетку) в крупной карточке.
const BIG_MAX_K := 1.35

var controls: HBoxContainer
## Строка цены (нет цены — null): окно правит её на месте, когда меняют количество.
var price_label: Label


## entry — запись предмета (id, n, состояние) или {id}; sub — подробности; price — "" без цены;
## plain — только имя (витрина торговца: новое, состояние писать незачем).
static func make(entry: Dictionary, sub: String, price: String, width: float = W, plain: bool = false) -> ItemCard:
	var c := ItemCard.new()
	var big := width <= 0.0
	c.custom_minimum_size = Vector2(maxf(width, 0.0), 0)
	if big:
		c.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.085, 0.09, 0.095, 0.98) if big else Color(0.11, 0.105, 0.1, 0.96)
	sb.border_color = Color(1, 1, 1, 0.09) if big else Color(0.95, 0.78, 0.5, 0.18)
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(4 if big else 3)
	sb.set_content_margin_all(10 if big else 8)
	c.add_theme_stylebox_override("panel", sb)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6 if big else 4)
	c.add_child(v)
	var icon := IconBox.new()
	icon.id = String(entry.get("id", ""))
	icon.entry = entry
	icon.custom_minimum_size = Vector2(0, 78)
	if big:
		icon.studio = true
		icon.aspect = BIG_ASPECT
	v.add_child(icon)
	var info := Button.new()
	info.text = "i"
	info.tooltip_text = "Описание"
	info.focus_mode = Control.FOCUS_NONE
	info.add_theme_font_size_override("font_size", 15)
	info.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	info.offset_left = -28
	info.offset_right = -3
	info.offset_top = 3
	info.offset_bottom = 28
	var e := entry.duplicate()
	info.pressed.connect(func() -> void: ItemInfo.open(c.popup_host(), e))
	icon.add_child(info)
	var n := int(entry.get("n", 1))
	var title := ItemDb.item_name(String(entry.get("id", ""))) if plain else ItemDb.label(entry)
	var name := _label(title + ("  ×%d" % n if n > 1 else ""), 18 if big else 14, Color(0.95, 0.95, 0.94) if big else Color(0.93, 0.91, 0.86))
	v.add_child(name)
	if sub != "":
		v.add_child(_label(sub, 13 if big else 12, Color(0.6, 0.63, 0.66) if big else Color(0.66, 0.68, 0.66)))
	if price != "":
		c.price_label = _label(price, 18 if big else 14, Color(0.78, 0.9, 0.7) if big else Color(0.72, 0.87, 0.66))
		v.add_child(c.price_label)
	c.controls = HBoxContainer.new()
	c.controls.add_theme_constant_override("separation", 4)
	v.add_child(c.controls)
	return c


## Строка списка светлого окна (LightUi, витрина Михалыча): слева снимок на светлой плашке, имя и подпись,
## справа цена; выбранная — с рамкой акцентом, закрытая — подпись цветом замка. Клик вешает окно.
static func row(entry: Dictionary, sub: String, price: String, selected: bool, locked: bool) -> ItemCard:
	var c := ItemCard.new()
	c.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	c.custom_minimum_size.y = 76
	var sb := LightUi.box(LightUi.ACCENT_SOFT if selected else LightUi.SURFACE, 6, 0,
		LightUi.ACCENT if selected else Color("e2ded6"), 2 if selected else 1)
	sb.content_margin_left = 8
	sb.content_margin_right = 14
	c.add_theme_stylebox_override("panel", sb)
	c.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 14)
	h.mouse_filter = Control.MOUSE_FILTER_IGNORE
	c.add_child(h)
	var icon := IconBox.new()
	icon.id = String(entry.get("id", ""))
	icon.entry = entry
	icon.studio = true
	icon.light = true
	icon.plate = LightUi.PLATE
	icon.pad = 5.0
	icon.frame = Vector2i(320, 145)
	icon.custom_minimum_size = Vector2(132, 60)
	icon.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	h.add_child(icon)
	var v := VBoxContainer.new()
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	v.alignment = BoxContainer.ALIGNMENT_CENTER
	v.add_theme_constant_override("separation", 2)
	v.mouse_filter = Control.MOUSE_FILTER_IGNORE
	h.add_child(v)
	var name := LightUi.label(ItemDb.item_name(String(entry.get("id", ""))), 18, LightUi.ACCENT_DARK if selected else LightUi.TEXT, LightUi.head_font())
	name.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	v.add_child(name)
	var s := LightUi.label(sub, 13, LightUi.LOCK if locked else LightUi.MUTED)
	s.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	v.add_child(s)
	c.price_label = LightUi.mono(price, 15, Color("8a8b8f") if locked else LightUi.TEXT2)
	c.price_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	h.add_child(c.price_label)
	for n: Control in [name, s, c.price_label]:
		n.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return c


## Куда класть окно описания: ближайший CanvasLayer сверху (окна убежища, рюкзак) — поверх них.
func popup_host() -> Node:
	var n: Node = self
	while n and not n is CanvasLayer:
		n = n.get_parent()
	return n if n else get_tree().root


## Отметка: 1 — подходит (золотая рамка), -1 — не к месту (приглушить), 0 — как есть.
func mark(k: int) -> void:
	var sb := (get_theme_stylebox("panel") as StyleBoxFlat).duplicate() as StyleBoxFlat
	if k > 0:
		sb.border_color = Color(1.0, 0.8, 0.35, 0.95)
		sb.set_border_width_all(2)
	add_theme_stylebox_override("panel", sb)
	modulate = Color(1, 1, 1, 0.35) if k < 0 else Color(1, 1, 1, 1)


static func _label(t: String, size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = t
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l


## Иконка предмета на подложке (как в сетках инвентаря).
class IconBox:
	extends Control
	var id: String = ""
	## Запись экземпляра (необязательно): у оружия рисуется его сборка.
	var entry: Dictionary = {}
	## Крупная карточка: студийный фон вместо цвета категории (категория — полоской снизу), оружие —
	## крупным снимком модели; высота — aspect от ширины.
	var studio: bool = false
	var aspect: float = 0.0
	## Светлые окна (LightUi): своя ровная подложка вместо студийной (прозрачная — без подложки, витрина) и свой
	## кадр снимка (нулевой — BIG_FRAME), отступ картинки от краёв.
	var plate: Color = Color(0, 0, 0, 0)
	var light: bool = false
	var frame: Vector2i = Vector2i.ZERO
	var pad: float = 12.0
	## снимать вне очереди (большой снимок витрины)
	var urgent: bool = false

	func _notification(what: int) -> void:
		if what == NOTIFICATION_RESIZED and aspect > 0.0:
			var h: float = roundf(size.x * aspect)
			if absf(custom_minimum_size.y - h) > 1.0:
				custom_minimum_size.y = h

	func _draw() -> void:
		if studio:
			_draw_studio()
			return
		var cat := String(ItemDb.item(id).get("cat", "misc"))
		var col: Color = GridView.CAT_COLOR.get(cat, Color(0.3, 0.3, 0.3))
		var r := Rect2(Vector2.ZERO, size)
		var has := ItemIcons.get_icon(id) != null
		draw_rect(r, ItemIcons.backdrop(col) if has else col)
		if entry.is_empty():
			ItemIcons.draw(self, id, r.grow(-4.0), false)
		else:
			ItemIcons.draw_entry(self, entry, r.grow(-4.0), false)
		draw_rect(r, Color(1, 1, 1, 0.12), false, 1.0)

	## Нейтральный серый фон сверху светлее, как студийная подложка: воронёный металл и песок читаются, фон не
	## спорит с предметом; цвет категории — тонкой полосой снизу.
	func _draw_studio() -> void:
		var r := Rect2(Vector2.ZERO, size)
		if light:
			if plate.a > 0.0:
				draw_rect(r, plate)
		else:
			var top := Color(0.33, 0.345, 0.36)
			var bottom := Color(0.2, 0.21, 0.225)
			draw_polygon(PackedVector2Array([r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)]),
				PackedColorArray([top, top, bottom, bottom]))
			var cat := String(ItemDb.item(id).get("cat", "misc"))
			var col: Color = GridView.CAT_COLOR.get(cat, Color(0.3, 0.3, 0.3))
			draw_rect(Rect2(r.position.x, r.end.y - 3.0, r.size.x, 3.0), col.lightened(0.35))
		var inner := r.grow(-pad)
		var tex: Texture2D = ItemThumbs.card_texture(entry if not entry.is_empty() else {"id": id}, frame if frame.x > 0 else ItemCard.BIG_FRAME, self, urgent)
		if tex:
			ItemIcons.draw_tex(self, tex, inner, false)
		else:
			ItemIcons.draw_tex(self, ItemIcons.entry_icon(entry if not entry.is_empty() else {"id": id}, self), inner, false, ItemCard.BIG_MAX_K)
