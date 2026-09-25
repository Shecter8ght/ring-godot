extends Node
## Чит «бессмертие»: попадание в голову, граната вплотную, очередь — жив и здоров; лежал раненым —
## встаёт; выключил — урон снова проходит. godot --headless --path . res://tools/god_test.tscn

var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var inst: Node = load(Balance.RAID_SCENE).instantiate()
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	for i in range(20):
		await get_tree().physics_frame
	var pl := get_tree().get_first_node_in_group("players") as Player
	var h := pl.health
	h.take_damage(60.0, pl.global_position + Vector3.FORWARD)
	_check("без чита урон проходит", h.hp < h.max_hp, "%.0f" % h.hp)
	h.take_damage(500.0, pl.global_position + Vector3.FORWARD)
	_check("…и кладёт раненым", h.downed, "")
	pl.set_god(true)
	await get_tree().process_frame
	await get_tree().process_frame
	_check("включил бессмертие лёжа — встал", h.alive and not h.downed, "")
	pl._apply_god(true)
	_check("здоровье полное", h.hp >= h.max_hp, "%.0f" % h.hp)
	h.take_damage(500.0, pl.global_position + Vector3.FORWARD, "head")
	h.take_damage(500.0, pl.global_position, "blast_close")
	for i in range(30):
		h.take_damage(40.0, pl.global_position + Vector3.FORWARD, "thorax")
	_check("голова, граната вплотную, очередь — жив и здоров", h.alive and not h.downed and h.hp >= h.max_hp, "%.0f" % h.hp)
	pl.set_god(false)
	h.take_damage(30.0, pl.global_position + Vector3.FORWARD)
	_check("выключил — урон снова проходит", h.hp < h.max_hp, "%.0f" % h.hp)
	print("god_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
