@tool
extends Node3D
## Воспроизводит сохранённый клип; геометрия и траектории уже записаны в GLB.

@export var requires_power: bool = true
@export var animation_path: NodePath = NodePath("Visual/AnimationPlayer")

func _ready() -> void:
	if not Engine.is_editor_hint():
		set_power(true)

func set_power(enabled: bool) -> void:
	var active: bool = enabled or not requires_power
	visible = active
	var animation: AnimationPlayer = get_node_or_null(animation_path) as AnimationPlayer
	if not animation:
		return
	if active:
		var clips: PackedStringArray = animation.get_animation_list()
		if not clips.is_empty():
			animation.play(clips[0])
	else:
		animation.pause()
