extends Node3D
## Прямоугольная область звука поверх основного пола. Под полом и на соседних этажах её не слышно.

const GROUP: StringName = &"step_layer_patches"

@export_enum("glass", "leaves", "trash") var layer: String = "glass"
@export var enabled: bool = true
@export var size: Vector2 = Vector2(2.0, 2.0)
@export_range(-24.0, 12.0, 1.0) var gain_db: float = 0.0
## Пустое поле берёт запись слоя из каталога шагов.
@export var sound_event: String = ""


func _ready() -> void:
	add_to_group(GROUP)


func covers(point: Vector3) -> bool:
	var local: Vector3 = to_local(point)
	return enabled and absf(local.y) <= Balance.STEP_LAYER_HEIGHT * 0.5 \
		and absf(local.x) <= size.x * 0.5 and absf(local.z) <= size.y * 0.5
