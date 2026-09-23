class_name HideoutUI
extends CanvasLayer
## Окна убежища (всё локально, в Profile):
##  тайник — три колонки: тайник ↔ снаряжение (слоты) ↔ рюкзак (с ним идёшь в рейд);
##  торговец — купить из ассортимента (data/trader.json) / продать из тайника;
##  выход — с чем идёшь, «Соло-рейд» или «Кооп (лобби)»;
##  верстак — обвесы на надетое оружие: витрина ствола, характеристики (сравнение с «голым»),
##  слоты: что стоит (снять) и что из тайника подходит (поставить, с кратким эффектом).
## Esc или Tab — закрыть.

const TRADER_PATH := "res://data/trader.json"

var _kind: int = -1
var _root: Control
var _title: Label
var _cols: HBoxContainer
var _sig: String = ""
var _trader: Dictionary = {}
## Верстак: какое оружие собираем (слот снаряжения) и его витрина.
var _wb_slot: String = "primary"
var _preview: WeaponPreview

const MOD_SLOT_NAMES := {"optic": "Прицел", "muzzle": "Дульное устройство", "grip": "Рукоятка",
	"stock": "Приклад", "mag": "Магазин", "tac": "Фонарь / ЛЦУ", "bipod": "Сошки"}
const FX_NAMES := {"kick": "отдача", "shake": "тряска", "spread": "разброс", "ads_spread": "разброс в прицеле",
	"hip_spread": "разброс от бедра (вкл.)", "noise": "шум", "damage": "урон", "braced_kick": "отдача лёжа/сидя",
	"braced_spread": "разброс лёжа/сидя"}


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
	var sig := "%d|%d|%s|%s|%s|%s" % [_kind, Profile.money, str(Profile.stash), str(Profile.equipment), str(Profile.backpack), _wb_slot]
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
		HideoutStation.Kind.WORKBENCH:
			_build_workbench()


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


# ---------------------------------------------------------------- верстак

func _build_workbench() -> void:
	_title.text = "Верстак — обвесы"
	if not Profile.equipment.has(_wb_slot):
		_wb_slot = "secondary" if Profile.equipment.has("secondary") else "primary"
	var left := VBoxContainer.new()
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.add_theme_constant_override("separation", 8)
	_cols.add_child(left)
	var tabs := HBoxContainer.new()
	left.add_child(tabs)
	for ws in ["primary", "secondary"]:
		var e: Dictionary = Profile.equipment.get(ws, {})
		var b := _button("%s: %s" % [Inventory.SLOT_NAMES[ws], ItemDb.item_name(String(e.id)) if not e.is_empty() else "—"], func() -> void: _wb_slot = ws)
		b.disabled = e.is_empty()
		b.toggle_mode = true
		b.button_pressed = ws == _wb_slot
		tabs.add_child(b)
	var weapon: Dictionary = Profile.equipment.get(_wb_slot, {})
	if weapon.is_empty():
		left.add_child(_text("Надень оружие в тайнике — обвесы ставятся на надетое.", Color(1.0, 0.7, 0.5)))
		return
	var wid := String(ItemDb.equip(String(weapon.id)).weapon)
	var mods := Profile.weapon_mods(_wb_slot)
	# витрина живёт между перестройками окна — пересобирается только модель
	if _preview == null or not is_instance_valid(_preview):
		_preview = WeaponPreview.new()
	if _preview.get_parent():
		_preview.get_parent().remove_child(_preview)
	left.add_child(_preview)
	_preview.show_weapon(wid, mods)
	_stats(left, WeaponStats.compute(wid, mods), WeaponStats.compute(wid, {}))
	# слоты обвесов
	var right := _column("Слоты", 1.0)
	for slot in ItemDb.equip(String(weapon.id)).get("slots", []):
		var sl := String(slot)
		right.add_child(_text(String(MOD_SLOT_NAMES.get(sl, sl)), Color(0.95, 0.82, 0.6)))
		if mods.has(sl):
			var row := HBoxContainer.new()
			var l := _text("  " + ItemDb.item_name(String(mods[sl])), Color(0.92, 0.9, 0.85))
			l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			row.add_child(l)
			row.add_child(_button("Снять", func() -> void: Profile.remove_mod(_wb_slot, sl)))
			right.add_child(row)
		var any := false
		# подходящее — и из тайника, и из рюкзака (подписано, откуда)
		for from_bp in [false, true]:
			var src: Array = Profile.backpack if from_bp else Profile.stash
			for i in range(src.size()):
				var id := String(src[i].id)
				if not ItemDb.mod_fits(id, String(weapon.id)) or String(ItemDb.mod_spec(id).slot) != sl:
					continue
				any = true
				var idx := i
				var bp: bool = from_bp
				var row := HBoxContainer.new()
				var l := _text("  + %s  —  %s" % [ItemDb.item_name(id), _fx_text(ItemDb.mod_spec(id))], Color(0.7, 0.8, 0.72))
				l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
				l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
				row.add_child(l)
				row.add_child(_text("рюкзак" if bp else "тайник", Color(0.55, 0.6, 0.65)))
				row.add_child(_button("Поставить", func() -> void: Profile.install_mod(_wb_slot, idx, bp)))
				right.add_child(row)
		if not mods.has(sl) and not any:
			right.add_child(_text("  пусто — подходящего в тайнике и рюкзаке нет", Color(0.5, 0.5, 0.5)))


## Шкалы характеристик: значение, полоса 0–100 и разница с оружием без обвесов (зелёным — лучше).
func _stats(parent: Container, s: Dictionary, base: Dictionary) -> void:
	var rows := WeaponStats.rows(s)
	var base_rows := WeaponStats.rows(base)
	for i in range(rows.size()):
		var r: Array = rows[i]
		var b: Array = base_rows[i]
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 10)
		var name := _text(String(r[0]), Color(0.8, 0.8, 0.78))
		name.custom_minimum_size.x = 190
		row.add_child(name)
		var bar := Control.new()
		bar.custom_minimum_size = Vector2(220, 12)
		bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		var bg := ColorRect.new()
		bg.color = Color(1, 1, 1, 0.08)
		bg.size = Vector2(220, 12)
		bar.add_child(bg)
		var fill := ColorRect.new()
		fill.color = Color(0.95, 0.8, 0.5, 0.85)
		fill.size = Vector2(220.0 * clampf(float(r[2]) / 100.0, 0.0, 1.0), 12)
		bar.add_child(fill)
		row.add_child(bar)
		var val := _text(String(r[4]) % float(r[1]), Color(0.92, 0.9, 0.85))
		val.custom_minimum_size.x = 150
		row.add_child(val)
		var d := float(r[1]) - float(b[1])
		if absf(d) > 0.05:
			var better := (d > 0.0) == bool(r[3])
			row.add_child(_text("%+.0f" % d if absf(d) >= 1.0 else "%+.1f" % d, Color(0.55, 0.9, 0.5) if better else Color(1.0, 0.5, 0.4)))
		parent.add_child(row)


## «отдача −20%, эргономика +6, магазин +15»
func _fx_text(ms: Dictionary) -> String:
	var parts: Array[String] = []
	var fx: Dictionary = ms.get("fx", {})
	for k in fx:
		var v: Variant = fx[k]
		if k == "ergo":
			parts.append("эргономика %+d" % int(v))
		elif k == "mag":
			parts.append("магазин +%d" % int(v))
		elif k == "zoom":
			parts.append("кратность %d×" % int(v))
		elif k == "suppressed":
			parts.append("без вспышки")
		elif k == "db" or k == "scoped":
			continue
		elif FX_NAMES.has(k):
			parts.append("%s %+d%%" % [FX_NAMES[k], int(round((float(v) - 1.0) * 100.0))])
	return ", ".join(parts)


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
