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
## Верстак: "build" — обвесы и ремонт, "stickers" — наклейки на оружие (StickerPanel).
var _wb_mode: String = "build"
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
## Торговец: подгруппа внутри раздела ("" — все): класс оружия, калибр, назначение обвеса.
var _sub_tab: String = ""
## Торговец: поиск по названию и порядок по цене ("" — как в каталоге, "up" / "down").
var _shop_search: String = ""
var _shop_sort: String = ""
## Торговец: список товаров под закреплённой шапкой (перезаполняется без перестройки окна).
var _shop_list: VBoxContainer
## Витрина Михалыча (LightUi): выбранный предмет, шапка разделов, витрина и подробности, раздел выбора
var _sel: String = ""
var _sel_view: String = ""
var _shop_head: VBoxContainer
var _shop_center: VBoxContainer
var _shop_detail: VBoxContainer
## Рамка окна: тёмная у всех, у Михалыча — светлая без своей строки заголовка (у него шапка своя)
var _panel: PanelContainer
var _panel_dark: StyleBoxFlat
var _head_row: HBoxContainer
## Где окну переносить строки само (у Михалыча — только тёмная вставка прежних вкладок; null — нигде)
var _wrap_root: Control
## Кадр открытия: Tab, открывший окно, его же не закрывает.
var _opened_frame: int = -1
var _toast: Label
var _toast_t: float = 0.0
var _tb_where: String = "equip:primary"
var _tb_uid: String = ""
## Вкладка «Продать»: выбранный предмет [где, индекс] ("equip:<слот>", -1 — надетый ствол), [] — нет.
var _sell_sel: Array = []
## Вкладка «Продать»: отмеченное к продаже — [[где, индекс], …] (сколько угодно предметов).
var _sell_picks: Array = []

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
	_panel = panel
	_panel_dark = sb
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 12)
	panel.add_child(v)
	var head := HBoxContainer.new()
	v.add_child(head)
	_head_row = head
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
			# обучение: «открыть рюкзак» засчитывается и заранее
			Quests.ui_seen("inventory")
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
	if UiTheme.typing():
		# курсор в поле (поиск, количество, имя шаблона): Esc — выйти из поля, клавиши окно не закрывают
		if Input.is_action_just_pressed("ui_cancel"):
			get_viewport().gui_release_focus()
	elif (Input.is_action_just_pressed("ui_cancel") or Input.is_action_just_pressed("inventory")) and not ItemInfo.blocking() and not just_opened:
		close_ui()
		return
	if _kind == HideoutStation.Kind.ENGRAVER and _sig == "engraver":
		return
	# страница наклеек — своя панель, сама следит за вещами (как окно гравировщика)
	if _kind == HideoutStation.Kind.WORKBENCH and _wb_mode == "stickers" and _sig == "stickers":
		return
	var sig := "%d|%d|%s|%s|%s|%s|%s|%s|%d|%s|%s|%s" % [_kind, Profile.money, str(Profile.stash), str(Profile.equipment), str(Profile.backpack), _wb_slot,
		Profile.floor, str(Profile.floors_open), Profile.trust, str(Profile.pocket), str(Profile.modules), str(Profile.missions_active) + str(Profile.next_conditions)]
	# количество к покупке в подписи нет: карточка правит цену на месте, поле ввода не теряет курсор
	var plan_level: Node = get_tree().get_first_node_in_group("hideout_level")
	sig += "|plan%s" % str(plan_level != null and bool(plan_level.get("raid_plan_accepted")))
	sig += "|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s" % [_trader_tab, _tb_where, _tb_uid, _buy_to, _focus, _focus_only, _cat_tab, _sub_tab, _shop_sort, Settings.shop_loot]
	sig += "|" + str(Profile.loadout_templates) + "|" + str(_sell_sel) + "|" + str(_sell_picks)
	# собрание: кто в сети и где — окно выхода обновляется
	sig += "|%s|%s|%s|%s|%s" % [Net.is_networked(), str(Net.player_names), str(Net.peer_scene), str(Net.host_conditions), Settings.shop_all()]
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
	# Михалыч — светлое окно со своей шапкой (LightUi), остальные — прежние тёмные
	var light := _kind == HideoutStation.Kind.TRADER
	_panel.add_theme_stylebox_override("panel", LightUi.box(LightUi.BG, 6, 0) if light else _panel_dark)
	_head_row.visible = not light
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
		HideoutStation.Kind.ENGRAVER:
			_title.text = "Лазерный гравировщик"
			_cols.add_child(EngraverPanel.new())
			_sig = "engraver"
	# строки-абзацы в колонках переносятся по словам: длинная строка не раздвигает окно за экран. Светлое окно
	# Михалыча переносит само, где надо (подписи строк и плиток обрезаются: с переносом они схлопывались в
	# нулевую высоту); прежние его вкладки — тёмная вставка (_wrap_root) — как у всех
	var wrap_root: Control = _wrap_root if light else _cols
	if wrap_root and is_instance_valid(wrap_root):
		for l in wrap_root.find_children("*", "Label", true, false):
			if l.get_parent() is VBoxContainer and (l as Label).autowrap_mode == TextServer.AUTOWRAP_OFF:
				(l as Label).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		for b in wrap_root.find_children("*", "Button", true, false):
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
	# подсумки и сумка сброса надетой разгрузки — тоже сетки окна
	for part: String in ["rig", "dump"]:
		if Profile.grid_of(part) != Vector2i.ZERO:
			expected += 1
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
	# ростовая фигура: слоты стоят на своих местах
	var doll := EquipDoll.new()
	gear.add_child(doll)
	for slot in Inventory.SLOTS:
		var s := String(slot)
		var sv: SlotView = doll.views[s]
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
	doll.set_equipment(Profile.equipment)
	# места брони: подсумок из сетки — на полуслот, с места на место, двойной клик — снять в тайник
	doll.places.pouch_from.connect(func(src: GridView, idx: int, at: int) -> void:
		if not Profile.equip_from(src.role, idx, "pouch:%d" % at):
			toast("Подсумок сюда не встаёт"))
	doll.places.pouch_moved.connect(func(from_at: int, to_at: int) -> void:
		if not Profile.move_pouch(from_at, to_at):
			toast("Подсумок сюда не встаёт"))
	doll.places.pouch_off.connect(func(at: int) -> void:
		if not Profile.unequip("pouch:%d" % at):
			toast("В тайнике нет места"))
	# разгрузка: подсумки под магазины (перезарядка — из них) и сумка сброса пустых
	var rig_views: Array[GridView] = []
	if Profile.grid_of("rig") != Vector2i.ZERO:
		var rig_row := HBoxContainer.new()
		rig_row.add_theme_constant_override("separation", 14)
		gear.add_child(rig_row)
		for part: Array in [["rig", "Подсумки — магазины"], ["dump", "Сброс пустых"]]:
			var pg2: Vector2i = Profile.grid_of(String(part[0]))
			if pg2 == Vector2i.ZERO:
				continue
			var box := VBoxContainer.new()
			box.add_theme_constant_override("separation", 3)
			rig_row.add_child(box)
			var cap := _text(String(part[1]), Color(0.95, 0.82, 0.6))
			cap.add_theme_font_size_override("font_size", 13)
			box.add_child(cap)
			var gv := GridView.new(pg2, String(part[0]))
			gv.set_items(Profile.list_of(String(part[0])))
			if String(part[0]) == "rig":
				# в подсумок — магазин его вида: подписи колонок и красная подсветка не на своём
				gv.column_groups = ItemDb.rig_column_groups(Profile.equipment)
				gv.accept_at = func(id: String, x: int, r: bool) -> bool: return ItemDb.rig_id_fits_at(Profile.equipment, id, x, r)
			box.add_child(gv)
			rig_views.append(gv)
	else:
		var no_rig := _text("Разгрузки нет: магазины в рейде достаются из рюкзака — перезарядка дольше.", Color(0.6, 0.6, 0.56))
		no_rig.add_theme_font_size_override("font_size", 13)
		gear.add_child(no_rig)
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
	views.append_array(rig_views)
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
	if Balance.LOOT_PACKS.has(id):
		menu.add_item("Вскрыть упаковку")
		acts.append(func() -> void:
			if not Profile.unpack(name, idx, id):
				toast("Нет места для содержимого упаковки")
			_sig = "")
	if not ItemDb.equip(id).is_empty():
		menu.add_item("Надеть" if not ItemDb.equip(id).has("weapon") else "Взять (слот оружия)")
		acts.append(func() -> void: Profile.equip_from(name, idx))
	if ItemDb.pouch_cost(id) > 0.0:
		var armor: Dictionary = Profile.equipment.get("armor", {})
		var free := ItemDb.places_free(armor) if not armor.is_empty() else 0.0
		menu.add_item("На броню (мест свободно: %s)" % str(free).replace(".5", "½").replace(".0", "") if not armor.is_empty() else "На броню — броня не надета")
		acts.append(func() -> void:
			if not Profile.equip_from(name, idx):
				toast("На броне нет места под этот подсумок"))
	if ItemDb.pouch_list(list[idx]).size() > 0:
		menu.add_item("Снять подсумки")
		acts.append(func() -> void: Profile.strip_pouches(name, idx))
	menu.add_item("В рюкзак" if name == "stash" else "В тайник")
	acts.append(func() -> void: _quick(name, idx))
	if WeaponDb.is_weapon(id):
		menu.add_item("Собрать…")
		acts.append(func() -> void: open_builder(name, idx))
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
			var types := Gear.mag_types_text(entry)
			toast("%s: %s%s" % [ItemDb.item_name(id), Gear.ammo_estimate(int(entry.get("rounds", 0)), cap, Gear.mag_exact(id)), " · " + types if types != "" else ""])
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
	for r in [role, "backpack", "pocket", "stash", "rig", "dump"]:
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
	var before := _op.steps
	var more := _op.tick(delta)
	# в убежище тоже слышно, как патроны встают в магазин
	if _op.steps > before and _op.kind == "load":
		Audio.play_ui("mag_round", -12.0)
	if not more:
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
	if WeaponDb.is_weapon(String(e.get("id", ""))):
		menu.add_item("Собрать…")
		acts.append(func() -> void: open_builder(where, idx))
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
	if ItemDb.pouch_list(e).size() > 0:
		menu.add_item("Снять подсумки (%d)" % ItemDb.pouch_list(e).size())
		acts.append(func() -> void: Profile.strip_pouches(where, idx))
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

## Михалыч в светлом виде (владелец 2026-10-30, макет «Б1 — витрина светлая»): шапка с вкладками-«пилюлями»,
## «Купить» — разделы чертой, слева список, в центре большой снимок выбранного и что к нему подходит, справа
## подробности и покупка; «Комплекты» — карточками по три в строку. Обвес, продажа и задания пока прежние —
## тёмной вставкой под светлой шапкой.
func _build_trader() -> void:
	_title.text = String(_trader.get("name", "Торговец"))
	_wrap_root = null
	var page := VBoxContainer.new()
	page.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	page.size_flags_vertical = Control.SIZE_EXPAND_FILL
	page.add_theme_constant_override("separation", 0)
	page.theme = LightUi.theme()
	_cols.add_child(page)
	page.add_child(_trader_header())
	match _trader_tab:
		"buy":
			_trader_buy(page)
		"kits":
			_trader_kits(page)
		_:
			# прежние вкладки — тёмной вставкой со своей (умалчиваемой) темой: их надписи светлые
			var pad := MarginContainer.new()
			pad.size_flags_vertical = Control.SIZE_EXPAND_FILL
			for side: String in ["left", "right", "top", "bottom"]:
				pad.add_theme_constant_override("margin_" + side, 18)
			page.add_child(pad)
			var inset := PanelContainer.new()
			_wrap_root = inset
			inset.theme = ThemeDB.get_default_theme()
			inset.add_theme_stylebox_override("panel", LightUi.box(Color(0.075, 0.07, 0.065, 0.97), 8, 16))
			pad.add_child(inset)
			var row := HBoxContainer.new()
			row.add_theme_constant_override("separation", 16)
			inset.add_child(row)
			var keep := _cols
			_cols = row
			match _trader_tab:
				"mods":
					_trader_mods()
				"sell":
					_trader_sell()
				_:
					_missions_column()
			_cols = keep


## Шапка: имя, доверие, вкладки, деньги, закрыть.
func _trader_header() -> Control:
	var bar := PanelContainer.new()
	var sb := LightUi.box(LightUi.SURFACE, 0, 0)
	sb.border_color = LightUi.LINE
	sb.border_width_bottom = 1
	sb.content_margin_left = 28
	sb.content_margin_right = 20
	sb.content_margin_top = 12
	sb.content_margin_bottom = 12
	bar.add_theme_stylebox_override("panel", sb)
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 24)
	bar.add_child(h)
	var who := HBoxContainer.new()
	who.add_theme_constant_override("separation", 12)
	h.add_child(who)
	var name := LightUi.caps(String(_trader.get("short", "Михалыч")), 30, LightUi.TEXT)
	who.add_child(name)
	var trust := LightUi.caps("доверие %d / %d" % [Profile.trust_step(), int(Balance.TRUST_STEPS.max)], 14)
	trust.size_flags_vertical = Control.SIZE_SHRINK_END
	who.add_child(trust)
	var nav := HBoxContainer.new()
	nav.add_theme_constant_override("separation", 4)
	h.add_child(nav)
	var talk := not Quests.talk_options("trader").is_empty()
	for t in [["buy", "Купить"], ["kits", "Комплекты"], ["mods", "Обвес оружия"], ["sell", "Продать"], ["tasks", "Задания" + ("  •" if talk else "")]]:
		var key := String(t[0])
		var b := LightUi.button(String(t[1]).to_upper(), "pill_on" if _trader_tab == key else "pill", func() -> void: _trader_tab = key)
		b.custom_minimum_size.y = 38
		b.add_theme_font_size_override("font_size", 16)
		if key == "tasks" and talk and _trader_tab != key:
			b.add_theme_color_override("font_color", LightUi.ACCENT)
		nav.add_child(b)
	var gap := Control.new()
	gap.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(gap)
	if Settings.shop_all():
		var admin := LightUi.caps("админ: всё у Михалыча", 13, LightUi.ACCENT)
		admin.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		h.add_child(admin)
	var money := LightUi.mono("%s ₽" % InventoryUI.money(Profile.money), 22)
	money.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	h.add_child(money)
	var close := Button.new()
	close.text = "Закрыть · Esc"
	close.focus_mode = Control.FOCUS_NONE
	close.pressed.connect(close_ui)
	close.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	h.add_child(close)
	return bar


## Купить: разделы и поиск сверху (не уезжают), ниже — список, витрина выбранного, подробности.
func _trader_buy(page: VBoxContainer) -> void:
	var stock := _trader_stock()
	var top := MarginContainer.new()
	top.add_theme_constant_override("margin_left", 28)
	top.add_theme_constant_override("margin_right", 28)
	top.add_theme_constant_override("margin_top", 4)
	page.add_child(top)
	var head := VBoxContainer.new()
	head.add_theme_constant_override("separation", 0)
	top.add_child(head)
	_shop_head = head
	# разделы чертой снизу (только те, где что-то есть) и поиск
	var tabs := HBoxContainer.new()
	tabs.add_theme_constant_override("separation", 22)
	head.add_child(tabs)
	for t in CAT_TABS:
		var key := String(t[0])
		var cnt := 0
		for id in stock:
			if key == "all" or _cat_of(String(id)) == key:
				cnt += 1
		if cnt == 0:
			continue
		var tb := LightUi.button("%s  %d" % [String(t[1]).to_upper(), cnt], "tab_on" if _cat_tab == key else "tab", func() -> void:
			_cat_tab = key
			_sub_tab = "")
		tb.add_theme_font_size_override("font_size", 15)
		tabs.add_child(tb)
	var gap := Control.new()
	gap.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tabs.add_child(gap)
	var search := LineEdit.new()
	search.placeholder_text = "Поиск по названию"
	search.text = _shop_search
	search.clear_button_enabled = true
	search.custom_minimum_size = Vector2(300, 36)
	search.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	search.add_theme_font_size_override("font_size", 15)
	search.text_changed.connect(func(t: String) -> void:
		_shop_search = t
		if _fill_shop(false):
			_fill_showcase())
	search.text_submitted.connect(func(_t: String) -> void: search.release_focus())
	tabs.add_child(search)
	var rule := ColorRect.new()
	rule.color = LightUi.LINE
	rule.custom_minimum_size.y = 1
	head.add_child(rule)
	# подгруппы раздела (пистолеты, ПП… / калибры / прицелы, дульные…) и порядок по цене
	var subs_row := HBoxContainer.new()
	subs_row.add_theme_constant_override("separation", 18)
	head.add_child(subs_row)
	if _cat_tab != "all":
		var subs: Array = []
		var counts := {}
		for id in stock:
			if _cat_of(String(id)) != _cat_tab:
				continue
			var g := _subgroup(String(id))
			if not counts.has(g[1]):
				subs.append(g)
			counts[g[1]] = int(counts.get(g[1], 0)) + 1
		subs.sort_custom(func(a: Array, b: Array) -> bool: return int(a[0]) < int(b[0]))
		if subs.size() > 1:
			var all_b := LightUi.button("ВСЕ", "tab_on" if _sub_tab == "" else "tab", func() -> void: _sub_tab = "")
			all_b.add_theme_font_size_override("font_size", 14)
			subs_row.add_child(all_b)
			for g in subs:
				var gname := String(g[1])
				var cb := LightUi.button("%s  %d" % [gname.to_upper(), int(counts[gname])], "tab_on" if _sub_tab == gname else "tab", func() -> void: _sub_tab = gname)
				cb.add_theme_font_size_override("font_size", 14)
				subs_row.add_child(cb)
		elif _sub_tab != "":
			_sub_tab = ""
	var sgap := Control.new()
	sgap.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	subs_row.add_child(sgap)
	var sort_names := {"": "Цена: по каталогу", "up": "Цена ↑ дешёвые", "down": "Цена ↓ дорогие"}
	var sort_b := Button.new()
	sort_b.text = String(sort_names[_shop_sort])
	sort_b.focus_mode = Control.FOCUS_NONE
	sort_b.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	sort_b.pressed.connect(func() -> void: _shop_sort = {"": "up", "up": "down", "down": ""}[_shop_sort])
	subs_row.add_child(sort_b)
	# тело: список, витрина, подробности
	var body_pad := MarginContainer.new()
	body_pad.size_flags_vertical = Control.SIZE_EXPAND_FILL
	for side: String in ["left", "right"]:
		body_pad.add_theme_constant_override("margin_" + side, 28)
	body_pad.add_theme_constant_override("margin_top", 14)
	body_pad.add_theme_constant_override("margin_bottom", 20)
	page.add_child(body_pad)
	var body := HBoxContainer.new()
	body.add_theme_constant_override("separation", 20)
	body_pad.add_child(body)
	var left := VBoxContainer.new()
	left.custom_minimum_size.x = 440
	left.add_theme_constant_override("separation", 8)
	body.add_child(left)
	var open_n := Profile.trust_level()
	var cat_line := "открыто каталогов %d из %d — %s" % [open_n, TraderStock.catalogs().size(), TraderStock.catalog_name(open_n)]
	if open_n < TraderStock.catalogs().size():
		cat_line += " · «%s» — со ступени %d" % [TraderStock.catalog_name(open_n + 1), TraderStock.step_of(open_n + 1)]
	var cl := LightUi.label(cat_line, 13, LightUi.MUTED)
	cl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	left.add_child(cl)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	left.add_child(scroll)
	var list := VBoxContainer.new()
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.add_theme_constant_override("separation", 6)
	scroll.add_child(list)
	_shop_list = list
	var center := VBoxContainer.new()
	center.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	center.add_theme_constant_override("separation", 12)
	body.add_child(center)
	_shop_center = center
	var detail_panel := PanelContainer.new()
	detail_panel.custom_minimum_size.x = 400
	detail_panel.add_theme_stylebox_override("panel", LightUi.box(LightUi.SURFACE, 8, 22, LightUi.LINE, 1))
	body.add_child(detail_panel)
	var detail := VBoxContainer.new()
	detail.add_theme_constant_override("separation", 10)
	detail_panel.add_child(detail)
	_shop_detail = detail
	_fill_shop()
	_fill_showcase()


## Список под шапкой: перезаполняется сам (поиск) — шапка и поле поиска остаются на месте. Выбранное держится,
## пока оно в продаже (keep_sel — и когда его нет в списке: выбрали плиткой «подходит»); сменили раздел или
## поиском убрали выбранное из списка — выбирается первое. true — выбранное сменилось.
func _fill_shop(keep_sel: bool = true) -> bool:
	if _shop_list == null or not is_instance_valid(_shop_list):
		return false
	var shop := _shop_list
	for c in shop.get_children():
		shop.remove_child(c)
		c.queue_free()
	if Profile.needs_rescue():
		# без ствола и без денег — Михалыч выручает, иначе из этой ямы не выбраться
		var kit: Array[String] = []
		for pair in Balance.RESCUE_KIT:
			kit.append(ItemDb.label(ItemDb.make(String(pair[0]), int(pair[1]))))
		var rescue := LightUi.label("Михалыч: «Гол как сокол? Держи, отдашь потом»  —  " + ", ".join(kit), 14, LightUi.ACCENT_DARK)
		rescue.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		shop.add_child(rescue)
		var take := LightUi.button("ВЗЯТЬ ДАРОМ", "primary", func() -> void: Profile.take_rescue())
		take.custom_minimum_size.y = 40
		shop.add_child(take)
	var rows := _shop_rows()
	if rows.is_empty():
		shop.add_child(LightUi.label("Ничего не найдено." if _shop_search.strip_edges() != "" else "В этом разделе пусто.", 15, LightUi.MUTED))
		return false
	var ids: Array = rows.map(func(r: Dictionary) -> String: return String(r.id))
	var view := "%s|%s" % [_cat_tab, _sub_tab]
	if view != _sel_view:
		_sel_view = view
		keep_sel = false
	var before := _sel
	if _sel == "" or not _sel in _trader_stock() or (not keep_sel and not _sel in ids):
		_sel = String(ids[0])
	var cat_names := {}
	for t in CAT_TABS:
		cat_names[String(t[0])] = String(t[1])
	var last_cat := ""
	var last_g := ""
	for r: Dictionary in rows:
		if String(r.cat) != last_cat and _cat_tab == "all":
			var ch := LightUi.caps(String(cat_names.get(String(r.cat), "Разное")), 14, LightUi.TEXT)
			if last_cat != "":
				var pad := Control.new()
				pad.custom_minimum_size.y = 8
				shop.add_child(pad)
			shop.add_child(ch)
			last_g = ""
		if String(r.cat) != last_cat or String(r.g) != last_g:
			last_cat = String(r.cat)
			last_g = String(r.g)
			shop.add_child(LightUi.caps(last_g, 12))
		shop.add_child(_shop_row(String(r.id)))
	return _sel != before


## Что показывать в списке: раздел, подгруппа, поиск; порядок — раздел, подгруппа, цена (если выбрана), каталог.
func _shop_rows() -> Array:
	var needle := _shop_search.strip_edges().to_lower()
	var rows: Array = []
	var stock := _trader_stock()
	for i in stock.size():
		var sid := String(stock[i])
		var cat := _cat_of(sid)
		if _cat_tab != "all" and cat != _cat_tab:
			continue
		var g := _subgroup(sid)
		if _cat_tab != "all" and _sub_tab != "" and String(g[1]) != _sub_tab:
			continue
		if needle != "" and not needle in ItemDb.item_name(sid).to_lower() and not needle in String(ItemDb.item(sid).get("short", "")).to_lower():
			continue
		var cat_rank := 0
		for ti in CAT_TABS.size():
			if String(CAT_TABS[ti][0]) == cat:
				cat_rank = ti
		rows.append({"id": sid, "cat": cat, "cat_rank": cat_rank, "g_rank": int(g[0]), "g": String(g[1]), "i": i, "price": Profile.buy_price(sid)})
	var by_price := _shop_sort
	rows.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		if a.cat_rank != b.cat_rank:
			return int(a.cat_rank) < int(b.cat_rank)
		if a.g_rank != b.g_rank:
			return int(a.g_rank) < int(b.g_rank)
		if a.g != b.g:
			return String(a.g) < String(b.g)
		if by_price != "" and a.price != b.price:
			return int(a.price) < int(b.price) if by_price == "up" else int(a.price) > int(b.price)
		return int(a.i) < int(b.i))
	return rows


## Строка списка: снимок, имя, подпись (закрытое — со ступени N), цена; клик — выбрать.
func _shop_row(sid: String) -> ItemCard:
	var tl := maxi(TraderStock.catalog_of(sid), 1)
	var locked := _trust_blocked(sid, tl)
	var sub := "откроется со ступени %d" % TraderStock.step_of(tl) if locked else _sub_of(sid)
	var row := ItemCard.row({"id": sid, "n": 1}, sub, "%s ₽" % InventoryUI.money(Profile.buy_price(sid)), sid == _sel, locked)
	row.gui_input.connect(func(ev: InputEvent) -> void:
		var mb := ev as InputEventMouseButton
		if mb and mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT:
			_select(sid))
	return row


## Выбрать предмет: список (подсветка), витрина и подробности — без перестройки окна (поиск не теряет курсор).
func _select(sid: String) -> void:
	if sid == _sel:
		return
	_sel = sid
	Audio.play_ui("ui_click")
	var scroll := _shop_list.get_parent() as ScrollContainer if _shop_list and is_instance_valid(_shop_list) else null
	var at: int = scroll.scroll_vertical if scroll else 0
	_fill_shop(true)
	if scroll:
		scroll.set_deferred("scroll_vertical", at)
	_fill_showcase()


## Витрина (большой снимок и что подходит) и подробности выбранного.
func _fill_showcase() -> void:
	if _shop_center == null or not is_instance_valid(_shop_center) or _sel == "":
		return
	for c in _shop_center.get_children():
		_shop_center.remove_child(c)
		c.queue_free()
	var stage := PanelContainer.new()
	stage.size_flags_vertical = Control.SIZE_EXPAND_FILL
	stage.add_theme_stylebox_override("panel", LightUi.box(LightUi.STAGE, 8, 0))
	_shop_center.add_child(stage)
	var shot := ItemCard.IconBox.new()
	shot.id = _sel
	shot.entry = {"id": _sel, "n": 1}
	shot.studio = true
	shot.light = true
	shot.pad = 34.0
	shot.frame = SHOWCASE_FRAME
	shot.urgent = true
	shot.size_flags_vertical = Control.SIZE_EXPAND_FILL
	shot.custom_minimum_size.y = 200
	stage.add_child(shot)
	var fits := _fits_of(_sel)
	if not fits.is_empty():
		_shop_center.add_child(LightUi.caps("подходит к нему" if WeaponDb.is_weapon(_sel) else "к чему подходит", 13))
		var grid := GridContainer.new()
		grid.columns = 3
		grid.add_theme_constant_override("h_separation", 12)
		grid.add_theme_constant_override("v_separation", 12)
		_shop_center.add_child(grid)
		for fid: String in fits:
			grid.add_child(_fit_tile(fid))
	_fill_detail()


## Кадр большого снимка на витрине (пропорции витрины ~2,4 : 1).
const SHOWCASE_FRAME := Vector2i(1280, 536)
## Сколько показывать «что подходит».
const SHOWCASE_FITS := 6


## Что подходит к выбранному из того, что продаётся: к стволу — магазины (штатный первым), патроны, обвес;
## к магазину, патрону, обвесу — стволы. Закрытое доверием не показывается.
func _fits_of(sid: String) -> Array:
	var out: Array = []
	var stock := _trader_stock()
	var avail := func(id: String) -> bool: return not _trust_blocked(id, maxi(TraderStock.catalog_of(id), 1))
	if WeaponDb.is_weapon(sid):
		var w := WeaponDb.weapon(sid)
		var first: Array = [String(w.get("default_mag", "")), WeaponDb.default_ammo(String(w.get("caliber", "")))]
		for id: String in first:
			if id in stock and avail.call(id) and _fits(sid, id):
				out.append(id)
		for kind: String in ["mag", "ammo", "mod"]:
			for id in stock:
				var s := String(id)
				if out.size() >= SHOWCASE_FITS:
					return out
				if s in out or _cat_of(s) != kind or not avail.call(s):
					continue
				if _fits(sid, s):
					out.append(s)
		return out
	for id in stock:
		var s := String(id)
		if out.size() >= SHOWCASE_FITS:
			break
		if WeaponDb.is_weapon(s) and avail.call(s) and _fits(s, sid):
			out.append(s)
	return out


## Подходит ли предмет к стволу weapon: патрон — калибр, магазин — шахта, обвес — есть место крепления.
func _fits(weapon: String, sid: String) -> bool:
	if not WeaponDb.ammo(sid).is_empty():
		return WeaponDb.ammo_fits(weapon, sid)
	if not WeaponDb.magazine(sid).is_empty():
		return WeaponDb.mag_fits(weapon, sid)
	if not WeaponDb.attachment(sid).is_empty():
		return not WeaponDb.mounts_for({"id": weapon, "n": 1, "mods": {}}, sid).is_empty()
	return false


## Плитка «подходит»: имя, снимок, цена; клик — выбрать.
func _fit_tile(fid: String) -> Control:
	var tile := PanelContainer.new()
	tile.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tile.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	tile.add_theme_stylebox_override("panel", LightUi.box(LightUi.SURFACE, 6, 10, LightUi.LINE, 1))
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 4)
	v.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tile.add_child(v)
	var name := LightUi.caps(ItemDb.item_name(fid), 13, LightUi.TEXT)
	name.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	name.mouse_filter = Control.MOUSE_FILTER_IGNORE
	v.add_child(name)
	var icon := ItemCard.IconBox.new()
	icon.id = fid
	icon.entry = {"id": fid, "n": 1}
	icon.studio = true
	icon.light = true
	icon.pad = 4.0
	icon.frame = Vector2i(320, 145)
	icon.custom_minimum_size.y = 64
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	v.add_child(icon)
	var price := LightUi.mono("%s ₽" % InventoryUI.money(Profile.buy_price(fid)), 13, LightUi.TEXT2)
	price.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	price.mouse_filter = Control.MOUSE_FILTER_IGNORE
	v.add_child(price)
	tile.gui_input.connect(func(ev: InputEvent) -> void:
		var mb := ev as InputEventMouseButton
		if mb and mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT:
			_select(fid))
	return tile


## Подробности выбранного: что это, характеристики, цена с количеством, купить в рюкзак или в тайник.
func _fill_detail() -> void:
	var d := _shop_detail
	if d == null or not is_instance_valid(d):
		return
	for c in d.get_children():
		d.remove_child(c)
		c.queue_free()
	var sid := _sel
	var it := ItemDb.item(sid)
	var w := WeaponDb.weapon(sid)
	var over := _sub_of(sid) if not w.is_empty() else String(_subgroup(sid)[1])
	d.add_child(LightUi.caps(over, 14, LightUi.ACCENT))
	var title := LightUi.label(ItemDb.item_name(sid), 38, LightUi.TEXT, LightUi.head_font())
	title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	d.add_child(title)
	var about := String(it.get("desc", ""))
	if about == "":
		about = String(it.get("flavor", ""))
	if w.is_empty() and _sub_of(sid) != "":
		about = (_sub_of(sid) + ("\n" + about if about != "" else ""))
	if about != "":
		var al := LightUi.label(about, 14, LightUi.TEXT2)
		al.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		d.add_child(al)
	for r: Array in _detail_stats(sid):
		var row := VBoxContainer.new()
		row.add_theme_constant_override("separation", 4)
		var top := HBoxContainer.new()
		var k := LightUi.caps(String(r[0]), 13, LightUi.TEXT2)
		k.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		top.add_child(k)
		top.add_child(LightUi.mono(String(r[1]), 14))
		row.add_child(top)
		var track := Panel.new()
		track.custom_minimum_size.y = 6
		track.add_theme_stylebox_override("panel", LightUi.box(LightUi.TRACK, 3))
		var fill := Panel.new()
		fill.add_theme_stylebox_override("panel", LightUi.box(LightUi.BAR, 3))
		fill.anchor_bottom = 1.0
		fill.anchor_right = clampf(float(r[2]) / 100.0, 0.0, 1.0)
		track.add_child(fill)
		row.add_child(track)
		d.add_child(row)
	var info := Button.new()
	info.text = "Подробнее"
	info.focus_mode = Control.FOCUS_NONE
	info.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	info.pressed.connect(func() -> void: ItemInfo.open(self, {"id": sid, "n": 1}))
	d.add_child(info)
	var gap := Control.new()
	gap.size_flags_vertical = Control.SIZE_EXPAND_FILL
	d.add_child(gap)
	var stackable := ItemDb.stack(sid) > 1
	var unit := Profile.buy_price(sid)
	var tl := maxi(TraderStock.catalog_of(sid), 1)
	var line := HBoxContainer.new()
	var cat_l := LightUi.caps("каталог «%s»" % TraderStock.catalog_name(tl) if TraderStock.catalog_of(sid) > 0 else "находка", 13)
	cat_l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	cat_l.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	line.add_child(cat_l)
	var price := LightUi.mono("%s ₽" % InventoryUI.money(unit * (_qty_of(sid) if stackable else 1)), 26)
	line.add_child(price)
	d.add_child(line)
	if _trust_blocked(sid, tl):
		var lock := LightUi.caps("откроется со ступени %d" % TraderStock.step_of(tl), 16, LightUi.LOCK)
		d.add_child(lock)
		return
	var buy_bp := LightUi.button("КУПИТЬ В РЮКЗАК", "primary", func() -> void: _buy(sid, "backpack"))
	buy_bp.custom_minimum_size.y = 52
	buy_bp.add_theme_font_size_override("font_size", 19)
	var buy_st := Button.new()
	buy_st.text = "В ТАЙНИК"
	buy_st.focus_mode = Control.FOCUS_NONE
	buy_st.custom_minimum_size.y = 40
	buy_st.add_theme_font_override("font", LightUi.head_font())
	buy_st.add_theme_font_size_override("font_size", 15)
	buy_st.pressed.connect(func() -> void: _buy(sid, "stash"))
	var afford := func() -> void:
		var cost := unit * (_qty_of(sid) if stackable else 1)
		price.text = "%s ₽" % InventoryUI.money(cost)
		buy_bp.disabled = cost > Profile.money
		buy_st.disabled = cost > Profile.money
	if stackable:
		# количество: шаг кнопками (патроны — по 30), любое число — руками в поле
		var qrow := HBoxContainer.new()
		qrow.add_theme_constant_override("separation", 6)
		var field := LineEdit.new()
		field.text = str(_qty_of(sid))
		field.alignment = HORIZONTAL_ALIGNMENT_CENTER
		field.max_length = 4
		field.select_all_on_focus = true
		field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		field.tooltip_text = "Сколько купить — можно набрать число"
		field.add_theme_font_override("font", LightUi.mono_font())
		var step := func(dir: int) -> void:
			_step_qty(sid, dir)
			field.text = str(_qty_of(sid))
			afford.call()
		var minus := Button.new()
		minus.text = "−"
		minus.focus_mode = Control.FOCUS_NONE
		minus.custom_minimum_size.x = 44
		minus.pressed.connect(func() -> void: step.call(-1))
		var plus := Button.new()
		plus.text = "+"
		plus.focus_mode = Control.FOCUS_NONE
		plus.custom_minimum_size.x = 44
		plus.pressed.connect(func() -> void: step.call(1))
		qrow.add_child(minus)
		qrow.add_child(field)
		qrow.add_child(plus)
		field.text_changed.connect(func(t: String) -> void:
			if t.is_valid_int() and int(t) >= 1:
				_qty[sid] = clampi(int(t), 1, _qty_max(sid))
				afford.call())
		field.focus_exited.connect(func() -> void: field.text = str(_qty_of(sid)))
		field.text_submitted.connect(func(_t: String) -> void: field.release_focus())
		d.add_child(qrow)
	d.add_child(buy_bp)
	d.add_child(buy_st)
	afford.call()


## Характеристики в подробностях: [название, значение, полоса 0–100]. Ствол — урон, пробитие, темп,
## эргономика, дальность, вес (как в схеме оружия, WeaponStats); патрон — урон и пробитие; остальное — нет.
func _detail_stats(sid: String) -> Array:
	var out: Array = []
	if WeaponDb.is_weapon(sid):
		var rng := RandomNumberGenerator.new()
		rng.seed = 1
		var e: Dictionary = WeaponDb.bare_weapon(sid, rng, [100, 100])
		var s := WeaponStats.compute(e, WeaponDb.default_ammo(String(WeaponDb.weapon(sid).get("caliber", ""))))
		if s.is_empty():
			return out
		var rows := WeaponStats.rows(s)
		# не боевое (ракетница): урона нет — характеристики стрельбы не показываем
		if float((rows[0] as Array)[1]) <= 0.0:
			return out
		for i: int in [0, 1, 2, 7, 9, 12]:
			var r: Array = rows[i]
			out.append([String(r[0]), String(r[4]) % float(r[1]), float(r[2])])
		return out
	var a := WeaponDb.ammo(sid)
	if not a.is_empty():
		out.append(["Урон", "%d" % int(a.damage), clampf(float(a.damage), 0.0, 100.0)])
		out.append(["Пробитие", "%d" % int(a.pen), clampf(float(a.pen) * 1.6, 0.0, 100.0)])
	return out


## Купить выбранное: в рюкзак (не влезло — в тайник, с сообщением) или в тайник.
func _buy(sid: String, to: String) -> void:
	var q := _qty_of(sid) if ItemDb.stack(sid) > 1 else 1
	var stash_before: int = Profile.stash_count(sid)
	_buy_to = to
	if not Profile.buy(sid, q, to):
		if Profile.buy_price(sid) * q > Profile.money:
			toast("Не хватает денег")
		else:
			toast("Нет места ни в рюкзаке, ни в тайнике" if to == "backpack" else "В тайнике нет места")
		return
	if to == "backpack" and Profile.stash_count(sid) > stash_before:
		toast("Покупка отправлена в тайник: в рюкзаке нет места")
	# купил — количество снова по умолчанию
	_qty.erase(sid)


## Абзац в колонке: переносится по словам (строки, добавленные после общей перестройки окна).
func _wrap(l: Label) -> Label:
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return l


## Комплекты: готовые (Balance.TRADER_KITS) и свои шаблоны карточками по три в строку — полный набор одной
## кнопкой: что есть в тайнике — оттуда, остальное докупается; ниже — сохранить надетое как свой.
func _trader_kits(page: VBoxContainer) -> void:
	var pad := MarginContainer.new()
	pad.size_flags_vertical = Control.SIZE_EXPAND_FILL
	for side: String in ["left", "right"]:
		pad.add_theme_constant_override("margin_" + side, 28)
	pad.add_theme_constant_override("margin_top", 18)
	pad.add_theme_constant_override("margin_bottom", 20)
	page.add_child(pad)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	pad.add_child(scroll)
	var list := VBoxContainer.new()
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.add_theme_constant_override("separation", 12)
	scroll.add_child(list)
	list.add_child(LightUi.caps("готовые комплекты", 14))
	var grid := GridContainer.new()
	grid.columns = 3
	grid.add_theme_constant_override("h_separation", 14)
	grid.add_theme_constant_override("v_separation", 14)
	list.add_child(grid)
	for kit: Dictionary in Balance.TRADER_KITS:
		grid.add_child(_kit_card(kit))
	list.add_child(LightUi.caps("свои комплекты  %d / %d" % [LoadoutTemplates.all().size(), LoadoutTemplates.MAX], 14))
	if not LoadoutTemplates.all().is_empty():
		var own := GridContainer.new()
		own.columns = 3
		own.add_theme_constant_override("h_separation", 14)
		own.add_theme_constant_override("v_separation", 14)
		list.add_child(own)
		for i in range(LoadoutTemplates.all().size()):
			own.add_child(_kit_card(LoadoutTemplates.all()[i], i))
	var hint := LightUi.label("Надень и сложи в рюкзак то, с чем ходишь, — и сохрани: потом соберётся одной кнопкой (что есть в тайнике — оттуда, остальное докупится). То же имя — заменить.", 14, LightUi.MUTED)
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	list.add_child(hint)
	var save_row := HBoxContainer.new()
	save_row.add_theme_constant_override("separation", 10)
	list.add_child(save_row)
	var name_edit := LineEdit.new()
	name_edit.placeholder_text = "Имя комплекта"
	name_edit.max_length = 24
	name_edit.custom_minimum_size = Vector2(320, 40)
	save_row.add_child(name_edit)
	var save := LightUi.button("СОХРАНИТЬ НАДЕТОЕ И РЮКЗАК", "primary", func() -> void:
		if Profile.equipment.is_empty() and Profile.backpack.is_empty():
			toast("Сохранять нечего: ничего не надето и рюкзак пуст")
			return
		var t := LoadoutTemplates.capture(name_edit.text)
		toast("Комплект «%s» сохранён" % String(t.name)))
	save.custom_minimum_size.y = 40
	save_row.add_child(save)


## Карточка комплекта: снимок основного ствола, что в нём, сколько докупить, чего не хватает, «Собрать».
func _kit_card(kit: Dictionary, own_idx: int = -1) -> Control:
	var card := PanelContainer.new()
	card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	card.add_theme_stylebox_override("panel", LightUi.box(LightUi.SURFACE, 8, 14, LightUi.LINE, 1))
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	card.add_child(v)
	var slots: Dictionary = kit.get("slots", {})
	var icon := ItemCard.IconBox.new()
	icon.id = String((slots.get("primary", {}) as Dictionary).get("id", ""))
	icon.entry = (slots.get("primary", {}) as Dictionary).duplicate(true)
	icon.studio = true
	icon.light = true
	icon.plate = LightUi.PLATE
	icon.pad = 14.0
	icon.aspect = ItemCard.BIG_ASPECT
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	v.add_child(icon)
	var head := HBoxContainer.new()
	v.add_child(head)
	var name := LightUi.label(String(kit.name), 24, LightUi.TEXT, LightUi.head_font())
	name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	head.add_child(name)
	if own_idx >= 0:
		var del := Button.new()
		del.text = "Удалить"
		del.focus_mode = Control.FOCUS_NONE
		del.pressed.connect(func() -> void: LoadoutTemplates.remove(own_idx))
		head.add_child(del)
	if String(kit.get("about", "")) != "":
		var about := LightUi.label(String(kit.get("about", "")), 14, LightUi.TEXT2)
		about.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		v.add_child(about)
	# состав одной строкой: стволы, броня, шлем, рюкзак, сколько всего в рюкзаке
	var parts: Array[String] = []
	for slot in ["primary", "secondary", "sidearm", "launcher", "armor", "helmet", "backpack"]:
		if slots.has(slot):
			parts.append(ItemDb.item_name(String((slots[slot] as Dictionary).id)))
			var pouches: Array = (slots[slot] as Dictionary).get("pouches", [])
			if not pouches.is_empty():
				parts.append("подсумков %d" % pouches.size())
	var bp_n := (kit.get("backpack", []) as Array).size()
	if bp_n > 0:
		parts.append("в рюкзаке %d поз." % bp_n)
	var what := LightUi.label(" · ".join(parts), 13, LightUi.MUTED)
	what.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(what)
	var p := LoadoutTemplates.plan(kit)
	var cost := int(p.cost)
	if int(p.missing) > 0:
		var why := ""
		for r in p.rows:
			if String(r.how) == "нет":
				why = String(r.why)
				break
		var miss := LightUi.label("не собрать полностью: %d поз. — %s" % [int(p.missing), why], 13, LightUi.LOCK)
		miss.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		v.add_child(miss)
	var go := LightUi.button("СОБРАТЬ — ВСЁ ЕСТЬ" if cost == 0 and int(p.missing) == 0 else "СОБРАТЬ · ДОКУПИТЬ НА %s ₽" % InventoryUI.money(cost), "primary",
		func() -> void: _confirm_template(kit))
	go.disabled = cost > Profile.money
	go.custom_minimum_size.y = 42
	go.add_theme_font_size_override("font_size", 16)
	if go.disabled:
		go.tooltip_text = "Не хватает денег"
	v.add_child(go)
	return card


## Группы оружия на витрине: название и классы (WeaponDb) в нём.
const WEAPON_GROUPS := [["Пистолеты", ["PISTOL"]], ["Пистолеты-пулемёты", ["SMG", "PDW"]], ["Ружья", ["SHOTGUN"]],
	["Автоматы и карабины", ["ASSAULT_RIFLE", "CARBINE", "SPECIAL"]], ["Марксманские и боевые винтовки", ["BATTLE_RIFLE", "DMR"]],
	["Снайперские винтовки", ["SNIPER"]], ["Пулемёты", ["LMG"]]]
## Калибры по возрастанию: пистолетные, промежуточные, винтовочные, крупные, ружейный.
const CALIBER_ORDER := ["9x18", "9x19", "45acp", "57x28", "9x21", "545x39", "9x39", "556x45", "300blk", "68x51", "762x51", "762x54r",
	"338lm", "50bmg", "12x76"]


## Подгруппа предмета внутри раздела: [порядок, название]. Оружие — по классам, патроны и магазины —
## по калибрам, обвес — по назначению, броня — по виду; так же делятся и находки (чит «лут в продаже»).
func _subgroup(id: String) -> Array:
	var w := WeaponDb.weapon(id)
	if not w.is_empty():
		var cls := String(w["class"])
		for i in WEAPON_GROUPS.size():
			if cls in (WEAPON_GROUPS[i][1] as Array):
				return [i, String(WEAPON_GROUPS[i][0])]
		return [WEAPON_GROUPS.size(), "Прочее оружие"]
	var cal := ""
	if not WeaponDb.ammo(id).is_empty():
		cal = String((WeaponDb.ammo(id) as Dictionary).get("caliber", ""))
	elif not WeaponDb.magazine(id).is_empty():
		cal = WeaponDb.mag_caliber(id)
	if cal != "":
		var ci := CALIBER_ORDER.find(cal)
		return [ci if ci >= 0 else CALIBER_ORDER.size(), WeaponDb.caliber_name(cal)]
	var at := WeaponDb.attachment(id)
	if not at.is_empty():
		var kind := String(at.get("type", ""))
		match WeaponBuilder.tab_of(id):
			"optic":
				return [0, "Прицелы"]
			"muzzle":
				return [2, "Глушители"] if kind == "SUPPRESSOR" else [1, "Дульные устройства"]
			"stock":
				return [5, "Приклады"]
			"adapter":
				return [6, "Кронштейны и планки"]
		if "FLASHLIGHT" in kind or "LASER" in kind:
			return [4, "Фонари и ЛЦУ"]
		return [3, "Рукоятки и сошки"]
	if not WeaponDb.helmet(id).is_empty():
		return [0, "Шлемы"]
	if not WeaponDb.vest(id).is_empty():
		return [1, "Бронежилеты и плитоносцы"]
	if not WeaponDb.plate(id).is_empty():
		return [2, "Бронеплиты"]
	if not WeaponDb.headset(id).is_empty():
		return [3, "Гарнитуры"]
	if ItemDb.item(id).has("pouch") or ItemDb.item(id).has("rig"):
		return [4, "Подсумки"]
	var cat := String(ItemDb.item(id).get("cat", "misc"))
	if cat == "backpack":
		return [5, "Рюкзаки"]
	var order := ["med", "food", "throw", "tools", "tech", "barter", "value"]
	var oi := order.find(cat)
	return [oi if oi >= 0 else order.size(), String(ItemInfo.CAT_NAMES.get(cat, "Разное"))]


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
	# после «Фирменного знака» Михалыч продаёт плёнку для наклеек
	if Stickers.printer_ready() and not String(Balance.STICKERS.film) in stock:
		stock.append(String(Balance.STICKERS.film))
	if Settings.shop_all() or Settings.shop_loot:
		for id in ItemDb.all_ids():
			var cat := String(ItemDb.item(String(id)).get("cat", "misc"))
			if id in stock or cat in ["key", "intel"] or ItemDb.value(String(id)) <= 0:
				continue
			# находки из рейда (головка станка, сигнал самолёта, ценности) — отдельным читом
			if Settings.shop_loot if ItemDb.loot_only(String(id)) else Settings.shop_all():
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
	if Settings.shop_all():
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


## Сколько брать расходника: патроны — шагом Balance.TRADER_AMMO_STEP (магазин), остальное — поштучно;
## любое число — руками в поле между «−» и «+».
func _qty_step(sid: String) -> int:
	return Balance.TRADER_AMMO_STEP if String(ItemDb.item(sid).cat) == "ammo" else 1


func _qty_max(sid: String) -> int:
	return mini(ItemDb.stack(sid) * Balance.TRADER_QTY_STACKS, 999)


func _qty_of(sid: String) -> int:
	var step := _qty_step(sid)
	return int(_qty.get(sid, step))


## «+» — до следующего кратного шагу (30 → 60, набранные 45 → 60), «−» — до предыдущего, не ниже шага.
func _step_qty(sid: String, dir: int) -> void:
	var step := _qty_step(sid)
	var n := _qty_of(sid)
	var next := (n / step + 1) * step if dir > 0 else ((n - 1) / step) * step
	if next < 1:
		next = mini(n, step)
	_qty[sid] = clampi(next, 1, _qty_max(sid))


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
		return "плиты: %s · мест под подсумки %d" % ["спереди и сзади" if not (v.get("plates", []) as Array).is_empty() else "нет", int(v.get("places", 0))]
	var pouch: Dictionary = ItemDb.item(id).get("pouch", {})
	if not pouch.is_empty():
		var kinds := {"rifle": "автоматные", "pistol": "пистолетные", "big": "крупные"}
		return "мест %s · магазины %s" % [str(float(pouch.places)).replace(".5", "½").replace(".0", ""), String(kinds.get(String(pouch.mags), ""))]
	var rig: Dictionary = ItemDb.item(id).get("rig", {})
	if not rig.is_empty():
		return "старая разгрузка: станет подсумками (%d)" % int(rig.pouches)
	# остальное — вид предмета; подробно — по «i»
	return String(ItemInfo.CAT_NAMES.get(String(ItemDb.item(id).get("cat", "misc")), ""))


## Обвес оружия: выбрать своё оружие (надетое, в тайнике, в рюкзаке) и собрать его на схеме —
## купить у Михалыча и сразу поставить или поставить своё из наличия.
func _trader_mods() -> void:
	var pick := _column("Своё оружие", 0.55)
	var ref := _weapon_ref()
	var any := false
	for src in ItemDb.WEAPON_SLOTS.map(func(s: String) -> Array: return ["equip:" + s, Profile.equipment.get(s, {})]):
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
	_builder_card(col, weapon, String(ref[0]), int(ref[1]), "shop")
	var spec := WeaponStats.compute(weapon)
	var ads_deg: float = WeaponStats.ads_spread_deg(spec)
	col.add_child(_text("Разброс в прицеле %s · отдача %.3f · эргономика %d · шум %d м · %.1f кг" % [
		"нет" if ads_deg <= 0.0 else "%.2f°" % ads_deg, float(spec.kick), int(spec.ergo), int(spec.noise_m), float(spec.weight)], Color(0.8, 0.82, 0.78)))
	col.add_child(_text("Клик по квадратику у точки крепления: купить у Михалыча и сразу поставить или поставить своё. Снятое — в тайник.", Color(0.6, 0.62, 0.6)))


## Сборка оружия крупно (миниатюра экземпляра) и вход в конструктор.
func _builder_card(parent: Control, weapon: Dictionary, where: String, idx: int, source: String) -> void:
	var icon := ItemCard.IconBox.new()
	icon.id = String(weapon.get("id", ""))
	icon.entry = weapon
	icon.custom_minimum_size = Vector2(0, 220)
	parent.add_child(icon)
	var open := _button("Открыть конструктор оружия", func() -> void: open_builder(where, idx, source))
	open.custom_minimum_size.y = 44
	open.add_theme_font_size_override("font_size", 18)
	parent.add_child(open)


## Конструктор поверх окна убежища; source — "mine" (свои вещи) или "shop" (у Михалыча).
func open_builder(where: String, idx: int, source: String = "mine") -> void:
	var b := WeaponBuilder.open_hideout(_root, where, idx)
	b._source = source
	b._refresh()


func _weapon_pick_card(parent: Control, e: Dictionary, where: String, chosen: bool, pick: Callable) -> void:
	var card := ItemCard.make(e, where, "", 260.0)
	if chosen:
		card.controls.add_child(_text("▶ на схеме", Color(1.0, 0.86, 0.6)))
		card.mark(1)
	else:
		# выбрать — клик в любое место карточки (кнопка оставлена для привычки)
		card.controls.add_child(_button("Выбрать", pick))
		_clickable(card, pick)
	parent.add_child(card)


## Вся плашка — как кнопка: «рука», подсветка под курсором, клик в любое место (кроме её же кнопок).
func _clickable(card: Control, action: Callable) -> void:
	card.mouse_filter = Control.MOUSE_FILTER_STOP
	card.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	for n in card.find_children("*", "Control", true, false):
		var c := n as Control
		if not c is BaseButton and c.mouse_filter == Control.MOUSE_FILTER_STOP:
			c.mouse_filter = Control.MOUSE_FILTER_PASS
	card.mouse_entered.connect(func() -> void: card.self_modulate = Color(1.35, 1.3, 1.2))
	card.mouse_exited.connect(func() -> void: card.self_modulate = Color(1, 1, 1))
	card.gui_input.connect(func(ev: InputEvent) -> void:
		var mb := ev as InputEventMouseButton
		if mb and mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT:
			card.accept_event()
			action.call())


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
	for slot in ItemDb.WEAPON_SLOTS:
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


## Продать: тайник и рюкзак (с карманом) — рядом, сетками, как они лежат; пустой низ тайника не
## показывается. Клик — отметить предмет к продаже (ещё клик — снять отметку), отмечать можно сколько
## угодно; справа — отмеченное, общая цена и «Продать выбранное». У последнего отмеченного ствола
## подсвечены его магазины и патроны, у магазина — стволы и патроны к нему, у патронов — стволы и
## магазины. Надетые стволы — кнопками справа (только подсветка припасов).
func _trader_sell() -> void:
	var focus := _sell_focus_entry()
	# отметки, которых уже нет (продали, список стал короче), — убрать
	_sell_picks = _sell_picks.filter(func(p: Variant) -> bool:
		return int((p as Array)[1]) >= 0 and int((p as Array)[1]) < Profile.list_of(String((p as Array)[0])).size())
	var any := false
	var stash_col := _column("Тайник", 1.0)
	var bag_col := _column("Рюкзак", 0.72)
	for src in [["stash", "Тайник", stash_col], ["backpack", "Рюкзак", bag_col], ["pocket", "Защищённый карман", bag_col]]:
		var from := String(src[0])
		var list := Profile.list_of(from)
		var col := src[2] as VBoxContainer
		if list.is_empty():
			if from != "pocket":
				col.add_child(_text("Пусто.", Color(0.6, 0.6, 0.6)))
			continue
		any = true
		var total := 0
		for e in list:
			total += Profile.sell_price(e)
		var head := HBoxContainer.new()
		head.add_theme_constant_override("separation", 8)
		var caption := _text("%sвсё вместе %s ₽" % ["Карман · " if from == "pocket" else "", InventoryUI.money(total)], Color(0.95, 0.82, 0.6))
		caption.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		head.add_child(caption)
		var all_picked := true
		for i in range(list.size()):
			all_picked = all_picked and [from, i] in _sell_picks
		head.add_child(_button("Снять все" if all_picked else "Отметить все", func() -> void:
			_sell_picks = _sell_picks.filter(func(p: Variant) -> bool: return String((p as Array)[0]) != from)
			if not all_picked:
				for i in range(Profile.list_of(from).size()):
					_sell_picks.append([from, i])
			_sell_sel = []))
		col.add_child(head)
		# тайник — только занятые ряды (и один свободный): без пустого полотна на тридцать рядов
		var grid := Profile.grid_of(from)
		if from == "stash":
			var rows := 1
			for e in list:
				var sz := ItemDb.size(String(e.id))
				rows = maxi(rows, int(e.get("y", 0)) + (sz.x if bool(e.get("r", false)) else sz.y) + 1)
			grid = Vector2i(grid.x, mini(grid.y, rows))
		var view := GridView.new(grid, from)
		view.drag_enabled = false
		view.set_items(list)
		for p in _sell_picks:
			if String((p as Array)[0]) == from:
				view.picked[int((p as Array)[1])] = true
		if not focus.is_empty():
			for i in range(list.size()):
				var c := _sell_mark(focus, list[i])
				if c.a > 0.0:
					view.marks[i] = c
		view.clicked.connect(func(idx: int) -> void:
			var key := [from, idx]
			if key in _sell_picks:
				_sell_picks.erase(key)
				_sell_sel = (_sell_picks[-1] as Array).duplicate() if not _sell_picks.is_empty() else []
			else:
				_sell_picks.append(key)
				_sell_sel = key.duplicate())
		view.context.connect(func(idx: int, _at: Vector2) -> void: ItemInfo.open(self, (Profile.list_of(from)[idx] as Dictionary).duplicate(true)))
		col.add_child(view)
	# справа — отмеченное: что, сколько стоит, продать разом
	var side := _column("К продаже", 0.8)
	var picked_total := 0
	for p in _sell_picks:
		picked_total += Profile.sell_price(Profile.list_of(String((p as Array)[0]))[int((p as Array)[1])])
	if _sell_picks.is_empty():
		side.add_child(_text("Кликай предметы в сетках — они отмечаются к продаже (ещё клик — снять отметку). Отметить можно сколько угодно и продать разом.
Правая кнопка — описание." if any else "Продавать нечего: тайник и рюкзак пусты.", Color(0.6, 0.62, 0.6)))
	else:
		var sell_all := _button("Продать выбранное: %d — %s ₽" % [_sell_picks.size(), InventoryUI.money(picked_total)], func() -> void:
			var got := Profile.sell_many(_sell_picks)
			_sell_picks = []
			_sell_sel = []
			if got > 0:
				toast("Продано на %s ₽" % InventoryUI.money(got)))
		sell_all.custom_minimum_size.y = 40
		sell_all.add_theme_font_size_override("font_size", 16)
		side.add_child(sell_all)
		side.add_child(_button("Снять отметки", func() -> void:
			_sell_picks = []
			_sell_sel = []))
		if _sell_picks.size() == 1:
			var from_one := String(_sell_picks[0][0])
			var idx_one := int(_sell_picks[0][1])
			var one: Dictionary = Profile.list_of(from_one)[idx_one]
			var card := ItemCard.make(one, _sub_of(String(one.id)), "%s ₽" % InventoryUI.money(Profile.sell_price(one)), 260.0)
			if int(one.n) > 1:
				card.controls.add_child(_button("Продать 1 шт.", func() -> void: Profile.sell(idx_one, 1, from_one)))
			side.add_child(card)
		else:
			for p in _sell_picks:
				var e: Dictionary = Profile.list_of(String((p as Array)[0]))[int((p as Array)[1])]
				var row := HBoxContainer.new()
				row.add_theme_constant_override("separation", 8)
				var name := _text(ItemDb.item_name(String(e.id)) + ("  ×%d" % int(e.n) if int(e.n) > 1 else ""), Color(0.9, 0.88, 0.82))
				name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
				name.clip_text = true
				row.add_child(name)
				row.add_child(_text("%s ₽" % InventoryUI.money(Profile.sell_price(e)), Color(0.7, 0.9, 0.6)))
				side.add_child(row)
	# надетое оружие отсюда не продаётся, но к нему можно подсветить припасы
	var worn_any := false
	for slot in ItemDb.WEAPON_SLOTS:
		var e: Dictionary = Profile.equipment.get(slot, {})
		if e.is_empty():
			continue
		if not worn_any:
			side.add_child(_text("Подсветить магазины и патроны к надетому:", Color(0.6, 0.62, 0.6)))
			worn_any = true
		var key: String = "equip:" + String(slot)
		var b := _button("%s: %s" % [Inventory.SLOT_NAMES[slot], ItemDb.item_name(String(e.id))], func() -> void:
			_sell_sel = [] if _sell_sel == [key, -1] else [key, -1])
		b.toggle_mode = true
		b.button_pressed = _sell_sel == [key, -1]
		side.add_child(b)
	if not focus.is_empty() and (WeaponDb.is_weapon(String(focus.id)) or not WeaponDb.magazine(String(focus.id)).is_empty() or not WeaponDb.ammo(String(focus.id)).is_empty()):
		for l in [["оружие", SELL_MARK_WEAPON], ["магазины", SELL_MARK_MAG], ["патроны", SELL_MARK_AMMO]]:
			var row := HBoxContainer.new()
			row.add_theme_constant_override("separation", 6)
			var sw := ColorRect.new()
			sw.color = l[1] as Color
			sw.custom_minimum_size = Vector2(14, 14)
			sw.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			row.add_child(sw)
			row.add_child(_text("подходит: " + String(l[0]), Color(0.75, 0.75, 0.72)))
			side.add_child(row)


const SELL_MARK_WEAPON := Color(1.0, 0.78, 0.3)
const SELL_MARK_MAG := Color(0.4, 0.75, 1.0)
const SELL_MARK_AMMO := Color(0.45, 0.95, 0.45)


## Выбранное во вкладке «Продать» (запись) или {} — выбор пропал (продали, сдвинулось).
func _sell_focus_entry() -> Dictionary:
	if _sell_sel.size() != 2:
		return {}
	var where := String(_sell_sel[0])
	if where.begins_with("equip:"):
		return Profile.equipment.get(where.trim_prefix("equip:"), {})
	var list := Profile.list_of(where)
	var i := int(_sell_sel[1])
	if i < 0 or i >= list.size():
		_sell_sel = []
		return {}
	return list[i]


## Цвет подсветки записи e к выбранному focus (прозрачный — не подходит): ствол ↔ магазин ↔ патрон.
func _sell_mark(focus: Dictionary, e: Dictionary) -> Color:
	var f := String(focus.id)
	var id := String(e.id)
	var none := Color(0, 0, 0, 0)
	if WeaponDb.is_weapon(f):
		if not WeaponDb.magazine(id).is_empty() and WeaponDb.mag_fits(f, id):
			return SELL_MARK_MAG
		if not WeaponDb.ammo(id).is_empty() and WeaponDb.ammo_fits(f, id):
			return SELL_MARK_AMMO
	elif not WeaponDb.magazine(f).is_empty():
		if WeaponDb.is_weapon(id) and WeaponDb.mag_fits(id, f):
			return SELL_MARK_WEAPON
		if not WeaponDb.ammo(id).is_empty() and String(WeaponDb.ammo(id).get("caliber", "")) == WeaponDb.mag_caliber(f):
			return SELL_MARK_AMMO
	elif not WeaponDb.ammo(f).is_empty():
		if WeaponDb.is_weapon(id) and WeaponDb.ammo_fits(id, f):
			return SELL_MARK_WEAPON
		if not WeaponDb.magazine(id).is_empty() and String(WeaponDb.ammo(f).get("caliber", "")) == WeaponDb.mag_caliber(id):
			return SELL_MARK_MAG
	return none


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
	_title.text = "Модули убежища   ·   %s ₽   ·   доверие Михалыча: ступень %d (каталог %d)%s" % [InventoryUI.money(Profile.money), Profile.trust_step(), Profile.trust_level(),
		"   ·   ЧИТ: всё открыто" if Settings.unlocked() else ""]
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
	_title.text = "План рейда"
	var col := _column("С собой", 1.0)
	for slot in Inventory.SLOTS:
		var e: Dictionary = Profile.equipment.get(slot, {})
		col.add_child(_text("%s:  %s" % [Inventory.SLOT_NAMES[slot], ItemDb.label(e) if not e.is_empty() else "—"], Color(0.85, 0.85, 0.82)))
	col.add_child(_text("Рюкзак: %d / %d ячеек, продажа %s ₽" % [Profile.backpack_cells(), Profile.backpack_capacity(), InventoryUI.money(Profile.sell_value_of(Profile.backpack))], Color(0.85, 0.85, 0.82)))
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
	# в рейд выходят пешком: здесь план только принимают, а начинается рейд у ворот во дворе, когда
	# все, кто в убежище, встанут в зону сбора (HideoutLevel._tick_raid_start)
	var level: Node = get_tree().get_first_node_in_group("hideout_level")
	var accepted: bool = level != null and bool(level.get("raid_plan_accepted"))
	if Net.is_networked() and not Net.is_host():
		go.add_child(_wrapped("План рейда принимает хост. Идёте по его маршруту и в его условия." if not accepted
			else "Хост принял план. К воротам во дворе — рейд начнётся, когда все встанут в зону сбора.", Color(0.9, 0.8, 0.6)))
	elif accepted:
		go.add_child(_wrapped("План принят. Дверь тамбура, коридор, лестница — и к воротам во дворе. Рейд начнётся, когда все, кто в убежище, встанут в зону сбора.", Color(0.75, 1.0, 0.75)))
		go.add_child(_button("Отменить план", func() -> void:
			level.call("accept_raid_plan", false)
			_sig = ""))
	else:
		var accept := _button("Принять план (%d в сети)" % Net.player_names.size() if Net.is_networked() else "Принять план", func() -> void:
			_confirm_raid(func() -> void:
				if level:
					level.call("accept_raid_plan", true)
				close_ui()))
		accept.name = "AcceptRaidPlan"
		accept.custom_minimum_size.y = 40
		accept.disabled = block != "" or level == null
		accept.add_theme_stylebox_override("normal", UiTheme.face(Color(0.5, 0.36, 0.14), Color(1.0, 0.8, 0.45), 2))
		accept.add_theme_stylebox_override("hover", UiTheme.face(Color(0.62, 0.45, 0.18), Color(1.0, 0.9, 0.65), 2))
		accept.add_theme_stylebox_override("pressed", UiTheme.face(Color(0.4, 0.28, 0.1), Color(1.0, 0.8, 0.45), 0))
		go.add_child(accept)
		go.add_child(_wrapped("После этого — пешком: дверь тамбура, коридор, лестница, ворота во дворе.", Color(0.7, 0.72, 0.7)))
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
	d.dialog_text = "С собой нет:\n\n· " + "\n· ".join(gaps) + "\n\nВсё равно идти в рейд?"
	d.ok_button_text = "Принять план"
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
			Net.change_scene(Balance.HIDEOUT_SCENE, "Возвращение в своё убежище")))
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
			Net.change_scene(Balance.HIDEOUT_SCENE, "Загрузка общего убежища")))
	col.add_child(_button("Подключиться по IP", func() -> void:
		remember.call()
		var err := Net.join(ip.text, nick.text)
		if err != "":
			status.text = err
			return
		status.text = "Подключаюсь…"
		Net.joined.connect(func() -> void: Net.change_scene(Balance.HIDEOUT_SCENE, "Загрузка общего убежища"), CONNECT_ONE_SHOT)
		Net.join_failed.connect(func() -> void: status.text = "Не удалось подключиться", CONNECT_ONE_SHOT)))
	col.add_child(status)


## Условия рейда: время, погода, электричество — выбор; риск, награда за него и что взять с собой.
func _conditions_column() -> void:
	var col := _column("Условия рейда", 1.0)
	var c := RaidConditions.normalized(Profile.next_conditions)
	if Net.is_networked() and not Net.is_host() and not Net.host_conditions.is_empty():
		# в коопе в рейд идут с условиями хоста — его выбор и за окнами
		col.add_child(_text("В коопе условия выбирает хост: %s" % RaidConditions.title(RaidConditions.next_shared()), Color(1.0, 0.8, 0.5)))
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
	_title.text = "Верстак — обвесы и ремонт"
	if _wb_mode == "stickers":
		_title.text = "Верстак — наклейки"
		var page := VBoxContainer.new()
		page.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		page.size_flags_vertical = Control.SIZE_EXPAND_FILL
		page.add_theme_constant_override("separation", 8)
		_cols.add_child(page)
		_workbench_modes(page)
		page.add_child(StickerPanel.new())
		_sig = "stickers"
		return
	if not Profile.equipment.has(_wb_slot):
		_wb_slot = "primary"
		for ws: String in ItemDb.WEAPON_SLOTS:
			if Profile.equipment.has(ws):
				_wb_slot = ws
				break
	var left := VBoxContainer.new()
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.add_theme_constant_override("separation", 8)
	_cols.add_child(left)
	_workbench_modes(left)
	var tabs := HBoxContainer.new()
	left.add_child(tabs)
	for ws in ItemDb.WEAPON_SLOTS:
		var e: Dictionary = Profile.equipment.get(ws, {})
		var b := _button("%s: %s" % [Inventory.SLOT_NAMES[ws], ItemDb.item_name(String(e.id)) if not e.is_empty() else "—"], func() -> void: _wb_slot = ws)
		b.disabled = e.is_empty()
		b.toggle_mode = true
		b.button_pressed = ws == _wb_slot
		tabs.add_child(b)
	var weapon: Dictionary = Profile.equipment.get(_wb_slot, {})
	if weapon.is_empty():
		left.add_child(_wrapped("Надень оружие в тайнике — обвесы ставятся на надетое.", Color(1.0, 0.7, 0.5)))
		_build_repairs()
		return
	var wid := String(weapon.id)
	# схема: от точек крепления — квадратики; клик — что подходит из тайника и рюкзака
	_builder_card(left, weapon, "equip:" + _wb_slot, -1, "mine")
	# карточка: калибр, состояние, магазин и патрон, вес
	var spec := WeaponStats.compute(weapon)
	var mag: Dictionary = weapon.get("mag", {}) if weapon.get("mag") is Dictionary else {}
	var w := WeaponDb.weapon(wid)
	left.add_child(_wrapped("%s · %s · %s · состояние %d%% · %.1f кг" % [String(WeaponDb.CLASS_NAMES.get(String(w["class"]), "")), WeaponDb.caliber_name(String(w.caliber)),
		"встроенный магазин" if w.has("internal_mag") else ItemDb.item_name(String(mag.get("id", ""))) if String(mag.get("id", "")) != "" else "без магазина",
		int(weapon.get("dur", 100)), float(spec.weight)], Color(0.85, 0.85, 0.8)))
	# сколько внутри — не видно: полный / пустой (проверка — в рейде, держать R)
	var loaded := "пустой" if int(mag.get("rounds", 0)) <= 0 else ("полный" if int(mag.get("rounds", 0)) >= int(spec.mag) else "не пустой")
	left.add_child(_wrapped("Магазин на %d — %s · %s — урон %d, пробитие %d" % [int(spec.mag), loaded, ItemDb.item_name(String(spec.ammo)), int(spec.damage), int(spec.pen)], Color(0.8, 0.85, 0.75)))
	left.add_child(_wrapped("Клик по квадратику у точки крепления — поставить или снять.", Color(0.6, 0.62, 0.6)))
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
	_build_repairs()


## Переключатель страниц верстака: обвесы и ремонт / наклейки.
func _workbench_modes(parent: Container) -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	parent.add_child(row)
	for pair: Array in [["build", "Обвесы и ремонт"], ["stickers", "Наклейки"]]:
		var mode: String = pair[0]
		var b := _button(String(pair[1]), func() -> void:
			_wb_mode = mode
			_sig = "")
		b.toggle_mode = true
		b.button_pressed = _wb_mode == mode
		b.custom_minimum_size.y = 32
		row.add_child(b)


## Ремонт — своя колонка верстака: всё изношенное из снаряжения, тайника и рюкзака плашками, сразу
## целиком (раньше — строки в окошке на три строки, его приходилось листать). Оружие, следом его обвесы;
## чинится по одной плашке или всё разом.
func _build_repairs() -> void:
	var jobs: Array[Dictionary] = _repair_jobs()
	var total: int = 0
	for job: Dictionary in jobs:
		total += int(job.cost)
	var box := VBoxContainer.new()
	box.name = "Repairs"
	box.custom_minimum_size.x = 470
	box.add_theme_constant_override("separation", 6)
	_cols.add_child(box)
	var title := _text("Ремонт до 100%" if jobs.is_empty() else "Ремонт до 100%% · %d шт." % jobs.size(), Color(0.95, 0.82, 0.6))
	title.add_theme_font_size_override("font_size", 18)
	box.add_child(title)
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 10)
	box.add_child(head)
	var money := _text("Деньги: %s ₽" % InventoryUI.money(Profile.money), Color(0.72, 0.87, 0.66))
	money.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(money)
	if jobs.is_empty():
		box.add_child(_wrapped("Чинить нечего: оружие и обвесы в порядке.", Color(0.6, 0.62, 0.6)))
		return
	if jobs.size() > 1:
		var all := _button("Починить всё · %s ₽" % InventoryUI.money(total), _repair_all)
		all.name = "RepairAll"
		all.custom_minimum_size.y = 34
		all.disabled = Profile.money < total
		all.tooltip_text = "Не хватает %s ₽" % InventoryUI.money(total - Profile.money) if all.disabled else "Восстановить всё до 100%"
		all.add_theme_stylebox_override("normal", UiTheme.face(Color(0.5, 0.36, 0.14), Color(1.0, 0.8, 0.45), 2))
		all.add_theme_stylebox_override("hover", UiTheme.face(Color(0.62, 0.45, 0.18), Color(1.0, 0.9, 0.65), 2))
		all.add_theme_stylebox_override("pressed", UiTheme.face(Color(0.4, 0.28, 0.1), Color(1.0, 0.8, 0.45), 0))
		head.add_child(all)
	# листать приходится, только если плашек больше, чем влезает в высоту окна
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	box.add_child(scroll)
	var list := VBoxContainer.new()
	list.name = "Plates"
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.add_theme_constant_override("separation", 4)
	scroll.add_child(list)
	for job: Dictionary in jobs:
		list.add_child(_repair_plate(job))


## Что можно починить: {where, idx, mount, entry, cost, place, host} — host: оружие, на котором стоит
## обвес ("" — сам предмет). Надетое — первым.
func _repair_jobs() -> Array[Dictionary]:
	var sources: Array = []
	for slot: String in ItemDb.WEAPON_SLOTS:
		var worn: Dictionary = Profile.equipment.get(slot, {})
		if not worn.is_empty():
			sources.append(["equip:" + slot, -1, worn, "надето"])
	for where: String in ["stash", "backpack"]:
		var items: Array = Profile.list_of(where)
		for idx: int in range(items.size()):
			if WeaponCondition.supported(String(items[idx].id)):
				sources.append([where, idx, items[idx], "тайник" if where == "stash" else "рюкзак"])
	var jobs: Array[Dictionary] = []
	for src: Array in sources:
		var entry: Dictionary = src[2]
		var parts: Array = [["", entry]]
		for raw_mount: Variant in entry.get("mods", {}):
			parts.append([String(raw_mount), WeaponCondition.mod_entry(entry.mods[raw_mount])])
		for part: Array in parts:
			var cost: int = WeaponCondition.repair_price(part[1])
			if cost > 0:
				jobs.append({"where": String(src[0]), "idx": int(src[1]), "mount": String(part[0]), "entry": part[1], "cost": cost,
					"place": String(src[3]), "host": ItemDb.item_name(String(entry.id)) if String(part[0]) != "" else ""})
	return jobs


func _repair_all() -> void:
	for job: Dictionary in _repair_jobs():
		Profile.repair_part(String(job.where), int(job.idx), String(job.mount))
	Audio.play_ui("tac_click")


## Плашка ремонта: иконка, имя, состояние и где лежит, кнопка с ценой.
func _repair_plate(job: Dictionary) -> PanelContainer:
	var entry: Dictionary = job.entry
	var plate := PanelContainer.new()
	plate.set_meta("repair_job", job)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.11, 0.105, 0.1, 0.96)
	sb.border_color = Color(0.95, 0.78, 0.5, 0.18)
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(3)
	sb.set_content_margin_all(6)
	plate.add_theme_stylebox_override("panel", sb)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	plate.add_child(row)
	var icon := ItemCard.IconBox.new()
	icon.id = String(entry.id)
	icon.entry = entry
	icon.custom_minimum_size = Vector2(76, 46)
	row.add_child(icon)
	var texts := VBoxContainer.new()
	texts.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	texts.add_theme_constant_override("separation", 0)
	texts.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_child(texts)
	var name := _text(ItemDb.item_name(String(entry.id)), Color(0.93, 0.91, 0.86))
	name.add_theme_font_size_override("font_size", 15)
	# обрезаемая подпись сама высоты не просит — задаём (иначе строка схлопывается в 1 px)
	name.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	name.custom_minimum_size.y = 22
	texts.add_child(name)
	var state := "СЛОМАНО" if WeaponCondition.broken(entry) else "%d%%" % int(WeaponCondition.percent(entry))
	var tone := Color(1.0, 0.45, 0.38)
	if not WeaponCondition.broken(entry):
		tone = Color(1.0, 0.66, 0.36) if WeaponCondition.stage(entry) == int(Balance.CONDITION.worn) else Color(0.9, 0.84, 0.55)
	var where := String(job.place) + (" · на %s" % String(job.host) if String(job.host) != "" else "")
	var sub := _text("%s · %s" % [state, where], tone)
	sub.add_theme_font_size_override("font_size", 13)
	sub.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	sub.custom_minimum_size.y = 19
	texts.add_child(sub)
	var cost: int = int(job.cost)
	var fix := _button("Починить · %s ₽" % InventoryUI.money(cost), func() -> void:
		Profile.repair_part(String(job.where), int(job.idx), String(job.mount)))
	fix.custom_minimum_size = Vector2(150, 0)
	fix.disabled = Profile.money < cost
	fix.tooltip_text = "Не хватает денег" if fix.disabled else "Восстановить состояние до 100%"
	row.add_child(fix)
	return plate


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
			out.append({"id": id, "sub": "%s · %d%% · %s" % ["тайник" if sn == "stash" else "рюкзак", int(WeaponCondition.percent(src[i])), _fx_text(WeaponDb.attachment(id))],
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
			# через прицел пуля идёт без разброса — прицел сужает только сноп дроби
			var fx_name: String = "разброс дроби в прицеле" if k == "ads_spread" and Balance.ADS_SPREAD_K <= 0.0 else String(FX_NAMES[k])
			parts.append("%s %+d%%" % [fx_name, int(round((float(v) - 1.0) * 100.0))])
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


## Текст с переносом строк: длинная строка не распирает колонку.
func _wrapped(t: String, color: Color) -> Label:
	var l := _text(t, color)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return l


func _button(t: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = t
	b.focus_mode = Control.FOCUS_NONE
	b.add_theme_font_size_override("font_size", 14)
	b.pressed.connect(cb)
	return b
