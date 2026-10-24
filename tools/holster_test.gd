extends Node
## Оружие убирается клавишей своего слота и достаётся ею же: руки пусты, бег быстрее и легче; другая
## клавиша — другой ствол. И: с открытым рюкзаком в рейде персонаж не ходит.
## tools/godot.cmd --headless res://tools/holster_test.tscn

var _fails: int = 0
var _me: Player


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in level.get_node("Marauders").get_children():
		m.queue_free()
	_me = Raid.current.local_player()
	_me.health.invulnerable = true
	await _frames(20)
	var keys: Array = _me.weapon_keys()
	_me._switch(String(keys[0]), false)
	await _frames(5)
	var gun: String = _me.weapon_id
	_check("ствол в руках", gun != "" and not _me.holstered)
	Input.action_press("sprint")
	await _frames(3)
	var armed: float = _me._stance_speed()
	await _tap("weapon_1")
	_check("клавиша своего слота — оружие убрано, слот помнится", _me.weapon_id == "" and _me.holstered and _me.weapon_slot == String(keys[0]))
	var free: float = _me._stance_speed()
	_check("с убранным оружием бежит быстрее", is_equal_approx(free / armed, float(Balance.HOLSTER.sprint_k)), "%.2f → %.2f" % [armed, free])
	Input.action_release("sprint")
	Input.action_press("fire")
	await _frames(10)
	Input.action_release("fire")
	_check("убранное оружие не стреляет и само не возвращается", _me.weapon_id == "" and _me.holstered)
	await _tap("weapon_1")
	_check("та же клавиша — оружие снова в руках", _me.weapon_id == gun and not _me.holstered)
	await _tap("weapon_1")
	await _tap("weapon_2")
	_check("убрано, затем другая клавиша — в руках другой ствол", _me.weapon_id != "" and _me.weapon_slot == String(keys[1]) and not _me.holstered, _me.weapon_id)
	# рюкзак открыт — стоит
	var moved: float = await _walk()
	_check("без окон персонаж идёт", moved > 0.3, "%.2f м" % moved)
	await _tap("inventory")
	_check("рюкзак открыт", Raid.current.ui_open())
	moved = await _walk()
	_check("с открытым рюкзаком персонаж стоит", moved < 0.05, "%.2f м" % moved)
	await _tap("inventory")
	moved = await _walk()
	_check("рюкзак закрыт — снова идёт", not Raid.current.ui_open() and moved > 0.3, "%.2f м" % moved)
	print("holster_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _tap(action: String) -> void:
	Input.action_press(action)
	await _frames(3)
	Input.action_release(action)
	await _frames(6)


func _walk() -> float:
	var from: Vector3 = _me.global_position
	Input.action_press("move_forward")
	await get_tree().create_timer(0.6).timeout
	Input.action_release("move_forward")
	await _frames(20)
	var d: Vector3 = _me.global_position - from
	return Vector2(d.x, d.z).length()


func _check(what: String, ok: bool, note: String = "") -> void:
	print("[%s] %s %s" % ["ok" if ok else "ПРОВАЛ", what, note])
	if not ok:
		_fails += 1


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame
