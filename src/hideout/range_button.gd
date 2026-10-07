@tool
class_name RangeButton
extends Interactable
## Кнопка пульта дорожки тира: «Ближе», «Дальше» или «Сменить лист». Узел стоит на самой кнопке
## пульта (модель — в сцене); из нескольких кнопок рядом срабатывает та, что под курсором.

@export var lane_path: NodePath
@export_enum("closer", "farther", "reset") var action: String = "farther"


func prompt() -> String:
	var lane: RangeLane = get_node_or_null(lane_path) as RangeLane
	if lane == null:
		return ""
	var now: String = "%d м" % int(round(lane.goal_distance()))
	match action:
		"closer":
			return "%s: мишень ближе (сейчас %s)" % [lane.display_name, now]
		"farther":
			return "%s: мишень дальше (сейчас %s)" % [lane.display_name, now]
	return "%s: сменить лист (пробоин %d)" % [lane.display_name, lane.target().hole_count() if lane.target() else 0]


## Пульт работает у каждого сам: состояние рассылает ShootingRange.
func request_use() -> void:
	var lane: RangeLane = get_node_or_null(lane_path) as RangeLane
	if lane == null:
		return
	Audio.play("power_switch", global_position, -10.0)
	lane.press(action)


## Кнопка — часть модели пульта: подсказку даёт уровень, своей надписи нет.
func _build_visual(_parent: Node3D) -> void:
	pass
