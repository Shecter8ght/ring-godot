class_name EquipDoll
extends Control
## Снаряжение на силуэте (окно рюкзака в рейде и тайник в убежище; docs/design/equip_doll_v2.md): в середине —
## контур человека в А-позе (BodySilhouette, без 3D-модели), напротив частей тела — их слоты: слева голова
## (шлем, уши — гарнитура, независимый слот, глаза — ПНВ / очки), справа корпус (броня или пояс) и спина
## (рюкзак). У надетого шлема раскрываются его крепления (ПНВ, гарнитура, фонарь, забрало), у брони — полоска
## мест под подсумки на половинках (PouchPlaces). Внизу — два слота крупного оружия, пистолет и ракетница.
## Слоты — обычные SlotView (views: слот → ячейка), места — PouchPlaces (places): окно подключает их сигналы.

const SIZE := Vector2(440.0, 484.0)
const LAYOUT := {
	"helmet": Rect2(0, 0, 92, 80),
	"ears": Rect2(0, 86, 92, 80),
	"eyes": Rect2(0, 172, 92, 80),
	"armor": Rect2(348, 0, 92, 80),
	"backpack": Rect2(348, 172, 92, 80),
	"primary": Rect2(0, 326, 217, 82),
	"secondary": Rect2(223, 326, 217, 82),
	"sidearm": Rect2(0, 414, 217, 70),
	"launcher": Rect2(223, 414, 217, 70),
}
## Где стоит силуэт.
const FIGURE := Rect2(98, 0, 244, 258)
## Крепления шлема — столбик плашек правее слота шлема.
const MOUNT_CHIP := Rect2(97, 2, 46, 18)
## Полоска мест под подсумки (подпись — над ней).
const PLACES_AT := Vector2(0, 278)
const MOUNT_NAMES := {"NVG": "ПНВ", "HEADSET": "Уши", "LIGHT": "Свет", "VISOR": "Забр"}

var views: Dictionary = {}
var places: PouchPlaces
var figure: BodySilhouette
var _chips: Array[MountChip] = []
var _eq: Dictionary = {}
var _font: Font


## Плашка крепления шлема: что на нём (горит), свободно (контур) или закрыто (нет такого предмета пока).
class MountChip extends Control:
	var label: String = ""
	var state: String = "free"   # on / free / closed
	var hint: String = ""

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_STOP
		tooltip_text = " "

	func _get_tooltip(_at: Vector2) -> String:
		return hint

	func _draw() -> void:
		var r := Rect2(Vector2.ZERO, size)
		var f := ThemeDB.fallback_font
		var lt := LightUi.inside(self)
		match state:
			"on":
				draw_rect(r, Color(LightUi.ACCENT, 0.16) if lt else Color(1.0, 0.8, 0.48, 0.32))
				draw_rect(r, LightUi.ACCENT if lt else Color(1.0, 0.8, 0.48, 0.9), false, 1.0)
			"closed":
				draw_rect(r, Color("ecebe7") if lt else Color(0.05, 0.05, 0.06, 0.8))
				draw_line(r.position, r.end, Color(0, 0, 0, 0.15) if lt else Color(1, 1, 1, 0.12), 1.0)
			_:
				draw_rect(r, LightUi.SURFACE if lt else Color(0.085, 0.087, 0.092, 0.86))
				draw_rect(r, LightUi.SLOT_EDGE if lt else Color(1, 1, 1, 0.22), false, 1.0)
		var c := Color(0.95, 0.93, 0.88) if state == "on" else Color(0.55, 0.57, 0.6, 0.6 if state == "closed" else 1.0)
		if lt:
			c = LightUi.ACCENT_DARK if state == "on" else Color(LightUi.MUTED, 0.6 if state == "closed" else 1.0)
		draw_string(f, Vector2(0, size.y - 5.0), label, HORIZONTAL_ALIGNMENT_CENTER, size.x, 10, c)


func _init() -> void:
	custom_minimum_size = SIZE
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_font = ThemeDB.fallback_font
	figure = BodySilhouette.new()
	figure.position = FIGURE.position
	figure.size = FIGURE.size
	add_child(figure)
	for slot: String in Inventory.SLOTS:
		var r: Rect2 = LAYOUT.get(slot, Rect2(0, 262, 92, 80))
		var sv := SlotView.new(slot)
		sv.custom_minimum_size = r.size
		sv.position = r.position
		sv.size = r.size
		add_child(sv)
		views[slot] = sv
	places = PouchPlaces.new()
	places.position = PLACES_AT
	places.size = places.custom_minimum_size
	add_child(places)


## Показать надетое (слот → запись): слоты, силуэт, крепления шлема, места брони.
func set_equipment(eq: Dictionary) -> void:
	_eq = eq
	for slot: String in views:
		var sv := views[slot] as SlotView
		sv.eq = eq
		sv.note = ""
		sv.set_entry(eq.get(slot, {}))
	# под шлем без площадки ПНВ не встаёт — подпись у слота глаз
	if eq.has("helmet") and not "NVG" in ItemDb.helmet_mounts(eq):
		(views.eyes as SlotView).note = "ПНВ — не под этот шлем"
	figure.set_equipment(eq)
	places.set_armor(eq.get("armor", {}) as Dictionary)
	_build_chips()
	queue_redraw()


func _build_chips() -> void:
	for c: MountChip in _chips:
		remove_child(c)
		c.queue_free()
	_chips.clear()
	var y := MOUNT_CHIP.position.y
	for m: Variant in ItemDb.helmet_mounts(_eq):
		var key := String(m)
		var chip := MountChip.new()
		chip.label = String(MOUNT_NAMES.get(key, key))
		match key:
			"NVG":
				var nvg := _eq.get("eyes") is Dictionary and bool(ItemDb.equip(String((_eq.eyes as Dictionary).get("id", ""))).get("nvg", false))
				chip.state = "on" if nvg else "free"
				chip.hint = "Площадка ПНВ: ПНВ из слота «Глаза» стоит на шлеме" if nvg else "Площадка ПНВ свободна — надень ПНВ в слот «Глаза»"
			"HEADSET":
				chip.state = "on" if _eq.has("ears") else "free"
				chip.hint = "Гарнитура надета — чашки встают на шлем" if _eq.has("ears") else "Под гарнитуру: чашки встают на шлем (слот «Уши»)"
			"LIGHT":
				chip.state = "closed"
				chip.hint = "Крепление фонаря на шлем — фонарей на шлем пока нет"
			"VISOR":
				chip.state = "on"
				chip.hint = "Забрало — часть шлема"
		chip.position = Vector2(MOUNT_CHIP.position.x, y)
		chip.size = MOUNT_CHIP.size
		add_child(chip)
		_chips.append(chip)
		y += MOUNT_CHIP.size.y + 3.0


func _draw() -> void:
	# подпись полоски мест: сколько мест и куда встаёт большой
	var a: Dictionary = _eq.get("armor", {}) if _eq.get("armor") is Dictionary else {}
	var text := "Надень броню или пояс — появятся места под подсумки"
	if not a.is_empty():
		var v := WeaponDb.vest(String(a.get("id", "")))
		var n := int(v.get("places", 0))
		var pairs: Array[String] = []
		for pair: Variant in v.get("pairs_big", []):
			pairs.append("%d+%d" % [int((pair as Array)[0]), int((pair as Array)[1])])
		text = "Места под подсумки: %d   ½ — пист · 1 — авт · 2 — большой: %s" % [n, ", ".join(pairs) if not pairs.is_empty() else "нет"]
	draw_string(_font, Vector2(0, PLACES_AT.y - 5.0), text, HORIZONTAL_ALIGNMENT_LEFT, SIZE.x, 11, LightUi.TEXT2 if LightUi.inside(self) else Color(0.95, 0.82, 0.6, 0.85))
