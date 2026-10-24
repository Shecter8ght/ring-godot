extends Node
## Анимации Persona по стойкам при частоте кадров как у быстрого монитора (144 к/с, физика 60):
## идёт — клип ходьбы не скачет, с автоматом бегом — спринт, присед на месте и ходьба вприсядку
## (и без своих клипов — с пистолетом) — ступни на полу, лёжа — тело на земле; оружие — в правой
## руке в любой стойке (стоя на уровне груди, в приседе ниже, лёжа у земли).
## godot --headless res://tools/anim_test.tscn

const FPS := 144

var _fails: int = 0
var _p: Player
var _an: CharacterAnimator
var _sk: Skeleton3D
var _hands: Dictionary = {}


func _ready() -> void:
	Engine.max_fps = FPS
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for enemy in level.get_node("Marauders").get_children():
		enemy.process_mode = Node.PROCESS_MODE_DISABLED
	_p = get_tree().get_first_node_in_group("players") as Player
	_p.health.hp = 100000.0
	_an = _p.get_node("CharacterAnimator") as CharacterAnimator
	_sk = _p.get_node("Body/Persona").find_children("*", "Skeleton3D", true, false)[0] as Skeleton3D
	await get_tree().create_timer(0.5).timeout
	var keys: Array = _p.weapon_keys()
	_p._switch(String(keys[0]), false)
	_an._support.modification_processed.connect(_record_hands)
	var stand := await _run(Player.Stance.STAND, "", false)
	_check("стоя: оружие в руке, на уровне груди", float(stand.gun_hand) < 0.25 and float(stand.gun_y) > 0.9, "от руки %.2f м, высота %.2f" % [stand.gun_hand, stand.gun_y])
	var walk := await _run(Player.Stance.STAND, "move_forward", false)
	_check("идёт: оружие не отстаёт от руки", float(walk.gun_hand) < 0.25, "от руки %.2f м" % float(walk.gun_hand))
	_check("левая кисть на цевье — стоя и на ходу (ИК)", float(stand.left) < 0.06 and float(walk.left) < 0.06, "мимо метки хвата: стоя %.3f м, идёт %.3f м" % [stand.left, walk.left])
	_check("автомат, идёт (%d к/с) — клип ходьбы не скачет" % FPS, String(walk.clip).begins_with("rifle_walk") and int(walk.switches) <= 1, "%s, смен %d" % [walk.clip, walk.switches])
	var sprint := await _run(Player.Stance.STAND, "move_forward", true)
	_check("автомат, бегом — спринт", String(sprint.clip) == "rifle_sprint", String(sprint.clip))
	var idle := await _run(Player.Stance.CROUCH, "", false)
	_check("присед на месте — ступни на полу", absf(float(idle.toe)) < 0.08, "%s, носок %.2f" % [idle.clip, idle.toe])
	_check("присед: оружие в руке и ниже, чем стоя", float(idle.gun_hand) < 0.25 and float(idle.gun_y) < float(stand.gun_y) - 0.25, "от руки %.2f м, высота %.2f (стоя %.2f)" % [idle.gun_hand, idle.gun_y, stand.gun_y])
	var cwalk := await _run(Player.Stance.CROUCH, "move_forward", false)
	_check("ходьба вприсядку — ступни на полу", String(cwalk.clip).contains("crouch_walk") and absf(float(cwalk.toe)) < 0.08 and int(cwalk.switches) <= 1, "%s, носок %.2f, смен %d" % [cwalk.clip, cwalk.toe, cwalk.switches])
	_p._switch(String(keys[1]), false)
	var pwalk := await _run(Player.Stance.CROUCH, "move_forward", false)
	_check("с пистолетом вприсядку — ноги не в полу", String(pwalk.clip).contains("crouch_walk") and absf(float(pwalk.toe)) < 0.08, "%s, носок %.2f" % [pwalk.clip, pwalk.toe])
	var prone := await _run(Player.Stance.PRONE, "", false)
	_check("лёжа — тело на земле", String(prone.clip).begins_with("prone") and float(prone.hips) < 0.45, "%s, таз %.2f" % [prone.clip, prone.hips])
	_check("лёжа: оружие в руке, у земли", float(prone.gun_hand) < 0.25 and float(prone.gun_y) < 0.6, "от руки %.2f м, высота %.2f" % [prone.gun_hand, prone.gun_y])
	print("anim_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


## Стойка и движение 1 с на разгон, потом 2 с замера: клип, сколько раз сменился, нижняя точка
## носков и таз (от пола капсулы).
func _run(stance: int, move: String, sprint: bool) -> Dictionary:
	_p.global_position = Vector3(100.0, 0.1, -5.0)
	_p.stance = stance
	_p._apply_stance()
	if move != "":
		Input.action_press(move)
	if sprint:
		Input.action_press("sprint")
	await get_tree().create_timer(1.0).timeout
	var toe := INF
	var hips := 0.0
	var gun_y := 0.0
	var gun_hand := 0.0
	var left := 0.0
	var switches := 0
	var last := _an._current
	var t := 0.0
	while t < 2.0:
		await get_tree().process_frame
		t += get_process_delta_time()
		if _an._current != last:
			switches += 1
			last = _an._current
		for b in ["mixamorig_LeftToeBase", "mixamorig_RightToeBase"]:
			toe = minf(toe, _bone_y(b))
		hips = _bone_y("mixamorig_Hips")
		# оружие: высота над полом и как далеко от кости правой руки (должно лежать в ладони)
		var gun := _p._weapon_model
		if gun and is_instance_valid(gun):
			gun_y = gun.global_position.y - _p.global_position.y
			var hand: Vector3 = _hands.get("Right", gun.global_position)
			gun_hand = maxf(gun_hand, gun.global_position.distance_to(hand))
			# левая кисть — от запястья до места, где его ставит метка хвата LeftGrip (после разгона)
			var mark := gun.find_child("LeftGrip", false, false) as Marker3D
			if mark and t > 0.5:
				var want := mark.global_position - mark.global_basis.orthonormalized() * (mark.get_meta("palm_offset", Vector3.ZERO) as Vector3)
				var lh: Vector3 = _hands.get("Left", want)
				left = maxf(left, lh.distance_to(want))
	for a in ["move_forward", "sprint"]:
		Input.action_release(a)
	await get_tree().create_timer(0.4).timeout
	return {"clip": last, "switches": switches, "toe": toe, "hips": hips, "gun_y": gun_y, "gun_hand": gun_hand, "left": left}


## После модификатора позы доступны до их восстановления AnimationMixer.
func _record_hands() -> void:
	for side: String in ["Right", "Left"]:
		_hands[side] = (_sk.global_transform * _sk.get_bone_global_pose(_sk.find_bone("mixamorig_" + side + "Hand"))).origin


func _bone_y(bone: String) -> float:
	return (_sk.global_transform * _sk.get_bone_global_pose(_sk.find_bone(bone))).origin.y - _p.global_position.y


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
