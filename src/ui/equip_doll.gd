class_name EquipDoll
extends Control
## Ростовая фигура со слотами снаряжения (окно рюкзака в рейде и тайник в убежище): шлем на голове,
## очки и наушники у головы, броня на груди, разгрузка на животе, рюкзак за спиной, оружие в руках.
## Слоты — обычные SlotView (views: слот → ячейка): окно само подключает их сигналы. Фигура рисуется
## кодом — силуэт без лица, чтобы слоты читались, а не картинка.

const SIZE := Vector2(430.0, 470.0)
## Где слот стоит на фигуре (в координатах SIZE).
const LAYOUT := {
	"helmet": Rect2(155, 2, 120, 60),
	"eyes": Rect2(8, 8, 130, 54),
	"ears": Rect2(292, 8, 130, 54),
	"armor": Rect2(130, 96, 170, 88),
	"rig": Rect2(130, 190, 170, 80),
	"backpack": Rect2(310, 92, 112, 110),
	"primary": Rect2(8, 286, 204, 78),
	"secondary": Rect2(218, 286, 204, 78),
}
const C_BODY := Color(0.3, 0.29, 0.27, 0.9)
const C_EDGE := Color(1.0, 0.86, 0.6, 0.16)

var views: Dictionary = {}


func _init() -> void:
	custom_minimum_size = SIZE
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	for slot: String in Inventory.SLOTS:
		var r: Rect2 = LAYOUT.get(slot, Rect2(8, 380, 130, 60))
		var sv := SlotView.new(slot)
		sv.custom_minimum_size = r.size
		sv.position = r.position
		sv.size = r.size
		add_child(sv)
		views[slot] = sv


## Показать надетое (слот → запись).
func set_equipment(eq: Dictionary) -> void:
	for slot: String in views:
		(views[slot] as SlotView).set_entry(eq.get(slot, {}))


func _draw() -> void:
	var cx := SIZE.x * 0.5
	# голова, шея
	draw_circle(Vector2(cx, 44), 30.0, C_BODY)
	draw_rect(Rect2(cx - 11, 70, 22, 22), C_BODY)
	# плечи и корпус — трапеция, таз
	draw_colored_polygon(PackedVector2Array([Vector2(cx - 88, 92), Vector2(cx + 88, 92), Vector2(cx + 62, 268), Vector2(cx - 62, 268)]), C_BODY)
	draw_colored_polygon(PackedVector2Array([Vector2(cx - 62, 268), Vector2(cx + 62, 268), Vector2(cx + 66, 300), Vector2(cx - 66, 300)]), C_BODY)
	# руки: от плеч к кистям у бёдер
	for side: float in [-1.0, 1.0]:
		draw_colored_polygon(PackedVector2Array([Vector2(cx + side * 88, 94), Vector2(cx + side * 116, 104), Vector2(cx + side * 124, 300),
			Vector2(cx + side * 96, 304)]), C_BODY)
		# ноги
		draw_colored_polygon(PackedVector2Array([Vector2(cx + side * 6, 300), Vector2(cx + side * 66, 300), Vector2(cx + side * 56, 456),
			Vector2(cx + side * 16, 456)]), C_BODY)
		draw_rect(Rect2(cx + side * 36 - 26, 456, 52, 12), C_BODY)
	# выноски: очки и наушники — к голове, рюкзак — к спине
	draw_line(Vector2(138, 35), Vector2(cx - 30, 40), C_EDGE, 1.5)
	draw_line(Vector2(292, 35), Vector2(cx + 30, 44), C_EDGE, 1.5)
	draw_line(Vector2(310, 140), Vector2(cx + 80, 130), C_EDGE, 1.5)
