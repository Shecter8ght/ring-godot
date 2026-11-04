class_name PhoneScreen
extends Control
## The physical display's independent 720 x 1556 interface, rendered by a SubViewport.
signal shutter
signal zoom_changed(value: float)

const RESOLUTION := Vector2i(720, 1556)
const INK := Color(0.95, 0.96, 0.98)
const MUTED := Color(0.57, 0.62, 0.69)
const ACCENT := Color(0.38, 0.79, 0.73)
var app: String = "Камера"
var viewfinder: Texture2D
var photos: Array = []
var zoom: float = 1.0
var _page: Control
var _toast: Label
var _toast_left: float = 0.0
var _thread: String = "car_recovery"
var _clock: Label


func _ready() -> void:
	size = Vector2(RESOLUTION)
	var background := ColorRect.new()
	background.color = Color(0.025, 0.032, 0.043)
	background.size = size
	background.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(background)
	_clock = label(self, "12:00", Rect2(46, 72, 180, 50), 30)
	label(self, "НЕТ СЕТИ", Rect2(480, 72, 198, 50), 23, MUTED)
	_page = Control.new()
	_page.position = Vector2(0, 164)
	_page.size = Vector2(720, 1270)
	add_child(_page)
	for i: int in range(4):
		var title: String = ["Камера", "Снимки", "Заказы", "Связь"][i]
		var button := button(self, title, Rect2(i * 180 + 8, 1440, 164, 74), 25)
		button.pressed.connect(select.bind(title))
	var home := panel(self, Rect2(255, 1532, 210, 7), Color(0.8, 0.82, 0.86), 4)
	home.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_toast = label(self, "", Rect2(45, 1275, 630, 100), 26, INK)
	_toast.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_toast.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_toast.mouse_filter = Control.MOUSE_FILTER_IGNORE
	Quests.changed.connect(refresh)
	refresh()


func _process(delta: float) -> void:
	_clock.text = DayCycle.current.clock_text() if is_instance_valid(DayCycle.current) else "12:00"
	_toast_left = maxf(0, _toast_left - delta)
	_toast.visible = _toast_left > 0


func toast(text: String) -> void:
	_toast.text = text
	_toast_left = 2.5


func select(title: String) -> void:
	app = title
	refresh()


func refresh() -> void:
	if _page == null:
		return
	for child: Node in _page.get_children():
		_page.remove_child(child)
		child.queue_free()
	match app:
		"Камера": camera_page()
		"Снимки": gallery_page()
		"Заказы": orders_page()
		"Связь": messages_page()


func camera_page() -> void:
	label(_page, "ФОТО", Rect2(40, 0, 300, 66), 30)
	label(_page, "Сохраняется на телефоне", Rect2(340, 8, 345, 55), 21, MUTED)
	var image := TextureRect.new()
	image.position = Vector2(0, 82)
	image.size = Vector2(720, 960)
	image.texture = viewfinder
	image.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	image.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	image.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_page.add_child(image)
	var focus := FocusFrame.new()
	focus.position = Vector2(240, 450)
	focus.size = Vector2(240, 240)
	focus.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_page.add_child(focus)
	for i: int in range(2):
		var value: float = 1.0 if i == 0 else 2.0
		var z := button(_page, "%d×" % int(value), Rect2(250 + i * 112, 1060, 108, 60), 27)
		z.modulate = ACCENT if zoom == value else INK
		z.pressed.connect(func() -> void: zoom = value; zoom_changed.emit(value); refresh())
	var shot := button(_page, "●", Rect2(304, 1140, 112, 112), 75)
	shot.add_theme_stylebox_override("normal", style(Color(0.9, 0.93, 0.96), 56))
	shot.add_theme_color_override("font_color", Color(0.025, 0.032, 0.043))
	shot.pressed.connect(func() -> void: shutter.emit())
	label(_page, "БОКОВАЯ КНОПКА", Rect2(430, 1164, 270, 70), 20, MUTED)
	if not photos.is_empty():
		var last := TextureButton.new()
		last.position = Vector2(46, 1158)
		last.size = Vector2(78, 78)
		last.ignore_texture_size = true
		last.stretch_mode = TextureButton.STRETCH_KEEP_ASPECT_COVERED
		last.texture_normal = photos[0].texture
		last.pressed.connect(select.bind("Снимки"))
		_page.add_child(last)


func gallery_page() -> void:
	label(_page, "Снимки", Rect2(40, 0, 620, 82), 46)
	label(_page, "%d сохранено на устройстве" % photos.size(), Rect2(40, 88, 640, 60), 25, MUTED)
	if photos.is_empty():
		label(_page, "Здесь появятся сделанные кадры.", Rect2(60, 480, 600, 150), 30, MUTED)
		return
	var scroll := ScrollContainer.new()
	scroll.position = Vector2(30, 180)
	scroll.size = Vector2(660, 1050)
	_page.add_child(scroll)
	var grid := GridContainer.new()
	grid.columns = 3
	grid.add_theme_constant_override("h_separation", 9)
	grid.add_theme_constant_override("v_separation", 9)
	scroll.add_child(grid)
	for photo: Dictionary in photos:
		var thumb := TextureButton.new()
		thumb.custom_minimum_size = Vector2(211, 282)
		thumb.ignore_texture_size = true
		thumb.stretch_mode = TextureButton.STRETCH_KEEP_ASPECT_COVERED
		thumb.texture_normal = photo.texture
		thumb.pressed.connect(view_photo.bind(photo))
		grid.add_child(thumb)


func view_photo(photo: Dictionary) -> void:
	for child: Node in _page.get_children(): child.queue_free()
	var image := TextureRect.new()
	image.position = Vector2(0, 100)
	image.size = Vector2(720, 1020)
	image.texture = photo.texture
	image.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	image.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_page.add_child(image)
	button(_page, "‹ Снимки", Rect2(30, 0, 300, 75), 32).pressed.connect(refresh)
	label(_page, String(photo.get("time", "")), Rect2(40, 1140, 640, 70), 27, MUTED)


func orders_page() -> void:
	label(_page, "Заказы", Rect2(40, 0, 620, 90), 46)
	var column := scrolling_column(_page, Rect2(36, 125, 648, 1110))
	var found := false
	for qid: String in Quests.ids():
		if Quests.state(qid) != "ACTIVE": continue
		found = true
		var box := VBoxContainer.new()
		box.custom_minimum_size.x = 600
		box.add_theme_constant_override("separation", 22)
		column.add_child(box)
		flow_label(box, String(Quests.def(qid).get("title", qid)), 31, INK)
		flow_label(box, String(Quests.objective(qid).get("text", Quests.status(qid))), 29, ACCENT)
		flow_label(box, String(Quests.def(qid).get("summary", "")), 24, MUTED)
		var gap := Control.new(); gap.custom_minimum_size.y = 40; box.add_child(gap)
	if not found: flow_label(column, "Активных заказов нет. Новые заказы — в терминале убежища.", 30, MUTED)


func messages_page() -> void:
	label(_page, "Связь", Rect2(40, 0, 620, 90), 46)
	var connected := Quests.field_link_unlocked(_thread)
	var state := "Канал мастерской подключён" if connected else "Нет полевого модема"
	label(_page, state, Rect2(40, 92, 640, 65), 27, ACCENT if connected else MUTED)
	var column := scrolling_column(_page, Rect2(36, 178, 648, 810))
	flow_label(column, String(Quests.def(_thread).get("title", "Илья · мастерская")), 30, INK)
	var log: Array = Quests.thread_log(_thread)
	for entry: Variant in log.slice(maxi(0, log.size() - 12)):
		var who := String(entry[0]) if entry is Array and entry.size() > 1 else ""
		var text := String(entry[1]) if entry is Array and entry.size() > 1 else String(entry)
		flow_label(column, String({"player":"Я", "ilya":"Илья", "kirill":"Кирилл", "nina":"Нина"}.get(who, who)), 23, ACCENT)
		flow_label(column, text, 27, INK)
	if log.is_empty(): flow_label(column, "Переписка появится после принятия заказа в убежище.", 29, MUTED)
	column.get_parent().set_deferred("scroll_vertical", 100000)
	var action := Quests.field_action(_thread)
	var send := button(_page, "Отправить пакет снимков", Rect2(36, 1020, 648, 88), 29)
	send.disabled = action.is_empty()
	send.pressed.connect(func() -> void: Quests.request_field_report(_thread))
	var note := "Сотовые станции отключены. Ранние отчёты отправляются из убежища."
	if connected:
		note = "Отдельный радиоканал мастерской. Отправка станет доступна, когда пакет снимков будет собран." if action.is_empty() else "Пакет собран. Можно отправить снимки Кириллу по радиоканалу мастерской."
	label(_page, note, Rect2(40, 1140, 640, 120), 24, MUTED).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART


static func style(color: Color, radius: int) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = color
	s.corner_radius_top_left = radius; s.corner_radius_top_right = radius
	s.corner_radius_bottom_left = radius; s.corner_radius_bottom_right = radius
	return s

static func panel(parent: Node, rect: Rect2, color: Color, radius: int) -> Panel:
	var p := Panel.new(); p.position = rect.position; p.size = rect.size
	p.add_theme_stylebox_override("panel", style(color, radius)); parent.add_child(p); return p

static func label(parent: Node, text: String, rect: Rect2, font: int, color: Color = INK) -> Label:
	var l := Label.new(); l.text = text; l.position = rect.position; l.size = rect.size
	l.add_theme_font_size_override("font_size", font); l.add_theme_color_override("font_color", color)
	parent.add_child(l); return l

static func button(parent: Node, text: String, rect: Rect2, font: int) -> Button:
	var b := Button.new(); b.text = text; b.position = rect.position; b.size = rect.size
	b.add_theme_font_size_override("font_size", font); b.add_theme_color_override("font_color", INK)
	b.add_theme_stylebox_override("normal", style(Color(0.075, 0.09, 0.11), 18))
	b.add_theme_stylebox_override("hover", style(Color(0.12, 0.16, 0.18), 18))
	b.add_theme_stylebox_override("pressed", style(Color(0.17, 0.25, 0.27), 18))
	b.focus_mode = Control.FOCUS_NONE; parent.add_child(b); return b

static func scrolling_column(parent: Node, rect: Rect2) -> VBoxContainer:
	var scroll := ScrollContainer.new(); scroll.position = rect.position; scroll.size = rect.size
	parent.add_child(scroll)
	var col := VBoxContainer.new(); col.custom_minimum_size.x = rect.size.x - 18
	col.add_theme_constant_override("separation", 20); scroll.add_child(col); return col

static func flow_label(parent: Node, text: String, font: int, color: Color) -> void:
	var l := Label.new(); l.text = text; l.custom_minimum_size.x = 600
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.add_theme_font_size_override("font_size", font); l.add_theme_color_override("font_color", color)
	parent.add_child(l)

class FocusFrame extends Control:
	func _draw() -> void:
		for point: Vector2 in [Vector2.ZERO, Vector2(size.x, 0), size, Vector2(0, size.y)]:
			var dx := 1.0 if point.x == 0 else -1.0
			var dy := 1.0 if point.y == 0 else -1.0
			draw_line(point, point + Vector2(32 * dx, 0), Color(1, 1, 1, 0.65), 2)
			draw_line(point, point + Vector2(0, 32 * dy), Color(1, 1, 1, 0.65), 2)
