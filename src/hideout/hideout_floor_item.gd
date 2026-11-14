class_name HideoutFloorItem
extends Interactable
## Вещь на полу убежища (магазин, сброшенный быстрой перезарядкой): лежит моделью, как в рейде, но
## только у этого игрока — в убежище у каждого свой профиль. F — подобрать в рюкзак (нет места — в
## тайник). Не подобрал до ухода — уровень сам вернёт её в тайник: в убежище ничего не теряется.

signal picked

var entry: Dictionary = {}
var lay_yaw: float = 0.0
## Вещь прилетела физическим телом (TossedItem): лежит так, как оно успокоилось (как у LooseLoot).
var posed: bool = false
var lay_pose: Transform3D = Transform3D.IDENTITY


func prompt() -> String:
	return "подобрать: " + ItemDb.item_name(String(entry.get("id", "")))


## Вещь местная: хоста не спрашиваем.
func request_use() -> void:
	picked.emit()


func _build_visual(parent: Node3D) -> void:
	if entry.is_empty():
		return
	if posed:
		LooseLoot.pose_item(parent, String(entry.id), lay_pose)
	else:
		LooseLoot.lay_item(parent, String(entry.id), lay_yaw)
