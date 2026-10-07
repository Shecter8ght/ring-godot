class_name ShootingRange
extends Node3D
## Тир в бывшем котельном зале убежища. Дочерние RangeLane (дорожки с мишенями на тележках),
## RangeButton (пульты), RangeWeaponRack (стойка: любой ствол игры, патроны без счёта).
## Кооп: как досуг убежища — кто нажал кнопку, тот рассылает новое состояние всем в убежище
## (call_local), новичку состояние шлёт хост. Пробоины видят все: стрелок шлёт точку попадания.
## Ушёл из зала со стволом стойки — ствол остаётся на стойке, в руки возвращается своё снаряжение.

## Зал тира в осях узла: за его пределами ствол стойки сдаётся.
@export var zone: AABB = AABB(Vector3(-6.5, -0.5, -5.0), Vector3(40.0, 6.0, 12.6))

var _lanes: Array[RangeLane] = []
## Сброс листа — счётчик на дорожку: повтор старого пакета не стирает новые пробоины.
var _reset_seq: Dictionary = {}


func _ready() -> void:
	for n: Node in find_children("*", "RangeLane", true, false):
		_lanes.append(n as RangeLane)
	if Net.is_networked():
		Net.scenes_changed.connect(_share_state)


func lanes() -> Array[RangeLane]:
	return _lanes


## Пульт дорожки: ближе / дальше / сменить лист — меняем у себя и рассылаем.
func request_lane(lane: RangeLane, action: String) -> void:
	var i: int = _lanes.find(lane)
	if i < 0:
		return
	var new_stop: int = lane.stop
	var reset: int = int(_reset_seq.get(i, 0))
	match action:
		"closer":
			new_stop = maxi(0, lane.stop - 1)
		"farther":
			new_stop = mini(lane.stops().size() - 1, lane.stop + 1)
		"reset":
			reset += 1
	_set_lane(i, new_stop, reset)
	for peer: int in _peers_here():
		_set_lane.rpc_id(peer, i, new_stop, reset)


@rpc("any_peer", "call_remote", "reliable")
func _set_lane(i: int, new_stop: int, reset: int) -> void:
	if i < 0 or i >= _lanes.size():
		return
	var cleared: bool = reset > int(_reset_seq.get(i, 0))
	if cleared:
		_reset_seq[i] = reset
	_lanes[i].apply_state(new_stop, cleared)


## Своё попадание — точку пробоины напарникам.
func share_hole(lane: RangeLane, local_point: Vector3) -> void:
	var i: int = _lanes.find(lane)
	if i < 0:
		return
	for peer: int in _peers_here():
		_hole.rpc_id(peer, i, local_point)


@rpc("any_peer", "call_remote", "unreliable_ordered")
func _hole(i: int, local_point: Vector3) -> void:
	if i < 0 or i >= _lanes.size() or not local_point.is_finite():
		return
	var t: RangeTarget = _lanes[i].target()
	if t:
		t.add_hole(local_point)


## Новичок в убежище: хост шлёт положение мишеней (пробоины — нет, лист у новичка чистый).
func _share_state() -> void:
	if not Net.is_networked() or not multiplayer.is_server():
		return
	for peer: int in _peers_here():
		for i: int in range(_lanes.size()):
			_set_lane.rpc_id(peer, i, _lanes[i].stop, int(_reset_seq.get(i, 0)))


func _peers_here() -> Array[int]:
	var out: Array[int] = []
	if not Net.is_networked():
		return out
	for peer: int in Net.peer_scene:
		if peer != multiplayer.get_unique_id() and Net.visible_in(peer, "hideout"):
			out.append(peer)
	return out


## Стоит ли точка мира в зале тира.
func contains(world_point: Vector3) -> bool:
	return zone.has_point(global_transform.affine_inverse() * world_point)


func _process(_delta: float) -> void:
	var pl: Player = _local_player()
	if pl == null or not pl.in_range_mode():
		return
	if not contains(pl.global_position):
		pl.clear_range_weapon()
		var level: Node = get_tree().get_first_node_in_group("hideout_level")
		if level:
			level.call("notify", "Ствол тира остался на стойке")


func _local_player() -> Player:
	for n: Node in get_tree().get_nodes_in_group("all_players"):
		var p: Player = n as Player
		if p and p.is_local():
			return p
	return null
