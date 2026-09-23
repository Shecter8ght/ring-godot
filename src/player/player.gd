class_name Player
extends CharacterBody3D
## Игрок: движение по стойкам относительно камеры, корпус смотрит на курсор.
## В прицеле (ПКМ, см. CameraRig) — вид от первого лица: взгляд ведёт мышь, WASD — относительно
## взгляда, выстрел — из глаз по оси взгляда. Оружие: 1–4 пистолет/автомат/дробовик/винтовка,
## G — граната. Смерть — регдолл.
## Сеть: узлом владеет тот peer, чей id записан в `peer_id`; чужих игроков двигает синхронизация.

enum Stance { STAND, CROUCH, PRONE }

@export var peer_id: int = 1

var stance: Stance = Stance.STAND
var aiming: bool = false
## Прицел от первого лица включён — ставит CameraRig.
var ads: bool = false
## Направление взгляда в прицеле, рад (курс от +Z, тангаж вверх) — ставит CameraRig.
var look_yaw: float = 0.0
var look_pitch: float = 0.0
## Точка на земле под курсором — ставит камера/уровень; корпус поворачивается к ней.
var cursor_ground: Vector3 = Vector3.ZERO
## Точка на теле противника под курсором (Vector3.ZERO — под курсором никого): выстрел идёт в неё.
var cursor_body: Vector3 = Vector3.ZERO

## Оружие в руках и патроны: ammo — в текущем магазине, остальные — в ammo_by.
var weapon_id: String = "pistol"
var ammo: int = int(Balance.WEAPONS.pistol.mag)
var ammo_by: Dictionary = {}
var grenades: int = Balance.GRENADES_START
var fire_timer: float = 0.0
var reload_timer: float = 0.0
var _step_timer: float = 0.0
## Текущий подброс ствола от отдачи, рад — гаснет к нулю.
var _recoil: float = 0.0
var _rng := RandomNumberGenerator.new()
var _hand: Node3D
var _weapon_model: Node3D
var _weapon_model_id: String = ""
var _ragdoll: Ragdoll
var _last_hit_from: Vector3 = Vector3.ZERO
var _last_damage: float = 0.0

@onready var _capsule: CollisionShape3D = $Capsule
@onready var _body: Node3D = $Body
@onready var _muzzle: OmniLight3D = $Body/Muzzle
@onready var health: Health = $Health
## Рюкзак: меняет хост, видят все (см. Inventory). Создаётся в _ready.
var inventory: Inventory
@onready var _camera_rig: Node3D = get_tree().get_first_node_in_group("camera_rig")


func _ready() -> void:
	add_to_group("players")
	# "players" — кто сейчас в мире (его видят мародёры); "all_players" — все, включая ушедших
	add_to_group("all_players")
	_rng.randomize()
	health.max_hp = Balance.PLAYER_HP
	health.hp = health.max_hp
	# смерть учитывает рейд (сигнал died приходит только у хоста — он и считает итог)
	health.died.connect(func() -> void:
		if Raid.current:
			Raid.current.mark_dead(peer_id))
	health.damaged.connect(func(amount: float, from: Vector3) -> void:
		_last_hit_from = from
		_last_damage = amount
		if is_local() and _camera_rig is CameraRig:
			(_camera_rig as CameraRig).add_shake(Balance.HURT_SHAKE))
	for id in Balance.WEAPON_ORDER:
		ammo_by[id] = int(Balance.WEAPONS[id].mag)
	_muzzle.visible = false
	# рюкзак — авторитет хоста (узел создан после выдачи авторитета Player — умалчиваемый 1)
	inventory = Inventory.new()
	inventory.name = "Inventory"
	add_child(inventory)
	# рука с оружием — не внутри Body: Body сжимается по стойке, оружие сжиматься не должно
	_hand = Node3D.new()
	_hand.name = "Hand"
	add_child(_hand)
	_apply_stance()
	# Слушаем мир из своей позиции, а не из камеры в 28 м над головой.
	if is_local():
		var listener := AudioListener3D.new()
		add_child(listener)
		listener.position = Vector3(0, 1.5, 0)
		listener.make_current()
	if Net.is_networked():
		_setup_sync()


## Позицию и позу владелец шлёт всем остальным сам (авторитет = peer_id, см. sector_level.gd —
## отзывчивое движение важнее для игрока, чем для мародёра/двери). Health синхронизируется
## отдельно, со своим (хостовым) авторитетом — урон всегда считает хост.
func _setup_sync() -> void:
	var sync := MultiplayerSynchronizer.new()
	# постоянное имя: синхронизатор адресуется по пути, а автоимя (@MultiplayerSynchronizer@N)
	# у каждого peer своё — пакеты хоста не находили узел у клиента
	sync.name = "Sync"
	var config := SceneReplicationConfig.new()
	for prop in [".:global_position", "Body:rotation", ".:stance", ".:aiming", ".:weapon_id"]:
		var path := NodePath(prop)
		config.add_property(path)
		config.property_set_replication_mode(path, SceneReplicationConfig.REPLICATION_MODE_ON_CHANGE)
	sync.replication_config = config
	# У свежего узла своё умалчиваемое authority (1) — не наследуется от родителя автоматически.
	# Ставить его нужно ДО add_child: иначе спавнер путает pending-спавн с уже вошедшим в дерево узлом.
	sync.set_multiplayer_authority(get_multiplayer_authority())
	add_child(sync)


func is_alive() -> bool:
	return health.alive


func is_local() -> bool:
	return peer_id == multiplayer.get_unique_id()


func body_yaw() -> float:
	return _body.rotation.y


func recoil() -> float:
	return _recoil


func eye_position() -> Vector3:
	return global_position + Vector3.UP * float(Balance.ADS_EYE[_stance_key()])


## Направление взгляда в прицеле.
func look_dir() -> Vector3:
	return Vector3(sin(look_yaw) * cos(look_pitch), sin(look_pitch), cos(look_yaw) * cos(look_pitch))


## Вид от первого лица: своё тело и оружие в руках не рисуем (камера внутри капсулы),
## но тень оставляем — на полу видно, где стоишь.
func set_first_person(on: bool) -> void:
	var mode := GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY if on else GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	for mi in _body.find_children("*", "MeshInstance3D", true, false):
		(mi as MeshInstance3D).cast_shadow = mode
	if _weapon_model:
		for mi in _weapon_model.find_children("*", "MeshInstance3D", true, false):
			(mi as MeshInstance3D).cast_shadow = mode


func _process(_delta: float) -> void:
	# эвакуирован (решает хост, видят все) — уходит из мира
	if Raid.current and Raid.current.is_extracted(peer_id) and is_in_group("players"):
		_leave_raid()
		return
	_update_hand()
	# смерть видна у всех peer: у хоста — по сигналу, у клиентов — по синхронизированному alive
	if not health.alive and _ragdoll == null:
		_die()


func _physics_process(delta: float) -> void:
	if not is_local() or not is_alive():
		return
	_read_stance()
	_combat(delta)
	var wish := _wish_direction()
	var speed := _stance_speed()
	var target := wish * speed
	var rate := Balance.PLAYER_ACCEL if wish.length() > 0.0 else Balance.PLAYER_DECEL
	velocity.x = move_toward(velocity.x, target.x, rate * delta)
	velocity.z = move_toward(velocity.z, target.z, rate * delta)
	if not is_on_floor():
		velocity.y -= ProjectSettings.get_setting("physics/3d/default_gravity") * delta
	else:
		velocity.y = 0.0
	move_and_slide()
	if ads:
		_body.rotation.y = look_yaw
	else:
		_face_cursor(delta)
	_footsteps(delta)
	_recoil = move_toward(_recoil, 0.0, Balance.RECOIL_RETURN * _recoil * delta + 0.02 * delta)
	_body.rotation.x = -_recoil * 0.4


## Оружие в правой руке у груди, повёрнуто с корпусом; высота — по стойке.
func _update_hand() -> void:
	if _weapon_model_id != weapon_id:
		if _weapon_model:
			_weapon_model.queue_free()
		_weapon_model = WeaponModels.build(weapon_id)
		_hand.add_child(_weapon_model)
		_weapon_model_id = weapon_id
		if ads:
			set_first_person(true)
	var h := float(Balance.STANCE_HEIGHT[_stance_key()]) / float(Balance.STANCE_HEIGHT.stand)
	var yaw := _body.rotation.y
	_hand.visible = health.alive
	_hand.position = Basis(Vector3.UP, yaw) * Vector3(-0.17, 1.24 * h, 0.24)
	_hand.rotation = Vector3(-_recoil, yaw, 0.0)


## Шаги слышны AI: радиус по стойке и бегу, только пока реально движемся.
func _footsteps(delta: float) -> void:
	var moving := Vector2(velocity.x, velocity.z).length() > 0.3
	if not moving:
		_step_timer = 0.0
		return
	_step_timer -= delta
	if _step_timer > 0.0:
		return
	_step_timer = Balance.NOISE_STEP_INTERVAL
	var key := _stance_key()
	if key == "stand" and Input.is_action_pressed("sprint") and not aiming:
		key = "sprint"
	NoiseBus.emit(global_position, float(Balance.NOISE_STEP[key]), "step")
	var step_db: Dictionary = {"stand": 0.0, "sprint": 2.0, "crouch": -8.0, "prone": -14.0}
	Audio.play("step_run" if key == "sprint" else "step", global_position, float(step_db[key]))


## Стрельба, перезарядка на R, смена оружия 1–4, граната G.
func _combat(delta: float) -> void:
	fire_timer -= delta
	# открыт рюкзак/обыск — клики идут в кнопки, не в спуск
	if Raid.current and Raid.current.ui_open():
		return
	for i in range(Balance.WEAPON_ORDER.size()):
		if Input.is_action_just_pressed("weapon_%d" % (i + 1)):
			_switch(String(Balance.WEAPON_ORDER[i]))
	if Input.is_action_just_pressed("grenade") and grenades > 0 and fire_timer <= 0.0:
		_throw_grenade()
	var spec: Dictionary = Balance.WEAPONS[weapon_id]
	if reload_timer > 0.0:
		reload_timer -= delta
		if reload_timer <= 0.0:
			ammo = int(spec.mag)
		return
	if Input.is_action_just_pressed("reload") and ammo < int(spec.mag):
		_start_reload(spec)
		return
	var trigger := Input.is_action_pressed("fire") if bool(spec.auto) else Input.is_action_just_pressed("fire")
	if trigger and fire_timer <= 0.0:
		if ammo <= 0:
			_start_reload(spec)
			return
		_fire(spec)


func _start_reload(spec: Dictionary) -> void:
	reload_timer = float(spec.reload)
	Audio.play(String(spec.reload_sound), global_position)


## Смена оружия: патроны текущего магазина сохраняются, перезарядка прерывается.
func _switch(id: String) -> void:
	if id == weapon_id:
		return
	ammo_by[weapon_id] = ammo
	weapon_id = id
	ammo = int(ammo_by.get(id, int(Balance.WEAPONS[id].mag)))
	reload_timer = 0.0
	fire_timer = 0.35
	Audio.play("bolt", global_position, -6.0)


func _fire(spec: Dictionary) -> void:
	ammo -= 1
	fire_timer = float(spec.interval)
	var from: Vector3
	var dir: Vector3
	if ads:
		from = eye_position()
		dir = look_dir()
	else:
		from = global_position + Vector3.UP * 1.3
		var target := cursor_body if cursor_body != Vector3.ZERO else cursor_ground + Vector3.UP * 1.3
		dir = target - from
		if dir.length_squared() < 0.01:
			dir = Vector3(sin(_body.rotation.y), 0.0, cos(_body.rotation.y))
		dir = dir.normalized()
	var exclude: Array[RID] = [get_rid()]
	var spread: float = float(spec.spread_deg) * (float(Balance.ADS_SPREAD[weapon_id]) if ads else 1.0)
	var mask := Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_MARAUDER | Hitscan.LAYER_DEBRIS
	var muzzle := _muzzle_world()
	var rig := _camera_rig as CameraRig
	var marked := false
	for i in range(int(spec.pellets)):
		var hit := Hitscan.fire(get_world_3d(), from, dir, spread, float(spec.range_m), mask, float(spec.damage), exclude, _rng)
		if i < 3:
			Tracer.spawn(get_tree().current_scene, muzzle, hit.get("position", hit.get("end", from)), Color(1.0, 0.85, 0.5))
		var c: Object = hit.get("collider")
		if rig and not marked:
			if c is Target:
				rig.show_hitmarker(hit.position.y - (c as Target).global_position.y >= (c as Target).head_height - 0.25)
				marked = true
			elif c is Marauder:
				rig.show_hitmarker(not ((c as Marauder).get_node("Health") as Health).alive)
				marked = true
	_recoil += float(spec.kick)
	if rig:
		rig.add_shake(float(spec.shake))
	_muzzle.global_position = muzzle
	_muzzle.visible = true
	get_tree().create_timer(0.05).timeout.connect(func() -> void: _muzzle.visible = false)
	NoiseBus.emit(global_position, float(spec.noise_m), "shot")
	Audio.play(String(spec.sound), muzzle)
	# помпа/затвор — щелчок после выстрела
	if String(spec.cycle_sound) != "":
		get_tree().create_timer(0.35).timeout.connect(func() -> void:
			Audio.play(String(spec.cycle_sound), global_position))


## Дуло: в прицеле — у модели в руках перед камерой, иначе — у модели на теле.
func _muzzle_world() -> Vector3:
	if ads and _camera_rig is CameraRig:
		return (_camera_rig as CameraRig).viewmodel_muzzle()
	if _weapon_model:
		return _weapon_model.to_global(_weapon_model.get_meta("muzzle", Vector3.ZERO))
	return global_position + Vector3.UP * 1.3


## Бросок: в прицеле — по взгляду, иначе — навесом в точку под курсором (не дальше max_range).
func _throw_grenade() -> void:
	grenades -= 1
	fire_timer = 0.6
	var g: Dictionary = Balance.GRENADE
	var from := eye_position() + Vector3.UP * 0.1
	var v: Vector3
	if ads:
		from += look_dir() * 0.4
		v = look_dir() * float(g.throw_speed) + Vector3.UP * 2.0
	else:
		var to := cursor_ground - global_position
		to.y = 0.0
		if to.length() > float(g.max_range):
			to = to.normalized() * float(g.max_range)
		var target := global_position + to
		from += to.normalized() * 0.4 if to.length() > 0.1 else Vector3.ZERO
		var t := clampf(to.length() / float(g.throw_speed), 0.45, 1.3)
		v = (target - from) / t + Vector3.UP * 0.5 * 9.8 * t
	Grenade.throw(get_tree().current_scene, from, v, get_rid())


func _read_stance() -> void:
	if Input.is_action_just_pressed("crouch"):
		stance = Stance.STAND if stance == Stance.CROUCH else Stance.CROUCH
		_apply_stance()
	if Input.is_action_just_pressed("prone"):
		stance = Stance.STAND if stance == Stance.PRONE else Stance.PRONE
		_apply_stance()
	aiming = Input.is_action_pressed("aim") and not (Raid.current and Raid.current.ui_open())


func _stance_key() -> String:
	match stance:
		Stance.CROUCH:
			return "crouch"
		Stance.PRONE:
			return "prone"
	return "stand"


func _stance_speed() -> float:
	var s: float
	match stance:
		Stance.CROUCH:
			s = Balance.PLAYER_CROUCH_SPEED
		Stance.PRONE:
			s = Balance.PLAYER_PRONE_SPEED
		_:
			s = Balance.PLAYER_SPRINT_SPEED if Input.is_action_pressed("sprint") and not aiming else Balance.PLAYER_WALK_SPEED
	if aiming:
		s *= Balance.PLAYER_ADS_SPEED_SCALE
	return s


## WASD: в прицеле — относительно взгляда (вперёд — куда смотришь), иначе — относительно камеры
## («вверх» на экране — от камеры вглубь).
func _wish_direction() -> Vector3:
	var input := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	if input.length_squared() == 0.0:
		return Vector3.ZERO
	var forward: Vector3
	var right: Vector3
	if ads:
		forward = Vector3(sin(look_yaw), 0.0, cos(look_yaw))
		right = forward.cross(Vector3.UP)
	else:
		var yaw := _camera_rig.rotation.y if _camera_rig else 0.0
		forward = Vector3(-sin(yaw), 0.0, -cos(yaw))
		right = Vector3(cos(yaw), 0.0, -sin(yaw))
	return (right * input.x + forward * -input.y).normalized()


func _face_cursor(delta: float) -> void:
	var to := cursor_ground - global_position
	to.y = 0.0
	if to.length_squared() < 0.04:
		return
	var want := atan2(to.x, to.z)
	_body.rotation.y = lerp_angle(_body.rotation.y, want, minf(1.0, Balance.PLAYER_TURN_SPEED * delta))


func _apply_stance() -> void:
	var key := _stance_key()
	var h: float = Balance.STANCE_HEIGHT[key]
	var shape := _capsule.shape as CapsuleShape3D
	shape.height = h
	shape.radius = minf(Balance.CAPSULE_RADIUS, h * 0.5)
	_capsule.position.y = h * 0.5
	_body.scale.y = h / Balance.STANCE_HEIGHT["stand"]


## Смерть: капсула прячется, падает регдолл, толкнутый от того, кто попал; камера — за телом.
## Эвакуация: тело пропадает, коллизий нет, мародёры больше не видят (не в группе "players").
func _leave_raid() -> void:
	remove_from_group("players")
	visible = false
	collision_layer = 0
	collision_mask = 0
	velocity = Vector3.ZERO
	set_physics_process(false)
	Audio.play("door", global_position)


func _die() -> void:
	var torso := _body.get_node("Torso") as MeshInstance3D
	var mat := torso.get_surface_override_material(0)
	var away := global_position - _last_hit_from
	away.y = 0.0
	away = away.normalized() if away.length() > 0.01 else -Vector3(sin(body_yaw()), 0.0, cos(body_yaw()))
	var push: Dictionary = Balance.RAGDOLL_DEATH_PUSH
	var imp := (away + Vector3.UP * 0.25) * (float(push.base) + float(push.per_damage) * _last_damage)
	var xf := Transform3D(Basis(Vector3.UP, body_yaw()), global_position)
	_ragdoll = Ragdoll.spawn(get_tree().current_scene, xf, velocity, imp, global_position + Vector3.UP * 1.25, mat, mat)
	_body.visible = false
	_hand.visible = false
	collision_layer = 0
	Audio.play("fall", global_position)
	if is_local() and _camera_rig is CameraRig:
		(_camera_rig as CameraRig).set_target(_ragdoll.chest())
