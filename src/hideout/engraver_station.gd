@tool
class_name EngraverStation
extends HideoutStation
## Установленный сюжетный модуль появляется в свободном месте мастерской. Вставленная в станок головка
## (Quests.engraver_head — общая для группы) лежит на станке и видна всем; подсказка говорит, сколько
## надписей в ней осталось.

var _head_model: Node3D

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
	# головка в станке — её модель на рабочем столе станка, с зелёным огоньком готовности
	var head: Dictionary = Quests.engraver_head()
	if _head_model == null and DisplayServer.get_name() != "headless":
		_head_model = Node3D.new()
		_head_model.name = "InstalledHead"
		_head_model.position = Vector3(0.14, 0.2, 0.0)
		add_child(_head_model)
		_head_model.add_child(ItemModels.build("laser_head"))
		var led := OmniLight3D.new()
		led.light_color = Color(0.3, 1.0, 0.45)
		led.light_energy = 0.25
		led.omni_range = 0.5
		led.position = Vector3(0, 0.08, 0)
		_head_model.add_child(led)
	if _head_model:
		_head_model.visible = installed and not head.is_empty()


func prompt() -> String:
	var head: Dictionary = Quests.engraver_head()
	if head.is_empty():
		return display_name + " · головки нет"
	return "%s · головка: %d / %d" % [display_name, int(head.get("charges", 0)), int(Balance.ENGRAVING.charges)]


func can_use() -> bool:
	return Upgrades.level("engraver") > 0
