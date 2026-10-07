extends Node
## Тир котельной: дорожки и мишени на месте, ствол стойки выдаётся без расхода вещей профиля,
## попадание оставляет пробоину, кнопки двигают мишень и меняют лист, выход из зала возвращает своё.
## tools/godot.cmd --headless res://tools/shooting_range_test.tscn

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://shooting_range_test.json", true)
	get_tree().change_scene_to_file("res://scenes/levels/hideout.tscn")
	await _frames(30)
	var level: Node = get_tree().current_scene
	var pl: Player = level.get("_player") as Player
	var range_node: ShootingRange = level.get_node_or_null("Gameplay/ShootingRange") as ShootingRange
	_check("в убежище есть тир", range_node != null)
	if range_node == null:
		_finish()
		return
	var lanes: Array[RangeLane] = range_node.lanes()
	var paper: int = 0
	var mannequins: int = 0
	for lane: RangeLane in lanes:
		if lane.target() and lane.target().kind == RangeTarget.Kind.PAPER:
			paper += 1
		elif lane.target():
			mannequins += 1
	_check("пять дорожек: три листа и два манекена", lanes.size() == 5 and paper == 3 and mannequins == 2)
	_check("на каждой дорожке три кнопки", level.find_children("*", "RangeButton", true, false).size() == 15)
	var rack: RangeWeaponRack = level.get_node_or_null("Gameplay/RangeWeaponRack") as RangeWeaponRack
	_check("стойка тира на месте", rack != null)
	var profile_before: String = _profile_sig()
	var lane: RangeLane = lanes[0]
	var fx: float = range_node.global_position.x
	pl.global_position = Vector3(fx - 1.2, .1, lane.global_position.z)
	await _frames(10)
	_check("стрелок на рубеже — в зале тира", range_node.contains(pl.global_position))
	rack.request_use()
	await _frames(2)
	var picker: RangeWeaponPicker = rack.get("_picker") as RangeWeaponPicker
	_check("окно стойки открылось", picker != null and picker.is_open())
	picker.call("_take", "wpn_sp_02", "VSS_BASE")
	await _frames(5)
	_check("ВСС со стойки в руках", pl.in_range_mode() and pl.weapon_id == "wpn_sp_02")
	_check("в тире без гранат", pl.grenade_count() == 0)
	_check("окно закрылось после выбора", not picker.is_open())
	# выстрел прямо в центр листа — пробоина и урон по мишени
	var target: RangeTarget = lane.target()
	var hits: Array[float] = []
	target.hit.connect(func(dmg: float, _head: bool) -> void: hits.append(dmg))
	var aim: Vector3 = target.global_transform * Vector3(0, 1.45, 0)
	var from: Vector3 = pl.eye_position()
	var exclude: Array[RID] = [pl.get_rid()]
	var shot: Dictionary = Hitscan.fire(get_viewport().get_world_3d(), from, (aim - from).normalized(), 0.0, 80.0, Hitscan.LAYER_WORLD | Hitscan.LAYER_MARAUDER, 40.0, exclude, RandomNumberGenerator.new())
	await _frames(2)
	_check("пуля попала в лист", shot.get("collider") == target and hits.size() == 1)
	_check("на листе пробоина", target.hole_count() == 1)
	# кнопки: дальше, ближе, сменить лист
	var start: float = lane.goal_distance()
	lane.press("farther")
	_check("«дальше» — следующая остановка", lane.goal_distance() > start)
	await _frames(int(ceil((lane.goal_distance() - start) / float(Balance.RANGE.carrier_mps) * 60.0)) + 30)
	_check("тележка доехала", is_equal_approx(lane.distance_now(), lane.goal_distance()))
	_check("мишень стоит на новой дистанции", absf(-target.position.z - lane.goal_distance()) < .01)
	lane.press("closer")
	lane.press("closer")
	_check("«ближе» дважды — ближе исходной", lane.goal_distance() < start)
	lane.press("reset")
	_check("сменить лист — пробоин нет", target.hole_count() == 0)
	_check("профиль не тронут, пока ствол стойки в руках", _profile_sig() == profile_before)
	# ушёл из зала — ствол стойки остаётся
	pl.global_position = Vector3(12, .1, 4)
	await _frames(10)
	_check("вышел из зала — ствол сдан", not pl.in_range_mode() and pl.loadout_mode)
	_check("своё снаряжение и рюкзак как были", _profile_sig() == profile_before)
	_finish()


func _profile_sig() -> String:
	return str(Profile.equipment) + str(Profile.backpack) + str(Profile.pocket) + str(Profile.stash) + str(Profile.money)


func _check(what: String, ok: bool) -> void:
	print(("  [ok] " if ok else "  [FAIL] ") + what)
	if not ok:
		_fails += 1


func _finish() -> void:
	print("shooting_range_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _frames(n: int) -> void:
	for i: int in range(n):
		await get_tree().physics_frame
