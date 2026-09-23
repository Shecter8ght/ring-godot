class_name Squad
extends RefCounted
## Отряд мародёров (1–3): ведущий выбирает точки патруля, остальные идут за ним строем.
## Отряд — это кто с кем ходит и кто кого прикрывает, а НЕ общая память: о цели товарищи
## узнают только окриком (NoiseBus.callout) — услышал, значит знает.

var members: Array[Marauder] = []


func add(m: Marauder) -> void:
	members.append(m)
	m.squad = self


func alive() -> Array[Marauder]:
	var out: Array[Marauder] = []
	for m in members:
		if is_instance_valid(m) and m.state != Marauder.State.DEAD:
			out.append(m)
	return out


## Ведущий — первый живой.
func leader() -> Marauder:
	var a := alive()
	return a[0] if not a.is_empty() else null


## Номер среди живых (0 — ведущий): второй идёт в обход, третий прикрывает.
func rank_of(m: Marauder) -> int:
	return alive().find(m)
