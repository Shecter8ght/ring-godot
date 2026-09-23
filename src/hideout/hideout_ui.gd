class_name HideoutUI
extends CanvasLayer
## Окна убежища (всё локально, в Profile):
##  тайник — три колонки: тайник ↔ снаряжение (слоты) ↔ рюкзак (с ним идёшь в рейд);
##  торговец — купить из ассортимента (data/trader.json) / продать из тайника;
##  выход — с чем идёшь, «Соло-рейд» или «Кооп (лобби)».
## Esc или Tab — закрыть.

const TRADER_PATH := "res://data/trader.json"

var _kind: int = -1
var _root: Control
var _title: Label
var _cols: HBoxContainer
var _sig: String = ""
var _trader: Dictionary = {}


func _ready() -> void:
	layer = 20
	_trader = JSON.parse_string(FileAccess.get_file_as_string(TRADER_PATH)) as Dictionary
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.visible = false
	add_child(_root)
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.45)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(dim)
	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_FULL_RECT)
	panel.offset_left = 60
	panel.offset_right = -60
	panel.offset_top = 60
	panel.offset_bottom = -60
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.07, 0.065, 0.06, 0.94)
	sb.border_color = Color(0.95, 0.78, 0.5, 0.35)
	sb.set_border_width_all(1)
	sb.set_content_margin_all(18)
	panel.add_theme_stylebox_override("panel", sb)
	_root.add_child(panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 12)
	panel.add_child(v)
	var head := HBoxContainer.new()
	v.add_child(head)
	_title = Label.new()
	_title.add_theme_font_size_override("font_size", 26)
	_title.add_theme_color_override("font_color", Color(1.0, 0.86, 0.6))
	_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(_title)
	var close := Button.new()
	close.text = "Закрыть (Esc)"
	close.focus_mode = Control.FOCUS_NONE
	close.pressed.connect(close_ui)
	head.add_child(close)
	_cols = HBoxContainer.new()
	_cols.add_theme_constant_override("separation", 16)
	_cols.size_flags_vertical = Control.SIZE_EXPAND_FILL
	v.add_child(_cols)


func is_open() -> bool:
	return _root.visible


func open(kind: int) -> void:
	_kind = kind
	_sig = ""
	_root.visible = true


func close_ui() -> void:
	_root.visible = false


func _process(_delta: float) -> void:
	if not _root.visible:
		return
	if Input.is_action_just_pressed("ui_cancel") or Input.is_action_just_pressed("inventory"):
		close_ui()
		return
	var sig := "%d|%d|%s|%s|%s" % [_kind, Profile.money, str(Profile.stash), str(Profile.equipment), str(Profile.backpack)]
	if sig == _sig:
		return
	_sig = sig
	for c in _cols.get_children():
		c.queue_free()
	match _kind:
		HideoutStation.Kind.STASH:
			_build_stash()
		HideoutStation.Kind.TRADER:
			_build_trader()
		HideoutStation.Kind.EXIT:
			_build_exit()


# ---------------------------------------------------------------- тайник

func _build_stash() -> void:
	_title.text = "Тайник и снаряжение   ·   %s ₽" % InventoryUI.money(Profile.money)
	var stash := _column("Тайник   %d / %d ячеек" % [Profile.stash_cells(), Balance.STASH_CELLS], 1.2)
	for i in range(Profile.stash.size()):
		var e: Dictionary = Profile.stash[i]
		var idx := i
		var row := _row(e, ItemDb.entry_value(e))
		if not ItemDb.equip(String(e.id)).is_empty():
			row.add_child(_button("Надеть", func() -> void: Profile.equip_from_stash(idx)))
		row.add_child(_button("В рюкзак", func() -> void: Profile.stash_to_backpack(idx, int(e.n))))
		stash.add_child(row)
	if Profile.stash.is_empty():
		stash.add_child(_text("пусто", Color(0.6, 0.6, 0.6)))
	var gear := _column("Снаряжение", 0.9)
	for slot in Inventory.SLOTS:
		var s := String(slot)
		gear.add_child(_text(String(Inventory.SLOT_NAMES[s]), Color(0.7, 0.72, 0.75)))
		if Profile.equipment.has(s):
			var e: Dictionary = Profile.equipment[s]
			var row := _row(e, ItemDb.entry_value(e))
			row.add_child(_button("Снять", func() -> void: Profile.unequip(s)))
			gear.add_child(row)
		else:
			gear.add_child(_text("—", Color(0.5, 0.5, 0.5)))
	var bp := _column("Рюкзак   %d / %d ячеек   (с ним — в рейд)" % [Profile.backpack_cells(), Balance.BACKPACK_CELLS], 1.0)
	for i in range(Profile.backpack.size()):
		var e: Dictionary = Profile.backpack[i]
		var idx := i
		var row := _row(e, ItemDb.entry_value(e))
		row.add_child(_button("В тайник", func() -> void: Profile.backpack_to_stash(idx, int(e.n))))
		bp.add_child(row)
	if Profile.backpack.is_empty():
		bp.add_child(_text("пусто — положи патроны и медицину", Color(0.6, 0.6, 0.6)))


# ---------------------------------------------------------------- торговец

func _build_trader() -> void:
	_title.text = "%s   ·   у тебя %s ₽" % [String(_trader.get("name", "Торговец")), InventoryUI.money(Profile.money)]
	var shop := _column("Купить", 1.0)
	for id in _trader.get("stock", []):
		var sid := String(id)
		# патроны — пачкой (стопка), остальное — поштучно
		var n := ItemDb.stack(sid) if ItemDb.item(sid).cat == "ammo" else 1
		var price := Profile.buy_price(sid) * n
		var e := ItemDb.make(sid, n)
		var row := _row(e, price)
		var b := _button("Купить", func() -> void: Profile.buy(sid, n))
		b.disabled = price > Profile.money
		row.add_child(b)
		shop.add_child(row)
	var sell := _column("Продать из тайника", 1.0)
	for i in range(Profile.stash.size()):
		var e: Dictionary = Profile.stash[i]
		var idx := i
		var row := _row(e, Profile.sell_price(e))
		row.add_child(_button("Продать", func() -> void: Profile.sell(idx, int(e.n))))
		sell.add_child(row)
	if Profile.stash.is_empty():
		sell.add_child(_text("тайник пуст", Color(0.6, 0.6, 0.6)))


# ---------------------------------------------------------------- выход

func _build_exit() -> void:
	_title.text = "Выход в рейд"
	var col := _column("С собой", 1.0)
	for slot in Inventory.SLOTS:
		var e: Dictionary = Profile.equipment.get(slot, {})
		col.add_child(_text("%s:  %s" % [Inventory.SLOT_NAMES[slot], ItemDb.label(e) if not e.is_empty() else "—"], Color(0.85, 0.85, 0.82)))
	col.add_child(_text("Рюкзак: %d / %d ячеек, на %s ₽" % [Profile.backpack_cells(), Balance.BACKPACK_CELLS, InventoryUI.money(ItemDb.value_of(Profile.backpack))], Color(0.85, 0.85, 0.82)))
	if Profile.equipped_weapon() == "":
		col.add_child(_text("Без оружия — надень его в тайнике.", Color(1.0, 0.55, 0.4)))
	col.add_child(_text("Всё, что с собой, в рейде можно потерять.", Color(0.9, 0.75, 0.5)))
	var go := _column("Куда", 0.7)
	go.add_child(_button("Соло-рейд", func() -> void:
		Profile.pending_raid = true
		get_tree().change_scene_to_file(Balance.RAID_SCENE)))
	go.add_child(_button("Кооп — лобби (хост / по IP)", func() -> void:
		Profile.from_hideout = true
		get_tree().change_scene_to_file("res://scenes/net/lobby.tscn")))


# ---------------------------------------------------------------- вёрстка

## Колонка с заголовком и прокруткой; возвращает список, куда класть строки.
func _column(title: String, ratio: float) -> VBoxContainer:
	var box := VBoxContainer.new()
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.size_flags_stretch_ratio = ratio
	box.add_theme_constant_override("separation", 6)
	_cols.add_child(box)
	var t := Label.new()
	t.text = title
	t.add_theme_font_size_override("font_size", 18)
	t.add_theme_color_override("font_color", Color(0.95, 0.82, 0.6))
	box.add_child(t)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	box.add_child(scroll)
	var list := VBoxContainer.new()
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.add_theme_constant_override("separation", 4)
	scroll.add_child(list)
	return list


func _row(e: Dictionary, price: int) -> HBoxContainer:
	var row := HBoxContainer.new()
	var n := int(e.n)
	var l := _text(ItemDb.label(e) + ("  ×%d" % n if n > 1 else ""), Color(0.92, 0.9, 0.85))
	l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	l.clip_text = true
	row.add_child(l)
	var v := _text("%s ₽" % InventoryUI.money(price), Color(0.7, 0.85, 0.65))
	v.custom_minimum_size.x = 96
	v.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	row.add_child(v)
	return row


func _text(t: String, color: Color) -> Label:
	var l := Label.new()
	l.text = t
	l.add_theme_font_size_override("font_size", 16)
	l.add_theme_color_override("font_color", color)
	return l


func _button(t: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = t
	b.focus_mode = Control.FOCUS_NONE
	b.add_theme_font_size_override("font_size", 14)
	b.pressed.connect(cb)
	return b
