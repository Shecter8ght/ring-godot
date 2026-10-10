class_name ItemCard
extends PanelContainer
## Плашка предмета для окон (торговец, схема оружия): иконка на подложке цвета категории, имя,
## строка подробностей, цена; снизу — ряд кнопок (controls). Без иконки — плашка цвета категории.
## В правом верхнем углу иконки — «i»: описание предмета простыми словами (ItemInfo).

const W := 200.0

var controls: HBoxContainer
## Строка цены (нет цены — null): окно правит её на месте, когда меняют количество.
var price_label: Label


## entry — запись предмета (id, n, состояние) или {id}; sub — подробности; price — "" без цены;
## plain — только имя (витрина торговца: новое, состояние писать незачем).
static func make(entry: Dictionary, sub: String, price: String, width: float = W, plain: bool = false) -> ItemCard:
	var c := ItemCard.new()
	c.custom_minimum_size = Vector2(width, 0)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.11, 0.105, 0.1, 0.96)
	sb.border_color = Color(0.95, 0.78, 0.5, 0.18)
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(3)
	sb.set_content_margin_all(8)
	c.add_theme_stylebox_override("panel", sb)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 4)
	c.add_child(v)
	var icon := IconBox.new()
	icon.id = String(entry.get("id", ""))
	icon.entry = entry
	icon.custom_minimum_size = Vector2(0, 78)
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
	var name := _label(title + ("  ×%d" % n if n > 1 else ""), 14, Color(0.93, 0.91, 0.86))
	v.add_child(name)
	if sub != "":
		v.add_child(_label(sub, 12, Color(0.66, 0.68, 0.66)))
	if price != "":
		c.price_label = _label(price, 14, Color(0.72, 0.87, 0.66))
		v.add_child(c.price_label)
	c.controls = HBoxContainer.new()
	c.controls.add_theme_constant_override("separation", 4)
	v.add_child(c.controls)
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

	func _draw() -> void:
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
