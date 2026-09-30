class_name WeaponRig
extends Node3D
## Визуальные детали импортированного оружия. Риг не распоряжается патронами и инвентарём:
## он показывает подтверждённое состояние и возвращает исходную сборку при отмене действия.

signal sound_event(slot: String)
signal action_finished(action: String)

const PART_NAMES: Array[String] = ["Frame", "Slide", "Barrel", "Trigger", "Hammer", "SlideStop", "Safety", "MagCatch", "Magazine", "Suppressor"]
const REQUIRED_PARTS: Array[String] = ["Frame", "Slide", "Trigger", "Hammer", "SlideStop", "Safety", "MagCatch", "Magazine", "Suppressor"]
const MARKER_NAMES: Array[String] = ["Muzzle", "MuzzleSuppressed", "SightFront", "SightRear", "GripR", "GripL"]

var weapon_id: String = ""
var action: String = ""
var _config: Dictionary = {}
var _parts: Dictionary = {}
var _rest: Dictionary = {}
var _visual: Node3D
var _target: Marker3D
var _arms: Node3D
var _rounds: Array[Node3D] = []
var _round_rest: Array[bool] = []
var _ammo: int = 1
var _capacity: int = 0
var _chamber_capacity: int = 0
var _locked: bool = false
var _cocked: bool = false
var _suppressed: bool = false
var _install: bool = false
var _empty_reload: bool = false
var _running: bool = false
var _elapsed: float = 0.0
var _duration: float = 0.0
var _weight: float = 0.0
var _events: Array[Dictionary] = []


static func find_on(root: Node3D) -> WeaponRig:
	if root is WeaponRig:
		return root as WeaponRig
	if root == null:
		return null
	for node: Node in root.find_children("*", "Node3D", true, false):
		if node is WeaponRig:
			return node as WeaponRig
	return null


func _ready() -> void:
	set_process(_running)
	_apply_pose()


## Настройка до добавления в дерево: исходные transforms сохраняются один раз, до анимации.
func configure(id: String, weapon: Dictionary, imported: Node3D, lod: int) -> void:
	weapon_id = id
	_config = (weapon.get("rig", {}) as Dictionary).duplicate(true)
	_chamber_capacity = int(weapon.get("chamber_capacity", 0))
	_capacity = int(WeaponDb.magazine(WeaponDb.default_mag(id)).get("capacity", 0))
	_visual = Node3D.new()
	_visual.name = "VisualPose"
	add_child(_visual)
	_visual.add_child(imported)
	for part_name: String in PART_NAMES:
		var found: Node3D = imported.find_child(part_name, true, false) as Node3D
		if found:
			_parts[part_name] = found
			_rest[part_name] = found.transform
	for player: Node in imported.find_children("*", "AnimationPlayer", true, false):
		var animation: AnimationPlayer = player as AnimationPlayer
		animation.stop()
		animation.autoplay = ""
	var magazine: Node3D = part("Magazine")
	if magazine:
		_mark_part(magazine, "mag")
		var rounds: Node3D = magazine.find_child("Rounds", true, false) as Node3D
		if rounds:
			for child: Node in rounds.get_children():
				if child is Node3D:
					_rounds.append(child as Node3D)
					_round_rest.append((child as Node3D).visible)
	var suppressor: Node3D = part("Suppressor")
	if suppressor:
		_mark_part(suppressor, "muzzle_device")
	_target = Marker3D.new()
	_target.name = "ActionHandTarget"
	add_child(_target)
	set_meta("asset_loaded", true)
	set_meta("asset_lod", lod)
	set_meta("ads_z", float(_config.get("ads_z", 0.36)))
	var front: Node3D = marker("SightFront")
	var rear: Node3D = marker("SightRear")
	if front and rear:
		var front_at: Vector3 = _relative_transform(front, self).origin
		var rear_at: Vector3 = _relative_transform(rear, self).origin
		set_meta("sight_h", (front_at.y + rear_at.y) * 0.5)
		set_meta("sight_front", front_at)
		set_meta("sight_rear", rear_at)
	set_suppressed(false)
	set_process(false)


func part(part_name: String) -> Node3D:
	return _parts.get(part_name) as Node3D


func marker(marker_name: String) -> Node3D:
	return _visual.find_child(marker_name, true, false) as Node3D if _visual else null


func has_parts() -> bool:
	for part_name: String in REQUIRED_PARTS:
		if part(part_name) == null:
			return false
	for marker_name: String in ["Muzzle", "MuzzleSuppressed", "SightFront", "SightRear"]:
		if marker(marker_name) == null:
			return false
	return true


func attach_arms(arms: Node3D) -> void:
	if is_instance_valid(_arms) and _arms.has_method("set_hand_target"):
		_arms.call("set_hand_target", "Left", null, 0.0)
	_arms = arms
	_update_hand_binding()


func get_hand_target() -> Node3D:
	return _target


func get_hand_weight() -> float:
	return _weight


func is_slide_locked() -> bool:
	return _locked


func is_busy() -> bool:
	return action != ""


func action_progress() -> float:
	return clampf(_elapsed / _duration, 0.0, 1.0) if _duration > 0.0 else 0.0


func set_ammo_state(rounds: int) -> void:
	_ammo = maxi(0, rounds)
	_locked = _ammo == 0
	if not is_busy():
		action = ""
		_apply_pose()


## Видимость и дульный срез меняются только по подтверждённому набору обвесов.
func set_suppressed(installed: bool) -> void:
	_suppressed = installed
	set_meta("suppressor_installed", installed)
	if not is_busy():
		action = ""
		_apply_pose()
	_update_muzzle()


func play_shot(rounds_left: int) -> void:
	cancel_action()
	_ammo = maxi(0, rounds_left)
	_locked = _ammo == 0
	_cocked = true
	_begin("shot", float(_config.get("shot_duration", 0.0)))
	if _locked:
		_queue_sound("bolt_lock", float(_config.get("shot_peak", 0.0)))
	_apply_pose()


func play_reload(empty: bool, duration: float) -> void:
	cancel_action()
	_empty_reload = empty
	_begin("reload", duration)
	var phases: Dictionary = _config.get("reload", {})
	_queue_sound("mag_out", float(phases.get("mag_out", 0.0)))
	_queue_sound("mag_in", float(phases.get("mag_in", 1.0)))
	if empty:
		_queue_sound("charge", float(phases.get("charge", 1.0)))
	_apply_pose()


func finish_reload(rounds: int) -> void:
	cancel_action()
	_cocked = rounds > 0
	set_ammo_state(rounds)


func play_suppressor(install: bool, duration: float = -1.0) -> void:
	cancel_action()
	_install = install
	var tuning: Dictionary = _config.get("suppressor", {})
	_begin("suppressor", duration if duration >= 0.0 else float(tuning.get("duration", 0.0)))
	_queue_sound("suppressor_on" if install else "suppressor_off", float(tuning.get("turn_end", 1.0)))
	_apply_pose()


## Отмена восстанавливает модель, но не подтверждает предмет, который ещё находится у хоста.
func cancel_action() -> void:
	_running = false
	action = ""
	_elapsed = 0.0
	_duration = 0.0
	_events.clear()
	set_process(false)
	_apply_pose()


## Детерминированная поза для снимков и тестов; не проигрывает звуки и не меняет инвентарь.
func pose_action(action_name: String, progress: float, empty: bool = false) -> void:
	cancel_action()
	action = action_name
	_empty_reload = empty
	_install = not _suppressed
	_duration = 1.0
	_elapsed = clampf(progress, 0.0, 1.0)
	_apply_pose()


## Камера получает фазу от модели тела: переключение вида не запускает второй таймер и звуки.
func synchronize_from(other: WeaponRig) -> void:
	if other == null or other == self:
		return
	_running = false
	set_process(false)
	_events.clear()
	_ammo = other._ammo
	_locked = other._locked
	_cocked = other._cocked
	_suppressed = other._suppressed
	_install = other._install
	_empty_reload = other._empty_reload
	action = other.action
	_elapsed = other._elapsed
	_duration = other._duration
	set_meta("suppressor_installed", _suppressed)
	_apply_pose()


func _begin(action_name: String, duration: float) -> void:
	action = action_name
	_duration = maxf(0.0, duration)
	_elapsed = 0.0
	_running = _duration > 0.0
	if not _running:
		action = ""
	set_process(_running)


func _queue_sound(slot: String, fraction: float) -> void:
	_events.append({"slot": slot, "at": clampf(fraction, 0.0, 1.0), "played": false})


func _process(delta: float) -> void:
	advance_action(delta)


## Один и тот же расчёт обслуживает кадры игры и headless-проверку промежуточных фаз.
func advance_action(delta: float) -> void:
	if not _running:
		return
	_elapsed = minf(_duration, _elapsed + maxf(0.0, delta))
	var progress: float = action_progress()
	_apply_pose()
	for event: Dictionary in _events:
		if not bool(event.played) and progress >= float(event.at):
			event.played = true
			sound_event.emit(String(event.slot))
	if progress >= 1.0:
		var finished: String = action
		_running = false
		set_process(false)
		# Последняя поза ждёт подтверждения перезарядки/обвеса, не возвращая затвор назад.
		if finished == "shot":
			action = ""
			_apply_pose()
		action_finished.emit(finished)


func _apply_pose() -> void:
	if _visual == null:
		return
	_visual.transform = Transform3D.IDENTITY
	for part_name: String in _rest:
		var node: Node3D = part(part_name)
		if node:
			node.transform = _rest[part_name] as Transform3D
	var magazine: Node3D = part("Magazine")
	if magazine:
		magazine.visible = true
	var suppressor: Node3D = part("Suppressor")
	if suppressor:
		suppressor.visible = _suppressed
	_show_rounds(maxi(0, _ammo - _chamber_capacity))
	_weight = 0.0
	if _cocked:
		_rotate_part("Hammer", _vector(_config.get("hammer_axis", [1, 0, 0])), float(_config.get("hammer_cocked_deg", 0.0)))
	if _locked:
		_slide(1.0)
		_rotate_part("SlideStop", Vector3.RIGHT, float(_config.get("slide_stop_angle_deg", 0.0)))
	var progress: float = action_progress()
	match action:
		"shot":
			_pose_shot(progress)
		"reload":
			_pose_reload(progress)
		"suppressor":
			_pose_suppressor(progress)
	_update_muzzle()
	_update_hand_binding()


func _pose_shot(progress: float) -> void:
	var peak: float = float(_config.get("shot_peak", 0.5))
	var recoil: float = _ramp(progress, 0.0, peak) if progress <= peak else (1.0 if _locked else 1.0 - _ramp(progress, peak, 1.0))
	_slide(recoil)
	_rotate_part("Hammer", _vector(_config.get("hammer_axis", [1, 0, 0])), float(_config.get("hammer_cocked_deg", 0.0)) * _ramp(progress, 0.0, peak))
	_rotate_part("Trigger", _vector(_config.get("trigger_axis", [1, 0, 0])), float(_config.get("trigger_angle_deg", 0.0)) * (1.0 - _ramp(progress, peak, 1.0)))
	_rotate_part("SlideStop", Vector3.RIGHT, float(_config.get("slide_stop_angle_deg", 0.0)) * (recoil if _locked else 0.0))


func _pose_reload(progress: float) -> void:
	var phases: Dictionary = _config.get("reload", {})
	var out_at: float = float(phases.get("mag_out", 0.0))
	var hidden_at: float = float(phases.get("mag_hidden", out_at))
	var new_at: float = float(phases.get("mag_new", hidden_at))
	var in_at: float = float(phases.get("mag_in", 1.0))
	var catch_at: float = float(phases.get("catch", 0.0))
	var extraction: Vector3 = _vector(_config.get("magazine_out_m", [0, 0, 0]))
	var magazine: Node3D = part("Magazine")
	_rotate_part("MagCatch", Vector3.RIGHT, float(_config.get("mag_catch_angle_deg", 0.0)) * (1.0 - _ramp(progress, in_at, 1.0)) * _ramp(progress, 0.0, catch_at))
	if magazine:
		var amount: float = _ramp(progress, catch_at, hidden_at) if progress < new_at else 1.0 - _ramp(progress, new_at, in_at)
		_move_part("Magazine", extraction * amount)
		magazine.visible = not (progress >= hidden_at and progress < new_at)
		if progress >= new_at:
			_show_rounds(_capacity)
		var target_at: Transform3D = _relative_transform(magazine, self)
		_hand_pose(target_at, _hand_offset("magazine"), _ramp(progress, 0.0, out_at) * (1.0 - _ramp(progress, in_at, 1.0)))
	if _empty_reload:
		var charge_at: float = float(phases.get("charge", 1.0))
		var charge_end: float = float(phases.get("charge_end", 1.0))
		_slide(1.0 - _ramp(progress, charge_at, charge_end))
		_rotate_part("SlideStop", Vector3.RIGHT, float(_config.get("slide_stop_angle_deg", 0.0)) * (1.0 - _ramp(progress, charge_at, charge_end)))
		if progress >= in_at:
			var slide_node: Node3D = part("Slide")
			if slide_node:
				_hand_pose(_relative_transform(slide_node, self), _hand_offset("slide"), _ramp(progress, in_at, charge_at) * (1.0 - _ramp(progress, charge_end, 1.0)))


func _pose_suppressor(progress: float) -> void:
	var tuning: Dictionary = _config.get("suppressor", {})
	var grasp: float = float(tuning.get("grasp", 0.0))
	var start: float = float(tuning.get("turn_start", grasp))
	var end: float = float(tuning.get("turn_end", 1.0))
	var release: float = float(tuning.get("release", 1.0))
	var held: float = _ramp(progress, 0.0, grasp) * (1.0 - _ramp(progress, release, 1.0))
	_visual.rotation_degrees = _vector(tuning.get("weapon_rotation_deg", [0, 0, 0])) * held
	var suppressor: Node3D = part("Suppressor")
	if not suppressor:
		return
	var turns: float = _ramp(progress, start, end)
	var amount: float = 1.0 - turns if _install else turns
	_move_part("Suppressor", Vector3.FORWARD * -float(tuning.get("travel_m", 0.0)) * amount)
	_rotate_part("Suppressor", Vector3.BACK, float(tuning.get("turns", 0.0)) * 360.0 * amount, false)
	suppressor.visible = progress >= grasp if _install else progress < release
	_hand_pose(_relative_transform(suppressor, self), _hand_offset("suppressor"), held)


func _hand_pose(at: Transform3D, offset: Vector3, weight: float) -> void:
	var grip: Node3D = find_child("LeftGrip", true, false) as Node3D
	var basis: Basis = _relative_transform(grip, self).basis.orthonormalized() if grip else Basis.IDENTITY
	_target.transform = Transform3D(basis, at.origin + _visual.basis * offset)
	_weight = clampf(weight, 0.0, 1.0)


## Смещение в осях камеры удерживает магазин и поддерживающую кисть в кадре.
## Отмена и завершение возвращают обычное положение оружия у бедра и в прицеле.
func view_offset() -> Vector3:
	if action == "":
		return Vector3.ZERO
	var pose: Dictionary = (_config.get("viewmodel_offsets", {}) as Dictionary).get(action, {}) as Dictionary
	if pose.is_empty():
		return Vector3.ZERO
	var progress: float = action_progress()
	var weight: float = smoothstep(0.0, float(pose.in_end), progress) * (1.0 - smoothstep(float(pose.out_start), 1.0, progress))
	return _vector(pose.offset_m) * weight


## Наклон при перезарядке показывает магазин сбоку; обе кисти наследуют этот поворот.
func view_rotation_degrees() -> Vector3:
	if action == "":
		return Vector3.ZERO
	var pose: Dictionary = (_config.get("viewmodel_offsets", {}) as Dictionary).get(action, {}) as Dictionary
	if pose.is_empty():
		return Vector3.ZERO
	var progress: float = action_progress()
	var weight: float = smoothstep(0.0, float(pose.in_end), progress) * (1.0 - smoothstep(float(pose.out_start), 1.0, progress))
	return _vector(pose.get("rotation_deg", [0, 0, 0])) * weight


func _hand_offset(key: String) -> Vector3:
	return _vector((_config.get("hand_offsets", {}) as Dictionary).get(key, [0, 0, 0]))


func _update_hand_binding() -> void:
	if is_instance_valid(_arms) and _arms.has_method("set_hand_target"):
		_arms.call("set_hand_target", "Left", _target, _weight)


func _update_muzzle() -> void:
	var muzzle: Node3D = marker("MuzzleSuppressed" if _suppressed else "Muzzle")
	if muzzle:
		set_meta("muzzle", _relative_transform(muzzle, self).origin)


func _slide(amount: float) -> void:
	_move_part("Slide", Vector3.FORWARD * float(_config.get("slide_travel_m", 0.0)) * clampf(amount, 0.0, 1.0))


func _move_part(part_name: String, displacement: Vector3) -> void:
	var node: Node3D = part(part_name)
	if node:
		var resting: Transform3D = _rest[part_name] as Transform3D
		var parent_pose: Transform3D = _relative_transform(node.get_parent() as Node3D, _visual)
		node.position = resting.origin + parent_pose.basis.inverse() * displacement


func _rotate_part(part_name: String, axis: Vector3, angle_degrees: float, restore_origin: bool = true) -> void:
	var node: Node3D = part(part_name)
	if node and not axis.is_zero_approx():
		var resting: Transform3D = _rest[part_name] as Transform3D
		var parent_pose: Transform3D = _relative_transform(node.get_parent() as Node3D, _visual)
		var axis_parent: Vector3 = (parent_pose.basis.inverse() * axis).normalized()
		node.basis = Basis(axis_parent, deg_to_rad(angle_degrees)) * resting.basis
		if restore_origin:
			node.position = resting.origin


func _show_rounds(count: int) -> void:
	for index: int in range(_rounds.size()):
		_rounds[index].visible = index < count and _round_rest[index]


static func _mark_part(node: Node3D, part_key: String) -> void:
	node.set_meta("part", part_key)
	for child: Node in node.find_children("*", "MeshInstance3D", true, false):
		child.set_meta("part", part_key)


## Работает и до add_child в SceneTree; global_transform в этот момент ещё не определён.
static func _relative_transform(node: Node3D, ancestor: Node3D) -> Transform3D:
	var result: Transform3D = Transform3D.IDENTITY
	var current: Node = node
	while current != null and current != ancestor:
		if current is Node3D:
			result = (current as Node3D).transform * result
		current = current.get_parent()
	return result


static func _vector(value: Variant) -> Vector3:
	if value is Vector3:
		return value as Vector3
	if value is Array and (value as Array).size() >= 3:
		var entries: Array = value as Array
		return Vector3(float(entries[0]), float(entries[1]), float(entries[2]))
	return Vector3.ZERO


static func _ramp(value: float, from: float, to: float) -> float:
	if to <= from:
		return 1.0 if value >= to else 0.0
	var fraction: float = clampf((value - from) / (to - from), 0.0, 1.0)
	return fraction * fraction * (3.0 - 2.0 * fraction)


func _exit_tree() -> void:
	if is_instance_valid(_arms) and _arms.has_method("set_hand_target"):
		_arms.call("set_hand_target", "Left", null, 0.0)
