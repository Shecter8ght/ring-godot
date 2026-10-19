extends Node3D
## Ангар № 8 ремонтных дворов Пригорода (заказ «Вернуть машину», data/quests/car_recovery.json): машина Ильи
## по состоянию заказа — колесо и аккумулятор стоят, когда их поставили (Quests.durable — сданное остаётся и
## после гибели без эвакуации); после вывоза (флаг car_recovered) — пустое место. Вид меняется от состояния
## заказа (сдача, следующий рейд), а не от того, что кто-то подошёл. Капот открыт — для снимков механику.

@export var quest_id: String = "car_recovery"
@export var recovered_flag: String = "car_recovered"

@onready var _car: IlyaCar = get_node_or_null("IlyaCar") as IlyaCar
@onready var _body: CollisionShape3D = get_node_or_null("CarBody/Shape") as CollisionShape3D


func _ready() -> void:
	if Engine.is_editor_hint():
		return
	Quests.changed.connect(_refresh)
	_refresh()


func _refresh() -> void:
	if _car == null:
		return
	var done: Array = Quests.durable(quest_id)
	_car.wheel_fitted = "wheel" in done
	_car.battery_installed = "battery" in done
	var gone: bool = Quests.flag(recovered_flag) == true
	_car.visible = not gone
	# у модели своё тело (импорт машин, tools/editor/vehicle_import.gd) — спрятанная машина не должна держать
	# игрока и пули; отложенно: изменение состояния заказа может прийти из обратного вызова физики
	var shapes: Array[Node] = _car.find_children("*", "CollisionShape3D", true, false)
	if _body:
		shapes.append(_body)
	for shape: Node in shapes:
		shape.set_deferred("disabled", gone)
