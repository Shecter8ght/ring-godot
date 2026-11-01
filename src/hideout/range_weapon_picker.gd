class_name RangeWeaponPicker
extends CanvasLayer
## Окно стойки тира: всё оружие игры по классам; у ствола — его сборки из пресетов (штатный, с
## коллиматором, с глушителем…). Выбор выдаёт ствол на зал тира, «Сдать ствол» — вернуть своё.
## Окно локальное: у каждого игрока своё. Esc — закрыть.

const GROUPS := [
	["Пистолеты", ["PISTOL"]],
	["Пистолеты-пулемёты", ["SMG", "PDW"]],
	["Автоматы и карабины", ["ASSAULT_RIFLE", "CARBINE", "BATTLE_RIFLE"]],
	["Марксманские и бесшумные", ["DMR", "SPECIAL"]],
	["Снайперские винтовки", ["SNIPER"]],
	["Дробовики", ["SHOTGUN"]],
	["Пулемёты", ["LMG"]],
]

var _player: Player
var _root: Control
var _list: VBoxContainer
var _hand_label: Label
var _return_button: Button
## Свои надетые стволы — взять копию на зал для пристрелки (кнопки пересобираются при открытии).
var _own_box: HBoxContainer
var _opened_frame: int = -1


func _ready() -> void:
	layer = 20
	add_to_group("esc_windows")
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.visible = false
	add_child(_root)
	var dim: ColorRect = ColorRect.new()
	dim.color = Color(0, 0, 0, 0.45)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(dim)
	var panel: PanelContainer = PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_FULL_RECT)
	panel.offset_left = 120
	panel.offset_right = -120
	panel.offset_top = 70
	panel.offset_bottom = -70
	var sb: StyleBoxFlat = StyleBoxFlat.new()
	sb.bg_color = Color(0.07, 0.065, 0.06, 0.95)
	sb.border_color = Color(0.95, 0.78, 0.5, 0.35)
	sb.set_border_width_all(1)
	sb.set_content_margin_all(18)
	panel.add_theme_stylebox_override("panel", sb)
	_root.add_child(panel)
	var v: VBoxContainer = VBoxContainer.new()
	v.add_theme_constant_override("separation", 10)
	panel.add_child(v)
	var head: HBoxContainer = HBoxContainer.new()
	v.add_child(head)
	var title: Label = Label.new()
	title.text = "Стойка тира"
	title.add_theme_font_size_override("font_size", 26)
	title.add_theme_color_override("font_color", Color(1.0, 0.86, 0.6))
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(title)
	var close: Button = Button.new()
	close.text = "Закрыть (Esc)"
	close.focus_mode = Control.FOCUS_NONE
	close.pressed.connect(close_ui)
	head.add_child(close)
	var note: Label = Label.new()
	note.text = "Любой ствол игры — только в этом зале, патроны без счёта. Своё снаряжение и рюкзак тир не трогает. Вышел из зала — ствол остаётся на стойке."
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	note.add_theme_color_override("font_color", Color(0.78, 0.74, 0.66))
	v.add_child(note)
	var hand: HBoxContainer = HBoxContainer.new()
	hand.add_theme_constant_override("separation", 12)
	v.add_child(hand)
	_hand_label = Label.new()
	_hand_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hand.add_child(_hand_label)
	_return_button = Button.new()
	_return_button.text = "Сдать ствол — взять своё"
	_return_button.focus_mode = Control.FOCUS_NONE
	_return_button.pressed.connect(_return_weapon)
	hand.add_child(_return_button)
	_own_box = HBoxContainer.new()
	_own_box.add_theme_constant_override("separation", 10)
	v.add_child(_own_box)
	var scroll: ScrollContainer = ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	v.add_child(scroll)
	_list = VBoxContainer.new()
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_list.add_theme_constant_override("separation", 6)
	scroll.add_child(_list)
	_fill()


func is_open() -> bool:
	return _root.visible


func open_for(pl: Player) -> void:
	_player = pl
	_refresh_hand()
	_fill_own()
	_root.visible = true
	_opened_frame = Engine.get_process_frames()
	Audio.play_ui("stash")


func close_ui() -> void:
	_root.visible = false
	Audio.play_ui("bag_close")


func _process(_delta: float) -> void:
	if not _root.visible:
		return
	if Engine.get_process_frames() != _opened_frame and (Input.is_action_just_pressed("pause") or Input.is_action_just_pressed("inventory")):
		close_ui()


func _refresh_hand() -> void:
	var active: bool = _player != null and _player.in_range_mode()
	_return_button.visible = active
	if active:
		_hand_label.text = "В руках со стойки: " + ItemDb.item_name(String(_player.range_weapon.get("id", "")))
	else:
		_hand_label.text = "В руках — своё снаряжение."


## Строки окна: класс → стволы → сборки. Сборки одного ствола с одинаковым обвесом — одна кнопка.
func _fill() -> void:
	var by_weapon: Dictionary = {}
	for pid: Variant in WeaponDb.presets():
		var p: Dictionary = WeaponDb.preset(String(pid))
		var wid: String = String(p.get("weapon", ""))
		if not WeaponDb.is_weapon(wid):
			continue
		var sig: String = JSON.stringify(p.get("mods", {}), "", true)
		var known: Array = by_weapon.get(wid, [])
		if known.any(func(x: Array) -> bool: return String(x[1]) == sig):
			continue
		known.append([String(pid), sig])
		by_weapon[wid] = known
	for group: Array in GROUPS:
		var ids: Array[String] = []
		for wid: String in WeaponDb.weapon_ids():
			if String(WeaponDb.weapon(wid).get("class", "")) in (group[1] as Array):
				ids.append(wid)
		if ids.is_empty():
			continue
		var heading: Label = Label.new()
		heading.text = String(group[0])
		heading.add_theme_font_size_override("font_size", 20)
		heading.add_theme_color_override("font_color", Color(0.95, 0.78, 0.5))
		_list.add_child(heading)
		for wid: String in ids:
			var row: HBoxContainer = HBoxContainer.new()
			row.add_theme_constant_override("separation", 8)
			_list.add_child(row)
			var name_label: Label = Label.new()
			name_label.text = ItemDb.item_name(wid)
			name_label.custom_minimum_size = Vector2(300, 0)
			row.add_child(name_label)
			var variants: Array = by_weapon.get(wid, [])
			if variants.is_empty():
				row.add_child(_variant_button("штатный", wid, ""))
			for entry: Array in variants:
				row.add_child(_variant_button(_variant_name(String(entry[0])), wid, String(entry[0])))


## Пристрелка своего оружия: копия надетого ствола на зал (патроны не тратятся); щелчки барабанчиков
## (стрелки в прицеле) сразу записываются в свой ствол.
func _fill_own() -> void:
	for old: Node in _own_box.get_children():
		old.queue_free()
	if _player == null or _player.inventory == null:
		return
	var any: bool = false
	for slot: String in ItemDb.WEAPON_SLOTS:
		var own: Dictionary = _player.inventory.equipment.get(slot, {})
		if own.is_empty() or not WeaponDb.is_weapon(String(own.get("id", ""))):
			continue
		if not any:
			var note: Label = Label.new()
			note.text = "Пристрелять своё (стрелки в прицеле — щелчки, смотри по листу):"
			note.add_theme_color_override("font_color", Color(0.78, 0.74, 0.66))
			_own_box.add_child(note)
			any = true
		var b: Button = Button.new()
		b.text = "%s: %s" % [Inventory.SLOT_NAMES[slot], ItemDb.item_name(String(own.id))]
		b.focus_mode = Control.FOCUS_NONE
		b.pressed.connect(_take_own.bind(slot))
		_own_box.add_child(b)


func _take_own(slot: String) -> void:
	if _player == null:
		return
	# состояние своего ствола — сначала в профиль (сдаёт текущий ствол зала, если он в руках)
	if _player.in_range_mode():
		_player.clear_range_weapon()
	_player.flush_weapon_state()
	var own: Dictionary = (_player.inventory.equipment.get(slot, {}) as Dictionary).duplicate(true)
	if own.is_empty():
		return
	# на зал — с полным магазином: патроны тир не считает
	if own.get("mag") is Dictionary:
		if String((own.mag as Dictionary).get("id", "")) == "" and not WeaponDb.weapon(String(own.id)).has("internal_mag"):
			(own.mag as Dictionary)["id"] = WeaponDb.default_mag(String(own.id))
		(own.mag as Dictionary).erase("mix")
		(own.mag as Dictionary)["rounds"] = WeaponDb.capacity(own)
	_player.set_range_weapon(own, slot)
	close_ui()


func _variant_button(text: String, wid: String, preset_id: String) -> Button:
	var b: Button = Button.new()
	b.text = text
	b.focus_mode = Control.FOCUS_NONE
	b.pressed.connect(_take.bind(wid, preset_id))
	return b


## Подпись сборки по её обвесу: прицел, глушитель или ДТК.
func _variant_name(preset_id: String) -> String:
	var mods: Dictionary = WeaponDb.preset(preset_id).get("mods", {})
	if mods.is_empty():
		return "штатный"
	var parts: Array[String] = []
	if mods.has("optic_primary"):
		var optic: Dictionary = ItemDb.item(String(mods.optic_primary))
		parts.append(String(optic.get("short", optic.get("name", "прицел"))))
	if mods.has("muzzle"):
		parts.append("глушитель" if String(mods.muzzle).contains("supp") else "ДТК")
	if parts.is_empty():
		parts.append("тактический")
	return " + ".join(parts)


func _take(wid: String, preset_id: String) -> void:
	if _player == null:
		return
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = hash(wid + preset_id)
	var entry: Dictionary = WeaponDb.make_weapon(preset_id, rng, [100, 100]) if preset_id != "" else WeaponDb.bare_weapon(wid, rng, [100, 100])
	if entry.is_empty():
		return
	_player.set_range_weapon(entry)
	close_ui()


func _return_weapon() -> void:
	if _player:
		_player.clear_range_weapon()
	_refresh_hand()
	close_ui()
