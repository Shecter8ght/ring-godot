class_name TossedItem
extends RigidBody3D
## Вещь, вылетевшая из рук настоящим телом: старый магазин быстрой перезарядки. Летит, падает, отскакивает
## и успокаивается физикой; считает её хост (в одиночной игре и в убежище — сам игрок), гостям положение
## приходит синхронизатором, у них тело только рисуется. Успокоилось (или вышло время Balance.MAG_TOSS.timeout) —
## сигнал rested: хозяин (Raid, HideoutLevel) кладёт на это место обычную лежащую вещь, тело исчезает.
## Числа — Balance.MAG_TOSS. Слой физики — debris: игроков и ботов не толкает, пули его не видят.

## pose — где и как тело лежит (мир); ok — место годится (под ним поверхность, не улетело за карту).
signal rested(pose: Transform3D, ok: bool)

## Запись предмета целиком (патроны в магазине и прочее) — её и положат на землю.
var entry: Dictionary = {}
## Чей это магазин: его руки перестают рисовать свой, когда тело появилось (Player.mag_body_seen).
var owner_peer: int = 0
## Звук удара о поверхность (действие mag_drop ствола); пусто — тишина.
var sound: String = ""
## Точка вылета — от неё меряется «улетело за карту» и ищется запасное место.
var start: Vector3 = Vector3.ZERO
## Сколько раз прозвучал удар (для проверок).
var hit_count: int = 0
var _simulate: bool = true
var _net: bool = false
var _velocity: Vector3 = Vector3.ZERO
var _spin: Vector3 = Vector3.ZERO
var _age: float = 0.0
var _calm: float = 0.0
var _hit_cd: float = 0.0
var _hits: int = 0
var _speed_before: float = 0.0
var _done: bool = false
## Где центр тела был тик назад и самая тонкая сторона габарита — для своей проверки «не прошло ли сквозь пол».
var _prev: Vector3 = Vector3.INF
var _thin: float = 0.02


## data — {name, pos, rot (Quaternion), vel, spin, entry, sound, peer}. simulate — этот peer считает физику
## (хост); net — узел есть у всех peer рейда (в убежище вещь местная: ни синхронизатора, ни RPC).
static func create(data: Dictionary, simulate: bool, net: bool) -> TossedItem:
	var cfg: Dictionary = Balance.MAG_TOSS
	var body := TossedItem.new()
	body.name = String(data.get("name", "Toss"))
	body.entry = (data.get("entry", {}) as Dictionary).duplicate(true)
	body.owner_peer = int(data.get("peer", 0))
	body.sound = String(data.get("sound", ""))
	body.start = data.get("pos", Vector3.ZERO)
	body._simulate = simulate
	body._net = net
	body._velocity = data.get("vel", Vector3.ZERO)
	body._spin = data.get("spin", Vector3.ZERO)
	body.position = body.start
	body.quaternion = (data.get("rot", Quaternion.IDENTITY) as Quaternion).normalized()
	body.mass = float(cfg.mass)
	body.collision_layer = Hitscan.LAYER_DEBRIS
	body.collision_mask = Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_GLASS
	body.continuous_cd = true
	body.can_sleep = false
	var material := PhysicsMaterial.new()
	material.bounce = float(cfg.bounce)
	material.friction = float(cfg.friction)
	body.physics_material_override = material
	body.linear_damp = float(cfg.linear_damp)
	body.angular_damp = float(cfg.angular_damp)
	var id: String = String(body.entry.get("id", ""))
	var model: Node3D = centered_model(id)
	model.name = "Model"
	body.add_child(model)
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = ItemModels.bounds(model).size.max(Vector3.ONE * 0.02)
	shape.shape = box
	body.add_child(shape)
	body._thin = minf(box.size.x, minf(box.size.y, box.size.z))
	body._prev = body.start
	return body


## Модель вещи с началом координат в центре её габарита: так стоит и тело, и лежащая после него вещь
## (LooseLoot.pose_item) — подмена тела на вещь не видна. Магазин — тот, что в оружии.
static func centered_model(id: String) -> Node3D:
	var holder := Node3D.new()
	var model: Node3D = ItemModels.weapon_magazine(id) if not WeaponDb.magazine(id).is_empty() else null
	if model == null:
		model = ItemModels.build(id)
	holder.add_child(model)
	model.position -= ItemModels.bounds(holder).get_center()
	for node: Node in holder.find_children("*", "GeometryInstance3D", true, false):
		(node as GeometryInstance3D).visibility_range_end = float(Balance.LOOSE_LOOT.distance)
	return holder


## Хост проверяет просьбу о вылете: точка — не дальше reach от глаз стрелка и не за стеной от них (иначе
## отодвигается к стрелку), скорость и вращение — не больше пределов. launch — {pos, rot, vel, spin, sound}.
static func checked_launch(pl: Player, launch: Dictionary) -> Dictionary:
	var cfg: Dictionary = Balance.MAG_TOSS
	var eye: Vector3 = pl.eye_position()
	var pos: Vector3 = launch.get("pos", eye) if launch.get("pos") is Vector3 else eye
	if not pos.is_finite() or pos.distance_to(eye) > float(cfg.reach):
		pos = eye + Vector3.DOWN * 0.25
	var query := PhysicsRayQueryParameters3D.create(eye, pos, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR)
	var hit: Dictionary = pl.get_world_3d().direct_space_state.intersect_ray(query)
	if not hit.is_empty():
		var back: Vector3 = (eye - pos).normalized()
		pos = (hit.position as Vector3) + back * minf(float(cfg.wall_gap), eye.distance_to(hit.position))
	var vel: Vector3 = launch.get("vel", Vector3.ZERO) if launch.get("vel") is Vector3 else Vector3.ZERO
	var spin: Vector3 = launch.get("spin", Vector3.ZERO) if launch.get("spin") is Vector3 else Vector3.ZERO
	var rot: Quaternion = launch.get("rot", Quaternion.IDENTITY) if launch.get("rot") is Quaternion else Quaternion.IDENTITY
	return {"pos": pos, "rot": rot.normalized() if rot.is_finite() and rot.length_squared() > 0.0001 else Quaternion.IDENTITY,
		"vel": vel.limit_length(float(cfg.max_speed)) if vel.is_finite() else Vector3.ZERO,
		"spin": spin.limit_length(float(cfg.max_spin)) if spin.is_finite() else Vector3.ZERO,
		"sound": String(launch.get("sound", ""))}


## Поверхность под точкой (ищется на depth м вниз); пусто — нет.
static func floor_under(world: World3D, point: Vector3, depth: float) -> Dictionary:
	var query := PhysicsRayQueryParameters3D.create(point + Vector3.UP * 0.05, point + Vector3.DOWN * depth, Hitscan.LAYER_WORLD)
	return world.direct_space_state.intersect_ray(query)


func _ready() -> void:
	add_to_group("tossed_items")
	if _net and Net.is_networked():
		var sync := MultiplayerSynchronizer.new()
		sync.name = "Sync"
		var config := SceneReplicationConfig.new()
		for prop: String in [".:position", ".:quaternion"]:
			var path := NodePath(prop)
			config.add_property(path)
			config.property_set_replication_mode(path, SceneReplicationConfig.REPLICATION_MODE_ALWAYS)
		sync.replication_config = config
		sync.set_multiplayer_authority(get_multiplayer_authority())
		Net.scope_sync(self, sync)
		add_child(sync)
	if _simulate:
		linear_velocity = _velocity
		angular_velocity = _spin
		contact_monitor = true
		max_contacts_reported = 2
		body_entered.connect(_on_hit)
	else:
		# у гостя тело только рисуется: положение ведёт хост
		freeze_mode = RigidBody3D.FREEZE_MODE_KINEMATIC
		freeze = true
	for node: Node in get_tree().get_nodes_in_group("all_players"):
		var pl := node as Player
		if pl != null and pl.peer_id == owner_peer and pl.is_local():
			pl.mag_body_seen = true


func _physics_process(delta: float) -> void:
	if not _simulate or _done:
		return
	var cfg: Dictionary = Balance.MAG_TOSS
	_age += delta
	_hit_cd -= delta
	_speed_before = linear_velocity.length()
	var still: bool = _speed_before < float(cfg.rest_speed) and angular_velocity.length() < float(cfg.rest_spin)
	_calm = _calm + delta if still else 0.0
	var lost: bool = not global_position.is_finite() or global_position.distance_to(start) > float(cfg.max_range) \
			or global_position.y < start.y - float(cfg.max_fall)
	if _calm >= float(cfg.rest_sec) or _age >= float(cfg.timeout) or lost:
		_finish(lost)


## Тонкий магазин на скорости проходит сквозь землю и перекрытия: за тик пролетает больше своей толщины, и
## движок его не ловит (на склоне карты ТЦ тело проваливалось). Поэтому каждый тик — луч от прошлого места центра
## к нынешнему: пересёк поверхность — тело возвращается на неё и отскакивает.
func _integrate_forces(state: PhysicsDirectBodyState3D) -> void:
	if not _simulate or _done:
		return
	var now: Vector3 = state.transform.origin
	if _prev.is_finite() and now.is_finite() and _prev.distance_squared_to(now) > 0.000001:
		var query := PhysicsRayQueryParameters3D.create(_prev, now, collision_mask, [get_rid()])
		var hit: Dictionary = state.get_space_state().intersect_ray(query)
		if not hit.is_empty():
			var normal: Vector3 = hit.normal
			now = (hit.position as Vector3) + normal * (_thin * 0.5 + 0.004)
			state.transform = Transform3D(state.transform.basis, now)
			var into: float = state.linear_velocity.dot(normal)
			if into < 0.0:
				state.linear_velocity -= normal * into * (1.0 + float(Balance.MAG_TOSS.bounce))
			_speed_before = maxf(_speed_before, -into)
			_on_hit(null)
	_prev = now


func _finish(lost: bool) -> void:
	_done = true
	var pose: Transform3D = global_transform.orthonormalized()
	var ok: bool = not lost and not floor_under(get_world_3d(), pose.origin, float(Balance.MAG_TOSS.floor_probe)).is_empty()
	rested.emit(pose, ok)
	queue_free()


## Удар о поверхность: звук у всех, кто в этой сцене; отскоки — тише.
func _on_hit(_other: Node) -> void:
	var cfg: Dictionary = Balance.MAG_TOSS
	if _hit_cd > 0.0 or _speed_before < float(cfg.hit_speed):
		return
	_hit_cd = float(cfg.hit_gap)
	var db: float = float(cfg.hit_db) + float(cfg.bounce_db) * float(_hits)
	_hits += 1
	if _net:
		Net.broadcast_scene(self, &"_rpc_hit", [db])
	else:
		_rpc_hit(db)


@rpc("authority", "call_remote", "unreliable")
func _rpc_hit(db: float) -> void:
	hit_count += 1
	if sound != "":
		Audio.play(sound, global_position, db)
