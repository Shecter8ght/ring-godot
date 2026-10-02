extends Node3D
## Стенд настоящих столкновений: тело персонажа, колёса, инерция, стены, витрина и прижатие.
## С окном сохраняет общий вид; игровые профили и снаряжение не используются.

const CART_SCENE: PackedScene = preload("res://scenes/props/shopping_cart.tscn")
var _fails: int = 0
var _case: Node3D
var _drivers: Array[Dictionary] = []
var _press: ShoppingCart


func _ready() -> void:
	Engine.max_fps = 120
	_floor()
	await _new_case()
	var cart: ShoppingCart = _cart(Vector3.ZERO)
	await _frames(90)
	_check("тележка стоит на колёсах без дрейфа", Vector2(cart.position.x, cart.position.z).length() < 0.05 and cart.global_basis.y.y > 0.98, str(cart.position))
	var placed: PhysicsBody3D = Props.new(1).build("cart")
	_check("случайные тележки стали физическими", placed is ShoppingCart)
	placed.free()
	var batches: int = PropBatcher.batch(_case, 24.0, 110.0)
	_check("склейка пропсов сохраняет подвижную модель", cart.get_node("Visuals/Handle") != null and batches == 0)
	var walk: float = await _bump(Balance.PLAYER_WALK_SPEED)
	var run: float = await _bump(Balance.PLAYER_SPRINT_SPEED)
	_check("бег передаёт больше импульса, чем шаг", run > walk * 1.3 and walk > 0.3, "шаг %.2f, бег %.2f м/с" % [walk, run])

	await _new_case()
	cart = _cart(Vector3.ZERO)
	await _frames(12)
	cart.apply_central_impulse(Vector3.BACK * cart.mass * 2.8)
	await _frames(60)
	var speed: float = cart.linear_velocity.length()
	var point: Vector3 = cart.position
	await _frames(120)
	_check("накат сохраняется после толчка и постепенно затухает", cart.position.z > point.z + 2.0 and cart.linear_velocity.length() > 0.1 and cart.linear_velocity.length() < speed, "путь %.2f, скорость %.2f" % [cart.position.z, cart.linear_velocity.length()])
	await _frames(600)
	_check("колёса в конце останавливаются", cart.linear_velocity.length() < 0.06, "%.3f м/с" % cart.linear_velocity.length())

	await _new_case()
	cart = _cart(Vector3.ZERO)
	var actor: CharacterBody3D = _actor(Vector3(-1.2, 0.0, 0.3), Vector3.RIGHT * 3.0)
	await _frames(50)
	_check("удар мимо центра разворачивает тележку", absf(cart.rotation.y) > 0.08, "поворот %.1f°" % rad_to_deg(cart.rotation.y))

	await _new_case()
	cart = _cart(Vector3.ZERO)
	_box("Wall", Vector3(0.0, 1.0, 3.0), Vector3(6.0, 2.0, 0.3))
	await _frames(12)
	cart.apply_central_impulse(Vector3.BACK * cart.mass * 4.0)
	var bounced: bool = false
	for i: int in range(100):
		await get_tree().physics_frame
		bounced = bounced or cart.linear_velocity.z < -0.05
	_check("стена останавливает и отталкивает тележку", bounced and cart.position.z < 2.7, "z=%.2f" % cart.position.z)

	await _new_case()
	cart = _cart(Vector3.ZERO)
	var other: ShoppingCart = _cart(Vector3(0.0, 0.0, 2.0))
	await _frames(12)
	cart.apply_central_impulse(Vector3.BACK * cart.mass * 3.0)
	await _frames(80)
	_check("две тележки передают друг другу импульс", other.position.z > 2.3, "вторая z=%.2f" % other.position.z)

	await _new_case()
	cart = _cart(Vector3.ZERO)
	var glass: GlassPanes = _glass(2.4)
	await _frames(12)
	cart.apply_central_impulse(Vector3.BACK * cart.mass * 4.0)
	await _frames(100)
	_check("тележка выбивает витрину физическим контактом", bool(glass.panes[0].broken))
	_check("после разрушения проходит в проём", cart.position.z > 3.0, "z=%.2f" % cart.position.z)

	await _new_case()
	cart = _cart(Vector3.ZERO)
	glass = _glass(2.4)
	await _frames(12)
	cart.apply_central_impulse(Vector3.BACK * cart.mass * Balance.PLAYER_SPRINT_SPEED)
	var min_up: float = 1.0
	var max_height: float = 0.0
	for i: int in range(100):
		await get_tree().physics_frame
		min_up = minf(min_up, cart.global_basis.y.y)
		max_height = maxf(max_height, cart.position.y)
	_check("зацеп колёс за раму опрокидывает корпус", min_up < 0.0 and max_height > 0.2, "вертикаль %.2f, подъём %.2f м" % [min_up, max_height])
	var center: Vector3 = cart.global_transform * cart.center_of_mass
	_check("перевёрнутая тележка перелетела через разбитое стекло", bool(glass.panes[0].broken) and center.z > 2.6, "центр z=%.2f" % center.z)
	if DisplayServer.get_name() != "headless":
		await _shot("cart_vault")

	await _new_case()
	cart = _cart(Vector3.ZERO)
	glass = _glass(1.0)
	await _frames(12)
	cart.apply_central_impulse(Vector3.BACK * cart.mass * 0.3)
	await _frames(120)
	_check("медленное касание не выбивает стекло", not bool(glass.panes[0].broken))

	await _new_case()
	cart = _cart(Vector3.ZERO)
	actor = _actor(Vector3(0.0, 0.0, 2.0), Vector3.ZERO)
	await _frames(12)
	cart.apply_central_impulse(Vector3.BACK * cart.mass * 4.0)
	await _frames(65)
	var health: Health = actor.get_node("Health") as Health
	_check("сильный удар отталкивает человека и наносит травму", health.hp < health.max_hp and actor.position.z > 2.05, "HP %.1f, z %.2f" % [health.hp, actor.position.z])
	var hp: float = health.hp
	await _frames(60)
	_check("спокойный контакт не повторяет урон каждый кадр", health.hp >= hp - 0.1)

	await _new_case()
	cart = _cart(Vector3(0.0, 0.0, 0.8))
	actor = _actor(Vector3(0.0, 0.0, 1.75), Vector3.ZERO)
	_box("BehindPerson", Vector3(0.0, 1.0, 2.3), Vector3(6.0, 2.0, 0.3))
	await _frames(12)
	_press = cart
	await _frames(100)
	_press = null
	health = actor.get_node("Health") as Health
	_check("человек между тележкой и стеной получает урон от давления", health.hp < health.max_hp, "HP %.1f" % health.hp)
	_check("прижатие не проталкивает человека через стену", actor.position.z < 2.05, "z=%.2f" % actor.position.z)
	if DisplayServer.get_name() != "headless":
		await _shot()
	print("cart_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _physics_process(delta: float) -> void:
	for driver: Dictionary in _drivers:
		var actor: CharacterBody3D = driver.actor as CharacterBody3D
		var wish: Vector3 = driver.wish
		actor.velocity.x = wish.x
		actor.velocity.z = wish.z
		actor.velocity.y = 0.0 if actor.is_on_floor() else actor.velocity.y - 9.8 * delta
		(actor.get_node("CartContact") as CartContact).move_character(delta)
	if is_instance_valid(_press):
		_press.apply_central_force(Vector3.BACK * 700.0)


func _bump(speed: float) -> float:
	await _new_case()
	var cart: ShoppingCart = _cart(Vector3.ZERO)
	_actor(Vector3(0.0, 0.0, -1.3), Vector3.BACK * speed)
	var maximum: float = 0.0
	for i: int in range(50):
		await get_tree().physics_frame
		maximum = maxf(maximum, Vector2(cart.linear_velocity.x, cart.linear_velocity.z).length())
	_check("тело толкает тележку без действия удара", cart.position.z > 0.2, "скорость %.1f, z %.2f" % [speed, cart.position.z])
	return maximum


func _new_case() -> void:
	_drivers.clear()
	_press = null
	if is_instance_valid(_case):
		_case.queue_free()
		await _frames(3)
	_case = Node3D.new()
	_case.name = "Case"
	add_child(_case)


func _cart(at: Vector3) -> ShoppingCart:
	var cart: ShoppingCart = CART_SCENE.instantiate() as ShoppingCart
	cart.name = "Cart_%d" % _case.get_child_count()
	cart.position = at + Vector3.UP * 0.015
	_case.add_child(cart)
	return cart


func _actor(at: Vector3, wish: Vector3) -> CharacterBody3D:
	var actor: CharacterBody3D = CharacterBody3D.new()
	actor.name = "Person_%d" % _drivers.size()
	actor.collision_layer = Hitscan.LAYER_PLAYER
	actor.collision_mask = Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_GLASS
	actor.position = at + Vector3.UP * 0.02
	var shape: CapsuleShape3D = CapsuleShape3D.new()
	shape.radius = 0.35
	shape.height = 1.8
	var collision: CollisionShape3D = CollisionShape3D.new()
	collision.position.y = 0.9
	collision.shape = shape
	actor.add_child(collision)
	var contact: CartContact = CartContact.new()
	contact.name = "CartContact"
	actor.add_child(contact)
	var health: Health = Health.new()
	health.name = "Health"
	actor.add_child(health)
	var visual: MeshInstance3D = MeshInstance3D.new()
	var mesh: CapsuleMesh = CapsuleMesh.new()
	mesh.radius = shape.radius
	mesh.height = shape.height
	visual.mesh = mesh
	visual.position.y = 0.9
	actor.add_child(visual)
	_case.add_child(actor)
	_drivers.append({"actor": actor, "wish": wish})
	return actor


func _glass(z: float) -> GlassPanes:
	var glass: GlassPanes = GlassPanes.new()
	glass.setup([{"xf": Transform3D(Basis.IDENTITY, Vector3(0.0, 1.6, z)), "size": Vector2(4.0, 3.0), "floor_y": 0.0, "sill": Vector3(4.0, 0.1, 0.12), "broken": false}])
	_case.add_child(glass)
	return glass


func _floor() -> void:
	_box("Floor", Vector3(0.0, -0.15, 0.0), Vector3(100.0, 0.3, 100.0))


func _box(label: String, at: Vector3, size: Vector3) -> StaticBody3D:
	var body: StaticBody3D = StaticBody3D.new()
	body.name = label
	body.position = at
	var collision: CollisionShape3D = CollisionShape3D.new()
	var shape: BoxShape3D = BoxShape3D.new()
	shape.size = size
	collision.shape = shape
	body.add_child(collision)
	var visual: MeshInstance3D = MeshInstance3D.new()
	var mesh: BoxMesh = BoxMesh.new()
	mesh.size = size
	visual.mesh = mesh
	body.add_child(visual)
	if _case == null:
		add_child(body)
	else:
		_case.add_child(body)
	return body


func _frames(count: int) -> void:
	for i: int in range(count):
		await get_tree().physics_frame


func _shot(label: String = "cart_contact") -> void:
	var light: DirectionalLight3D = DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-55.0, -25.0, 0.0)
	add_child(light)
	var camera: Camera3D = Camera3D.new()
	add_child(camera)
	camera.position = Vector3(3.0, 2.2, -2.5)
	camera.look_at(Vector3(0.0, 0.5, 1.5))
	camera.make_current()
	await _frames(10)
	get_viewport().get_texture().get_image().save_png("res://docs/screens/%s.png" % label)


func _check(what: String, ok: bool, info: String = "") -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
