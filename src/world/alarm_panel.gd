class_name AlarmPanel
extends Interactable
## Пульт сигнализации магазина (ставит AlarmZone своим ребёнком «Panel»): пока сирена воет —
## F, постоять рядом Balance.RAID_EVENTS.alarm_off_sec — сигнализация отключена у всех. Отошёл —
## сначала. Решает хост (как ремонт генератора). До срабатывания — просто коробка с клавиатурой.

var zone: AlarmZone
var _off_t: float = -1.0
var _who: int = 0


func can_use() -> bool:
	return zone != null and zone.sounding() and _off_t < 0.0


func prompt() -> String:
	return "отключить сигнализацию (%.0f с)" % float(Balance.RAID_EVENTS.alarm_off_sec)


func _use(peer_id: int) -> void:
	_off_t = 0.0
	_who = peer_id
	Audio.play("alarm_panel", global_position + Vector3.UP * 1.3, -4.0)


func _process(delta: float) -> void:
	if _off_t < 0.0 or (Net.is_networked() and not multiplayer.is_server()):
		return
	var pl := Raid.current.player_of(_who) if Raid.current else null
	if pl == null or not pl.is_alive() or pl.global_position.distance_to(global_position) > Balance.INTERACT_RADIUS + 1.0 or not zone.sounding():
		_off_t = -1.0
		return
	_off_t += delta
	if _off_t >= float(Balance.RAID_EVENTS.alarm_off_sec):
		_off_t = -1.0
		zone.disarm()


## Блокаут: коробка пульта на стойке, клавиатура, красный индикатор.
func _build_visual(parent: Node3D) -> void:
	_box(parent, Vector3(0, 0.6, 0), Vector3(0.08, 1.2, 0.08), Color(0.3, 0.31, 0.32))
	_box(parent, Vector3(0, 1.3, 0), Vector3(0.24, 0.3, 0.07), Color(0.88, 0.88, 0.85))
	_box(parent, Vector3(0, 1.26, -0.04), Vector3(0.16, 0.14, 0.01), Color(0.2, 0.2, 0.22))
	_box(parent, Vector3(0.07, 1.4, -0.04), Vector3(0.03, 0.03, 0.01), Color(1.0, 0.15, 0.1), 3.0)
