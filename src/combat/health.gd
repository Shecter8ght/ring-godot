class_name Health
extends Node
## Здоровье сущности. Узел-компонент: вешается на игрока и мародёра.

signal damaged(amount: float, from: Vector3)
signal died

@export var max_hp: float = 100.0

var hp: float
var alive: bool = true


func _ready() -> void:
	hp = max_hp


func take_damage(amount: float, from: Vector3) -> void:
	if not alive:
		return
	hp = maxf(0.0, hp - amount)
	damaged.emit(amount, from)
	var owner_3d := get_parent() as Node3D
	if owner_3d:
		Audio.play("hit", owner_3d.global_position + Vector3.UP)
	if hp <= 0.0:
		alive = false
		died.emit()
