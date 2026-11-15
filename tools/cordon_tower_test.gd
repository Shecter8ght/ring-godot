extends Node3D
## Headless — проходимость от двери до площадки и обратно плюс лучи Hitscan.
## С окном — ручной проход. Аргумент shots рендерит проверочные кадры и выходит.

const PLAYER := preload("res://scenes/player/player.tscn")
const CAMERA_RIG := preload("res://scenes/player/camera_rig.tscn")
const DECK_Y := 6.99
@onready var _tower: Node3D = $CordonTower
@onready var _ladder: Ladder = $CordonTower/Ladder
@onready var _door: Door = $CordonTower/Door
@onready var _concrete: StaticBody3D = $CordonTower/Concrete
var _player: Player
var _manual := false
var _fails := 0
var _rng := RandomNumberGenerator.new()


func _ready() -> void:
	RaidEvents.enabled = false
	var headless := DisplayServer.get_name() == "headless"
	if not headless and OS.get_cmdline_user_args().has("shots"):
		await _shots()
		return
	_player = PLAYER.instantiate() as Player
	_player.name = "Player_1"
	add_child(_player)
	_player.global_position = Vector3(0, 0.10, -2.48)
	_player.get_node("Body").rotation.y = 0.0
	_player.cursor_ground = Vector3(0, 0.0, 1.0)
	await _frames(10)
	if not headless:
		_manual = true
		var rig := CAMERA_RIG.instantiate() as CameraRig
		add_child(rig)
		rig.set_target(_player)
		rig._look_yaw = PI
		var overlay := CanvasLayer.new()
		add_child(overlay)
		var help := Label.new()
		help.text = "F — дверь и лестница   ·   W / S — вверх / вниз"
		help.position = Vector2(24, 20)
		help.add_theme_font_size_override("font_size", 20)
		overlay.add_child(help)
		return
	await _verify()
	print("cordon_tower_test: %d failures" % _fails)
	get_tree().quit(1 if _fails else 0)


func _process(_delta: float) -> void:
	if not _manual or not Input.is_action_just_pressed("interact"):
		return
	for name in ["Bottom", "Top"]:
		var point := _ladder.get_node(name) as LadderPoint
		if point.can_use():
			point.request_use()
			return


func _verify() -> void:
	var bottom := _ladder.get_node("Bottom") as LadderPoint
	var top := _ladder.get_node("Top") as LadderPoint
	var leaf := _door.get_node("Leaf") as StaticBody3D
	_check("импорт: бетон и металл башни отдельны от створки", _mesh_count(_tower.get_node("Model")) == 2
		and _mesh_count(leaf.get_node("Finish")) == 1)
	_check("три материала импортированы с атласами цвета, нормалей и блеска",
		_pbr_ready(_tower.get_node("Model")) and _pbr_ready(leaf.get_node("Finish")))
	_check("точка монтажа выше пола, дверь закрыта", is_equal_approx(_tower.get_node("EquipmentAnchor").position.y, DECK_Y)
		and not _door.is_open)
	_check("закрытая створка ловит выстрел", _shot(Vector3(0, 1.19, -3), Vector3.BACK, 2.4) == leaf)
	_check("лестница не перехватывает F снаружи", not bottom.can_use())
	await _frames(2)
	_player.global_position.y = 0.13
	var blocked := _player.move_and_collide(Vector3.BACK * 1.35)
	_check("закрытая створка держит капсулу игрока", blocked != null and blocked.get_collider() == leaf)
	_player.global_position = Vector3(0, 0.08, -2.48)
	await _frames(4)
	await _tap_door()
	_check("F открывает дверь, створка и коллайдер повернулись", _door.is_open
		and absf(leaf.rotation.y) > 1.45 and _mesh_count(leaf.get_node("Finish")) == 1)
	_check("свободный дверной проём пропускает выстрел", _shot(Vector3(0, 1.19, -3), Vector3.BACK, 2.4) == null)
	_player.global_position.y = 0.13
	var cross := _player.move_and_collide(Vector3.BACK * 1.50)
	_check("капсула проходит в шахту через открытую дверь", cross == null and _player.global_position.z > -1.2,
		str(_player.global_position))
	await _frames(5)
	_check("нижняя точка доступна изнутри", bottom.can_use())
	bottom.request_use()
	await _frames(30)
	_check("игрок взялся за штатную лестницу", _player.is_climbing())
	var exit := _ladder.top_exit(get_world_3d().direct_space_state, [_player.get_rid()])
	_check("у лестницы есть выход на площадку", not exit.is_empty(), str(exit.get("land", Vector3.ZERO)))
	Input.action_press("move_forward")
	for i in range(700):
		await get_tree().physics_frame
		if not _player.is_climbing() and not _player.is_vaulting():
			break
	Input.action_release("move_forward")
	await _frames(8)
	_check("поднялся по лестнице и встал на площадку",
		not _player.is_climbing() and absf(_player.global_position.y - DECK_Y) < 0.12
		and absf(_player.global_position.x + 0.51) < 0.21, str(_player.global_position))
	_check("верхняя точка позволяет спуститься", top.can_use())
	top.request_use()
	Input.action_press("move_back")
	for i in range(700):
		await get_tree().physics_frame
		if not _player.is_climbing() and not _player.is_vaulting():
			break
	Input.action_release("move_back")
	await _frames(9)
	_check("спустился до пола", not _player.is_climbing() and _player.global_position.y < 0.15,
		str(_player.global_position))
	_player.global_position = Vector3(0, 0.12, -2.48)
	await _frames(6)
	await _tap_door()
	_check("F закрывает дверь, выстрел снова попадает в створку", not _door.is_open
		and absf(leaf.rotation.y) < 0.10 and _shot(Vector3(0, 1.19, -3), Vector3.BACK, 2.4) == leaf)

	var clear_count := 0
	for y in [8.06, 8.55, 9.16]:
		for side in [-1.0, 1.0]:
			if _shot(Vector3(0.64, y, side * 3.0), Vector3(0, 0, -side), 6.0) == null:
				clear_count += 1
			if _shot(Vector3(side * 3.0, y, 0.67), Vector3(-side, 0, 0), 6.0) == null:
				clear_count += 1
	_check("Hitscan проходит через четыре сквозных проёма", clear_count == 12, "%d/12" % clear_count)
	_check("стойки, парапет и крыша остаются твёрдыми",
		_shot(Vector3(1.857, 8.60, -3), Vector3.BACK, 6.0) == _concrete
		and _shot(Vector3(0, 7.47, -3), Vector3.BACK, 6.0) == _concrete
		and _shot(Vector3(0.2, 11.0, 0), Vector3.DOWN, 3.0) == _concrete)


func _tap_door() -> void:
	await get_tree().process_frame
	Input.action_press("interact")
	await get_tree().process_frame
	Input.action_release("interact")
	await _frames(66)


func _shot(from: Vector3, dir: Vector3, distance: float) -> Object:
	# На стенде нужны настоящие Hitscan-лучи без долгоживущих следов и частиц.
	var tree := get_tree()
	var scene := tree.current_scene
	tree.current_scene = null
	var hit := Hitscan.fire(get_world_3d(), from, dir, 0.0, distance,
		Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR, 0.0, [_player.get_rid()], _rng)
	tree.current_scene = scene
	return hit.get("collider")


func _mesh_count(node: Node) -> int:
	var count := 1 if node is MeshInstance3D else 0
	for child in node.get_children():
		count += _mesh_count(child)
	return count


func _pbr_ready(node: Node) -> bool:
	if node is MeshInstance3D:
		var model := node as MeshInstance3D
		var mat := model.get_active_material(0) as BaseMaterial3D
		if not mat or not mat.albedo_texture or not mat.normal_texture:
			return false
		if mat is ORMMaterial3D:
			return (mat as ORMMaterial3D).orm_texture != null
		return mat.get("roughness_texture") != null
	for child in node.get_children():
		if not _pbr_ready(child):
			return false
	return true


func _check(label: String, success: bool, value := "") -> void:
	if not success:
		_fails += 1
	print("[%s] %s %s" % ["OK" if success else "FAIL", label, value])


func _frames(count: int) -> void:
	for i in range(count):
		await get_tree().physics_frame


func _shots() -> void:
	var camera := Camera3D.new()
	add_child(camera)
	camera.current = true
	await _frames(12)
	var dest := OS.get_environment("CORDON_TOWER_SHOTS")
	if dest.is_empty():
		dest = ProjectSettings.globalize_path("res://_asset_src/cordon_tower/game_review")
	DirAccess.make_dir_recursive_absolute(dest)
	camera.fov = 47
	await _shot_image(camera, Vector3(-11, 3.1, -16), Vector3(0, 4.85, 0), dest, "tower_game")
	_door.toggle(Vector3(0, 0, -3))
	await _frames(72)
	camera.fov = 69
	await _shot_image(camera, Vector3(-0.16, 1.35, -2.95), Vector3(-0.35, 1.80, -0.56), dest, "door_game")
	camera.fov = 63
	await _shot_image(camera, Vector3(1.1, 8.94, 1.25), Vector3(-0.53, 7.19, -0.88), dest, "deck_game")
	get_tree().quit()


func _shot_image(camera: Camera3D, at: Vector3, target: Vector3, path: String, name: String) -> void:
	camera.look_at_from_position(at, target)
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(path.path_join(name + ".png"))
