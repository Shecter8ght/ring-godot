@tool
class_name QuestAnchor
extends Marker3D
## Где стоит место сюжетного квеста на этом уровне: site_id — ключ из data/quests (sites).
## Поставил в сцену уровня и передвинул мышкой — место квеста появится здесь, а не там, куда
## указывает anchor в данных. Так сюжет переезжает вместе с перестроенным уровнем.

@export var site_id: String = "":
	set(v):
		site_id = v
		_update_label()

var _label: Label3D


func _ready() -> void:
	add_to_group("quest_anchors")
	if Engine.is_editor_hint():
		_update_label()


func _update_label() -> void:
	if not Engine.is_editor_hint() or not is_inside_tree():
		return
	if _label == null:
		_label = Label3D.new()
		_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		_label.pixel_size = 0.01
		_label.position = Vector3.UP * 1.2
		_label.modulate = Color(1.0, 0.8, 0.3)
		add_child(_label, false, Node.INTERNAL_MODE_FRONT)
	_label.text = "квест: " + (site_id if site_id != "" else "?")
