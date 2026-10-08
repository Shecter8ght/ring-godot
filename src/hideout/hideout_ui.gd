class_name HideoutUI
extends CanvasLayer
## Окна убежища (всё локально, в Profile):
##  тайник — три колонки: тайник ↔ снаряжение (слоты) ↔ рюкзак (с ним идёшь в рейд);
##  торговец — купить из ассортимента (data/trader.json) / продать из тайника;
##  выход — с чем идёшь, этаж и маршрут (открыть у Михалыча за доверие и деньги, см. Floors),
##  «Соло-рейд» или «Кооп (лобби)»;
##  верстак — обвесы на надетое оружие: витрина ствола, характеристики (сравнение с «голым»),
##  слоты: что стоит (снять) и что из тайника подходит (поставить, с кратким эффектом);
##  какие слоты доступны — по уровню верстака (модуль убежища);
##  модули убежища — уровни, что нужно на следующий (деньги, детали, доверие), «Построить».
##  У торговца ещё и задания: взять, прогресс, сдать (деньги и доверие).
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
## Торговец: вкладка, количество расходников к покупке, оружие на схеме обвеса (где и uid).
var _trader_tab: String = "buy"
## Куда класть купленное: рюкзак (по умолчанию — собираешься в рейд) или тайник (стеллаж).
var _buy_to: String = "backpack"
## Торговец: к какому стволу подсвечивать патроны, магазины, обвес ("" — ни к какому) и
## показывать ли только подходящее.
var _focus: String = ""
var _focus_only: bool = false
var _qty: Dictionary = {}
## Поштучная операция в тайнике (снарядить магазин, разрядить, вынуть плиты) — MagOps над профилем.
var _op: MagOps
var _stash_views: Array[GridView] = []
var _stash_slots: Array[SlotView] = []
var _stash_heading: Label
var _backpack_heading: Label
## Торговец: раздел ассортимента ("all" — всё, иначе ключ CAT_TABS).
var _cat_tab: String = "all"
## Кадр открытия: Tab, открывший окно, его же не закрывает.
var _opened_frame: int = -1
var _toast: Label
var _toast_t: float = 0.0
var _tb_where: String = "equip:primary"
var _tb_uid: String = ""

## Разделы ассортимента торговца: ключ, название, категории предметов ("misc" — всё прочее).
const CAT_TABS := [["all", "Всё", []], ["weapon", "Оружие", ["weapon"]], ["mag", "Магазины", ["mag"]], ["ammo", "Патроны", ["ammo"]],
	["mod", "Обвес", ["mod"]], ["armor", "Броня и рюкзаки", ["armor", "plate", "backpack"]], ["med", "Медицина", ["med", "food"]],
	["throw", "Гранаты и свет", ["throw"]], ["misc", "Разное", []]]

const MOD_SLOT_NAMES := {"optic": "Прицел", "muzzle": "Дульное устройство", "grip": "Рукоятка",
	"stock": "Приклад", "mag": "Магазин", "tac": "Фонарь / ЛЦУ", "bipod": "Сошки"}
const FX_NAMES := {"kick": "отдача", "shake": "тряска", "spread": "разброс", "ads_spread": "разброс в прицеле",
	"hip_spread": "разброс от бедра (вкл.)", "noise": "шум", "damage": "урон", "braced_kick": "отдача лёжа/сидя",
	"braced_spread": "разброс лёжа/сидя"}


func _ready() -> void:
	layer = 20
	# окно само закрывается по Esc — меню паузы тогда не открывается
	add_to_group("esc_windows")
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
	# сообщение внизу окна: не влезло, не хватает денег…
	_toast = Label.new()
	_toast.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_toast.offset_left = -500
	_toast.offset_right = 500
	_toast.offset_top = -120
	_toast.offset_bottom = -80
	_toast.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_toast.add_theme_font_size_override("font_size", 22)
	_toast.add_theme_color_override("font_color", Color(1.0, 0.55, 0.42))
	_toast.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	_toast.add_theme_constant_override("outline_size", 8)
	_toast.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_toast.visible = false
	_root.add_child(_toast)


## Сообщение внизу окна на пару секунд.
func toast(text: String) -> void:
	Audio.play_ui("ui_deny")
	_toast.text = text
	_toast_t = 3.0
	_toast.visible = true
	_toast.modulate.a = 1.0


func is_open() -> bool:
	return _root.visible


func open(kind: int) -> void:
	_kind = kind
	_sig = ""
	_root.visible = true
	match kind:
		HideoutStation.Kind.STASH:
			Audio.play_ui("stash")
		HideoutStation.Kind.WORKBENCH:
			Audio.play_ui("workbench")
		HideoutStation.Kind.EXIT:
			Audio.play_ui("hatch")
	_opened_frame = Engine.get_process_frames()
	# Сергею есть что сказать — сразу на задания
	if kind == HideoutStation.Kind.TRADER and not Quests.talk_options("trader").is_empty():
		_trader_tab = "tasks"


func close_ui() -> void:
	_root.visible = false
	Audio.play_ui("bag_close")
	_cancel_op()
	# меню правой кнопки, описание, вопросы — отдельные окошки: сами с окном не прячутся
	for n in find_children("*", "", true, false):
		if n is Window:
			(n as Window).hide()
		elif n is ItemInfo:
			(n as ItemInfo)._close()


func _process(delta: float) -> void:
	if not _root.visible:
		return
	_tick_op(delta)
	if _toast_t > 0.0:
		_toast_t -= delta
		_toast.modulate.a = clampf(_toast_t / 0.6, 0.0, 1.0)
		_toast.visible = _toast_t > 0.0
	# Esc закрыл описание предмета — окно остаётся; Tab, открывший окно, его не закрывает
	var just_opened := Engine.get_process_frames() == _opened_frame
	if (Input.is_action_just_pressed("ui_cancel") or Input.is_action_just_pressed("inventory")) and not ItemInfo.blocking() and not just_opened:
		close_ui()
		return
	var sig := "%d|%d|%s|%s|%s|%s|%s|%s|%d|%s|%s|%s" % [_kind, Profile.money, str(Profile.stash), str(Profile.equipment), str(Profile.backpack), _wb_slot,
		Profile.floor, str(Profile.floors_open), Profile.trust, str(Profile.pocket), str(Profile.modules), str(Profile.missions_active) + str(Profile.next_conditions)]
	sig += "|%s|%s|%s|%s|%s|%s|%s|%s" % [_trader_tab, str(_qty), _tb_where, _tb_uid, _buy_to, _focus, _focus_only, _cat_tab]
	sig += "|" + str(Profile.loadout_templates)
	# собрание: кто в сети и где — окно выхода обновляется
	sig += "|%s|%s|%s" % [Net.is_networked(), str(Net.player_names), str(Net.peer_scene)]
	if sig == _sig:
		return
	_sig = sig
	if _kind == HideoutStation.Kind.STASH and _refresh_stash_content():
		return
	# прокрутка колонок — вернуть после перестройки (купил с конца списка — список не прыгает)
	var scrolls := {}
	for c in _cols.get_children():
		for sc in c.find_children("*", "ScrollContainer", true, false):
			scrolls[_scroll_key(sc as ScrollContainer)] = (sc as ScrollContainer).scroll_vertical
	_stash_views.clear()
	_stash_slots.clear()
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
		HideoutStation.Kind.UPGRADES:
			_build_upgrades()
	# строки-абзацы в колонках переносятся по словам: длинная строка не раздвигает окно за экран
	for l in _cols.find_children("*", "Label", true, false):
		if l.get_parent() is VBoxContainer and (l as Label).autowrap_mode == TextServer.AUTOWRAP_OFF:
			(l as Label).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	for b in _cols.find_children("*", "Button", true, false):
		if b.get_parent() is VBoxContainer and not b.get_parent().get_parent() is MountBoard:
			(b as Button).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_restore_scroll(scrolls)


## Ключ колонки для прокрутки: заголовок её колонки (он у колонки неизменен).
func _scroll_key(sc: ScrollContainer) -> String:
	var box := sc.get_parent()
	if box and box.get_child_count() > 0 and box.get_child(0) is Label:
		return (box.get_child(0) as Label).text.get_slice("   ", 0)
	return str(sc.get_index())


func _restore_scroll(scrolls: Dictionary) -> void:
	if scrolls.is_empty():
		return
	# прокрутка встанет, когда содержимое разложится по высоте
	for i in range(2):
		await get_tree().process_frame
	for sc in _cols.find_children("*", "ScrollContainer", true, false):
		var k := _scroll_key(sc as ScrollContainer)
		if scrolls.has(k) and not (sc as Node).is_queued_for_deletion():
			(sc as ScrollContainer).scroll_vertical = int(scrolls[k])


# ---------------------------------------------------------------- тайник

## Снаряжение магазина меняет числа, но не дерево окна: мышь продолжает держать живую сетку.
func _refresh_stash_content() -> bool:
	var expected: int = 2 if Profile.pocket_grid() == Vector2i.ZERO else 3
	if _stash_views.size() != expected or _stash_slots.size() != Inventory.SLOTS.size():
		return false
	for index: int in range(_stash_views.size()):
		if not is_instance_valid(_stash_views[index]):
			return false
		var view: GridView = _stash_views[index]
		if view.is_queued_for_deletion() or view.grid != Profile.grid_of(view.role):
			return false
	for index: int in range(_stash_slots.size()):
		if not is_instance_valid(_stash_slots[index]):
			return false
	for view: GridView in _stash_views:
		view.set_items(Profile.list_of(view.role))
	for view: SlotView in _stash_slots:
		view.set_entry(Profile.equipment.get(view.slot, {}))
	var sg: Vector2i = Profile.stash_grid()
	_title.text = "Тайник и снаряжение   ·   %s ₽" % InventoryUI.money(Profile.money)
	_stash_heading.text = "Тайник   %d / %d ячеек" % [Profile.stash_cells(), sg.x * sg.y]
	_backpack_heading.text = ("Рюкзак" if Profile.equipment.has("backpack") else "Карманы (рюкзака нет)") + "   %d / %d ячеек   (с ним — в рейд)" % [Profile.backpack_cells(), Profile.backpack_capacity()]
	return true


func _build_stash() -> void:
	_title.text = "Тайник и снаряжение   ·   %s ₽" % InventoryUI.money(Profile.money)
	var sg := Profile.stash_grid()
	var stash_col := _column("Тайник   %d / %d ячеек" % [Profile.stash_cells(), sg.x * sg.y], 1.25)
	_stash_heading = stash_col.get_parent().get_parent().get_child(0) as Label
	stash_col.add_child(_sort_button("stash"))
	var stash := GridView.new(sg, "stash")
	stash.set_items(Profile.stash)
	stash_col.add_child(stash)
	var gear := _column("Снаряжение", 0.8)
	for slot in Inventory.SLOTS:
		var s := String(slot)
		var sv := SlotView.new(s)
		_stash_slots.append(sv)
		sv.set_entry(Profile.equipment.get(s, {}))
		sv.equip_from.connect(func(src: GridView, idx: int) -> void: Profile.equip_from(src.role, idx, s))
		sv.unequip_requested.connect(func() -> void: Profile.unequip(s))
		# на оружие — обвес или магазин, в плитоносец — плиту
		sv.mod_from.connect(func(src: GridView, idx: int) -> void:
			if not src.role in ["stash", "backpack"]:
				return
			var it: Dictionary = Profile.list_of(src.role)[idx]
			if not WeaponDb.attachment(String(it.id)).is_empty():
				Profile.install_mod(s, idx, src.role == "backpack")
			else:
				Profile.fit_part("equip:" + s, -1, src.role, idx, ""))
		sv.context.connect(func(at: Vector2) -> void: _parts_menu("equip:" + s, -1, Profile.equipment.get(s, {}), at))
		gear.add_child(sv)
	gear.add_child(_text("Тащи мышью · R — повернуть на лету\nДвойной клик — надеть / перенести\nCtrl+клик — в другую сетку\nПравая кнопка — действия", Color(0.6, 0.62, 0.6)))
	_templates_block(gear, true)
	var bp_col := _column(("Рюкзак" if Profile.equipment.has("backpack") else "Карманы (рюкзака нет)") + "   %d / %d ячеек   (с ним — в рейд)" % [Profile.backpack_cells(), Profile.backpack_capacity()], 0.95)
	_backpack_heading = bp_col.get_parent().get_parent().get_child(0) as Label
	bp_col.add_child(_sort_button("backpack"))
	var bp := GridView.new(Profile.grid_of("backpack"), "backpack")
	bp.set_items(Profile.backpack)
	bp_col.add_child(bp)
	var views: Array[GridView] = [stash, bp]
	# защищённый карман — если модуль построен: не теряется при смерти
	var pg := Profile.pocket_grid()
	if pg != Vector2i.ZERO:
		bp_col.add_child(_text("Защищённый карман %d×%d — не теряется при смерти" % [pg.x, pg.y], Color(0.95, 0.82, 0.6)))
		var pk := GridView.new(pg, "pocket")
		pk.set_items(Profile.pocket)
		bp_col.add_child(pk)
		views.append(pk)
	else:
		bp_col.add_child(_text("Защищённого кармана нет — строится в «Модулях убежища».", Color(0.55, 0.57, 0.55)))
	_stash_views.assign(views)
	for v in views:
		var name := v.role
		v.dropped.connect(func(src: GridView, idx: int, x: int, y: int, r: bool) -> void:
			if src == v:
				Profile.move_in(name, idx, x, y, r)
			elif not Profile.transfer(src.role, idx, name, x, y, r):
				toast("Сюда не влезает"))
		v.slot_dropped.connect(func(slot: String, x: int, y: int, r: bool) -> void: Profile.unequip_to(slot, name, x, y, r))
		v.quick_move.connect(func(idx: int) -> void: _quick(name, idx))
		v.activated.connect(func(idx: int) -> void:
			var list := Profile.list_of(name)
			if idx < list.size() and not ItemDb.equip(String(list[idx].id)).is_empty():
				Profile.equip_from(name, idx)
			else:
				_quick(name, idx))
		v.context.connect(func(idx: int, at: Vector2) -> void: _stash_menu(name, idx, at))
		# патроны на магазин — снарядить им (поштучно), плиту на жилет — вставить
		v.dropped_on.connect(func(src: GridView, si: int, di: int) -> void:
			if not src.role in ["stash", "backpack", "pocket"]:
				return
			var from := Profile.list_of(src.role)
			if si >= from.size():
				return
			if not WeaponDb.ammo(String(from[si].id)).is_empty():
				_start_op("load", name, di, String(from[si].id), src.role)
			elif not Profile.fit_part(name, di, src.role, si):
				toast("Не встаёт"))


## Шаблоны снаряжения: собрать (план — что из тайника, что купить и за сколько), удалить; в тайнике —
## ещё «сохранить надетое и рюкзак как шаблон».
func _templates_block(parent: Control, can_save: bool) -> void:
	parent.add_child(_text("Шаблоны снаряжения", Color(0.95, 0.82, 0.6)))
	for i in range(LoadoutTemplates.all().size()):
		var t: Dictionary = LoadoutTemplates.all()[i]
		var idx := i
		var p := LoadoutTemplates.plan(t)
		var row := HFlowContainer.new()
		row.add_theme_constant_override("h_separation", 6)
		var cost := int(p.cost)
		var label := String(t.name) + ("   ·   всё есть" if cost == 0 and int(p.missing) == 0 else "")
		row.add_child(_text(label, Color(0.9, 0.9, 0.86)))
		var go := _button("Собрать" + ("  (%s ₽)" % InventoryUI.money(cost) if cost > 0 else ""), func() -> void: _confirm_template(t))
		go.disabled = cost > Profile.money
		row.add_child(go)
		if can_save:
			row.add_child(_button("Удалить", func() -> void: LoadoutTemplates.remove(idx)))
		parent.add_child(row)
		if int(p.missing) > 0:
			parent.add_child(_text("   не собрать полностью: %d поз. (нет у Михалыча, доверие, верстак)" % int(p.missing), Color(0.85, 0.55, 0.45)))
	if can_save:
		var save_row := HBoxContainer.new()
		save_row.add_theme_constant_override("separation", 6)
		var name_edit := LineEdit.new()
		name_edit.placeholder_text = "Имя шаблона"
		name_edit.custom_minimum_size.x = 150
		save_row.add_child(name_edit)
		save_row.add_child(_button("Сохранить надетое и рюкзак", func() -> void:
			var t := LoadoutTemplates.capture(name_edit.text)
			toast("Шаблон «%s» сохранён" % String(t.name))))
		parent.add_child(save_row)


## План шаблона — окно: по строкам что откуда, итог; «Собрать» — выполнить.
func _confirm_template(t: Dictionary) -> void:
	var p := LoadoutTemplates.plan(t)
	var lines: Array[String] = []
	for r in p.rows:
		var how := String(r.how)
		var tail := ""
		match how:
			"есть":
				tail = "уже надето"
			"тайник":
				tail = "из тайника"
			"купить":
				tail = "купить — %s ₽" % InventoryUI.money(int(r.price))
			"нет":
				tail = "нет: " + String(r.why)
		lines.append("%s — %s" % [String(r.what), tail])
	lines.append("")
	lines.append("Докупить на %s ₽ (у тебя %s ₽)" % [InventoryUI.money(int(p.cost)), InventoryUI.money(Profile.money)])
	var d := ConfirmationDialog.new()
	d.title = "Собрать: " + String(t.name)
	d.dialog_text = "\n".join(lines)
	d.ok_button_text = "Собрать"
	d.cancel_button_text = "Отмена"
	d.confirmed.connect(func() -> void:
		var fails := LoadoutTemplates.apply(t)
		toast("Собрано" if fails.is_empty() else "Собрано не всё: " + ", ".join(fails)))
	d.visibility_changed.connect(func() -> void:
		if not d.visible:
			d.queue_free())
	_root.add_child(d)
	d.popup_centered()


## «Сортировать» над сеткой: крупное в начало, стопки добраны — место освобождается.
func _sort_button(name: String) -> Button:
	return InventoryUI.sort_button(func() -> void:
		if not Profile.sort_grid(name):
			toast("Не разложить — места впритык"))


## Тайник ↔ рюкзак (Ctrl+клик, двойной клик); не влезло — сказать.
func _quick(name: String, idx: int) -> void:
	if not Profile.quick_move(name, idx):
		toast("Не влезает в %s" % ("тайник" if name != "stash" else "рюкзак"))


## Правая кнопка по предмету: что с ним можно сделать.
func _stash_menu(name: String, idx: int, at: Vector2) -> void:
	var list := Profile.list_of(name)
	if idx >= list.size():
		return
	var id := String(list[idx].id)
	var menu := PopupMenu.new()
	var acts: Array[Callable] = []
	var entry: Dictionary = (list[idx] as Dictionary).duplicate(true)
	menu.add_item("Описание")
	acts.append(func() -> void: ItemInfo.open(self, entry))
	if not ItemDb.equip(id).is_empty():
		menu.add_item("Надеть" if not ItemDb.equip(id).has("weapon") else "Взять (слот оружия)")
		acts.append(func() -> void: Profile.equip_from(name, idx))
	menu.add_item("В рюкзак" if name == "stash" else "В тайник")
	acts.append(func() -> void: _quick(name, idx))
	# оружие, жилет: снять обвес, магазин — в рюкзак (из тайника — в тайник); плиты — по одной
	for p in Gear.parts(list[idx]):
		var part := String(p[1])
		if part.begins_with("plate:"):
			menu.add_item(String(p[0]).replace("Снять", "Вынуть"))
			acts.append(func() -> void: _start_op("plates", name, idx, "", "", part.trim_prefix("plate:")))
		else:
			menu.add_item(String(p[0]))
			acts.append(func() -> void: Profile.strip_part(name, idx, part))
	if list[idx].has("rounds"):
		menu.add_item("Проверить патроны")
		var cap := int(WeaponDb.magazine(id).get("capacity", 0))
		acts.append(func() -> void:
			toast("%s: %s" % [ItemDb.item_name(id), Gear.ammo_estimate(int(entry.get("rounds", 0)), cap, Gear.mag_exact(id))])
			Profile.check_mag(name, idx))
		menu.add_item("Снарядить")
		acts.append(func() -> void: _load_mag(name, idx))
		menu.add_item("Разрядить")
		acts.append(func() -> void: _start_op("unload", name, idx))
	if list[idx].has("plates") and (list[idx].plates as Dictionary).size() > 1:
		menu.add_item("Вынуть все плиты")
		acts.append(func() -> void: _start_op("plates", name, idx))
	if int(list[idx].n) > 1:
		menu.add_item("Разделить стопку пополам")
		acts.append(func() -> void: _split(name, idx))
	menu.add_item("Выбросить…")
	acts.append(func() -> void: _confirm_discard(name, idx, list[idx]))
	menu.id_pressed.connect(func(i: int) -> void: acts[i].call())
	menu.popup_hide.connect(menu.queue_free)
	_root.add_child(menu)
	menu.popup(Rect2i(Vector2i(at), Vector2i.ZERO))


# ---------------------------------------------------------------- поштучно (MagOps)

## Снарядить один магазин (любыми подходящими патронами: сначала из той же сетки, потом рюкзак,
## карман, тайник), разрядить (в ту же сетку, потом в тайник), вынуть плиты — по шагу, с кругом на
## предмете. Новая операция прерывает старую.
func _start_op(kind: String, role: String, idx: int, ammo: String = "", src: String = "", side: String = "") -> void:
	_cancel_op()
	var op := MagOps.make(kind, role, 1,
		func(r: String) -> Array: return Profile.list_of(r),
		func(_r: String, _list: Array) -> void: pass,
		func(r: String) -> Vector2i: return Profile.grid_of(r))
	var have: Array[String] = []
	for r in [role, "backpack", "pocket", "stash"]:
		if not String(r) in have and Profile.grid_of(String(r)) != Vector2i.ZERO:
			have.append(String(r))
	op.all_roles.assign(have)
	if kind == "load":
		op.sources.assign([src] if src != "" else have)
	else:
		op.dests.assign([role, "stash"] if role != "stash" else ["stash", "backpack"])
	op.ammo = ammo
	op.only_side = side
	if not op.start(idx):
		var why := {"full": "Магазин и так полный", "empty": "Нечего вынимать", "no_ammo": "Нет подходящих патронов",
			"no_room": "Некуда класть — освободи место"}
		if why.has(op.reason):
			toast(String(why[op.reason]))
		return
	_op = op


func _tick_op(delta: float) -> void:
	if _op == null:
		return
	if not _op.tick(delta):
		var t := MagOps.reason_text(_op.reason)
		if t != "" and _op.reason != "no_room":
			toast(t)
		elif _op.reason == "no_room":
			toast("Некуда класть — освободи место")
		_op = null
		Profile.save()


func _cancel_op() -> void:
	if _op:
		_op.cancel()
		_op = null
		Profile.save()


## «Снарядить»: нет подходящих патронов — сказать, каких нужно и какие есть.
func _load_mag(name: String, idx: int) -> void:
	var list := Profile.list_of(name)
	if idx < 0 or idx >= list.size():
		return
	var mag: Dictionary = list[idx]
	var mine: Array = Profile.backpack + Profile.pocket + Profile.stash
	if int(mag.rounds) >= MagOps.capacity(mag):
		toast("Магазин и так полный")
		return
	var ammo := MagOps.pick_ammo(mag, mine)
	if ammo == "" or MagOps.count_of(mine, ammo) <= 0:
		toast(MagOps.no_ammo_text(mag, mine))
		return
	_start_op("load", name, idx)


## Правая кнопка по слоту снаряжения: снять в тайник, выбросить, снять обвес / магазин / плиты.
func _parts_menu(where: String, idx: int, e: Dictionary, at: Vector2) -> void:
	if e.is_empty():
		return
	var parts := Gear.parts(e)
	var menu := PopupMenu.new()
	var acts: Array[Callable] = []
	if where.begins_with("equip:"):
		var slot := where.trim_prefix("equip:")
		menu.add_item("Снять в тайник")
		acts.append(func() -> void: Profile.unequip(slot))
		menu.add_item("Выбросить…")
		acts.append(func() -> void: _confirm_discard(where, -1, e))
	for p in parts:
		var part := String(p[1])
		menu.add_item(String(p[0]))
		acts.append(func() -> void: Profile.strip_part(where, idx, part))
	menu.id_pressed.connect(func(i: int) -> void: acts[i].call())
	menu.popup_hide.connect(menu.queue_free)
	_root.add_child(menu)
	menu.popup(Rect2i(Vector2i(at), Vector2i.ZERO))


## Выбросить насовсем — только после «Да».
func _confirm_discard(where: String, idx: int, e: Dictionary) -> void:
	var d := ConfirmationDialog.new()
	d.title = "Выбросить"
	d.dialog_text = "Выбросить насовсем: %s?" % ItemDb.label(e)
	d.ok_button_text = "Выбросить"
	d.cancel_button_text = "Отмена"
	d.confirmed.connect(func() -> void: Profile.discard(where, idx))
	d.visibility_changed.connect(func() -> void:
		if not d.visible:
			d.queue_free())
	_root.add_child(d)
	d.popup_centered()


## Половину стопки — отдельной стопкой в свободное место той же сетки.
func _split(name: String, idx: int) -> void:
	var list := Profile.list_of(name)
	var grid := Profile.grid_of(name)
	var e: Dictionary = list[idx]
	var half := int(e.n) / 2
	var spot := ItemDb.find_spot(ItemDb.occupancy(list, grid), grid, String(e.id))
	if half <= 0 or spot.x < 0:
		return
	var part := e.duplicate(true)
	part.n = half
	part.x = spot.x
	part.y = spot.y
	part.r = spot.z == 1
	e.n = int(e.n) - half
	list.append(part)
	Profile.save()


# ---------------------------------------------------------------- торговец

func _build_trader() -> void:
	_title.text = "%s   ·   у тебя %s ₽   ·   доверие: ступень %d / %d%s" % [String(_trader.get("name", "Торговец")), InventoryUI.money(Profile.money), Profile.trust_step(), int(Balance.TRUST_STEPS.max),
		"   ·   АДМИН: всё у Михалыча" if Settings.all_weapons else ""]
	# вкладки слева: купить, обвес оружия, продать, задания (разговор — отметка)
	var tabs := VBoxContainer.new()
	tabs.custom_minimum_size.x = 170
	tabs.add_theme_constant_override("separation", 6)
	_cols.add_child(tabs)
	var talk := not Quests.talk_options("trader").is_empty()
	for t in [["buy", "Купить"], ["mods", "Обвес оружия"], ["sell", "Продать"], ["tasks", "Задания" + ("  •" if talk else "")]]:
		var key := String(t[0])
		var b := _button(String(t[1]), func() -> void: _trader_tab = key)
		b.toggle_mode = true
		b.button_pressed = _trader_tab == key
		b.custom_minimum_size.y = 36
		b.add_theme_font_size_override("font_size", 16)
		if key == "tasks" and talk:
			b.add_theme_color_override("font_color", Color(1.0, 0.72, 0.45))
		tabs.add_child(b)
	match _trader_tab:
		"buy":
			_trader_buy()
		"mods":
			_trader_mods()
		"sell":
			_trader_sell()
		_:
			_missions_column()


## Купить: карточки по разделам; у расходников — количество (− / +).
func _trader_buy() -> void:
	var shop := _column("Купить", 1.0)
	# куда класть купленное
	var dest := HBoxContainer.new()
	dest.add_theme_constant_override("separation", 6)
	dest.add_child(_text("Куда класть:", Color(0.75, 0.75, 0.72)))
	for d in [["backpack", "В рюкзак"], ["stash", "В тайник (стеллаж)"]]:
		var key := String(d[0])
		var chosen := _buy_to == key
		var b := _button(("▶ " if chosen else "") + String(d[1]), func() -> void: _buy_to = key)
		b.toggle_mode = true
		b.button_pressed = chosen
		if chosen:
			b.add_theme_color_override("font_color", Color(1.0, 0.86, 0.6))
			b.add_theme_color_override("font_pressed_color", Color(1.0, 0.86, 0.6))
		dest.add_child(b)
	dest.add_child(_text("рюкзак: %d / %d ячеек" % [Profile.backpack_cells(), Profile.backpack_capacity()], Color(0.6, 0.62, 0.6)))
	shop.add_child(dest)
	if _focus != "":
		var fr := HBoxContainer.new()
		fr.add_theme_constant_override("separation", 6)
		fr.add_child(_text("Подходит к: %s" % ItemDb.item_name(_focus), Color(1.0, 0.82, 0.45)))
		var only := _button("Только подходящее", func() -> void: _focus_only = not _focus_only)
		only.toggle_mode = true
		only.button_pressed = _focus_only
		fr.add_child(only)
		fr.add_child(_button("Сбросить", func() -> void:
			_focus = ""
			_focus_only = false))
		shop.add_child(fr)
	if Profile.needs_rescue():
		# без ствола и без денег — Михалыч выручает, иначе из этой ямы не выбраться
		var kit: Array[String] = []
		for pair in Balance.RESCUE_KIT:
			kit.append(ItemDb.label(ItemDb.make(String(pair[0]), int(pair[1]))))
		shop.add_child(_text("Михалыч: «Гол как сокол? Держи, отдашь потом»  —  " + ", ".join(kit), Color(1.0, 0.85, 0.55)))
		shop.add_child(_button("Взять даром", func() -> void: Profile.take_rescue()))
	# свои шаблоны — собрать комплект одной кнопкой (докупить недостающее)
	if not LoadoutTemplates.all().is_empty():
		_templates_block(shop, false)
	# каталоги: что открыто и когда следующий
	var open_n := Profile.trust_level()
	var cat_line := "Открыто каталогов: %d из %d — %s" % [open_n, TraderStock.catalogs().size(), TraderStock.catalog_name(open_n)]
	if open_n < TraderStock.catalogs().size():
		cat_line += "   ·   следующий «%s» — со ступени %d" % [TraderStock.catalog_name(open_n + 1), TraderStock.step_of(open_n + 1)]
	shop.add_child(_text(cat_line, Color(0.95, 0.82, 0.6)))
	# разделы: всё, оружие, патроны, магазины, обвес… — только те, где что-то есть
	var stock := _trader_stock()
	var cats := HFlowContainer.new()
	cats.add_theme_constant_override("h_separation", 6)
	cats.add_theme_constant_override("v_separation", 6)
	for t in CAT_TABS:
		var key := String(t[0])
		var cnt := 0
		for id in stock:
			if key == "all" or _cat_of(String(id)) == key:
				cnt += 1
		if cnt == 0:
			continue
		var tb := _button("%s  %d" % [String(t[1]), cnt], func() -> void: _cat_tab = key)
		tb.toggle_mode = true
		tb.button_pressed = _cat_tab == key
		cats.add_child(tb)
	shop.add_child(cats)
	var heads := {"weapon": "Оружие", "ammo": "Патроны", "mag": "Магазины", "mod": "Обвес", "armor": "Броня и снаряжение", "plate": "Броня и снаряжение", "backpack": "Рюкзаки",
		"med": "Медицина", "food": "Медицина", "throw": "Гранаты и свет"}
	var last_head := ""
	var flow: HFlowContainer = null
	for id in stock:
		var sid := String(id)
		if _cat_tab != "all" and _cat_of(sid) != _cat_tab:
			continue
		var head := String(heads.get(String(ItemDb.item(sid).cat), "Разное"))
		if head != last_head:
			last_head = head
			shop.add_child(_text(head, Color(0.95, 0.82, 0.6)))
			flow = HFlowContainer.new()
			flow.add_theme_constant_override("h_separation", 8)
			flow.add_theme_constant_override("v_separation", 8)
			shop.add_child(flow)
		# к выбранному стволу: подходит / не к месту (только патроны, магазины, обвес)
		var fit := _fits_focus(sid)
		if _focus_only and fit < 0:
			continue
		var stackable := ItemDb.stack(sid) > 1
		var n := _qty_of(sid) if stackable else 1
		var price := Profile.buy_price(sid) * n
		# сколько выбрано — счётчиком между «−» и «+», цена — за всё выбранное
		var card := ItemCard.make({"id": sid, "n": 1}, _sub_of(sid), "%s ₽" % InventoryUI.money(price), ItemCard.W, true)
		var tl := maxi(TraderStock.catalog_of(sid), 1)
		if _trust_blocked(sid, tl):
			# сильное Михалыч продаёт только тем, кому доверяет: каталог — со своей ступени
			card.controls.add_child(_text("ступень %d" % TraderStock.step_of(tl), Color(0.8, 0.5, 0.4)))
			card.modulate = Color(1, 1, 1, 0.6)
		else:
			if stackable:
				card.controls.add_child(_button("−", func() -> void: _step_qty(sid, -1)))
				card.controls.add_child(_qty_label(n))
				card.controls.add_child(_button("+", func() -> void: _step_qty(sid, 1)))
			var b := _button("Купить", func() -> void:
				if not Profile.buy(sid, n, _buy_to):
					if Profile.buy_price(sid) * n > Profile.money:
						toast("Не хватает денег")
					else:
						toast("Не купил: не влезает в %s — освободи место или выбери «%s»" % ["рюкзак" if _buy_to == "backpack" else "тайник",
							"В тайник" if _buy_to == "backpack" else "В рюкзак"])
					return
				# купил — количество снова по умолчанию
				_qty.erase(sid)
				if WeaponDb.is_weapon(sid):
					# купил ствол — сразу видно, что к нему подходит
					_focus = sid)
			b.disabled = price > Profile.money
			b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			card.controls.add_child(b)
		if WeaponDb.is_weapon(sid):
			card.controls.add_child(_button("Что подходит", func() -> void: _focus = "" if _focus == sid else sid))
			if sid == _focus:
				card.mark(1)
		elif fit != 0:
			card.mark(fit)
		flow.add_child(card)


## Раздел ассортимента предмета (ключ CAT_TABS).
func _cat_of(id: String) -> String:
	var cat := String(ItemDb.item(id).get("cat", "misc"))
	for t in CAT_TABS:
		if cat in (t[2] as Array):
			return String(t[0])
	return "misc"


## Порядок разделов в магазине: оружие, магазины, патроны, обвес, броня, медицина, гранаты, прочее.
const STOCK_ORDER := ["weapon", "mag", "ammo", "mod", "armor", "plate", "backpack", "med", "food", "throw"]


## Ассортимент по разделам (STOCK_ORDER), внутри раздела — как в каталоге. Админ («всё у
## Михалыча» в настройках) видит вообще всё: каждый предмет игры, кроме ключей и сведений
## (квестовые), без ступеней доверия.
func _trader_stock() -> Array:
	var stock: Array = TraderStock.stock().duplicate()
	if Settings.all_weapons:
		for id in ItemDb.all_ids():
			var cat := String(ItemDb.item(String(id)).get("cat", "misc"))
			if not id in stock and not cat in ["key", "intel"] and ItemDb.value(String(id)) > 0:
				stock.append(id)
	var keyed: Array = []
	for i in stock.size():
		var cat := String(ItemDb.item(String(stock[i])).get("cat", "misc"))
		var rank := STOCK_ORDER.find(cat)
		keyed.append([rank if rank >= 0 else STOCK_ORDER.size(), i, stock[i]])
	keyed.sort_custom(func(a: Array, b: Array) -> bool: return a[0] < b[0] or (a[0] == b[0] and a[1] < b[1]))
	var out: Array = []
	for k in keyed:
		out.append(k[2])
	return out


func _trust_blocked(id: String, level: int) -> bool:
	if Settings.all_weapons:
		return false
	return Profile.trust_level() < level and not id in Profile.unlocked_stock


## Подходит ли предмет к выбранному стволу: 1 — да, -1 — нет (патроны, магазины, обвес), 0 — не про то.
func _fits_focus(sid: String) -> int:
	if _focus == "":
		return 0
	if not WeaponDb.ammo(sid).is_empty():
		return 1 if WeaponDb.ammo_fits(_focus, sid) else -1
	if not WeaponDb.magazine(sid).is_empty():
		return 1 if WeaponDb.mag_fits(_focus, sid) else -1
	if not WeaponDb.attachment(sid).is_empty():
		var probe := {"id": _focus, "n": 1, "mods": {}}
		return 1 if not WeaponDb.mounts_for(probe, sid).is_empty() else -1
	return 0


## Сколько брать расходника: патроны — шагом 10 (от 10 до 5 стопок), остальное — поштучно.
func _qty_step(sid: String) -> int:
	return 10 if String(ItemDb.item(sid).cat) == "ammo" else 1


func _qty_of(sid: String) -> int:
	var step := _qty_step(sid)
	return int(_qty.get(sid, mini(ItemDb.stack(sid), 30) if step > 1 else 1))


func _step_qty(sid: String, dir: int) -> void:
	var step := _qty_step(sid)
	_qty[sid] = clampi(_qty_of(sid) + dir * step, step, ItemDb.stack(sid) * 5)


## Выбранное количество между «−» и «+».
func _qty_label(n: int) -> Label:
	var l := Label.new()
	l.text = "%d шт" % n
	l.custom_minimum_size.x = 46
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.add_theme_font_size_override("font_size", 14)
	l.add_theme_color_override("font_color", Color(1.0, 0.9, 0.6))
	return l


## Короткая строка под именем: чем предмет важен (класс и калибр, урон и пробитие, эффект, класс брони).
func _sub_of(id: String) -> String:
	var w := WeaponDb.weapon(id)
	if not w.is_empty():
		return "%s · %s" % [String(WeaponDb.CLASS_NAMES.get(String(w["class"]), "")), WeaponDb.caliber_name(String(w.caliber))]
	var a := WeaponDb.ammo(id)
	if not a.is_empty():
		return "урон %d · пробитие %d" % [int(a.damage), int(a.pen)]
	var at := WeaponDb.attachment(id)
	if not at.is_empty():
		return _fx_text(at)
	var mg := WeaponDb.magazine(id)
	if not mg.is_empty():
		return "на %d · %s" % [int(mg.capacity), WeaponDb.caliber_name(WeaponDb.mag_caliber(id))]
	for d in [WeaponDb.plate(id), WeaponDb.helmet(id)]:
		if not (d as Dictionary).is_empty():
			return "класс %d" % int(d["class"])
	var v := WeaponDb.vest(id)
	if not v.is_empty():
		return "плиты: " + ("спереди и сзади" if not (v.get("plates", []) as Array).is_empty() else "нет")
	# остальное — вид предмета; подробно — по «i»
	return String(ItemInfo.CAT_NAMES.get(String(ItemDb.item(id).get("cat", "misc")), ""))


## Обвес оружия: выбрать своё оружие (надетое, в тайнике, в рюкзаке) и собрать его на схеме —
## купить у Михалыча и сразу поставить или поставить своё из наличия.
func _trader_mods() -> void:
	var pick := _column("Своё оружие", 0.55)
	var ref := _weapon_ref()
	var any := false
	for src in [["equip:primary", Profile.equipment.get("primary", {})], ["equip:secondary", Profile.equipment.get("secondary", {})]]:
		var e: Dictionary = src[1]
		if e.is_empty():
			continue
		any = true
		var where := String(src[0])
		_weapon_pick_card(pick, e, "надето: " + Inventory.SLOT_NAMES[where.trim_prefix("equip:")], ref[0] == where,
			func() -> void:
				_tb_where = where
				_tb_uid = "")
	for ln in ["stash", "backpack"]:
		var list: Array = Profile.list_of(ln)
		for i in range(list.size()):
			var e: Dictionary = list[i]
			if not WeaponDb.is_weapon(String(e.id)):
				continue
			any = true
			var lname: String = ln
			var ei := i
			_weapon_pick_card(pick, e, "тайник" if ln == "stash" else "рюкзак", ref[0] == lname and int(ref[1]) == i,
				func() -> void:
					var le: Dictionary = Profile.list_of(lname)[ei]
					if not le.has("uid"):
						le["uid"] = "%d" % (Time.get_ticks_usec() % 1000000000)
					_tb_where = lname
					_tb_uid = String(le.uid))
	if not any:
		pick.add_child(_text("Оружия нет — купи во вкладке «Купить».", Color(0.7, 0.6, 0.5)))
		return
	var weapon: Dictionary = ref[2]
	var col := _column("Схема: %s" % ItemDb.item_name(String(weapon.get("id", ""))), 1.4)
	if weapon.is_empty():
		col.add_child(_text("Выбери оружие слева.", Color(0.7, 0.7, 0.66)))
		return
	var board := MountBoard.new()
	board.candidates = func(m: String) -> Array: return _trader_candidates(m)
	board.remove = func(m: String) -> void:
		var r := _weapon_ref()
		Profile.strip_part(String(r[0]), int(r[1]), "mod:" + m)
	col.add_child(board)
	board.setup(weapon)
	var spec := WeaponStats.compute(weapon)
	col.add_child(_text("Точность в прицеле %s · отдача %.3f · эргономика %d · шум %d м · %.1f кг" % [
		"%.2f°" % float(spec.ads_spread), float(spec.kick), int(spec.ergo), int(spec.noise_m), float(spec.weight)], Color(0.8, 0.82, 0.78)))
	col.add_child(_text("Клик по квадратику у точки крепления: купить у Михалыча и сразу поставить или поставить своё. Снятое — в тайник.", Color(0.6, 0.62, 0.6)))


func _weapon_pick_card(parent: Control, e: Dictionary, where: String, chosen: bool, pick: Callable) -> void:
	var card := ItemCard.make(e, where, "", 260.0)
	if chosen:
		card.controls.add_child(_text("▶ на схеме", Color(1.0, 0.86, 0.6)))
	else:
		card.controls.add_child(_button("Выбрать", pick))
	parent.add_child(card)


## Выбранное на схеме оружие: [где, индекс, запись] ("equip:<слот>", -1 — надетое; список и индекс —
## в тайнике / рюкзаке, найден по uid — индексы сдвигаются, когда из списка что-то уходит).
func _weapon_ref() -> Array:
	if _tb_where.begins_with("equip:"):
		var e: Dictionary = Profile.equipment.get(_tb_where.trim_prefix("equip:"), {})
		if not e.is_empty():
			return [_tb_where, -1, e]
	elif _tb_uid != "":
		var list := Profile.list_of(_tb_where)
		for i in range(list.size()):
			if String((list[i] as Dictionary).get("uid", "")) == _tb_uid:
				return [_tb_where, i, list[i]]
	for slot in ["primary", "secondary"]:
		if Profile.equipment.has(slot):
			return ["equip:" + slot, -1, Profile.equipment[slot]]
	return ["", -1, {}]


## В точку mount выбранного оружия: из ассортимента (купить и поставить) и своё из наличия.
func _trader_candidates(mount: String) -> Array:
	var ref := _weapon_ref()
	var weapon: Dictionary = ref[2]
	var out: Array = []
	if weapon.is_empty():
		return out
	var probe := weapon.duplicate(true)
	(probe.mods as Dictionary).erase(mount)
	for id in TraderStock.stock():
		var sid := String(id)
		if WeaponDb.attachment(sid).is_empty() or not mount in WeaponDb.mounts_for(probe, sid):
			continue
		var price := Profile.buy_price(sid)
		var why := WeaponDb.attach_block(probe, mount, sid)
		var tl := maxi(TraderStock.catalog_of(sid), 1)
		if _trust_blocked(sid, tl):
			why = "ступень доверия %d" % TraderStock.step_of(tl)
		elif price > Profile.money and why == "":
			why = "не хватает денег"
		out.append({"id": sid, "sub": "%s ₽ · %s" % [InventoryUI.money(price), _fx_text(WeaponDb.attachment(sid))],
			"act": "Купить и поставить", "why": why, "action": func() -> void: _buy_fit(sid, mount)})
	out.append_array(_owned_candidates(weapon, mount, String(ref[0]), false, int(ref[1])))
	return out


## Купить обвес и сразу поставить на выбранное оружие (вытесненное — в тайник).
func _buy_fit(sid: String, mount: String) -> void:
	if not Profile.buy(sid, 1):
		toast("Не купил: " + ("не хватает денег" if Profile.buy_price(sid) > Profile.money else "тайник полон"))
		return
	var si := -1
	for i in range(Profile.stash.size() - 1, -1, -1):
		if String(Profile.stash[i].id) == sid:
			si = i
			break
	var ref := _weapon_ref()
	if si >= 0 and String(ref[0]) != "":
		Profile.fit_part(String(ref[0]), int(ref[1]), "stash", si, mount)


## Продать: карточки тайника, рюкзака и кармана с ценой (стопку — целиком или по одной).
func _trader_sell() -> void:
	var sell := _column("Продать", 1.0)
	var any := false
	for src in [["stash", "Из тайника"], ["backpack", "Из рюкзака"], ["pocket", "Из защищённого кармана"]]:
		var from := String(src[0])
		var list := Profile.list_of(from)
		if list.is_empty():
			continue
		any = true
		var total := 0
		for e in list:
			total += Profile.sell_price(e)
		sell.add_child(_text("%s   ·   всё вместе %s ₽" % [String(src[1]), InventoryUI.money(total)], Color(0.95, 0.82, 0.6)))
		var flow := HFlowContainer.new()
		flow.add_theme_constant_override("h_separation", 8)
		flow.add_theme_constant_override("v_separation", 8)
		sell.add_child(flow)
		for i in range(list.size()):
			var e: Dictionary = list[i]
			var idx := i
			var card := ItemCard.make(e, "", "%s ₽" % InventoryUI.money(Profile.sell_price(e)))
			if int(e.n) > 1:
				card.controls.add_child(_button("1 шт.", func() -> void: Profile.sell(idx, 1, from)))
			var b := _button("Продать", func() -> void: Profile.sell(idx, int(e.n), from))
			b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			card.controls.add_child(b)
			flow.add_child(card)
	if not any:
		sell.add_child(_text("Продавать нечего: тайник и рюкзак пусты.", Color(0.6, 0.6, 0.6)))


## Задания Михалыча: взятые (прогресс, «Сдать»), предложенные («Взять» — пока есть свободные слоты).
func _missions_column() -> void:
	var col := _column("Задания   %d / %d" % [Profile.missions_active.size(), Missions.slots()], 1.1)
	# сюжет: Сергею есть что сказать — разговор (взять квест или отчитаться)
	for opt in Quests.talk_options("trader"):
		var o: Dictionary = opt
		var head := HBoxContainer.new()
		var t := _text(String(o.label), Color(1.0, 0.72, 0.45))
		t.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		t.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		head.add_child(t)
		head.add_child(_button("Поговорить", func() -> void: _talk(String(o.quest), String(o.dialogue))))
		col.add_child(head)
	if not Quests.talk_options("trader").is_empty():
		col.add_child(HSeparator.new())
	for id in Profile.missions_active.keys():
		var m := Missions.find(String(id))
		var mid := String(id)
		var head := HBoxContainer.new()
		var t := _text(Missions.line(mid), Color(1.0, 0.86, 0.6))
		t.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		head.add_child(t)
		var b := _button("Сдать", func() -> void: Missions.turn_in(mid))
		b.disabled = not Missions.done(mid)
		head.add_child(b)
		col.add_child(head)
		var d := _text("   %s%s  ·  %s ₽, доверие +%d" % [String(m.text), "  (только найденное в рейде)" if String(m.type) == "hand_in" else "", InventoryUI.money(int(m.reward.get("money", 0))), int(m.reward.get("trust", 0))], Color(0.66, 0.68, 0.66))
		d.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		col.add_child(d)
	col.add_child(HSeparator.new())
	var free := Missions.slots() - Profile.missions_active.size()
	for m in Missions.offered():
		var mid := String(m.id)
		var head := HBoxContainer.new()
		var t := _text(String(m.name), Color(0.9, 0.9, 0.86))
		t.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		head.add_child(t)
		var b := _button("Взять", func() -> void: Missions.take(mid))
		b.disabled = free <= 0
		head.add_child(b)
		col.add_child(head)
		var d := _text("   %s%s  ·  %s ₽, доверие +%d" % [String(m.text), "  (только найденное в рейде)" if String(m.type) == "hand_in" else "", InventoryUI.money(int(m.reward.get("money", 0))), int(m.reward.get("trust", 0))], Color(0.6, 0.62, 0.6))
		d.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		col.add_child(d)
	if free <= 0:
		col.add_child(_text("Больше заданий — с рацией (модули убежища).", Color(0.55, 0.57, 0.55)))


## Разговор с Сергеем по сюжету: окно торговли закрывается, реплики — внизу экрана.
func _talk(qid: String, did: String) -> void:
	close_ui()
	Quests.hud.start_dialogue(Quests.dialogue(qid, did), func() -> void: Quests.finish_talk(qid, "trader", did))


# ---------------------------------------------------------------- модули убежища

func _build_upgrades() -> void:
	_title.text = "Модули убежища   ·   %s ₽   ·   доверие Михалыча: ступень %d (каталог %d)" % [InventoryUI.money(Profile.money), Profile.trust_step(), Profile.trust_level()]
	var col := _column("Что построено и что дальше", 1.0)
	for m in Upgrades.all():
		var id := String(m.id)
		var lv := Upgrades.level(id)
		var mx := Upgrades.max_level(id)
		var head := HBoxContainer.new()
		var t := _text("%s   —   уровень %d из %d" % [String(m.name), lv, mx], Color(1.0, 0.86, 0.6))
		t.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		head.add_child(t)
		var cost := Upgrades.next_cost(id)
		if not cost.is_empty():
			var b := _button("Построить", func() -> void: Upgrades.build(id))
			b.disabled = Upgrades.block(id) != ""
			head.add_child(b)
		col.add_child(head)
		var what := _text("   " + String(m.what), Color(0.7, 0.72, 0.7))
		what.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		col.add_child(what)
		if lv > 0:
			col.add_child(_text("   сейчас: " + String((m.levels as Array)[lv - 1].effect), Color(0.6, 0.85, 0.6)))
		if not cost.is_empty():
			var parts: Array[String] = []
			if int(cost.get("money", 0)) > 0:
				parts.append("%s ₽" % InventoryUI.money(int(cost.money)))
			for pair in cost.get("items", []):
				var have := Profile.stash_count(String(pair[0]))
				parts.append("%s %d/%d" % [ItemDb.item_name(String(pair[0])), mini(have, int(pair[1])), int(pair[1])])
			var next := _text("   дальше: %s  ←  %s" % [String(cost.effect), ",  ".join(parts)], Color(0.85, 0.8, 0.7))
			next.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			col.add_child(next)
			var why := Upgrades.block(id)
			if why != "":
				col.add_child(_text("   " + why, Color(0.85, 0.55, 0.45)))
		col.add_child(HSeparator.new())


# ---------------------------------------------------------------- выход

func _build_exit() -> void:
	_title.text = "Выход в рейд"
	var col := _column("С собой", 1.0)
	for slot in Inventory.SLOTS:
		var e: Dictionary = Profile.equipment.get(slot, {})
		col.add_child(_text("%s:  %s" % [Inventory.SLOT_NAMES[slot], ItemDb.label(e) if not e.is_empty() else "—"], Color(0.85, 0.85, 0.82)))
	col.add_child(_text("Рюкзак: %d / %d ячеек, на %s ₽" % [Profile.backpack_cells(), Profile.backpack_capacity(), InventoryUI.money(ItemDb.value_of(Profile.backpack))], Color(0.85, 0.85, 0.82)))
	# чего из основного не хватает — видно заранее (выйти всё равно можно, спросим)
	var gaps := Profile.raid_kit_gaps()
	if not gaps.is_empty():
		col.add_child(_text("Не хватает: " + "; ".join(gaps), Color(1.0, 0.55, 0.4)))
	col.add_child(_text("Всё, что с собой, в рейде можно потерять.", Color(0.9, 0.75, 0.5)))
	_floors_column()
	_conditions_column()
	var go := _column("Выход", 0.6)
	var sel := Floors.find(Profile.floor)
	var route := _text("%s — %s" % [String(sel.get("name", "")), String(sel.get("route", ""))], Color(0.95, 0.82, 0.6))
	route.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	go.add_child(route)
	var fee := int(sel.get("fee", 0))
	if fee > 0:
		go.add_child(_text("Вылет — %s ₽" % InventoryUI.money(fee), Color(0.9, 0.75, 0.5)))
	var block := Floors.start_block(Profile.floor)
	if not Net.is_networked():
		var solo := _button("Соло-рейд", func() -> void:
			_confirm_raid(func() -> void:
				Floors.pay_fee(Profile.floor)
				Profile.pending_raid = true
				get_tree().change_scene_to_file(Floors.scene(Profile.floor))))
		solo.disabled = block != ""
		go.add_child(solo)
	elif Net.is_host():
		# все, кто в сети, идут по маршруту хоста (плата — с хоста)
		var all := _button("Рейд всем (%d в сети)" % (Net.player_names.size()), func() -> void:
			_confirm_raid(func() -> void:
				Floors.pay_fee(Profile.floor)
				Net.start_level.rpc(Floors.scene(Profile.floor), Profile.next_conditions)))
		all.disabled = block != ""
		go.add_child(all)
	else:
		go.add_child(_text("Рейд начинает хост — ждём его. Идёте по его маршруту и в его условия.", Color(0.9, 0.8, 0.6)))
	if block != "":
		go.add_child(_text(block, Color(1.0, 0.55, 0.4)))
	_coop_block(go)
	go.add_child(_text("Доверие Михалыча: ступень %d   ·   выходов из рейда: %d" % [Profile.trust_step(), Profile.extractions], Color(0.7, 0.72, 0.7)))


## Выход в рейд: чего из основного нет (Profile.raid_kit_gaps) — перечислить и спросить; не
## запрещаем — можно идти осознанно. Всё есть — сразу.
func _confirm_raid(go: Callable) -> void:
	var gaps := Profile.raid_kit_gaps()
	if gaps.is_empty():
		go.call()
		return
	var d := ConfirmationDialog.new()
	d.name = "RaidKitCheck"
	d.title = "Проверка снаряжения"
	d.dialog_text = "С собой нет:\n\n· " + "\n· ".join(gaps) + "\n\nВсё равно выйти в рейд?"
	d.ok_button_text = "Выйти в рейд"
	d.cancel_button_text = "Остаться"
	d.confirmed.connect(go)
	d.visibility_changed.connect(func() -> void:
		if not d.visible:
			d.queue_free())
	_root.add_child(d)
	d.popup_centered()


## Собрание: кто в сети и где; созвать своих (хост) или подключиться по IP; покинуть.
func _coop_block(col: VBoxContainer) -> void:
	col.add_child(_text("Собрание (кооп)", Color(0.95, 0.82, 0.6)))
	if Net.is_networked():
		var where := {"hideout": "в убежище", "raid": "в рейде", "menu": "в меню"}
		for id in Net.player_names:
			var tag := " (хост)" if int(id) == 1 else ""
			col.add_child(_text("· %s%s — %s" % [String(Net.player_names[id]), tag, String(where.get(String(Net.peer_scene.get(int(id), "")), "подключается"))], Color(0.85, 0.85, 0.8)))
		col.add_child(_button("Покинуть собрание", func() -> void:
			Net.disconnect_all()
			get_tree().reload_current_scene()))
		return
	var cfg := ConfigFile.new()
	cfg.load(CameraRig.SETTINGS_PATH)
	var nick := LineEdit.new()
	nick.placeholder_text = "Ник"
	nick.text = String(cfg.get_value("net", "name", "Игрок%d" % (randi() % 900 + 100)))
	col.add_child(nick)
	var ip := LineEdit.new()
	ip.placeholder_text = "IP хоста"
	ip.text = String(cfg.get_value("net", "address", "127.0.0.1"))
	col.add_child(ip)
	var status := _text("", Color(1.0, 0.6, 0.45))
	var remember := func() -> void:
		cfg.set_value("net", "name", nick.text)
		cfg.set_value("net", "address", ip.text)
		cfg.save(CameraRig.SETTINGS_PATH)
	col.add_child(_button("Созвать своих (я хост, порт %d)" % Net.PORT, func() -> void:
		remember.call()
		var err := Net.host(nick.text)
		if err != "":
			status.text = err
		else:
			# убежище заново — уже в сети (свой игрок с синхронизацией)
			get_tree().reload_current_scene()))
	col.add_child(_button("Подключиться по IP", func() -> void:
		remember.call()
		var err := Net.join(ip.text, nick.text)
		if err != "":
			status.text = err
			return
		status.text = "Подключаюсь…"
		Net.joined.connect(func() -> void: get_tree().reload_current_scene(), CONNECT_ONE_SHOT)
		Net.join_failed.connect(func() -> void: status.text = "Не удалось подключиться", CONNECT_ONE_SHOT)))
	col.add_child(status)


## Условия рейда: время, погода, электричество — выбор; риск, награда за него и что взять с собой.
func _conditions_column() -> void:
	var col := _column("Условия рейда", 1.0)
	var c := RaidConditions.normalized(Profile.next_conditions)
	for axis in [["time", "Время", Balance.RAID_TIME], ["weather", "Погода", Balance.RAID_WEATHER], ["power", "Электричество", Balance.RAID_POWER]]:
		col.add_child(_text(String(axis[1]), Color(0.75, 0.75, 0.72)))
		var row := HFlowContainer.new()
		row.add_theme_constant_override("h_separation", 6)
		for key in (axis[2] as Dictionary):
			var k := String(key)
			var ax := String(axis[0])
			var chosen := String(c[ax]) == k
			var b := _button(("▶ " if chosen else "") + String((axis[2] as Dictionary)[key].name), func() -> void:
				var nc := RaidConditions.normalized(Profile.next_conditions)
				nc[ax] = k
				Profile.next_conditions = nc
				Profile.save())
			if chosen:
				b.add_theme_color_override("font_color", Color(1.0, 0.86, 0.6))
			row.add_child(b)
		col.add_child(row)
	var r := RaidConditions.risk(c)
	col.add_child(_text("Риск: %d   ·   лут богаче: %d%% контейнеров   ·   доплата Михалыча: +%d%% от вынесенного" % [
		r, int(RaidConditions.loot_bonus(c) * 100.0), int(RaidConditions.pay_bonus(c) * 100.0)], Color(1.0, 0.8, 0.5)))
	for h in RaidConditions.hints(c):
		var l := _text("• " + h, Color(0.82, 0.82, 0.78))
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		col.add_child(l)
	col.add_child(_button("Случайные условия", func() -> void:
		var rng := RandomNumberGenerator.new()
		rng.randomize()
		Profile.next_conditions = RaidConditions.random(rng)
		Profile.save()))


## Карты: этажи внутри здания отрезаны, у каждого свой путь снаружи. Открытый маршрут выбирается,
## закрытый — открывается у Михалыча (доверие + плата за наводку).
func _floors_column() -> void:
	var col := _column("Маршрут", 1.1)
	for f in Floors.all():
		var id := String(f.id)
		var box := VBoxContainer.new()
		box.add_theme_constant_override("separation", 2)
		var head := HBoxContainer.new()
		var chosen := id == Profile.floor
		var title := _text(("▶ " if chosen else "   ") + String(f.name), Color(1.0, 0.86, 0.6) if chosen else Color(0.9, 0.9, 0.86))
		title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		head.add_child(title)
		if Floors.is_open(id):
			if not chosen:
				head.add_child(_button("Выбрать", func() -> void: Floors.select(id)))
		else:
			var b := _button("Открыть за %s ₽" % InventoryUI.money(int(f.price)), func() -> void: Floors.unlock(id))
			b.disabled = Floors.unlock_block(id) != ""
			head.add_child(b)
		box.add_child(head)
		var how := _text("   %s — %s" % [String(f.route), String(f.how)], Color(0.62, 0.64, 0.62))
		how.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		box.add_child(how)
		var state := ""
		if not Floors.is_open(id):
			var why := Floors.unlock_block(id)
			state = "закрыт — " + (why if why != "" else "Михалыч готов показать дорогу")
		elif not Floors.built(id):
			state = "маршрут открыт, этаж ещё не собран"
		if state != "":
			box.add_child(_text("   " + state, Color(0.85, 0.55, 0.45)))
		col.add_child(box)


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
	var wid := String(weapon.id)
	# схема: от точек крепления — квадратики; клик — что подходит из тайника и рюкзака
	var board := MountBoard.new()
	board.candidates = func(m: String) -> Array: return _owned_candidates(weapon, m, "equip:" + _wb_slot, true)
	board.remove = func(m: String) -> void: Profile.remove_mod(_wb_slot, m)
	left.add_child(board)
	board.setup(weapon)
	# карточка: калибр, состояние, магазин и патрон, вес
	var spec := WeaponStats.compute(weapon)
	var mag: Dictionary = weapon.get("mag", {}) if weapon.get("mag") is Dictionary else {}
	var w := WeaponDb.weapon(wid)
	left.add_child(_text("%s · %s · %s · износ %d%% · %.1f кг" % [String(WeaponDb.CLASS_NAMES.get(String(w["class"]), "")), WeaponDb.caliber_name(String(w.caliber)),
		"встроенный магазин" if w.has("internal_mag") else ItemDb.item_name(String(mag.get("id", ""))) if String(mag.get("id", "")) != "" else "без магазина",
		int(weapon.get("dur", 100)), float(spec.weight)], Color(0.85, 0.85, 0.8)))
	# сколько внутри — не видно: полный / пустой (проверка — в рейде, держать R)
	var loaded := "пустой" if int(mag.get("rounds", 0)) <= 0 else ("полный" if int(mag.get("rounds", 0)) >= int(spec.mag) else "не пустой")
	left.add_child(_text("Магазин на %d — %s · %s — урон %d, пробитие %d" % [int(spec.mag), loaded, ItemDb.item_name(String(spec.ammo)), int(spec.damage), int(spec.pen)], Color(0.8, 0.85, 0.75)))
	left.add_child(_text("Клик по квадратику у точки крепления — поставить или снять.", Color(0.6, 0.62, 0.6)))
	# справа: характеристики (сравнение с «голым») и магазин
	var right := _column("Характеристики", 1.0)
	var bare := weapon.duplicate(true)
	bare["mods"] = {}
	_stats(right, spec, WeaponStats.compute(bare))
	# магазин — сменить на подходящий из тайника / рюкзака
	if not w.has("internal_mag"):
		right.add_child(_text("Магазин  [%s]" % String(w.get("mag_if", "")), Color(0.95, 0.82, 0.6)))
		for from_bp in [false, true]:
			var src: Array = Profile.backpack if from_bp else Profile.stash
			for i2 in range(src.size()):
				if not WeaponDb.mag_fits(wid, String(src[i2].id)):
					continue
				var idx := i2
				var bp: bool = from_bp
				var row := HBoxContainer.new()
				var l := _text("  ⇄ " + ItemDb.label(src[i2]), Color(0.7, 0.8, 0.72))
				l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
				row.add_child(l)
				row.add_child(_button("Вставить", func() -> void: Profile.fit_part("equip:" + _wb_slot, -1, "backpack" if bp else "stash", idx, "")))
				right.add_child(row)


## Что из своего (тайник и рюкзак) встаёт в точку mount оружия weapon (запись where / idx в профиле):
## [{id, sub, act, action, why}] для схемы оружия. bench — ставит верстак (его уровень решает).
func _owned_candidates(weapon: Dictionary, mount: String, where: String, bench: bool, idx: int = -1) -> Array:
	var out: Array = []
	var probe := weapon.duplicate(true)
	(probe.mods as Dictionary).erase(mount)
	for src_name in ["stash", "backpack"]:
		var src: Array = Profile.list_of(src_name)
		for i in range(src.size()):
			var id := String(src[i].id)
			if WeaponDb.attachment(id).is_empty() or not mount in WeaponDb.mounts_for(probe, id):
				continue
			var si := i
			var sn: String = src_name
			var why := Profile.mod_block(id, mount) if bench else ""
			if why == "":
				why = WeaponDb.attach_block(probe, mount, id)
			out.append({"id": id, "sub": "%s · %s" % ["тайник" if sn == "stash" else "рюкзак", _fx_text(WeaponDb.attachment(id))],
				"act": "Поставить", "why": why,
				"action": func() -> void: Profile.fit_part(where, idx, sn, si, mount)})
	return out


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
			parts.append("глушитель")
		elif k == "flash":
			parts.append("вспышка %d%%" % int(round(float(v) * 100.0)))
		elif k == "aim":
			parts.append("вскидка %+d%%" % int(round((float(v) - 1.0) * 100.0)))
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
