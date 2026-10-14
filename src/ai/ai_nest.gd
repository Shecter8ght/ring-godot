class_name AINest
extends Marker3D
## Гнездо снайпера (слой «движение», docs/design/enemy_population.md): стоит здесь и смотрит вдоль −Z
## маркера в секторе sector_deg. При расстановке: сектор проверен лучом с высоты глаз, не накрывает
## целиком вход игроков и круг эвакуации, к гнезду есть два разных подхода. 0–1 снайпер за рейд.

@export var title: String = ""
## Насколько чаще других выбирается.
@export_range(0.0, 10.0, 0.1) var weight: float = 1.0
## Ширина сектора обзора, град.
@export_range(20.0, 180.0, 1.0) var sector_deg: float = 75.0
## Отходит от точки не дальше, м (на краю плиты — меньше).
@export_range(0.0, 12.0, 0.5) var radius: float = 3.0


func _ready() -> void:
	add_to_group("ai_nests")


## Куда смотрит (по горизонтали).
func watch_dir() -> Vector3:
	var d := -global_basis.z
	d.y = 0.0
	return d.normalized() if d.length_squared() > 0.0001 else Vector3.FORWARD
