@tool
class_name BlockoutOpening
extends Node3D
## Дверь или ворота в стене постройки-блокаута. Кладётся дочерним узлом BlockoutBuilding и
## двигается мышкой: проём прорезается в ближайшей стене, постройка пересобирается сразу.

enum Kind { DOOR, GATE }

@export var kind: Kind = Kind.DOOR:
	set(v):
		kind = v
		_changed()
## Ширина проёма, м. Эвакуационная дверь — не уже 1.2 (СП 1.13130), ворота под грузовик — 4–5.
@export var width: float = 1.6:
	set(v):
		width = maxf(0.8, v)
		_changed()


func _ready() -> void:
	set_notify_local_transform(true)


func _notification(what: int) -> void:
	if what == NOTIFICATION_LOCAL_TRANSFORM_CHANGED:
		_changed()


func _changed() -> void:
	var b := get_parent() as BlockoutBuilding
	if b:
		b.queue_build()
