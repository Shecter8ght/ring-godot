extends Node3D
## Ангар № 8 ремонтных дворов Пригорода (заказ «Вернуть машину», data/quests/car_recovery.json): машина Ильи
## по состоянию заказа — колесо и аккумулятор стоят, когда их поставили (Quests.durable — сданное остаётся и
## после гибели без эвакуации); после вывоза (флаг car_recovered) — пустое место. Вид меняется от состояния
## заказа (сдача, следующий рейд), а не от того, что кто-то подошёл. Капот открыт — для снимков механику.

@export var quest_id: String = "car_recovery"
@export var recovered_flag: String = "car_recovered"

@onready var _car: IlyaCar = get_node_or_null("IlyaCar") as IlyaCar
@onready var _body: CollisionShape3D = get_node_or_null("CarBody/Shape") as CollisionShape3D

var _delivery_label: Label3D
var _hood_label: Label3D


func _ready() -> void:
	if Engine.is_editor_hint():
		return
	_delivery_label = _make_delivery_label("car_belt_delivery", "РАДИАТОР — В ЭТОТ ЯЩИК\n↓", 0.4, float(Balance.CAR_DELIVERY_LABEL.crate_range_m))
	_hood_label = _make_delivery_label("car_belt_photo_engine", "Радиатор — в ящик\nу задней части машины", 0.9, float(Balance.CAR_DELIVERY_LABEL.hood_range_m))
	if _hood_label:
		_hood_label.position.z = -0.5
		_hood_label.pixel_size = 0.0012
	Quests.changed.connect(_refresh)
	_refresh()


func _make_delivery_label(anchor_name: String, text: String, height: float, distance: float) -> Label3D:
	var anchor := get_node_or_null(NodePath(anchor_name)) as Node3D
	if anchor == null:
		return null
	var label := Label3D.new()
	label.name = "RadiatorDeliveryLabel"
	label.text = text
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.font_size = 32
	label.pixel_size = 0.0018
	label.outline_size = 8
	label.modulate = Color(1.0, 0.8, 0.3)
	label.position.y = height
	label.visibility_range_end = distance
	anchor.add_child(label)
	return label


func _refresh() -> void:
	if _car == null:
		return
	var done: Array = Quests.durable(quest_id)
	_car.wheel_fitted = "wheel" in done
	_car.battery_installed = "battery" in done
	var gone: bool = Quests.flag(recovered_flag) == true
	var delivery_pending := not gone and Quests.state(quest_id) == "ACTIVE" \
		and String(Quests.stage(quest_id).get("id", "")) == "kit" and not "radiator" in done
	if _delivery_label:
		_delivery_label.visible = delivery_pending
	if _hood_label:
		_hood_label.visible = delivery_pending
	_car.visible = not gone
	# у модели своё тело (импорт машин, tools/editor/vehicle_import.gd) — спрятанная машина не должна держать
	# игрока и пули; отложенно: изменение состояния заказа может прийти из обратного вызова физики
	var shapes: Array[Node] = _car.find_children("*", "CollisionShape3D", true, false)
	if _body:
		shapes.append(_body)
	for shape: Node in shapes:
		shape.set_deferred("disabled", gone)
