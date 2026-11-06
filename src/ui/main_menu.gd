extends Control
## Главное меню (стартовая сцена): Продолжить (последнее сохранение), Новая игра (имя —
## новый профиль со стартовым набором), Загрузить (список сохранений: деньги, доверие, выходы;
## удалить — с подтверждением), Собрание (кооп: созвать своих хостом или подключиться по IP —
## встречаемся в убежище), Настройки (те же, что в меню Esc), Выход. Все сохранения — Saves.

const ACCENT := Color(1.0, 0.84, 0.58)
const DIM := Color(0.62, 0.63, 0.62)
const BEACON := Color(0.95, 0.16, 0.12)

var _side: VBoxContainer
var _status: Label


func _ready() -> void:
	# своё окно: Esc здесь не открывает меню паузы
	add_to_group("esc_windows")
	Net.enter_scene("menu")
	Saves.migrate_legacy()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_build()
	Net.money_received.connect(func(t: String) -> void: _status.text = t)


func is_open() -> bool:
	return true


func _build() -> void:
	var bg := ColorRect.new()
	bg.color = Color(0.028, 0.03, 0.036)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	var glow := _Glow.new()
	glow.set_anchors_preset(Control.PRESET_FULL_RECT)
	glow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(glow)
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 72 if side in ["left", "right"] else 64)
	add_child(margin)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 64)
	margin.add_child(row)
	var left := VBoxContainer.new()
	left.custom_minimum_size.x = 320
	left.add_theme_constant_override("separation", 10)
	row.add_child(left)
	var title := Label.new()
	title.text = "RING"
	title.add_theme_font_size_override("font_size", 96)
	title.add_theme_color_override("font_color", ACCENT)
	title.add_theme_constant_override("outline_size", 0)
	left.add_child(title)
	var sub := _label("Сектор 1 · торговый центр «РИНГ»", 16, DIM)
	left.add_child(sub)
	# в выпуске для друзей — метка сборки и номер патча: у хоста и гостя они должны совпадать
	if ReleasePatch.label() != "":
		left.add_child(_label(ReleasePatch.label(), 13, DIM))
	var gap := Control.new()
	gap.custom_minimum_size.y = 36
	left.add_child(gap)
	var last := Saves.last()
	if last != "":
		var nm := _save_name(last)
		left.add_child(_big("Продолжить  ·  " + nm, func() -> void: _play(last)))
	left.add_child(_big("Новая игра", _show_new))
	left.add_child(_big("Загрузить", _show_load))
	left.add_child(_big("Собрание (кооп)", _show_coop))
	left.add_child(_big("Настройки", func() -> void: Pause.open_settings()))
	left.add_child(_big("Оружие и хват рук", func() -> void:
		Net.change_scene("res://scenes/debug/weapon_pose_lab.tscn", "Стенд настройки оружия")))
	left.add_child(_big("Отладочные стенды", _show_labs))
	left.add_child(_big("Звуковой стенд", func() -> void: Pause.open_audio_bench()))
	left.add_child(_big("Выход", func() -> void: get_tree().quit()))
	var spacer := Control.new()
	spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	left.add_child(spacer)
	_status = _label("", 14, Color(1.0, 0.7, 0.5))
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	left.add_child(_status)
	_side = VBoxContainer.new()
	_side.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_side.add_theme_constant_override("separation", 10)
	row.add_child(_side)
	if last == "":
		_show_new()


func _clear_side(title: String) -> void:
	for c in _side.get_children():
		c.queue_free()
	_side.add_child(_label(title, 26, ACCENT))


## Новая игра: имя сохранения — и первый выход (пролог на «Проспекте», docs/design/prologue.md); «Пропустить
## пролог» — сразу в убежище со стартовым набором в тайнике.
func _show_new() -> void:
	_clear_side("Новая игра")
	_side.add_child(_label("Как назвать сохранение? Первый выход — через кордон закрытого района: снаряжение ждёт в закладке у входа. Пролог можно пропустить — тогда набор сразу в тайнике убежища.", 15, DIM))
	var name_edit := LineEdit.new()
	name_edit.placeholder_text = "Имя"
	name_edit.text = "Выживший %d" % (Saves.list().size() + 1)
	name_edit.custom_minimum_size = Vector2(360, 40)
	name_edit.add_theme_font_size_override("font_size", 18)
	_side.add_child(name_edit)
	var start := _big("Начать", func() -> void:
		var save_name: String = name_edit.text
		Prologue.launch(func() -> void: Saves.create(save_name, true)))
	start.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	_side.add_child(start)
	var skip := _big("Пропустить пролог", func() -> void:
		var save_name: String = name_edit.text
		Net.change_scene(Balance.HIDEOUT_SCENE, "Новая игра", func() -> void: Saves.create(save_name, false)))
	skip.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	_side.add_child(skip)
	name_edit.text_submitted.connect(func(_t: String) -> void: start.pressed.emit())


## Загрузить: сохранения карточками — имя, деньги, доверие, сколько раз вышел; удалить.
func _show_load() -> void:
	_clear_side("Загрузить")
	var saves := Saves.list()
	if saves.is_empty():
		_side.add_child(_label("Сохранений нет — начни новую игру.", 15, DIM))
		return
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_side.add_child(scroll)
	var list := VBoxContainer.new()
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.add_theme_constant_override("separation", 8)
	scroll.add_child(list)
	for s in saves:
		var d: Dictionary = s
		var card := PanelContainer.new()
		var sb := StyleBoxFlat.new()
		sb.bg_color = Color(0.09, 0.09, 0.1, 0.92)
		sb.border_color = Color(ACCENT, 0.18)
		sb.set_border_width_all(1)
		sb.set_content_margin_all(12)
		card.add_theme_stylebox_override("panel", sb)
		var h := HBoxContainer.new()
		h.add_theme_constant_override("separation", 12)
		card.add_child(h)
		var info := VBoxContainer.new()
		info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		info.add_child(_label(String(d.name), 20, Color(0.95, 0.93, 0.88)))
		info.add_child(_label("%s ₽  ·  доверие %d  ·  выходов из рейда %d  ·  %s" % [InventoryUI.money(int(d.money)), int(d.trust), int(d.extractions),
			Time.get_datetime_string_from_unix_time(int(d.time), true)], 14, DIM))
		h.add_child(info)
		var path := String(d.path)
		h.add_child(_small("Играть", func() -> void: _play(path)))
		h.add_child(_small("Удалить…", func() -> void: _confirm_delete(path, String(d.name))))
		list.add_child(card)


func _confirm_delete(path: String, nm: String) -> void:
	var dlg := ConfirmationDialog.new()
	dlg.title = "Удалить сохранение"
	dlg.dialog_text = "Удалить «%s» насовсем?" % nm
	dlg.ok_button_text = "Удалить"
	dlg.cancel_button_text = "Отмена"
	dlg.confirmed.connect(func() -> void:
		Saves.remove(path)
		get_tree().reload_current_scene())
	add_child(dlg)
	dlg.popup_centered()


## Собрание: встречаемся в убежище. Хост созывает, остальные — по его IP (порт 7777).
func _show_coop() -> void:
	_clear_side("Собрание")
	var last := Saves.last()
	if last == "":
		_side.add_child(_label("Сначала начни новую игру или загрузи сохранение — с ним и придёшь.", 15, DIM))
		return
	_side.add_child(_label("Своим сохранением («%s») — в общее убежище. Рейд начинает хост; каждый берёт своё снаряжение." % _save_name(last), 15, DIM))
	var cfg := ConfigFile.new()
	cfg.load(CameraRig.SETTINGS_PATH)
	var nick := LineEdit.new()
	nick.placeholder_text = "Ник"
	nick.text = String(cfg.get_value("net", "name", "Игрок%d" % (randi() % 900 + 100)))
	nick.custom_minimum_size = Vector2(360, 38)
	_side.add_child(nick)
	var remember := func(ip: String) -> void:
		cfg.set_value("net", "name", nick.text)
		if ip != "":
			cfg.set_value("net", "address", ip)
		cfg.save(CameraRig.SETTINGS_PATH)
	var host := _big("Созвать своих (я хост)", func() -> void:
		remember.call("")
		Saves.open(last)
		var err := Net.host(nick.text)
		if err != "":
			_status.text = err
			return
		Net.change_scene(Balance.HIDEOUT_SCENE, "Загрузка убежища"))
	host.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	_side.add_child(host)
	_side.add_child(_label("Друзьям нужен твой IP и открытый порт %d (UDP) — или общая сеть (Radmin VPN, ZeroTier)." % Net.PORT, 13, DIM))
	var ip := LineEdit.new()
	ip.placeholder_text = "IP хоста"
	ip.text = String(cfg.get_value("net", "address", "127.0.0.1"))
	ip.custom_minimum_size = Vector2(360, 38)
	_side.add_child(ip)
	var join := _big("Подключиться", func() -> void:
		remember.call(ip.text)
		Saves.open(last)
		var err := Net.join(ip.text, nick.text)
		if err != "":
			_status.text = err
			return
		_status.text = "Подключаюсь к %s…" % ip.text
		Net.joined.connect(func() -> void: Net.change_scene(Balance.HIDEOUT_SCENE, "Загрузка общего убежища"), CONNECT_ONE_SHOT)
		Net.join_failed.connect(func() -> void: _status.text = "Не удалось подключиться к %s" % ip.text, CONNECT_ONE_SHOT))
	join.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	_side.add_child(join)


func _play(path: String) -> void:
	# пролог не пройден — снова в первый выход (после гибели — от контрольной точки у кофейни)
	if Saves.prologue_pending(path):
		Prologue.launch(func() -> void: Saves.open(path))
		return
	Net.change_scene(Balance.HIDEOUT_SCENE, "Продолжить игру", func() -> void: Saves.open(path))


func _save_name(path: String) -> String:
	for s in Saves.list():
		if String(s.path) == path:
			return String(s.name)
	return path.get_file().get_basename()


func _big(t: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = t
	b.focus_mode = Control.FOCUS_NONE
	b.alignment = HORIZONTAL_ALIGNMENT_LEFT
	b.custom_minimum_size = Vector2(300, 44)
	b.add_theme_font_size_override("font_size", 20)
	b.pressed.connect(cb)
	return b


func _small(t: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = t
	b.focus_mode = Control.FOCUS_NONE
	b.add_theme_font_size_override("font_size", 15)
	b.pressed.connect(cb)
	return b


func _label(t: String, size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = t
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l


## Фон: красный отсвет заградительного огня на крыше в ночи — медленно дышит.
class _Glow:
	extends Control

	func _process(_delta: float) -> void:
		queue_redraw()

	func _draw() -> void:
		var t := Time.get_ticks_msec() / 1000.0
		var k := 0.75 + 0.25 * sin(t * 1.3)
		var c := Vector2(size.x * 0.78, size.y * 0.22)
		for i in range(18):
			var r := size.y * (0.06 + 0.05 * float(i))
			draw_circle(c, r, Color(0.95, 0.16, 0.12, 0.018 * k * (1.0 - float(i) / 18.0)))
		draw_circle(c, 5.0, Color(1.0, 0.45, 0.4, 0.9 * k))
		# горизонт — чуть светлее
		draw_rect(Rect2(0, size.y * 0.72, size.x, size.y * 0.28), Color(0.05, 0.06, 0.075, 0.6))


## Интерактивные стенды открываются отдельно от сохранения игрока.
func _show_labs() -> void:
	_clear_side("Отладочные стенды")
	for entry: Array in [
		["Свет и атмосфера", "atmosphere_lab", "Часы, погода, солнце, тени, экспозиция и туман."],
		["Попадания и эффекты", "impact_lab", "Материалы, пыль, обломки, искры и следы попаданий."],
		["Зрение и слух противников", "perception_lab", "Настоящий мародёр: конус зрения, обнаружение, шум и память."],
		["Оружие и хват рук", "weapon_pose_lab", "Положение оружия, обе кисти и пальцы. Осмотр, проверка в движении и сохранение."],
	]:
		var path: String = "res://scenes/debug/%s.tscn" % String(entry[1])
		var title: String = String(entry[0])
		_side.add_child(_big(title, func() -> void: Net.change_scene(path, title)))
		_side.add_child(_label(String(entry[2]), 16, DIM))
