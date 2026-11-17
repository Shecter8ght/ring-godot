class_name ShoppingCart
extends RigidBody3D
## Тележку двигает физика, а не анимация: колёса катятся, корпус может развернуться и опрокинуться.
## Решает хост. У клиентов тело заморожено, положение приходит с синхронизатора.

var _last_velocity: Vector3 = Vector3.ZERO
var _last_angular: Vector3 = Vector3.ZERO
var _prior_velocity: Vector3 = Vector3.ZERO
var _prior_angular: Vector3 = Vector3.ZERO
var _contacts: Dictionary = {}
var _injury_until: Dictionary = {}
var _push_sent_ms: int = -1000
var _pusher: int = 0
var _pushed_ms: int = -100000
var _sound_ms: int = -1000
var _resume: Array[Dictionary] = []
var _glass_hits: Dictionary = {}
var _net_transform: Transform3D = Transform3D.IDENTITY
var _net_velocity: Vector3 = Vector3.ZERO
var _snapshot: bool = false
var _tipped: bool = false

var net_transform: Transform3D:
	get:
		return global_transform if _simulates() else _net_transform
	set(value):
		_net_transform = value
		if not _snapshot:
			global_transform = value
		_snapshot = true

var net_velocity: Vector3:
	get:
		return linear_velocity if _simulates() else _net_velocity
	set(value):
		_net_velocity = value


func _ready() -> void:
	add_to_group("shopping_carts")
	set_meta("surface", "metal")
	var c: Dictionary = Balance.CART
	mass = float(c.mass_kg)
	center_of_mass_mode = CENTER_OF_MASS_MODE_CUSTOM
	center_of_mass = Vector3(0.0, float(c.center_y), 0.0)
	linear_damp_mode = DAMP_MODE_REPLACE
	angular_damp_mode = DAMP_MODE_REPLACE
	linear_damp = float(c.linear_damp)
	angular_damp = float(c.angular_damp)
	continuous_cd = true
	max_contacts_reported = int(c.contacts)
	contact_monitor = true
	var material: PhysicsMaterial = PhysicsMaterial.new()
	material.friction = float(c.friction)
	material.bounce = float(c.bounce)
	physics_material_override = material
	if Net.is_networked():
		freeze_mode = FREEZE_MODE_KINEMATIC
		freeze = not multiplayer.is_server()
		_setup_sync()


func _simulates() -> bool:
	return not Net.is_networked() or multiplayer.is_server()


func _setup_sync() -> void:
	var sync: MultiplayerSynchronizer = MultiplayerSynchronizer.new()
	sync.name = "Sync"
	sync.replication_interval = float(Balance.CART.net_sec)
	sync.delta_interval = float(Balance.CART.net_sec)
	var config: SceneReplicationConfig = SceneReplicationConfig.new()
	for prop: String in [".:net_transform", ".:net_velocity"]:
		var path: NodePath = NodePath(prop)
		config.add_property(path)
		config.property_set_replication_mode(path, SceneReplicationConfig.REPLICATION_MODE_ON_CHANGE)
	sync.replication_config = config
	sync.set_multiplayer_authority(1)
	Net.scope_sync(self, sync)
	add_child(sync)


func _physics_process(delta: float) -> void:
	if not _simulates() and _snapshot:
		var far: bool = global_position.distance_to(_net_transform.origin) > float(Balance.CART.net_snap_m)
		global_transform = _net_transform if far else global_transform.interpolate_with(_net_transform, 1.0 - exp(-float(Balance.CART.net_smooth) * delta))
	var tipped: bool = global_basis.y.dot(Vector3.UP) < float(Balance.CART.upright_dot)
	if tipped != _tipped:
		_tipped = tipped
		physics_material_override.friction = float(Balance.CART.tipped_friction if tipped else Balance.CART.friction)


## Контакт после move_and_slide. Относительная скорость, приведённая масса и плечо удара.
func push_character(character: CharacterBody3D, velocity: Vector3, direction: Vector3, at: Vector3) -> void:
	if not velocity.is_finite() or not direction.is_finite() or not at.is_finite():
		return
	if not _simulates():
		if Time.get_ticks_msec() - _push_sent_ms >= int(float(Balance.CART.push_net_sec) * 1000.0):
			_push_sent_ms = Time.get_ticks_msec()
			_rpc_push.rpc_id(1, character.get_path(), velocity, direction, at)
		return
	var health: Health = character.get_node_or_null("Health") as Health
	if health != null and not health.alive:
		return
	if character.global_position.distance_to(global_position) > float(Balance.CART.push_reach_m):
		return
	direction.y = 0.0
	direction = direction.normalized()
	var arm: Vector3 = at - (global_transform * center_of_mass)
	var relative: Vector3 = velocity - linear_velocity - angular_velocity.cross(arm)
	var closing: float = relative.dot(direction)
	if closing < float(Balance.CART.push_min_speed):
		return
	var person_mass: float = float(Balance.CART.person_kg)
	if character.has_method("carried_kg"):
		person_mass += float(character.call("carried_kg"))
	# Часть импульса уходит во вращение: верх корзины и удар сбоку не разгоняют всё тело как центр.
	var lever: Vector3 = arm.cross(direction)
	var inverse_mass: float = 1.0 / mass + 1.0 / person_mass + lever.dot(get_inverse_inertia_tensor() * lever)
	var reduced_mass: float = 1.0 / inverse_mass
	var impulse: Vector3 = direction * closing * reduced_mass * (1.0 + float(Balance.CART.push_restitution))
	sleeping = false
	apply_impulse(impulse, at - global_position)
	_pusher = character.get_multiplayer_authority() if character is Player else 0
	_pushed_ms = Time.get_ticks_msec()


@rpc("any_peer", "call_remote", "unreliable_ordered")
func _rpc_push(path: NodePath, velocity: Vector3, direction: Vector3, at: Vector3) -> void:
	if not multiplayer.is_server() or not velocity.is_finite() or not direction.is_finite() or not at.is_finite():
		return
	var character: Player = get_node_or_null(path) as Player
	if character == null or character.get_multiplayer_authority() != multiplayer.get_remote_sender_id():
		return
	if Net.scene_of(character) != Net.scene_of(self):
		return
	if at.distance_to(global_position + Vector3.UP * float(Balance.CART.center_y)) > float(Balance.CART.push_reach_m):
		return
	var towards: Vector3 = global_position - character.global_position
	towards.y = 0.0
	if direction.dot(towards.normalized()) <= 0.0:
		return
	velocity = velocity.limit_length((Balance.PLAYER_SPRINT_SPEED + float(Balance.CART.shove_max_mps)) * float(Balance.CART.push_speed_margin))
	push_character(character, velocity, direction, at)


func _integrate_forces(state: PhysicsDirectBodyState3D) -> void:
	if not _simulates():
		return
	_resume_after_glass(state)
	_glass_hits.clear()
	var current: Dictionary = {}
	var people: Dictionary = {}
	var grounded: bool = false
	for i: int in range(state.get_contact_count()):
		var body: CollisionObject3D = state.get_contact_collider_object(i) as CollisionObject3D
		if body == null:
			continue
		var normal: Vector3 = state.get_contact_local_normal(i)
		var at: Vector3 = state.get_contact_local_position(i)
		grounded = grounded or normal.y > float(Balance.CART.wheel_ground_dot)
		var shape: int = state.get_contact_collider_shape(i)
		var key: String = "%d:%d" % [body.get_instance_id(), shape]
		var fresh: bool = not _contacts.has(key) and not current.has(key)
		current[key] = true
		var arm: Vector3 = at - (state.transform * center_of_mass)
		var incoming: Vector3 = _last_velocity + _last_angular.cross(arm)
		# CCD уменьшает скорость за кадр до появления контакта в списке. Сохраняем скорость подхода.
		var approach: Vector3 = _prior_velocity + _prior_angular.cross(arm)
		if body.get_parent() is GlassPanes:
			if fresh:
				_hit_glass(state, body, shape, state.get_contact_local_shape(i), at, incoming, approach)
		elif body is CharacterBody3D:
			var actor: CharacterBody3D = body as CharacterBody3D
			var dir: Vector3 = actor.global_position - global_position
			dir.y = 0.0
			dir = dir.normalized()
			var contact: CartContact = actor.get_node_or_null("CartContact") as CartContact
			var actor_velocity: Vector3 = contact.travel_velocity if contact != null else actor.velocity
			var speed: float = maxf(0.0, maxf((incoming - actor_velocity).dot(dir), (approach - actor_velocity).dot(dir)))
			var force: float = absf(state.get_contact_impulse(i).dot(dir)) / state.step
			var id: int = actor.get_instance_id()
			if not people.has(id):
				people[id] = {"body": actor, "dir": dir, "at": at, "speed": 0.0, "force": 0.0, "fresh": false}
			var p: Dictionary = people[id]
			p.speed = maxf(float(p.speed), speed)
			p.force = float(p.force) + force
			p.fresh = bool(p.fresh) or fresh
		elif fresh:
			var speed: float = maxf(0.0, -incoming.dot(normal))
			if speed >= float(Balance.CART.sound_min_speed):
				_impact_sound.call_deferred(at)
	for id: int in people:
		var p: Dictionary = people[id]
		_hit_person.call_deferred(p.body, p.dir, p.at, float(p.speed), float(p.force), bool(p.fresh), state.step)
	_contacts = current
	var rolling: Vector3 = Vector3(state.linear_velocity.x, 0.0, state.linear_velocity.z)
	# стоящую тележку не толкать: любой импульс будит тело, и она никогда не засыпает
	if grounded and not _tipped and rolling.length() > float(Balance.CART.rest_mps):
		# Сопротивление качению почти постоянно; без контакта с полом остаются гравитация и воздух.
		var loss: float = minf(rolling.length(), float(Balance.CART.rolling_decel) * state.step)
		state.apply_central_impulse(-rolling.normalized() * loss * mass)
	_prior_velocity = _last_velocity
	_prior_angular = _last_angular
	_last_velocity = state.linear_velocity
	_last_angular = state.angular_velocity


func _hit_glass(state: PhysicsDirectBodyState3D, body: CollisionObject3D, shape: int, local_shape: int, at: Vector3, incoming: Vector3, approach: Vector3) -> void:
	var pane: Array = GlassPanes.pane_of({"collider": body, "shape": shape})
	if pane.is_empty():
		# Передние колёса встречают нижнюю раму чуть раньше корзины; удар нагружает ту же панель.
		# Отдельная метка сохраняет металлической раме обычную непробиваемую коллизию для пуль.
		var owner_node: Object = body.shape_owner_get_owner(body.shape_find_owner(shape))
		if owner_node == null or not owner_node.has_meta("sill_pane"):
			return
		pane = [body.get_parent(), int(owner_node.get_meta("sill_pane"))]
	var glass: GlassPanes = pane[0] as GlassPanes
	var idx: int = int(pane[1])
	var p: Dictionary = glass.panes[idx]
	if bool(p.broken):
		return
	var key: String = "%d:%d" % [glass.get_instance_id(), idx]
	if _glass_hits.has(key):
		return
	_glass_hits[key] = true
	var normal: Vector3 = glass.pane_world_transform(idx).basis.z.normalized()
	if absf(approach.dot(normal)) > absf(incoming.dot(normal)):
		incoming = approach
	var speed: float = absf(incoming.dot(normal))
	var energy: float = 0.5 * mass * speed * speed
	glass.impact.call_deferred(idx, energy, at)
	var required: float = float(Balance.CART.glass_break_j) * float(p.hp) / GlassPanes.HP
	if energy >= required:
		# После осыпания продолжаем движение, вычтя энергию разрушения, а не застреваем в проёме.
		var across: Vector3 = normal * incoming.dot(normal)
		var velocity: Vector3 = incoming - across + across * sqrt(maxf(0.0, 1.0 - required / energy))
		var angular: Vector3 = state.angular_velocity
		var own_shape: CollisionShape3D = shape_owner_get_owner(shape_find_owner(local_shape)) as CollisionShape3D
		if own_shape != null and String(own_shape.name).begins_with("Wheel") and body.name == "Sills" \
				and speed >= float(Balance.CART.wheel_vault_min_mps) and not _tipped:
			var wheel: SphereShape3D = own_shape.shape as SphereShape3D
			if wheel != null and (p.sill as Vector3).y >= wheel.radius:
				# Колесо зацепилось за раму: момент импульса относительно контакта поднимает корпус.
				# Скорость и вращение получаем из того же запаса энергии, без постановочного кувырка.
				# Рама встречает пару колёс: ось опоры проходит вдоль рамы, а не через один её угол.
				var axis: Vector3 = Vector3.UP.cross(across).normalized()
				var center: Vector3 = state.transform * center_of_mass
				var pivot: Vector3 = at + axis * (center - at).dot(axis)
				var arm: Vector3 = pivot - center
				var lever: Vector3 = arm.cross(normal)
				var inverse_mass: float = 1.0 / mass + lever.dot(state.inverse_inertia_tensor * lever)
				var impulse: Vector3 = -normal * velocity.dot(normal) * (1.0 + float(Balance.CART.bounce)) / inverse_mass
				velocity += impulse / mass
				# Ось рамы ограничивает колесо по нормали, затем разбитый проём освобождает тело.
				angular = state.inverse_inertia_tensor * arm.cross(impulse)
				velocity.y = maxf(velocity.y, state.linear_velocity.y)
				var used: float = 0.5 * mass * velocity.length_squared() + 0.5 * angular.dot(state.inverse_inertia_tensor.inverse() * angular)
				var budget: float = maxf(0.0, 0.5 * mass * incoming.length_squared() - required)
				var scale_k: float = sqrt(minf(1.0, budget / maxf(used, 0.000001)))
				velocity *= scale_k
				angular *= scale_k
		_resume.append({"glass": glass, "idx": idx, "velocity": velocity, "angular": angular})


func _resume_after_glass(state: PhysicsDirectBodyState3D) -> void:
	for r: Dictionary in _resume:
		var glass: GlassPanes = r.glass as GlassPanes
		if is_instance_valid(glass) and bool(glass.panes[int(r.idx)].broken):
			var velocity: Vector3 = r.velocity
			state.apply_central_impulse((velocity - state.linear_velocity) * mass)
			var angular: Vector3 = r.angular
			state.apply_torque_impulse(state.inverse_inertia_tensor.inverse() * (angular - state.angular_velocity))
	_resume.clear()


func _hit_person(actor: CharacterBody3D, dir: Vector3, at: Vector3, speed: float, force: float, fresh: bool, delta: float) -> void:
	if not is_instance_valid(actor):
		return
	var health: Health = actor.get_node_or_null("Health") as Health
	if health == null or not health.alive:
		return
	var id: int = actor.get_instance_id()
	var contact: CartContact = actor.get_node_or_null("CartContact") as CartContact
	var energy: float = 0.5 * mass * speed * speed
	if fresh and speed >= float(Balance.CART.sound_min_speed) and contact != null:
		contact.receive_impulse(dir * mass * speed)
	if fresh and energy > float(Balance.CART.injury_min_j) and Time.get_ticks_msec() >= int(_injury_until.get(id, 0)):
		_injury_until[id] = Time.get_ticks_msec() + int(float(Balance.CART.injury_cooldown_sec) * 1000.0)
		var damage: float = minf(float(Balance.CART.injury_max_hp), (energy - float(Balance.CART.injury_min_j)) * float(Balance.CART.injury_hp_per_j))
		_damage_person(health, damage, at)
	if force > float(Balance.CART.crush_min_n) and _pinned(actor, dir):
		_damage_person(health, (force - float(Balance.CART.crush_min_n)) * float(Balance.CART.crush_hp_per_ns) * delta, at)


func _pinned(actor: CharacterBody3D, dir: Vector3) -> bool:
	var query: PhysicsTestMotionParameters3D = PhysicsTestMotionParameters3D.new()
	query.from = actor.global_transform
	query.motion = dir * float(Balance.CART.crush_probe_m)
	query.exclude_bodies = [get_rid()]
	var result: PhysicsTestMotionResult3D = PhysicsTestMotionResult3D.new()
	if not PhysicsServer3D.body_test_motion(actor.get_rid(), query, result):
		return false
	for i: int in range(result.get_collision_count()):
		var body: CollisionObject3D = result.get_collider(i) as CollisionObject3D
		if body != null and not (body is CharacterBody3D or body is ShoppingCart) and result.get_collision_normal(i).dot(dir) < 0.0:
			return true
	return false


func _damage_person(health: Health, damage: float, at: Vector3) -> void:
	var by: int = _pusher if Time.get_ticks_msec() - _pushed_ms < int(float(Balance.CART.attribution_sec) * 1000.0) else 0
	health.last_attacker = by
	health.take_damage(damage, global_position, "impact", at, {"src": {"kind": "collision", "by": by}})


func _impact_sound(at: Vector3) -> void:
	if Time.get_ticks_msec() - _sound_ms < int(float(Balance.CART.sound_cooldown_sec) * 1000.0):
		return
	_sound_ms = Time.get_ticks_msec()
	NoiseBus.emit(at, float(Balance.CART.noise_m), "impact")
	if Net.is_networked():
		for peer: int in multiplayer.get_peers():
			if Net.visible_in(peer, Net.scene_of(self)):
				_rpc_sound.rpc_id(peer, at)
	_rpc_sound(at)


@rpc("authority", "call_remote", "unreliable")
func _rpc_sound(at: Vector3) -> void:
	Audio.play("impact_metal", at)
