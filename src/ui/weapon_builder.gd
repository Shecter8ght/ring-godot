class_name WeaponBuilder
extends Control
## Конструктор оружия: фактическая сборка конкретного экземпляра в 3D. В центре — модель (вращать,
## приближать, виды «сбоку / сверху / из глаза»); на ней точки креплений, от них линии к карточкам
## (что стоит или «пусто»). Слева — дерево сборки (оружие → планка → кронштейн → прицел) и действия
## с выбранной деталью, справа — характеристики «было → стало» (наведение на деталь — «стало бы»),
## снизу — детали по вкладкам из своих вещей и у торговца. Деталь на планку ставится мышью: призрак
## едет вдоль планки по пазам, зелёный — можно, красный — с причиной; колесо/←→ — на паз, R —
## другая сторона кронштейна, Q/E — угол поворотного. Всё — в черновике (Ctrl+Z / Ctrl+Y), на
## «Применить» — одна операция BuildPlan: взять из вещей, купить, снятое — в тайник (в рейде —
## в рюкзак, через хост; торговца нет, приклад не меняют).

signal closed

const C_BG := Color(0.035, 0.036, 0.04, 1.0)
const C_PANEL := Color(0.075, 0.077, 0.082, 0.96)
const C_CARD := Color(0.11, 0.112, 0.12, 1.0)
const C_CARD_HI := Color(0.16, 0.162, 0.172, 1.0)
const C_EDGE := Color(1, 1, 1, 0.07)
const C_TEXT := Color(0.93, 0.91, 0.87)
const C_MUTED := Color(0.58, 0.59, 0.58)
const C_ACCENT := Color(0.96, 0.74, 0.38)
const C_OK := Color(0.45, 0.88, 0.55)
const C_BAD := Color(0.96, 0.42, 0.34)
const C_SHOP := Color(0.56, 0.76, 1.0)
const TABS := [["all", "Всё"], ["optic", "Прицелы"], ["muzzle", "Ствол"], ["fore", "Цевьё"], ["stock", "Приклад"],
	["adapter", "Переходники"], ["mag", "Магазины"]]
const CARD := Vector2(176, 50)

var mode: String = "hideout"
var where: String = ""
var idx: int = -1
var _uid: String = ""
var _player: Player

var _weapon: Dictionary = {}
var _draft: Dictionary = {}
var _mag: Dictionary = {"from": "weapon"}
var _undo: Array = []
var _redo: Array = []
## Выбранная точка: ключ детали (занята) или ключ точки (свободна); _sel_add — «ещё одно на планку».
var _sel: String = ""
var _sel_add: bool = false
## Установка по планке: {key, id, src, slot, flip, angle, carried, ok, why, moving}.
var _place: Dictionary = {}
var _hover: Dictionary = {}
var _tab: String = "all"
var _source: String = "mine"
## Порядок деталей в полосе: "" — как лежат, "up" — дешёвые первыми, "down" — дорогие первыми.
var _sort: String = ""
var _status_t: float = 0.0
var _plan: Dictionary = {}

var _view: BuilderView
var _overlay: Control
var _cards: Control
var _tree_box: VBoxContainer
var _actions: HFlowContainer
var _stats_box: VBoxContainer
var _strip: HBoxContainer
var _tabs_box: HBoxContainer
var _source_box: HBoxContainer
## Плашка «для точки: …» — полоса деталей отфильтрована по выбранной точке; ✕ снимает выбор.
var _filter_box: HBoxContainer
var _title: Label
var _subtitle: Label
var _summary: Label
var _status: Label
var _apply_btn: Button
var _undo_btn: Button
var _redo_btn: Button
var _hint: Label
var _spots: Array[Dictionary] = []
var _font: Font


# ---------------------------------------------------------------- открыть

## Убежище: оружие на месте where ("equip:<слот>" / "stash" / "backpack") и индекс; торговец есть.
static func open_hideout(parent: Node, p_where: String, p_idx: int) -> WeaponBuilder:
	var b := WeaponBuilder.new()
	b.mode = "hideout"
	b.where = p_where
	b.idx = p_idx
	if not p_where.begins_with("equip:"):
		var list: Array = Profile.list_of(p_where)
		if p_idx >= 0 and p_idx < list.size():
			if not (list[p_idx] as Dictionary).has("uid"):
				list[p_idx]["uid"] = "%d" % (Time.get_ticks_usec() % 1000000000)
			b._uid = String(list[p_idx].uid)
	parent.add_child(b)
	return b


## Ствол стойки тира / стенда (Player.range_weapon): любой обвес и магазин игры без покупки и без тайника —
## «Применить» сразу выдаёт собранный ствол в руки (Player.set_range_weapon). Своё снаряжение не трогается.
static func open_sandbox(parent: Node, player: Player) -> WeaponBuilder:
	var b := WeaponBuilder.new()
	b.mode = "sandbox"
	b._player = player
	parent.add_child(b)
	return b


## Рейд: своё оружие в слоте ("equip:<слот>") или в рюкзаке ("backpack", idx); применяет хост.
static func open_raid(parent: Node, player: Player, p_where: String, p_idx: int) -> WeaponBuilder:
	var b := WeaponBuilder.new()
	b.mode = "raid"
	b._player = player
	b.where = p_where
	b.idx = p_idx
	parent.add_child(b)
	return b


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	_font = ThemeDB.fallback_font
	_weapon = _current_weapon()
	_draft = BuildPlan.draft_of(_weapon)
	_build_ui()
	_refresh()


## Пока открыт — Esc его, а не окно под ним (счётчик ItemInfo, как у окна описания).
func _enter_tree() -> void:
	ItemInfo._open += 1


func _exit_tree() -> void:
	ItemInfo._open = maxi(0, ItemInfo._open - 1)
	ItemInfo._closed_frame = Engine.get_process_frames()


func _current_weapon() -> Dictionary:
	if mode == "sandbox":
		return _player.range_weapon.duplicate(true) if _player != null and is_instance_valid(_player) else {}
	if mode == "raid":
		if _player == null or not is_instance_valid(_player):
			return {}
		if where.begins_with("equip:"):
			return (_player.inventory.equipment.get(where.trim_prefix("equip:"), {}) as Dictionary).duplicate(true)
		return (_player.inventory.items[idx] as Dictionary).duplicate(true) if idx >= 0 and idx < _player.inventory.items.size() else {}
	if where.begins_with("equip:"):
		return (Profile.equipment.get(where.trim_prefix("equip:"), {}) as Dictionary).duplicate(true)
	var list: Array = Profile.list_of(where)
	for i in range(list.size()):
		if String((list[i] as Dictionary).get("uid", "")) == _uid and _uid != "":
			idx = i
			return (list[i] as Dictionary).duplicate(true)
	return (list[idx] as Dictionary).duplicate(true) if idx >= 0 and idx < list.size() else {}


## Стенд: по два экземпляра каждого обвеса игры (две одинаковые детали на одном стволе) и по полному магазину.
var _sandbox_items: Array = []


func _lists() -> Dictionary:
	if mode == "sandbox":
		if _sandbox_items.is_empty():
			for id: Variant in WeaponDb.ids("attachments"):
				for copy: int in range(2):
					_sandbox_items.append({"id": String(id), "n": 1, "dur": float(Balance.CONDITION.full)})
			for mid: Variant in WeaponDb.ids("magazines"):
				var cal: String = WeaponDb.mag_caliber(String(mid))
				var mag: Dictionary = WeaponDb.make_mag(String(mid), WeaponDb.default_ammo(cal), int(WeaponDb.magazine(String(mid)).get("capacity", 0)))
				mag["n"] = 1
				_sandbox_items.append(mag)
		return {"sandbox": _sandbox_items}
	if mode == "raid":
		return {"backpack": _player.inventory.items}
	return {"stash": Profile.stash, "backpack": Profile.backpack}


func _rules() -> Dictionary:
	if mode == "sandbox":
		return {"shop": false, "lists": ["sandbox"], "locked": []}
	if mode == "raid":
		return {"shop": false, "lists": BuildPlan.RAID_LISTS, "locked": ["stock"]}
	return {"shop": true, "lists": BuildPlan.HIDEOUT_LISTS}


# ---------------------------------------------------------------- разметка

func _panel(color: Color = C_PANEL, radius: int = 8, margin: int = 12) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = color
	sb.border_color = C_EDGE
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(radius)
	sb.set_content_margin_all(margin)
	return sb


func _label(text: String, size: int = 14, color: Color = C_TEXT) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l


func _button(text: String, action: Callable, accent: bool = false) -> Button:
	var b := Button.new()
	b.text = text
	b.focus_mode = Control.FOCUS_NONE
	b.add_theme_font_size_override("font_size", 13)
	# обычная кнопка — из общей темы (UiTheme); выбранная / главная — залита золотым
	if accent:
		b.add_theme_stylebox_override("normal", UiTheme.face(Color(0.5, 0.36, 0.14), Color(1.0, 0.8, 0.45), 2))
		b.add_theme_stylebox_override("hover", UiTheme.face(Color(0.62, 0.45, 0.18), Color(1.0, 0.9, 0.65), 2))
		b.add_theme_stylebox_override("pressed", UiTheme.face(Color(0.4, 0.28, 0.1), Color(1.0, 0.8, 0.45), 0))
		b.add_theme_color_override("font_color", Color(1.0, 0.95, 0.82))
	b.pressed.connect(action)
	return b


func _build_ui() -> void:
	var bg := ColorRect.new()
	bg.color = C_BG
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	# мягкое пятно света за моделью — студийный фон
	var glow := TextureRect.new()
	var grad := GradientTexture2D.new()
	grad.fill = GradientTexture2D.FILL_RADIAL
	grad.fill_from = Vector2(0.5, 0.5)
	grad.fill_to = Vector2(1.0, 0.5)
	var g := Gradient.new()
	g.set_color(0, Color(0.2, 0.2, 0.22, 1.0))
	g.set_color(1, Color(0.035, 0.036, 0.04, 0.0))
	grad.gradient = g
	glow.texture = grad
	glow.stretch_mode = TextureRect.STRETCH_SCALE
	glow.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	glow.set_anchors_preset(Control.PRESET_FULL_RECT)
	glow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(glow)
	var root := VBoxContainer.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.add_theme_constant_override("separation", 8)
	root.offset_left = 16
	root.offset_top = 12
	root.offset_right = -16
	root.offset_bottom = -12
	add_child(root)
	# шапка
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 14)
	root.add_child(head)
	var titles := VBoxContainer.new()
	titles.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	titles.add_theme_constant_override("separation", 0)
	head.add_child(titles)
	_title = _label("", 24, C_TEXT)
	titles.add_child(_title)
	_subtitle = _label("", 13, C_MUTED)
	titles.add_child(_subtitle)
	for v: Array in [["Три четверти", "q"], ["Сбоку", "side"], ["Сверху", "top"], ["Из глаза", "eye"]]:
		var view_name: String = String(v[1])
		head.add_child(_button(String(v[0]), func() -> void: _set_view(view_name)))
	head.add_child(_button("Закрыть  Esc", _close))
	# середина: дерево | студия | характеристики
	var mid := HBoxContainer.new()
	mid.size_flags_vertical = Control.SIZE_EXPAND_FILL
	mid.add_theme_constant_override("separation", 10)
	root.add_child(mid)
	var left := PanelContainer.new()
	left.add_theme_stylebox_override("panel", _panel())
	left.custom_minimum_size.x = 280
	mid.add_child(left)
	var lv := VBoxContainer.new()
	lv.add_theme_constant_override("separation", 8)
	left.add_child(lv)
	lv.add_child(_label("СБОРКА", 12, C_MUTED))
	var tree_scroll := ScrollContainer.new()
	tree_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	tree_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	lv.add_child(tree_scroll)
	_tree_box = VBoxContainer.new()
	_tree_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_tree_box.add_theme_constant_override("separation", 2)
	tree_scroll.add_child(_tree_box)
	_actions = HFlowContainer.new()
	_actions.add_theme_constant_override("h_separation", 6)
	_actions.add_theme_constant_override("v_separation", 6)
	lv.add_child(_actions)
	var center := Control.new()
	center.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	center.clip_contents = true
	mid.add_child(center)
	_view = BuilderView.new()
	_view.set_anchors_preset(Control.PRESET_FULL_RECT)
	center.add_child(_view)
	_view.clicked.connect(_on_view_click)
	_view.hovered.connect(_on_view_hover)
	_view.alt_clicked.connect(_on_view_alt_click)
	_overlay = Control.new()
	_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_overlay.draw.connect(_draw_overlay)
	center.add_child(_overlay)
	_cards = Control.new()
	_cards.set_anchors_preset(Control.PRESET_FULL_RECT)
	_cards.mouse_filter = Control.MOUSE_FILTER_IGNORE
	center.add_child(_cards)
	_hint = _label("", 13, C_TEXT)
	_hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hint.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	_hint.add_theme_constant_override("outline_size", 5)
	center.add_child(_hint)
	var keys := _label("ЛКМ — вращать · колесо — ближе · ПКМ тянуть — сдвинуть · ПКМ по детали — снять · СКМ — поставить / применить", 12, Color(1, 1, 1, 0.32))
	keys.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	keys.position = Vector2(10, -24)
	keys.mouse_filter = Control.MOUSE_FILTER_IGNORE
	center.add_child(keys)
	var right := PanelContainer.new()
	right.add_theme_stylebox_override("panel", _panel())
	right.custom_minimum_size.x = 300
	mid.add_child(right)
	var rv := VBoxContainer.new()
	rv.add_theme_constant_override("separation", 6)
	right.add_child(rv)
	rv.add_child(_label("ХАРАКТЕРИСТИКИ", 12, C_MUTED))
	_stats_box = VBoxContainer.new()
	_stats_box.add_theme_constant_override("separation", 7)
	rv.add_child(_stats_box)
	# низ: вкладки, источник, детали
	var bottom := PanelContainer.new()
	bottom.add_theme_stylebox_override("panel", _panel())
	bottom.custom_minimum_size.y = 168
	root.add_child(bottom)
	var bv := VBoxContainer.new()
	bv.add_theme_constant_override("separation", 8)
	bottom.add_child(bv)
	var bar := HBoxContainer.new()
	bar.add_theme_constant_override("separation", 6)
	bv.add_child(bar)
	_tabs_box = HBoxContainer.new()
	_tabs_box.add_theme_constant_override("separation", 4)
	_tabs_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bar.add_child(_tabs_box)
	_filter_box = HBoxContainer.new()
	bar.add_child(_filter_box)
	_source_box = HBoxContainer.new()
	_source_box.add_theme_constant_override("separation", 4)
	bar.add_child(_source_box)
	var strip_scroll := ScrollContainer.new()
	strip_scroll.custom_minimum_size.y = 104
	strip_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	bv.add_child(strip_scroll)
	_strip = HBoxContainer.new()
	_strip.add_theme_constant_override("separation", 8)
	strip_scroll.add_child(_strip)
	# подвал: итог и кнопки
	var foot := HBoxContainer.new()
	foot.add_theme_constant_override("separation", 10)
	root.add_child(foot)
	var sums := VBoxContainer.new()
	sums.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	sums.add_theme_constant_override("separation", 0)
	foot.add_child(sums)
	_summary = _label("", 14, C_TEXT)
	sums.add_child(_summary)
	_status = _label("", 13, C_BAD)
	sums.add_child(_status)
	foot.add_child(_button("Вернуть как было", _reset))
	_undo_btn = _button("↶  Ctrl+Z", _do_undo)
	foot.add_child(_undo_btn)
	_redo_btn = _button("↷  Ctrl+Y", _do_redo)
	foot.add_child(_redo_btn)
	_apply_btn = _button("Применить  Enter", _apply, true)
	_apply_btn.custom_minimum_size.x = 190
	foot.add_child(_apply_btn)


# ---------------------------------------------------------------- черновик

## Запись оружия по черновику (или по mods / mag, если даны) — для модели и характеристик.
func _draft_entry(p_mods: Variant = null, p_mag: Variant = null) -> Dictionary:
	var mods: Dictionary = p_mods if p_mods is Dictionary else _draft
	var mag: Dictionary = p_mag if p_mag is Dictionary else _mag
	var e: Dictionary = _weapon.duplicate(true)
	e["mods"] = BuildPlan.clean(mods)
	var from: String = String(mag.get("from", "weapon"))
	if from == "none":
		e["mag"] = {"id": "", "ammo": "", "rounds": 0}
	elif from != "weapon":
		var list: Array = _lists().get(from, [])
		var mi: int = int(mag.get("idx", -1))
		if mi >= 0 and mi < list.size():
			e["mag"] = Gear.mag_record(list[mi])
	return e


func _push() -> void:
	_undo.append([_draft.duplicate(true), _mag.duplicate(true)])
	if _undo.size() > 80:
		_undo.pop_front()
	_redo.clear()


func _do_undo() -> void:
	if _undo.is_empty():
		return
	_redo.append([_draft.duplicate(true), _mag.duplicate(true)])
	var s: Array = _undo.pop_back()
	_draft = s[0]
	_mag = s[1]
	_place = {}
	_refresh()


func _do_redo() -> void:
	if _redo.is_empty():
		return
	_undo.append([_draft.duplicate(true), _mag.duplicate(true)])
	var s: Array = _redo.pop_back()
	_draft = s[0]
	_mag = s[1]
	_place = {}
	_refresh()


func _reset() -> void:
	if _draft == BuildPlan.draft_of(_weapon) and String(_mag.get("from", "weapon")) == "weapon":
		return
	_push()
	_draft = BuildPlan.draft_of(_weapon)
	_mag = {"from": "weapon"}
	_place = {}
	_sel = ""
	_refresh()


## Снять деталь key со всем, что на ней, из черновика.
func _remove(key: String) -> void:
	if not _draft.has(key):
		return
	if _locked(key) != "":
		_say(_locked(key))
		return
	_push()
	for k: String in WeaponBuild.subtree(_draft, key):
		_draft.erase(k)
	_sel = WeaponBuild.point_key(key)
	_sel_add = false
	_refresh()


## Почему точку key здесь трогать нельзя ("" — можно): приклад в рейде, верстак в убежище.
func _locked(key: String) -> String:
	var top: String = WeaponBuild.top_mount(key)
	if mode == "raid" and top == "stock":
		return "Приклад — только на верстаке в убежище"
	if mode == "hideout":
		var why: String = Profile.mod_block("", top)
		if why != "":
			return why[0].to_upper() + why.substr(1)
	return ""


# ---------------------------------------------------------------- детали: откуда и куда

## Что можно поставить: снятое с этого оружия, вещи (тайник, рюкзак), торговец (в убежище).
func _pool() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var used: Dictionary = {}
	for k: Variant in _draft:
		var src: Dictionary = (_draft[k] as Dictionary).get("src", {})
		match String(src.get("from", "")):
			"weapon":
				used["weapon:" + String(src.key)] = true
			"shop":
				pass
			_:
				used["%s:%d" % [String(src.from), int(src.get("idx", -1))]] = true
	if _source == "mine":
		var old: Dictionary = _weapon.get("mods", {})
		for k: String in WeaponBuild.sorted_keys(old):
			if used.has("weapon:" + k):
				continue
			var parent: String = WeaponBuild.parent_key(k)
			if parent != "" and not used.has("weapon:" + parent):
				continue
			out.append({"id": WeaponDb.mod_id(old[k]), "src": {"from": "weapon", "key": k}, "item": WeaponCondition.mod_entry(old[k]),
				"sub": "снято с оружия · %d%%" % int(WeaponCondition.percent(old[k]))})
		var lists: Dictionary = _lists()
		for ln: Variant in lists:
			var list: Array = lists[ln]
			for i in range(list.size()):
				var e: Dictionary = list[i]
				if WeaponDb.attachment(String(e.id)).is_empty() or used.has("%s:%d" % [String(ln), i]):
					continue
				var carried: int = (e.get("mods", {}) as Dictionary).size()
				out.append({"id": WeaponDb.canonical(String(e.id)), "src": {"from": String(ln), "idx": i, "sub": ""}, "item": e,
					"sub": "%s · %d%%%s" % [_list_name(String(ln)), int(WeaponCondition.percent(e)), " · +%d на нём" % carried if carried > 0 else ""]})
	elif mode == "hideout":
		for id: Variant in TraderStock.stock():
			var sid: String = String(id)
			if WeaponDb.attachment(sid).is_empty():
				continue
			var price: int = Profile.buy_price(sid)
			var lock: String = ""
			var tl: int = maxi(TraderStock.catalog_of(sid), 1)
			if not Settings.all_weapons and Profile.trust_level() < tl and not sid in Profile.unlocked_stock:
				lock = "ступень доверия %d" % TraderStock.step_of(tl)
			out.append({"id": sid, "src": {"from": "shop"}, "item": {"id": sid, "n": 1}, "price": price, "lock": lock,
				"sub": "%s ₽" % InventoryUI.money(price)})
	return out


## Вкладка детали по её типу.
static func tab_of(id: String) -> String:
	var a: Dictionary = WeaponDb.attachment(id)
	var kind: String = String(a.get("type", ""))
	if not (a.get("provides", {}) as Dictionary).is_empty():
		return "adapter"
	if WeaponDb.is_optic(id):
		return "optic"
	if kind in ["SUPPRESSOR", "COMPENSATOR", "FLASH_HIDER", "MUZZLE_BRAKE"]:
		return "muzzle"
	for f: Variant in a.get("fits", []):
		if String(f).begins_with("STOCK"):
			return "stock"
	return "fore"


## Куда деталь встанет и как: {key, slot, rail: bool, why}. Выбранная точка — в приоритете.
func _target_for(part: Dictionary) -> Dictionary:
	var id: String = String(part.id)
	var e: Dictionary = _draft_entry()
	var keys: Array[String] = []
	if _sel != "":
		var pk: String = WeaponBuild.point_key(_sel)
		if _draft.has(_sel) and not _sel_add:
			keys.append(_sel)
		keys.append(pk)
		for n in range(2, 8):
			keys.append(pk + WeaponBuild.MULTI + str(n))
	else:
		keys.append_array(WeaponBuild.candidate_keys(e, id))
	var first_why: String = ""
	var no_room: Dictionary = {}
	for key: String in keys:
		if _draft.has(key) and (key != _sel or _sel_add):
			continue
		var pt: Dictionary = WeaponBuild.point(String(_weapon.id), e.mods, key)
		if pt.is_empty() or not String(pt.iface) in WeaponDb.attachment(id).get("fits", []):
			if first_why == "":
				first_why = "сюда не встаёт" if not pt.is_empty() else ""
			continue
		var lock: String = _locked(key)
		if lock != "":
			first_why = lock
			continue
		var slots: Array[int] = WeaponBuild.valid_slots(e, key, id)
		var rail: bool = WeaponBuild.is_rail(pt)
		if slots.is_empty():
			if first_why == "":
				first_why = WeaponBuild.block(e, key, id)
			# на планке места нет — запомнить, но сначала поискать другие точки
			if rail and no_room.is_empty():
				no_room = {"key": key, "slot": 0, "rail": true, "why": first_why}
			continue
		return {"key": key, "slot": slots[0], "rail": rail, "why": ""}
	if not no_room.is_empty():
		return no_room
	return {"key": "", "why": first_why if first_why != "" else "некуда поставить"}


## Выбрали деталь в полосе: на планку — режим установки по пазам, иначе — сразу.
func _choose(part: Dictionary) -> void:
	if String(part.get("lock", "")) != "":
		_say(String(part.lock))
		return
	var t: Dictionary = _target_for(part)
	if String(t.get("key", "")) == "":
		_say(String(t.why))
		return
	if bool(t.get("rail", false)):
		_begin_place(String(t.key), part, int(t.slot), false)
		return
	_commit(String(t.key), part, -1, false, NAN)


## Поставить деталь в черновик (со всем, что на ней было в вещах или на этом оружии).
func _commit(key: String, part: Dictionary, slot: int, flip: bool, angle: float) -> void:
	var id: String = String(part.id)
	var e: Dictionary = _draft_entry()
	var why: String = WeaponBuild.block(e, key, id, slot)
	if why != "":
		_say(why)
		return
	_push()
	for k: String in WeaponBuild.subtree(_draft, key):
		_draft.erase(k)
	var rec: Dictionary = {"id": id, "src": part.src}
	var item: Dictionary = part.get("item", {})
	for keep: String in ["light", "laser"]:
		if item.has(keep):
			rec[keep] = item[keep]
	if slot >= 0:
		rec["slot"] = slot
	if flip:
		rec["flip"] = true
	if not is_nan(angle):
		rec["angle"] = angle
	_draft[key] = rec
	_bind_remotes()
	# что ехало на детали: из вещей — её mods; с этого оружия — снятые вместе с ней потомки
	var src: Dictionary = part.src
	var children: Dictionary = {}
	if String(src.from) == "weapon":
		var old: Dictionary = _weapon.get("mods", {})
		for d: String in WeaponBuild.subtree(old, String(src.key)):
			if d != String(src.key):
				children[d.substr(String(src.key).length() + 1)] = {"rec": old[d], "src": {"from": "weapon", "key": d}}
	elif String(src.from) != "shop":
		var carried: Dictionary = item.get("mods", {})
		for c: Variant in carried:
			children[String(c)] = {"rec": carried[c], "src": {"from": String(src.from), "idx": int(src.idx), "sub": String(c)}}
	for rel: String in WeaponBuild.sorted_keys(children):
		var full: String = key + WeaponBuild.SEP + rel
		var crec: Dictionary = (children[rel].rec as Dictionary).duplicate(true) if children[rel].rec is Dictionary else {"id": String(children[rel].rec)}
		crec["src"] = children[rel].src
		if WeaponBuild.block(_draft_entry(), full, WeaponDb.mod_id(crec), int(crec.get("slot", -1))) == "":
			_draft[full] = crec
	_sel = key
	_sel_add = false
	_place = {}
	_refresh()


# ---------------------------------------------------------------- установка по планке

func _begin_place(key: String, part: Dictionary, slot: int, moving: bool) -> void:
	var item: Dictionary = part.get("item", {})
	var rec: Dictionary = _draft.get(key, {}) if moving else {}
	_place = {"key": key, "part": part, "slot": slot, "flip": bool(rec.get("flip", item.get("flip", false))),
		"angle": float(rec.get("angle", NAN)), "moving": moving}
	_view.set_meta("wheel_taken", true)
	_update_place()


func _place_mods() -> Dictionary:
	var mods: Dictionary = _draft.duplicate(true)
	var key: String = String(_place.key)
	var keep: Dictionary = {}
	if bool(_place.moving):
		# переезжает вместе с тем, что на ней
		for k: String in WeaponBuild.subtree(mods, key):
			if k != key:
				keep[k] = mods[k]
	for k: String in WeaponBuild.subtree(mods, key):
		mods.erase(k)
	var rec: Dictionary = {"id": String(_place.part.id), "src": _place.part.src, "slot": int(_place.slot)}
	if bool(_place.flip):
		rec["flip"] = true
	if not is_nan(float(_place.angle)):
		rec["angle"] = float(_place.angle)
	var old: Dictionary = _draft.get(key, {})
	for k2: String in ["light", "laser", "remote"]:
		if k2 == "remote" and WeaponDb.mod_id(old) != String(_place.part.id):
			continue
		if old.has(k2):
			rec[k2] = old[k2]
	mods[key] = rec
	mods.merge(keep)
	var resolved: Dictionary = AttachmentRemote.resolve(String(_weapon.id), mods)
	return resolved.mods if String(resolved.why) == "" else mods


func _update_place() -> void:
	if _place.is_empty():
		return
	var key: String = String(_place.key)
	var probe: Dictionary = _draft_entry()
	probe.mods = BuildPlan.clean(_place_mods())
	var why: String = WeaponBuild.block(probe, key, String(_place.part.id), int(_place.slot))
	_place["ok"] = why == ""
	_place["why"] = why
	_refresh_model()
	var node: Node3D = _view.model().find_child("Attachment_" + WeaponBuild.node_name(key), true, false) as Node3D if _view.model() else null
	_view.tint(node, why == "")
	_refresh_stats()
	var warning: String = WeaponBuild.sight_warning(probe, key, String(_place.part.id), int(_place.slot))
	if why == "" and _status_t <= 0.0:
		_status.text = warning
		_status.add_theme_color_override("font_color", C_ACCENT)
	_overlay.queue_redraw()


func _end_place() -> void:
	_place = {}
	_view.set_meta("wheel_taken", false)
	_refresh()


func _confirm_place() -> void:
	if _place.is_empty():
		return
	if not bool(_place.get("ok", false)):
		_say(String(_place.get("why", "нельзя")))
		return
	var mods: Dictionary = _place_mods()
	var key: String = String(_place.key)
	_push()
	_draft = mods
	_bind_remotes()
	_sel = key
	_sel_add = false
	_end_place()


func _nudge(step: int) -> void:
	if _place.is_empty():
		var key: String = _sel
		if not _draft.has(key):
			return
		var pt: Dictionary = WeaponBuild.point(String(_weapon.id), BuildPlan.clean(_draft), key)
		if not WeaponBuild.is_rail(pt):
			return
		var rec: Dictionary = _draft[key]
		var cur: int = int(rec.get("slot", WeaponBuild.nearest_slot(pt.rail, WeaponBuild.clamp_of(String(rec.id)), WeaponBuild.placed_z(WeaponBuild.model_of(String(_weapon.id)), BuildPlan.clean(_draft), key))))
		var e: Dictionary = _draft_entry()
		var why: String = WeaponBuild.block(e, key, String(rec.id), cur + step)
		if why != "":
			_say(why)
			return
		_push()
		rec["slot"] = cur + step
		_refresh()
		return
	var pt2: Dictionary = WeaponBuild.point(String(_weapon.id), BuildPlan.clean(_place_mods()), String(_place.key))
	var n: int = WeaponBuild.slot_count(pt2.get("rail", [0, 0]), WeaponBuild.clamp_of(String(_place.part.id)))
	_place.slot = clampi(int(_place.slot) + step, 0, maxi(n - 1, 0))
	_update_place()


## Сторона кронштейна (R): в установке — у призрака, иначе — у выбранного.
func _flip() -> void:
	var key: String = String(_place.get("key", _sel))
	var id: String = String(_place.part.id) if not _place.is_empty() else WeaponDb.mod_id(_draft.get(key, ""))
	var spec: Dictionary = (WeaponDb.attachment(id).get("provides", {}) as Dictionary).get("rail", {})
	if not bool(spec.get("flip", false)):
		return
	if not _place.is_empty():
		_place.flip = not bool(_place.flip)
		_update_place()
		return
	_push()
	var rec: Dictionary = _draft[key]
	rec["flip"] = not bool(rec.get("flip", false))
	_refresh()


## Угол поворотного кронштейна (Q/E): шаг из данных, в пределах конструкции.
func _turn(dir: int) -> void:
	var key: String = String(_place.get("key", _sel))
	var id: String = String(_place.part.id) if not _place.is_empty() else WeaponDb.mod_id(_draft.get(key, ""))
	var spec: Dictionary = (WeaponDb.attachment(id).get("provides", {}) as Dictionary).get("rail", {})
	if not spec.has("angle"):
		return
	var lim: Array = spec.angle
	var step: float = float(spec.get("step", 15.0))
	var cur: float = float(_place.angle) if not _place.is_empty() else float((_draft[key] as Dictionary).get("angle", spec.get("roll", 45.0)))
	if is_nan(cur):
		cur = float(spec.get("roll", 45.0))
	var nxt: float = clampf(cur + step * dir, float(lim[0]), float(lim[1]))
	if not _place.is_empty():
		_place.angle = nxt
		_update_place()
		return
	_push()
	(_draft[key] as Dictionary)["angle"] = nxt
	_refresh()


# ---------------------------------------------------------------- мышь в студии

func _on_view_hover(at: Vector2) -> void:
	if _place.is_empty():
		_overlay.queue_redraw()
		return
	var ends: Array[Vector3] = WeaponMods.rail_ends(_view.space(), WeaponBuild.model_of(String(_weapon.id)), BuildPlan.clean(_place_mods()), String(_place.key))
	if ends.size() < 2:
		return
	var a: Vector2 = _view.project(ends[0])
	var b: Vector2 = _view.project(ends[1])
	var ab: Vector2 = b - a
	if ab.length_squared() < 4.0:
		return
	var t: float = clampf((at - a).dot(ab) / ab.length_squared(), 0.0, 1.0)
	var g: Dictionary = WeaponBuild.geo(WeaponBuild.model_of(String(_weapon.id)), BuildPlan.clean(_place_mods()), String(_place.key))
	var z: float = lerpf(float(g.rail[0]), float(g.rail[1]), t)
	var slot: int = WeaponBuild.nearest_slot(g.rail, WeaponBuild.clamp_of(String(_place.part.id)), z)
	if slot != int(_place.slot):
		_place.slot = slot
		_update_place()
	_hint.position = at + Vector2(16, 14)


func _on_view_click(at: Vector2) -> void:
	if not _place.is_empty():
		_confirm_place()
		return
	# клик по точке на модели
	var s: Dictionary = _spot_at(at)
	if not s.is_empty():
		_select(String(s.key), bool(s.get("add", false)))


## Точка крепления под курсором ({} — мимо).
func _spot_at(at: Vector2) -> Dictionary:
	var best: Dictionary = {}
	var best_d: float = 18.0
	for s: Dictionary in _spots:
		var d: float = (s.pos as Vector2).distance_to(at)
		if d < best_d:
			best_d = d
			best = s
	return best


## Щелчок без протяжки: правой по детали — снять её, средней — поставить / применить сборку.
func _on_view_alt_click(at: Vector2, button: int) -> void:
	if button == MOUSE_BUTTON_MIDDLE:
		_middle_click()
	elif button == MOUSE_BUTTON_RIGHT and _place.is_empty():
		var s: Dictionary = _spot_at(at)
		if not s.is_empty() and _draft.has(String(s.key)):
			_remove(String(s.key))


## Средняя кнопка: призрак на планке — поставить; иначе — применить собранное (как Enter).
func _middle_click() -> void:
	if not _place.is_empty():
		_confirm_place()
	else:
		_apply()


func _select(key: String, add: bool = false) -> void:
	_sel = key
	_sel_add = add
	_refresh()


# ---------------------------------------------------------------- обновление

func _refresh() -> void:
	if _weapon.is_empty():
		_title.text = "Оружия нет"
		return
	var e: Dictionary = _draft_entry()
	_title.text = ItemDb.item_name(String(_weapon.id))
	var w: Dictionary = WeaponDb.weapon(String(_weapon.id))
	_subtitle.text = "%s · %s · состояние %d%%%s" % [String(WeaponDb.CLASS_NAMES.get(String(w.get("class", "")), "")), WeaponDb.caliber_name(String(w.get("caliber", ""))),
		int(WeaponCondition.percent(_weapon)), "  ·  рейд: детали из рюкзака, приклад — только в убежище" if mode == "raid" else ""]
	_plan = BuildPlan.resolve(_weapon, _draft, _mag, _lists(), _rules())
	_refresh_model()
	_refresh_tree()
	_refresh_actions()
	_refresh_stats()
	_refresh_strip()
	_refresh_footer()
	_overlay.queue_redraw()


func _refresh_model() -> void:
	var mods: Dictionary = BuildPlan.clean(_place_mods()) if not _place.is_empty() else BuildPlan.clean(_draft)
	var e: Dictionary = _draft_entry()
	var mag: String = WeaponMods.mag_state(e)
	var key: String = ItemThumbs.key_of({"id": _weapon.id, "mods": mods, "dur": _weapon.get("dur", 100.0), "mag": e.get("mag", {})}) + "|" + mag + "|" + str(mods.size())
	_view.show_build(String(_weapon.id), mods, WeaponCondition.percent(_weapon), mag, key + WeaponMark.key(WeaponMark.marks(_weapon)), WeaponMark.marks(_weapon))


func _row_style(selected: bool) -> StyleBoxFlat:
	var sb := _panel(Color(0.96, 0.74, 0.38, 0.16) if selected else Color(0, 0, 0, 0), 6, 6)
	sb.border_color = Color(0.96, 0.74, 0.38, 0.5) if selected else Color(0, 0, 0, 0)
	return sb


func _refresh_tree() -> void:
	for c: Node in _tree_box.get_children():
		c.queue_free()
	var mods: Dictionary = BuildPlan.clean(_draft)
	var wid: String = String(_weapon.id)
	var mounts: Dictionary = WeaponDb.mounts_of(wid)
	var order: Array[String] = []
	for m: String in WeaponDb.MOUNTS:
		if mounts.has(m):
			order.append(m)
	for m: Variant in mounts:
		if not String(m) in order:
			order.append(String(m))
	for m: String in order:
		var on: Array[String] = []
		for k: String in WeaponBuild.sorted_keys(mods):
			if WeaponBuild.top_mount(k) == m:
				on.append(k)
		if on.is_empty():
			var remote_owner: String = ""
			for owner: String in WeaponBuild.sorted_keys(mods):
				var rec: Dictionary = mods[owner] if mods[owner] is Dictionary else {}
				if not AttachmentRemote.spec(WeaponDb.mod_id(rec)).is_empty() and String((rec.get("remote", {}) as Dictionary).get("point", "")) == m:
					remote_owner = owner
			if remote_owner != "":
				_tree_row(remote_owner, "Пульт МЕТКА-4", String(WeaponDb.MOUNT_NAMES.get(m, m)), 0, true)
			else:
				_tree_row(m, String(WeaponDb.MOUNT_NAMES.get(m, m)), "пусто", 0, false)
			continue
		on.sort_custom(func(a: String, b: String) -> bool: return _tree_order(a) < _tree_order(b))
		for k: String in on:
			var rec: Dictionary = mods[k]
			var sub: String = WeaponBuild.label(wid, mods, k) if WeaponBuild.depth(k) == 0 else String(WeaponBuild.POINT_NAMES.get(WeaponBuild.base_of(k), WeaponBuild.base_of(k)))
			if rec.has("slot"):
				sub += " · паз %d" % (int(rec.slot) + 1)
			if bool(rec.get("flip", false)):
				sub += " · слева"
			if rec.has("angle"):
				sub += " · %d°" % int(rec.angle)
			_tree_row(k, ItemDb.item_name(String(rec.id)), sub, WeaponBuild.depth(k), true)
		# свободные точки переходников
		for k: String in on:
			for p: Variant in (WeaponDb.attachment(WeaponDb.mod_id(mods[k])).get("provides", {}) as Dictionary):
				var pk: String = k + WeaponBuild.SEP + String(p)
				if not mods.has(pk):
					_tree_row(pk, String(WeaponBuild.POINT_NAMES.get(String(p), p)), "пусто", WeaponBuild.depth(pk), false)
	if not WeaponDb.weapon(wid).has("internal_mag") and WeaponDb.weapon(wid).has("mag_if"):
		var e: Dictionary = _draft_entry()
		var mag: Dictionary = e.get("mag", {})
		var label: String = ItemDb.item_name(String(mag.get("id", ""))) if String(mag.get("id", "")) != "" else "нет магазина"
		_tree_row("@mag", label, "магазин · %s" % (Gear.ammo_estimate(int(mag.get("rounds", 0)), int(WeaponDb.magazine(String(mag.get("id", ""))).get("capacity", 0)), false) if String(mag.get("id", "")) != "" else "вынут"), 0, String(mag.get("id", "")) != "")


func _tree_order(k: String) -> String:
	# по точке, на планке — по месту вдоль неё, дети сразу за родителем
	var parts: PackedStringArray = k.split(WeaponBuild.SEP)
	var out: String = ""
	var acc: String = ""
	for i in range(parts.size()):
		acc = parts[i] if i == 0 else acc + WeaponBuild.SEP + parts[i]
		var z: float = WeaponBuild.placed_z(WeaponBuild.model_of(String(_weapon.id)), BuildPlan.clean(_draft), acc)
		out += "%s|%08d|" % [WeaponBuild.point_key(acc), int((z + 1.0) * 10000.0)]
	return out


func _tree_row(key: String, title: String, sub: String, depth: int, filled: bool) -> void:
	var row := PanelContainer.new()
	var selected: bool = key == _sel or (key == "@mag" and _tab == "mag" and _sel == "@mag")
	row.add_theme_stylebox_override("panel", _row_style(selected))
	row.mouse_filter = Control.MOUSE_FILTER_STOP
	row.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 8)
	row.add_child(h)
	var pad := Control.new()
	pad.custom_minimum_size.x = depth * 16
	h.add_child(pad)
	var dot := _label("●" if filled else "○", 12, C_ACCENT if filled else C_MUTED)
	h.add_child(dot)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", -2)
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(v)
	v.add_child(_label(title, 14, C_TEXT if filled else C_MUTED))
	v.add_child(_label(sub, 11, C_MUTED))
	row.gui_input.connect(func(ev: InputEvent) -> void:
		if ev is InputEventMouseButton and (ev as InputEventMouseButton).pressed and (ev as InputEventMouseButton).button_index == MOUSE_BUTTON_RIGHT:
			if _draft.has(key):
				_remove(key)
			return
		if ev is InputEventMouseButton and (ev as InputEventMouseButton).pressed and (ev as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
			if key == "@mag":
				_tab = "mag"
				_sel = "@mag"
				_refresh()
				return
			_select(key)
			if (ev as InputEventMouseButton).double_click and _view.space():
				_view.focus(WeaponMods.point_frame(_view.space(), WeaponBuild.model_of(String(_weapon.id)), BuildPlan.clean(_draft), key).origin))
	_tree_box.add_child(row)


func _refresh_actions() -> void:
	for c: Node in _actions.get_children():
		c.queue_free()
	if not _draft.has(_sel):
		if _sel != "" and _sel != "@mag":
			_actions.add_child(_label("Выбери деталь снизу — встанет сюда.", 12, C_MUTED))
		return
	var id: String = WeaponDb.mod_id(_draft[_sel])
	var key: String = _sel
	_actions.add_child(_button("Снять  ПКМ", func() -> void: _remove(key)))
	if not AttachmentRemote.spec(id).is_empty():
		_actions.add_child(_label("Пульт: отдельная планка", 12, C_MUTED))
		var selector: OptionButton = OptionButton.new()
		var choices: Array[Dictionary] = AttachmentRemote.options(String(_weapon.id), BuildPlan.clean(_draft), key)
		var current: Dictionary = (_draft[key] as Dictionary).get("remote", {})
		for i: int in range(choices.size()):
			var place: Dictionary = choices[i]
			selector.add_item("%s · паз %d · %s" % [String(WeaponDb.MOUNT_NAMES.get(String(place.point), place.point)), int(place.slot) + 1, "к прикладу" if bool(place.reverse) else "к дулу"])
			if String(place.point) == String(current.get("point", "")) and int(place.slot) == int(current.get("slot", -1)) and bool(place.reverse) == bool(current.get("reverse", false)):
				selector.select(i)
		selector.item_selected.connect(func(i: int) -> void: _move_remote(key, choices[i]))
		_actions.add_child(selector)
	var pt: Dictionary = WeaponBuild.point(String(_weapon.id), BuildPlan.clean(_draft), key)
	if WeaponBuild.is_rail(pt):
		_actions.add_child(_button("◀ паз", func() -> void: _nudge(-1)))
		_actions.add_child(_button("паз ▶", func() -> void: _nudge(1)))
		var rec: Dictionary = _draft[key]
		var move: Callable = func() -> void: _begin_place(key, {"id": id, "src": rec.src, "item": rec}, int(rec.get("slot", 0)), true)
		_actions.add_child(_button("Двигать мышью", move))
	var spec: Dictionary = (WeaponDb.attachment(id).get("provides", {}) as Dictionary).get("rail", {})
	if bool(spec.get("flip", false)):
		_actions.add_child(_button("Другая сторона  R", _flip))
	if spec.has("angle"):
		_actions.add_child(_button("Угол −  Q", func() -> void: _turn(-1)))
		_actions.add_child(_button("Угол +  E", func() -> void: _turn(1)))


func _bind_remotes() -> void:
	var resolved: Dictionary = AttachmentRemote.resolve(String(_weapon.id), _draft)
	if String(resolved.why) == "":
		_draft = resolved.mods


func _move_remote(key: String, place: Dictionary) -> void:
	if not _draft.has(key):
		return
	var probe: Dictionary = _draft_entry()
	(probe.mods[key] as Dictionary)["remote"] = {"point": String(place.point), "slot": int(place.slot), "reverse": bool(place.get("reverse", false))}
	var why: String = WeaponBuild.block(probe, key, WeaponDb.mod_id(probe.mods[key]))
	if why != "":
		_say(why)
		return
	_push()
	(_draft[key] as Dictionary)["remote"] = (probe.mods[key] as Dictionary).remote.duplicate()
	_refresh()


func _refresh_stats(preview: Dictionary = {}) -> void:
	for c: Node in _stats_box.get_children():
		c.queue_free()
	var before: Dictionary = WeaponStats.compute(_weapon)
	var now_entry: Dictionary = _draft_entry(_place_mods() if not _place.is_empty() else _draft)
	var now: Dictionary = WeaponStats.compute(now_entry)
	var after: Dictionary = WeaponStats.compute(preview) if not preview.is_empty() else now
	var rb: Array = WeaponStats.rows(before)
	var ra: Array = WeaponStats.rows(after)
	for i in range(ra.size()):
		var r: Array = ra[i]
		var b: Array = rb[i]
		var row := VBoxContainer.new()
		row.add_theme_constant_override("separation", 2)
		var top := HBoxContainer.new()
		var name := _label(String(r[0]), 13, C_TEXT)
		name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		top.add_child(name)
		var delta: float = float(r[1]) - float(b[1])
		var better: bool = (delta > 0.0) == bool(r[3])
		var vtext: String = String(r[4]) % float(r[1])
		if absf(delta) > 0.0001 and absf(delta) > absf(float(b[1])) * 0.002:
			var dl := _label(("+" if delta > 0 else "−") + (String(r[4]) % absf(delta)).get_slice(" ", 0) + "  ", 12, C_OK if better else C_BAD)
			top.add_child(dl)
		top.add_child(_label(vtext, 13, C_ACCENT))
		row.add_child(top)
		var bar := _Bar.new()
		bar.value = clampf(float(r[2]) / 100.0, 0.0, 1.0)
		bar.base = clampf(float(b[2]) / 100.0, 0.0, 1.0)
		bar.custom_minimum_size = Vector2(0, 6)
		row.add_child(bar)
		_stats_box.add_child(row)
	_stats_box.add_child(_label("Вес %.2f кг  ·  было %.2f" % [float(after.weight), float(before.weight)], 12, C_MUTED))
	var sights: Array = WeaponStats.sights_of(now_entry)
	if sights.size() > 1:
		_stats_box.add_child(_label("Прицелов: %d — переключение СКМ" % sights.size(), 12, C_MUTED))


func _refresh_strip() -> void:
	for c: Node in _tabs_box.get_children():
		c.queue_free()
	for c2: Node in _source_box.get_children():
		c2.queue_free()
	for c4: Node in _filter_box.get_children():
		c4.queue_free()
	if _sel != "" and _sel != "@mag":
		var mods: Dictionary = BuildPlan.clean(_draft)
		var where_text: String = WeaponBuild.label(String(_weapon.id), mods, _sel) if not _draft.has(_sel) or _sel_add else ItemDb.item_name(WeaponDb.mod_id(mods[_sel]))
		var clear: Callable = func() -> void: _select("")
		_filter_box.add_child(_button(("ещё на: " if _sel_add else ("замена: " if _draft.has(_sel) else "для точки: ")) + where_text + "   ✕", clear, true))
	for c3: Node in _strip.get_children():
		c3.queue_free()
	for t: Array in TABS:
		var tid: String = String(t[0])
		var pick_tab: Callable = func() -> void: _pick_tab(tid)
		_tabs_box.add_child(_button(String(t[1]), pick_tab, tid == _tab))
	if mode == "hideout":
		var mine: Callable = func() -> void: _pick_source("mine")
		var shop: Callable = func() -> void: _pick_source("shop")
		_source_box.add_child(_button("Мои вещи", mine, _source == "mine"))
		_source_box.add_child(_button("У Михалыча", shop, _source == "shop"))
	var sort_names: Dictionary = {"": "Цена: как лежат", "up": "Цена ↑ дешёвые", "down": "Цена ↓ дорогие"}
	var next_sort: Callable = func() -> void:
		_sort = {"": "up", "up": "down", "down": ""}[_sort]
		_refresh()
	_source_box.add_child(_button(String(sort_names[_sort]), next_sort, _sort != ""))
	if _tab == "mag":
		_mag_strip()
		return
	var e: Dictionary = _draft_entry()
	var any: bool = false
	var pool: Array[Dictionary] = _pool()
	if _sort != "":
		# по цене: у Михалыча — за сколько продаст, своё — сколько стоит
		var up: bool = _sort == "up"
		pool.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
			var pa: int = int(a.get("price", ItemDb.value(String(a.id))))
			var pb: int = int(b.get("price", ItemDb.value(String(b.id))))
			return pa < pb if up else pa > pb)
	for part: Dictionary in pool:
		var id: String = String(part.id)
		if _tab != "all" and tab_of(id) != _tab:
			continue
		# подходит ли хоть куда (или в выбранную точку)
		var t: Dictionary = _target_for(part)
		if String(t.get("key", "")) == "" and _sel != "":
			continue
		if WeaponBuild.candidate_keys(e, id).is_empty() and _sel == "":
			continue
		any = true
		_strip.add_child(_part_card(part, String(t.get("why", ""))))
	if not any:
		_strip.add_child(_label("Подходящих деталей нет" + (" у Михалыча" if _source == "shop" else " в вещах") + (" для этой точки" if _sel != "" else "") + ".", 13, C_MUTED))


func _pick_tab(tid: String) -> void:
	_tab = tid
	if tid == "mag":
		_sel = "@mag"
	elif _sel == "@mag":
		_sel = ""
	_refresh()


func _pick_source(src: String) -> void:
	_source = src
	_refresh()


func _part_card(part: Dictionary, why: String) -> Control:
	var card := PanelContainer.new()
	var lock: String = String(part.get("lock", ""))
	var cant: bool = why != "" or lock != ""
	card.add_theme_stylebox_override("panel", _panel(C_CARD, 8, 8))
	card.custom_minimum_size = Vector2(200, 96)
	card.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	card.tooltip_text = "%s\n%s" % [ItemDb.item_name(String(part.id)), String(WeaponDb.attachment(String(part.id)).get("desc", ""))]
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 2)
	card.add_child(v)
	var icon := ItemCard.IconBox.new()
	icon.id = String(part.id)
	icon.custom_minimum_size = Vector2(0, 40)
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	v.add_child(icon)
	var name := _label(ItemDb.item_name(String(part.id)), 13, C_TEXT)
	name.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	name.custom_minimum_size.x = 184
	v.add_child(name)
	v.add_child(_label(String(part.get("sub", "")), 11, C_SHOP if String(part.src.from) == "shop" else C_MUTED))
	if cant:
		v.add_child(_label(lock if lock != "" else why, 11, C_BAD))
		card.modulate = Color(1, 1, 1, 0.6)
	card.mouse_entered.connect(func() -> void:
		(card.get_theme_stylebox("panel") as StyleBoxFlat).bg_color = C_CARD_HI
		_hover = part
		_preview_hover())
	card.mouse_exited.connect(func() -> void:
		(card.get_theme_stylebox("panel") as StyleBoxFlat).bg_color = C_CARD
		if _hover == part:
			_hover = {}
			_refresh_stats()
			_overlay.queue_redraw())
	card.gui_input.connect(func(ev: InputEvent) -> void:
		if ev is InputEventMouseButton and (ev as InputEventMouseButton).pressed and (ev as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
			_choose(part))
	return card


## Наведение на деталь: «стало бы» в характеристиках и подсветка точек, куда она встаёт.
func _preview_hover() -> void:
	if _hover.is_empty() or not _place.is_empty():
		return
	var t: Dictionary = _target_for(_hover)
	if String(t.get("key", "")) == "" or String(t.get("why", "")) != "":
		_refresh_stats()
		_overlay.queue_redraw()
		return
	var mods: Dictionary = _draft.duplicate(true)
	for k: String in WeaponBuild.subtree(mods, String(t.key)):
		mods.erase(k)
	var rec: Dictionary = {"id": String(_hover.id), "src": _hover.src}
	if bool(t.get("rail", false)):
		rec["slot"] = int(t.slot)
	mods[String(t.key)] = rec
	_refresh_stats(_draft_entry(mods))
	var warning: String = WeaponBuild.sight_warning(_draft_entry(), String(t.key), String(_hover.id), int(t.get("slot", -1)))
	if warning != "" and _status_t <= 0.0:
		_status.text = warning
		_status.add_theme_color_override("font_color", C_ACCENT)
	_overlay.queue_redraw()


func _mag_strip() -> void:
	var w: Dictionary = WeaponDb.weapon(String(_weapon.id))
	if w.has("internal_mag") or not w.has("mag_if"):
		_strip.add_child(_label("Магазин встроенный.", 13, C_MUTED))
		return
	var cur: Dictionary = _draft_entry().get("mag", {})
	if String(cur.get("id", "")) != "":
		var take_out: Callable = func() -> void: _set_mag({"from": "none"})
		_strip.add_child(_simple_card("Вынуть магазин", "останется пустая шахта", take_out))
	if String(_mag.get("from", "weapon")) != "weapon":
		var own: Dictionary = _weapon.get("mag", {})
		var keep_own: Callable = func() -> void: _set_mag({"from": "weapon"})
		_strip.add_child(_simple_card("Вернуть свой", ItemDb.item_name(String(own.get("id", ""))) if String(own.get("id", "")) != "" else "без магазина", keep_own))
	var lists: Dictionary = _lists()
	for ln: Variant in lists:
		var list: Array = lists[ln]
		for i in range(list.size()):
			var e: Dictionary = list[i]
			if not WeaponDb.mag_fits(String(_weapon.id), String(e.id)):
				continue
			var li: int = i
			var lname: String = String(ln)
			var cap: int = int(WeaponDb.magazine(String(e.id)).get("capacity", 0))
			var put_in: Callable = func() -> void: _set_mag({"from": lname, "idx": li})
			_strip.add_child(_simple_card(ItemDb.item_name(String(e.id)), "%s · %s" % [_list_name(lname),
				Gear.ammo_estimate(int(e.get("rounds", 0)), cap, false)], put_in, String(e.id)))


static func _list_name(list_name: String) -> String:
	return {"stash": "тайник", "backpack": "рюкзак", "sandbox": "любой, без покупки"}.get(list_name, list_name)


func _set_mag(mag: Dictionary) -> void:
	_push()
	_mag = mag
	_refresh()


func _simple_card(title: String, sub: String, action: Callable, icon_id: String = "") -> Control:
	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", _panel(C_CARD, 8, 8))
	card.custom_minimum_size = Vector2(190, 96)
	card.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	var v := VBoxContainer.new()
	card.add_child(v)
	if icon_id != "":
		var icon := ItemCard.IconBox.new()
		icon.id = icon_id
		icon.custom_minimum_size = Vector2(0, 40)
		icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
		v.add_child(icon)
	v.add_child(_label(title, 13, C_TEXT))
	v.add_child(_label(sub, 11, C_MUTED))
	card.gui_input.connect(func(ev: InputEvent) -> void:
		if ev is InputEventMouseButton and (ev as InputEventMouseButton).pressed and (ev as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
			action.call())
	return card


func _refresh_footer() -> void:
	var changed: bool = _draft != BuildPlan.draft_of(_weapon) or String(_mag.get("from", "weapon")) != "weapon"
	_undo_btn.disabled = _undo.is_empty()
	_redo_btn.disabled = _redo.is_empty()
	var why: String = String(_plan.get("why", ""))
	_apply_btn.disabled = not changed or why != ""
	if not changed:
		_summary.text = "Сборка как есть. Выбери точку на модели или деталь снизу."
		_summary.add_theme_color_override("font_color", C_MUTED)
	else:
		var parts: Array[String] = []
		var buy: Array = _plan.get("buy", [])
		if not buy.is_empty():
			parts.append("купить: %d на %s ₽" % [buy.size(), InventoryUI.money(BuildPlan.cost(buy))])
		var taken: int = 0
		for t: Variant in _plan.get("take", []):
			taken += 1
		if taken > 0:
			parts.append("взять из вещей: %d" % taken)
		var back: Array = _plan.get("returned", [])
		if not back.is_empty():
			parts.append("снятое → %s: %d" % ["тайник" if mode == "hideout" else "рюкзак", back.size()])
		_summary.text = "Изменения: " + (", ".join(parts) if not parts.is_empty() else "перестановка")
		_summary.add_theme_color_override("font_color", C_TEXT)
		if mode == "hideout" and BuildPlan.cost(buy) > Profile.money:
			why = "не хватает денег (%s ₽)" % InventoryUI.money(Profile.money)
			_apply_btn.disabled = true
	if _status_t <= 0.0:
		var warnings: Array[String] = WeaponBuild.sight_warnings(_draft_entry())
		_status.text = why if why != "" else (warnings[0] if not warnings.is_empty() else "")
		_status.tooltip_text = "\n".join(warnings)
		_status.add_theme_color_override("font_color", C_BAD if why != "" else C_ACCENT)


func _say(text: String, good: bool = false) -> void:
	_status.text = text
	_status.add_theme_color_override("font_color", C_OK if good else C_BAD)
	_status_t = 3.0


func _apply() -> void:
	if _apply_btn.disabled:
		return
	if mode == "raid":
		if Raid.current:
			Raid.current.request_build(where, idx, _draft, _mag)
		_close()
		return
	if mode == "sandbox":
		var entry: Dictionary = (_plan.get("entry", {}) as Dictionary).duplicate(true)
		if entry.is_empty() or _player == null or not is_instance_valid(_player):
			return
		_player.set_range_weapon(entry, _player.range_own_slot)
		_weapon = _current_weapon()
		_draft = BuildPlan.draft_of(_weapon)
		_mag = {"from": "weapon"}
		_undo.clear()
		_redo.clear()
		_place = {}
		Audio.play_ui("mod_fit")
		_say("Собрано — в руках.", true)
		_refresh()
		return
	var why: String = Profile.apply_build(where, idx, _draft, _mag)
	if why != "":
		_say("Не собрано: " + why)
		return
	_weapon = _current_weapon()
	_draft = BuildPlan.draft_of(_weapon)
	_mag = {"from": "weapon"}
	_undo.clear()
	_redo.clear()
	_place = {}
	Audio.play_ui("mod_fit")
	_say("Собрано.", true)
	_refresh()


func _close() -> void:
	closed.emit()
	queue_free()


func _set_view(view: String) -> void:
	if view != "eye":
		_view.set_view(view)
		return
	# из глаза — по линии выбранного прицела: окуляр (или задняя часть оружия) и крен прицела
	var m: Node3D = _view.space()
	if m == null:
		return
	var e: Dictionary = _draft_entry()
	var sight: String = WeaponStats.active_sight(e)
	# выбран прицел в сборке — смотрим через него
	if _sel in WeaponStats.sights_of(e):
		sight = _sel
	elif _sel != "" and _sel == WeaponBuild.primary_key(e.mods):
		sight = "primary"
	var lines: Dictionary = m.get_meta("sights", {})
	var line: Dictionary = lines.get(sight, lines.get("primary", {}))
	var roll: float = float(line.get("roll", 0.0))
	# глаз — в 30 см за окуляром (основной) или за коробкой: видно и прицел, и посадку на планке
	var oz: float = (m.get_meta("ocular", Vector3(0, 0, 0.0)) as Vector3).z - 0.3 if sight == "primary" else -0.28
	var up := Vector3(-sin(roll), cos(roll), 0.0)
	var eye := Vector3(float(line.get("x", 0.0)), float(line.get("h", m.get_meta("sight_h", 0.08))), oz)
	_view.set_view("eye", Transform3D(Basis.looking_at(Vector3.BACK, up), eye))


# ---------------------------------------------------------------- точки и карточки

func _process(delta: float) -> void:
	if _status_t > 0.0:
		_status_t -= delta
		if _status_t <= 0.0:
			_refresh_footer()
	_layout_spots()
	_hint.visible = not _place.is_empty()
	if not _place.is_empty():
		var ok: bool = bool(_place.get("ok", false))
		_hint.text = ("✓ паз %d — клик или СКМ, чтобы поставить" % (int(_place.slot) + 1)) if ok else ("✕ " + String(_place.get("why", "")))
		_hint.add_theme_color_override("font_color", C_OK if ok else C_BAD)


## Точки на модели: занятые (что стоит), свободные (пусто), «ещё на планку» (+).
func _layout_spots() -> void:
	_spots.clear()
	var space: Node3D = _view.space()
	if space == null or _weapon.is_empty():
		return
	var model_key: String = WeaponBuild.model_of(String(_weapon.id))
	var mods: Dictionary = BuildPlan.clean(_draft)
	var wid: String = String(_weapon.id)
	var fits: Array = WeaponDb.attachment(String(_hover.get("id", ""))).get("fits", []) if not _hover.is_empty() else []
	var points: Array[String] = []
	for m: Variant in WeaponDb.mounts_of(wid):
		if WeaponMods.socket(model_key, String(m)).is_empty():
			continue
		points.append(String(m))
	for k: String in WeaponBuild.sorted_keys(mods):
		for p: Variant in (WeaponDb.attachment(WeaponDb.mod_id(mods[k])).get("provides", {}) as Dictionary):
			points.append(k + WeaponBuild.SEP + String(p))
	for k: String in WeaponBuild.sorted_keys(mods):
		var xf: Transform3D = WeaponMods.point_frame(space, model_key, mods, k)
		_spot(k, xf.origin + xf.basis.y.normalized() * 0.012, ItemDb.item_name(WeaponDb.mod_id(mods[k])), WeaponBuild.label(wid, mods, k), true, false, fits)
		var rec: Dictionary = mods[k] if mods[k] is Dictionary else {}
		if not AttachmentRemote.spec(WeaponDb.mod_id(rec)).is_empty() and rec.has("remote"):
			var rf: Transform3D = AttachmentRemote.remote_frame(model_key, rec)
			_spot(k, rf.origin + rf.basis.y * 0.012, "Пульт МЕТКА-4", String(WeaponDb.MOUNT_NAMES.get(String(rec.remote.point), rec.remote.point)), true, false, fits)
	for pk: String in points:
		var pt: Dictionary = WeaponBuild.point(wid, mods, pk)
		if pt.is_empty():
			continue
		var occupied: bool = false
		for k: Variant in mods:
			if WeaponBuild.point_key(String(k)) == pk:
				occupied = true
			var rec: Dictionary = mods[k] if mods[k] is Dictionary else {}
			if not AttachmentRemote.spec(WeaponDb.mod_id(rec)).is_empty() and String((rec.get("remote", {}) as Dictionary).get("point", "")) == pk:
				occupied = true
		var xf2: Transform3D = WeaponMods.point_frame(space, model_key, mods, pk)
		var label: String = String(WeaponDb.MOUNT_NAMES.get(WeaponBuild.base_of(pk), WeaponBuild.POINT_NAMES.get(WeaponBuild.base_of(pk), pk)))
		if not occupied:
			_spot(pk, xf2.origin, label, "пусто", false, false, fits, String(pt.iface))
		elif WeaponBuild.is_rail(pt):
			# свободный участок планки — «ещё одно устройство»
			var free_z: float = _free_gap(model_key, mods, pk, pt)
			if not is_nan(free_z):
				var mid: float = (float(pt.rail[0]) + float(pt.rail[1])) * 0.5
				var at: Vector3 = xf2 * Vector3(0, 0, free_z - mid)
				_spot(pk, at, label, "ещё на планку", false, true, fits, String(pt.iface))
	_place_cards()
	_overlay.queue_redraw()


## Середина самого длинного свободного участка планки (NAN — места нет).
func _free_gap(model_key: String, mods: Dictionary, pk: String, pt: Dictionary) -> float:
	var spans: Array = []
	for k: Variant in mods:
		if WeaponBuild.point_key(String(k)) == pk:
			var s: Vector2 = WeaponBuild.span(model_key, mods, String(k))
			spans.append(s)
		var rec: Dictionary = mods[k] if mods[k] is Dictionary else {}
		if not AttachmentRemote.spec(WeaponDb.mod_id(rec)).is_empty() and String((rec.get("remote", {}) as Dictionary).get("point", "")) == pk:
			spans.append(AttachmentRemote.remote_span(model_key, rec))
	spans.sort_custom(func(a: Vector2, b: Vector2) -> bool: return a.x < b.x)
	var best: float = NAN
	var best_len: float = WeaponBuild.SLOT_M
	var cur: float = float(pt.rail[0])
	spans.append(Vector2(float(pt.rail[1]), float(pt.rail[1])))
	for s2: Variant in spans:
		var gap: float = (s2 as Vector2).x - cur
		if gap >= best_len:
			best_len = gap
			best = cur + gap * 0.5
		cur = maxf(cur, (s2 as Vector2).y)
	return best


func _spot(key: String, p: Vector3, title: String, sub: String, filled: bool, add: bool, fits: Array, iface: String = "") -> void:
	if _view.behind(p):
		return
	var match_hover: bool = false
	if not fits.is_empty():
		var pt_iface: String = iface if iface != "" else String(WeaponBuild.point(String(_weapon.id), BuildPlan.clean(_draft), key).get("iface", ""))
		match_hover = pt_iface in fits
	_spots.append({"key": key, "pos": _view.project(p), "title": title, "sub": sub, "filled": filled, "add": add,
		"hot": match_hover, "lock": _locked(key) != ""})


## Карточки по краям студии: слева — точки левой половины, справа — правой, без наложений.
func _place_cards() -> void:
	var w: float = _cards.size.x
	var h: float = _cards.size.y
	var sides: Dictionary = {"l": [], "r": []}
	for i in range(_spots.size()):
		var s: Dictionary = _spots[i]
		if bool(s.add):
			continue
		(sides["l" if (s.pos as Vector2).x < w * 0.5 else "r"] as Array).append(i)
	var used: int = 0
	for side: String in ["l", "r"]:
		var list: Array = sides[side]
		list.sort_custom(func(a: int, b: int) -> bool: return (_spots[a].pos as Vector2).y < (_spots[b].pos as Vector2).y)
		var y: float = 8.0
		var total: float = list.size() * (CARD.y + 6.0)
		var start: float = clampf(h * 0.5 - total * 0.5, 8.0, maxf(8.0, h - total - 8.0))
		y = start
		for i: int in list:
			var want: float = clampf((_spots[i].pos as Vector2).y - CARD.y * 0.5, y, h - CARD.y - 8.0)
			var x: float = 10.0 if side == "l" else w - CARD.x - 10.0
			_spots[i]["card"] = Rect2(Vector2(x, want), CARD)
			y = want + CARD.y + 6.0
			used += 1
	# кнопки-карточки: переиспользуем узлы
	var buttons: Array[Node] = _cards.get_children()
	var n: int = 0
	for s2: Dictionary in _spots:
		if not s2.has("card"):
			continue
		var btn: _SpotCard
		if n < buttons.size():
			btn = buttons[n] as _SpotCard
		else:
			btn = _SpotCard.new()
			btn.owner_builder = self
			_cards.add_child(btn)
		btn.visible = true
		btn.setup(s2, s2.key == _sel)
		n += 1
	for j in range(n, buttons.size()):
		(buttons[j] as Control).visible = false


func _draw_overlay() -> void:
	# линии от точек к карточкам, сами точки, планка в режиме установки
	for s: Dictionary in _spots:
		var p: Vector2 = s.pos
		var col: Color = C_OK if bool(s.hot) else (C_ACCENT if bool(s.filled) else Color(0.85, 0.85, 0.82, 0.7))
		if bool(s.lock):
			col = Color(0.6, 0.6, 0.6, 0.5)
		if s.has("card"):
			var r: Rect2 = s.card
			var to := Vector2(r.position.x + (r.size.x if r.position.x < p.x else 0.0), r.position.y + r.size.y * 0.5)
			var knee := Vector2(lerpf(to.x, p.x, 0.35), to.y)
			_overlay.draw_polyline(PackedVector2Array([p, knee, to]), Color(col, 0.55), 1.4, true)
		var radius: float = 6.0 if not bool(s.add) else 7.5
		if bool(s.filled):
			_overlay.draw_circle(p, radius, Color(col, 0.9))
			_overlay.draw_circle(p, radius - 2.5, Color(0.05, 0.05, 0.05, 0.9))
			_overlay.draw_circle(p, radius - 4.0, col)
		else:
			_overlay.draw_arc(p, radius, 0.0, TAU, 24, col, 1.8, true)
			if bool(s.add):
				_overlay.draw_line(p + Vector2(-3.5, 0), p + Vector2(3.5, 0), col, 1.6)
				_overlay.draw_line(p + Vector2(0, -3.5), p + Vector2(0, 3.5), col, 1.6)
		if String(s.key) == _sel and _sel_add == bool(s.add):
			_overlay.draw_arc(p, radius + 5.0, 0.0, TAU, 32, Color(1, 1, 1, 0.85), 1.5, true)
	if not _place.is_empty() and _view.space():
		var ends: Array[Vector3] = WeaponMods.rail_ends(_view.space(), WeaponBuild.model_of(String(_weapon.id)), BuildPlan.clean(_place_mods()), String(_place.key))
		if ends.size() == 2:
			var a: Vector2 = _view.project(ends[0])
			var b: Vector2 = _view.project(ends[1])
			var ok: bool = bool(_place.get("ok", false))
			_overlay.draw_line(a, b, Color(C_OK if ok else C_BAD, 0.85), 3.0, true)
			# риски пазов
			var g: Dictionary = WeaponBuild.geo(WeaponBuild.model_of(String(_weapon.id)), BuildPlan.clean(_place_mods()), String(_place.key))
			var length: float = float(g.rail[1]) - float(g.rail[0])
			var n: int = int(length / WeaponBuild.SLOT_M)
			for i in range(n + 1):
				var t: float = float(i) * WeaponBuild.SLOT_M / maxf(length, 0.001)
				var q: Vector2 = a.lerp(b, t)
				var nrm: Vector2 = (b - a).orthogonal().normalized() * 4.0
				_overlay.draw_line(q - nrm, q + nrm, Color(1, 1, 1, 0.5), 1.0)


# ---------------------------------------------------------------- клавиши

func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey) or not (event as InputEventKey).pressed:
		return
	var k := event as InputEventKey
	match k.keycode:
		KEY_ESCAPE:
			if not _place.is_empty():
				_end_place()
			elif _sel != "":
				_sel = ""
				_refresh()
			else:
				_close()
		KEY_Z:
			if k.ctrl_pressed and k.shift_pressed:
				_do_redo()
			elif k.ctrl_pressed:
				_do_undo()
		KEY_Y:
			if k.ctrl_pressed:
				_do_redo()
		KEY_DELETE, KEY_BACKSPACE:
			if _draft.has(_sel):
				_remove(_sel)
		KEY_LEFT:
			_nudge(-1)
		KEY_RIGHT:
			_nudge(1)
		KEY_R:
			_flip()
		KEY_Q:
			_turn(-1)
		KEY_E:
			_turn(1)
		KEY_F:
			_view.set_view("q")
		KEY_ENTER, KEY_KP_ENTER:
			if not _place.is_empty():
				_confirm_place()
			else:
				_apply()
		_:
			return
	get_viewport().set_input_as_handled()


func _gui_input(event: InputEvent) -> void:
	# колесо в установке — на паз
	if not _place.is_empty() and event is InputEventMouseButton and (event as InputEventMouseButton).pressed:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_WHEEL_UP:
			_nudge(1)
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			_nudge(-1)
		elif mb.button_index == MOUSE_BUTTON_RIGHT:
			_end_place()


func _input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton):
		return
	var mb := event as InputEventMouseButton
	# средняя кнопка мимо студии (над деталями, деревом) — то же «поставить / применить»;
	# над студией её щелчок приходит от самой студии (протяжка там двигает модель)
	if mb.pressed and mb.button_index == MOUSE_BUTTON_MIDDLE and not _view.get_global_rect().has_point(mb.global_position):
		_middle_click()
		get_viewport().set_input_as_handled()
		return
	# колесо над студией в режиме установки сдвигает по пазам (студия его не берёт)
	if _place.is_empty():
		return
	if not mb.pressed or not _view.get_global_rect().has_point(mb.global_position):
		return
	if mb.button_index == MOUSE_BUTTON_WHEEL_UP:
		_nudge(1)
		get_viewport().set_input_as_handled()
	elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
		_nudge(-1)
		get_viewport().set_input_as_handled()
	elif mb.button_index == MOUSE_BUTTON_RIGHT:
		_end_place()
		get_viewport().set_input_as_handled()


# ---------------------------------------------------------------- мелкие элементы

## Полоса характеристики: заливка — сейчас, тонкая метка — как было.
class _Bar:
	extends Control
	var value: float = 0.0
	var base: float = 0.0

	func _draw() -> void:
		var r := Rect2(Vector2.ZERO, size)
		draw_rect(r, Color(1, 1, 1, 0.07))
		var col: Color = Color(0.96, 0.74, 0.38)
		if value > base + 0.002:
			col = Color(0.45, 0.88, 0.55)
		elif value < base - 0.002:
			col = Color(0.96, 0.42, 0.34)
		draw_rect(Rect2(Vector2.ZERO, Vector2(size.x * minf(value, base), size.y)), Color(0.96, 0.74, 0.38, 0.85))
		if not is_equal_approx(value, base):
			var a: float = size.x * minf(value, base)
			var b: float = size.x * maxf(value, base)
			draw_rect(Rect2(Vector2(a, 0), Vector2(b - a, size.y)), col)
		draw_rect(Rect2(Vector2(size.x * base - 1.0, -2.0), Vector2(2.0, size.y + 4.0)), Color(1, 1, 1, 0.6))


## Карточка точки у края студии: иконка детали или «пусто», имя, где стоит.
class _SpotCard:
	extends PanelContainer
	var owner_builder: WeaponBuilder
	var key: String = ""
	var add: bool = false
	var _icon: ItemCard.IconBox
	var _t: Label
	var _s: Label
	var _style: StyleBoxFlat

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_STOP
		mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
		_style = StyleBoxFlat.new()
		_style.set_corner_radius_all(7)
		_style.set_border_width_all(1)
		_style.set_content_margin_all(6)
		add_theme_stylebox_override("panel", _style)
		var h := HBoxContainer.new()
		h.add_theme_constant_override("separation", 8)
		add_child(h)
		_icon = ItemCard.IconBox.new()
		_icon.custom_minimum_size = Vector2(52, 36)
		_icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
		h.add_child(_icon)
		var v := VBoxContainer.new()
		v.add_theme_constant_override("separation", -2)
		v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		h.add_child(v)
		_t = Label.new()
		_t.add_theme_font_size_override("font_size", 13)
		_t.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		_t.custom_minimum_size.x = 96
		v.add_child(_t)
		_s = Label.new()
		_s.add_theme_font_size_override("font_size", 11)
		_s.add_theme_color_override("font_color", Color(0.58, 0.59, 0.58))
		_s.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		_s.custom_minimum_size.x = 96
		v.add_child(_s)

	func setup(s: Dictionary, selected: bool) -> void:
		key = String(s.key)
		add = bool(s.add)
		var r: Rect2 = s.card
		position = r.position
		size = r.size
		custom_minimum_size = r.size
		var filled: bool = bool(s.filled)
		var mods: Dictionary = BuildPlan.clean(owner_builder._draft)
		var id: String = WeaponDb.mod_id(mods.get(key, "")) if filled else ""
		if _icon.id != id:
			_icon.id = id
			_icon.queue_redraw()
		_icon.visible = filled
		_t.text = String(s.title)
		_t.add_theme_color_override("font_color", Color(0.93, 0.91, 0.87) if filled else Color(0.75, 0.75, 0.72))
		_s.text = ("🔒 " if bool(s.lock) else "") + String(s.sub)
		_style.bg_color = Color(0.96, 0.74, 0.38, 0.18) if selected else Color(0.08, 0.082, 0.088, 0.92)
		_style.border_color = Color(0.45, 0.88, 0.55, 0.8) if bool(s.hot) else (Color(0.96, 0.74, 0.38, 0.7) if selected else Color(1, 1, 1, 0.08))

	func _gui_input(event: InputEvent) -> void:
		if event is InputEventMouseButton and (event as InputEventMouseButton).pressed and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
			owner_builder._select(key, add)
			accept_event()
		elif event is InputEventMouseButton and (event as InputEventMouseButton).pressed and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_RIGHT:
			if owner_builder._place.is_empty() and owner_builder._draft.has(key):
				owner_builder._remove(key)
			accept_event()
