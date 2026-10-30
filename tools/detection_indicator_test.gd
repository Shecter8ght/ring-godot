extends "res://tools/hurt_direction_test.gd"
## Общий стенд Player/Health/CameraRig; здесь проверяется реальное зрение Marauder и подсказка.
## --headless res://tools/detection_indicator_test.tscn; -- host/client — два ENet-процесса, 17797.
## -- shots с окном — обнаружение и попадание одновременно, светлый/тёмный фон, ПНВ.

const DetectionView = preload("res://src/ui/detection_indicator.gd")
var _view: DetectionView


func _solo() -> void:
	_view = _rig._detection
	_view.set_process(false)
	var player: Player = _players[1] as Player
	var enemy: Marauder = (load("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	enemy.archetype = "gunner"
	enemy.position = player.position + Vector3.BACK * 10.0
	add_child(enemy)
	enemy.set_physics_process(false)
	enemy.set_process(false)
	enemy._facing = PI
	await _physics_settle()
	enemy._perceive(0.01)
	_check("мелькнул в поле зрения — подсказки ещё нет", _view._contacts.is_empty())
	enemy._perceive(3.0)
	_view._process(0.0)
	_check("настоящее обнаружение показывает глаз и надпись", enemy._seen_now and _view._screen.visible and _view._contacts.size() == 1)
	_check("источник сзади — стрелка снизу", _view.direction_on_screen(_view._contacts[enemy.get_instance_id()].direction).is_equal_approx(Vector2.DOWN))
	_check("обнаружение не наносит урон", is_equal_approx(player.health.hp, player.health.max_hp))
	_view._process(0.2)
	enemy._perceive(0.01)
	_check("каждый тик не пересылает обнаружение заново", is_equal_approx(float(_view._contacts[enemy.get_instance_id()].age), 0.2))
	enemy._perceive(float(Balance.DETECTION_INDICATOR.refresh_sec))
	_check("длительное наблюдение обновляет одну запись", _view._contacts.size() == 1 and is_zero_approx(float(_view._contacts[enemy.get_instance_id()].age)))
	var wall: StaticBody3D = StaticBody3D.new()
	var collision: CollisionShape3D = CollisionShape3D.new()
	var shape: BoxShape3D = BoxShape3D.new()
	shape.size = Vector3(4.0, 4.0, 0.5)
	collision.shape = shape
	wall.add_child(collision)
	wall.position = player.position + Vector3(0.0, 1.0, 5.0)
	add_child(wall)
	await _physics_settle()
	_view._process(0.2)
	enemy._perceive(0.5)
	_check("стена обрывает обновление от зрения", not enemy._seen_now and is_equal_approx(float(_view._contacts[enemy.get_instance_id()].age), 0.2))
	_view._process(2.0)
	_check("за укрытием подсказка сама исчезает", _view._contacts.is_empty() and not _view._screen.visible)
	enemy._on_noise(player.position, 100.0, "shot")
	enemy._perceive(0.5)
	_check("память о цели и шум за стеной не дают ложной подсказки", _view._contacts.is_empty())
	wall.queue_free()
	await _physics_settle()
	_reset_enemy(enemy)
	enemy._facing = 0.0
	enemy._perceive(3.0)
	_check("враг спиной не обнаруживает игрока", _view._contacts.is_empty())
	_reset_enemy(enemy)
	enemy.faction = "resident"
	enemy.hostile_to_players = false
	enemy._facing = PI
	enemy._perceive(3.0)
	_check("нейтральный жилец не даёт предупреждение", _view._contacts.is_empty())
	enemy.queue_free()
	await get_tree().process_frame
	var directions: Array[Vector3] = [Vector3.FORWARD, Vector3.RIGHT, Vector3.BACK, Vector3.LEFT]
	var expected: Array[Vector2] = [Vector2.UP, Vector2.RIGHT, Vector2.DOWN, Vector2.LEFT]
	for i: int in range(4):
		player.notify_detected(i, player.position + directions[i] * 10.0, player.position)
		_check("сторона наблюдателя %d" % i, _view.direction_on_screen(_view._contacts[i].direction).is_equal_approx(expected[i]))
	_check("несколько направлений одновременно", _view._contacts.size() == 4)
	_view.camera_basis = Basis(Vector3.UP, PI * 0.5)
	_check("поворот взгляда поворачивает указатели", _view.direction_on_screen(Vector3.LEFT).is_equal_approx(Vector2.UP))
	_view.camera_basis = Basis.IDENTITY
	player.notify_detected(0, player.position + Vector3.RIGHT, player.position)
	_check("движение одного врага не плодит записи", _view._contacts.size() == 4 and _view.direction_on_screen(_view._contacts[0].direction).is_equal_approx(Vector2.RIGHT))
	for i: int in range(10):
		player.notify_detected(i, player.position + Vector3.RIGHT, player.position)
	_check("число источников ограничено", _view._contacts.size() == int(Balance.DETECTION_INDICATOR.max_sources))
	_clear_view()
	_view.contact(99, Vector3.INF, player.position)
	_check("неизвестный источник не рисуется", _view._contacts.is_empty())
	player.health.alive = false
	player.notify_detected(99, player.position + Vector3.RIGHT, player.position)
	_check("мёртвому игроку подсказка не приходит", _view._contacts.is_empty())
	player.health.alive = true
	player.notify_detected(99, player.position + Vector3.RIGHT, player.position)
	_view.set_enabled(false)
	_check("выход из игры или смена цели очищает HUD", _view._contacts.is_empty() and not _view._screen.visible)
	_view.set_enabled(true)
	if _shots:
		await _screenshots(player)


func _reset_enemy(enemy: Marauder) -> void:
	enemy.state = Marauder.State.PATROL
	enemy.notice_timer = 0.0
	enemy._seen_now = false
	enemy._detection_t = 0.0
	enemy._target_player = null
	_clear_view()


func _clear_view() -> void:
	_view.set_enabled(false)
	_view.set_enabled(true)


func _physics_settle() -> void:
	await get_tree().physics_frame
	await get_tree().physics_frame
	await get_tree().process_frame


func _network_host() -> void:
	_view = _rig._detection
	_view.set_process(false)
	var guest: Player = _players[_client] as Player
	guest.notify_detected(123, guest.position + Vector3.RIGHT * 10.0, guest.position)
	await get_tree().create_timer(0.3).timeout
	_check("обнаружение гостя не показывается хосту", _view._contacts.is_empty())
	_check_guest.rpc_id(_client)
	_check("гость проверил обнаружение", await _wait(func() -> bool: return _finished, 10.0))
	var host: Player = _players[1] as Player
	host.notify_detected(456, host.position + Vector3.LEFT * 10.0, host.position)
	_check("своё обнаружение хост видит слева", _view._contacts.has(456) and _view.direction_on_screen(_view._contacts[456].direction).is_equal_approx(Vector2.LEFT))
	_check("обнаружение не запускает эффект попадания", _fx._directions.is_empty() and is_zero_approx(_fx._k))
	_finish.rpc_id(_client)
	await get_tree().create_timer(0.3).timeout


@rpc("authority", "call_remote", "reliable")
func _check_guest() -> void:
	_view = _rig._detection
	_view.set_process(false)
	var guest: Player = _players[_client] as Player
	_check("гость получил подтверждённое обнаружение справа", _view._contacts.has(123) and _view.direction_on_screen(_view._contacts[123].direction).is_equal_approx(Vector2.RIGHT))
	_check("здоровье гостя не меняется", is_equal_approx(guest.health.hp, guest.health.max_hp))
	await get_tree().process_frame
	_clear_view()
	guest._rpc_detected(789, guest.position + Vector3.LEFT, guest.position)
	_check("событие без подтверждения хоста отвергнуто", _view._contacts.is_empty())
	guest.notify_detected(789, guest.position + Vector3.LEFT, guest.position)
	_check("гость не может подтвердить обнаружение сам", _view._contacts.is_empty())
	_peer_checked.rpc_id(1)


func _screenshots(player: Player) -> void:
	var background: CanvasLayer = CanvasLayer.new()
	background.layer = -1
	add_child(background)
	var rect: ColorRect = ColorRect.new()
	rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	background.add_child(rect)
	var cases: Dictionary = {"light": Color(0.85, 0.85, 0.85), "dark": Color(0.025, 0.025, 0.025), "nvg_hit": Color(0.3, 0.35, 0.3)}
	for key: String in cases:
		_clear_view()
		rect.color = cases[key]
		_view.contact(1, player.position + Vector3.RIGHT, player.position)
		_view.contact(2, player.position + Vector3.FORWARD, player.position)
		_rig._nvg_fx.visible = key == "nvg_hit"
		_rig._nvg_copy.visible = key == "nvg_hit"
		if key == "nvg_hit":
			_fx.hit(15.0, player.position + Vector3.RIGHT, player.position)
		_fx._process(0.0)
		_view._process(0.0)
		await RenderingServer.frame_post_draw
		var image: Image = get_viewport().get_texture().get_image()
		image.save_png(ProjectSettings.globalize_path("res://tools/_probe/detection_%s.png" % key))
		var center: Vector2 = _view._screen.size * 0.5
		var short_side: float = minf(_view._screen.size.x, _view._screen.size.y)
		_check("указатель остаётся жёлтым: " + key, _has_tint(image, center + Vector2.RIGHT * short_side * float(Balance.DETECTION_INDICATOR.radius), false))
		if key == "nvg_hit":
			_check("попадание в ПНВ остаётся красным", _has_tint(image, center + Vector2.RIGHT * short_side * float(Balance.HURT_DIRECTION.radius), true))


func _has_tint(image: Image, point: Vector2, red: bool) -> bool:
	var scale: Vector2 = Vector2(image.get_width(), image.get_height()) / _view._screen.size
	var pixel: Vector2i = Vector2i(point * scale)
	for y: int in range(pixel.y - 15, pixel.y + 16):
		for x: int in range(pixel.x - 15, pixel.x + 16):
			var color: Color = image.get_pixel(x, y)
			if red and color.r > 0.5 and color.g < color.r * 0.45:
				return true
			if not red and color.r > 0.6 and color.g > 0.4 and color.b < color.r * 0.5:
				return true
	return false
