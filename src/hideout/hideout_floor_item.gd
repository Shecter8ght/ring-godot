class_name HideoutFloorItem
extends Interactable
## Вещь на полу убежища (магазин, сброшенный быстрой перезарядкой): лежит моделью, как в рейде, но
## только у этого игрока — в убежище у каждого свой профиль. F — подобрать в рюкзак (нет места — в
## тайник). Не подобрал до ухода — уровень сам вернёт её в тайник: в убежище ничего не теряется.

signal picked

var entry: Dictionary = {}
var lay_yaw: float = 0.0


func prompt() -> String:
	return "подобрать: " + ItemDb.item_name(String(entry.get("id", "")))


## Вещь местная: хоста не спрашиваем.
func request_use() -> void:
	picked.emit()


func _build_visual(parent: Node3D) -> void:
	if not entry.is_empty():
		LooseLoot.lay_item(parent, String(entry.id), lay_yaw)
