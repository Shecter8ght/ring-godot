class_name Squad
extends RefCounted
## Отряд мародёров (1–3): ведущий выбирает точки патруля, остальные идут за ним строем.
## Отряд — это кто с кем ходит и кто кого прикрывает, а НЕ общая память: о цели товарищи
## узнают только окриком (NoiseBus.callout) — услышал, значит знает.

enum Role { NONE, ASSAULT, FLANK, COVER }

## Отряды, которые сейчас в бою (для порядка ролей).
static var engaged: Array = []

var members: Array[Marauder] = []
## Роль отряда в текущем бою и где цель, когда её выдали; сторона обхода — одна на отряд.
var role: Role = Role.NONE
var role_at: Vector3 = Vector3.ZERO
var flank_side: float = 1.0
var _calm_since: int = 0


func add(m: Marauder) -> void:
	members.append(m)
	m.squad = self


func alive() -> Array[Marauder]:
	var out: Array[Marauder] = []
	for m in members:
		if is_instance_valid(m) and m.state != Marauder.State.DEAD:
			out.append(m)
	return out


## Отряд вступил в бой у точки target: роль — по порядку среди отрядов, что уже воюют рядом
## (первый — штурм, второй — обход, третий — прикрытие). О соседях отряд знает по окрикам.
func engage(target: Vector3) -> Role:
	if role != Role.NONE:
		return role
	var busy := 0
	var alive_engaged: Array = []
	for s in engaged:
		var sq := s as Squad
		if sq == null or sq == self or sq.alive().is_empty() or sq.role == Role.NONE:
			continue
		alive_engaged.append(sq)
		if sq.role_at.distance_to(target) <= Balance.AI_ROLE_RADIUS:
			busy += 1
	engaged = alive_engaged
	engaged.append(self)
	role = [Role.ASSAULT, Role.FLANK, Role.COVER][busy % 3]
	role_at = target
	flank_side = 1.0 if randf() < 0.5 else -1.0
	return role


## Никто в отряде не воюет AI_ROLE_FORGET_SEC — роль снята.
func tick_calm() -> void:
	if role == Role.NONE:
		return
	for m in alive():
		if m.state == Marauder.State.COMBAT:
			_calm_since = Time.get_ticks_msec()
			return
	if Time.get_ticks_msec() - _calm_since > int(Balance.AI_ROLE_FORGET_SEC * 1000.0):
		role = Role.NONE
		engaged.erase(self)


## Ведущий — первый живой.
func leader() -> Marauder:
	var a := alive()
	return a[0] if not a.is_empty() else null


## Номер среди живых (0 — ведущий): второй идёт в обход, третий прикрывает.
func rank_of(m: Marauder) -> int:
	return alive().find(m)
