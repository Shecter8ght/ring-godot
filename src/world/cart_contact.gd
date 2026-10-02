class_name CartContact
extends Node
## Контакт тела персонажа с тележкой. Хранит отталкивание отдельно от ввода WASD/пути ИИ.
## Игрок движется у владельца, поэтому хост передаёт ему импульс; здоровье остаётся у хоста.

var travel_velocity: Vector3 = Vector3.ZERO
var shove_velocity: Vector3 = Vector3.ZERO
var _last_position: Vector3
var _character: CharacterBody3D


func _ready() -> void:
	_character = get_parent() as CharacterBody3D
	_last_position = _character.global_position


func _physics_process(delta: float) -> void:
	# У чужого игрока velocity не реплицируется: скорость контакта снимаем с движения тела.
	travel_velocity = (_character.global_position - _last_position) / delta
	var limit: float = (Balance.PLAYER_SPRINT_SPEED + float(Balance.CART.shove_max_mps)) * float(Balance.CART.push_speed_margin)
	travel_velocity = travel_velocity.limit_length(limit)
	_last_position = _character.global_position


## Вызывается вместо move_and_slide: скорость до скольжения нужна для передачи импульса.
func move_character(delta: float) -> void:
	var drive: Vector3 = _character.velocity
	var incoming: Vector3 = drive + shove_velocity
	_character.velocity = incoming
	_character.move_and_slide()
	_character.velocity = drive
	var pushed: Dictionary = {}
	for i: int in range(_character.get_slide_collision_count()):
		var hit: KinematicCollision3D = _character.get_slide_collision(i)
		var normal: Vector3 = hit.get_normal()
		_character.velocity = _character.velocity.slide(normal)
		var cart: ShoppingCart = hit.get_collider() as ShoppingCart
		if cart != null and not pushed.has(cart.get_instance_id()):
			pushed[cart.get_instance_id()] = true
			cart.push_character(_character, incoming, -normal, hit.get_position())
	shove_velocity = shove_velocity.move_toward(Vector3.ZERO, float(Balance.CART.shove_decel) * delta)


## Только хост: движущийся предмет толкнул тело. Стены проверяет move_and_slide владельца.
func receive_impulse(impulse: Vector3) -> void:
	if Net.is_networked() and not multiplayer.is_server():
		return
	var owner_peer: int = _character.get_multiplayer_authority()
	if Net.is_networked() and owner_peer != multiplayer.get_unique_id():
		_rpc_impulse.rpc_id(owner_peer, impulse)
	else:
		_apply_impulse(impulse)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_impulse(impulse: Vector3) -> void:
	if multiplayer.get_remote_sender_id() == 1 and _character.is_multiplayer_authority():
		_apply_impulse(impulse)


func _apply_impulse(impulse: Vector3) -> void:
	var mass_kg: float = float(Balance.CART.person_kg)
	if _character.has_method("carried_kg"):
		mass_kg += float(_character.call("carried_kg"))
	shove_velocity = (shove_velocity + impulse / mass_kg).limit_length(float(Balance.CART.shove_max_mps))
