@tool
class_name EngraverStation
extends HideoutStation
## Установленный сюжетный модуль появляется в свободном месте мастерской.

func _ready() -> void:
	super._ready()
	if not Engine.is_editor_hint():
		Quests.changed.connect(_refresh)
		_refresh()


func _refresh() -> void:
	var installed: bool = Upgrades.level("engraver") > 0
	visible = installed
	for node: Node in find_children("*", "CollisionObject3D", true, false):
		(node as CollisionObject3D).collision_layer = 1 if installed else 0


func can_use() -> bool:
	return Upgrades.level("engraver") > 0
