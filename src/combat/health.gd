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
	if hp <= 0.0:
		alive = false
		died.emit()
