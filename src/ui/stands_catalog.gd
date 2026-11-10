extends ScrollContainer
## Интерактивные сцены отдельно от прогонов тестов и съёмки кадров.

const STANDS: Array[Array] = [
	["Поверхности и звуки карт", "scenes/debug/surface_audio_lab.tscn", "Пройди по всем покрытиям, сравни шаги на улице и в комнате, назначь фон карте.", "steps"],
	["Противник", "scenes/debug/enemy_lab.tscn", "Собери бойца, прокрути клипы, проверь падение и стрельбу в обе стороны.", "enemy"],
	["Камера и движение оружия", "scenes/debug/motion_lab.tscn", "Настрой голову, прыжок, направление качания на шаге и беге и дыхание в покое.", "weapon"],
	["Оружие и хват рук", "scenes/debug/weapon_pose_lab.tscn", "Положение оружия, обе кисти и пальцы. Осмотр и проверка в движении.", "weapon"],
	["Свет и атмосфера", "scenes/debug/atmosphere_lab.tscn", "Время суток, погода, солнце, тени, экспозиция и туман.", "light"],
	["Попадания и эффекты", "scenes/debug/impact_lab.tscn", "Сравни следы пуль, пыль, искры, обломки и разбитое стекло.", "impact"],
	["Зрение и слух противников", "scenes/debug/perception_lab.tscn", "Конус зрения, обнаружение через проём, шум и память мародёра.", "eye"],
	["Звуковой стенд", "", "Прослушай назначенные звуки оружия, предметов и карт. Настрой громкость.", "audio"],
]

const PROJECT_STANDS: Array[Array] = [
	["Стенд масштаба", "tools/scale_probe.tscn", "Пять вариантов габаритов улицы, комнаты и проходов. Сравнение поля зрения.", "map"],
	["Высота паркинга", "tools/parking_probe.tscn", "Пять залов с разной высотой потолка, балками и коммуникациями.", "map"],
	["Покрытия «Проспекта»", "tools/paving_probe.tscn", "Сравнение материалов дороги, тротуара, бордюра и площади.", "steps"],
	["Стенд анимаций", "tools/anim_stand.tscn", "Сравнение старых и новых движений рядом. Орбита, пауза и замедление.", "enemy"],
	["Телефон · хват", "tools/phone_grip_lab.tscn", "Правка запястья и суставов пальцев правой руки вокруг телефона.", "weapon"],
	["Осока · полигон", "tools/osoka_range.tscn", "Проверка прицела, захвата и пуска на карте «Плотина».", "weapon"],
	["Сравнение с Road to Vostok", "tools/rtv_look.tscn", "Две поляны для сравнения земли, деревьев и света. Нужна установленная Road to Vostok.", "light"],
	["Общежитие · свет", "tools/dorm_study.tscn", "Прогулка и проверка света, планировки и точек обзора.", "light"],
	["Общежитие · бой", "tools/dorm_play.tscn", "Игрок с оружием и расстановка ботов для проверки боёв в здании.", "enemy"],
	["«Плотина» · прогулка", "tools/heli_study.tscn", "Осмотр планировки, отметок высоты и маршрутов на карте «Плотина».", "map"],
	["«Плотина» · бой", "tools/dam_play.tscn", "Игровая прогулка по «Плотине» с оружием и ботами.", "enemy"],
	["«Проспект» · прогулка", "tools/prospekt_study.tscn", "Черновик квартала с планом, точками обзора и режимом полёта.", "map"],
	["ТЦ · прогулка", "tools/mall_study.tscn", "Черновик территории ТЦ. План, участки и полёт для осмотра.", "map"],
	["«Санаторий» · прогулка", "tools/sanatorium_study.tscn", "Осмотр корпусов, маршрутов, склона и берега на черновике карты.", "map"],
	["«Санаторий» · игровой проход", "tools/sanatorium_play.tscn", "Прогулка по черновику карты от первого лица.", "map"],
	["Кофейня «Зерно»", "tools/zerno_review/run.tscn", "Кофейня на тестовом «Проспекте». Осмотр зала, витрины и служебного выхода.", "map"],
]

const ICONS: Dictionary = {
	"steps": "M21 9l5 3 2 8-5 10-7-2-2-6z M13 31l8 2-2 6-7-2z M38 14l5 4 1 9-5 10-7-2-1-6z M32 39l8 2-2 6-8-2z",
	"enemy": "M24 24a8 8 0 1 1 16 0 8 8 0 1 1-16 0 M18 47v-4q0-9 14-9t14 9v4z M12 24v-10h10 M52 24v-10H42 M12 40v10h10 M52 40v10H42",
	"weapon": "M8 26h12l5-7h12v7h17v6H39l-4 12h-8l2-12H19l-5 8H8z",
	"light": "M24 31a8 8 0 1 1 16 0 8 8 0 1 1-16 0 M32 12v5 M32 45v5 M13 31h5 M46 31h5 M18 17l4 4 M42 41l4 4 M18 45l4-4 M42 21l4-4",
	"impact": "M32 16a16 16 0 1 0 16 16 M32 24a8 8 0 1 0 8 8 M32 32l18-18 M43 14h7v7 M26 8l-1 4 M52 39l4 2",
	"eye": "M9 32q23-24 46 0-23 24-46 0z M25 32a7 7 0 1 1 14 0 7 7 0 1 1-14 0",
	"audio": "M12 28v8h9l11 9V19l-11 9z M38 25q9 7 0 14 M44 19q15 13 0 26",
	"map": "M11 20l14-6 14 6 14-6v30l-14 6-14-6-14 6z M25 14v30 M39 20v30",
}

var _icons: Dictionary = {}
var _status: Label


func _ready() -> void:
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	follow_focus = true
	var content: VBoxContainer = VBoxContainer.new()
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.add_theme_constant_override("separation", 12)
	add_child(content)
	_status = _label("Выбери, что хочешь проверить или настроить.", 15, Color(0.72, 0.74, 0.75))
	content.add_child(_status)
	_add_cards(content, STANDS, false)
	if not OS.has_feature("editor"):
		return
	content.add_child(_label("Инструменты проекта · отдельные окна", 18, Color(1.0, 0.84, 0.58)))
	_add_cards(content, PROJECT_STANDS, true)


func _add_cards(parent: VBoxContainer, entries: Array[Array], external: bool) -> void:
	var grid: GridContainer = GridContainer.new()
	grid.add_theme_constant_override("h_separation", 10)
	grid.add_theme_constant_override("v_separation", 10)
	parent.add_child(grid)
	grid.resized.connect(func() -> void: grid.columns = 2 if grid.size.x >= 580.0 else 1)
	for entry: Array in entries:
		var path: String = "res://" + String(entry[1]) if entry[1] != "" else ""
		if path != "" and not ResourceLoader.exists(path, "PackedScene"):
			continue
		var card: Button = Button.new()
		card.text = String(entry[0])
		card.tooltip_text = String(entry[2])
		card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		card.custom_minimum_size.y = 108
		card.add_theme_color_override("font_color", Color.TRANSPARENT)
		card.add_theme_color_override("font_hover_color", Color.TRANSPARENT)
		card.add_theme_color_override("font_focus_color", Color.TRANSPARENT)
		card.add_theme_color_override("font_pressed_color", Color.TRANSPARENT)
		card.add_theme_font_size_override("font_size", 1)
		card.pressed.connect(_open.bind(path, String(entry[0]), external))
		grid.add_child(card)
		var row: HBoxContainer = HBoxContainer.new()
		row.mouse_filter = Control.MOUSE_FILTER_IGNORE
		card.add_child(row)
		row.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		row.offset_left = 12
		row.offset_right = -12
		row.offset_top = 10
		row.offset_bottom = -10
		row.add_theme_constant_override("separation", 12)
		var icon: TextureRect = TextureRect.new()
		icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
		icon.texture = _icon(String(entry[3]))
		icon.custom_minimum_size = Vector2(48, 48)
		icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		icon.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		row.add_child(icon)
		var copy: VBoxContainer = VBoxContainer.new()
		copy.mouse_filter = Control.MOUSE_FILTER_IGNORE
		copy.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		copy.alignment = BoxContainer.ALIGNMENT_CENTER
		row.add_child(copy)
		copy.add_child(_label(String(entry[0]), 18, Color(1.0, 0.89, 0.72)))
		copy.add_child(_label(String(entry[2]), 14, Color(0.77, 0.79, 0.80)))


func _label(value: String, font_size: int, color: Color) -> Label:
	var label: Label = Label.new()
	label.text = value
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	return label


func _icon(key: String) -> Texture2D:
	if not _icons.has(key):
		var drawing: Image = Image.new()
		drawing.load_svg_from_string(
			'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect x="1" y="1" width="62" height="62" rx="12" fill="#272922" stroke="#615541"/><path d="%s" fill="none" stroke="#efc383" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>' % String(ICONS[key]))
		_icons[key] = ImageTexture.create_from_image(drawing)
	return _icons[key] as Texture2D


func _open(path: String, title: String, external: bool) -> void:
	if path.is_empty():
		Pause.open_audio_bench()
	elif external:
		var pid: int = OS.create_instance(["--path", ProjectSettings.globalize_path("res://"), "--windowed", path])
		_status.text = "Открывается «%s»." % title if pid > 0 else "Не удалось открыть «%s»." % title
	else:
		Net.change_scene(path, title)
