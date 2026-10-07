@tool
class_name HideoutStation
extends Interactable
## Точка в убежище, у которой F открывает окно: тайник со снаряжением, торговец, выход в рейд,
## верстак (обвесы на надетое оружие).
## Ставится руками в сцену убежища и двигается мышкой; окно — HideoutUI.

enum Kind { STASH, TRADER, EXIT, WORKBENCH, UPGRADES }

@export var kind: Kind = Kind.STASH
## Авторская сцена использует настенные таблички и обычную подсказку F.
@export var authored_visual: bool = false
@export var display_name: String = "Тайник":
	set(v):
		display_name = v
		_rebuild()


func prompt() -> String:
	return display_name


## Окно открывает уровень убежища (оффлайн, без хоста) — здесь ничего не нужно.
func request_use() -> void:
	var level := get_tree().get_first_node_in_group("hideout_level")
	if level:
		level.call("open_station", self)


func _build_visual(parent: Node3D) -> void:
	if display_name != "" and not authored_visual:
		_label(parent, display_name, 2.4, Color(1.0, 0.86, 0.6))
