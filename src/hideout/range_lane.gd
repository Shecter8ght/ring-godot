class_name RangeLane
extends Node3D
## Дорожка тира: узел стоит на огневом рубеже, -Z узла — в сторону мишени. Мишень (RangeTarget,
## дочерний узел Target) едет на тележке по направляющей между остановками Balance.RANGE.distances_m;
## узел Carriage (тележка, подвес) едет вместе с ней. Кнопки пульта (RangeButton) просят ShootingRange,
## тот рассылает новое состояние всем в убежище — у всех дорожка едет одинаково.

@export var display_name: String = "Дорожка"
## Дальше этого мишень не уезжает (длина направляющей до улавливателя), м.
@export var max_distance_m: float = 32.0

## Индекс текущей остановки в Balance.RANGE.distances_m.
var stop: int = 0
var _distance: float = 0.0
var _target: RangeTarget
var _carriage: Node3D
var _range: Node
## Табло на пульте: куда едет мишень (узел Display, Label3D).
var _display: Label3D


func _ready() -> void:
	_target = get_node_or_null("Target") as RangeTarget
	_carriage = get_node_or_null("Carriage") as Node3D
	_display = get_node_or_null("Display") as Label3D
	stop = clampi(int(Balance.RANGE.start_index), 0, stops().size() - 1)
	_distance = stop_distance(stop)
	_place()
	if _target:
		_target.holed.connect(_on_holed)


## Остановки, до которых дотягивает направляющая этой дорожки.
func stops() -> Array[float]:
	var out: Array[float] = []
	for d: Variant in Balance.RANGE.distances_m:
		if float(d) <= max_distance_m + 0.01:
			out.append(float(d))
	return out


func stop_distance(i: int) -> float:
	var s: Array[float] = stops()
	return s[clampi(i, 0, s.size() - 1)]


## Где мишень сейчас (м) и куда едет.
func distance_now() -> float:
	return _distance


func goal_distance() -> float:
	return stop_distance(stop)


func target() -> RangeTarget:
	return _target


## Нажата кнопка пульта: «closer», «farther», «reset». Состояние меняет и рассылает ShootingRange.
func press(action: String) -> void:
	var r: Node = _owner_range()
	if r:
		r.call("request_lane", self, action)


## Новое состояние дорожки (от ShootingRange у всех peer).
func apply_state(new_stop: int, reset_seq: bool) -> void:
	var changed: bool = new_stop != stop
	stop = clampi(new_stop, 0, stops().size() - 1)
	if reset_seq and _target:
		_target.clear_holes()
	if changed:
		_place()
		Audio.play("shutter_rattle", global_position + Vector3.UP * 2.4 - global_basis.z * _distance, -26.0)


func _on_holed(local_point: Vector3) -> void:
	var r: Node = _owner_range()
	if r:
		r.call("share_hole", self, local_point)


func _owner_range() -> Node:
	if _range == null:
		var p: Node = get_parent()
		while p and not p.has_method("request_lane"):
			p = p.get_parent()
		_range = p
	return _range


func _physics_process(delta: float) -> void:
	var goal: float = goal_distance()
	if is_equal_approx(_distance, goal):
		return
	_distance = move_toward(_distance, goal, float(Balance.RANGE.carrier_mps) * delta)
	_place()


func _place() -> void:
	var at: Vector3 = Vector3(0, 0, -_distance)
	if _target:
		_target.position = at
	if _carriage:
		_carriage.position = at
	if _display:
		var goal: float = goal_distance()
		_display.text = "%d м" % int(round(goal)) if is_equal_approx(_distance, goal) else "%d → %d м" % [int(round(_distance)), int(round(goal))]
