class_name EquipDoll
extends Control
## Снаряжение на фигуре (окно рюкзака в рейде и тайник в убежище) — как в играх жанра: в середине
## стоит сам персонаж (CharacterPreview, настоящая модель), слева от него узкая колонка «голова» (шлем,
## наушники, глаза), справа — «корпус» (броня, разгрузка, рюкзак), под ногами — два широких слота крупного оружия (1, 2),
## под ними — пистолет (3) и ракетница (5).
## Слоты маленькие и одинаковые, без рамок-плит. Сами слоты — обычные SlotView (views: слот → ячейка):
## окно подключает их сигналы, перетаскивание работает как раньше.

const SIZE := Vector2(440.0, 420.0)
## Малый слот и где какой стоит (в координатах SIZE).
const CELL := Vector2(92.0, 80.0)
const LAYOUT := {
	"helmet": Rect2(0, 0, 92, 80),
	"ears": Rect2(0, 86, 92, 80),
	"eyes": Rect2(0, 172, 92, 80),
	"armor": Rect2(348, 0, 92, 80),
	"rig": Rect2(348, 86, 92, 80),
	"backpack": Rect2(348, 172, 92, 80),
	"primary": Rect2(0, 262, 217, 82),
	"secondary": Rect2(223, 262, 217, 82),
	"sidearm": Rect2(0, 350, 217, 70),
	"launcher": Rect2(223, 350, 217, 70),
}
## Где стоит фигура.
const FIGURE := Rect2(98, 0, 244, 258)

var views: Dictionary = {}
var _figure: CharacterPreview


func _init() -> void:
	custom_minimum_size = SIZE
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_figure = CharacterPreview.new()
	_figure.position = FIGURE.position
	_figure.size = FIGURE.size
	_figure.custom_minimum_size = FIGURE.size
	add_child(_figure)
	for slot: String in Inventory.SLOTS:
		var r: Rect2 = LAYOUT.get(slot, Rect2(0, 262, 92, 80))
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
	# мягкая подложка под фигурой: человек не висит в пустоте
	var c := FIGURE.get_center()
	draw_circle(Vector2(c.x, FIGURE.end.y - 10.0), 62.0, Color(1.0, 0.86, 0.6, 0.035))
	draw_circle(Vector2(c.x, FIGURE.end.y - 10.0), 40.0, Color(1.0, 0.86, 0.6, 0.04))
