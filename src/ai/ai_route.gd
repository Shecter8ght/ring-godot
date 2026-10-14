class_name AIRoute
extends Node3D
## Маршрут патруля (слой «движение», docs/design/enemy_population.md): группа ходит по дочерним
## Marker3D по порядку — по дорогам и проходам между участками, не сквозь квартиры, подсобки и круги
## эвакуации. Встреча «в пути» — от них. В рейд выбирается часть маршрутов карты (AIPopulation).

@export var title: String = ""
## Насколько чаще других выбирается.
@export_range(0.0, 10.0, 0.1) var weight: float = 1.0
## По кругу (последняя точка → первая); иначе туда-обратно.
@export var loop: bool = false


func _ready() -> void:
	add_to_group("ai_routes")


## Точки маршрута по порядку.
func points() -> PackedVector3Array:
	var out := PackedVector3Array()
	for c in get_children():
		if c is Marker3D:
			out.append((c as Marker3D).global_position)
	return out
