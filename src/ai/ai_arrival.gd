class_name AIArrival
extends Marker3D
## Точка подхода (docs/design/enemy_population.md): отсюда по ходу рейда входят новые группы мародёров —
## у края карты, вне видимости главных мест добычи, не ближе 40 м ко входам игроков и кругам эвакуации.
## Вход годится, только если игроки дальше Balance.AI_POPULATION.arrive_min_m и его не видят.

@export var title: String = ""


func _ready() -> void:
	add_to_group("ai_arrivals")
