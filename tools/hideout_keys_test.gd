extends Node
## Клавиши под окном убежища: открыт торговец (или набирают текст в поиске) — движение и стойка
## персонажу не идут; закрыли окно — снова ходит.
## tools/godot.cmd --headless res://tools/hideout_keys_test.tscn

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://hideout_keys_test.json", true)
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	await _frames(120)
	var level: Node = get_tree().current_scene
	var pl: Player = level.get("_player") as Player
	_check("без окон клавиши идут персонажу", not pl.keys_blocked())
	var moved: float = await _walk(pl)
	_check("без окон персонаж идёт", moved > 0.3, "%.2f м" % moved)
	for st: Node in get_tree().get_nodes_in_group("interactables"):
		if st is HideoutStation and (st as HideoutStation).kind == HideoutStation.Kind.TRADER:
			level.call("open_station", st)
			break
	await _frames(10)
	var ui: HideoutUI = level.get("_ui") as HideoutUI
	_check("окно торговца открыто — клавиши заблокированы", ui.is_open() and pl.keys_blocked())
	var stance: int = pl.stance
	Input.action_press("crouch")
	moved = await _walk(pl)
	Input.action_release("crouch")
	_check("под окном торговца персонаж стоит на месте и не приседает", moved < 0.05 and pl.stance == stance, "%.2f м" % moved)
	ui.close_ui()
	await _frames(10)
	_check("окно закрыли — клавиши снова идут персонажу", not pl.keys_blocked())
	moved = await _walk(pl)
	_check("после окна персонаж снова идёт", moved > 0.3, "%.2f м" % moved)
	# набор текста в любом поле — тоже
	var layer := CanvasLayer.new()
	add_child(layer)
	var edit := LineEdit.new()
	layer.add_child(edit)
	edit.grab_focus()
	await _frames(3)
	moved = await _walk(pl)
	_check("набирают текст — персонаж стоит", UiTheme.typing() and moved < 0.05, "%.2f м" % moved)
	print("hideout_keys_test: провалено %d" % _fails)
	get_tree().quit(_fails)


## Полсекунды «вперёд»: сколько прошёл по земле.
func _walk(pl: Player) -> float:
	var from: Vector3 = pl.global_position
	Input.action_press("move_forward")
	await get_tree().create_timer(0.6).timeout
	Input.action_release("move_forward")
	await _frames(20)
	var d: Vector3 = pl.global_position - from
	return Vector2(d.x, d.z).length()


func _check(what: String, ok: bool, note: String = "") -> void:
	print("[%s] %s %s" % ["ok" if ok else "ПРОВАЛ", what, note])
	if not ok:
		_fails += 1


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame
