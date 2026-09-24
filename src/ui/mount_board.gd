class_name MountBoard
extends Control
## Схема оружия: ствол сбоку (WeaponPreview), от каждой точки крепления — луч к квадратику-слоту.
## В слоте — что стоит (иконка) или пусто. Клик — список подходящего: candidates.call(точка) →
## [{id, sub, act, action: Callable, why}] (why — почему нельзя, "" — можно); у стоящего — «Снять»
## (remove.call(точка)). Один и тот же для торговца (купить и поставить, из наличия) и верстака
## (из тайника и рюкзака). Точки — из данных (WeaponDb.mounts_of + sockets основы модели).

const SLOT := Vector2(84, 70)
const SHORT := {"optic_primary": "Прицел", "optic_offset": "Угловой", "muzzle": "Дуло", "underbarrel": "Под цевьё",
	"side_left": "Слева", "side_right": "Справа", "stock": "Приклад"}
## Какие точки — над стволом (остальные — под).
const TOP := ["optic_primary", "optic_offset", "muzzle"]

var candidates: Callable
var remove: Callable

var _entry: Dictionary = {}
var _preview: WeaponPreview
var _slots: Dictionary = {}
var _anchor: Dictionary = {}
var _last_size: Vector2 = Vector2.ZERO
var _popup: PopupPanel


func _init() -> void:
	custom_minimum_size = Vector2(620, 430)
	clip_contents = true


func _ready() -> void:
	_preview = WeaponPreview.new()
	_preview.spin = false
	add_child(_preview)
	_preview.custom_minimum_size = Vector2.ZERO
	_layout_preview()
	if not _entry.is_empty():
		setup(_entry)


func setup(entry: Dictionary) -> void:
	_entry = entry
	if _preview == null:
		return
	for b in _slots.values():
		(b as Node).queue_free()
	_slots.clear()
	_preview.show_weapon(String(entry.get("id", "")), entry.get("mods", {}))
	var mods: Dictionary = entry.get("mods", {})
	var mounts := WeaponDb.mounts_of(String(entry.get("id", "")))
	for m in WeaponDb.MOUNTS:
		if not mounts.has(m):
			continue
		var mount := String(m)
		var b := Button.new()
		b.focus_mode = Control.FOCUS_NONE
		b.custom_minimum_size = SLOT
		b.size = SLOT
		b.add_theme_font_size_override("font_size", 12)
		b.text = String(SHORT.get(mount, mount))
		b.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
		b.vertical_icon_alignment = VERTICAL_ALIGNMENT_TOP
		b.expand_icon = true
		var id := WeaponDb.mod_id(mods.get(mount, ""))
		if id != "":
			b.icon = ItemIcons.get_icon(id)
			b.tooltip_text = "%s [%s]\n%s" % [String(WeaponDb.MOUNT_NAMES.get(mount, mount)), String(mounts[mount]), ItemDb.item_name(id)]
		else:
			b.tooltip_text = "%s [%s]\nпусто" % [String(WeaponDb.MOUNT_NAMES.get(mount, mount)), String(mounts[mount])]
		b.modulate = Color(1, 1, 1) if id != "" else Color(0.75, 0.75, 0.72)
		b.pressed.connect(func() -> void: _open(mount, b))
		add_child(b)
		_slots[mount] = b
	_last_size = Vector2.ZERO


func _layout_preview() -> void:
	# витрина — средняя полоса, слоты — над и под ней
	_preview.position = Vector2(0, SLOT.y + 24)
	_preview.size = Vector2(size.x, maxf(size.y - (SLOT.y + 24) * 2.0, 120.0))


func _process(_delta: float) -> void:
	if _preview == null or _slots.is_empty():
		return
	if size != _last_size:
		_last_size = size
		_layout_preview()
		# модель встала в новый размер — точки пересчитать кадром позже
		await get_tree().process_frame
	_place_slots()


## Слоты: над стволом и под ним, по порядку точек вдоль ствола, не налезая друг на друга.
func _place_slots() -> void:
	var model_key := String(WeaponDb.weapon(String(_entry.get("id", ""))).get("model", ""))
	var rows := {"top": [], "bottom": []}
	for mount in _slots:
		var sk := WeaponMods.socket(model_key, String(mount))
		var p: Vector2 = _preview.position + _preview.project(sk.get("pos", Vector3.ZERO))
		_anchor[mount] = p
		rows["top" if mount in TOP else "bottom"].append([p.x, mount])
	for key in rows:
		var row: Array = rows[key]
		row.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
		var x_min := 4.0
		for i in range(row.size()):
			var want := clampf(float(row[i][0]) - SLOT.x * 0.5, x_min, size.x - SLOT.x * (row.size() - i) - 4.0)
			var y := 6.0 if key == "top" else size.y - SLOT.y - 6.0
			(_slots[row[i][1]] as Control).position = Vector2(want, y)
			x_min = want + SLOT.x + 8.0
	queue_redraw()


func _draw() -> void:
	var mods: Dictionary = _entry.get("mods", {})
	for mount in _slots:
		if not _anchor.has(mount):
			continue
		var b := _slots[mount] as Control
		var a: Vector2 = _anchor[mount]
		var to := b.position + Vector2(SLOT.x * 0.5, SLOT.y if mount in TOP else 0.0)
		var on := mods.has(mount)
		var col := Color(0.98, 0.8, 0.45, 0.85) if on else Color(0.7, 0.72, 0.7, 0.45)
		draw_line(a, to, col, 1.5, true)
		draw_circle(a, 4.0, col)


func _open(mount: String, from: Control) -> void:
	if _popup and is_instance_valid(_popup):
		_popup.queue_free()
	_popup = PopupPanel.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.08, 0.075, 0.07, 0.98)
	sb.border_color = Color(0.95, 0.78, 0.5, 0.35)
	sb.set_border_width_all(1)
	sb.set_content_margin_all(10)
	_popup.add_theme_stylebox_override("panel", sb)
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(560, 360)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_popup.add_child(scroll)
	var list := VBoxContainer.new()
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.add_theme_constant_override("separation", 6)
	scroll.add_child(list)
	var mounts := WeaponDb.mounts_of(String(_entry.get("id", "")))
	list.add_child(ItemCard._label("%s  [%s]" % [String(WeaponDb.MOUNT_NAMES.get(mount, mount)), String(mounts.get(mount, ""))], 16, Color(0.98, 0.84, 0.6)))
	var cur := WeaponDb.mod_id((_entry.get("mods", {}) as Dictionary).get(mount, ""))
	if cur != "":
		var row := _row({"id": cur, "n": 1}, "стоит сейчас", "Снять", "", func() -> void: remove.call(mount))
		list.add_child(row)
	var cands: Array = candidates.call(mount) if candidates.is_valid() else []
	if cands.is_empty():
		list.add_child(ItemCard._label("Подходящего нет.", 14, Color(0.6, 0.6, 0.6)))
	for c in cands:
		var d: Dictionary = c
		list.add_child(_row({"id": String(d.id), "n": 1}, String(d.get("sub", "")), String(d.get("act", "Поставить")), String(d.get("why", "")), d.action))
	add_child(_popup)
	var at := from.get_screen_position() + Vector2(0, from.size.y + 4)
	_popup.popup(Rect2i(Vector2i(at), Vector2i(580, 380)))


func _row(e: Dictionary, sub: String, act: String, why: String, action: Callable) -> Control:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	var icon := ItemCard.IconBox.new()
	icon.id = String(e.id)
	icon.custom_minimum_size = Vector2(86, 52)
	row.add_child(icon)
	var v := VBoxContainer.new()
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	v.add_child(ItemCard._label(ItemDb.item_name(String(e.id)), 14, Color(0.93, 0.91, 0.86)))
	if sub != "":
		v.add_child(ItemCard._label(sub, 12, Color(0.66, 0.68, 0.66)))
	row.add_child(v)
	if why != "":
		var wl := ItemCard._label(why, 12, Color(0.85, 0.5, 0.4))
		wl.custom_minimum_size.x = 150
		row.add_child(wl)
	else:
		var b := Button.new()
		b.text = act
		b.focus_mode = Control.FOCUS_NONE
		b.pressed.connect(func() -> void:
			if _popup and is_instance_valid(_popup):
				_popup.hide()
			action.call())
		row.add_child(b)
	return row
