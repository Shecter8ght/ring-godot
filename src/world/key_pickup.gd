@tool
class_name KeyPickup
extends Interactable
## Ключ / карта-ключ на полу. Подобрал — ключ у группы (Raid.team_keys): открывает двери
## помещений с тем же "key" в данных кольца и точки эвакуации с required_key.

@export var key_id: String = "key":
	set(v):
		key_id = v
		_rebuild()
@export var display_name: String = "Ключ":
	set(v):
		display_name = v
		_rebuild()


func _ready() -> void:
	super._ready()
	if not Engine.is_editor_hint():
		add_to_group("key_pickups")


func can_use() -> bool:
	return Raid.current != null and not Raid.current.has_key(key_id)


func prompt() -> String:
	return "взять: " + display_name


func _use() -> void:
	Raid.current.add_key(key_id)
	Audio.play("pin", global_position)


func _process(_delta: float) -> void:
	if Engine.is_editor_hint() or Raid.current == null or _vis == null:
		return
	# подобран кем угодно — пропадает у всех (ключи группы синхронизированы)
	_vis.visible = not Raid.current.has_key(key_id)


func _build_visual(parent: Node3D) -> void:
	_box(parent, Vector3(0, 0.45, 0), Vector3(0.7, 0.9, 0.5), Color(0.3, 0.3, 0.32))
	_box(parent, Vector3(0, 0.93, 0), Vector3(0.22, 0.04, 0.14), Color(1.0, 0.8, 0.2), 1.5)
	_label(parent, display_name, 1.5, Color(1.0, 0.85, 0.4))
