class_name SpawnPoint
extends Marker3D
## Точка появления группы. Уровень выбирает одну случайную на рейд; игроки встают вокруг неё.
## Двигается мышкой в сцене уровня.

@export var display_name: String = ""
## Точка у спуска в убежище (HideoutEntrance): укрыта от улицы. Есть такие — уровень берёт только их.
@export var bunker: bool = false


func _ready() -> void:
	add_to_group("spawn_points")
